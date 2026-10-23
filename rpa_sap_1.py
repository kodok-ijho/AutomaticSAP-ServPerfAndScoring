"""rpa_sap_1.py — Pembuatan Background Job ZSMR007B per Batch Equipment.

Mengambil data EQUIPMENT dari tabel Tb_R_SerPervEq, menyalin ke Clipboard
per-batch (default 1.000 equipment), lalu menjadwalkan eksekusi SAP via VBScript.
"""

import pyperclip
import subprocess
import time
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


def main(
    periode: str,
    max_offset: int,
    batch_size: int,
    delay_seconds: int,
    vbs_path: str,
    sched_start_time: str,
    db_config: dict | None = None,
) -> int:
    print("=" * 60)
    print(f"[CONFIG] Job          : CREATE BG JOB ZSMR007B (Equipment Batch)")
    print(f"[CONFIG] Periode      : {periode}")
    print(f"[CONFIG] Max Offset   : {max_offset if max_offset > 0 else 'Auto (Seluruh Data)'}")
    print(f"[CONFIG] Batch Size   : {batch_size}")
    print(f"[CONFIG] Delay (detik): {delay_seconds}")
    print(f"[CONFIG] VBS Path     : {vbs_path}")
    print(f"[CONFIG] Sched Start  : {sched_start_time}")
    print("=" * 60)

    conn = None
    cursor = None
    try:
        print("[DB] Menghubungkan ke database...")
        conn = get_connection_with_retry(db_config)
        cursor = conn.cursor()
        print("[DB OK] Berhasil terhubung ke database.")

        # 1. Resolusi Periode Cerdas (Exact -> Month Start -> Closing Range -> Latest)
        effective_periode = periode
        cursor.execute("SELECT COUNT(*) FROM Tb_R_SerPervEq WHERE Periode = ?", (effective_periode,))
        total_equipments = cursor.fetchone()[0]

        if total_equipments == 0 and len(str(periode)) == 10:
            month_start = str(periode)[:8] + "01"
            cursor.execute("SELECT COUNT(*) FROM Tb_R_SerPervEq WHERE Periode = ?", (month_start,))
            c = cursor.fetchone()[0]
            if c > 0:
                effective_periode = month_start
                total_equipments = c
                print(f"[RESOLVE] Menggunakan periode bulan {effective_periode} ({total_equipments:,} equipment).")

        if total_equipments == 0:
            cursor.execute("SELECT Periode FROM Tb_R_PeriodeClosing WHERE ? BETWEEN StartDate AND EndDate", (periode,))
            row = cursor.fetchone()
            if row and row[0]:
                closing_p = str(row[0]).split()[0]
                cursor.execute("SELECT COUNT(*) FROM Tb_R_SerPervEq WHERE Periode = ?", (closing_p,))
                c = cursor.fetchone()[0]
                if c > 0:
                    effective_periode = closing_p
                    total_equipments = c
                    print(f"[RESOLVE] Menggunakan periode closing aktif {effective_periode} ({total_equipments:,} equipment).")

        if total_equipments == 0:
            print(f"[WARN] Tidak ada data equipment untuk periode {periode}. Proses batch dihentikan.")
            return 0

        # Ambil StartDate dan EndDate dari Tb_R_PeriodeClosing
        print(f"[DB] Mengambil rentang tanggal untuk periode: {effective_periode}...")
        query_dates = "SELECT StartDate, EndDate FROM Tb_R_PeriodeClosing WHERE Periode = ?"
        cursor.execute(query_dates, (effective_periode,))
        date_row = cursor.fetchone()

        if not date_row or not date_row[0] or not date_row[1]:
            print(f"[WARN] Tidak ada rentang tanggal di Tb_R_PeriodeClosing untuk periode {effective_periode}. Menggunakan fallback.")
            dt_p = datetime.strptime(effective_periode, "%Y-%m-%d")
            start_date_str = dt_p.replace(day=1).strftime("%d%m%y")
            end_date_str = (dt_p.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            end_date_str = end_date_str.strftime("%d%m%y")
        else:
            s_dt = date_row[0] if isinstance(date_row[0], datetime) else datetime.strptime(str(date_row[0]).split()[0], "%Y-%m-%d")
            e_dt = date_row[1] if isinstance(date_row[1], datetime) else datetime.strptime(str(date_row[1]).split()[0], "%Y-%m-%d")
            start_date_str = s_dt.strftime("%d%m%y")
            end_date_str = e_dt.strftime("%d%m%y")

        print(f"[CLOSING DATES] Rentang Tanggal: {start_date_str} s/d {end_date_str}")
        print(f"[DB INFO] Total peralatan di Tb_R_SerPervEq periode {effective_periode}: {total_equipments:,} baris.")

        effective_max = total_equipments if (max_offset <= 0 or max_offset > total_equipments) else max_offset

    except Exception as e:
        print(f"[DB ERROR] Gagal mengakses database: {e}")
        return 1

    # Parse jam mulai schedule (format HH:MM atau HH:MM:SS)
    try:
        parts = sched_start_time.split(":")
        sched_h = int(parts[0])
        sched_m = int(parts[1])
    except Exception:
        print(f"[CONFIG] Peringatan: Format sched-start-time tidak valid ('{sched_start_time}'). Menggunakan 17:00.")
        sched_h, sched_m = 17, 0

    offset_counter = 0
    call_counter = 0
    resolved_vbs = os.path.abspath(os.path.expandvars(vbs_path))

    if not os.path.exists(resolved_vbs):
        print(f"[ERROR] File VBS tidak ditemukan di {resolved_vbs}")
        return 1

    try:
        while offset_counter < effective_max:
            print(f"\n--- [BATCH {call_counter + 1}] Memproses offset {offset_counter:,} s/d {min(offset_counter + batch_size, effective_max):,} ---")
            query = """
                SELECT EQUIPMENT
                FROM Tb_R_SerPervEq
                WHERE Periode = ?
                ORDER BY Equipment
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """
            cursor.execute(query, (effective_periode, offset_counter, batch_size))
            rows = cursor.fetchall()

            if not rows:
                print(f"[INFO] Tidak ada data tersisa pada offset {offset_counter}. Selesai.")
                break

            equipments = [str(row[0]).strip() for row in rows if row[0]]
            data_eq_copy = "\r\n".join(equipments)
            pyperclip.copy(data_eq_copy)
            print(f"[CLIPBOARD] {len(equipments):,} peralatan berhasil disalin ke clipboard.")

            # Hitung tanggal & jam schedule secara dinamis
            sched_date_str = datetime.now().strftime("%d%m%y")
            base_time = datetime.now().replace(hour=sched_h, minute=sched_m, second=0, microsecond=0)
            time1 = base_time + timedelta(minutes=call_counter * 2)
            time2 = base_time + timedelta(minutes=call_counter * 2 + 1)
            sched_time1 = time1.strftime("%H%M%S")
            sched_time2 = time2.strftime("%H%M%S")

            print(f"[EXEC] Menjalankan VBScript: {resolved_vbs}")
            print(f"       Schedule Date: {sched_date_str} | Batch1: {sched_time1} | Batch2: {sched_time2}")
            
            vbs_ok = run_vbs(resolved_vbs, [start_date_str, end_date_str, sched_date_str, sched_time1, sched_time2])
            if not vbs_ok:
                print(f"[WARN] Batch {call_counter + 1} menemui kendala saat eksekusi VBScript.")
            call_counter += 1
            offset_counter += batch_size

            if offset_counter < effective_max:
                print(f"[WAIT] Menunggu selama {delay_seconds} detik sebelum batch berikutnya...")
                time.sleep(delay_seconds)

        print(f"\n[SUCCESS] Berhasil menjadwalkan {call_counter} batch background job di SAP ({effective_max:,} total peralatan).")
        return 0

    except Exception as e:
        print(f"[ERROR] Terjadi kesalahan saat eksekusi batch: {e}")
        return 1

    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RPA SAP 1 - Equipment Batch Clipboard Scheduler")
    parser.add_argument("--periode", default=datetime.now().strftime("%Y-%m-01"),
                        help="Periode data yang diambil (format YYYY-MM-DD)")
    parser.add_argument("--max-offset", type=int, default=0,
                        help="Batas maksimum offset (0 = otomatis seluruh data di database)")
    parser.add_argument("--batch-size", type=int, default=1000,
                        help="Jumlah baris per batch yang diambil dari DB (default 1.000)")
    parser.add_argument("--delay", type=int, default=10,
                        help="Delay antar iterasi batch (detik)")
    parser.add_argument("--vbs-path", default="vbs\\CreateBG007B-Scheduled.vbs",
                        help="Path ke file VBS SAP GUI")
    parser.add_argument("--sched-start-time", default="17:00",
                        help="Jam mulai jadwal SAP BG Job (format HH:MM, contoh: 17:00)")

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

    ret = main(
        periode=args.periode,
        max_offset=args.max_offset,
        batch_size=args.batch_size,
        delay_seconds=args.delay,
        vbs_path=args.vbs_path,
        sched_start_time=args.sched_start_time,
        db_config=db_cfg,
    )
    sys.exit(ret)
