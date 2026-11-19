"""scripts/import_zsmr012_excel.py — Script Importer & ETL Excel ZSMR012 ke Database DesSy.

Engine ETL untuk membaca file Excel ZSMR012 secara efisien menggunakan openpyxl
streaming mode (read_only=True), memetakan kolom ke skema dbo.ZSMR012, menormalisasi
tipe data, menyaring baris WorkCenter %-OFF% dan duplikasi in-memory, serta menggantikan
data transaksi di database DesSy untuk rentang tanggal target (default: 1 Sept – 18 Nov 2026).

Fitur:
  - CLI fleksibel (--excel-path, --delete-start, --delete-end, --exclude-off, --batch-size, --dry-run, --execute).
  - Mode safe dry-run secara default (hanya mengeksekusi DELETE/INSERT saat flag --execute diberikan).
  - Dynamic column mapping dengan penanganan 2 kolom Confirmati.
  - Normalisasi format jam ke base 1900-01-01 sesuai skema database SQL Server.
  - In-memory deduplication berbasis composite key: (Order, ActivityType, ExecutionStart, ActualStartTime).
  - Bulk insertion via pyodbc fast_executemany = True dan insert_batch chunked.
  - Verifikasi post-count di database setelah eksekusi.
"""

import os
import sys
import argparse
import time
import re
from datetime import datetime, date, time as dt_time, timedelta
import openpyxl

# Pastikan output stream menggunakan UTF-8 di Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Tambahkan root path ke sys.path agar dapat mengimpor config, db_utils, dan process_zsmr012
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import DB_CONFIG
from db_utils import get_connection_with_retry, insert_batch
from process_zsmr012 import ZSMR012_DB_COLUMNS


def log(msg: str) -> None:
    """Cetak log dengan timestamp terformat."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)


def _normalize_key(s: str) -> str:
    """Membersihkan string nama kolom menjadi lowercase alfanumerik tanpa spasi atau tanda baca."""
    return re.sub(r"[^a-z0-9]", "", str(s).lower()) if s else ""


def _to_clean_str(val, max_len: int = 255) -> str | None:
    """Bersihkan nilai teks, hilangkan whitespace, dan kembalikan None jika kosong."""
    if val is None:
        return None
    s = str(val).strip()
    return s[:max_len] if s and s != "None" else None


def _to_sql_date(val) -> datetime | None:
    """Normalisasi nilai tanggal ke objek datetime dengan jam 00:00:00."""
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return datetime(val.year, val.month, val.day)
    text = str(val).strip()
    if not text or text in ("00.00.0000", "0", "-", "None"):
        return None
    if "." in text:
        parts = text.split(".")
        if len(parts) == 3 and len(parts[2]) == 4:
            try:
                return datetime(int(parts[2]), int(parts[1]), int(parts[0]))
            except ValueError:
                pass
    elif "-" in text:
        parts = text.split("-")
        if len(parts) == 3 and len(parts[0]) == 4:
            try:
                return datetime(int(parts[0]), int(parts[1]), int(parts[2]))
            except ValueError:
                pass
    return None


def _to_sql_time(val) -> datetime | None:
    """Konversi waktu ke format datetime base 1900-01-01 sesuai skema database SQL Server."""
    if val is None:
        return None
    if isinstance(val, dt_time):
        return datetime(1900, 1, 1, val.hour, val.minute, val.second)
    if isinstance(val, datetime):
        return val
    text = str(val).strip()
    if not text or text in ("00:00:00", "-", "None"):
        return None
    parts = text.split(":")
    if len(parts) >= 2:
        try:
            h = int(parts[0])
            m = int(parts[1])
            s = int(parts[2]) if len(parts) > 2 else 0
            return datetime(1900, 1, 1, h, m, s)
        except ValueError:
            pass
    return None


def _to_sql_float(val) -> float | None:
    """Konversi angka Excel/SAP ke float Python."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    text = str(val).strip()
    if not text or text in ("-", "None"):
        return None
    cleaned = text.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_excel_zsmr012(
    excel_path: str,
    exclude_off: bool = True,
) -> tuple[list[dict], dict]:
    """Membaca file Excel ZSMR012, memetakan 28 kolom Excel ke 30 kolom skema dbo.ZSMR012,

    menyaring baris WorkCenter %-OFF% dan menduplikasi in-memory.

    Args:
        excel_path: Path lengkap ke file Excel sumber (.xlsx).
        exclude_off: Jika True, baris dengan WorkCenter mengandung '-OFF' dilewati (default: True).

    Returns:
        tuple (dedup_rows, stats):
        - dedup_rows: list of dict berisi 30 kolom sesuai urutan ZSMR012_DB_COLUMNS.
        - stats: dict statistik parsing ('total_read', 'off_filtered', 'internal_dups', 'clean_rows').
    """
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"File Excel ZSMR012 tidak ditemukan: {excel_path}")

    log(f"Membuka file Excel: {excel_path} (read_only=True)...")
    wb = openpyxl.load_workbook(excel_path, read_only=True)
    sheet = wb.active
    rows = sheet.iter_rows(values_only=True)

    try:
        raw_headers = next(rows)
    except StopIteration:
        wb.close()
        return [], {"total_read": 0, "off_filtered": 0, "internal_dups": 0, "clean_rows": 0}

    # Pemetaan kolom dinamis berbasis nama kolom
    col_map: dict[str, int] = {}
    confirmati_occurrences = 0

    for idx, h in enumerate(raw_headers):
        if h is None:
            continue
        norm = _normalize_key(str(h))
        if norm in ("order", "orderno", "auftrag"):
            col_map["Order"] = idx
        elif norm in ("equipment", "equnr"):
            col_map["Equipment"] = idx
        elif norm in ("acttyp", "activitytype", "acttype"):
            col_map["ActivityType"] = idx
        elif norm in ("entrydate", "enteredon"):
            col_map["EnteredOn"] = idx
        elif norm in ("entered", "enteredby"):
            col_map["EnteredBy"] = idx
        elif norm in ("workctr", "workcenter", "arbpl"):
            col_map["WorkCenter"] = idx
        elif norm in ("startex", "executionstart", "startdate"):
            col_map["ExecutionStart"] = idx
        elif norm in ("actstart", "actualstart"):
            col_map["ActualStart"] = idx
        elif norm in ("finexecut", "actualfinish", "actfin"):
            col_map["ActualFinish"] = idx
        elif norm in ("actfin", "finishexecution"):
            # Perhatikan: jika di header ada 'Act. Fin.', norm bisa 'actfin'.
            # Di Excel sample:
            # col 8: FinExecut. -> norm 'finexecut' (ActualFinish)
            # col 9: Act. Fin.  -> norm 'actfin' (FinishExecution)
            col_map["FinishExecution"] = idx
        elif norm in ("actwork", "actualwork"):
            col_map["ActualWork"] = idx
        elif norm in ("un", "unitforwork", "unit"):
            col_map["UnitForWork"] = idx
        elif norm == "delay":
            col_map["Delay"] = idx
        elif norm == "time":
            col_map["Time"] = idx
        elif norm in ("mat", "maintactivitytype"):
            col_map["MaintActivityType"] = idx
        elif norm in ("type", "ordertype", "auart"):
            col_map["OrderType"] = idx
        elif norm == "confirmati":
            confirmati_occurrences += 1
            if confirmati_occurrences == 1:
                col_map["ConfirmationCounter"] = idx
            elif confirmati_occurrences == 2:
                col_map["ConfirmationCounterOfCanceled"] = idx
        elif norm in ("confirmationcounter", "confcounter"):
            col_map["ConfirmationCounter"] = idx
        elif norm in ("confirmationcounterofcanceled", "confcanceled"):
            col_map["ConfirmationCounterOfCanceled"] = idx
        elif norm in ("reversedi", "reversedindicator", "revind"):
            col_map["ReversedIndicator"] = idx
        elif norm in ("matnreq", "materialeq"):
            col_map["MatnrEQ"] = idx
        elif norm in ("mateqgrp", "materialeqgrp"):
            col_map["MatEQGrp"] = idx
        elif norm in ("plannergr", "plannergrp"):
            col_map["PlannerGrp"] = idx
        elif norm == "portfolio":
            col_map["Portfolio"] = idx
        elif norm in ("detailpor", "detailport"):
            col_map["DetailPort"] = idx
        elif norm in ("salestype",):
            col_map["SalesType"] = idx
        elif norm == "location":
            col_map["Location"] = idx
        elif norm == "family":
            col_map["Family"] = idx

    # Penyesuaian khusus jika FinExecut dan ActFin keduanya ada
    # Header Excel aktual:
    # 8: FinExecut. -> ActualFinish (Date)
    # 9: Act. Fin.  -> FinishExecution (Time)
    for idx, h in enumerate(raw_headers):
        if h is None:
            continue
        norm = _normalize_key(str(h))
        if norm.startswith("finexecut"):
            col_map["ActualFinish"] = idx
        elif norm in ("actfin", "actfinish"):
            col_map["FinishExecution"] = idx

    total_read = 0
    off_filtered = 0
    internal_dups = 0
    seen_keys: set[tuple] = set()
    dedup_rows: list[dict] = []

    for r in rows:
        if r is None or all(c is None for c in r):
            continue

        total_read += 1

        # Validasi Order: string digit max 10 karakter
        raw_order = r[col_map["Order"]] if "Order" in col_map and col_map["Order"] < len(r) else None
        if raw_order is None:
            continue
        order_str = str(raw_order).strip()
        if not order_str.isdigit() or len(order_str) > 10:
            continue

        # Validasi WorkCenter & filter %-OFF%
        work_center = (
            _to_clean_str(r[col_map["WorkCenter"]])
            if "WorkCenter" in col_map and col_map["WorkCenter"] < len(r)
            else None
        )
        if exclude_off and "-OFF" in (work_center or "").upper():
            off_filtered += 1
            continue

        # Parsing tanggal dan waktu utama
        exec_start = (
            _to_sql_date(r[col_map["ExecutionStart"]])
            if "ExecutionStart" in col_map and col_map["ExecutionStart"] < len(r)
            else None
        )
        act_start = (
            _to_sql_time(r[col_map["ActualStart"]])
            if "ActualStart" in col_map and col_map["ActualStart"] < len(r)
            else None
        )
        act_typ = (
            _to_clean_str(r[col_map["ActivityType"]])
            if "ActivityType" in col_map and col_map["ActivityType"] < len(r)
            else None
        )

        # In-memory deduplication composite key:
        # (Order, ActivityType or "", ExecutionStart, ActualStart.strftime("%H:%M:%S") if ActualStart else "")
        act_start_str = act_start.strftime("%H:%M:%S") if act_start else ""
        dedup_key = (order_str, act_typ or "", exec_start, act_start_str)
        if dedup_key in seen_keys:
            internal_dups += 1
            continue
        seen_keys.add(dedup_key)

        # Metadata
        date_periode = exec_start.date() if isinstance(exec_start, (datetime, date)) else None

        row = {
            "Order": order_str,
            "WorkCenter": work_center,
            "ExecutionStart": exec_start,
            "ActualStart": act_start,
            "ActualFinish": (
                _to_sql_date(r[col_map["ActualFinish"]])
                if "ActualFinish" in col_map and col_map["ActualFinish"] < len(r)
                else None
            ),
            "FinishExecution": (
                _to_sql_time(r[col_map["FinishExecution"]])
                if "FinishExecution" in col_map and col_map["FinishExecution"] < len(r)
                else None
            ),
            "EnteredOn": (
                _to_sql_date(r[col_map["EnteredOn"]])
                if "EnteredOn" in col_map and col_map["EnteredOn"] < len(r)
                else None
            ),
            "Time": (
                _to_sql_time(r[col_map["Time"]])
                if "Time" in col_map and col_map["Time"] < len(r)
                else None
            ),
            "Equipment": (
                _to_clean_str(r[col_map["Equipment"]], 10)
                if "Equipment" in col_map and col_map["Equipment"] < len(r)
                else None
            ),
            "FileName": "ZSMR012",
            "DatePeriode": date_periode,
            "ActivityType": act_typ,
            "EnteredBy": (
                _to_clean_str(r[col_map["EnteredBy"]])
                if "EnteredBy" in col_map and col_map["EnteredBy"] < len(r)
                else None
            ),
            "ActualWork": (
                _to_sql_float(r[col_map["ActualWork"]])
                if "ActualWork" in col_map and col_map["ActualWork"] < len(r)
                else None
            ),
            "UnitForWork": (
                _to_clean_str(r[col_map["UnitForWork"]])
                if "UnitForWork" in col_map and col_map["UnitForWork"] < len(r)
                else None
            ),
            "Delay": (
                _to_sql_float(r[col_map["Delay"]])
                if "Delay" in col_map and col_map["Delay"] < len(r)
                else None
            ),
            "MaintActivityType": (
                _to_clean_str(r[col_map["MaintActivityType"]])
                if "MaintActivityType" in col_map and col_map["MaintActivityType"] < len(r)
                else None
            ),
            "OrderType": (
                _to_clean_str(r[col_map["OrderType"]])
                if "OrderType" in col_map and col_map["OrderType"] < len(r)
                else None
            ),
            "MatnrEQ": (
                _to_clean_str(r[col_map["MatnrEQ"]])
                if "MatnrEQ" in col_map and col_map["MatnrEQ"] < len(r)
                else None
            ),
            "MatEQGrp": (
                _to_clean_str(r[col_map["MatEQGrp"]])
                if "MatEQGrp" in col_map and col_map["MatEQGrp"] < len(r)
                else None
            ),
            "PlannerGrp": (
                _to_clean_str(r[col_map["PlannerGrp"]])
                if "PlannerGrp" in col_map and col_map["PlannerGrp"] < len(r)
                else None
            ),
            "Portfolio": (
                _to_clean_str(r[col_map["Portfolio"]])
                if "Portfolio" in col_map and col_map["Portfolio"] < len(r)
                else None
            ),
            "DetailPort": (
                _to_clean_str(r[col_map["DetailPort"]])
                if "DetailPort" in col_map and col_map["DetailPort"] < len(r)
                else None
            ),
            "SalesType": (
                _to_clean_str(r[col_map["SalesType"]])
                if "SalesType" in col_map and col_map["SalesType"] < len(r)
                else None
            ),
            "Location": (
                _to_clean_str(r[col_map["Location"]])
                if "Location" in col_map and col_map["Location"] < len(r)
                else None
            ),
            "Family": (
                _to_clean_str(r[col_map["Family"]])
                if "Family" in col_map and col_map["Family"] < len(r)
                else None
            ),
            "proses": False,
            "ConfirmationCounter": (
                _to_clean_str(r[col_map["ConfirmationCounter"]])
                if "ConfirmationCounter" in col_map and col_map["ConfirmationCounter"] < len(r)
                else None
            ),
            "ReversedIndicator": (
                _to_clean_str(r[col_map["ReversedIndicator"]])
                if "ReversedIndicator" in col_map and col_map["ReversedIndicator"] < len(r)
                else None
            ),
            "ConfirmationCounterOfCanceled": (
                _to_clean_str(r[col_map["ConfirmationCounterOfCanceled"]])
                if "ConfirmationCounterOfCanceled" in col_map and col_map["ConfirmationCounterOfCanceled"] < len(r)
                else None
            ),
        }
        dedup_rows.append(row)

    wb.close()

    stats = {
        "total_read": total_read,
        "off_filtered": off_filtered,
        "internal_dups": internal_dups,
        "clean_rows": len(dedup_rows),
    }

    log(
        f"Parsing selesai: Total dibaca={total_read:,}, Filtered -OFF={off_filtered:,}, "
        f"Dups={internal_dups:,}, Bersih siap insert={len(dedup_rows):,}"
    )
    return dedup_rows, stats


def replace_zsmr012_from_excel(
    excel_path: str = r"D:\Kerja\2026 CSSD\02. REPORTING 2026\11 NOV 2026 REPORTING\ZSMR012 - 010826-181126.xlsx",
    delete_start: str = "2026-09-01",
    delete_end: str = "2026-11-18",
    exclude_off: bool = True,
    batch_size: int = 2000,
    dry_run: bool = True,
    db_config: dict | None = None,
) -> int:
    """Menggantikan data dbo.ZSMR012 dari file Excel dengan menghapus data lama pada rentang tanggal target.

    Args:
        excel_path: Path ke file Excel sumber.
        delete_start: Tanggal awal pembersihan di DB (format YYYY-MM-DD).
        delete_end: Tanggal akhir pembersihan di DB (format YYYY-MM-DD).
        exclude_off: Filter baris WorkCenter %-OFF%.
        batch_size: Ukuran chunk pyodbc insert.
        dry_run: Jika True, hanya simulasi tanpa delete/insert.
        db_config: Konfigurasi DB opsional.

    Returns:
        0 jika sukses, 1 jika terjadi error.
    """
    start_time = time.time()
    log("=" * 70)
    log("ZSMR012 EXCEL IMPORTER & DATA REPLACEMENT UTILITY")
    log("=" * 70)
    log(f"File Sumber Excel : {excel_path}")
    log(f"Periode Delete    : {delete_start} s/d {delete_end} (inklusif)")
    log(f"Filter WorkCenter : Exclude %-OFF% = {exclude_off}")
    log(f"Batch Insert Size : {batch_size:,} baris")
    log(f"Mode Operasi      : {'DRY-RUN (SIMULASI AMAN)' if dry_run else 'LIVE EXECUTION (DELETE & INSERT)'}")
    log("-" * 70)

    # Validasi parameter tanggal
    try:
        start_dt = datetime.strptime(delete_start, "%Y-%m-%d").date()
    except ValueError:
        log(f"[ERROR] Format --delete-start salah (harus YYYY-MM-DD): {delete_start}")
        return 1

    try:
        end_dt = datetime.strptime(delete_end, "%Y-%m-%d").date()
    except ValueError:
        log(f"[ERROR] Format --delete-end salah (harus YYYY-MM-DD): {delete_end}")
        return 1

    if start_dt > end_dt:
        log(f"[ERROR] --delete-start ({start_dt}) tidak boleh lebih besar dari --delete-end ({end_dt})")
        return 1

    next_day_dt = end_dt + timedelta(days=1)
    start_param = start_dt.strftime("%Y-%m-%d")
    next_day_param = next_day_dt.strftime("%Y-%m-%d")

    # 1. Parsing file Excel
    try:
        dedup_rows, stats = parse_excel_zsmr012(excel_path, exclude_off=exclude_off)
    except Exception as e:
        log(f"[ERROR] Gagal memparsing file Excel: {e}")
        return 1

    # 2. Hubungkan ke database DesSy
    conn = None
    try:
        conn = get_connection_with_retry(db_config or DB_CONFIG)
        cursor = conn.cursor()
        cursor.fast_executemany = True

        table_name = "dbo.ZSMR012"

        # Hitung data existing pada rentang tanggal target
        count_query = f"SELECT COUNT(*) FROM {table_name} WHERE [ExecutionStart] >= ? AND [ExecutionStart] < ?"
        cursor.execute(count_query, (start_param, next_day_param))
        target_db_count = cursor.fetchone()[0]

        # Hitung data sebelum periode target (misal data Agustus 2026 dan sebelumnya)
        prior_query = f"SELECT COUNT(*) FROM {table_name} WHERE [ExecutionStart] < ?"
        cursor.execute(prior_query, (start_param,))
        prior_db_count = cursor.fetchone()[0]

        log(f"Data existing di {table_name} periode target ({start_param} s/d {delete_end}): {target_db_count:,} baris")
        log(f"Data existing di {table_name} sebelum {start_param} (Aman/Tidak disentuh) : {prior_db_count:,} baris")

        # 3. Penanganan Mode DRY-RUN
        if dry_run:
            log("-" * 70)
            log("[DRY-RUN] Ringkasan Simulasi:")
            log(f"  * Total baris dibaca dari Excel          : {stats['total_read']:,} baris")
            log(f"  * Baris WorkCenter %-OFF% difilter       : {stats['off_filtered']:,} baris")
            log(f"  * Baris duplikat internal disaring       : {stats['internal_dups']:,} baris")
            log(f"  * Data bersih siap di-insert ke DB       : {len(dedup_rows):,} baris")
            log(f"  * Data existing yang akan dihapus di DB  : {target_db_count:,} baris")
            log(f"  * Data prior (< {start_param}) tetap aman: {prior_db_count:,} baris")
            log("[DRY-RUN] Simulasi selesai dengan sukses. Tidak ada data yang dihapus atau dimasukkan ke DB.")
            log("=" * 70)
            return 0

        # 4. Mode LIVE EXECUTION: DELETE & INSERT
        log("-" * 70)
        log(f"[EXECUTE] Menghapus {target_db_count:,} baris lama di {table_name}...")
        delete_query = f"DELETE FROM {table_name} WHERE [ExecutionStart] >= ? AND [ExecutionStart] < ?"
        cursor.execute(delete_query, (start_param, next_day_param))
        actual_deleted = cursor.rowcount
        log(f"[SQL] Berhasil menghapus {actual_deleted:,} baris dari {table_name}.")

        # Siapkan list of tuples sesuai urutan ZSMR012_DB_COLUMNS
        data_tuples = [
            tuple(r[col] for col in ZSMR012_DB_COLUMNS)
            for r in dedup_rows
        ]

        log(f"[EXECUTE] Mengunggah {len(data_tuples):,} baris baru ke {table_name} via insert_batch...")
        insert_batch(cursor, table_name, ZSMR012_DB_COLUMNS, data_tuples, chunk_size=batch_size)

        # Commit transaksi
        conn.commit()
        log(f"[SQL SUKSES] Transaksi penggantian data ZSMR012 berhasil di-commit!")

        # 5. Verifikasi Post-Count di Database
        cursor.execute(count_query, (start_param, next_day_param))
        post_target_count = cursor.fetchone()[0]

        cursor.execute(prior_query, (start_param,))
        post_prior_count = cursor.fetchone()[0]

        duration = time.time() - start_time
        log("=" * 70)
        log("[VERIFIKASI DATABASE PASCA-EKSEKUSI]")
        log(f"  * Baris baru di {table_name} ({start_param} s/d {delete_end}): {post_target_count:,} baris (Ekspektasi: {len(data_tuples):,})")
        log(f"  * Baris data prior (< {start_param}): {post_prior_count:,} baris (Status: {'Utuh/Aman' if post_prior_count == prior_db_count else 'BERUBAH!'})")
        log(f"  * Total durasi proses: {duration:.2f} detik")
        log("=" * 70)

        if post_target_count != len(data_tuples):
            log(f"[WARNING] Post-count DB ({post_target_count:,}) tidak sesuai dengan jumlah data ({len(data_tuples):,})!")
            return 1

        return 0

    except Exception as e:
        log(f"[FATAL ERROR] Gagal mengeksekusi operasi penggantian data: {e}")
        if conn:
            try:
                conn.rollback()
                log("[SQL] Transaksi dibatalkan (rollback).")
            except Exception:
                pass
        return 1
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def main() -> None:
    """Entry point CLI untuk impor dan penggantian data ZSMR012 dari Excel."""
    default_excel = r"D:\Kerja\2026 CSSD\02. REPORTING 2026\11 NOV 2026 REPORTING\ZSMR012 - 010826-181126.xlsx"

    parser = argparse.ArgumentParser(
        description="Script Importer & ETL Excel ZSMR012 ke dbo.ZSMR012 Database DesSy."
    )
    parser.add_argument(
        "--excel-path",
        default=default_excel,
        help=f"Path file Excel sumber ZSMR012 (default: {default_excel})",
    )
    parser.add_argument(
        "--delete-start",
        default="2026-09-01",
        help="Tanggal awal pembersihan data di DB (format YYYY-MM-DD, default: 2026-09-01)",
    )
    parser.add_argument(
        "--delete-end",
        default="2026-11-18",
        help="Tanggal akhir pembersihan data di DB (format YYYY-MM-DD, default: 2026-11-18)",
    )
    parser.add_argument(
        "--exclude-off",
        dest="exclude_off",
        action="store_true",
        default=True,
        help="Filter baris WorkCenter %%-OFF%% (default: True)",
    )
    parser.add_argument(
        "--include-off",
        dest="exclude_off",
        action="store_false",
        help="Sertakan baris WorkCenter %%-OFF%% (tanpa filter)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=2000,
        help="Ukuran chunk insert pyodbc (default: 2000)",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=None,
        help="Mode simulasi tanpa modifikasi DB (default aktif kecuali flag --execute diberikan)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Flag eksekusi riil ke database (DELETE & INSERT)",
    )

    args = parser.parse_args()

    # Logika safe dry-run default: jika --dry-run tidak eksplisit diberikan, aktif jika --execute False
    if args.dry_run is None:
        dry_run = not args.execute
    else:
        dry_run = args.dry_run

    exit_code = replace_zsmr012_from_excel(
        excel_path=args.excel_path,
        delete_start=args.delete_start,
        delete_end=args.delete_end,
        exclude_off=args.exclude_off,
        batch_size=args.batch_size,
        dry_run=dry_run,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
