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
    for key in ("zsmr007b_dir", "zsme09e_dir", "zsmr019_dir", "ke30_div_dir", "ke30_eq_dir"):
        target_dir = paths.get(key)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
