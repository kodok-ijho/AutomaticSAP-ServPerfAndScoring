"""process_zsmr012.py — Parsing File Hasil Spool ZSMR012 & Upload ke Database DesSy.

Alur Kerja:
1. Membaca semua file teks ZSMR012_*.txt di folder penyimpanan.
2. Memparsing baris tabel SAP berbasis delimiter Pipe (|) atau Tab (\\t).
3. Mengabaikan header laporan SAP (banner teks & garis pembatas).
4. Melakukan normalisasi format tanggal (dd.MM.yyyy -> YYYY-MM-DD 00:00:00),
   jam (HH:mm:ss -> 1900-01-01 HH:mm:ss), dan angka desimal koma (30,0 -> 30.0).
5. Menambahkan metadata (FileName, DatePeriode, proses = 0).
6. Menghapus data existing pada periode yang sama untuk mencegah duplikasi.
7. Melakukan batch insert ke tabel dbo.ZSMR012 di database DesSy.
"""

import os
import sys
import glob
import re
import argparse
from datetime import date, datetime, timedelta
import pandas as pd

# Pastikan output stream menggunakan UTF-8 di Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config import DB_CONFIG
from db_utils import get_connection_with_retry, insert_batch, read_text_with_fallback
from path_resolver import resolve_workspace_paths


ZSMR012_DB_COLUMNS = [
    "Order",
    "WorkCenter",
    "ExecutionStart",
    "ActualStart",
    "ActualFinish",
    "FinishExecution",
    "EnteredOn",
    "Time",
    "Equipment",
    "FileName",
    "DatePeriode",
    "ActivityType",
    "EnteredBy",
    "ActualWork",
    "UnitForWork",
    "Delay",
    "MaintActivityType",
    "OrderType",
    "MatnrEQ",
    "MatEQGrp",
    "PlannerGrp",
    "Portfolio",
    "DetailPort",
    "SalesType",
    "Location",
    "Family",
    "proses",
    "ConfirmationCounter",
    "ReversedIndicator",
    "ConfirmationCounterOfCanceled",
]


def parse_sap_date(val: str | None) -> datetime | None:
    """Konversi string tanggal SAP ('01.01.2016' atau '2016-01-01') ke datetime (jam 00:00:00)."""
    if not val:
        return None
    text = str(val).strip()
    if not text or text in ("00.00.0000", "0", "-", "None"):
        return None
    if "." in text:
        parts = text.split(".")
        if len(parts) == 3 and len(parts[2]) == 4:
            try:
                return datetime(int(parts[2]), int(parts[1]), int(parts[0]))
            except ValueError:
                return None
    elif "-" in text:
        parts = text.split("-")
        if len(parts) == 3 and len(parts[0]) == 4:
            try:
                return datetime(int(parts[0]), int(parts[1]), int(parts[2]))
            except ValueError:
                return None
    return None


def parse_sap_time(val: str | None) -> datetime | None:
    """Konversi string jam SAP ('15:45:00') ke datetime SQL Server dengan base 1900-01-01."""
    if not val:
        return None
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
            return None
    return None


def parse_sap_float(val: str | None) -> float | None:
    """Konversi format angka SAP (pemisah ribuan titik, desimal koma) ke float Python."""
    if val is None:
        return None
    text = str(val).strip()
    if not text or text in ("-", "None"):
        return None
    # Bersihkan titik ribuan dan ubah koma menjadi titik desimal
    cleaned = text.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


clean_number = parse_sap_float


def _normalize_key(s: str) -> str:
    """Membersihkan string nama kolom menjadi lowercase alfanumerik tanpa spasi/tanda baca."""
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def parse_zsmr012_file(
    file_path: str,
    target_periode: datetime | date | str,
) -> list[dict]:
    """Membaca 1 file teks ZSMR012 dan mengekstrak baris-baris data ke format kolom DB."""
    if isinstance(target_periode, str):
        try:
            target_dt = datetime.strptime(target_periode[:10], "%Y-%m-%d")
        except ValueError:
            target_dt = datetime.now()
    elif isinstance(target_periode, date) and not isinstance(target_periode, datetime):
        target_dt = datetime(target_periode.year, target_periode.month, target_periode.day)
    else:
        target_dt = target_periode

    if not os.path.exists(file_path):
        print(f"[PARSE ERROR] File tidak ditemukan: {file_path}")
        return []

    file_sz = os.path.getsize(file_path)
    base_name = os.path.basename(file_path)

    if file_sz == 0:
        print(f"[PARSE INFO] File '{base_name}' berukuran 0 byte (kosong). Spool belum siap atau ekspor terputus.")
        return []

    text, encoding = read_text_with_fallback(file_path)
    raw_lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not raw_lines:
        print(f"[PARSE INFO] File '{base_name}' tidak memiliki baris teks yang dapat diproses.")
        return []

    for l in raw_lines[:15]:
        l_lower = l.lower()
        if (
            "list does not contain any data" in l_lower
            or "keine daten vorhanden" in l_lower
            or "daftar tidak berisi data" in l_lower
        ):
            print(f"[PARSE INFO] File '{base_name}' berisi info SAP: 'List does not contain any data' (tidak ada transaksi di SAP).")
            return []

    # Smart Header Detection: cari baris header dalam 80 baris pertama
    header_idx = -1
    delim = "\t"
    header_cols: list[str] = []
    is_pipe = False

    meta_keywords = (
        "selectionfield",
        "sortcriteria",
        "filtercriteria",
        "datastatistics",
        "recordspassed",
        "filteredout",
        "outstanding",
        "postponed",
        "inprocess",
        "completed",
    )

    for idx, line in enumerate(raw_lines[:80]):
        # Abaikan garis pemisah horizontal
        if line.startswith("---") or line.startswith("|---") or line.startswith("|--") or line.startswith("==="):
            continue

        line_norm = _normalize_key(line)
        if any(kw in line_norm for kw in meta_keywords):
            continue

        has_order = "order" in line_norm or "orderno" in line_norm or "auftrag" in line_norm
        has_other = "workctr" in line_norm or "startex" in line_norm or "actstart" in line_norm or "actualstart" in line_norm or "delay" in line_norm or "acttyp" in line_norm

        if has_order and has_other:
            if "|" in line and line.count("|") >= 6:
                is_pipe = True
                delim = "|"
                cols = [c.strip() for c in line.split("|")]
                if cols and cols[0] == "":
                    cols = cols[1:]
                if cols and cols[-1] == "":
                    cols = cols[:-1]
                if len(cols) >= 5:
                    header_idx = idx
                    header_cols = cols
                    break
            elif "\t" in line and line.count("\t") >= 4:
                cols = [c.strip() for c in line.split("\t")]
                if len(cols) >= 5:
                    header_idx = idx
                    delim = "\t"
                    header_cols = cols
                    break
            elif ";" in line and line.count(";") >= 4:
                cols = [c.strip() for c in line.split(";")]
                if len(cols) >= 5:
                    header_idx = idx
                    delim = ";"
                    header_cols = cols
                    break
            else:
                cols = [c.strip() for c in line.split()]
                if len(cols) >= 5:
                    header_idx = idx
                    delim = "\t"
                    header_cols = cols
                    break

    if header_idx == -1:
        print(f"[PARSE WARN] Header kolom tidak ditemukan di 80 baris pertama '{base_name}'.")
        sample_preview = " | ".join(raw_lines[:3])[:120]
        print(f"             Cuplikan baris file: {sample_preview}")
        return []

    norm_headers = [_normalize_key(c) for c in header_cols]
    data_rows: list[dict] = []

    for line in raw_lines[header_idx + 1:]:
        if not line or line.startswith("---") or line.startswith("==="):
            continue
        if is_pipe and (line.startswith("|--") or line.startswith("|-")):
            continue

        if is_pipe:
            if not line.startswith("|") or line.count("|") < 5:
                continue
            parts = [c.strip() for c in line.split("|")]
            if parts and parts[0] == "":
                parts = parts[1:]
            if parts and parts[-1] == "":
                parts = parts[:-1]
        else:
            parts = [c.strip() for c in line.split(delim)]

        if not parts:
            continue

        if len(parts) < len(header_cols):
            parts += [""] * (len(header_cols) - len(parts))

        # Abaikan jika baris header berulang di halaman baru atau judul spool
        first_col_clean = parts[0].strip().lower()
        if first_col_clean in ("order", "orderno", "auftrag", "selectionfield", ""):
            continue
        if any(kw in first_col_clean for kw in ("list delay", "delay entry", "confirmation", "sortcriteria")):
            continue

        row_dict = dict(zip(header_cols, parts))
        norm_dict = dict(zip(norm_headers, parts))

        order_raw = (
            norm_dict.get("order")
            or norm_dict.get("orderno")
            or norm_dict.get("auftrag")
            or row_dict.get("Order")
        )
        if not order_raw and len(parts) > 0 and parts[0].isdigit():
            order_raw = parts[0]

        if not order_raw or not str(order_raw).strip():
            continue

        order_val = str(order_raw).strip()
        # Order ZSMR012 di SAP adalah digit angka dan maksimal 10 karakter sesuai skema DB
        if not order_val.isdigit() or len(order_val) > 10:
            continue

        def _safe_str(val, max_len=255):
            if val is None:
                return None
            s = str(val).strip()
            return s[:max_len] if s else None

        exec_start = parse_sap_date(norm_dict.get("startex") or row_dict.get("Start Ex-") or row_dict.get("Start Ex."))
        entered_on = parse_sap_date(norm_dict.get("entrydate") or row_dict.get("Entry Date"))
        exec_date = exec_start.date() if isinstance(exec_start, datetime) else exec_start
        entered_date = entered_on.date() if isinstance(entered_on, datetime) else entered_on
        target_date_val = target_dt.date() if isinstance(target_dt, datetime) else target_dt
        row_date_periode = exec_date or entered_date or target_date_val

        row = {
            "Order": order_val[:10],
            "WorkCenter": _safe_str(norm_dict.get("workctr") or row_dict.get("Work Ctr"), 255),
            "ExecutionStart": exec_start,
            "ActualStart": parse_sap_time(norm_dict.get("actstart") or norm_dict.get("actualstart") or row_dict.get("Act. start")),
            "ActualFinish": parse_sap_date(norm_dict.get("finexecut") or row_dict.get("FinExecut-") or row_dict.get("FinExecut.")),
            "FinishExecution": parse_sap_time(norm_dict.get("actfin") or row_dict.get("Act. Fin.")),
            "EnteredOn": entered_on,
            "Time": parse_sap_time(norm_dict.get("time") or row_dict.get("Time")),
            "Equipment": _safe_str(norm_dict.get("equipment") or row_dict.get("Equipment"), 10),
            "FileName": "ZSMR012",
            "DatePeriode": row_date_periode,
            "ActivityType": _safe_str(norm_dict.get("acttyp") or norm_dict.get("activitytype") or row_dict.get("ActTyp"), 255),
            "EnteredBy": _safe_str(norm_dict.get("entered") or norm_dict.get("enteredby") or row_dict.get("Entered"), 255),
            "ActualWork": parse_sap_float(norm_dict.get("actwork") or row_dict.get("Act.work")),
            "UnitForWork": _safe_str(norm_dict.get("un") or norm_dict.get("unit") or row_dict.get("Un."), 255),
            "Delay": parse_sap_float(norm_dict.get("delay") or row_dict.get("Delay")),
            "MaintActivityType": _safe_str(norm_dict.get("mat") or row_dict.get("MAT"), 255),
            "OrderType": _safe_str(norm_dict.get("type") or norm_dict.get("ordertype") or row_dict.get("Type"), 255),
            "MatnrEQ": _safe_str(norm_dict.get("matnreq") or row_dict.get("Matnr EQ"), 255),
            "MatEQGrp": _safe_str(norm_dict.get("mateqgrp") or row_dict.get("Mat EQ Grp"), 255),
            "PlannerGrp": _safe_str(norm_dict.get("plannergr") or norm_dict.get("plannergrp") or row_dict.get("Planner Gr"), 255),
            "Portfolio": _safe_str(norm_dict.get("portfolio") or row_dict.get("Portfolio"), 255),
            "DetailPort": _safe_str(norm_dict.get("detailpor") or norm_dict.get("detailport") or row_dict.get("Detail Por"), 255),
            "SalesType": _safe_str(norm_dict.get("salestype") or row_dict.get("Sales Type"), 255),
            "Location": _safe_str(norm_dict.get("location") or row_dict.get("Location"), 255),
            "Family": _safe_str(norm_dict.get("family") or row_dict.get("Family"), 255),
            "proses": False,
            "ConfirmationCounter": _safe_str(norm_dict.get("confirmati") or row_dict.get("Confirmati"), 255),
            "ReversedIndicator": _safe_str(norm_dict.get("reversedi") or row_dict.get("Reversed I"), 255),
            "ConfirmationCounterOfCanceled": None,
        }
        data_rows.append(row)

    return data_rows


def process_and_upload_zsmr012(
    folder_path: str = "D:\\Kerja\\SS\\ZSMR012\\",
    periode: str | None = None,
    dry_run: bool = False,
    db_config: dict | None = None,
) -> int:
    """Memproses seluruh file ZSMR012_*.txt dan mengunggahnya ke dbo.ZSMR012 di database DesSy."""
    resolved_folder = os.path.abspath(os.path.expandvars(folder_path))
    print("=" * 68)
    print("  [ETL] PROSES & UPLOAD ZSMR012 KE DATABASE DESSY")
    print(f"  Folder Sumber  : {resolved_folder}")
    print(f"  Periode Target : {periode or 'Auto-Detect / Hari Ini'}")
    print(f"  Mode Simulasi  : {'YA (Dry Run)' if dry_run else 'TIDAK (Upload Langsung ke DB)'}")
    print("=" * 68)

    if not os.path.exists(resolved_folder):
        print(f"[ERROR] Folder sumber tidak ditemukan: {resolved_folder}")
        return 1

    # Cari file ZSMR012_*.txt atau *.txt
    pattern = os.path.join(resolved_folder, "ZSMR012_*.txt")
    files = sorted(glob.glob(pattern))
    if not files:
        pattern_all = os.path.join(resolved_folder, "*.txt")
        files = sorted(glob.glob(pattern_all))

    if not files:
        print(f"[WARN] Tidak ada file teks ditemukan di: {resolved_folder}")
        return 0

    print(f"[INFO] Ditemukan {len(files)} file untuk diproses:")
    for f in files:
        print(f"  - {os.path.basename(f)} ({os.path.getsize(f):,} bytes)")

    # Tentukan DatePeriode target
    if periode:
        try:
            if "-" in periode and len(periode.split("-")) == 3:
                dt_p = datetime.strptime(periode, "%Y-%m-%d")
            else:
                dt_p = datetime.strptime(periode, "%d.%m.%Y")
            target_dt = dt_p.replace(hour=0, minute=0, second=0, microsecond=0)
        except Exception:
            target_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        target_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Parsing seluruh file
    all_rows: list[dict] = []
    for f in files:
        rows = parse_zsmr012_file(f, target_dt)
        print(f"  -> File {os.path.basename(f)}: berhasil mengekstrak {len(rows):,} baris data.")
        all_rows.extend(rows)

    if not all_rows:
        print("\n[INFO] Tidak ada data transaksi yang dapat diekstrak dari file-file tersebut.")
        print("       (Kondisi ini wajar jika background job di SAP memang tidak menghasilkan transaksi / spool kosong pada periode yang difilter).")
        return 0

    # Deduplikasi dalam batch berdasarkan Order + ConfirmationCounter + ExecutionStart + ActualStart
    seen_zsmr = set()
    dedup_rows = []
    for r in all_rows:
        key = (r["Order"], r.get("ConfirmationCounter"), r.get("ExecutionStart"), r.get("ActualStart"))
        if key not in seen_zsmr:
            seen_zsmr.add(key)
            dedup_rows.append(r)

    print(f"\n[HASIL PARSE] Total data siap di-upload: {len(dedup_rows):,} baris ({len(all_rows) - len(dedup_rows)} duplikat internal disaring).")

    if dry_run:
        print("[DRY-RUN] Selesai. Data tidak dimasukkan ke database.")
        return 0

    # Upload ke SQL Server
    print("[SQL] Menghubungkan ke database DesSy...")
    conn = None
    try:
        conn = get_connection_with_retry(db_config)
        cursor = conn.cursor()
        cursor.fast_executemany = True

        table_name = "dbo.ZSMR012"
        date_str = target_dt.strftime("%Y-%m-%d")

        # 1. Hapus data existing pada DatePeriode target (jika re-run)
        cursor.execute(
            f"DELETE FROM {table_name} WHERE CAST(DatePeriode AS DATE) = ?",
            (date_str,)
        )
        if cursor.rowcount and cursor.rowcount > 0:
            print(f"[SQL] Membersihkan {cursor.rowcount:,} data lama pada periode {date_str}...")

        # 2. True UPSERT: Hapus record lama dengan Order & ConfirmationCounter yang sama di database
        unique_keys = list({(r["Order"], r.get("ConfirmationCounter") or "") for r in dedup_rows if r.get("Order")})
        if unique_keys:
            cursor.execute("CREATE TABLE #TempZSMRKeys ([Order] NVARCHAR(10), [ConfirmationCounter] NVARCHAR(255));")
            cursor.fast_executemany = True
            cursor.executemany("INSERT INTO #TempZSMRKeys ([Order], [ConfirmationCounter]) VALUES (?, ?)", unique_keys)
            cursor.execute(f"""
                DELETE Z
                FROM {table_name} Z
                INNER JOIN #TempZSMRKeys T
                    ON Z.[Order] = T.[Order]
                   AND (ISNULL(Z.ConfirmationCounter, '') = T.ConfirmationCounter);
                DROP TABLE #TempZSMRKeys;
            """)
            if cursor.rowcount and cursor.rowcount > 0:
                print(f"[SQL UPSERT] Menimpa/memperbarui {cursor.rowcount:,} data konfirmasi ZSMR012 existing di database.")

        # Siapkan tuple list untuk insert_batch
        data_tuples = [
            tuple(r[col] for col in ZSMR012_DB_COLUMNS)
            for r in dedup_rows
        ]

        print(f"[SQL] Mengunggah {len(data_tuples):,} baris ke {table_name}...")
        insert_batch(cursor, table_name, ZSMR012_DB_COLUMNS, data_tuples, chunk_size=2000)

        conn.commit()
        print(f"[SQL SUKSES] Berhasil mengunggah {len(data_tuples):,} data ke {table_name}!")
        return 0

    except Exception as e:
        print(f"[SQL ERROR] Gagal mengunggah data ZSMR012 ke database: {e}")
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
    parser = argparse.ArgumentParser(
        description="Parsing File Hasil Spool ZSMR012 & Upload ke Database DesSy."
    )
    parser.add_argument(
        "--folder",
        default="D:\\Kerja\\SS\\ZSMR012\\",
        help="Folder tempat file ZSMR012_*.txt berada (default: D:\\Kerja\\SS\\ZSMR012\\)",
    )
    parser.add_argument(
        "--periode",
        default=None,
        help="Tanggal periode penanda data di DB (format YYYY-MM-DD, default: hari ini)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulasi parsing tanpa mengunggah ke database",
    )
    parser.add_argument("--db-server", default=None)
    parser.add_argument("--db-user", default=None)
    parser.add_argument("--db-pwd", default=None)
    parser.add_argument("--db-name", default=None)

    args = parser.parse_args()

    db_cfg = None
    if args.db_server:
        db_cfg = {
            "server": args.db_server,
            "user": args.db_user or "",
            "pwd": args.db_pwd or "",
            "name": args.db_name or DB_CONFIG.get("name", "DesSy"),
        }

    exit_code = process_and_upload_zsmr012(
        folder_path=args.folder,
        periode=args.periode,
        dry_run=args.dry_run,
        db_config=db_cfg,
    )
    sys.exit(exit_code)
