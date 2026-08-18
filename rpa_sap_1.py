import pyperclip
import subprocess
import time
import os
import argparse
from datetime import datetime, timedelta

from db import get_connection

def main(periode: str, max_offset: int, batch_size: int, delay_seconds: int, vbs_path: str, sched_start_time: str):
    print(f"[CONFIG] Periode      : {periode}")
    print(f"[CONFIG] Max Offset   : {max_offset}")
    print(f"[CONFIG] Batch Size   : {batch_size}")
    print(f"[CONFIG] Delay (detik): {delay_seconds}")
    print(f"[CONFIG] VBS Path     : {vbs_path}")
    print("-" * 50)

    try:
        print("Menghubungkan ke database...")
        conn = get_connection()
        cursor = conn.cursor()
        print("Berhasil terhubung ke database.")

        # 1. Ambil StartDate dan EndDate dari Tb_R_PeriodeClosing
        print(f"Mengambil rentang tanggal untuk periode: {periode}...")
        query_dates = "SELECT StartDate, EndDate FROM Tb_R_PeriodeClosing WHERE Periode = ?"
        cursor.execute(query_dates, (periode,))
        date_row = cursor.fetchone()

        if not date_row:
            print(f"Peringatan: Tidak ada data rentang tanggal untuk periode {periode}.")
            return

        # Format tanggal ke DDMMYY (contoh: 301225)
        start_date_str = date_row[0].strftime("%d%m%y")
        end_date_str = date_row[1].strftime("%d%m%y")
        print(f"Rentang Tanggal ditemukan: {start_date_str} s/d {end_date_str}")

    except Exception as e:
        print(f"Gagal menghubungkan ke database atau mengambil tanggal: {e}")
        return

    # Parse jam mulai schedule (format HH:MM atau HH:MM:SS)
    try:
        parts = sched_start_time.split(":")
        sched_h = int(parts[0])
        sched_m = int(parts[1])
    except Exception:
        print(f"[CONFIG] Peringatan: Format sched-start-time tidak valid ('{sched_start_time}'). Menggunakan 18:00.")
        sched_h, sched_m = 18, 0

    offset_counter = 0
    call_counter   = 0  # Menghitung berapa kali VBS dipanggil

    while offset_counter < max_offset:
        try:
            print(f"--- Memproses offset: {offset_counter} ---")
            query = """
                SELECT EQUIPMENT
                FROM Tb_R_SerPervEq
                WHERE Periode = ?
                ORDER BY Equipment
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """
            cursor.execute(query, (periode, offset_counter, batch_size))
            rows = cursor.fetchall()

            if not rows:
                print(f"Tidak ada data ditemukan untuk offset {offset_counter}. Menghentikan proses.")
                break

            equipments = [str(row[0]) for row in rows]
            data_eq_copy = "\r\n".join(equipments)
            pyperclip.copy(data_eq_copy)
            print(f"{len(equipments)} peralatan berhasil disalin ke clipboard.")

            resolved_vbs = os.path.expandvars(vbs_path)
            if os.path.exists(resolved_vbs):
                # Hitung tanggal & jam schedule secara dinamis
                sched_date_str = datetime.now().strftime("%d%m%y")  # format DDMMYY
                base_time  = datetime.now().replace(hour=sched_h, minute=sched_m, second=0, microsecond=0)
                time1 = base_time + timedelta(minutes=call_counter * 2)
                time2 = base_time + timedelta(minutes=call_counter * 2 + 1)
                sched_time1 = time1.strftime("%H%M%S")
                sched_time2 = time2.strftime("%H%M%S")

                print(f"Menjalankan skrip VBS: {resolved_vbs}")
                print(f"  Schedule: {sched_date_str} | Batch1={sched_time1} | Batch2={sched_time2}")
                subprocess.run(
                    ["wscript.exe", resolved_vbs, start_date_str, end_date_str, sched_date_str, sched_time1, sched_time2],
                    check=True
                )
                call_counter += 1
            else:
                print(f"Peringatan: File VBS tidak ditemukan di {resolved_vbs}")

            print(f"Menunggu selama {delay_seconds} detik...\n")
            time.sleep(delay_seconds)

        except Exception as e:
            print(f"Terjadi kesalahan di dalam perulangan: {e}")
            break

        offset_counter += batch_size

    cursor.close()
    conn.close()
    print("Proses selesai.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RPA SAP 1 - Equipment Batch Clipboard")
    parser.add_argument("--periode",       default="2026-01-01",
                        help="Periode data yang diambil (format YYYY-MM-DD)")
    parser.add_argument("--max-offset",    type=int, default=1000,
                        help="Batas maksimum offset perulangan")
    parser.add_argument("--batch-size",    type=int, default=500,
                        help="Jumlah baris per batch yang diambil dari DB")
    parser.add_argument("--delay",         type=int, default=10,
                        help="Delay antar iterasi (detik)")
    parser.add_argument("--vbs-path",
                        default="vbs\\CreateBG007B-Scheduled.vbs",
                        help="Path ke file VBS SAP GUI")
    parser.add_argument("--sched-start-time",
                        default="18:00",
                        help="Jam mulai jadwal SAP BG Job (format HH:MM, contoh: 18:00)")
    args = parser.parse_args()

    main(
        periode=args.periode,
        max_offset=args.max_offset,
        batch_size=args.batch_size,
        delay_seconds=args.delay,
        vbs_path=args.vbs_path,
        sched_start_time=args.sched_start_time,
    )
