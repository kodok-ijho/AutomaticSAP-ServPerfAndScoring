import os
import sys
import pandas as pd
import argparse
import glob
import pyodbc
from datetime import datetime

# Pastikan output stream menggunakan UTF-8 di Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config import DB_CONFIG
from db_utils import delete_by_periode, get_connection_with_retry, insert_batch


def get_db_periode(db_config=None):
    try:
        conn = get_connection_with_retry(db_config)
        cursor = conn.cursor()
        query = "SELECT Periode FROM Tb_R_PeriodeClosing WHERE GETDATE() BETWEEN StartDate AND EndDate"
        cursor.execute(query)
        row = cursor.fetchone()
        if row:
            p = row[0]
            return p.strftime("%Y-%m-%d") if hasattr(p, 'strftime') else str(p).split(" ")[0]
    except Exception:
        pass
    return datetime.now().strftime("%Y-%m-01") # Fallback to first day of current month

def upload_to_sql(df, periode, db_config):
    """Membaca dataframe dan upload ke SQL table ZSMR007B."""
    print(f"[SQL] Menyiapkan upload data ke SQL Server...")

    conn = None
    cursor = None
    try:
        conn = get_connection_with_retry(db_config)
        cursor = conn.cursor()
        cursor.fast_executemany = True
        
        table_name = 'ZSMR007B'
        delete_by_periode(cursor, table_name, periode)
        
        # Buat copy dataframe untuk modifikasi kolom
        df_sql = df.copy()
        
        # Bersihkan nama kolom (buang spasi) agar pas dengan schema database
        df_sql.columns = [c.replace(" ", "") for c in df_sql.columns]
        
        # List kolom yang ada di database agar urutan data masuk dengan benar
        cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{table_name}'")
        db_columns = [r[0] for r in cursor.fetchall()]
        
        if not db_columns:
            print(f"[SQL ERROR] Tabel {table_name} tidak ditemukan di database atau tidak memiliki kolom.")
            return False
            
        # Filter dataframe kolom hanya yang ada di DB
        columns_to_insert = [c for c in db_columns if c in df_sql.columns]
        df_sql = df_sql[columns_to_insert]
        
        # Konversi kolom numerik ke numeric type agar tidak error saat casting string kosong
        for col in df_sql.columns:
            if col not in ['Periode', 'Equipment', 'Modelnumber']:
                # Bersihkan string jika tipe datanya bukan numerik (menghindari bypass karena tipe data string/object)
                if not pd.api.types.is_numeric_dtype(df_sql[col]):
                    cleaned_col = df_sql[col].astype(str).str.strip()
                    # Bersihkan titik ribuan dan ganti koma desimal menjadi titik
                    cleaned_col = cleaned_col.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                    df_sql[col] = pd.to_numeric(cleaned_col, errors='coerce')
                else:
                    df_sql[col] = pd.to_numeric(df_sql[col], errors='coerce')
        
        # Convert dataframe to list of lists (raw python types) to avoid float NaN coercion in pandas
        raw_rows = df_sql.values.tolist()
        
        # Replace NaN/None with Python None (which maps to SQL NULL)
        data_to_insert = []
        for row in raw_rows:
            cleaned_row = []
            for val in row:
                if pd.isnull(val):
                    cleaned_row.append(None)
                else:
                    cleaned_row.append(val)
            data_to_insert.append(tuple(cleaned_row))
            
        insert_batch(cursor, table_name, columns_to_insert, data_to_insert)
        
        conn.commit()
        print(f"[SQL] Berhasil! {len(df_sql)} data telah di-insert ke tabel {table_name}.")
        return True
    except Exception as e:
        print(f"[SQL ERROR] Gagal mengupload data: {e}")
        try:
            conn.rollback()
        except:
            pass
        return False
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

def process_files(folder_path, suffix):
    """
    Combines files ending with the specified suffix (*1 or *2).
    - Skips initial lines.
    - Cleans up pipe delimiters.
    - Sorts by Equipment.
    """
    pattern = os.path.join(folder_path, f"*{suffix}.txt")
    files = glob.glob(pattern)
    
    if not files:
        print(f"No files found for suffix: {suffix} in {folder_path}")
        return None

    combined_df = pd.DataFrame()
    frames = []

    for file in files:
        print(f"Processing file: {file}")
        
        with open(file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        header_idx = -1
        for i, line in enumerate(lines):
            if "|Equipment" in line:
                header_idx = i
                break
        
        if header_idx == -1:
            print(f"Header not found in {file}, skipping.")
            continue
            
        data_rows = []
        # Find the header columns first
        header_line = lines[header_idx].strip()
        header = [c.strip() for c in header_line.split('|') if c.strip()]
        
        for line in lines[header_idx+1:]:
            line = line.strip()
            if not line.startswith('|'):
                continue
            
            # Skip separator lines like |-------|
            if all(c in '| -' for c in line):
                continue
                
            cols = [c.strip() for c in line.split('|')]
            # Many SAP reports have leading/trailing pipes causing empty strings at start/end
            if not cols[0]: cols = cols[1:]
            if cols and not cols[-1]: cols = cols[:-1]
            
            if len(cols) >= len(header):
                data_rows.append(cols[:len(header)])

        df = pd.DataFrame(data_rows, columns=header)
        
        # Clean numeric columns
        for col in df.columns:
            if col in ["Equipment", "Model number"]:
                continue
            
            # Bersihkan whitespace, titik ribuan (.), dan koma desimal (,)
            cleaned_col = df[col].astype(str).str.strip()
            cleaned_col = cleaned_col.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            df[col] = pd.to_numeric(cleaned_col, errors='coerce')

        frames.append(df)

    # Gabungkan SEMUA file sekaligus lalu group sekali saja (lebih cepat dari groupby per-iterasi)
    if frames:
        combined_df = pd.concat(frames, axis=0, ignore_index=True)
        if "Equipment" in combined_df.columns:
            combined_df = combined_df.groupby("Equipment", as_index=False).first()

    if not combined_df.empty:
        # Final pass: Ensure numeric columns are actually numeric
        for col in combined_df.columns:
            if col in ["Equipment", "Model number"]:
                continue
            try:
                combined_df[col] = pd.to_numeric(combined_df[col])
            except (ValueError, TypeError):
                pass

        # Sort by Equipment
        combined_df['Equipment'] = combined_df['Equipment'].astype(str)
        combined_df = combined_df.sort_values(by="Equipment")
        
        # Save to excel
        output_file = os.path.join(folder_path, f"{suffix}.xlsx")
        combined_df.to_excel(output_file, index=False)
        print(f"Saved {output_file}")
        
    return combined_df

def main():
    parser = argparse.ArgumentParser(description="Clean and Combine SAP reports")
    parser.add_argument("--folder", required=True, help="Path to the folder containing .txt reports")
    parser.add_argument("--periode", default=None, help="Periode override (yyyy-MM-dd)")
    parser.add_argument("--insert-sql", default="False", help="Insert combined data into SQL Server")
    parser.add_argument("--db-server", default=DB_CONFIG["server"])
    parser.add_argument("--db-user", default=DB_CONFIG["user"])
    parser.add_argument("--db-pwd", default=DB_CONFIG["pwd"])
    parser.add_argument("--db-name", default=DB_CONFIG["name"])
    args = parser.parse_args()
    
    folder_path = args.folder
    periode_val = args.periode
    insert_sql = args.insert_sql.lower() == "true"
    
    db_config = {
        'server': args.db_server,
        'user': args.db_user,
        'pwd': args.db_pwd,
        'db': args.db_name
    }
    
    if not periode_val:
        print("Fetching periode from database...")
        periode_val = get_db_periode(db_config)
    
    print(f"Processing reports in: {folder_path} (Periode: {periode_val})")
    
    # 1. Process *1 files
    df1 = process_files(folder_path, "1")
    
    # 2. Process *2 files
    df2 = process_files(folder_path, "2")
    
    # 3. Combine 1 and 2
    if df1 is not None and df2 is not None:
        print("Combining result 1 and 2...")
        # Ensure Equipment is string for matching
        df1['Equipment'] = df1['Equipment'].astype(str)
        df2['Equipment'] = df2['Equipment'].astype(str)
        
        combined_all = pd.merge(df1, df2, on="Equipment", how="inner", suffixes=('_1', '_2'))
        
        # Add Periode column at the beginning
        combined_all.insert(0, 'Periode', periode_val)
        
        timestamp = datetime.now().strftime("%H%M%S")
        output_path = os.path.join(folder_path, f"combine_{timestamp}.xlsx")
        txt_filename = f"combine_{periode_val}.txt"
        txt_path = os.path.join(folder_path, txt_filename)

        # Save Excel
        try:
            combined_all.to_excel(output_path, index=False)
            print(f"Final combined report saved to: {output_path}")
        except Exception as e:
            print(f"Could not save Excel (likely file in use): {e}")

        def format_universal_num(val):
            if pd.isnull(val):
                return ""
            if isinstance(val, (int, float)):
                if val == int(val):
                    return str(int(val))
                else:
                    return str(val)
            v = str(val).strip()
            if v == "" or v.lower() == "nan":
                return ""
            try:
                # Handle trailing minus sign from SAP
                is_negative = False
                if v.endswith('-'):
                    is_negative = True
                    v = v[:-1].strip()

                # Raw SAP string format handling (e.g. "322.361" or "0,01")
                # Remove dot (thousands separator), then change comma to dot (decimal)
                clean_v = v.replace('.', '').replace(',', '.')
                num = float(clean_v)
                
                if is_negative:
                    num = -num
                    
                if num == int(num):
                    return str(int(num))
                else:
                    return str(num)
            except ValueError:
                return v

        # Save Tab-delimited TXT
        try:
            txt_df = combined_all.copy()
            
            # Gabungkan semua kolom menjadi satu target yang diproses formatter seragam
            target_cols = [
                "MOP diff CV", "MOP diff FV", "MOP diff PV", "MOP diff LV", 
                "MOP diff OV", "MOP diff RV", "MOP diff TV", "MOP diff QV", 
                "MOP diff WV", "MOP diff GV", "MOP diff HV", "MOP diff KV", 
                "MOP diff MV", "MOP diff NV", "MOP diff XV", "MOP diff YV", 
                "MOP diff ZV", "MOP bill CV", "MOP bill FV", "MOP bill PV", 
                "MOP bill LV", "MOP bill OV", "MOP bill RV", "MOP bill TV", 
                "MOP bill QV", "MOP bill WV", "MOP bill GV", "MOP bill HV", 
                "MOP bill KV", "MOP bill MV", "MOP bill NV", "MOP bill XV", 
                "MOP bill YV", "MOP bill ZV", "Cost Deprec", "Cost Cons", 
                "Cost Part", "Cost Material", "Cost Labor", "Equipment",
                "TR UMC Hours", "TR SMC Conf", "TR SMC Hours", "TR INST Conf", 
                "TR INST Hours", "TR DIST Conf", "TR DIST Hours", "WK UMC Conf", 
                "WK UMC Hours", "WK SMC Conf", "WK SMC Hours", "WK INST Conf", 
                "WK INST Hours", "WK DIST Conf", "WK DIST Hours", "RespTime Total", 
                "DTime UMC Total", "DTime SMC Total", "DTime OGM Total", 
                "Avail Time (hr)", "UpTime Total",
                "Drum CMYK", "Drum C", "Drum M", "Drum Y", "Drum K",
                "Toner C", "Toner M", "Toner Y", "Toner K"
            ]
            
            for c in target_cols:
                if c in txt_df.columns:
                    txt_df[c] = txt_df[c].apply(format_universal_num)
                for suffix_col in [f"{c}_1", f"{c}_2"]:
                    if suffix_col in txt_df.columns:
                        txt_df[suffix_col] = txt_df[suffix_col].apply(format_universal_num)

            txt_df.to_csv(txt_path, sep='\t', index=False)
            print(f"Tab-delimited text saved to: {txt_path}")
        except Exception as e:
            print(f"Could not save TXT: {e}")

        # Upload to SQL if checked
        if insert_sql:
            upload_to_sql(combined_all, periode_val, db_config)
    else:
        print("Could not combine 1 and 2 because one or both are missing.")

if __name__ == "__main__":
    main()
