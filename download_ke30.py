import subprocess
import os
import sys
import argparse
from datetime import datetime

# Pastikan output stream menggunakan UTF-8 di Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


from sap_utils import run_vbs


def main(periode_override: str | None, vbs_path: str, save_path: str):
    if periode_override:
        periode_str = periode_override.strip()
    else:
        periode_str = datetime.now().strftime("%Y-%m-%d")

    try:
        dt = datetime.strptime(periode_str, "%Y-%m-%d")
        year_str = dt.strftime("%Y")
        month_str = dt.strftime("%m")
    except Exception:
        year_str = datetime.now().strftime("%Y")
        month_str = datetime.now().strftime("%m")

    clean_save_path = save_path.strip().strip('"').strip("'").rstrip('\\').rstrip('/')
    resolved_save_path = os.path.abspath(clean_save_path)
    os.makedirs(resolved_save_path, exist_ok=True)

    resolved_vbs = os.path.abspath(vbs_path)

    print("=" * 60)
    print(f"[CONFIG] Job                     : DOWNLOAD LAPORAN KE30")
    print(f"[CONFIG] Periode                 : {periode_str}")
    print(f"[CONFIG] Tahun / Bulan           : {year_str} / {month_str}")
    print(f"[CONFIG] Save Path               : {resolved_save_path}")
    print(f"[CONFIG] VBS Path                : {resolved_vbs}")
    print("=" * 60)

    if not os.path.exists(resolved_vbs):
        print(f"[ERROR] File VBS tidak ditemukan di {resolved_vbs}")
        return

    print(f"\n[EXEC] Menjalankan VBScript: {resolved_vbs}")
    ok = run_vbs(resolved_vbs, [year_str, month_str, resolved_save_path])
    if ok:
        print("[SUCCESS] Proses download KE30 via SAP GUI VBScript telah selesai.")
    else:
        print("[ERROR] Eksekusi VBScript KE30 gagal.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download Laporan KE30 per Divisi dari SAP GUI")
    parser.add_argument("--periode", default=None, help="Periode (format YYYY-MM-DD). Default: hari ini")
    parser.add_argument("--vbs-path", default="vbs\\KE30 Get CMNWDN by Div.vbs", help="Path ke file VBS")
    parser.add_argument("--save-path", default="D:\\Kerja\\2026 CSSD\\03. KE30\\KE30 - 06 JUN 26\\AUTO\\BY DIV\\", help="Folder tujuan simpan file .dat")

    args = parser.parse_args()
    main(args.periode, args.vbs_path, args.save_path)
