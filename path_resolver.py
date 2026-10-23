"""path_resolver.py — Modul Resolusi Path Dinamis Berbasis Struktur Folder Astragraphia.

Menerapkan pola baku yang terdapat di D:\\Kerja\\:
  1. Root CSSD:
     D:\\Kerja\\{YYYY} CSSD\\
  2. Reporting SS (untuk ZSMR007B, ZSME09E, ZSMR019):
     D:\\Kerja\\{YYYY} CSSD\\02. REPORTING {YYYY}\\{MM} {MMM} {YYYY} REPORTING\\SS\\
     - ZSMR007B: ...\\SS\\ZSMR007\\
     - ZSME09E : ...\\SS\\ZSME09E\\
     - ZSMR019 : ...\\SS\\
  3. KE30:
     D:\\Kerja\\{YYYY} CSSD\\03. KE30\\KE30 - {MM} {MMM} {yy}\\
     - By Divisi   : ...\\AUTO\\BY DIV\\
     - By Equipment: ...\\ (file: CMNW by EQ-{MMyy}-{ddMMyy}.dat)
"""

import os
from datetime import datetime, timedelta


MONTH_MAP_EN = {
    1: "JAN", 2: "FEB", 3: "MAR", 4: "APR",
    5: "MAY", 6: "JUN", 7: "JUL", 8: "AUG",
    9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC"
}


def get_smart_spool_date_range(ref_date: datetime | None = None) -> tuple[str, str]:
    """Menghasilkan rentang tanggal (from_date, to_date) dalam format 'dd.MM.yyyy' untuk spool SAP.

    Logika Cerdas:
    - Hari Senin (weekday 0) : from_date mundur 3 hari (Jumat / H-3)
    - Hari Minggu (weekday 6): from_date mundur 2 hari (Jumat / H-2)
    - Hari Lainnya           : from_date mundur 1 hari (Kemarin / H-1)
    - to_date                : Hari ini (ref_date)
    """
    today = ref_date or datetime.now()
    weekday = today.weekday()

    if weekday == 0:  # Hari Senin
        from_dt = today - timedelta(days=3)
    elif weekday == 6:  # Hari Minggu
        from_dt = today - timedelta(days=2)
    else:  # Selasa s/d Sabtu
        from_dt = today - timedelta(days=1)

    return from_dt.strftime("%d.%m.%Y"), today.strftime("%d.%m.%Y")


def get_cascading_spool_date_ranges(ref_date: datetime | None = None) -> list[tuple[str, str, str]]:
    """Menghasilkan daftar rentang tanggal bertahap (tier_label, from_date, to_date)
    untuk pencarian spool bertingkat (Cascading Lookback):
    1. Primary : Kemarin (H-1) atau Jumat (H-3 jika Senin)
    2. Extended: 5 Hari ke Belakang (H-5 - Mengantisipasi Libur/Cuti Bersama)
    3. Maximum : 7 Hari ke Belakang (H-7 - 1 Minggu Penuh)
    """
    today = ref_date or datetime.now()
    weekday = today.weekday()
    today_str = today.strftime("%d.%m.%Y")

    if weekday == 0:  # Hari Senin
        h_primary = today - timedelta(days=3)
        label_1 = f"H-3 Jumat ({h_primary.strftime('%d.%m.%Y')})"
    elif weekday == 6:  # Hari Minggu
        h_primary = today - timedelta(days=2)
        label_1 = f"H-2 Jumat ({h_primary.strftime('%d.%m.%Y')})"
    else:
        h_primary = today - timedelta(days=1)
        label_1 = f"H-1 Kemarin ({h_primary.strftime('%d.%m.%Y')})"

    h_extended = today - timedelta(days=5)
    h_max = today - timedelta(days=7)

    return [
        (label_1, h_primary.strftime("%d.%m.%Y"), today_str),
        (f"H-5 ({h_extended.strftime('%d.%m.%Y')})", h_extended.strftime("%d.%m.%Y"), today_str),
        (f"H-7 / 1 Minggu ({h_max.strftime('%d.%m.%Y')})", h_max.strftime("%d.%m.%Y"), today_str),
    ]


def parse_period_date(periode: str | datetime) -> datetime:
    """Konversi input periode (string YYYY-MM-DD atau datetime) ke objek datetime."""
    if isinstance(periode, datetime):
        return periode
    text = str(periode).strip()
    # Jika format YYYY-MM-DD
    try:
        return datetime.strptime(text.split()[0], "%Y-%m-%d")
    except Exception:
        pass
    # Fallback format dd.MM.yyyy
    try:
        return datetime.strptime(text, "%d.%m.%Y")
    except Exception:
        pass
    # Default ke hari ini
    return datetime.now()


def resolve_workspace_paths(periode: str | datetime, base_drive: str = "D:\\Kerja") -> dict:
    """Menghasilkan pemetaan path lengkap untuk seluruh kebutuhan otomatisasi SAP.

    Args:
        periode: Tanggal periode target (contoh: '2026-06-01' atau datetime).
        base_drive: Root drive kerja (default: 'D:\\Kerja').

    Returns:
        dict dengan kunci path lengkap:
          - yyyy, yy, mm, mmm, mmyy
          - cssd_root
          - reporting_ss
          - zsmr007b_dir
          - zsme09e_dir
          - zsmr019_dir
          - zsmr019_filename
          - ke30_root
          - ke30_div_dir
          - ke30_eq_dir
          - ke30_eq_raw_filename
          - ke30_eq_combined_filename
    """
    dt = parse_period_date(periode)
    yyyy = dt.strftime("%Y")        # "2026"
    yy = dt.strftime("%y")          # "26"
    mm = dt.strftime("%m")          # "06"
    month_int = dt.month
    mmm = MONTH_MAP_EN.get(month_int, dt.strftime("%b").upper())  # "JUN"
    mmyy = dt.strftime("%m%y")      # "0626"
    ddmmyy_today = datetime.now().strftime("%d%m%y")

    cssd_root = os.path.join(base_drive, f"{yyyy} CSSD")
    reporting_dir_name = f"{mm} {mmm} {yyyy} REPORTING"
    reporting_root = os.path.join(cssd_root, f"02. REPORTING {yyyy}", reporting_dir_name, "SS")

    zsmr007b_dir = os.path.join(reporting_root, "ZSMR007")
    zsme09e_dir = os.path.join(reporting_root, "ZSME09E")
    zsmr012_dir = os.path.join(reporting_root, "ZSMR012")
    iw58_dir = os.path.join(reporting_root, "IW58")
    iw73_dir = os.path.join(reporting_root, "IW73")
    zsmr019_dir = reporting_root
    zsmr019_filename = f"ZSMR019 - {mmyy} - {ddmmyy_today}.txt"

    ke30_month_dir = f"KE30 - {mm} {mmm} {yy}"
    ke30_root = os.path.join(cssd_root, "03. KE30", ke30_month_dir)
    ke30_div_dir = os.path.join(ke30_root, "AUTO", "BY DIV")
    ke30_eq_dir = ke30_root
    ke30_eq_raw_filename = f"CMNW by EQ-{mmyy}-{ddmmyy_today}.dat"
    ke30_eq_combined_filename = f"Combined_KE30_ByEq_{dt.strftime('%Y-%m-%d')}.txt"

    return {
        "yyyy": yyyy,
        "yy": yy,
        "mm": mm,
        "mmm": mmm,
        "mmyy": mmyy,
        "cssd_root": os.path.abspath(cssd_root),
        "reporting_ss": os.path.abspath(reporting_root),
        "zsmr007b_dir": os.path.abspath(zsmr007b_dir),
        "zsme09e_dir": os.path.abspath(zsme09e_dir),
        "zsmr012_dir": os.path.abspath(zsmr012_dir),
        "iw58_dir": os.path.abspath(iw58_dir),
        "iw73_dir": os.path.abspath(iw73_dir),
        "zsmr019_dir": os.path.abspath(zsmr019_dir),
        "zsmr019_filename": zsmr019_filename,
        "ke30_root": os.path.abspath(ke30_root),
        "ke30_div_dir": os.path.abspath(ke30_div_dir),
        "ke30_eq_dir": os.path.abspath(ke30_eq_dir),
        "ke30_eq_raw_filename": ke30_eq_raw_filename,
        "ke30_eq_combined_filename": ke30_eq_combined_filename,
    }


def ensure_workspace_directories(paths: dict) -> None:
    """Membuat direktori kerja jika belum ada di disk."""
    for key in ("zsmr007b_dir", "zsme09e_dir", "zsmr012_dir", "iw58_dir", "iw73_dir", "zsmr019_dir", "ke30_div_dir", "ke30_eq_dir", "scoring_ytdn_dir"):
        target_dir = paths.get(key)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)


MONTH_MAP_ID = {
    1: "JAN", 2: "FEB", 3: "MAR", 4: "APR",
    5: "MEI", 6: "JUN", 7: "JUL", 8: "AGU",
    9: "SEP", 10: "OKT", 11: "NOV", 12: "DES"
}

MONTH_MAP_FULL_ID = {
    1: "JANUARI", 2: "FEBRUARI", 3: "MARET", 4: "APRIL",
    5: "MEI", 6: "JUNI", 7: "JULI", 8: "AGUSTUS",
    9: "SEPTEMBER", 10: "OKTOBER", 11: "NOVEMBER", 12: "DESEMBER"
}


def resolve_scoring_paths(periode: str | datetime, base_drive: str = "D:\\Kerja") -> dict:
    """Menghasilkan pemetaan path lengkap untuk proses Scoring KE30 YTDN.

    Mendukung deteksi folder fleksibel (MEI/MAY, JUN/JUNI, dsb).
    """
    dt = parse_period_date(periode)
    yyyy = dt.strftime("%Y")
    yy = dt.strftime("%y")
    mm = dt.strftime("%m")
    m = dt.month
    mmm_en = MONTH_MAP_EN.get(m, "JUN")
    mmm_id = MONTH_MAP_ID.get(m, "JUN")

    # Hitung periode bulan sebelumnya (H-1 Bulan)
    if m == 1:
        prev_dt = datetime(dt.year - 1, 12, 1)
    else:
        prev_dt = datetime(dt.year, m - 1, 1)
    prev_yyyy = prev_dt.strftime("%Y")
    prev_yy = prev_dt.strftime("%y")
    prev_mm = prev_dt.strftime("%m")
    prev_m = prev_dt.month
    prev_mmm_en = MONTH_MAP_EN.get(prev_m, "MAY")
    prev_mmm_id = MONTH_MAP_ID.get(prev_m, "MEI")

    # Hitung periode scoring selanjutnya (H+1 Bulan) untuk teks banner
    if m == 12:
        next_dt = datetime(dt.year + 1, 1, 1)
    else:
        next_dt = datetime(dt.year, m + 1, 1)
    next_full_id = MONTH_MAP_FULL_ID.get(next_dt.month, "JULI")
    next_yyyy = next_dt.strftime("%Y")

    cssd_root = os.path.join(base_drive, f"{yyyy} CSSD")
    scoring_base = os.path.join(cssd_root, f"01. SCORING {yyyy}")

    # Deteksi folder bulan berjalan di bawah SCORING
    possible_month_dir_names = [
        f"{mm} {mmm_id} {yyyy} SCORING",
        f"{mm} {mmm_en} {yyyy} SCORING",
        f"{mm}. {mmm_id} {yyyy} SCORING",
        f"{mm}. {mmm_en} {yyyy} SCORING",
    ]
    cur_scoring_month_dir = os.path.join(scoring_base, possible_month_dir_names[0])
    for name in possible_month_dir_names:
        candidate = os.path.join(scoring_base, name)
        if os.path.isdir(candidate):
            cur_scoring_month_dir = candidate
            break

    cur_automatic_dir = os.path.join(cur_scoring_month_dir, "AUTOMATIC")

    # Deteksi folder KE30 YTDN bulan berjalan
    possible_ytdn_dir_names = [
        f"KE30 YTDN {mmm_en} {yy}",
        f"KE30 YTDN {mmm_id} {yy}",
    ]
    scoring_ytdn_dir = os.path.join(cur_automatic_dir, possible_ytdn_dir_names[0])
    for name in possible_ytdn_dir_names:
        candidate = os.path.join(cur_automatic_dir, name)
        if os.path.isdir(candidate):
            scoring_ytdn_dir = candidate
            break

    # Master file target
    scoring_master_file = os.path.join(scoring_ytdn_dir, f"KE30 YTDN Scoring {mmm_en} {yy}.xlsx")

    # Deteksi file master bulan sebelumnya
    prev_scoring_base = os.path.join(base_drive, f"{prev_yyyy} CSSD", f"01. SCORING {prev_yyyy}")
    possible_prev_month_dirs = [
        f"{prev_mm} {prev_mmm_id} {prev_yyyy} SCORING",
        f"{prev_mm} {prev_mmm_en} {prev_yyyy} SCORING",
    ]
    prev_scoring_master_file = None
    for p_name in possible_prev_month_dirs:
        p_auto = os.path.join(prev_scoring_base, p_name, "AUTOMATIC")
        for ytdn_sub in [f"KE30 YTDN {prev_mmm_en} {prev_yy}", f"KE30 YTDN {prev_mmm_id} {prev_yy}"]:
            cand_file1 = os.path.join(p_auto, ytdn_sub, f"KE30 YTDN Scoring {prev_mmm_en} {prev_yy}.xlsx")
            cand_file2 = os.path.join(p_auto, ytdn_sub, f"KE30 YTDN Scoring {prev_mmm_id} {prev_yy}.xlsx")
            cand_file3 = os.path.join(p_auto, f"KE30 YTDN Scoring {prev_mmm_en} {prev_yy}.xlsx")
            cand_file4 = os.path.join(p_auto, f"KE30 YTDN Scoring {prev_mmm_id} {prev_yy}.xlsx")
            for cf in [cand_file1, cand_file2, cand_file3, cand_file4]:
                if os.path.isfile(cf):
                    prev_scoring_master_file = cf
                    break
            if prev_scoring_master_file:
                break
        if prev_scoring_master_file:
            break

    # Folder raw .dat bulanan
    ke30_month_raw_dirs = [
        os.path.join(cssd_root, "03. KE30", f"KE30 - {mm} {mmm_en} {yy}", "All Div", "YTDN-DN"),
        os.path.join(cssd_root, "03. KE30", f"KE30 - {mm} {mmm_id} {yy}", "All Div", "YTDN-DN"),
        os.path.join(cssd_root, "03. KE30", f"KE30 - {mm} {mmm_en} {yy}", "AUTO", "BY DIV"),
    ]
    ke30_month_raw_dir = ke30_month_raw_dirs[0]
    for rd in ke30_month_raw_dirs:
        if os.path.isdir(rd):
            ke30_month_raw_dir = rd
            break

    return {
        "yyyy": yyyy,
        "yy": yy,
        "mm": mm,
        "month_int": m,
        "mmm_en": mmm_en,
        "mmm_id": mmm_id,
        "next_full_id": next_full_id,
        "next_yyyy": next_yyyy,
        "cssd_root": os.path.abspath(cssd_root),
        "cur_scoring_month_dir": os.path.abspath(cur_scoring_month_dir),
        "cur_automatic_dir": os.path.abspath(cur_automatic_dir),
        "scoring_ytdn_dir": os.path.abspath(scoring_ytdn_dir),
        "scoring_master_file": os.path.abspath(scoring_master_file),
        "prev_scoring_master_file": os.path.abspath(prev_scoring_master_file) if prev_scoring_master_file else None,
        "ke30_month_raw_dir": os.path.abspath(ke30_month_raw_dir),
    }

