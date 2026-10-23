"""process_iw73.py — Parsing File Hasil Spool IW73 & Upload ke Tabel dbo.Service (DesSy).

Alur Kerja:
1. Membaca semua file teks IW73_*.txt di folder penyimpanan.
2. Memparsing baris data berbasis delimiter Tab (\\t) atau Pipe (|).
3. Normalisasi format integer (Order, BusA), float biaya (ActTotSum, SumTotPlan), dan tanggal.
4. Menambahkan metadata (FileName, DatePeriode, proses = 0).
5. Menghapus data existing pada periode yang sama atau deduplikasi.
6. Melakukan batch insert ke tabel dbo.Service di database DesSy.
"""

import os
import sys
import glob
import re
import argparse
from datetime import date, datetime
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


SERVICE_DB_COLUMNS = [
    "FileName",
    "DatePeriode",
    "BscStart",
    "Order",
    "Equipment",
    "SerialNo",
    "MaterialDescription",
    "WorkCtr",
    "MnWkCtr",
    "ListName",
    "Description",
    "MAT",
    "SystemStatus",
    "Street",
    "Material",
    "ActStart",
    "CreatedOn",
    "ChangedOn",
    "ChangedBy",
    "Type",
    "City",
    "Enteredby",
    "Release",
    "ActTotSum",
    "SumTotPlan",
    "ActualEnd",
    "SchedFin",
    "BusA",
    "SchedStart",
    "PG",
    "RespCCtr",
    "proses",
    "UserStatus",
]


def parse_sap_int(val: str | None, default: int | None = None) -> int | None:
    """Konversi string ke integer (membersihkan spasi dan titik)."""
    if val is None:
        return default
    text = str(val).strip().replace(".", "").replace(",", "")
    if not text or text.lower() == "none" or text == "-":
        return default
    try:
        return int(text)
    except ValueError:
        return default


def parse_sap_date(val: str | None) -> date | None:
    """Konversi string tanggal SAP ('01.01.2026' atau '2026-01-01') ke date object."""
    if not val:
        return None
    text = str(val).strip()
    if not text or text in ("00.00.0000", "0", "-", "None"):
        return None
    if "." in text:
        parts = text.split(".")
        if len(parts) == 3 and len(parts[2]) == 4:
            try:
                return datetime(int(parts[2]), int(parts[1]), int(parts[0])).date()
            except ValueError:
                return None
    elif "-" in text:
        parts = text.split("-")
        if len(parts) == 3 and len(parts[0]) == 4:
            try:
                return datetime(int(parts[0]), int(parts[1]), int(parts[2])).date()
            except ValueError:
                return None
    return None


def parse_sap_float(val: str | None) -> float | None:
    """Konversi format angka mata uang SAP (pemisah ribuan titik, desimal koma) ke float Python."""
    if val is None:
        return None
    text = str(val).strip()
    if not text or text in ("-", "None"):
        return None
    cleaned = text.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _normalize_key(s: str) -> str:
    """Membersihkan string nama kolom menjadi lowercase alfanumerik tanpa spasi/tanda baca."""
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def parse_iw73_file(file_path: str, target_periode: datetime | date | str) -> list[dict]:
    """Membaca 1 file teks IW73 dan mengekstrak data baris ke format kolom dbo.Service."""
    if isinstance(target_periode, str):
        try:
            target_date = datetime.strptime(target_periode[:10], "%Y-%m-%d").date()
        except ValueError:
            target_date = datetime.now().date()
    elif isinstance(target_periode, datetime):
        target_date = target_periode.date()
    else:
        target_date = target_periode

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
        has_other = "equipment" in line_norm or "bscstart" in line_norm or "workctr" in line_norm or "mat" in line_norm or "systemstatus" in line_norm or "mnwkctr" in line_norm

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

        order_id = parse_sap_int(order_raw)
        if not order_id:
            continue

        bsc_start = parse_sap_date(norm_dict.get("bscstart") or row_dict.get("Bsc start") or row_dict.get("BscStart"))
        created_on = parse_sap_date(norm_dict.get("createdon") or row_dict.get("Created on") or row_dict.get("CreatedOn"))
        bsc_date = bsc_start.date() if isinstance(bsc_start, datetime) else bsc_start
        created_date = created_on.date() if isinstance(created_on, datetime) else created_on
        row_date_periode = bsc_date or created_date or target_date

        row = {
            "FileName": base_name[:50],
            "DatePeriode": row_date_periode,
            "BscStart": bsc_start,
            "Order": order_id,
            "Equipment": norm_dict.get("equipment") or row_dict.get("Equipment") or None,
            "SerialNo": norm_dict.get("serialno") or row_dict.get("Serial No.") or row_dict.get("SerialNo") or None,
            "MaterialDescription": norm_dict.get("materialdescription") or norm_dict.get("materialdesc") or row_dict.get("Material Description") or row_dict.get("MaterialDescription") or None,
            "WorkCtr": norm_dict.get("workctr") or row_dict.get("Work ctr") or row_dict.get("WorkCtr") or None,
            "MnWkCtr": norm_dict.get("mnwkctr") or row_dict.get("Mn.wk.ctr") or row_dict.get("MnWkCtr") or None,
            "ListName": norm_dict.get("listname") or row_dict.get("List name") or row_dict.get("ListName") or None,
            "Description": norm_dict.get("description") or row_dict.get("Description") or None,
            "MAT": norm_dict.get("mat") or row_dict.get("MAT") or None,
            "SystemStatus": norm_dict.get("systemstatus") or norm_dict.get("sysstatus") or row_dict.get("System status") or row_dict.get("SystemStatus") or None,
            "Street": norm_dict.get("street") or row_dict.get("Street") or None,
            "Material": norm_dict.get("material") or row_dict.get("Material") or None,
            "ActStart": parse_sap_date(norm_dict.get("actstart") or row_dict.get("Act. start") or row_dict.get("ActStart")),
            "CreatedOn": created_on,
            "ChangedOn": parse_sap_date(norm_dict.get("changedon") or row_dict.get("Changed on") or row_dict.get("ChangedOn")),
            "ChangedBy": norm_dict.get("changedby") or row_dict.get("Changed by") or row_dict.get("ChangedBy") or None,
            "Type": norm_dict.get("type") or row_dict.get("Type") or None,
            "City": norm_dict.get("city") or row_dict.get("City") or None,
            "Enteredby": norm_dict.get("enteredby") or row_dict.get("Entered by") or row_dict.get("Enteredby") or None,
            "Release": parse_sap_date(norm_dict.get("release") or row_dict.get("Release")),
            "ActTotSum": parse_sap_float(norm_dict.get("acttotsum") or row_dict.get("ActTotSum")),
            "SumTotPlan": parse_sap_float(norm_dict.get("sumtotplan") or row_dict.get("SumTotPlan")),
            "ActualEnd": parse_sap_date(norm_dict.get("actualend") or row_dict.get("Actual end") or row_dict.get("ActualEnd")),
            "SchedFin": parse_sap_date(norm_dict.get("schedfin") or row_dict.get("Sched.Fin.") or row_dict.get("SchedFin")),
            "BusA": parse_sap_int(norm_dict.get("busa") or row_dict.get("BusA")),
            "SchedStart": parse_sap_date(norm_dict.get("schedstart") or row_dict.get("SchedStart")),
            "PG": norm_dict.get("pg") or row_dict.get("PG") or None,
            "RespCCtr": norm_dict.get("respcctr") or row_dict.get("Resp. CCtr") or row_dict.get("RespCCtr") or None,
            "proses": False,
            "UserStatus": norm_dict.get("userstatus") or row_dict.get("UserStatus") or None,
        }
        data_rows.append(row)

    return data_rows


def process_and_upload_iw73(
    folder_path: str = "D:\\Kerja\\SS\\IW73\\",
    periode: str | None = None,
    dry_run: bool = False,
    db_config: dict | None = None,
) -> int:
    """Memproses seluruh file IW73_*.txt dan mengunggahnya ke dbo.Service di database DesSy."""
    resolved_folder = os.path.abspath(os.path.expandvars(folder_path))
    print("=" * 68)
    print("  [ETL] PROSES & UPLOAD IW73 (SERVICE) KE DATABASE DESSY")
    print(f"  Folder Sumber  : {resolved_folder}")
    print(f"  Periode Target : {periode or 'Auto-Detect / Hari Ini'}")
    print(f"  Mode Simulasi  : {'YA (Dry Run)' if dry_run else 'TIDAK (Upload Langsung ke DB)'}")
    print("=" * 68)

    if not os.path.exists(resolved_folder):
        print(f"[ERROR] Folder sumber tidak ditemukan: {resolved_folder}")
        return 1

    pattern = os.path.join(resolved_folder, "IW73_*.txt")
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

    all_rows: list[dict] = []
    for f in files:
        rows = parse_iw73_file(f, target_dt)
        print(f"  -> File {os.path.basename(f)}: berhasil mengekstrak {len(rows):,} order service.")
        all_rows.extend(rows)

    if not all_rows:
        print("\n[INFO] Tidak ada data transaksi yang dapat diekstrak dari file-file tersebut.")
        print("       (Kondisi ini wajar jika background job di SAP memang tidak menghasilkan transaksi / spool kosong pada periode yang difilter).")
        return 0

    # Deduplikasi dalam batch berdasarkan (Order, Equipment)
    seen_keys = set()
    dedup_rows = []
    for r in all_rows:
        key = (r["Order"], r["Equipment"])
        if key not in seen_keys:
            seen_keys.add(key)
            dedup_rows.append(r)

    print(f"\n[HASIL PARSE] Total order siap di-upload: {len(dedup_rows):,} baris ({len(all_rows) - len(dedup_rows)} duplikat internal disaring).")

    if dry_run:
        print("[DRY-RUN] Selesai. Data tidak dimasukkan ke database.")
        return 0

    print("[SQL] Menghubungkan ke database DesSy...")
    conn = None
    try:
        conn = get_connection_with_retry(db_config)
        cursor = conn.cursor()
        cursor.fast_executemany = True

        table_name = "dbo.Service"
        date_str = target_dt.strftime("%Y-%m-%d")

        # 1. Hapus data existing pada DatePeriode target (jika re-run)
        cursor.execute(
            f"DELETE FROM {table_name} WHERE DatePeriode = ?",
            (date_str,)
        )
        if cursor.rowcount and cursor.rowcount > 0:
            print(f"[SQL] Membersihkan {cursor.rowcount:,} data lama pada periode {date_str}...")

        # 2. True UPSERT: Hapus record lama dengan (Order, Equipment) yang sama di database
        unique_keys = list({(r["Order"], r["Equipment"] or "") for r in dedup_rows if r.get("Order")})
        if unique_keys:
            cursor.execute("CREATE TABLE #TempServiceKeys ([Order] INT, [Equipment] NVARCHAR(20));")
            cursor.fast_executemany = True
            cursor.executemany("INSERT INTO #TempServiceKeys ([Order], [Equipment]) VALUES (?, ?)", unique_keys)
            cursor.execute(f"""
                DELETE S
                FROM {table_name} S
                INNER JOIN #TempServiceKeys T
                    ON S.[Order] = T.[Order]
                   AND (ISNULL(S.Equipment, '') = T.Equipment);
                DROP TABLE #TempServiceKeys;
            """)
            if cursor.rowcount and cursor.rowcount > 0:
                print(f"[SQL UPSERT] Menimpa/memperbarui {cursor.rowcount:,} data order service existing di database.")

        data_tuples = [
            tuple(r[col] for col in SERVICE_DB_COLUMNS)
            for r in dedup_rows
        ]

        print(f"[SQL] Mengunggah {len(data_tuples):,} baris ke {table_name}...")
        insert_batch(cursor, table_name, SERVICE_DB_COLUMNS, data_tuples, chunk_size=2000)

        conn.commit()
        print(f"[SQL SUKSES] Berhasil mengunggah {len(data_tuples):,} data ke {table_name}!")
        return 0

    except Exception as e:
        print(f"[SQL ERROR] Gagal mengunggah data IW73 ke database: {e}")
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
        description="Parsing File Hasil Spool IW73 & Upload ke Database DesSy."
    )
    parser.add_argument(
        "--folder",
        default="D:\\Kerja\\SS\\IW73\\",
        help="Folder tempat file IW73_*.txt berada (default: D:\\Kerja\\SS\\IW73\\)",
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

    exit_code = process_and_upload_iw73(
        folder_path=args.folder,
        periode=args.periode,
        dry_run=args.dry_run,
        db_config=db_cfg,
    )
    sys.exit(exit_code)
