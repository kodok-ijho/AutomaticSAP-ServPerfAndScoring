"""download_zsmr019.py — Download & Upload SQL Laporan ZSMR019 dari SAP GUI.

Alur:
  1. Ambil StartDate & EndDate dari Tb_R_PeriodeClosing berdasarkan 1 input tanggal Periode (YYYY-MM-DD).
  2. Login SAP GUI (jika belum).
  3. Jalankan VBScript vbs/ZSMR019.vbs (From Date = StartDate, To Date = EndDate).
  4. Validasi file output (keberadaan & ukuran > 0 byte).
  5. Cek data periode di tabel ZSMR019:
     - Jika data periode tersebut SUDAH ada -> DELETE periode tersebut.
     - Jika BELUM ada -> langsung INSERT data baru.
  6. Commit transaction & log status.
"""

import os
import sys
import argparse
import pandas as pd
from datetime import datetime, timedelta

# Pastikan output stream menggunakan UTF-8 di Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from sap_utils import ensure_sap_logged_in, run_vbs
from db_utils import (
    get_connection_with_retry,
    delete_by_periode,
    insert_batch,
    clean_sap_number,
    read_text_with_fallback,
)

ZSMR019_COLUMNS = [
    "Periode", "ServiceOrder", "Wctr", "NotifDate", "Equipment", "ModelNumber",
    "CustomerName", "Time", "LocationStatus", "ReasonCode", "ReasonDescr",
    "Notification", "SalesDoc", "SerialNumber", "CustomerCode", "PG", "BA",
    "Partner", "ReasonText", "CustomerAddress", "ForceMajorFlag",
    "EquipmentIDNTeritory", "ActivityOnOffStat", "ServiceOrderFlag",
    "DiscountFlag", "MaterialEQ", "MaterialEQGroup", "Portfolio",
    "DetailPortFolio", "SalesType", "Location", "Family"
]


def get_periode_closing_dates(periode: str, db_config: dict | None = None) -> tuple[str, str]:
    """Mengambil StartDate dan EndDate dari Tb_R_PeriodeClosing di DB.

    Returns:
        Tuple (from_date_str, to_date_str) dalam format 'dd.MM.yyyy'.
    """
    try:
        conn = get_connection_with_retry(db_config)
        cursor = conn.cursor()
        query = "SELECT StartDate, EndDate FROM Tb_R_PeriodeClosing WHERE Periode = ?"
        cursor.execute(query, (periode,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row and row[0] and row[1]:
            s_date = row[0] if isinstance(row[0], datetime) else datetime.strptime(str(row[0]).split()[0], "%Y-%m-%d")
            e_date = row[1] if isinstance(row[1], datetime) else datetime.strptime(str(row[1]).split()[0], "%Y-%m-%d")
            from_str = s_date.strftime("%d.%m.%Y")
            to_str = e_date.strftime("%d.%m.%Y")
            print(f"[CLOSING DB] Periode {periode} -> StartDate: {from_str}, EndDate: {to_str}")
            return from_str, to_str
    except Exception as e:
        print(f"[WARN] Gagal membaca Tb_R_PeriodeClosing dari DB: {e}")

    # Fallback dari tanggal periode YYYY-MM-DD
    try:
        dt = datetime.strptime(periode, "%Y-%m-%d")
        from_str = dt.replace(day=1).strftime("%d.%m.%Y")
        if dt.month == 12:
            next_m = dt.replace(year=dt.year + 1, month=1, day=1)
        else:
            next_m = dt.replace(month=dt.month + 1, day=1)
        last_d = next_m - timedelta(days=1)
        to_str = last_d.strftime("%d.%m.%Y")
        print(f"[CLOSING FALLBACK] Periode {periode} -> From: {from_str}, To: {to_str}")
        return from_str, to_str
    except Exception:
        today_str = datetime.now().strftime("%d.%m.%Y")
        return today_str, today_str


def clean_sap_date(date_str: str | None) -> str | None:
    """Normalisasi string tanggal SAP (mis. '29.07.2026') menjadi format 'YYYY-MM-DD'."""
    if not date_str:
        return None
    text = str(date_str).strip()
    if not text or text.lower() == "none":
        return None
    if "." in text and len(text.split(".")) == 3:
        p = text.split(".")
        if len(p[0]) <= 2 and len(p[2]) == 4:
            return f"{p[2]}-{p[1].zfill(2)}-{p[0].zfill(2)}"
    return text


def parse_zsmr019_tsv(file_path: str, periode_override: str | None = None) -> tuple[pd.DataFrame, str]:
    """Membaca dan memparsing file ZSMR019 (mendukung format Pipe '|' dan Tab '\\t').

    Returns:
        Tuple (df_clean, target_periode)
    """
    text, encoding = read_text_with_fallback(file_path)
    print(f"[SQL] File terbaca dengan encoding: {encoding}")

    raw_lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not raw_lines:
        raise ValueError("File ZSMR019 kosong.")

    target_periode = periode_override
    data_rows = []

    pipe_lines = [l for l in raw_lines if l.startswith("|") and not l.startswith("|---") and not l.startswith("|-")]

    if pipe_lines:
        print(f"[SQL] Terdeteksi format SAP Pipe-Delimited (|) dengan {len(pipe_lines)} baris data.")
        for line in pipe_lines:
            parts = [p.strip() for p in line.strip("|").split("|")]
            if not parts or parts[0] in ("Order", "ServiceOrder", "1") or "ServiceOrder" in parts[0] or "Order" in parts[0]:
                continue
            if len(parts) < 31:
                parts += [""] * (31 - len(parts))

            row_dict = {
                "Periode": target_periode,
                "ServiceOrder": parts[0] or None,
                "Wctr": parts[1] or None,
                "NotifDate": clean_sap_date(parts[2]),
                "Equipment": parts[3] or None,
                "ModelNumber": parts[4] or None,
                "CustomerName": parts[5] or None,
                "Time": clean_sap_number(parts[6]),
                "LocationStatus": parts[7] or None,
                "ReasonCode": parts[8] or None,
                "ReasonDescr": parts[9] or None,
                "Notification": parts[10] or None,
                "SalesDoc": parts[11] or None,
                "SerialNumber": parts[12] or None,
                "CustomerCode": parts[13] or None,
                "PG": parts[14] or None,
                "BA": parts[15] or None,
                "Partner": parts[16] or None,
                "ReasonText": parts[17] or None,
                "CustomerAddress": parts[18] or None,
                "ForceMajorFlag": parts[19] or None,
                "EquipmentIDNTeritory": parts[20] or None,
                "ActivityOnOffStat": parts[21] or None,
                "ServiceOrderFlag": parts[22] or None,
                "DiscountFlag": parts[23] or None,
                "MaterialEQ": parts[24] or None,
                "MaterialEQGroup": parts[25] or None,
                "Portfolio": parts[26] or None,
                "DetailPortFolio": parts[27] or None,
                "SalesType": parts[28] or None,
                "Location": parts[29] or None,
                "Family": parts[30] if len(parts) > 30 else None,
            }
            data_rows.append(row_dict)
    else:
        print("[SQL] Terdeteksi format SAP Tab-Delimited (\\t).")
        header_raw = raw_lines[0].split("\t")
        header = [h.strip() for h in header_raw]

        for line in raw_lines[1:]:
            parts = line.split("\t")
            if len(parts) < len(header):
                parts += [""] * (len(header) - len(parts))

            row_dict = dict(zip(header, parts))
            row_periode = row_dict.get("Periode", "").strip()

            if not target_periode and row_periode:
                target_periode = row_periode

            cleaned_row = {}
            for col in ZSMR019_COLUMNS:
                val = row_dict.get(col, "").strip() if row_dict.get(col) else ""

                if col == "Time":
                    cleaned_row[col] = clean_sap_number(val)
                elif col == "NotifDate":
                    cleaned_row[col] = clean_sap_date(val)
                elif col == "Periode":
                    cleaned_row[col] = target_periode or row_periode
                else:
                    cleaned_row[col] = None if val == "" else val

            data_rows.append(cleaned_row)

    if not target_periode:
        target_periode = datetime.now().strftime("%Y-%m-01")

    df = pd.DataFrame(data_rows, columns=ZSMR019_COLUMNS)
    return df, target_periode


def upload_zsmr019_to_sql(file_path: str, periode_override: str | None = None, db_config: dict | None = None) -> bool:
    """Parsing file TSV ZSMR019, cek DB per periode (delete jika ada), lalu insert batch."""
    print(f"[SQL] Membaca data ZSMR019 dari: {file_path}")
    try:
        df, target_periode = parse_zsmr019_tsv(file_path, periode_override)
    except Exception as e:
        print(f"[SQL ERROR] Gagal memparsing file TSV ZSMR019: {e}")
        return False

    if df.empty:
        print("[WARN] Data ZSMR019 terbaca 0 baris. Upload SQL dibatalkan agar data lama tidak terhapus.")
        return False

    print(f"[SQL] Berhasil memparsing {len(df)} baris data untuk Periode: {target_periode}")

    table_name = "ZSMR019"
    conn = None
    cursor = None
    try:
        print(f"[SQL] Menghubungkan ke SQL Server...")
        conn = get_connection_with_retry(db_config)
        cursor = conn.cursor()
        cursor.fast_executemany = True

        # Cek apakah ada data periode tersebut -> jika ada DELETE, jika tidak langsung INSERT
        delete_by_periode(cursor, table_name, target_periode)

        # Konversi dataframe ke tipe Python native agar pyodbc fast_executemany tidak hang/deadlock
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

        insert_batch(cursor, table_name, ZSMR019_COLUMNS, data_to_insert)

        conn.commit()
        print(f"[SQL SUCCESS] Berhasil memperbarui {len(df)} baris data ZSMR019 periode {target_periode} di database.")
        return True
    except Exception as e:
        print(f"[SQL ERROR] Gagal mengupload data ZSMR019 ke database: {e}")
        if conn:
            try:
                conn.rollback()
                print("[SQL] Rollback berhasil dilakukan.")
            except Exception:
                pass
        return False
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
                print("[SQL] Koneksi database ditutup.")
            except Exception:
                pass


def generate_zsmr019_filename(periode: str) -> str:
    """Generates automated filename matching pattern: ZSMR019 - MMyy - ddMMyy.txt

    Example: Periode 2026-06-01 pulled on 04 Aug 2026 -> 'ZSMR019 - 0626 - 040826.txt'
    """
    try:
        dt_p = datetime.strptime(periode, "%Y-%m-%d")
        mmyy_p = dt_p.strftime("%m%y")
    except Exception:
        mmyy_p = datetime.now().strftime("%m%y")

    ddmmyy_pull = datetime.now().strftime("%d%m%y")
    return f"ZSMR019 - {mmyy_p} - {ddmmyy_pull}.txt"


def main(
    periode: str,
    vbs_path: str,
    save_path: str,
    file_name: str | None = None,
    insert_sql: bool = True,
    db_config: dict | None = None,
) -> int:
    # 1. Dapatkan StartDate & EndDate dari Tb_R_PeriodeClosing berdasarkan 1 input tanggal Periode
    from_date, to_date = get_periode_closing_dates(periode, db_config=db_config)

    resolved_save_path = os.path.abspath(save_path)
    os.makedirs(resolved_save_path, exist_ok=True)

    # Otomatiskan nama file jika kosong/None: ZSMR019 - [MMyy] - [ddMMyy].txt
    if not file_name or file_name.strip() == "":
        file_name = generate_zsmr019_filename(periode)

    resolved_vbs = os.path.abspath(vbs_path)

    print("=" * 60)
    print(f"[CONFIG] Job                     : ZSMR019 AUTOMATION (Download & SQL)")
    print(f"[CONFIG] Periode                 : {periode}")
    print(f"[CONFIG] From Date (StartDate)   : {from_date}")
    print(f"[CONFIG] To Date (EndDate)       : {to_date}")
    print(f"[CONFIG] Save Path               : {resolved_save_path}")
    print(f"[CONFIG] Output Filename         : {file_name}")
    print(f"[CONFIG] VBS Path                : {resolved_vbs}")
    print(f"[CONFIG] Insert to SQL           : {insert_sql}")
    print("=" * 60)

    # 2. Pastikan SAP Logged In
    vbs_login = os.path.join(os.path.dirname(resolved_vbs), "LoginSAP.vbs")
    if not ensure_sap_logged_in(vbs_login):
        print("[ERROR] SAP GUI belum ter-login. Download dibatalkan.")
        return 1

    # 3. Jalankan VBS ZSMR019 dengan (from_date, to_date, save_path, file_name)
    if not os.path.exists(resolved_vbs):
        print(f"[ERROR] File VBS tidak ditemukan di {resolved_vbs}")
        return 1

    print(f"\n[EXEC] Menjalankan VBScript: {resolved_vbs}")
    vbs_ok = run_vbs(resolved_vbs, [from_date, to_date, resolved_save_path, file_name])
    if not vbs_ok:
        print("[ERROR] Eksekusi VBScript ZSMR019 gagal.")
        return 1

    print("[SUCCESS] VBScript ZSMR019 selesai dieksekusi.")

    # 4. Validasi Output File
    output_file_path = os.path.join(resolved_save_path, file_name)
    print(f"\n[VALIDASI] Memeriksa hasil export di: {output_file_path}")
    if not os.path.exists(output_file_path):
        print(f"[ERROR] File hasil download tidak ditemukan: {output_file_path}")
        return 1

    size_bytes = os.path.getsize(output_file_path)
    if size_bytes == 0:
        print(f"[ERROR] File hasil download berukuran 0 byte (kosong): {output_file_path}")
        return 1

    print(f"[VALIDASI OK] File terverifikasi: {os.path.basename(output_file_path)} ({size_bytes / 1024:.1f} KB)")

    # 5. Upload ke SQL Server (jika insert_sql=True)
    if insert_sql:
        print("\n[STEP 5] Memulai Proses Upload ke Database SQL Server...")
        sql_ok = upload_zsmr019_to_sql(output_file_path, periode_override=periode, db_config=db_config)
        return 0 if sql_ok else 1

    print("[INFO] Opsional Insert SQL dimatikan. Eksekusi selesai.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ZSMR019 Automation - Download & Upload SQL Server")
    parser.add_argument("--periode", default=datetime.now().strftime("%Y-%m-01"), help="Periode (format YYYY-MM-DD)")
    parser.add_argument("--vbs-path", default="vbs\\ZSMR019.vbs", help="Path ke file VBS ZSMR019")
    parser.add_argument("--save-path", default="D:\\Kerja\\SS\\", help="Folder simpan file download")
    parser.add_argument("--file-name", default=None, help="Nama file hasil download (mis. ZSMR019.txt)")
    parser.add_argument("--insert-sql", default="True", help="Upload ke SQL Server (True/False)")

    # Param DB otomatis dari dashboard CLI args
    parser.add_argument("--db-server", default=None)
    parser.add_argument("--db-user", default=None)
    parser.add_argument("--db-pwd", default=None)
    parser.add_argument("--db-name", default=None)

    args = parser.parse_args()

    db_cfg = None
    if args.db_server and args.db_user:
        db_cfg = {
            "server": args.db_server,
            "user": args.db_user,
            "pwd": args.db_pwd,
            "name": args.db_name,
        }

    should_insert = str(args.insert_sql).lower() in ("true", "1", "yes")

    ret = main(
        periode=args.periode,
        vbs_path=args.vbs_path,
        save_path=args.save_path,
        file_name=args.file_name,
        insert_sql=should_insert,
        db_config=db_cfg,
    )
    sys.exit(ret)
