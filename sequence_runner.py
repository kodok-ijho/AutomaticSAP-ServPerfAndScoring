"""sequence_runner.py — Engine Eksekusi Urutan (Pipeline) Job SAP Automation.

Memungkinkan eksekusi berantai beberapa job secara sekuensial (satu per satu)
dalam background thread, dengan event callbacks untuk status per step,
streaming log langsung, dan kemampuan pembatalan (abort).
"""

import time
import subprocess
from datetime import datetime
from typing import Callable
from job_runner import run_job, stop_job, classify_log_tag, build_job_command
from custom_sequence_runner import resolve_dynamic_params


class SequenceRunner:
    """Mengelola eksekusi sekuensial antrean job."""

    def __init__(
        self,
        sequence_items: list[dict],
        db_config: dict | None = None,
        stop_on_error: bool = True,
        on_step_start: Callable[[int, int, str], None] | None = None,
        on_log_line: Callable[[str, str], None] | None = None,
        on_step_end: Callable[[int, int, str, bool, str], None] | None = None,
        on_sequence_complete: Callable[[bool, str], None] | None = None,
    ):
        self.sequence_items = sequence_items
        self.db_config = db_config
        self.stop_on_error = stop_on_error
        self.on_step_start = on_step_start
        self.on_log_line = on_log_line
        self.on_step_end = on_step_end
        self.on_sequence_complete = on_sequence_complete

        self._current_proc: subprocess.Popen | None = None
        self._is_aborted = False

    def stop(self) -> None:
        """Batalkan eksekusi sequence yang sedang berjalan."""
        self._is_aborted = True
        if self._current_proc:
            try:
                stop_job(self._current_proc)
            except Exception:
                pass

    def run(self) -> bool:
        """Jalankan antrean job secara sekuensial (blocking — jalankan di background thread)."""
        total_steps = len(self.sequence_items)
        if total_steps == 0:
            if self.on_sequence_complete:
                self.on_sequence_complete(True, "Tidak ada job dalam antrean sequence.")
            return True

        def _log(tag: str, text: str):
            if self.on_log_line:
                self.on_log_line(tag, text)

        _log("HEADER", f"{'='*68}\n  MEMULAI CUSTOM SEQUENCE ({total_steps} JOB)\n{'='*68}")
        overall_success = True
        seq_start_time = time.time()

        for idx, item in enumerate(self.sequence_items):
            if self._is_aborted:
                _log("WARN", f"[ABORT] Urutan dibatalkan oleh pengguna sebelum Step #{idx + 1}.")
                overall_success = False
                break

            job_name = item.get("name", "")
            if not job_name:
                if item.get("type") in ("wait", "delay") or ((item.get("name") or "").startswith("⏳")):
                    sec = item.get("seconds", 60)
                    job_name = f"⏳ JEDA WAKTU ({sec}s)"
                else:
                    job_name = f"Job #{idx + 1}"
            params = item.get("params", {})

            if self.on_step_start:
                self.on_step_start(idx, total_steps, job_name)

            _log("INFO", f"\n>>> [STEP {idx + 1}/{total_steps}] Memulai: {job_name}")
            step_start_time = time.time()

            # Dukungan Step Tipe Wait / Jeda Waktu
            if item.get("type") in ("wait", "delay") or job_name.startswith("⏳"):
                seconds = int(item.get("seconds", 60))
                desc = item.get("desc", f"Jeda waktu {seconds} detik")
                _log("INFO", f"[WAIT] {desc}...")
                remaining = seconds
                while remaining > 0 and not self._is_aborted:
                    chunk = min(remaining, 1)
                    time.sleep(chunk)
                    remaining -= chunk
                step_success = not self._is_aborted
                if step_success:
                    _log("OK", f"[WAIT OK] Selesai menunggu {seconds} detik.")
            else:
                # Resolusi parameter dinamis
                resolved_params = resolve_dynamic_params(params)

                def _proc_started(proc):
                    self._current_proc = proc

                def _proc_ended():
                    self._current_proc = None

                step_success = run_job(
                    name=job_name,
                    params=resolved_params,
                    db_config=self.db_config,
                    on_log_line=self.on_log_line,
                    on_proc_started=_proc_started,
                    on_proc_ended=_proc_ended,
                )

            step_elapsed = time.time() - step_start_time
            m, s = divmod(int(step_elapsed), 60)
            elapsed_str = f"{m:02d}:{s:02d}"

            if self._is_aborted:
                _log("WARN", f"[STEP {idx + 1}] Dibatalkan oleh pengguna ({elapsed_str}).")
                if self.on_step_end:
                    self.on_step_end(idx, total_steps, job_name, False, elapsed_str)
                overall_success = False
                break

            if self.on_step_end:
                self.on_step_end(idx, total_steps, job_name, step_success, elapsed_str)

            if not step_success:
                _log("ERROR", f"[STEP {idx + 1}] GAGAL: {job_name} ({elapsed_str})")
                overall_success = False
                if self.stop_on_error:
                    _log("ERROR", "[SEQUENCE STOP] Penghentian sequence diaktifkan. Sisa job dibatalkan.")
                    break
            else:
                _log("OK", f"[STEP {idx + 1}] SUKSES: {job_name} ({elapsed_str})")

        total_elapsed = time.time() - seq_start_time
        tm, ts = divmod(int(total_elapsed), 60)
        tot_elapsed_str = f"{tm:02d}:{ts:02d}"

        result_tag = "OK" if overall_success else ("WARN" if self._is_aborted else "ERROR")
        summary_status = "SUKSES" if overall_success else ("DIBATALKAN" if self._is_aborted else "GAGAL")
        _log(result_tag, f"\n{'='*68}\n  SEQUENCE {summary_status} (Total Waktu: {tot_elapsed_str})\n{'='*68}")

        if self.on_sequence_complete:
            self.on_sequence_complete(overall_success, summary_status)

        return overall_success
