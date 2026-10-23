import os
import sys
import pandas as pd
import pyodbc
import argparse
import traceback
from datetime import datetime

# Pastikan output stream menggunakan UTF-8 di Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config import DB_CONFIG, get_connection_string
from sap_utils import verify_sap_ready, run_vbs
from db_utils import (
    get_connection_with_retry,
    delete_by_periode,
    insert_batch,
    read_text_with_fallback,
    parse_sap_int,
)


class TeeLogger:
    """Mirror stdout/stderr to a permanent trail log file."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            try:
                stream.write(data)
                stream.flush()
            except Exception:
                pass

    def flush(self):
        for stream in self.streams:
            try:
                stream.flush()
            except Exception:
                pass


def setup_trail_log(periode, log_dir="logs"):
    os.makedirs(log_dir, exist_ok=True)
    safe_periode = str(periode).replace("-", "")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.abspath(os.path.join(log_dir, f"zsme09e_{safe_periode}_{ts}.log"))
    log_file = open(log_path, "a", encoding="utf-8")
    sys.stdout = TeeLogger(sys.__stdout__, log_file)
    sys.stderr = TeeLogger(sys.__stderr__, log_file)
    print(f"[TRAIL] Log file: {log_path}")
    return log_path, log_file


def file_snapshot(path):
    if not os.path.exists(path):
        return {"exists": False, "path": os.path.abspath(path)}
    stat = os.stat(path)
    return {
        "exists": True,
        "path": os.path.abspath(path),
        "size": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
    }


def print_file_snapshot(label, snapshot):
    if not snapshot["exists"]:
        print(f"[FILE] {label}: tidak ada ({snapshot['path']})")
        return
    print(
        f"[FILE] {label}: ada | size={snapshot['size']} bytes | "
        f"modified={snapshot['modified']} | path={snapshot['path']}"
    )


def backup_existing_file(path):
    if not os.path.exists(path):
        return None
    backup_path = f"{path}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
    os.replace(path, backup_path)
    print(f"[FILE] File lama dipindahkan agar SAP membuat output baru: {backup_path}")
    return backup_path


def build_period_filename(base_name, periode, extension):
    safe_periode = str(periode).strip().replace("/", "-").replace("\\", "-")
    return f"{base_name}_{safe_periode}.{extension.lstrip('.')}"


def save_excel_copy(df, source_path, periode):
    excel_filename = build_period_filename("ZSME09E_Data", periode, "xlsx")
    excel_path = os.path.abspath(os.path.join(os.path.dirname(source_path), excel_filename))
    try:
        df.to_excel(excel_path, index=False, engine="openpyxl")
        print_file_snapshot("Excel output", file_snapshot(excel_path))
        return excel_path
    except Exception as e:
        print(f"[EXCEL ERROR] Gagal menyimpan file Excel: {e}")
        print(traceback.format_exc())
        return None


ZSME09E_COLUMNS = [
    "Periode", "MPG", "Div", "Material", "MaterialDescription", "GroupModel",
    "GIQty", "WHRecQty", "ROCRecQty", "SealWHRecQty", "SealROCRecQty",
    "Category", "Description", "WHRecQtyRef", "ROCRecQtyRef", "ActRtrnWH", "ActRtenROC",
]

ZSME09E_HEADER_MAP = {
    "MPG": "MPG",
    "DIV": "Div",
    "Material": "Material",
    "Material Decription": "MaterialDescription",
    "Material Description": "MaterialDescription",
    "Group Model": "GroupModel",
    "GI Qty PC": "GIQty",
    "WH's Rec Qty PC": "WHRecQty",
    "ROC's Rec Qty PC": "ROCRecQty",
    "SealWH's Rec Qty PC": "SealWHRecQty",
    "SealROC's Rec Qty PC": "SealROCRecQty",
    "Category": "Category",
    "Description": "Description",
    "WH's RecQty(Ref) PC": "WHRecQtyRef",
    "ROC's RecQty(Ref) PC": "ROCRecQtyRef",
    "ActRtrn WH": "ActRtrnWH",
    "ActRtrn ROC": "ActRtenROC",
}

ZSME09E_INT_COLUMNS = {
    "GIQty", "WHRecQty", "ROCRecQty", "SealWHRecQty", "SealROCRecQty",
    "Category", "Description", "WHRecQtyRef", "ROCRecQtyRef", "ActRtrnWH", "ActRtenROC",
}





def read_zsme09e_export(file_path, periode):
    text, encoding = read_text_with_fallback(file_path)
    print(f"[SQL] File berhasil dibaca dengan encoding {encoding}.")

    header = None
    data_rows = []
    skipped_pipe_lines = 0
    skipped_summary_rows = 0

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n")
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue

        parts = [part.strip() for part in stripped.strip("|").split("|")]
        if not parts or all(not part for part in parts):
            continue

        if "Material" in parts and ("MPG" in parts or "DIV" in parts):
            header = [ZSME09E_HEADER_MAP.get(part, part) for part in parts]
            print(f"[SQL] Header SAP terdeteksi: {', '.join(header)}")
            continue

        if header is None:
            skipped_pipe_lines += 1
            continue

        if len(parts) != len(header):
            skipped_pipe_lines += 1
            continue

        row = dict(zip(header, parts))
        if not row.get("MPG") or not row.get("Div") or not row.get("Material") or str(row.get("MPG", "")).strip().startswith("*"):
            skipped_summary_rows += 1
            continue

        normalized = {column: None for column in ZSME09E_COLUMNS}
        normalized["Periode"] = periode
        for column in ZSME09E_COLUMNS:
            if column == "Periode":
                continue
            value = row.get(column)
            if column in ZSME09E_INT_COLUMNS:
                normalized[column] = parse_sap_int(value)
            else:
                normalized[column] = None if value is None or value == "" else str(value).strip()
        data_rows.append(normalized)

    if header is None:
        raise ValueError("Header tabel ZSME09E tidak ditemukan di file export SAP.")

    df = pd.DataFrame(data_rows, columns=ZSME09E_COLUMNS)
    for column in ZSME09E_INT_COLUMNS:
        df[column] = pd.Series([None if pd.isna(value) else int(value) for value in df[column]], dtype=object)
    print(f"[SQL] Baris pipe non-data yang dilewati: {skipped_pipe_lines}")
    print(f"[SQL] Baris summary/total yang dilewati: {skipped_summary_rows}")
    return df


# check_sap_login() dan run_vbs() telah dipindahkan ke sap_utils.py


def upload_to_sql(file_path, periode, db_config):
    """Membaca file TXT ZSME09E, simpan Excel, lalu upload ke SQL."""
    print(f"[SQL] Membaca data dari {file_path}...")

    df = read_zsme09e_export(file_path, periode)
    print(f"[SQL] Jumlah baris dari file: {len(df)}")
    print(f"[SQL] Jumlah kolom dari file: {len(df.columns)}")
    print(f"[SQL] Kolom: {', '.join(df.columns)}")

    if df.empty:
        print("[WARN] File hasil SAP terbaca 0 baris. Proses SQL dibatalkan agar tabel tidak dikosongkan.")
        return False

    excel_path = save_excel_copy(df, file_path, periode)
    if not excel_path:
        return False

    print(
        "[SQL] Membuka koneksi: "
        f"server={db_config['server']}; db={db_config.get('db') or db_config.get('name')}; "
        f"user={db_config['user']}"
    )
    conn = get_connection_with_retry(db_config)
    cursor = conn.cursor()
    cursor.fast_executemany = True

    try:
        table_name = 'ZSME09E'
        delete_by_periode(cursor, table_name, periode)

        raw_rows = df.values.tolist()
        data_to_insert = []
        for row in raw_rows:
            cleaned_row = []
            for val in row:
                if pd.isna(val) or val is None or val == "":
                    cleaned_row.append(None)
                elif isinstance(val, (int, float)):
                    cleaned_row.append(float(val) if isinstance(val, float) else int(val))
                else:
                    cleaned_row.append(str(val))
            data_to_insert.append(tuple(cleaned_row))

        insert_batch(cursor, table_name, list(df.columns), data_to_insert)

        cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE Periode = ?", (periode,))
        final_count = cursor.fetchone()[0]

        conn.commit()
        print("[SQL] Commit berhasil.")
        print(f"[SQL] Row final di {table_name} untuk periode {periode}: {final_count}")
        print(f"[SQL] Berhasil! {len(df)} data telah diperbarui.")
        return True
    except Exception as e:
        print(f"[SQL ERROR] {e}")
        print(traceback.format_exc())
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def get_periode_dates(periode, db_config):
    """Ambil StartDate & EndDate dari Tb_R_PeriodeClosing untuk periode tsb."""
    conn = get_connection_with_retry(db_config)
    cur = conn.cursor()
    cur.execute(
        "SELECT StartDate, EndDate FROM Tb_R_PeriodeClosing WHERE Periode = ?",
        (periode,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None, None
    return row[0], row[1]


# verify_sap_ready() telah dipindahkan ke sap_utils.py


def main():
    parser = argparse.ArgumentParser(description="SAP ZSME09E Automation Orchestrator")
    parser.add_argument("--periode", required=True, help="Periode (yyyy-MM-dd)")
    parser.add_argument("--vbs-path", required=True, help="Path ke file VBS Input/Download")
    parser.add_argument("--vbs-login", default=r"vbs\LoginSAP.vbs", help="Path ke VBS Login")
    parser.add_argument("--save-path", required=True, help="Folder simpan file download")
    parser.add_argument("--log-dir", default="logs", help="Folder trail log")

    # DB Config bypass parameters (from Dashboard)
    parser.add_argument("--db-server", default=DB_CONFIG["server"])
    parser.add_argument("--db-user", default=DB_CONFIG["user"])
    parser.add_argument("--db-pwd", default=DB_CONFIG["pwd"])
    parser.add_argument("--db-name", default=DB_CONFIG["name"])

    args = parser.parse_args()
    trail_log_path, trail_log_file = setup_trail_log(args.periode, args.log_dir)

    try:
        download_filename = build_period_filename("ZSME09E_Data", args.periode, "txt")
        db_config = {
            'server': args.db_server,
            'user': args.db_user,
            'pwd': args.db_pwd,
            'db': args.db_name,
        }

        print("-" * 50)
        print(f"SAP AUTOMATION - ZSME09E ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
        print(f"Target Periode: {args.periode}")
        print(f"Save Path: {os.path.abspath(args.save_path)}")
        print(f"VBS Path: {os.path.abspath(args.vbs_path)}")
        print(f"Trail Log: {trail_log_path}")
        print("-" * 50)

        # STEP 1: Cek SAP GUI aktif & sudah login (tanpa auto-login).
        print("[STEP 1] Verifikasi SAP GUI & status login...")
        if not verify_sap_ready():
            print("[BATAL] SAP belum siap. Pastikan SAP GUI terbuka dan sudah login, lalu jalankan ulang.")
            return 1

        try:
            start_date, end_date = get_periode_dates(args.periode, db_config)
        except Exception as e:
            print(f"[ERROR] Gagal mengambil tanggal periode dari database: {e}")
            print(traceback.format_exc())
            return 1

        if not start_date or not end_date:
            print(f"[ERROR] Periode '{args.periode}' tidak ditemukan di Tb_R_PeriodeClosing.")
            return 1

        # Format untuk SAP: ddMMyy (mis. 010526, 310526)
        from_date_sap = start_date.strftime("%d%m%y")
        to_date_sap = end_date.strftime("%d%m%y")
        print(f"[CONFIG] StartDate (DB): {start_date} -> {from_date_sap}")
        print(f"[CONFIG] EndDate   (DB): {end_date} -> {to_date_sap}")

        clean_save_path = os.path.abspath(args.save_path)
        os.makedirs(clean_save_path, exist_ok=True)

        file_full_path = os.path.abspath(os.path.join(clean_save_path, download_filename))
        before_snapshot = file_snapshot(file_full_path)
        print_file_snapshot("Sebelum VBS", before_snapshot)
        backup_existing_file(file_full_path)

        print(f"[STEP 2] Menjalankan VBS: {args.vbs_path}")
        print(f"         > From Date: {from_date_sap}")
        print(f"         > To Date  : {to_date_sap}")
        print(f"         > Output   : {file_full_path}")
        if not run_vbs(args.vbs_path, [from_date_sap, to_date_sap, clean_save_path, download_filename]):
            print("[CRITICAL] Gagal mengeksekusi proses SAP.")
            return 1

        after_snapshot = file_snapshot(file_full_path)
        print_file_snapshot("Sesudah VBS", after_snapshot)
        if before_snapshot.get("exists") and after_snapshot.get("exists"):
            same_size = before_snapshot.get("size") == after_snapshot.get("size")
            same_modified = before_snapshot.get("modified") == after_snapshot.get("modified")
            if same_size and same_modified:
                print("[WARN] File output tidak berubah dari sebelum VBS. Kemungkinan SAP tidak overwrite/download file baru.")

        print("[STEP 3] Validasi File & Upload SQL...")
        if not os.path.exists(file_full_path):
            print(f"[ERROR] File hasil download tidak ditemukan: {file_full_path}")
            return 1
        if os.path.getsize(file_full_path) == 0:
            print(f"[ERROR] File hasil download berukuran 0 byte (kosong): {file_full_path}. Upload dibatalkan.")
            return 1

        print(f"[VALIDASI OK] File terverifikasi: {file_full_path} ({os.path.getsize(file_full_path)/1024:.1f} KB)")
        ok = upload_to_sql(file_full_path, args.periode, db_config)
        return 0 if ok else 1
    finally:
        print(f"[TRAIL] Selesai. Log tersimpan di: {trail_log_path}")
        trail_log_file.close()


if __name__ == "__main__":
    sys.exit(main())











