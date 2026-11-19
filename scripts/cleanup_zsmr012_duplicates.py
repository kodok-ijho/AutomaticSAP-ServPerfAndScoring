"""scripts/cleanup_zsmr012_duplicates.py — Script Pembersihan Data Duplikat Existing di Database DesSy.

Deskripsi:
  Mendeteksi dan membersihkan data duplikat existing di tabel dbo.ZSMR012 SQL Server
  secara aman dan bertahap dengan partisi composite key transaksi:
    [Order] + [ActivityType] + [ExecutionStart] + [ActualStart] (Time: HH:mm:ss)

Prioritas record yang dipertahankan (rn = 1):
  1. Record dengan ConfirmationCounter valid (tidak NULL dan bukan string kosong).
  2. Record dengan tanggal input terbaru (EnteredOn DESC).

Fitur Keamanan:
  - Default mode: DRY-RUN (simulasi aman, tidak ada data yang dihapus tanpa flag --execute).
  - Batching: Penghapusan dilakukan bertahap (default 5.000 baris per commit)
    untuk menghindari lock escalation dan transaction log bloat pada SQL Server.
  - Verifikasi: Pengecekan ulang otomatis setelah proses penghapusan selesai.
"""

import sys
import os
import argparse
import time
from datetime import datetime

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


def build_where_clause(year: int | None) -> tuple[str, list, str]:
    """Bangun klausa WHERE berbasis tahun jika ditentukan."""
    if year is not None:
        start_date = f"{year}-01-01"
        end_date = f"{year + 1}-01-01"
        where_clause = "WHERE [ExecutionStart] >= ? AND [ExecutionStart] < ?"
        params = [start_date, end_date]
        desc = f"Tahun ExecutionStart = {year} ({start_date} s/d {year}-12-31)"
    else:
        where_clause = ""
        params = []
        desc = "Seluruh Data (Semua Periode)"
    return where_clause, params, desc


def get_pre_counts(cursor, where_clause: str, params: list) -> tuple[int, int]:
    """Hitung total baris dan total duplikat (rn > 1)."""
    # 1. Total Baris
    total_query = f"SELECT COUNT(*) FROM dbo.ZSMR012 {where_clause}"
    cursor.execute(total_query, tuple(params))
    total_rows = cursor.fetchone()[0]

    # 2. Total Baris Duplikat (rn > 1)
    dup_query = f"""
    WITH RankedRecords AS (
        SELECT 
            ROW_NUMBER() OVER (
                PARTITION BY [Order], [ActivityType], [ExecutionStart], CONVERT(VARCHAR(8), [ActualStart], 108)
                ORDER BY 
                    CASE 
                        WHEN [ConfirmationCounter] IS NOT NULL AND LTRIM(RTRIM(CAST([ConfirmationCounter] AS NVARCHAR(50)))) <> '' 
                        THEN 1 
                        ELSE 0 
                    END DESC,
                    [EnteredOn] DESC
            ) AS rn
        FROM dbo.ZSMR012
        {where_clause}
    )
    SELECT COUNT(*) FROM RankedRecords WHERE rn > 1;
    """
    cursor.execute(dup_query, tuple(params))
    duplicate_rows = cursor.fetchone()[0]

    return total_rows, duplicate_rows


def get_top_duplicate_samples(cursor, where_clause: str, params: list, limit: int = 5) -> list[tuple]:
    """Ambil sampel kelompok duplikat teratas dengan jumlah record terbanyak."""
    sample_query = f"""
    SELECT TOP ({limit})
        [Order],
        [ActivityType],
        [ExecutionStart],
        CONVERT(VARCHAR(8), [ActualStart], 108) AS ActualStartTime,
        COUNT(*) AS DuplicateCount
    FROM dbo.ZSMR012
    {where_clause}
    GROUP BY [Order], [ActivityType], [ExecutionStart], CONVERT(VARCHAR(8), [ActualStart], 108)
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC, [Order] ASC;
    """
    cursor.execute(sample_query, tuple(params))
    return cursor.fetchall()


def cleanup_duplicates(conn, cursor, where_clause: str, params: list, batch_size: int) -> int:
    """Eksekusi penghapusan data duplikat secara bertahap per batch commit."""
    delete_query = f"""
    WITH CTE AS (
        SELECT ROW_NUMBER() OVER (
            PARTITION BY [Order], [ActivityType], [ExecutionStart], CONVERT(VARCHAR(8), [ActualStart], 108)
            ORDER BY 
                CASE 
                    WHEN [ConfirmationCounter] IS NOT NULL AND LTRIM(RTRIM(CAST([ConfirmationCounter] AS NVARCHAR(50)))) <> '' 
                    THEN 1 
                    ELSE 0 
                END DESC,
                [EnteredOn] DESC
        ) AS rn
        FROM dbo.ZSMR012
        {where_clause}
    )
    DELETE TOP ({batch_size}) FROM CTE WHERE rn > 1;
    """
    batch_num = 0
    total_deleted = 0

    log(f"[EXECUTE] Memulai batch delete (batch size = {batch_size:,} baris per commit)...")
    while True:
        cursor.execute(delete_query, tuple(params))
        deleted = cursor.rowcount
        if deleted is None or deleted <= 0:
            break

        conn.commit()
        batch_num += 1
        total_deleted += deleted
        log(f"[BATCH {batch_num:>3}] Berhasil menghapus {deleted:,} baris duplikat (Total terhapus: {total_deleted:,} baris)")

        if deleted < batch_size:
            # Batch terakhir telah selesai menghapus semua sisa duplikat
            break

    return total_deleted


def main():
    parser = argparse.ArgumentParser(
        description="Tool Pembersihan Data Duplikat dbo.ZSMR012 di Database DesSy"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Flag eksekusi penghapusan riil (jika tidak diset, default adalah DRY-RUN/simulasi)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="Ukuran batch penghapusan baris per commit (default: 5000)",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Filter tahun ExecutionStart (opsional, contoh: 2026. Default: seluruh data)",
    )

    args = parser.parse_args()

    start_time = time.time()
    mode_str = "EKSEKUSI RIIL" if args.execute else "DRY-RUN (SIMULASI AMAN)"
    log("=" * 70)
    log("ZSMR012 Duplication Cleanup Tool")
    log(f"Mode          : {mode_str}")
    log(f"Batch Size    : {args.batch_size:,} baris")
    log(f"Filter Target : {args.year if args.year else 'Seluruh Data'}")
    log("=" * 70)

    where_clause, params, scope_desc = build_where_clause(args.year)

    conn = None
    try:
        log("[DB] Menghubungkan ke database DesSy...")
        conn = get_connection_with_retry(DB_CONFIG)
        cursor = conn.cursor()

        # Step 1: Pre-count
        log(f"[STEP 1] Menghitung status baris dan duplikasi ({scope_desc})...")
        total_rows, dup_rows = get_pre_counts(cursor, where_clause, params)

        log(f"[PRE-COUNT] Total Baris di dbo.ZSMR012 : {total_rows:,} baris")
        pct = (dup_rows / total_rows * 100) if total_rows > 0 else 0.0
        log(f"[PRE-COUNT] Total Baris Duplikat (rn>1): {dup_rows:,} baris ({pct:.2f}%)")

        if dup_rows > 0:
            log("[SAMPEL] Mengambil 5 contoh kelompok data duplikat teratas...")
            samples = get_top_duplicate_samples(cursor, where_clause, params, limit=5)
            log("-" * 70)
            log(f"{'No':<3} | {'Order':<10} | {'ActivityType':<12} | {'ExecutionStart':<14} | {'ActualTime':<10} | {'Jumlah':<8}")
            log("-" * 70)
            for idx, s in enumerate(samples, 1):
                order, act_type, exec_start, actual_time, count = s
                exec_start_str = exec_start.strftime("%Y-%m-%d") if hasattr(exec_start, "strftime") else str(exec_start)[:10]
                log(f"{idx:<3} | {str(order):<10} | {str(act_type):<12} | {exec_start_str:<14} | {str(actual_time):<10} | {count} baris")
            log("-" * 70)
        else:
            log("[PRE-COUNT] Tidak ditemukan data duplikat pada kriteria ini. Data sudah bersih!")
            return 0

        # Cek Mode Eksekusi
        if not args.execute:
            log("[DRY-RUN] Mode simulasi selesai. Tidak ada data yang dihapus dari database.")
            log(f"[DRY-RUN] Untuk mengeksekusi penghapusan {dup_rows:,} data duplikat di atas, jalankan perintah:")
            year_arg = f" --year {args.year}" if args.year else ""
            log(f"[DRY-RUN] >> python scripts/cleanup_zsmr012_duplicates.py{year_arg} --execute")
            return 0

        # Jika --execute aktif:
        log("[STEP 2] Memulai proses penghapusan riil...")
        total_deleted = cleanup_duplicates(conn, cursor, where_clause, params, args.batch_size)
        log(f"[EXECUTE] Selesai menghapus total {total_deleted:,} baris duplikat.")

        # Step 3: Verifikasi Pasca Penghapusan
        log("[STEP 3] Memverifikasi integritas data setelah pembersihan...")
        post_total_rows, post_dup_rows = get_pre_counts(cursor, where_clause, params)
        log(f"[POST-COUNT] Total Baris Akhir di dbo.ZSMR012 : {post_total_rows:,} baris")
        log(f"[POST-COUNT] Sisa Baris Duplikat (rn>1)       : {post_dup_rows:,} baris")

        if post_dup_rows == 0:
            log("[VERIFIKASI SUKSES] Data duplikat telah 100% bersih!")
        else:
            log(f"[VERIFIKASI PERINGATAN] Masih tersisa {post_dup_rows:,} baris duplikat.")

        duration = time.time() - start_time
        log(f"[SELESAI] Total durasi eksekusi: {duration:.2f} detik")
        return 0

    except Exception as e:
        log(f"[ERROR] Terjadi kesalahan selama operasi pembersihan: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return 1
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main() or 0)
