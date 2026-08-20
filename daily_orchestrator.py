"""daily_orchestrator.py — Master Orchestrator Otomatisasi Harian Terpadu (6 Tahapan).

Mengeksekusi seluruh siklus otomatisasi SAP secara end-to-end:
  1. Tahap 1: Membuat Background Job ZSMR007B per 1.000 equipment secara batch.
  2. Tahap 2: Mendownload spool ZSMR007B -> merge *1 & *2 -> upsert ke SQL (tabel ZSMR007B).
  3. Tahap 3: Mendownload KE30 per Divisi -> Excel COM mapping -> upsert ke SQL (tabel KE30).
  4. Tahap 4: Mendownload KE30 per Equipment -> parse Eq -> upsert ke SQL (tabel KE30_ByEq).
  5. Tahap 5: Mendownload ZSME09E Material Movement -> upsert ke SQL (tabel ZSME09E).
  6. Tahap 6: Mendownload ZSMR019 Service Order -> upsert ke SQL (tabel ZSMR019).
"""

import os
import sys
import time
import argparse
import traceback
from datetime import datetime

from config import DB_CONFIG
from db_utils import get_connection_with_retry
from sap_utils import ensure_sap_logged_in, verify_sap_ready, run_vbs
from path_resolver import resolve_workspace_paths, ensure_workspace_directories, get_smart_spool_date_range

# Import ETL helpers directly from pipeline modules for in-process high performance
import rpa_sap_1
import process_reports
import ProsesKE30byDiv
import ProcessKE30byEq
import automate_zsme09e
import download_zsmr019


def get_active_closing_period(db_config: dict | None = None) -> tuple[str, str, str]:
    """Mengambil periode closing aktif dari database (atau fallback).

    Returns:
        Tuple (periode_str_ymd, start_date_dmy, end_date_dmy)
    """
    try:
        conn = get_connection_with_retry(db_config)
        cursor = conn.cursor()
        query = "SELECT Periode, StartDate, EndDate FROM Tb_R_PeriodeClosing WHERE GETDATE() BETWEEN StartDate AND EndDate"
        cursor.execute(query)
        row = cursor.fetchone()
        if not row:
            # Fallback ambil record paling terakhir
            cursor.execute("SELECT TOP 1 Periode, StartDate, EndDate FROM Tb_R_PeriodeClosing ORDER BY Periode DESC")
            row = cursor.fetchone()

        cursor.close()
        conn.close()

        if row and row[0]:
            p = row[0].strftime("%Y-%m-%d") if hasattr(row[0], 'strftime') else str(row[0]).split()[0]
            s = row[1].strftime("%d.%m.%Y") if hasattr(row[1], 'strftime') else str(row[1])
            e = row[2].strftime("%d.%m.%Y") if hasattr(row[2], 'strftime') else str(row[2])
            return p, s, e
    except Exception as exc:
        print(f"[WARN] Gagal membaca Tb_R_PeriodeClosing: {exc}")

    today_p = datetime.now().strftime("%Y-%m-01")
    today_dmy = datetime.now().strftime("%d.%m.%Y")
    return today_p, today_dmy, today_dmy


def print_preflight_inspection(periode: str, paths: dict, stages_to_run: list[int], db_config: dict) -> None:
    """Mencetak tabel inspeksi variabel pre-flight untuk ditinjau oleh operator."""
    spool_from, spool_to = get_smart_spool_date_range()
    print("=" * 80)
    print(" [PRE-FLIGHT] DAILY AUTOMATION PIPELINE -- VARIABLE INSPECTOR")
    print("=" * 80)
    print(f" Target Periode           : {periode}")
    print(f" Root Workspace (CSSD)   : {paths['cssd_root']}")
    print(f" Reporting SS Base       : {paths['reporting_ss']}")
    print(f" Tahapan yang Dipilih    : {', '.join(f'Tahap {s}' for s in stages_to_run)}")
    print(f" Sched BG Job Jam (Thp 1): 17:00 Sore (Eksekusi Batch di Server SAP)")
    print(f" Spool Lookback (Tahap 2): {spool_from} s/d {spool_to} (Auto H-3 jika Senin)")
    print("-" * 80)
    print(f" [Tahap 1 & 2] ZSMR007B  : {paths['zsmr007b_dir']}")
    print(f" [Tahap 3] KE30 Divisi   : {paths['ke30_div_dir']}")
    print(f" [Tahap 4] KE30 Equipment: {paths['ke30_eq_dir']}")
    print(f" [Tahap 5] ZSME09E       : {paths['zsme09e_dir']}")
    print(f" [Tahap 6] ZSMR019       : {paths['zsmr019_dir']} (File: {paths['zsmr019_filename']})")
    print("-" * 80)
    print(f" Database Server         : {db_config['server']} / Database: {db_config.get('name') or db_config.get('db')}")
    print("=" * 80)
    sys.stdout.flush()


def run_stage_1_zsmr007b_bg(periode: str, batch_size: int, vbs_dir: str, db_config: dict) -> bool:
    """Tahap 1: Membuat Background Job ZSMR007B per 1.000 equipment."""
    print("\n" + "─" * 70)
    print(f" ▶ [TAHAP 1/6] MEMBUAT BACKGROUND JOB ZSMR007B (Batch {batch_size:,} Eq, Target: 17:00)")
    print("─" * 70)
    vbs_path = os.path.join(vbs_dir, "CreateBG007B-Scheduled.vbs")
    ret = rpa_sap_1.main(
        periode=periode,
        max_offset=0,  # 0 = seluruh equipment di Tb_R_SerPervEq
        batch_size=batch_size,
        delay_seconds=10,
        vbs_path=vbs_path,
        sched_start_time="17:00",
        db_config=db_config,
    )
    return ret == 0


def run_stage_2_zsmr007b_etl(periode: str, paths: dict, vbs_dir: str, db_config: dict) -> bool:
    """Tahap 2: Mendownload spool ZSMR007B -> merge *1 & *2 -> upsert ke SQL."""
    print("\n" + "─" * 70)
    print(" ▶ [TAHAP 2/6] DOWNLOAD & UPSERT DATA ZSMR007B KE SQL SERVER")
    print("─" * 70)
    folder = paths["zsmr007b_dir"]
    os.makedirs(folder, exist_ok=True)
    vbs_path = os.path.join(vbs_dir, "DownloadBGJob007B.vbs")

    # 1. Download via VBS dengan smart lookback (H-3 jika hari Senin, H-1 jika hari lain)
    from_date, to_date = get_smart_spool_date_range()
    save_path_arg = folder.rstrip("\\") + "\\"

    print(f"[STEP 2.1] Menjalankan VBScript download spool: {vbs_path}")
    print(f"           Rentang Spool: {from_date} s/d {to_date} (Smart Lookback)")
    vbs_ok = run_vbs(vbs_path, [from_date, to_date, save_path_arg])
    if not vbs_ok:
        print("[WARN] Eksekusi VBS download ZSMR007B mengalami kendala. Melanjutkan pemeriksaan file lokal...")

    # 2. Process reports and merge
    print(f"[STEP 2.2] Memproses file laporan di {folder}...")
    df1 = process_reports.process_files(folder, "1")
    df2 = process_reports.process_files(folder, "2")

    if df1 is not None and df2 is not None:
        import pandas as pd
        df1['Equipment'] = df1['Equipment'].astype(str)
        df2['Equipment'] = df2['Equipment'].astype(str)
        combined_all = pd.merge(df1, df2, on="Equipment", how="inner", suffixes=('_1', '_2'))
        combined_all.insert(0, 'Periode', periode)

        out_xlsx = os.path.join(folder, f"combine_{datetime.now().strftime('%H%M%S')}.xlsx")
        out_txt = os.path.join(folder, f"combine_{periode}.txt")
        try:
            combined_all.to_excel(out_xlsx, index=False)
            print(f"[FILE OK] Disimpan ke Excel: {os.path.basename(out_xlsx)}")
        except Exception:
            pass

        # Upsert to SQL
        print(f"[STEP 2.3] Mengupload {len(combined_all):,} baris ke tabel ZSMR007B...")
        sql_ok = process_reports.upload_to_sql(combined_all, periode, db_config)
        return sql_ok
    else:
        print("[ERROR] File *1.txt atau *2.txt tidak ditemukan di folder ZSMR007.")
        return False


def run_stage_3_ke30_div_etl(periode: str, paths: dict, vbs_dir: str, db_config: dict) -> bool:
    """Tahap 3: Download KE30 per Divisi -> Excel COM mapping -> upsert ke SQL."""
    print("\n" + "─" * 70)
    print(" ▶ [TAHAP 3/6] DOWNLOAD & UPSERT KE30 BY DIVISI KE SQL SERVER")
    print("─" * 70)
    folder = paths["ke30_div_dir"]
    os.makedirs(folder, exist_ok=True)
    vbs_path = os.path.join(vbs_dir, "KE30 Get CMNWDN by Div.vbs")

    dt = datetime.strptime(periode, "%Y-%m-%d")
    year_str = dt.strftime("%Y")
    month_str = dt.strftime("%m")
    save_path_arg = folder.rstrip("\\") + "\\"

    print(f"[STEP 3.1] Menjalankan VBScript download KE30 Divisi ({year_str}/{month_str})...")
    vbs_ok = run_vbs(vbs_path, [year_str, month_str, save_path_arg])
    if not vbs_ok:
        print("[WARN] Eksekusi VBS download KE30 divisi menemui kendala. Mengecek file .dat...")

    # Jalankan Excel COM Parser & SQL Upsert
    print(f"[STEP 3.2] Menjalankan Excel COM Parser untuk seluruh file .dat di {folder}...")
    try:
        ProsesKE30byDiv.process_ke30(folder, periode, insert_sql=True, db_config=db_config)
        return True
    except Exception as e:
        print(f"[ERROR] Gagal memproses KE30 Divisi: {e}")
        return False


def run_stage_4_ke30_eq_etl(periode: str, paths: dict, vbs_dir: str, db_config: dict) -> bool:
    """Tahap 4: Download KE30 per Equipment -> parse Eq -> upsert ke SQL."""
    print("\n" + "─" * 70)
    print(" ▶ [TAHAP 4/6] DOWNLOAD & UPSERT KE30 BY EQUIPMENT KE SQL SERVER")
    print("─" * 70)
    folder = paths["ke30_eq_dir"]
    os.makedirs(folder, exist_ok=True)
    vbs_path = os.path.join(vbs_dir, "KE30 Get CMNWDN by Eq.vbs")

    dt = datetime.strptime(periode, "%Y-%m-%d")
    period_tag = dt.strftime("%m%y")
    save_path_arg = folder.rstrip("\\") + "\\"

    print(f"[STEP 4.1] Menjalankan VBScript download KE30 Equipment (Tag: {period_tag})...")
    vbs_ok = run_vbs(vbs_path, [period_tag, save_path_arg])
    if not vbs_ok:
        print("[WARN] Eksekusi VBS download KE30 Equipment menemui kendala. Mengecek file .dat...")

    # Cari file .dat equipment di folder
    print(f"[STEP 4.2] Memproses file .dat KE30 Equipment di {folder}...")
    try:
        ProcessKE30byEq.process_ke30_eq(folder, periode, insert_sql=True, db_config=db_config)
        return True
    except Exception as e:
        print(f"[ERROR] Gagal memproses KE30 Equipment: {e}")
        return False


def run_stage_5_zsme09e_etl(periode: str, paths: dict, vbs_dir: str, db_config: dict) -> bool:
    """Tahap 5: Download ZSME09E Material Movement -> upsert ke SQL."""
    print("\n" + "─" * 70)
    print(" ▶ [TAHAP 5/6] DOWNLOAD & UPSERT ZSME09E (MATERIAL MOVEMENT) KE SQL SERVER")
    print("─" * 70)
    folder = paths["zsme09e_dir"]
    os.makedirs(folder, exist_ok=True)
    vbs_path = os.path.join(vbs_dir, "DownloadZSME09E.vbs")

    download_filename = automate_zsme09e.build_period_filename("ZSME09E_Data", periode, "txt")
    file_full_path = os.path.abspath(os.path.join(folder, download_filename))

    # Ambil tanggal DB
    try:
        start_date, end_date = automate_zsme09e.get_periode_dates(periode, db_config)
    except Exception:
        start_date, end_date = None, None

    if not start_date or not end_date:
        dt = datetime.strptime(periode, "%Y-%m-%d")
        start_date = dt.replace(day=1)
        end_date = dt

    from_date_sap = start_date.strftime("%d%m%y")
    to_date_sap = end_date.strftime("%d%m%y")

    automate_zsme09e.backup_existing_file(file_full_path)

    print(f"[STEP 5.1] Menjalankan VBScript ZSME09E ({from_date_sap} s/d {to_date_sap})...")
    vbs_ok = run_vbs(vbs_path, [from_date_sap, to_date_sap, folder, download_filename])
    if not vbs_ok:
        print("[ERROR] Eksekusi VBScript ZSME09E gagal.")
        return False

    if not os.path.exists(file_full_path) or os.path.getsize(file_full_path) == 0:
        print(f"[ERROR] File hasil download ZSME09E tidak valid: {file_full_path}")
        return False

    print(f"[STEP 5.2] Mengupload file {download_filename} ke tabel ZSME09E...")
    return automate_zsme09e.upload_to_sql(file_full_path, periode, db_config)


def run_stage_6_zsmr019_etl(periode: str, paths: dict, vbs_dir: str, db_config: dict) -> bool:
    """Tahap 6: Download ZSMR019 Service Order -> upsert ke SQL."""
    print("\n" + "─" * 70)
    print(" ▶ [TAHAP 6/6] DOWNLOAD & UPSERT ZSMR019 (SERVICE ORDER) KE SQL SERVER")
    print("─" * 70)
    folder = paths["zsmr019_dir"]
    os.makedirs(folder, exist_ok=True)
    vbs_path = os.path.join(vbs_dir, "ZSMR019.vbs")
    file_name = paths["zsmr019_filename"]

    ret = download_zsmr019.main(
        periode=periode,
        vbs_path=vbs_path,
        save_path=folder,
        file_name=file_name,
        insert_sql=True,
        db_config=db_config,
    )
    return ret == 0


def fetch_database_audit(periode: str, db_config: dict) -> dict[str, int]:
    """Mengambil jumlah row saat ini di database SQL Server untuk audit kelengkapan data."""
    counts = {}
    tables = ["ZSMR007B", "KE30", "KE30_ByEq", "ZSME09E", "ZSMR019"]
    try:
        conn = get_connection_with_retry(db_config)
        cursor = conn.cursor()
        for tbl in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {tbl} WHERE Periode = ?", (periode,))
                counts[tbl] = cursor.fetchone()[0]
            except Exception:
                counts[tbl] = -1
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[AUDIT WARN] Gagal mengambil row count audit: {e}")
    return counts


def main(
    periode: str | None = None,
    base_drive: str = "D:\\Kerja",
    stages: str = "1,2,3,4,5,6",
    batch_size: int = 1000,
    vbs_dir: str = "vbs",
    dry_run: bool = False,
    db_config: dict | None = None,
) -> int:
    effective_db = db_config or {
        "server": DB_CONFIG["server"],
        "user": DB_CONFIG["user"],
        "pwd": DB_CONFIG["pwd"],
        "name": DB_CONFIG["name"],
        "driver": DB_CONFIG["driver"],
    }

    # 1. Resolve Periode
    if not periode or periode.strip() == "" or periode == "dynamic-today-ymd":
        db_p, _, _ = get_active_closing_period(effective_db)
        target_periode = db_p
    else:
        target_periode = periode.strip()

    # 2. Resolve Workspace Paths berdasarkan struktur baku Astragraphia
    paths = resolve_workspace_paths(target_periode, base_drive=base_drive)
    ensure_workspace_directories(paths)

    # 3. Parse stages
    stages_to_run = []
    for s in stages.split(","):
        s_clean = s.strip()
        if s_clean.isdigit():
            stages_to_run.append(int(s_clean))
    if not stages_to_run:
        stages_to_run = [1, 2, 3, 4, 5, 6]

    # 4. Print Pre-Flight Inspection
    print_preflight_inspection(target_periode, paths, stages_to_run, effective_db)

    if dry_run:
        print("\n[DRY RUN] Mode inspeksi aktif. Validasi variabel selesai tanpa eksekusi SAP.")
        return 0

    # 5. Pre-flight Check: Database Connectivity & SAP GUI Login
    print("\n[PRE-FLIGHT] Memeriksa konektivitas Database Server...")
    try:
        conn = get_connection_with_retry(effective_db, retries=2, delay=1)
        conn.close()
        print("[PRE-FLIGHT OK] Database SQL Server terhubung.")
    except Exception as db_err:
        print(f"[PRE-FLIGHT ALERT] Gagal terhubung ke database server {effective_db.get('server')}: {db_err}")
        print("[HINT] Pastikan laptop Anda telah terhubung ke jaringan kantor (LAN) atau VPN Astragraphia.")
        return 1

    vbs_login = os.path.join(vbs_dir, "LoginSAP.vbs")
    print("[PRE-FLIGHT] Memeriksa status login SAP GUI...")
    if not ensure_sap_logged_in(vbs_login):
        print("[CRITICAL] SAP GUI belum siap / login gagal. Otomatisasi dibatalkan.")
        print("[HINT] Pastikan SAP Logon sudah dibuka dan user/password di .env sudah benar.")
        return 1

    start_total_time = time.time()
    results = {}

    # 6. Eksekusi Tahap demi Tahap
    if 1 in stages_to_run:
        t0 = time.time()
        ok = run_stage_1_zsmr007b_bg(target_periode, batch_size, vbs_dir, effective_db)
        results[1] = {"name": "Create BG Job ZSMR007B", "ok": ok, "time": time.time() - t0}

    if 2 in stages_to_run:
        t0 = time.time()
        ok = run_stage_2_zsmr007b_etl(target_periode, paths, vbs_dir, effective_db)
        results[2] = {"name": "Download & Upsert ZSMR007B", "ok": ok, "time": time.time() - t0}

    if 3 in stages_to_run:
        t0 = time.time()
        ok = run_stage_3_ke30_div_etl(target_periode, paths, vbs_dir, effective_db)
        results[3] = {"name": "Download & Upsert KE30 Divisi", "ok": ok, "time": time.time() - t0}

    if 4 in stages_to_run:
        t0 = time.time()
        ok = run_stage_4_ke30_eq_etl(target_periode, paths, vbs_dir, effective_db)
        results[4] = {"name": "Download & Upsert KE30 Equipment", "ok": ok, "time": time.time() - t0}

    if 5 in stages_to_run:
        t0 = time.time()
        ok = run_stage_5_zsme09e_etl(target_periode, paths, vbs_dir, effective_db)
        results[5] = {"name": "Download & Upsert ZSME09E", "ok": ok, "time": time.time() - t0}

    if 6 in stages_to_run:
        t0 = time.time()
        ok = run_stage_6_zsmr019_etl(target_periode, paths, vbs_dir, effective_db)
        results[6] = {"name": "Download & Upsert ZSMR019", "ok": ok, "time": time.time() - t0}

    total_duration = time.time() - start_total_time

    # 7. Audit Ringkasan Akhir
    audit_counts = fetch_database_audit(target_periode, effective_db)

    print("\n" + "=" * 80)
    print(f" [SUMMARY] RINGKASAN AKHIR EKSEKUSI PIPELINE HARIAN (Periode: {target_periode})")
    print("=" * 80)
    all_success = True
    for stage_num, res in results.items():
        status_badge = "[OK] SUKSES" if res["ok"] else "[ERROR] GAGAL"
        if not res["ok"]:
            all_success = False
        print(f" [Tahap {stage_num}] {res['name']:<35} : {status_badge} ({res['time']:.1f}s)")

    print("-" * 80)
    print(" [DATABASE AUDIT] STATUS JUMLAH BARIS DI DATABASE SQL SERVER:")
    for tbl, cnt in audit_counts.items():
        cnt_str = f"{cnt:,} baris" if cnt >= 0 else "Error/N/A"
        print(f"   * Tabel [{tbl:<12}] : {cnt_str}")
    print("-" * 80)
    print(f" Total Waktu Eksekusi: {total_duration:.1f} detik ({total_duration/60:.2f} menit)")
    print("=" * 80)

    return 0 if all_success else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Master Daily E2E Automation Pipeline (6 Stages)")
    parser.add_argument("--periode", default=None, help="Target periode YYYY-MM-DD (Default: dari database)")
    parser.add_argument("--base-drive", default="D:\\Kerja", help="Base drive folder kerja (Default: D:\\Kerja)")
    parser.add_argument("--stages", default="1,2,3,4,5,6", help="Tahapan yang dijalankan (contoh: 1,2,3,4,5,6)")
    parser.add_argument("--batch-size", type=int, default=1000, help="Jumlah equipment per batch (default 1.000)")
    parser.add_argument("--vbs-dir", default="vbs", help="Folder lokasi script VBScript")
    parser.add_argument("--dry-run", action="store_true", help="Inspeksi variabel pre-flight tanpa eksekusi SAP")

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
            "driver": DB_CONFIG.get("driver", "ODBC Driver 17 for SQL Server"),
        }

    ret = main(
        periode=args.periode,
        base_drive=args.base_drive,
        stages=args.stages,
        batch_size=args.batch_size,
        vbs_dir=args.vbs_dir,
        dry_run=args.dry_run,
        db_config=db_cfg,
    )
    sys.exit(ret)
