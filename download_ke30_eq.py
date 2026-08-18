import subprocess
import os
import argparse
from datetime import datetime


def main(periode_override: str | None, vbs_path: str, save_path: str):
    if periode_override:
        periode_str = periode_override.strip()
    else:
        periode_str = datetime.now().strftime("%Y-%m-%d")

    try:
        dt = datetime.strptime(periode_str, "%Y-%m-%d")
        period_tag = dt.strftime("%m%y")  # e.g. 0726 for July 2026
    except Exception:
        period_tag = datetime.now().strftime("%m%y")

    resolved_save_path = os.path.abspath(save_path)
    os.makedirs(resolved_save_path, exist_ok=True)

    resolved_vbs = os.path.abspath(vbs_path)

    print("=" * 60)
    print(f"[CONFIG] Job                     : DOWNLOAD LAPORAN KE30 – By Eq")
    print(f"[CONFIG] Periode                 : {periode_str}")
    print(f"[CONFIG] Tag Periode (MMYY)      : {period_tag}")
    print(f"[CONFIG] Save Path               : {resolved_save_path}")
    print(f"[CONFIG] VBS Path                : {resolved_vbs}")
    print("=" * 60)

    if not os.path.exists(resolved_vbs):
        print(f"[ERROR] File VBS tidak ditemukan di {resolved_vbs}")
        return

    print(f"\n[EXEC] Menjalankan VBScript: {resolved_vbs}")
    try:
        subprocess.run(
            ["wscript.exe", resolved_vbs, period_tag, resolved_save_path],
            check=True
        )
        print("[SUCCESS] Proses download KE30 By Eq via SAP GUI VBScript telah selesai.")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Eksekusi VBScript gagal dengan returncode {e.returncode}")
    except Exception as e:
        print(f"[ERROR] Gagal menjalankan VBScript: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download Laporan KE30 by Equipment dari SAP GUI")
    parser.add_argument("--periode", default=None, help="Periode (format YYYY-MM-DD). Default: hari ini")
    parser.add_argument("--vbs-path", default="vbs\\KE30 Get CMNWDN by Eq.vbs", help="Path ke file VBS")
    parser.add_argument("--save-path", default="D:\\Kerja\\2026 CSSD\\03. KE30\\KE30 - 07 JUL 26\\", help="Folder tujuan simpan file .dat")

    args = parser.parse_args()
    main(args.periode, args.vbs_path, args.save_path)
