"""process_iw58.py — Parsing File Hasil Spool IW58 & Upload ke Tabel dbo.Notif (DesSy).

Alur Kerja:
1. Membaca semua file teks IW58_*.txt di folder penyimpanan.
2. Memparsing baris data berbasis delimiter Tab (\\t) atau Pipe (|).
3. Normalisasi format integer (Notification, Order, Customer), tanggal, dan jam.
4. Menambahkan metadata (FileName, DatePeriode, proses = 0).
5. Menghapus data existing pada periode yang sama atau deduplikasi.
6. Melakukan batch insert ke tabel dbo.Notif di database DesSy.
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


NOTIF_DB_COLUMNS = [
    "Notification",
    "FileName",
    "DatePeriode",
    "Order",
    "Typ",
    "SysStatus",
    "UserStatus",
    "PG",
    "MnWkCtr",
    "CreatedOn",
    "CreatTme",
    "Notifdate",
    "Time",
    "Equipment",
    "Material",
    "Description",
    "ListName",
    "MaterialDesc",
    "Street",
    "BusA",
    "Dv",
    "Created",
    "Customer",
    "SalesDoc",
    "Item",
    "SalesOrd",
    "proses",
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


def parse_sap_date(val: str | None) -> datetime | None:
    """Konversi string tanggal SAP ('01.01.2026' atau '2026-01-01') ke datetime."""
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


def _normalize_key(s: str) -> str:
    """Membersihkan string nama kolom menjadi lowercase alfanumerik tanpa spasi/tanda baca."""
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def parse_iw58_file(file_path: str, target_periode: datetime | date | str) -> list[dict]:
    """Membaca 1 file teks IW58 dan mengekstrak data baris ke format kolom dbo.Notif."""
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

        has_notif = "notif" in line_norm or "notification" in line_norm or "notifictn" in line_norm or "meldung" in line_norm
        has_context = "order" in line_norm or "equipment" in line_norm or "mnwkctr" in line_norm or "workctr" in line_norm

        if has_notif and has_context:
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

        notif_raw = (
            norm_dict.get("notifctn")
            or norm_dict.get("notification")
            or norm_dict.get("notif")
            or norm_dict.get("notifictn")
            or norm_dict.get("notifno")
            or norm_dict.get("meldung")
            or row_dict.get("Notifctn")
            or row_dict.get("Notification")
            or row_dict.get("Notif.")
        )
        if not notif_raw and len(parts) > 0 and parts[0].isdigit():
            notif_raw = parts[0]

        notif_id = parse_sap_int(notif_raw)
        if not notif_id:
            continue

        created_on = parse_sap_date(
            norm_dict.get("createdon")
            or norm_dict.get("on")
            or row_dict.get("Created on")
            or row_dict.get("CreatedOn")
            or row_dict.get("On")
        )
        created_date = created_on.date() if isinstance(created_on, datetime) else created_on
        row_date_periode = created_date or target_date

        row = {
            "Notification": notif_id,
            "FileName": base_name[:50],
            "DatePeriode": row_date_periode,
            "Order": parse_sap_int(norm_dict.get("order") or norm_dict.get("orderno") or row_dict.get("Order"), default=0),
            "Typ": norm_dict.get("typ") or row_dict.get("Typ") or None,
            "SysStatus": norm_dict.get("sysstatus") or norm_dict.get("systemstatus") or row_dict.get("SysStatus") or None,
            "UserStatus": norm_dict.get("userstatus") or row_dict.get("UserStatus") or None,
            "PG": norm_dict.get("pg") or row_dict.get("PG") or None,
            "MnWkCtr": norm_dict.get("mnwkctr") or norm_dict.get("workctr") or row_dict.get("Mn.wk.ctr") or row_dict.get("MnWkCtr") or None,
            "CreatedOn": created_on,
            "CreatTme": parse_sap_time(norm_dict.get("creattme") or norm_dict.get("createdtime") or row_dict.get("CreatTme")),
            "Notifdate": parse_sap_date(norm_dict.get("notifdate") or row_dict.get("Notif.date") or row_dict.get("Notifdate")),
            "Time": parse_sap_time(norm_dict.get("time") or row_dict.get("Time")),
            "Equipment": norm_dict.get("equipment") or row_dict.get("Equipment") or None,
            "Material": norm_dict.get("material") or norm_dict.get("materialnumber") or row_dict.get("Material") or None,
            "Description": norm_dict.get("description") or row_dict.get("Description") or None,
            "ListName": norm_dict.get("listname") or row_dict.get("List name") or row_dict.get("ListName") or None,
            "MaterialDesc": norm_dict.get("materialdesc") or norm_dict.get("materialdescription") or row_dict.get("Material Desc.") or row_dict.get("MaterialDesc") or None,
            "Street": norm_dict.get("street") or row_dict.get("Street") or None,
            "BusA": norm_dict.get("busa") or norm_dict.get("businessarea") or row_dict.get("BusA") or None,
            "Dv": norm_dict.get("dv") or norm_dict.get("division") or row_dict.get("Dv") or None,
            "Created": norm_dict.get("created") or row_dict.get("Created") or None,
            "Customer": parse_sap_int(norm_dict.get("customer") or row_dict.get("Customer")),
            "SalesDoc": norm_dict.get("salesdoc") or row_dict.get("Sales Doc.") or row_dict.get("SalesDoc") or None,
            "Item": norm_dict.get("item") or row_dict.get("Item") or None,
            "SalesOrd": norm_dict.get("salesord") or row_dict.get("Sales Ord.") or row_dict.get("SalesOrd") or None,
            "proses": False,
        }
        data_rows.append(row)

    return data_rows


def process_and_upload_iw58(
    folder_path: str = "D:\\Kerja\\SS\\IW58\\",
    periode: str | None = None,
    dry_run: bool = False,
    db_config: dict | None = None,
) -> int:
    """Memproses seluruh file IW58_*.txt dan mengunggahnya ke dbo.Notif di database DesSy."""
    resolved_folder = os.path.abspath(os.path.expandvars(folder_path))
    print("=" * 68)
    print("  [ETL] PROSES & UPLOAD IW58 (NOTIF) KE DATABASE DESSY")
    print(f"  Folder Sumber  : {resolved_folder}")
    print(f"  Periode Target : {periode or 'Auto-Detect / Hari Ini'}")
    print(f"  Mode Simulasi  : {'YA (Dry Run)' if dry_run else 'TIDAK (Upload Langsung ke DB)'}")
    print("=" * 68)

    if not os.path.exists(resolved_folder):
        print(f"[ERROR] Folder sumber tidak ditemukan: {resolved_folder}")
        return 1

    pattern = os.path.join(resolved_folder, "IW58_*.txt")
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
        rows = parse_iw58_file(f, target_dt)
        print(f"  -> File {os.path.basename(f)}: berhasil mengekstrak {len(rows):,} notifikasi.")
        all_rows.extend(rows)

    if not all_rows:
        print("\n[INFO] Tidak ada data transaksi yang dapat diekstrak dari file-file tersebut.")
        print("       (Kondisi ini wajar jika background job di SAP memang tidak menghasilkan transaksi / spool kosong pada periode yang difilter).")
        return 0

    # Deduplikasi dalam batch berdasarkan Notification ID
    seen_notif = set()
    dedup_rows = []
    for r in all_rows:
        nid = r["Notification"]
        if nid not in seen_notif:
            seen_notif.add(nid)
            dedup_rows.append(r)

    print(f"\n[HASIL PARSE] Total notifikasi siap di-upload: {len(dedup_rows):,} baris ({len(all_rows) - len(dedup_rows)} duplikat internal disaring).", flush=True)

    if dry_run:
        print("[DRY-RUN] Selesai. Data tidak dimasukkan ke database.", flush=True)
        return 0

    print("[SQL] Menghubungkan ke database DesSy...", flush=True)
    conn = None
    try:
        conn = get_connection_with_retry(db_config)
        cursor = conn.cursor()
        cursor.fast_executemany = True

        table_name = "dbo.Notif"
        date_str = target_dt.strftime("%Y-%m-%d")

        # 1. Hapus data existing pada DatePeriode target (jika re-run)
        cursor.execute(
            f"DELETE FROM {table_name} WHERE DatePeriode = ?",
            (date_str,)
        )
        if cursor.rowcount and cursor.rowcount > 0:
            print(f"[SQL] Membersihkan {cursor.rowcount:,} data lama pada periode {date_str}...", flush=True)

        # 2. True UPSERT Berkecepatan Tinggi: staging table #TempNotifKeys
        unique_notifs = [(r["Notification"],) for r in dedup_rows if r.get("Notification")]
        if unique_notifs:
            print(f"[SQL UPSERT] Mempersiapkan staging deduplikasi ({len(unique_notifs):,} notifikasi)...", flush=True)
            cursor.execute("CREATE TABLE #TempNotifKeys ([Notification] INT);")
            cursor.fast_executemany = True
            cursor.executemany("INSERT INTO #TempNotifKeys ([Notification]) VALUES (?)", unique_notifs)
            print("[SQL UPSERT] Menghapus data notifikasi lama yang cocok di database...", flush=True)
            cursor.execute(f"""
                DELETE N
                FROM {table_name} N
                INNER JOIN #TempNotifKeys T ON N.Notification = T.Notification;
                DROP TABLE #TempNotifKeys;
            """)
            if cursor.rowcount and cursor.rowcount > 0:
                print(f"[SQL UPSERT] Berhasil menimpa/memperbarui {cursor.rowcount:,} data notifikasi existing di database.", flush=True)

        data_tuples = [
            tuple(r[col] for col in NOTIF_DB_COLUMNS)
            for r in dedup_rows
        ]

        print(f"[SQL] Mengunggah {len(data_tuples):,} baris ke {table_name}...", flush=True)
        insert_batch(cursor, table_name, NOTIF_DB_COLUMNS, data_tuples, chunk_size=2000)

        conn.commit()
        print(f"[SQL SUKSES] Berhasil mengunggah {len(data_tuples):,} data ke {table_name}!", flush=True)
        return 0

    except Exception as e:
        print(f"[SQL ERROR] Gagal mengunggah data IW58 ke database: {e}")
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
        description="Parsing File Hasil Spool IW58 & Upload ke Database DesSy."
    )
    parser.add_argument(
        "--folder",
        default="D:\\Kerja\\SS\\IW58\\",
        help="Folder tempat file IW58_*.txt berada (default: D:\\Kerja\\SS\\IW58\\)",
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

    exit_code = process_and_upload_iw58(
        folder_path=args.folder,
        periode=args.periode,
        dry_run=args.dry_run,
        db_config=db_cfg,
    )
    sys.exit(exit_code)
