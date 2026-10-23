"""custom_sequence_runner.py — Engine Eksekutor Custom Sequence Job untuk Windows Task Scheduler.

Dapat dipanggil langsung oleh Windows Task Scheduler atau CLI:
python custom_sequence_runner.py --sequence-file custom_sequences/zsmr012_daily_15days.json
"""

import os
import sys
import time
import json
import re
import argparse
from datetime import datetime, timedelta

# Pastikan output stream menggunakan UTF-8 di Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config import DB_CONFIG
from job_runner import run_job, build_job_command


def resolve_dynamic_value(val: str) -> str:
    """Menerjemahkan token parameter dinamis menjadi nilai tanggal/waktu riil saat runtime."""
    if not isinstance(val, str):
        return val

    text = val.strip()
    now = datetime.now()

    # Hari ini
    if text in ("dynamic-today-ymd", "today", "today-ymd"):
        return now.strftime("%Y-%m-%d")
    if text in ("dynamic-today-dmy", "today-dmy"):
        return now.strftime("%d.%m.%Y")

    # Kemarin
    yesterday = now - timedelta(days=1)
    if text in ("dynamic-yesterday-ymd", "yesterday", "yesterday-ymd"):
        return yesterday.strftime("%Y-%m-%d")
    if text in ("dynamic-yesterday-dmy", "yesterday-dmy"):
        return yesterday.strftime("%d.%m.%Y")

    # Awal bulan ini
    if text in ("dynamic-first-day-month-ymd", "dynamic-first-day-ymd"):
        return now.strftime("%Y-%m-01")
    if text in ("dynamic-first-day-month-dmy", "dynamic-first-day-dmy"):
        return now.strftime("01.%m.%Y")

    # N Hari yang lalu (contoh: dynamic-15-days-ago-ymd, dynamic-30-days-ago-dmy)
    m_days = re.match(r"dynamic-(\d+)-days?-ago-(ymd|dmy)", text, re.IGNORECASE)
    if m_days:
        n_days = int(m_days.group(1))
        fmt = m_days.group(2).lower()
        past_dt = now - timedelta(days=n_days)
        return past_dt.strftime("%Y-%m-%d") if fmt == "ymd" else past_dt.strftime("%d.%m.%Y")

    # Waktu sekarang (HH:mm)
    if text in ("dynamic-now-time", "now-time"):
        return now.strftime("%H:%M")

    # Waktu sekarang + N Menit (contoh: dynamic-now-plus-1m, dynamic-now-time-plus-2m)
    m_time = re.match(r"dynamic-now(?:-time)?-plus-(\d+)m", text, re.IGNORECASE)
    if m_time:
        plus_m = int(m_time.group(1))
        sched_time = now + timedelta(minutes=plus_m)
        return sched_time.strftime("%H:%M")

    return text


def resolve_dynamic_params(params: dict) -> dict:
    """Menguraikan seluruh parameter dalam dictionary dengan token dinamis."""
    resolved = {}
    for k, v in params.items():
        if isinstance(v, str):
            resolved[k] = resolve_dynamic_value(v)
        else:
            resolved[k] = v
    return resolved


def execute_sequence_file(
    sequence_file: str,
    db_config: dict | None = None,
    stop_on_error: bool = True,
) -> int:
    """Membaca file konfigurasi sequence JSON dan mengeksekusi langkah-langkahnya."""
    if not os.path.exists(sequence_file):
        print(f"[ERROR] File konfigurasi sequence tidak ditemukan: {sequence_file}")
        return 1

    try:
        with open(sequence_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[ERROR] Gagal membaca file JSON sequence: {e}")
        return 1

    seq_name = data.get("name", os.path.basename(sequence_file))
    seq_desc = data.get("description", "Custom Sequence Execution")
    items = data.get("items", [])

    print("=" * 72)
    print(f"  [SEQUENCE RUNNER] MEMULAI: {seq_name}")
    print(f"  Deskripsi       : {seq_desc}")
    print(f"  Total Langkah   : {len(items)} Step")
    print(f"  Waktu Mulai     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 72)

    total_steps = len(items)
    overall_success = True

    for idx, item in enumerate(items):
        step_num = idx + 1
        item_type = item.get("type", "job").lower()

        # ── Tipe 1: Step Jeda Waktu (Wait / Delay) ──
        if item_type in ("wait", "delay", "sleep"):
            seconds = int(item.get("seconds", 60))
            desc = item.get("desc", f"Menunggu jeda {seconds} detik...")
            print(f"\n>>> [STEP {step_num}/{total_steps}] ⏳ JEDA WAKTU: {desc} ({seconds}s)")
            remaining = seconds
            while remaining > 0:
                sleep_chunk = min(remaining, 10)
                time.sleep(sleep_chunk)
                remaining -= sleep_chunk
                if remaining > 0:
                    print(f"    [WAIT] Masih menunggu... {remaining} detik tersisa.")
            print(f"    [WAIT OK] Selesai menunggu {seconds} detik.")
            continue

        # ── Tipe 2: Step Eksekusi Job SAP ──
        job_name = item.get("name", "")
        raw_params = item.get("params", {})
        resolved_params = resolve_dynamic_params(raw_params)

        print(f"\n>>> [STEP {step_num}/{total_steps}] 🚀 EKSEKUSI JOB: {job_name}")
        for p_k, p_v in resolved_params.items():
            if str(p_k).startswith("sch-"):
                continue
            if p_v != raw_params.get(p_k):
                print(f"    • {p_k} = {p_v}  (dinamis dari: {raw_params.get(p_k)})")
            else:
                print(f"    • {p_k} = {p_v}")

        def _log_line(tag: str, text: str):
            print(f"[{tag}]  {text}")
            sys.stdout.flush()

        step_ok = run_job(
            name=job_name,
            params=resolved_params,
            db_config=db_config or DB_CONFIG,
            on_log_line=_log_line,
        )

        if not step_ok:
            print(f"\n[ERROR] Step #{step_num} ({job_name}) GAGAL dieksekusi!")
            if stop_on_error:
                print("[ABORT] Eksekusi sequence dihentikan karena stop_on_error=True.")
                overall_success = False
                break
        else:
            print(f"[OK] Step #{step_num} ({job_name}) selesai dengan sukses.")

    print("\n" + "=" * 72)
    if overall_success:
        print(f"  [SEQUENCE RUNNER] SELESAI: SEMUA LANGKAH TUNTAS BERHASIL [SUCCESS]")
    else:
        print(f"  [SEQUENCE RUNNER] SELESAI: TERDAPAT LANGKAH YANG GAGAL [FAILED]")
    print(f"  Waktu Selesai   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 72)

    return 0 if overall_success else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Custom Sequence Runner for Windows Task Scheduler")
    parser.add_argument("--sequence-file", required=True, help="Path ke file JSON sequence")
    parser.add_argument("--db-server", default=None)
    parser.add_argument("--db-user", default=None)
    parser.add_argument("--db-pwd", default=None)
    parser.add_argument("--db-name", default=None)
    parser.add_argument("--ignore-errors", action="store_true", help="Tetap lanjutkan sequence jika ada step yang gagal")

    args = parser.parse_args()

    db_cfg = None
    if args.db_server:
        db_cfg = {
            "server": args.db_server,
            "user": args.db_user or "",
            "pwd": args.db_pwd or "",
            "name": args.db_name or DB_CONFIG.get("name", "DesSy"),
        }

    code = execute_sequence_file(
        sequence_file=args.sequence_file,
        db_config=db_cfg,
        stop_on_error=not args.ignore_errors,
    )
    sys.exit(code)
