"""scripts/backup_zsmr012_range.py — Script Backup Data ZSMR012 Berdasarkan Rentang Tanggal.

Mencadangkan data dari tabel dbo.ZSMR012 pada rentang tanggal target (default:
1 September 2026 s/d 18 November 2026) ke tabel cadangan
(default: dbo.ZSMR012_BACKUP_20260901_20261118) sebagai safety net sebelum
operasi delete & replace dari file Excel.

Fitur:
  - Parameter fleksibel: --start-date, --end-date, --backup-table, --overwrite, --dry-run.
  - Safe date filtering: [ExecutionStart] >= start_date AND [ExecutionStart] < end_date + 1 day.
  - Verifikasi otomatis: Validasi jumlah baris sumber vs backup setelah SELECT INTO.
  - Proteksi overwrite: Mencegah penghapusan tabel backup yang sudah ada kecuali flag --overwrite diberikan.
"""

import sys
import os
import argparse
import time
from datetime import datetime, timedelta

# Pastikan output stream menggunakan UTF-8 di Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Tambahkan root path ke sys.path agar dapat mengimpor db_utils dan config
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import DB_CONFIG
from db_utils import get_connection_with_retry


def log(msg: str) -> None:
    """Cetak log dengan timestamp terformat."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)


def format_table_name(table_name: str) -> str:
    """Format dan validasi nama tabel SQL Server dengan kurung siku aman."""
    cleaned = table_name.strip()
    parts = [p.strip("[]") for p in cleaned.split(".")]
    for p in parts:
        if not p.isidentifier():
            raise ValueError(f"Nama identifier tabel tidak valid: {p}")
    return ".".join(f"[{p}]" for p in parts)


def check_table_exists(cursor, table_name: str) -> bool:
    """Periksa apakah tabel sudah ada di SQL Server."""
    cursor.execute("SELECT OBJECT_ID(?, 'U')", (table_name,))
    row = cursor.fetchone()
    return row is not None and row[0] is not None


def get_table_row_count(cursor, formatted_table_name: str) -> int:
    """Ambil total baris dari tabel."""
    cursor.execute(f"SELECT COUNT(*) FROM {formatted_table_name}")
    return cursor.fetchone()[0]


def run_backup(
    start_date: str = "2026-09-01",
    end_date: str = "2026-11-18",
    backup_table: str | None = None,
    overwrite: bool = False,
    dry_run: bool = False,
) -> bool:
    """Jalankan proses backup data ZSMR012 untuk rentang tanggal tertentu."""
    start_time = time.time()

    # 1. Validasi & Parsing Tanggal
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
    except ValueError as e:
        log(f"[ERROR] Format --start-date salah (harus YYYY-MM-DD): {start_date}")
        raise e

    try:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError as e:
        log(f"[ERROR] Format --end-date salah (harus YYYY-MM-DD): {end_date}")
        raise e

    if start_dt > end_dt:
        raise ValueError(f"--start-date ({start_dt}) tidak boleh lebih besar dari --end-date ({end_dt})")

    next_day_dt = end_dt + timedelta(days=1)
    start_param = start_dt.strftime("%Y-%m-%d")
    next_day_param = next_day_dt.strftime("%Y-%m-%d")

    # Tentukan nama tabel backup default jika tidak ditentukan
    if not backup_table:
        backup_table = f"dbo.ZSMR012_BACKUP_{start_dt.strftime('%Y%m%d')}_{end_dt.strftime('%Y%m%d')}"

    formatted_backup_table = format_table_name(backup_table)
    raw_table_lookup = backup_table.strip("[]")

    log("=" * 70)
    log("ZSMR012 DATA BACKUP UTILITY")
    log("=" * 70)
    log(f"Tabel Sumber     : dbo.ZSMR012")
    log(f"Tabel Backup     : {formatted_backup_table}")
    log(f"Rentang Tanggal  : {start_param} s/d {end_dt.strftime('%Y-%m-%d')} (inklusif)")
    log(f"Filter Kriteria  : [ExecutionStart] >= '{start_param}' AND [ExecutionStart] < '{next_day_param}'")
    log(f"Mode Operasi     : {'DRY-RUN (SIMULASI)' if dry_run else 'LIVE EXECUTION'}")
    log(f"Opsi Overwrite   : {overwrite}")
    log("-" * 70)

    conn = get_connection_with_retry()
    try:
        cursor = conn.cursor()

        # 2. Hitung jumlah baris sumber yang memenuhi kriteria
        count_query = (
            "SELECT COUNT(*) FROM dbo.ZSMR012 "
            "WHERE [ExecutionStart] >= ? AND [ExecutionStart] < ?"
        )
        cursor.execute(count_query, (start_param, next_day_param))
        source_count = cursor.fetchone()[0]
        log(f"Jumlah baris sumber di dbo.ZSMR012 yang cocok: {source_count:,} baris")

        # 3. Periksa status keberadaan tabel backup
        table_exists = check_table_exists(cursor, raw_table_lookup)

        if table_exists:
            existing_backup_rows = get_table_row_count(cursor, formatted_backup_table)
            log(f"[PERINGATAN] Tabel backup {formatted_backup_table} sudah ada di database ({existing_backup_rows:,} baris).")

            if not overwrite:
                if not dry_run:
                    log(f"[INFO] Operasi dihentikan secara aman tanpa mengubah data.")
                    log(f"[INFO] Jika ingin menimpa (DROP & RECREATE), tambahkan parameter --overwrite.")
                    return False
                else:
                    log(f"[INFO] [DRY-RUN] Tabel backup sudah ada. Eksekusi LIVE nantinya membutuhkan flag --overwrite.")
            else:
                log(f"[INFO] Flag --overwrite aktif. Tabel lama akan di-DROP sebelum backup.")
                if not dry_run:
                    log(f"Menjalankan: DROP TABLE {formatted_backup_table}...")
                    cursor.execute(f"DROP TABLE {formatted_backup_table}")
                    conn.commit()
                    log("Tabel lama berhasil di-DROP.")
        else:
            log(f"Status tabel backup {formatted_backup_table}: Belum ada di database (aman dibuat).")

        # 4. Evaluasi Mode DRY-RUN
        if dry_run:
            log("-" * 70)
            log("[DRY-RUN] Ringkasan Simulasi:")
            log(f"  * Baris yang akan dicadangkan : {source_count:,} baris")
            log(f"  * Target tabel               : {formatted_backup_table}")
            log(f"  * Status overwrite           : {overwrite} (Tabel exists: {table_exists})")
            log("[DRY-RUN] Simulasi selesai. Tidak ada tabel yang dibuat atau diubah di database.")
            log("=" * 70)
            return True

        # 5. Eksekusi Backup Riil (SELECT INTO)
        if source_count == 0:
            log("[PERINGATAN] Tidak ada baris yang cocok pada rentang tanggal tersebut. Backup dibatalkan.")
            return False

        log(f"Mengeksekusi pencadangan: SELECT * INTO {formatted_backup_table} FROM dbo.ZSMR012...")
        backup_query = (
            f"SELECT * INTO {formatted_backup_table} "
            f"FROM dbo.ZSMR012 "
            f"WHERE [ExecutionStart] >= ? AND [ExecutionStart] < ?"
        )
        t_query_start = time.time()
        cursor.execute(backup_query, (start_param, next_day_param))
        conn.commit()
        t_query_duration = time.time() - t_query_start
        log(f"Query SELECT INTO selesai dalam {t_query_duration:.2f} detik.")

        # 6. Verifikasi Integritas Data Backup
        backup_count = get_table_row_count(cursor, formatted_backup_table)
        log(f"Verifikasi baris di tabel backup {formatted_backup_table}: {backup_count:,} baris")

        if backup_count != source_count:
            error_msg = (
                f"VERIFIKASI GAGAL! Jumlah baris sumber ({source_count:,}) "
                f"tidak sesuai dengan baris di tabel backup ({backup_count:,})."
            )
            log(f"[FATAL ERROR] {error_msg}")
            raise RuntimeError(error_msg)

        duration = time.time() - start_time
        log("=" * 70)
        log(f"[SUKSES] Backup berhasil dan terverifikasi 100% identik!")
        log(f"  * Total baris dicadangkan : {backup_count:,} baris")
        log(f"  * Tabel cadangan          : {formatted_backup_table}")
        log(f"  * Durasi total proses     : {duration:.2f} detik")
        log("=" * 70)
        return True

    except Exception as e:
        conn.rollback()
        log(f"[ERROR] Terjadi kegagalan saat proses backup: {e}")
        raise e
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Backup data dbo.ZSMR012 pada rentang tanggal tertentu sebelum operasi replace.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="2026-09-01",
        help="Tanggal awal inklusif (format: YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default="2026-11-18",
        help="Tanggal akhir inklusif (format: YYYY-MM-DD)",
    )
    parser.add_argument(
        "--backup-table",
        type=str,
        default="dbo.ZSMR012_BACKUP_20260901_20261118",
        help="Nama tabel target cadangan",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Hapus tabel backup jika sudah ada sebelumnya",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Simulasi hitungan tanpa membuat tabel backup",
    )

    args = parser.parse_args()

    success = run_backup(
        start_date=args.start_date,
        end_date=args.end_date,
        backup_table=args.backup_table,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )

    if not success and not args.dry_run:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
