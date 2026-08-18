import os
import glob
import argparse
import sys

from config import DB_CONFIG
from db_utils import (
    delete_by_periode,
    get_connection_with_retry,
    insert_batch,
    is_sap_numeric,
)

try:
    import win32com.client
except ImportError:
    print("Modul pywin32 (Excel COM) belum terinstall. Jalankan: pip install pywin32")
    sys.exit(1)

def process_ke30(folder_path, periode, insert_sql=False, db_config=None):
    # Menyimpan master map data yang diinstruksikan gambar
    mapping = {
        10:  ("EDS", "MONO", ""),
        11:  ("EDS", "MONO", "RENT"),
        15:  ("EDS", "MONO", "FSMA"),
        24:  ("EDS", "MONO", ""),
        25:  ("EDS", "MONO", "RENT"),
        29:  ("EDS", "MONO", "FSMA"),
        46:  ("EDS", "COLOR", ""),
        47:  ("EDS", "COLOR", "RENT"),
        51:  ("EDS", "COLOR", "FSMA"),
        118: ("GCS", "COLOR", ""),
        119: ("GCS", "COLOR", "RENT"),
        120: ("GCS", "COLOR", "FSMA"),
        123: ("GCS", "MONO", ""),
        124: ("GCS", "MONO", "RENT"),
        125: ("GCS", "MONO", "FSMA"),
        128: ("GCS", "MONO", ""),
        129: ("GCS", "MONO", "RENT"),
        130: ("GCS", "MONO", "FSMA"),
        147: ("GCS", "MONO", ""),
        148: ("GCS", "MONO", "RENT"),
        149: ("GCS", "MONO", "FSMA"),
        151: ("GCS", "COLOR", ""),
        152: ("GCS", "MONO", "RENT"),
        153: ("GCS", "MONO", "FSMA"),
        168: ("GCS", "MONO", "RENT"),
        169: ("GCS", "MONO", "FSMA"),
        303: ("DtM", "", ""),
        356: ("TOTAL", "", "")
    }

    try:
        excel = win32com.client.DispatchEx("Excel.Application")
    except Exception:
        print("Error: Tidak dapat membuka aplikasi Excel. Pastikan Microsoft Excel terinstall dengan baik.")
        return

    excel.Visible = False
    excel.DisplayAlerts = False

    all_clean_rows = []      # Akumulasi data untuk upload ke SQL Server
    current_master_row = 2   # Mulai paste data dari baris ke-2

    # try/finally menjamin Excel selalu ditutup walaupun terjadi error,
    # sehingga tidak ada proses EXCEL.EXE yang menggantung di background.
    try:
        search_pattern = os.path.join(folder_path, "*.dat")
        files = [f for f in glob.glob(search_pattern)]

        if not files:
            print(f"Tidak ada file .dat ditemukan di folder: {folder_path}")
            return

        print(f"\nDitemukan {len(files)} file .dat untuk diproses pada folder: {folder_path}")

        # Buat satu Master Workbook untuk menampung gabungan seluruh file
        master_wb = excel.Workbooks.Add()
        master_ws = master_wb.Sheets(1)

        headers = [
            "No", "Periode", "Div", "MBU", "Type", "SaTy",
            "Product Group", "Total Revenue", "Cost", "Gross Profit",
            "Copy Volume", "NBV", "Repair Cost", "Accesories",
            "Consumable", "Paper", "Depreciation", "MSF",
            "Other_Cost", "COGS"
        ]
        for col_idx, header_name in enumerate(headers, start=1):
            master_ws.Cells(1, col_idx).Value = header_name

        # Paksa kolom B (Periode) memakai format 'yyyy-mm-dd' agar tidak diubah regional setting Windows
        master_ws.Columns("B:B").NumberFormat = "yyyy-mm-dd"

        for file_path in files:
            file_path = os.path.abspath(file_path)
            if "~$" in file_path:
                continue

            print(f"\nMemproses {os.path.basename(file_path)} ...")

            # TAHAP 0.5: Baca baris dari teks agar akurat karena SAP TAB parser Excel bisa meleset
            div_val = "UN"  # unknown fallback
            max_row = 0
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                while lines and lines[-1].strip() == "":
                    lines.pop()
                max_row = len(lines)

                for line in lines[:20]:
                    if line.startswith("Division"):
                        parts = line.split('\t')
                        if len(parts) > 1:
                            div_val = parts[1].strip()[:2]
                        break

            if max_row < 2:
                max_row = 356  # safety fallback

            wb = None
            try:
                wb = excel.Workbooks.Open(file_path)
                ws = wb.Sheets(1)

                # --- TAHAP 1 & 2: MEMORY BATCH PROCESSING ---
                # Tarik seluruh data (Kolom A-N / 1-14) sekaligus dalam 1 pemanggilan COM (cepat)
                raw_data = ws.Range(ws.Cells(1, 1), ws.Cells(max_row, 14)).Value

                clean_rows = []

                # COM Range.Value mengembalikan tuple of tuples untuk >1 baris
                if isinstance(raw_data, tuple):
                    for row_idx in range(1, max_row + 1):
                        if row_idx - 1 >= len(raw_data):
                            break

                        row = raw_data[row_idx - 1]
                        if not isinstance(row, tuple):
                            row = (row,)  # pengaman tipe data

                        # Index Total Revenue adalah ke-1 (Kolom 2 di data mentah)
                        rev_val = row[1] if len(row) > 1 else None

                        if is_sap_numeric(rev_val):  # Filter baris
                            cleaned_row = list(row)

                            # Bersihkan angka di kolom numerik (Total Revenue s/d COGS / Index 1-13)
                            for c_idx in range(1, min(14, len(cleaned_row))):
                                val = cleaned_row[c_idx]
                                if val is not None:
                                    val_str = str(val).strip()
                                    if val_str and val_str != "nan":
                                        if val_str.endswith('-'):
                                            val_str = '-' + val_str[:-1]
                                        val_clean = val_str.replace(",", "").split(".")[0]
                                        try:
                                            cleaned_row[c_idx] = int(val_clean)
                                        except Exception:
                                            pass

                            no_val = row_idx
                            mbu_val, type_val, saty_val = mapping.get(no_val, ("", "", ""))
                            final_row = [no_val, periode, div_val, mbu_val, type_val, saty_val] + cleaned_row
                            clean_rows.append(final_row)

                # Segera tutup file mentahnya
                wb.Close(SaveChanges=False)
                wb = None

                # --- TAHAP 3: BATCH PASTE KE MASTER ---
                if clean_rows:
                    all_clean_rows.extend(clean_rows)
                    rows_count = len(clean_rows)
                    cols_count = len(clean_rows[0])

                    start_cell = master_ws.Cells(current_master_row, 1)
                    end_cell = master_ws.Cells(current_master_row + rows_count - 1, cols_count)

                    master_ws.Range(start_cell, end_cell).Value = clean_rows
                    current_master_row += rows_count

                    print(f" -> Berhasil di-filter dan di-merge! ({rows_count} baris ditambahkan)")
                else:
                    print(f" -> Peringatan: Tidak ada data tersisa setelah di-filter.")

            except Exception as e:
                print(f" -> Gagal memproses {os.path.basename(file_path)}: {e}")
                if wb:
                    try:
                        wb.Close(SaveChanges=False)
                    except Exception:
                        pass

        # --- SIMPAN MASTER WORKBOOK ---
        try:
            master_save_path = os.path.join(folder_path, f"Combined_KE30_{periode}.xlsx")
            master_save_txt_path = os.path.join(folder_path, f"Combined_KE30_{periode}.txt")

            # Hapus file lama secara paksa jika ada (DisplayAlerts=False bisa membatalkan Save secara diam-diam)
            if os.path.exists(master_save_path):
                os.remove(master_save_path)
            if os.path.exists(master_save_txt_path):
                os.remove(master_save_txt_path)

            master_wb.SaveAs(master_save_path, FileFormat=51)   # 51 = xlsx open xml
            master_wb.SaveAs(master_save_txt_path, FileFormat=20)  # 20 = xlTextWindows (Tab Delimited)
            master_wb.Close(SaveChanges=False)

            print(f"\n========================================")
            print(f"SEMUA PROSES SELESAI!")
            print(f"Hasil gabungan Excel disimpan di: {os.path.basename(master_save_path)}")
            print(f"Hasil gabungan TXT  disimpan di: {os.path.basename(master_save_txt_path)}")
            print(f"Total Baris Data Terkumpul: {current_master_row - 2} baris")
            print(f"========================================")
        except Exception as e:
            print(f"Gagal menyimpan file master: {e}")

    finally:
        try:
            excel.Quit()
        except Exception:
            pass

    # TAHAP 4: Upload ke SQL Server jika diaktifkan
    if insert_sql and db_config and all_clean_rows:
        upload_to_sql(all_clean_rows, db_config, periode)

def upload_to_sql(clean_rows, db_config, periode):
    """Uploads the cleaned KE30 rows into the database."""
    print(f"[SQL] Menyiapkan upload data ke SQL Server...")

    conn = None
    cursor = None
    try:
        conn = get_connection_with_retry(db_config)
        cursor = conn.cursor()
        cursor.fast_executemany = True
        
        table_name = 'KE30'
        delete_by_periode(cursor, table_name, periode)
        
        columns_list = [
            "No", "Periode", "Div", "MBU", "Type", "SaTy", 
            "ProductGroup", "Revenue", "CostOfRevenue", "GrossProfit", 
            "MoP", "NBV", "RepairCost", "AccesoriesCost", 
            "ConsumableCost", "PaperCost", "Deprecation", "MSF", 
            "OtherCost", "COGS"
        ]
        
        # Format the data to insert: convert empty strings and NaNs to None
        data_to_insert = []
        for row in clean_rows:
            cleaned_row = []
            for val in row:
                if val is None or (isinstance(val, str) and val.strip() == ""):
                    cleaned_row.append(None)
                elif isinstance(val, float) and (val != val): # NaN check
                    cleaned_row.append(None)
                else:
                    cleaned_row.append(val)
            data_to_insert.append(tuple(cleaned_row))
            
        insert_batch(cursor, table_name, columns_list, data_to_insert)
        conn.commit()
        print(f"[SQL] Berhasil! {len(clean_rows)} data telah di-insert ke tabel {table_name}.")
        return True
    except Exception as e:
        print(f"[SQL ERROR] Gagal mengupload data KE30: {e}")
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        return False
    finally:
        try:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        except Exception:
            pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Perapihan Laporan KE30 by Divisi")
    parser.add_argument("--folder", required=True, help="Path ke folder laporan")
    parser.add_argument("--periode", required=True, help="Target periode (contoh format: 2026-04-01)")
    parser.add_argument("--insert-sql", default="False", help="Insert combined data into SQL Server")
    parser.add_argument("--db-server", default=DB_CONFIG["server"])
    parser.add_argument("--db-user", default=DB_CONFIG["user"])
    parser.add_argument("--db-pwd", default=DB_CONFIG["pwd"])
    parser.add_argument("--db-name", default=DB_CONFIG["name"])
    args = parser.parse_args()

    insert_sql = args.insert_sql.lower() == "true"
    db_config = {
        'server': args.db_server,
        'user': args.db_user,
        'pwd': args.db_pwd,
        'db': args.db_name
    }

    process_ke30(args.folder, args.periode, insert_sql=insert_sql, db_config=db_config)
