"""download_iw73.py — Download Hasil Spool Background Job IW73 via SM37.

Alur Kerja:
1. Menentukan parameter tanggal From Date (H-1 / H-3 jika Senin) dan To Date (Hari ini).
2. Memeriksa ketersediaan folder penyimpanan lokal (membuatnya jika belum ada).
3. Memastikan session SAP GUI sudah aktif dan login via LoginSAP.vbs.
4. Menjalankan VBScript DownloadBGJob_IW73.vbs untuk mencari Job Name RIAUFK20 di SM37.
5. Mengunduh seluruh spool dari baris background job berstatus FINISHED.
6. Memvalidasi keberadaan dan ukuran file teks hasil unduhan (> 0 byte).
"""

import os
import sys
import glob
import argparse
from datetime import datetime, timedelta

# Pastikan output stream menggunakan UTF-8 di Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from sap_utils import ensure_sap_logged_in, run_vbs
from path_resolver import get_smart_spool_date_range, resolve_workspace_paths
from process_iw73 import process_and_upload_iw73


def resolve_dates(from_date_input: str | None, to_date_input: str | None) -> tuple[str, str]:
    """Menghitung rentang tanggal from_date dan to_date (format dd.MM.yyyy)."""
    # 1. To Date
    if to_date_input and to_date_input.strip() not in ("", "dynamic-today-dmy", "dynamic-today-ymd"):
        if "-" in to_date_input and len(to_date_input.split("-")) == 3:
            p = to_date_input.split("-")
            to_date = f"{p[2]}.{p[1]}.{p[0]}"
        else:
            to_date = to_date_input.strip()
    else:
        to_date = datetime.now().strftime("%d.%m.%Y")

    # 2. From Date
    if from_date_input and from_date_input.strip() not in ("", "dynamic-yesterday-dmy", "dynamic-yesterday-ymd"):
        if "-" in from_date_input and len(from_date_input.split("-")) == 3:
            p = from_date_input.split("-")
            from_date = f"{p[2]}.{p[1]}.{p[0]}"
        else:
            from_date = from_date_input.strip()
    else:
        # Gunakan Smart Spool Date Range (H-3 jika Senin, H-1 hari lainnya)
        try:
            dt_to = datetime.strptime(to_date, "%d.%m.%Y")
            smart_from, _ = get_smart_spool_date_range(dt_to)
            from_date = smart_from
        except Exception:
            from_date = (datetime.now() - timedelta(days=1)).strftime("%d.%m.%Y")

    return from_date, to_date


def main(
    to_date: str | None = None,
    from_date: str | None = None,
    job_name: str = "RIAUFK20",
    save_path: str = "D:\\Kerja\\SS\\IW73\\",
    file_prefix: str = "IW73_",
    vbs_path: str = "vbs\\DownloadBGJob_IW73.vbs",
    periode: str | None = None,
    insert_sql: bool | str = False,
    dry_run: bool = False,
    db_config: dict | None = None,
) -> int:
    resolved_from, resolved_to = resolve_dates(from_date, to_date)

    # Resolusi path dinamis jika ada periode spesifik atau save_path default
    effective_save_path = save_path
    if periode and (not save_path or save_path == "D:\\Kerja\\SS\\IW73\\"):
        try:
            paths = resolve_workspace_paths(periode)
            if "iw73_dir" in paths:
                effective_save_path = paths["iw73_dir"]
        except Exception as e:
            print(f"[WARN] Gagal resolusi path periode '{periode}': {e}")

    # Pastikan direktori tujuan memiliki trailing slash
    if not effective_save_path.endswith("\\") and not effective_save_path.endswith("/"):
        effective_save_path += "\\"

    print("=" * 68)
    print("  [JOB] DOWNLOAD BG JOB IW73 – SM37 Spool Downloader")
    print(f"  Target Job Name    : {job_name}")
    print(f"  Filter Dari Tanggal: {resolved_from} (From Date)")
    print(f"  Filter S/D Tanggal : {resolved_to} (To Date)")
    print(f"  Folder Penyimpanan : {effective_save_path}")
    print(f"  Prefix File Output : {file_prefix}")
    print(f"  File VBScript      : {vbs_path}")
    print(f"  Mode Simulasi      : {'YA (Dry Run)' if dry_run else 'TIDAK (Eksekusi SAP Langsung)'}")
    print("=" * 68)

    if dry_run:
        print("[DRY-RUN] Simulasi download selesai. Tidak ada panggilan VBScript ke SAP GUI.")
        return 0

    # 1. Pastikan folder tujuan download tersedia
    try:
        os.makedirs(effective_save_path, exist_ok=True)
        print(f"[FOLDER] Folder tujuan terverifikasi: {effective_save_path}")
    except Exception as e:
        print(f"[ERROR] Gagal membuat direktori {effective_save_path}: {e}")
        return 1

    # Bersihkan file spool lama dari folder sebelum download baru dimulai
    try:
        old_pattern = os.path.join(effective_save_path, f"{file_prefix}*.txt")
        old_files = glob.glob(old_pattern)
        if old_files:
            for old_f in old_files:
                try:
                    os.remove(old_f)
                except Exception:
                    pass
            print(f"[CLEANUP] Membersihkan {len(old_files)} file spool lama sebelum unduhan baru.")
    except Exception as e:
        print(f"[WARN] Kendala saat membersihkan file lama: {e}")

    # 2. Verifikasi keberadaan file VBScript
    resolved_vbs = os.path.abspath(os.path.expandvars(vbs_path))
    if not os.path.exists(resolved_vbs):
        print(f"[ERROR] File VBScript tidak ditemukan di: {resolved_vbs}")
        return 1

    # 3. Pastikan SAP GUI aktif dan login
    print("[SAP] Memeriksa status login SAP GUI...")
    login_vbs = os.path.join(os.path.dirname(resolved_vbs), "LoginSAP.vbs")
    if not os.path.exists(login_vbs):
        login_vbs = "vbs\\LoginSAP.vbs"

    sap_ready = ensure_sap_logged_in(login_vbs)
    if not sap_ready:
        print("[ERROR] SAP GUI belum siap atau gagal login otomatis. Proses dibatalkan.")
        return 1

    # Catat snapshot file sebelum download untuk mendeteksi file baru
    existing_files = set()
    if os.path.exists(effective_save_path):
        existing_files = set(os.listdir(effective_save_path))

    # 4. Jalankan script VBScript download SM37
    print(f"[SAP] Menjalankan VBScript SM37 download untuk job '{job_name}'...")
    vbs_args = [resolved_from, resolved_to, effective_save_path, job_name, file_prefix]
    success = run_vbs(resolved_vbs, vbs_args, interactive=False)

    if not success:
        print("[ERROR] Eksekusi VBScript download SM37 gagal.")
        return 1

    # 5. Verifikasi file hasil unduhan
    print("[VERIFIKASI] Memeriksa file hasil download di disk...")
    current_files = os.listdir(effective_save_path)
    downloaded_files = [
        f for f in current_files
        if f.startswith(file_prefix) and f.endswith(".txt")
    ]

    if not downloaded_files:
        print(f"[WARN] Tidak ditemukan file dengan prefix '{file_prefix}' di {effective_save_path}.")
        print("[INFO] Kemungkinan tidak ada spool job berstatus FINISHED pada rentang tanggal tersebut.")
        return 0

    valid_count = 0
    total_size = 0
    empty_spool_count = 0
    for f in downloaded_files:
        full_p = os.path.join(effective_save_path, f)
        size = os.path.getsize(full_p)
        total_size += size
        status_str = f"{size:,} bytes" if size > 0 else "0 byte (KOSONG)"
        print(f"  -> {f} : {status_str}")
        if size > 0:
            valid_count += 1
            try:
                with open(full_p, "r", encoding="utf-8", errors="ignore") as chk_f:
                    head_txt = "".join([chk_f.readline() for _ in range(15)]).lower()
                if "list does not contain any data" in head_txt or "keine daten vorhanden" in head_txt or "daftar tidak berisi data" in head_txt:
                    empty_spool_count += 1
            except Exception:
                pass

    if empty_spool_count > 0:
        print(f"[SM37 INFO] Terdeteksi {empty_spool_count} file spool berisi status 'List does not contain any data'.")
        print("            Laporan SAP tidak memiliki catatan transaksi untuk periode filter tersebut.")

    print("\n" + "=" * 68)
    print(f"  [SELESAI] Total file: {len(downloaded_files)} ({valid_count} valid >0 byte, {total_size:,} bytes total)")
    print("=" * 68)

    # Trigger auto-upload ke database DesSy jika insert_sql diaktifkan
    if str(insert_sql).strip().lower() in ("true", "1", "yes"):
        print("\n[AUTO-UPLOAD] Memulai upload data IW73 (Service) ke database DesSy...")
        upload_ret = process_and_upload_iw73(
            folder_path=effective_save_path,
            periode=periode,
            dry_run=dry_run,
            db_config=db_config,
        )
        return upload_ret

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download Hasil Spool Background Job IW73 via SM37."
    )
    parser.add_argument(
        "--to-date",
        default="dynamic-today-dmy",
        help="Tanggal akhir filter SM37 (format dd.MM.yyyy atau YYYY-MM-DD, default: hari ini)",
    )
    parser.add_argument(
        "--from-date",
        default="dynamic-yesterday-dmy",
        help="Tanggal awal filter SM37 (format dd.MM.yyyy atau YYYY-MM-DD, default: H-1 / H-3 jika Senin)",
    )
    parser.add_argument(
        "--job-name",
        default="RIAUFK20",
        help="Nama Background Job di SM37 (default: RIAUFK20)",
    )
    parser.add_argument(
        "--save-path",
        default="D:\\Kerja\\SS\\IW73\\",
        help="Folder tempat menyimpan file unduhan (default: D:\\Kerja\\SS\\IW73\\)",
    )
    parser.add_argument(
        "--file-prefix",
        default="IW73_",
        help="Prefix nama file hasil export (default: IW73_)",
    )
    parser.add_argument(
        "--vbs-path",
        default="vbs\\DownloadBGJob_IW73.vbs",
        help="Path file VBScript download (default: vbs\\DownloadBGJob_IW73.vbs)",
    )
    parser.add_argument(
        "--periode",
        default=None,
        help="Periode closing (format YYYY-MM-DD) untuk resolusi path dinamis jika diperlukan",
    )
    parser.add_argument(
        "--insert-sql",
        default="False",
        help="Upload data ke database DesSy setelah download selesai (True/False)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulasi proses tanpa memanggil SAP GUI / VBScript",
    )

    # DB arguments fallback (untuk kompatibilitas)
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

    exit_code = main(
        to_date=args.to_date,
        from_date=args.from_date,
        job_name=args.job_name,
        save_path=args.save_path,
        file_prefix=args.file_prefix,
        vbs_path=args.vbs_path,
        periode=args.periode,
        insert_sql=args.insert_sql,
        dry_run=args.dry_run,
        db_config=db_cfg,
    )
    sys.exit(exit_code)
