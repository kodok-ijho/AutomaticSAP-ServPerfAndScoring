"""job_runner.py — Service layer bersama untuk eksekusi job SAP Automation.

Menghilangkan duplikasi antara dashboard.py (Tkinter/sync) dan
web_dashboard.py (FastAPI/async) untuk:
  - Membangun command subprocess
  - Mengklasifikasi tag log (ERROR/OK/WARN/INFO)
  - Menghentikan proses (taskkill)
  - Menjalankan job secara sinkron (untuk desktop) atau memberi
    building block untuk async (untuk web)

Pemakaian dari desktop dashboard:
    from job_runner import run_job, stop_job, classify_log_tag

Pemakaian dari web dashboard:
    from job_runner import build_job_command, classify_log_tag, stop_job
"""

import os
import sys
import subprocess
from datetime import datetime
from typing import Callable

# Pastikan output stream menggunakan UTF-8 di Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from job_definitions import SCRIPTS, build_cli_args


# ---------------------------------------------------------------------------
#  Konstanta Tag
# ---------------------------------------------------------------------------

_ERROR_WORDS = ("error", "gagal", "failed", "critical")
_OK_WORDS = ("berhasil", "success", "selesai")
_WARN_WORDS = ("warn", "peringatan")


# ---------------------------------------------------------------------------
#  Konstanta Status Job
# ---------------------------------------------------------------------------

STATUS_IDLE = "idle"
STATUS_RUNNING = "running"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"

# Label tampilan untuk UI
STATUS_DISPLAY = {
    STATUS_IDLE:    "Idle",
    STATUS_RUNNING: "Running",
    STATUS_SUCCESS: "Success",
    STATUS_FAILED:  "Failed",
}


# ---------------------------------------------------------------------------
#  Utilitas
# ---------------------------------------------------------------------------

def classify_log_tag(line: str) -> str:
    """Klasifikasi baris log menjadi tag: ERROR, OK, WARN, atau INFO.

    Digunakan oleh kedua dashboard untuk pewarnaan log yang konsisten.
    """
    lower = line.lower()
    if any(w in lower for w in _ERROR_WORDS):
        return "ERROR"
    if any(w in lower for w in _OK_WORDS):
        return "OK"
    if any(w in lower for w in _WARN_WORDS):
        return "WARN"
    return "INFO"


def build_job_command(
    name: str,
    params: dict,
    db_config: dict | None = None,
) -> tuple[str, list[str]]:
    """Bangun command line untuk menjalankan job.

    Returns:
        Tuple (script_path, full_args_list) di mana full_args_list adalah
        [sys.executable, script_path, ...extra_args].

    Raises:
        FileNotFoundError: Jika file script tidak ditemukan.
    """
    info = SCRIPTS[name]
    script_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), info["file"]
    )
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Script tidak ditemukan: {script_path}")

    extra_args = build_cli_args(name, params, db_config=db_config)
    full_cmd = [sys.executable, script_path] + extra_args
    return script_path, full_cmd


# ---------------------------------------------------------------------------
#  Stop Job
# ---------------------------------------------------------------------------

def stop_job(proc: subprocess.Popen | None) -> None:
    """Hentikan subprocess yang sedang berjalan beserta child-nya."""
    if proc is None:
        return
    try:
        pid = proc.pid
        if pid:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                check=False,
            )
    except Exception:
        pass


# ---------------------------------------------------------------------------
#  Sync Runner (Desktop / Thread)
# ---------------------------------------------------------------------------

def run_job(
    name: str,
    params: dict,
    db_config: dict | None = None,
    on_log_line: Callable[[str, str], None] | None = None,
    on_proc_started: Callable | None = None,
    on_proc_ended: Callable | None = None,
) -> bool:
    """Jalankan job secara sinkron (blocking) — cocok untuk thread desktop.

    Alur:
      1. Build command dari SCRIPTS + params.
      2. Jalankan subprocess.Popen (stdout PIPE, stderr merged).
      3. Stream setiap baris stdout ke ``on_log_line(tag, line)``.
      4. Return True jika exit code 0, False jika gagal.

    Args:
        name: Nama job (key di SCRIPTS).
        params: Dict {arg_name: value} dari form user.
        db_config: Konfigurasi database (server, user, pwd, name).
        on_log_line: Callback ``(tag: str, line: str) -> None``
                     dipanggil untuk setiap baris output.
        on_proc_started: Callback ``(proc: subprocess.Popen) -> None``
                         dipanggil segera setelah proses dimulai (untuk tracking Stop).
        on_proc_ended: Callback ``() -> None``
                       dipanggil setelah proses selesai (untuk cleanup).

    Returns:
        True jika job berhasil (returncode == 0), False jika gagal.
    """
    def _log(tag: str, text: str):
        if on_log_line:
            on_log_line(tag, text)

    try:
        script_path, full_cmd = build_job_command(name, params, db_config)
    except FileNotFoundError as e:
        _log("ERROR", str(e))
        return False

    start_time = datetime.now().strftime("%H:%M:%S")
    info = SCRIPTS[name]
    extra_args = full_cmd[2:]  # skip sys.executable & script_path
    cmd_display = f"python {info['file']} " + " ".join(extra_args)

    _log("HEADER",
         f"{'-' * 62}\n"
         f"  JOB    : {name}\n"
         f"  START  : {start_time}\n"
         f"  CMD    : {cmd_display}\n"
         f"{'-' * 62}")

    ok = True
    proc = None
    try:
        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8"
        child_env["PYTHONUTF8"] = "1"

        proc = subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=os.path.dirname(script_path),
            env=child_env,
        )
        if on_proc_started:
            on_proc_started(proc)
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            tag = classify_log_tag(line)
            _log(tag, line)
        proc.wait()
        ok = proc.returncode == 0
    except Exception as exc:
        _log("ERROR", f"Gagal menjalankan proses: {exc}")
        ok = False
    finally:
        if on_proc_ended:
            on_proc_ended()

    end_time = datetime.now().strftime("%H:%M:%S")
    result = "SUCCESS [OK]" if ok else "FAILED [ERROR]"

    _log("HEADER",
         f"{'-' * 62}\n"
         f"  SELESAI: {result}   pukul {end_time}\n"
         f"{'-' * 62}")

    return ok
