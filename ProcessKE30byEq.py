import os
import glob
import argparse
import sys

from config import DB_CONFIG
from db_utils import (
    get_connection_with_retry,
    delete_by_periode,
    insert_batch,
    is_sap_numeric,
    parse_sap_int,
)


def process_ke30_eq(input_path, periode, insert_sql=False, db_config=None):
    print(f"Mulai memproses KE30 By Eq")
    print(f"Input: {input_path}")
    print(f"Periode: {periode}")

    # Terima 1 file langsung, atau (fallback) sebuah folder berisi banyak .dat
    if os.path.isfile(input_path):
        files = [input_path]
        output_dir = os.path.dirname(os.path.abspath(input_path))
    elif os.path.isdir(input_path):
        files = [f for f in glob.glob(os.path.join(input_path, "*.dat"))]
        output_dir = input_path
    else:
        print(f"Path tidak ditemukan (bukan file maupun folder): {input_path}")
        return

    if not files:
        print(f"Tidak ada file .dat untuk diproses di: {input_path}")
        return

    print(f"Menemukan {len(files)} file untuk diproses.")
    
    headers = [
        "Periode", "Equipment", "Material", "SerialNumber", 
        "Total Revenue", "Cost", "Gross Profit", "Copy Volume", 
        "NBV", "Repair Cost", "Accesories", "Consumable", 
        "Paper", "Depreciation", "MSF", "Other_Cost", "COGS"
    ]
    
    all_rows = []
    
    for file_path in files:
        print(f" -> Membaca {os.path.basename(file_path)} ...")
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                parts = line.split('\t')
                
                # Baris data SAP KE30 Eq yang valid minimal memiliki 14 kolom data kotor
                if len(parts) >= 14:
                    col_temp = parts[0].strip()
                    rev_val = parts[1].strip()
                    
                    # Cek apakah ini baris data (Revenue adalah angka)
                    if col_temp and col_temp != "Equipment Number" and is_sap_numeric(rev_val):
                        # Pecah teks kolom Temp menjadi Equipment, Material, dan SerialNumber
                        b2_parts = col_temp.split(' ', 1)
                        
                        if len(b2_parts) == 2:
                            eq_raw = b2_parts[0]
                            rest_text = b2_parts[1]
                            
                            # 1. Equipment: Konversi string ke int biar nol di depannya hilang
                            try:
                                equipment = str(int(eq_raw[-6:]))
                            except Exception:
                                equipment = eq_raw
                            
                            # 2 & 3. Material dan SerialNumber
                            mat_ser = rest_text.split('-', 1)
                            material = mat_ser[0].strip()
                            serial_number = mat_ser[1].strip() if len(mat_ser) > 1 else ""
                            
                            # Bersihkan dan paksa angka jadi bulat murni tanpa koma/titik untuk 13 kolom metrics
                            cleaned_nums = []
                            for i in range(1, 14):
                                parsed = parse_sap_int(parts[i])
                                cleaned_nums.append(str(parsed if parsed is not None else 0))
                                    
                            row = [periode, equipment, material, serial_number] + cleaned_nums
                            all_rows.append(row)

    master_save_txt_path = os.path.join(output_dir, f"Combined_KE30_ByEq_{periode}.txt")
    
    # Tulis hasil akhirnya ke file .txt (Tab Delimited)
    with open(master_save_txt_path, 'w', encoding='utf-8') as fout:
        fout.write("\t".join(headers) + "\n")
        for row in all_rows:
            fout.write("\t".join(row) + "\n")
            
    print(f"\n========================================")
    print(f"PROSES SELESAI!")
    print(f"Total Baris Data Digabung: {len(all_rows)}")
    print(f"Hasil TXT disimpan di: {os.path.basename(master_save_txt_path)}")
    print(f"========================================\n")

    # Upload ke SQL Server jika diaktifkan
    if insert_sql and db_config and all_rows:
        upload_to_sql(all_rows, db_config, periode)


def upload_to_sql(all_rows, db_config, periode):
    """Hapus data periode tsb di KE30_ByEq lalu insert data baru (per posisi kolom)."""
    print(f"[SQL] Menyiapkan upload data ke SQL Server...")

    conn = None
    cursor = None
    try:
        conn = get_connection_with_retry(db_config)
        cursor = conn.cursor()
        cursor.fast_executemany = True

        table_name = 'KE30_ByEq'

        # 1. Hapus data periode tsb
        delete_by_periode(cursor, table_name, periode)

        # 2. Insert data baru (mapping per posisi: 17 kolom)
        columns = [
            "Periode", "Equipment", "Material", "SerialNumber",
            "Revenue", "CostOfRevenue", "GrossProfit", "MoP",
            "NBV", "RepairCost", "AccesoriesCost", "ConsumableCost",
            "PaperCost", "Deprecation", "MSF", "OtherCost", "COGS"
        ]

        # Konversi: kolom 0-3 tetap teks; kolom 4-16 (13 metrik) jadi integer
        data_to_insert = []
        for row in all_rows:
            periode_v, equipment_v, material_v, serial_v = row[0], row[1], row[2], row[3]
            nums = [parse_sap_int(val) for val in row[4:17]]
            data_to_insert.append((periode_v, equipment_v, material_v, serial_v, *nums))

        insert_batch(cursor, table_name, columns, data_to_insert)
        conn.commit()
        print(f"[SQL] Berhasil! {len(data_to_insert)} data telah di-insert ke tabel {table_name}.")
        return True
    except Exception as e:
        print(f"[SQL ERROR] Gagal mengupload data KE30_ByEq: {e}")
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
    parser = argparse.ArgumentParser(description="Perapihan Laporan KE30 by Equipment")
    parser.add_argument("--file", required=True, help="Path ke 1 file laporan (.dat), atau folder berisi .dat")
    parser.add_argument("--periode", required=True, help="Target periode (contoh format: 2026-04-01)")
    parser.add_argument("--insert-sql", default="False", help="Insert hasil ke SQL Server (True/False)")
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

    process_ke30_eq(args.file, args.periode, insert_sql=insert_sql, db_config=db_config)
