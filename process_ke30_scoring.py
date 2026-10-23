"""process_ke30_scoring.py — Otomasi Pembuatan & Pemecahan File KE30 YTDN Scoring per MPG.

Fungsi Utama:
  1. generate_ke30_scoring_master:
     - Melanjutkan file master Scoring bulan sebelumnya (misal MEI 2026)
     - Mengisi sheet 'RAW ACH YTD 2026' langsung dari database SQL Server (atau fallback .DAT)
       Query: SELECT * FROM KE30 WHERE Periode BETWEEN '{YYYY}-01-01' AND '{target_periode}' ORDER BY Div, Periode
     - Mengupdate parameter bulan pada 'MoP (2)' (cell C2) dan teks banner
     - Me-refresh seluruh Pivot Table dan menyimpan file master bulan berjalan
  2. split_ke30_scoring_by_mpg:
     - Memecah file master menjadi 22 file per MPG (KE30 YTDN Scoring [MMM] [YY] - [MPG].xlsx)
     - Mendukung mapping single divisi (A1->83, B1->82, dst) maupun multi divisi (E1->22,27 & I1->25,26)
     - Memfilter data pada 'RAW ACH YTD 2026' dan 'RAW TARGET YTD DEC25'
     - Menyesuaikan formula khusus E1 & I1 pada sheet 'MoP '
     - Me-refresh Pivot Table dan menyimpan masing-masing file MPG
"""

import os
import sys
import glob
import shutil
import argparse
from datetime import datetime

# Pastikan output stream menggunakan UTF-8 di Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config import DB_CONFIG
from db_utils import get_connection_with_retry, is_sap_numeric
from path_resolver import (
    parse_period_date,
    resolve_scoring_paths,
    ensure_workspace_directories,
    MONTH_MAP_EN,
    MONTH_MAP_ID,
    MONTH_MAP_FULL_ID,
)

try:
    import win32com.client
except ImportError:
    print("Error: Modul pywin32 belum terinstall. Jalankan: pip install pywin32")
    sys.exit(1)


# ---------------------------------------------------------------------------
#  Master Mapping MPG ke Divisi (22 MPG)
# ---------------------------------------------------------------------------
MPG_MAPPING = {
    "A1": ["83"],
    "B1": ["82"],
    "C1": ["81"],
    "D1": ["84"],
    "E1": ["22", "27"],
    "F1": ["21"],
    "G1": ["23"],
    "H1": ["24"],
    "I1": ["25", "26"],
    "J1": ["47"],
    "K1": ["42"],
    "L1": ["41"],
    "M1": ["62"],
    "N1": ["43"],
    "O1": ["44"],
    "Q1": ["91"],
    "R1": ["71"],
    "S1": ["46"],
    "T1": ["45"],
    "U1": ["61"],
    "W1": ["72"],
    "Z1": ["48"],
}

# ---------------------------------------------------------------------------
#  Master Map Baris KE30
# ---------------------------------------------------------------------------
KE30_ROW_MAPPING = {
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


def fetch_ke30_ytd_from_db(periode_dt: datetime, db_config: dict | None = None) -> list:
    """Mengambil data YTD (Januari s/d Bulan Target) dari tabel KE30 di database.

    Query:
        SELECT [No], [Periode], [Div], [MBU], [Type], [SaTy], [ProductGroup], 
               [Revenue], [CostOfRevenue], [GrossProfit], [MoP], [NBV], 
               [RepairCost], [AccesoriesCost], [ConsumableCost], [PaperCost], 
               [Deprecation], [MSF], [OtherCost], [COGS]
        FROM KE30
        WHERE Periode BETWEEN '{YYYY}-01-01' AND '{target_periode}'
        ORDER BY Div, Periode
    """
    start_date = f"{periode_dt.year}-01-01"
    end_date = periode_dt.strftime("%Y-%m-%d")
    cfg = db_config or DB_CONFIG

    print(f"[DB] Mengambil data KE30 dari database: {start_date} s/d {end_date} ...")
    conn = get_connection_with_retry(cfg)
    cursor = conn.cursor()

    query = """
        SELECT [No], [Periode], [Div], [MBU], [Type], [SaTy], [ProductGroup], 
               [Revenue], [CostOfRevenue], [GrossProfit], [MoP], [NBV], 
               [RepairCost], [AccesoriesCost], [ConsumableCost], [PaperCost], 
               [Deprecation], [MSF], [OtherCost], [COGS]
        FROM KE30
        WHERE Periode BETWEEN ? AND ?
        ORDER BY Div, Periode
    """
    cursor.execute(query, (start_date, end_date))
    raw_rows = cursor.fetchall()
    conn.close()

    print(f"[DB] Berhasil menarik {len(raw_rows)} baris data dari tabel KE30.")

    clean_rows = []
    for r in raw_rows:
        row_list = []
        # No (int)
        row_list.append(int(r[0]) if r[0] is not None else 0)
        # Periode (str 'YYYY-MM-DD')
        row_list.append(str(r[1]) if r[1] is not None else "")
        # Div (int / str bersih)
        div_val = str(r[2]).strip() if r[2] is not None else ""
        try:
            div_val = int(div_val)
        except Exception:
            pass
        row_list.append(div_val)
        # MBU, Type, SaTy (str bersih)
        row_list.append(str(r[3]).strip() if r[3] is not None else "")
        row_list.append(str(r[4]).strip() if r[4] is not None else "")
        row_list.append(str(r[5]).strip() if r[5] is not None else "")
        # ProductGroup (str rstrip)
        row_list.append(str(r[6]).rstrip() if r[6] is not None else "")
        # Numeric cols 7 to 19 (Revenue to COGS)
        for c_idx in range(7, 20):
            val = r[c_idx]
            if val is not None:
                try:
                    row_list.append(int(round(float(val))))
                except Exception:
                    row_list.append(0)
            else:
                row_list.append(0)
        clean_rows.append(row_list)

    return clean_rows


def extract_monthly_ke30_dat(folder_path: str, periode_str: str) -> list:
    """Mengekstrak baris data bersih (261 baris x 31 file = 8091 baris) dari folder .dat bulanan."""
    search_pattern = os.path.join(folder_path, "*.dat")
    files = sorted(glob.glob(search_pattern))

    if not files:
        print(f"[EXTRACT] Peringatan: Tidak ada file .dat ditemukan di {folder_path}")
        return []

    print(f"[EXTRACT] Ditemukan {len(files)} file .dat di {folder_path}")
    all_clean_rows = []

    for fpath in files:
        if "~$" in fpath:
            continue

        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            lines = [line.rstrip("\r\n") for line in f]

        div_val = "UN"
        for line in lines[:20]:
            if line.startswith("Division"):
                parts = line.split("\t")
                if len(parts) > 1:
                    div_str = parts[1].strip()[:2]
                    try:
                        div_val = int(div_str)
                    except ValueError:
                        div_val = div_str
                break

        for row_idx, line in enumerate(lines, start=1):
            parts = line.split("\t")
            if len(parts) < 14:
                parts += [""] * (14 - len(parts))
            else:
                parts = parts[:14]

            rev_val = parts[1]
            if is_sap_numeric(rev_val):
                cleaned = list(parts)
                for c_idx in range(1, 14):
                    val_str = str(cleaned[c_idx]).strip()
                    if val_str and val_str != "nan":
                        if val_str.endswith("-"):
                            val_str = "-" + val_str[:-1]
                        val_clean = val_str.replace(",", "").split(".")[0]
                        try:
                            cleaned[c_idx] = int(val_clean)
                        except Exception:
                            cleaned[c_idx] = 0
                    else:
                        cleaned[c_idx] = 0

                no_val = row_idx
                mbu_val, type_val, saty_val = KE30_ROW_MAPPING.get(no_val, ("", "", ""))
                final_row = [no_val, periode_str, div_val, mbu_val, type_val, saty_val] + cleaned
                all_clean_rows.append(final_row)

    print(f"[EXTRACT] Total baris terekstrak: {len(all_clean_rows)} baris.")
    return all_clean_rows


def update_pivot_periode_filters(wb, target_month_int: int, yy: str) -> None:
    """Memastikan seluruh bulan dari Januari s/d bulan target dicentang (Visible=True) pada seluruh Pivot Table.

    Args:
        wb: COM Workbook object.
        target_month_int: Angka bulan target (1=Jan, 7=Jul, dst).
        yy: Dua digit tahun (misal '26').
    """
    month_abbrs = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    valid_months = [f"{month_abbrs[m - 1]}-{yy}" for m in range(1, target_month_int + 1)]

    print(f"[EXCEL] Memperbarui filter Periode Pivot Table untuk bulan: {', '.join(valid_months)} ...")
    for ws in wb.Sheets:
        for pt in ws.PivotTables():
            for pf in pt.PageFields:
                if pf.Name == "Periode" and pf.EnableMultiplePageItems:
                    for i in range(1, pf.PivotItems().Count + 1):
                        item = pf.PivotItems(i)
                        if item.Name in valid_months:
                            try:
                                item.Visible = True
                            except Exception:
                                pass
                        elif item.Name == "(blank)":
                            try:
                                item.Visible = False
                            except Exception:
                                pass


def generate_ke30_scoring_master(
    periode: str | datetime,
    base_drive: str = "D:\\Kerja",
    prev_file: str | None = None,
    output_file: str | None = None,
    output_dir: str | None = None,
    raw_folder: str | None = None,
    force_recreate: bool = False,
    source: str = "db",
    db_config: dict | None = None,
) -> str:
    """Membuat file master Scoring KE30 bulan berjalan.

    Args:
        periode: Tanggal periode target (contoh: '2026-06-01').
        base_drive: Root drive (default 'D:\\Kerja').
        prev_file: Path manual file master bulan sebelumnya (opsional).
        output_file: Path manual file master output (opsional).
        output_dir: Path folder output khusus jika di-override (opsional).
        raw_folder: Path folder .dat bulan berjalan (jika source='dat').
        force_recreate: Jika True, timpa master file yang sudah ada dari awal.
        source: Sumber data 'db' (SQL Server KE30) atau 'dat' (file .dat lokal).
        db_config: Konfigurasi koneksi database (opsional).

    Returns:
        Path lengkap file master yang berhasil dibuat.
    """
    paths = resolve_scoring_paths(periode, base_drive)
    ensure_workspace_directories(paths)

    if output_file:
        master_target = output_file
    elif output_dir:
        master_target = os.path.join(output_dir, f"KE30 YTDN Scoring {paths['mmm_en']} {paths['yy']}.xlsx")
    else:
        master_target = paths["scoring_master_file"]

    prev_master = prev_file or paths["prev_scoring_master_file"]
    dat_folder = raw_folder or paths["ke30_month_raw_dir"]

    periode_dt = parse_period_date(periode)
    periode_str = periode_dt.strftime("%Y-%m-%d")
    month_num = paths["month_int"]
    next_full_id = paths["next_full_id"]
    next_yyyy = paths["next_yyyy"]

    print("\n=======================================================")
    print(f" GENERASI MASTER SCORING: KE30 YTDN Scoring {paths['mmm_en']} {paths['yy']}")
    print("=======================================================")
    print(f" Periode Target       : {periode_str} (Bulan {month_num})")
    print(f" Sumber Data          : {source.upper()}")
    print(f" File Template/Lalu   : {prev_master}")
    print(f" Output Target        : {master_target}")
    print("-------------------------------------------------------")

    if not prev_master or not os.path.isfile(prev_master):
        raise FileNotFoundError(f"File master scoring bulan sebelumnya tidak ditemukan: {prev_master}")

    os.makedirs(os.path.dirname(master_target), exist_ok=True)

    # Ambil data YTD sesuai mode source
    if source.lower() == "db":
        ytd_rows = fetch_ke30_ytd_from_db(periode_dt, db_config=db_config)
        if not ytd_rows:
            raise RuntimeError(f"Tidak ada data KE30 ditemukan di database untuk periode {periode_dt.year}-01-01 s/d {periode_str}")
    else:
        if not os.path.isdir(dat_folder):
            raise FileNotFoundError(f"Folder raw .DAT tidak ditemukan: {dat_folder}")
        new_rows = extract_monthly_ke30_dat(dat_folder, periode_str)
        if not new_rows:
            raise RuntimeError("Gagal mengekstrak data dari file .DAT bulan berjalan.")

    # Salin template prev_master jika target belum ada atau force_recreate
    if not os.path.exists(master_target) or force_recreate:
        print(f"[MASTER] Menyalin template dari: {os.path.basename(prev_master)} ...")
        shutil.copyfile(prev_master, master_target)

    excel = win32com.client.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    excel.ScreenUpdating = False

    try:
        print(f"[EXCEL] Membuka {os.path.basename(master_target)} ...")
        wb = excel.Workbooks.Open(master_target)

        ws_ach = wb.Sheets("RAW ACH YTD 2026")
        last_row = ws_ach.Cells(ws_ach.Rows.Count, 1).End(-4162).Row  # xlUp

        if source.lower() == "db":
            # Clear data lama (baris 2 ke bawah) lalu masukkan seluruh YTD rows dari DB
            if last_row > 1:
                print(f"[EXCEL] Membersihkan data lama di RAW ACH YTD (baris 2 s/d {last_row})...")
                ws_ach.Range(f"A2:T{last_row}").ClearContents()

            print(f"[EXCEL] Menulis {len(ytd_rows)} baris data YTD dari database ke RAW ACH YTD...")
            start_cell = ws_ach.Cells(2, 1)
            end_cell = ws_ach.Cells(len(ytd_rows) + 1, len(ytd_rows[0]))
            ws_ach.Range(start_cell, end_cell).Value = ytd_rows
            print(f"[EXCEL] Berhasil menulis data DB! Total baris: {len(ytd_rows) + 1}")
        else:
            # Mode DAT: Append data baru jika belum ada
            already_has_period = False
            check_start = max(2, last_row - len(new_rows) - 50)
            for r in range(check_start, last_row + 1):
                val_p = ws_ach.Cells(r, 2).Value
                if val_p and str(val_p)[:10] == periode_str:
                    already_has_period = True
                    break

            if already_has_period:
                print(f"[EXCEL] Data periode {periode_str} sudah ada di RAW ACH YTD. Melewati tahap append.")
            else:
                print(f"[EXCEL] Menambahkan {len(new_rows)} baris data baru ke RAW ACH YTD...")
                start_row = last_row + 1
                end_row = start_row + len(new_rows) - 1
                start_cell = ws_ach.Cells(start_row, 1)
                end_cell = ws_ach.Cells(end_row, len(new_rows[0]))
                ws_ach.Range(start_cell, end_cell).Value = new_rows
                print(f"[EXCEL] Berhasil append data! Total baris: {end_row}")

        # 2. Update parameter bulan pada sheet 'MoP (2)' (cell C2)
        try:
            ws_mop2 = wb.Sheets("MoP (2)")
            ws_mop2.Range("C2").Value = month_num
            print(f"[EXCEL] Sheet 'MoP (2)' cell C2 diupdate ke: {month_num}")
        except Exception as e:
            print(f"[EXCEL] Catatan MoP (2) C2: {e}")

        # 3. Update Banner teks periode pada sheet 'Score CostPerRevenue dan MoP'
        try:
            ws_score = wb.Sheets("Score CostPerRevenue dan MoP")
            banner_formula = f'=_xlfn.UNICHAR(9888)&"  Penilaian ini akan masuk kedalam periode Scoring {next_full_id} {next_yyyy}  "&_xlfn.UNICHAR(9888)'
            ws_score.Range("A10").Formula = banner_formula
            print(f"[EXCEL] Sheet 'Score' banner A10 diupdate ke Scoring {next_full_id} {next_yyyy}")
        except Exception as e:
            print(f"[EXCEL] Catatan banner Score: {e}")

        # 4. Refresh dan Update Filter Periode Pivot Table (Centang seluruh bulan s/d bulan berjalan)
        print("[EXCEL] Me-refresh Pivot Table dan mengaktifkan filter seluruh bulan YTD...")
        wb.RefreshAll()
        update_pivot_periode_filters(wb, month_num, paths["yy"])
        wb.RefreshAll()

        # 5. Aktifkan Sheet Score
        ws_score = wb.Sheets("Score CostPerRevenue dan MoP")
        ws_score.Activate()
        ws_score.Cells(1, 1).Select()

        wb.Save()
        wb.Close(SaveChanges=False)
        print(f"[MASTER] File master berhasil disimpan di: {master_target}")
        return master_target


    finally:
        try:
            excel.Quit()
        except Exception:
            pass


def split_ke30_scoring_by_mpg(
    periode: str | datetime,
    base_drive: str = "D:\\Kerja",
    master_file: str | None = None,
    output_dir: str | None = None,
    target_mpgs: list[str] | None = None,
) -> list[str]:
    """Memecah file master scoring menjadi file per MPG (22 cabang)."""
    paths = resolve_scoring_paths(periode, base_drive)
    master_path = master_file or paths["scoring_master_file"]
    out_dir = output_dir or paths["scoring_ytdn_dir"]

    if not os.path.isfile(master_path):
        raise FileNotFoundError(f"File master scoring tidak ditemukan: {master_path}. Buat master terlebih dahulu.")

    os.makedirs(out_dir, exist_ok=True)

    master_base_name = os.path.splitext(os.path.basename(master_path))[0]
    mpgs_to_process = target_mpgs or list(MPG_MAPPING.keys())

    print("\n=======================================================")
    print(f" PEMECAHAN FILE KE30 SCORING PER MPG ({len(mpgs_to_process)} MPG)")
    print("=======================================================")
    print(f" File Master Sumber   : {master_path}")
    print(f" Direktori Output     : {out_dir}")
    print(f" Daftar MPG           : {', '.join(mpgs_to_process)}")
    print("-------------------------------------------------------")

    excel = win32com.client.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    excel.ScreenUpdating = False

    created_files = []
    summary_scores = []

    try:
        for idx, mpg in enumerate(mpgs_to_process, start=1):
            if mpg not in MPG_MAPPING:
                print(f"[{idx}/{len(mpgs_to_process)}] MPG '{mpg}' tidak dikenal di MPG_MAPPING. Dilewati.")
                continue

            divs = MPG_MAPPING[mpg]
            mpg_filename = f"{master_base_name} - {mpg}.xlsx"
            mpg_file_path = os.path.join(out_dir, mpg_filename)

            print(f"[{idx}/{len(mpgs_to_process)}] Memproses MPG {mpg} (Div: {', '.join(divs)}) -> {mpg_filename} ...")

            shutil.copyfile(master_path, mpg_file_path)
            wb = excel.Workbooks.Open(mpg_file_path)

            try:
                # 1. Filter & Hapus Divisi lain di 'RAW ACH YTD 2026'
                ws_ach = wb.Sheets("RAW ACH YTD 2026")
                last_row_ach = ws_ach.Cells(ws_ach.Rows.Count, 1).End(-4162).Row  # xlUp
                rng_ach = ws_ach.Range(f"A1:T{last_row_ach}")

                if len(divs) == 1:
                    rng_ach.AutoFilter(Field=3, Criteria1=f"<>{divs[0]}")
                elif len(divs) == 2:
                    rng_ach.AutoFilter(Field=3, Criteria1=f"<>{divs[0]}", Operator=1, Criteria2=f"<>{divs[1]}")

                try:
                    del_rng_ach = ws_ach.Range(f"A2:T{last_row_ach}").SpecialCells(12)
                    del_rng_ach.EntireRow.Delete()
                except Exception:
                    pass

                if ws_ach.AutoFilterMode:
                    ws_ach.AutoFilterMode = False

                # 2. Filter & Hapus Divisi lain di 'RAW TARGET YTD DEC25'
                ws_tgt = wb.Sheets("RAW TARGET YTD DEC25")
                last_row_tgt = ws_tgt.Cells(ws_tgt.Rows.Count, 1).End(-4162).Row
                rng_tgt = ws_tgt.Range(f"A1:T{last_row_tgt}")

                if len(divs) == 1:
                    rng_tgt.AutoFilter(Field=3, Criteria1=f"<>{divs[0]}")
                elif len(divs) == 2:
                    rng_tgt.AutoFilter(Field=3, Criteria1=f"<>{divs[0]}", Operator=1, Criteria2=f"<>{divs[1]}")

                try:
                    del_rng_tgt = ws_tgt.Range(f"A2:T{last_row_tgt}").SpecialCells(12)
                    del_rng_tgt.EntireRow.Delete()
                except Exception:
                    pass

                if ws_tgt.AutoFilterMode:
                    ws_tgt.AutoFilterMode = False

                # 3. Penyesuaian Formula Khusus E1 & I1 pada sheet 'MoP '
                ws_mop = wb.Sheets("MoP ")
                if mpg in ("E1", "I1"):
                    ws_mop.Range("E8").Formula = f'=VLOOKUP("{mpg}",\'Target MoP\'!A:N,\'MoP (2)\'!C2+2,FALSE)'
                    ws_mop.Range("E9").Formula = "=B10/E8"
                    ws_mop.Range("E10").Formula = "=IF(B10/E8>1.85,5,_xlfn.XLOOKUP(ROUND(B10/E8,2),'5 Scale-2021'!A:A,'5 Scale-2021'!B:B))"
                else:
                    ws_mop.Range("E8").Formula = "=VLOOKUP(A8,'Target MoP'!B:N,'MoP (2)'!C2+1,FALSE)"
                    ws_mop.Range("E9").Formula = "=B8/E8"
                    ws_mop.Range("E10").Formula = "=IF(B8/E8>1.85,5,_xlfn.XLOOKUP(ROUND(B8/E8,2),'5 Scale-2021'!A:A,'5 Scale-2021'!B:B))"

                # 4. Refresh All Pivot Tables
                wb.RefreshAll()

                # 5. Aktifkan Sheet Score CostPerRevenue dan MoP
                ws_score = wb.Sheets("Score CostPerRevenue dan MoP")
                ws_score.Activate()
                ws_score.Cells(1, 1).Select()

                mop_val = ws_score.Range("B4").Value
                cost_val = ws_score.Range("C4").Value
                summary_scores.append((mpg, divs, mop_val, cost_val))

                wb.Save()
                wb.Close(SaveChanges=False)
                created_files.append(mpg_file_path)
                print(f"     -> Berhasil! Score MoP: {mop_val}, Cost/Rev: {cost_val}")

            except Exception as e:
                print(f"     -> Error memproses MPG {mpg}: {e}")
                try:
                    wb.Close(SaveChanges=False)
                except Exception:
                    pass

        print("\n=======================================================")
        print(f" RINGKASAN SCORING KE30 YTDN ({len(created_files)} FILE BERHASIL)")
        print("=======================================================")
        print(f"{'MPG':<6} | {'Divisi':<10} | {'5 Scale MoP':<14} | {'5 Scale Cost/Rev':<16}")
        print("-" * 55)
        for item in summary_scores:
            m_mpg, m_divs, m_mop, m_cost = item
            div_str = ",".join(m_divs)
            mop_disp = f"{m_mop:.2f}" if isinstance(m_mop, (int, float)) else str(m_mop)
            cost_disp = f"{m_cost:.2f}" if isinstance(m_cost, (int, float)) else str(m_cost)
            print(f"{m_mpg:<6} | {div_str:<10} | {mop_disp:<14} | {cost_disp:<16}")
        print("=======================================================\n")

        return created_files

    finally:
        try:
            excel.Quit()
        except Exception:
            pass


DEFAULT_CSM_EMAIL = "dhani.yudhiantoro@astragraphia.co.id"
DEFAULT_CC_EMAILS = "Dhani Yudhiantoro <Dhani.Yudhiantoro@astragraphia.co.id>; Okky Chandra <Okky.Chandra@astragraphia.co.id>; Radite Bryllianto <Radite.Bryllianto@astragraphia.co.id>; Ummul Afifah <Ummul.Afifah@astragraphia.co.id>"


def fetch_csm_email_map(db_config: dict | None = None) -> dict[str, str]:
    """Mengambil pemetaan email CSM per MPG dari database Dispatcher.dbo.TB_M_Workcentre.

    Query:
        SELECT WorkCentre AS MPG, Email
        FROM Dispatcher.dbo.TB_M_Workcentre 
        WHERE LEN(Workcentre) = 2 AND
            ProdSupplyAreaDesc = 'TECHNICAL HEAD' AND
            FORMAT(UpdatedOn,'yyyy-MM-dd') = FORMAT(GETDATE(),'yyyy-MM-dd') AND
            Username IS NOT NULL
    """
    cfg = db_config or DB_CONFIG
    print("[DB] Mengambil data email CSM dari Dispatcher.dbo.TB_M_Workcentre ...")
    csm_map = {}
    try:
        conn = get_connection_with_retry(cfg)
        cursor = conn.cursor()
        query = """
            SELECT WorkCentre AS MPG, Email
            FROM Dispatcher.dbo.TB_M_Workcentre 
            WHERE LEN(Workcentre) = 2 AND
                ProdSupplyAreaDesc = 'TECHNICAL HEAD' AND
                FORMAT(UpdatedOn,'yyyy-MM-dd') = FORMAT(GETDATE(),'yyyy-MM-dd') AND
                Username IS NOT NULL
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        for r in rows:
            if r[0] and r[1]:
                mpg_key = str(r[0]).strip().upper()
                email_val = str(r[1]).strip()
                csm_map[mpg_key] = email_val
        print(f"[DB] Berhasil memuat {len(csm_map)} alamat email CSM dari database.")
    except Exception as e:
        print(f"[DB] Peringatan: Gagal mengambil email CSM dari DB ({e}). Menggunakan fallback default.")
    return csm_map


def send_csm_scoring_emails(
    periode: str | datetime,
    mpg_files: list[str],
    as_draft: bool = False,
    is_test: bool = True,
    to_email_override: str | None = None,
    cc_emails: str = DEFAULT_CC_EMAILS,
    csm_email_map: dict | None = None,
    db_config: dict | None = None,
) -> int:
    """Mengirim email laporan scoring per MPG ke masing-masing CSM via Outlook.

    Args:
        periode: Tanggal periode target (contoh: '2026-06-01').
        mpg_files: List file path XLSX per MPG yang akan dikirimkan.
        as_draft: Jika True, email hanya disimpan di folder Drafts Outlook.
        is_test: Jika True, hanya kirim ke dhani.yudhiantoro@astragraphia.co.id tanpa CC/BCC.
        to_email_override: Jika diisi, override alamat penerima.
        cc_emails: Daftar email CC saat non-test mode.
        csm_email_map: Dict mapping MPG -> email CSM jika tersedia.
        db_config: Konfigurasi database SQL Server.

    Returns:
        Jumlah email yang berhasil diproses/dikirim.
    """
    if not mpg_files:
        print("[EMAIL] Tidak ada file MPG yang diberikan untuk pengiriman email.")
        return 0

    if not is_test and csm_email_map is None:
        csm_email_map = fetch_csm_email_map(db_config=db_config)


    periode_dt = parse_period_date(periode)
    cur_m = periode_dt.month
    cur_y = periode_dt.year
    next_m = cur_m + 1 if cur_m < 12 else 1
    next_y = cur_y if cur_m < 12 else cur_y + 1

    cur_month_full = MONTH_MAP_FULL_ID[cur_m]
    next_month_full = MONTH_MAP_FULL_ID[next_m]
    cur_month_title = cur_month_full.capitalize()
    next_month_title = next_month_full.capitalize()

    subject = f"Data nilai MOP dan Cost Cons Per Revenue (CCPR) {cur_month_full} {cur_y} untuk Scoring {next_month_full} {next_y}"

    script_dir = os.path.dirname(os.path.abspath(__file__))
    img_path = os.path.join(script_dir, "assets", "iscore_guide.png")
    has_image = os.path.isfile(img_path)

    print("\n=======================================================")
    print(f" PENGIRIMAN EMAIL SCORING KE CSM ({len(mpg_files)} FILE)")
    print("=======================================================")
    print(f" Subject         : {subject}")
    print(f" Mode Test       : {'AKTIF (Hanya ke dhani.yudhiantoro@astragraphia.co.id, tanpa CC)' if is_test else 'NON-AKTIF (Kirim ke CSM & CC Team)'}")
    print(f" Output Type     : {'DRAFT (Simpan di Drafts)' if as_draft else 'SEND (Langsung Kirim)'}")
    if not is_test:
        print(f" CC              : {cc_emails}")
    print(f" Panduan Gambar  : {'Ditemukan' if has_image else 'Tidak ditemukan'}")
    print("-------------------------------------------------------")

    outlook = win32com.client.Dispatch("Outlook.Application")
    sent_count = 0

    for idx, fpath in enumerate(mpg_files, start=1):
        if not os.path.isfile(fpath):
            continue

        base_name = os.path.basename(fpath)
        mpg = base_name.split("-")[-1].replace(".xlsx", "").strip()

        if is_test:
            recipient = to_email_override or DEFAULT_CSM_EMAIL
            final_cc = ""
        else:
            if to_email_override:
                recipient = to_email_override
            elif csm_email_map and mpg in csm_email_map:
                recipient = csm_email_map[mpg]
            else:
                recipient = DEFAULT_CSM_EMAIL
            final_cc = cc_emails

        print(f"[{idx}/{len(mpg_files)}] Memproses email MPG {mpg} -> {recipient} (CC: '{final_cc}') ({base_name})...")

        mail = outlook.CreateItem(0)
        mail.To = recipient
        if final_cc:
            mail.CC = final_cc
        mail.Subject = subject

        if has_image:
            att_img = mail.Attachments.Add(img_path)
            att_img.PropertyAccessor.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x3712001F", "iscore_guide.png")

        mail.Attachments.Add(fpath)

        html_body = f"""
<html>
<body style="font-family: Calibri, Arial, sans-serif; font-size: 11pt; color: #000000; line-height: 1.4;">
<p style="font-weight: bold; color: #c00000; margin-bottom: 12px;">[STRICTLY CONFIDENTIAL]</p>

<p>Dear Bapak CSM,</p>

<p>Berikut kami sampaikan data detail pencapaian item scoring MOP dan Cost Consumable per Revenue (CCPR) periode <span style="background-color: #e040fb; color: #ffffff; font-weight: bold; padding: 1px 4px;">{cur_month_title} {cur_y}</span> untuk scoring {next_month_title} {next_y}.</p>

<p>Silahkan untuk dapat memberikan penilaian kepada anggota team dalam bentuk 5 scale <u>dengan rata-rata nilai Teknisi tidak boleh di atas nilai CSM</u> seperti contoh dibawah ini.</p>

<p>Saat ini, untuk melakukan submit data ini dapat dilakukan dengan cara mengupload melalui aplikasi iScore dengan Langkah-langkah sebagai berikut :</p>

<p style="margin-left: 20px;">
Melalui upload data ke <a href="http://172.30.155.20:3000/">iScore</a> di <a href="http://172.30.155.20:3000/">http://172.30.155.20:3000/</a><br>
-&nbsp;&nbsp;&nbsp;&nbsp;Login menggunakan user domain<br>
-&nbsp;&nbsp;&nbsp;&nbsp;Pilih menu Input Data CSM<br>
-&nbsp;&nbsp;&nbsp;&nbsp;Klik tombol Download template CSM (input nilai Cost Cons / Revenue) dan tombol Download Template Ijin (input data SPD dan training Teknisi)<br>
-&nbsp;&nbsp;&nbsp;&nbsp;Pilih periode data yang ingin di upload. Untuk periode kali ini pilih bulan <span style="background-color: #e040fb; color: #ffffff; font-weight: bold; padding: 1px 4px;">{cur_month_title}</span>, sedangkan tahun <span style="background-color: #e040fb; color: #ffffff; font-weight: bold; padding: 1px 4px;">{cur_y}</span><br>
-&nbsp;&nbsp;&nbsp;&nbsp;Upload data yang sudah diisikan di file template
</p>

<p style="margin-left: 20px; margin-top: 15px; margin-bottom: 15px;">
<img src="cid:iscore_guide.png" alt="Panduan iScore" style="border: 1px solid #d0d0d0; max-width: 750px;">
</p>

<p>Jika masih terdapat nilai yang belum sesuai pada aplikasi iScore, silahkan dapat disampaikan atau berdiskusi dengan kami.</p>

<p>Terima kasih.</p>

<p>Salam,<br><br>
<b>Dhani Y.</b><br>
Service Planning<br>
System & Data Analyst</p>
</body>
</html>
"""
        mail.HTMLBody = html_body

        if as_draft:
            mail.Save()
            print("     -> Disimpan di Drafts Outlook!")
        else:
            mail.Send()
            print("     -> Email Terkirim!")

        sent_count += 1

    print(f"\n[EMAIL] Selesai memproses {sent_count} email CSM.\n")
    return sent_count


def main():
    parser = argparse.ArgumentParser(description="Otomasi Pembuatan dan Pemecahan File KE30 YTDN Scoring")
    parser.add_argument("--periode", required=True, help="Periode target (contoh: 2026-06-01)")
    parser.add_argument("--action", choices=["all", "master", "split"], default="all", help="Aksi: 'all' (Master + Split), 'master', atau 'split'")
    parser.add_argument("--source", choices=["db", "dat"], default="db", help="Sumber data: 'db' (SQL Server KE30) atau 'dat' (file .dat lokal)")
    parser.add_argument("--mpg", default="ALL", help="Daftar MPG (contoh: 'ALL' atau 'A1,B1,E1,I1')")
    parser.add_argument("--base-drive", default="D:\\Kerja", help="Root base drive (default: D:\\Kerja)")
    parser.add_argument("--output-dir", default="", help="Override folder output")
    parser.add_argument("--master-file", default="", help="Path file master khusus jika di-override")
    parser.add_argument("--force-master", default="False", help="Paksa buat ulang master dari template bulan lalu (True/False)")
    parser.add_argument("--send-email", default="False", help="Kirim email ke masing-masing CSM via Outlook (True/False)")
    parser.add_argument("--test-mode", default="True", help="Mode Testing: Hanya kirim ke dhani tanpa CC (True/False)")
    parser.add_argument("--email-draft", default="True", help="Simpan email sebagai Draft di Outlook alih-alih langsung kirim (True/False)")
    parser.add_argument("--csm-email", default="", help="Override alamat email CSM penerima")
    parser.add_argument("--cc-emails", default=DEFAULT_CC_EMAILS, help="Alamat email CC")
    parser.add_argument("--db-server", default=DB_CONFIG["server"])
    parser.add_argument("--db-user", default=DB_CONFIG["user"])
    parser.add_argument("--db-pwd", default=DB_CONFIG["pwd"])
    parser.add_argument("--db-name", default=DB_CONFIG["name"])
    args = parser.parse_args()

    # Parse boolean flags dari CLI string
    is_force_master = str(args.force_master).strip().lower() in ("true", "1", "yes")
    is_send_email = str(args.send_email).strip().lower() in ("true", "1", "yes")
    is_test_mode = str(args.test_mode).strip().lower() in ("true", "1", "yes")
    is_email_draft = str(args.email_draft).strip().lower() in ("true", "1", "yes")

    db_config = {
        "server": args.db_server,
        "user": args.db_user,
        "pwd": args.db_pwd,
        "db": args.db_name,
    }

    target_mpgs = None
    if args.mpg.upper() != "ALL":
        target_mpgs = [m.strip().upper() for m in args.mpg.split(",") if m.strip()]

    out_dir = args.output_dir if args.output_dir else None
    master_path = args.master_file if args.master_file else None
    created_mpg_files = []

    if args.action in ("all", "master"):
        master_path = generate_ke30_scoring_master(
            periode=args.periode,
            base_drive=args.base_drive,
            output_file=master_path,
            output_dir=out_dir,
            force_recreate=is_force_master,
            source=args.source,
            db_config=db_config,
        )

    if args.action in ("all", "split"):
        created_mpg_files = split_ke30_scoring_by_mpg(
            periode=args.periode,
            base_drive=args.base_drive,
            master_file=master_path,
            output_dir=out_dir,
            target_mpgs=target_mpgs,
        )

    if is_send_email and created_mpg_files:
        to_override = args.csm_email if args.csm_email else None
        send_csm_scoring_emails(
            periode=args.periode,
            mpg_files=created_mpg_files,
            as_draft=is_email_draft,
            is_test=is_test_mode,
            to_email_override=to_override,
            cc_emails=args.cc_emails,
            db_config=db_config,
        )


if __name__ == "__main__":
    main()


