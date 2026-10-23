"""schedule_iw73.py — Penjadwalan Background Job IW73 per N Hari.

Memecah rentang tanggal (Start Date s/d End Date) menjadi batch per-N hari
(default: 5 hari), lalu menjadwalkan eksekusi masing-masing batch sebagai
SAP Background Job dengan jarak interval waktu teratur (dalam satuan menit).
"""

import os
import sys
import time
import argparse
from datetime import datetime, timedelta

# Pastikan output stream menggunakan UTF-8 di Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from sap_utils import ensure_sap_logged_in, run_vbs


def parse_date_flexibly(date_input: str) -> datetime:
    """Mendukung berbagai format input tanggal seperti YYYY-MM-DD, DD.MM.YYYY, DD/MM/YYYY, dll."""
    text = str(date_input).strip()
    if not text or text.lower() in ("today", "now", "dynamic-today-ymd", "dynamic-today-dmy"):
        return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    formats = [
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d%m%y",
        "%d%m%Y",
        "%Y%m%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"Format tanggal tidak dikenali: '{date_input}'. Gunakan format YYYY-MM-DD atau DD.MM.YYYY.")


def format_sap_date(dt: datetime, date_format: str = "ddMMyy") -> str:
    """Format datetime ke string tanggal yang diterima oleh SAP GUI."""
    if date_format == "dd.MM.yyyy":
        return dt.strftime("%d.%m.%Y")
    # Default ddMMyy (sesuai rekaman VBS IW73, contoh 010126 atau 010116)
    return dt.strftime("%d%m%y")


def generate_date_chunks(
    start_dt: datetime, end_dt: datetime, chunk_days: int
) -> list[tuple[datetime, datetime]]:
    """Memecah rentang tanggal menjadi daftar batch (chunk_start, chunk_end) per n hari inklusif."""
    if chunk_days < 1:
        raise ValueError(f"chunk_days harus minimal 1, nilai diberikan: {chunk_days}")
    if start_dt > end_dt:
        raise ValueError(f"start_date ({start_dt.strftime('%Y-%m-%d')}) tidak boleh lebih besar dari end_date ({end_dt.strftime('%Y-%m-%d')})")

    chunks: list[tuple[datetime, datetime]] = []
    curr = start_dt
    while curr <= end_dt:
        c_end = min(curr + timedelta(days=chunk_days - 1), end_dt)
        chunks.append((curr, c_end))
        curr = c_end + timedelta(days=1)
    return chunks


def calculate_job_schedules(
    base_sched_dt: datetime, num_jobs: int, interval_minutes: int
) -> list[datetime]:
    """Menghitung waktu schedule SAP BG Job untuk setiap batch berdasarkan interval menit."""
    schedules: list[datetime] = []
    for i in range(num_jobs):
        sched_time = base_sched_dt + timedelta(minutes=i * interval_minutes)
        schedules.append(sched_time)
    return schedules


def main(
    start_date: str,
    end_date: str,
    chunk_days: int = 5,
    sched_start_date: str = "dynamic-today-ymd",
    sched_start_time: str = "17:45",
    interval_minutes: int = 5,
    delay_seconds: int = 5,
    vbs_path: str = "vbs\\IW73-per 5 hari.vbs",
    date_format: str = "ddMMyy",
    dry_run: bool = False,
    db_config: dict | None = None,
) -> int:
    print("=" * 68)
    print("  [JOB] CREATE BG JOB IW73 – Split N Hari Scheduler")
    print(f"  Tanggal Awal Data  : {start_date}")
    print(f"  Tanggal Akhir Data : {end_date}")
    print(f"  Pecah per N Hari   : {chunk_days} hari")
    print(f"  Tanggal Sched SAP  : {sched_start_date}")
    print(f"  Jam Mulai Sched    : {sched_start_time}")
    print(f"  Interval Antar Job : {interval_minutes} menit")
    print(f"  Delay Submit SAP   : {delay_seconds} detik")
    print(f"  VBS Path           : {vbs_path}")
    print(f"  Format Tanggal SAP : {date_format}")
    print(f"  Mode Simulasi      : {'YA (Dry Run)' if dry_run else 'TIDAK (Eksekusi SAP Langsung)'}")
    print("=" * 68)

    # 1. Validasi & Parsing Tanggal
    try:
        start_dt = parse_date_flexibly(start_date)
        end_dt = parse_date_flexibly(end_date)
        chunks = generate_date_chunks(start_dt, end_dt, chunk_days)
    except Exception as e:
        print(f"[ERROR] Validasi rentang tanggal gagal: {e}")
        return 1

    total_chunks = len(chunks)
    total_days = (end_dt - start_dt).days + 1
    print(f"[INFO] Rentang total: {total_days} hari ({start_dt.strftime('%d.%m.%Y')} s/d {end_dt.strftime('%d.%m.%Y')}).")
    print(f"[INFO] Terbagi menjadi {total_chunks} batch background job.")

    # 2. Parsing Waktu Mulai Schedule
    try:
        sched_base_date = parse_date_flexibly(sched_start_date)
        time_parts = sched_start_time.strip().split(":")
        h = int(time_parts[0])
        m = int(time_parts[1]) if len(time_parts) > 1 else 0
        base_sched_dt = sched_base_date.replace(hour=h, minute=m, second=0, microsecond=0)
    except Exception as e:
        print(f"[WARN] Parsing sched_start_time '{sched_start_time}' gagal: {e}. Menggunakan jam 17:45 hari ini.")
        base_sched_dt = datetime.now().replace(hour=17, minute=45, second=0, microsecond=0)

    schedules = calculate_job_schedules(base_sched_dt, total_chunks, interval_minutes)

    # 3. Tampilkan Jadwal Batch
    print("\n--- Rincian Rencana Background Job IW73 ---")
    for idx, ((c_start, c_end), sched_dt) in enumerate(zip(chunks, schedules), start=1):
        s_date_str = format_sap_date(c_start, date_format)
        e_date_str = format_sap_date(c_end, date_format)
        sap_sched_date = format_sap_date(sched_dt, date_format)
        sap_sched_time = sched_dt.strftime("%H%M")
        days_in_batch = (c_end - c_start).days + 1
        print(
            f"  Batch {idx:2d}/{total_chunks:2d} | "
            f"Data: {c_start.strftime('%d.%m.%Y')} s/d {c_end.strftime('%d.%m.%Y')} ({days_in_batch} hr) "
            f"[GSTRP: {s_date_str}-{e_date_str}] -> "
            f"Sched: {sched_dt.strftime('%d.%m.%Y')} {sched_dt.strftime('%H:%M')} [SAP: {sap_sched_date} {sap_sched_time}]"
        )
    print("-------------------------------------------\n")

    if dry_run:
        print("[DRY-RUN] Simulasi selesai. Tidak ada VBScript yang dieksekusi ke SAP GUI.")
        return 0

    # 4. Verifikasi Keberadaan VBScript & Login SAP GUI
    resolved_vbs = os.path.abspath(os.path.expandvars(vbs_path))
    if not os.path.exists(resolved_vbs):
        print(f"[ERROR] File VBScript tidak ditemukan di: {resolved_vbs}")
        return 1

    print("[SAP] Memeriksa status koneksi SAP GUI...")
    login_vbs = os.path.join(os.path.dirname(resolved_vbs), "LoginSAP.vbs")
    if not os.path.exists(login_vbs):
        login_vbs = "vbs\\LoginSAP.vbs"

    sap_ready = ensure_sap_logged_in(login_vbs)
    if not sap_ready:
        print("[ERROR] SAP GUI belum siap atau gagal login otomatis. Proses dibatalkan.")
        return 1

    # 5. Eksekusi Batch Bertahap
    successful_count = 0
    failed_count = 0

    for idx, ((c_start, c_end), sched_dt) in enumerate(zip(chunks, schedules), start=1):
        s_date_str = format_sap_date(c_start, date_format)
        e_date_str = format_sap_date(c_end, date_format)
        sap_sched_date = format_sap_date(sched_dt, date_format)
        sap_sched_time = sched_dt.strftime("%H%M")

        print(
            f"\n>>> [BATCH {idx}/{total_chunks}] Menjadwalkan IW73 "
            f"({c_start.strftime('%d.%m.%Y')} s/d {c_end.strftime('%d.%m.%Y')}) "
            f"untuk dieksekusi pukul {sched_dt.strftime('%H:%M')}..."
        )

        vbs_args = [s_date_str, e_date_str, sap_sched_date, sap_sched_time]
        vbs_ok = run_vbs(resolved_vbs, vbs_args, interactive=False)

        if vbs_ok:
            successful_count += 1
            print(f"[OK] Batch {idx}/{total_chunks} berhasil diserahkan ke SAP Background Job.")
        else:
            failed_count += 1
            print(f"[WARN] Batch {idx}/{total_chunks} mengalami kendala saat eksekusi VBS.")

        # Delay antar batch (kecuali batch terakhir)
        if idx < total_chunks and delay_seconds > 0:
            print(f"[WAIT] Menunggu {delay_seconds} detik sebelum batch berikutnya...")
            time.sleep(delay_seconds)

    print("\n" + "=" * 68)
    print(f"  [SELESAI] Penjadwalan Job IW73: {successful_count} Berhasil, {failed_count} Gagal (Total {total_chunks})")
    print("=" * 68)

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Penjadwalan Background Job IW73 per N Hari di SAP GUI."
    )
    parser.add_argument(
        "--start-date",
        required=True,
        help="Tanggal awal data (format YYYY-MM-DD atau DD.MM.YYYY, misal: 2026-01-01)",
    )
    parser.add_argument(
        "--end-date",
        required=True,
        help="Tanggal akhir data (format YYYY-MM-DD atau DD.MM.YYYY, misal: 2026-01-31)",
    )
    parser.add_argument(
        "--chunk-days",
        type=int,
        default=5,
        help="Jumlah hari per-batch pemecahan background job (default: 5)",
    )
    parser.add_argument(
        "--sched-start-date",
        default="dynamic-today-ymd",
        help="Tanggal eksekusi job pertama di server SAP (default: hari ini)",
    )
    parser.add_argument(
        "--sched-start-time",
        default="17:45",
        help="Jam mulai eksekusi job pertama di server SAP (format HH:mm, default: 17:45)",
    )
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=5,
        help="Interval waktu antar background job dalam satuan menit (default: 5)",
    )
    parser.add_argument(
        "--delay-seconds",
        type=int,
        default=5,
        help="Jeda waktu antar submit batch ke SAP GUI dalam detik (default: 5)",
    )
    parser.add_argument(
        "--vbs-path",
        default="vbs\\IW73-per 5 hari.vbs",
        help="Path file VBScript otomasi IW73 (default: vbs\\IW73-per 5 hari.vbs)",
    )
    parser.add_argument(
        "--date-format",
        default="ddMMyy",
        help="Format tanggal yang dikirim ke parameter VBS/SAP (default: ddMMyy)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulasi jadwal tanpa mengeksekusi VBScript ke SAP GUI",
    )

    args = parser.parse_args()

    exit_code = main(
        start_date=args.start_date,
        end_date=args.end_date,
        chunk_days=args.chunk_days,
        sched_start_date=args.sched_start_date,
        sched_start_time=args.sched_start_time,
        interval_minutes=args.interval_minutes,
        delay_seconds=args.delay_seconds,
        vbs_path=args.vbs_path,
        date_format=args.date_format,
        dry_run=args.dry_run,
    )
    sys.exit(exit_code)
