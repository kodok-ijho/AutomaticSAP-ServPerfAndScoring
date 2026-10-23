import subprocess
import os
import sys
import argparse
from datetime import datetime, timedelta

# Pastikan output stream menggunakan UTF-8 di Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from db_utils import get_connection_with_retry
from sap_utils import run_vbs

def main(tanggal_override: str | None, periode_override: str | None, vbs_path: str, save_path: str):
    # 1. Tentukan tanggal input (To Date)
    if tanggal_override:
        tanggal_input = tanggal_override
        print(f"[CONFIG] Tanggal Input (manual)    : {tanggal_input}")
    else:
        tanggal_input = datetime.now().strftime("%d.%m.%Y")
        print(f"[CONFIG] Tanggal Input (hari ini)  : {tanggal_input}")

    # Hitung From Date = tanggal - 1 hari
    tanggal_dt = datetime.strptime(tanggal_input, "%d.%m.%Y")
    from_date  = (tanggal_dt - timedelta(days=1)).strftime("%d.%m.%Y")

    print(f"[CONFIG] From Date (H-1)           : {from_date}")
    print(f"[CONFIG] To Date                   : {tanggal_input}")
    print(f"[CONFIG] Periode Override           : {periode_override or '(dari database)'}")
    print(f"[CONFIG] Save Path                 : {save_path}")
    print(f"[CONFIG] VBS Path                  : {vbs_path}")
    print("-" * 50)

    try:
        print("Menghubungkan ke database...")
        conn = get_connection_with_retry()
        cursor = conn.cursor()
        print("Berhasil terhubung ke database.")
    except Exception as e:
        print(f"Gagal menghubungkan ke database: {e}")
        return

    try:
        # 2. Ambil Periode dari DB (atau gunakan override)
        if periode_override:
            periode_folder = periode_override
            print(f"Periode Folder (manual override): {periode_folder}")
        else:
            query = """
                SELECT Periode
                FROM Tb_R_PeriodeClosing
                WHERE GETDATE() BETWEEN StartDate AND EndDate
            """
            cursor.execute(query)
            row = cursor.fetchone()

            if not row:
                print("Peringatan: Tidak ada data 'Periode' yang aktif hari ini.")
                return

            periode_raw = row[0]
            if hasattr(periode_raw, 'strftime'):
                periode_folder = periode_raw.strftime("%Y-%m-%d")
            else:
                periode_folder = str(periode_raw).split(" ")[0]

            print(f"Periode Folder (dari database): {periode_folder}")

        # 3. Jalankan VBS via sap_utils
        resolved_vbs = os.path.expandvars(vbs_path)
        if os.path.exists(resolved_vbs):
            print(f"\nMenjalankan skrip VBS: {resolved_vbs}")
            vbs_ok = run_vbs(resolved_vbs, [from_date, tanggal_input, save_path])
            if not vbs_ok:
                print("[ERROR] Eksekusi VBS SAP gagal. Download dibatalkan.")
                return
            print("Proses otomatisasi SAP (VBS) telah selesai.")

            # 4. Validasi Output File (Task 3.3)
            print(f"\n[VALIDASI] Memeriksa hasil export di: {save_path}")
            if not os.path.exists(save_path):
                print(f"[ERROR] Folder tujuan save-path tidak ditemukan: {save_path}")
                return
            files = [os.path.join(save_path, f) for f in os.listdir(save_path) if os.path.isfile(os.path.join(save_path, f))]
            if not files:
                print(f"[ERROR] Tidak ada file hasil download ditemukan di folder: {save_path}")
                return

            # Cari file yang baru dibuat/diubah
            valid_files = [f for f in files if os.path.getsize(f) > 0]
            if not valid_files:
                print(f"[ERROR] Semua file di {save_path} berukuran 0 byte (kosong). Export gagal.")
                return
            latest_file = max(valid_files, key=os.path.getmtime)
            size_kb = os.path.getsize(latest_file) / 1024
            print(f"[VALIDASI OK] File terverifikasi: {os.path.basename(latest_file)} ({size_kb:.1f} KB)")
        else:
            print(f"Peringatan: File VBS tidak ditemukan di {resolved_vbs}")

    except Exception as e:
        print(f"Terjadi kesalahan pada alur eksekusi: {e}")

    finally:
        try:
            cursor.close()
            conn.close()
            print("Koneksi database ditutup.")
        except Exception:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download ZSMR007B - SAP Background Job")
    parser.add_argument("--tanggal",
                        default=None,
                        help="Override tanggal input (format dd.MM.yyyy). Default: H-1 otomatis.")
    parser.add_argument("--periode",
                        default=None,
                        help="Override periode folder (format YYYY-MM-DD). Default: dari database.")
    parser.add_argument("--vbs-path",
                        default="vbs\\DownloadBGJob007B.vbs",
                        help="Path ke file VBS SAP GUI")
    parser.add_argument("--save-path",
                        default="D:\\Kerja\\SS\\",
                        help="Folder tujuan simpan file download (contoh: D:\\Kerja\\SS\\)")
    args = parser.parse_args()

    main(
        tanggal_override=args.tanggal,
        periode_override=args.periode,
        vbs_path=args.vbs_path,
        save_path=args.save_path,
    )
