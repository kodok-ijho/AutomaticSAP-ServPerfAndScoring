"""test_smoke.py — Smoke Test Dasar untuk SAP Automation.

Menguji fungsi-fungsi utilitas utama tanpa memerlukan koneksi database atau SAP GUI aktif:
  - Definisi job dan build CLI args (`job_definitions.py`)
  - Resolusi path dinamis workspace Astragraphia (`path_resolver.py`)
  - Parsing angka format SAP (`db_utils.py`)
  - Klasifikasi log tag (`job_runner.py`)
  - Validasi konfigurasi (`job_definitions.py`)

Jalankan dengan: python test_smoke.py
"""

import os
import sys
import unittest
from job_definitions import SCRIPTS, build_cli_args, validate_job_config
from db_utils import clean_sap_number, parse_sap_int, is_sap_numeric, format_sap_number_display
from job_runner import classify_log_tag, STATUS_IDLE, STATUS_RUNNING, STATUS_SUCCESS, STATUS_FAILED
from path_resolver import (
    resolve_workspace_paths,
    parse_period_date,
    get_smart_spool_date_range,
    get_cascading_spool_date_ranges,
)
from datetime import datetime


class TestJobDefinitions(unittest.TestCase):
    """Pengujian untuk definisi job dan argumen CLI."""

    def test_scripts_not_empty(self):
        """Pastikan SCRIPTS terdefinisi dan tidak kosong."""
        self.assertGreater(len(SCRIPTS), 0, "Daftar SCRIPTS tidak boleh kosong")

    def test_daily_pipeline_job_registered(self):
        """Pastikan job DAILY AUTOMATION PIPELINE terdaftar di SCRIPTS."""
        self.assertIn("DAILY AUTOMATION PIPELINE – Full 6 Stages", SCRIPTS)

    def test_build_cli_args_for_all_jobs(self):
        """Pastikan build_cli_args dapat menghasilkan list argumen tanpa error untuk semua job."""
        dummy_db = {"server": "localhost", "user": "sa", "pwd": "123", "name": "DB"}
        for name, info in SCRIPTS.items():
            params = {p["arg"]: p["default"] for p in info["params"]}
            args = build_cli_args(name, params, db_config=dummy_db)
            self.assertIsInstance(args, list, f"Result build_cli_args untuk '{name}' harus berupa list")


class TestPathResolver(unittest.TestCase):
    """Pengujian modul resolusi path dinamis Astragraphia."""

    def test_resolve_paths_june_2026(self):
        paths = resolve_workspace_paths("2026-06-01", base_drive="D:\\Kerja")
        self.assertIn("2026 CSSD", paths["cssd_root"])
        self.assertIn("06 JUN 2026 REPORTING", paths["reporting_ss"])
        self.assertIn("ZSMR007", paths["zsmr007b_dir"])
        self.assertIn("ZSME09E", paths["zsme09e_dir"])
        self.assertIn("KE30 - 06 JUN 26", paths["ke30_root"])
        self.assertIn("AUTO", paths["ke30_div_dir"])

    def test_resolve_paths_august_2026(self):
        paths = resolve_workspace_paths("2026-08-01", base_drive="D:\\Kerja")
        self.assertIn("08 AUG 2026 REPORTING", paths["reporting_ss"])
        self.assertIn("KE30 - 08 AUG 26", paths["ke30_root"])
        self.assertTrue(paths["zsmr019_filename"].startswith("ZSMR019 - 0826 - "))

    def test_parse_period_date(self):
        dt = parse_period_date("2026-04-01")
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 4)

    def test_smart_spool_lookback_monday(self):
        # 2026-08-24 adalah hari Senin (weekday 0)
        monday_dt = datetime(2026, 8, 24)
        from_str, to_str = get_smart_spool_date_range(monday_dt)
        self.assertEqual(from_str, "21.08.2026", "Hari Senin harus mundur 3 hari ke hari Jumat (21.08.2026)")
        self.assertEqual(to_str, "24.08.2026")

    def test_smart_spool_lookback_tuesday(self):
        # 2026-08-25 adalah hari Selasa (weekday 1)
        tuesday_dt = datetime(2026, 8, 25)
        from_str, to_str = get_smart_spool_date_range(tuesday_dt)
        self.assertEqual(from_str, "24.08.2026", "Hari Selasa harus mundur 1 hari ke hari Senin (24.08.2026)")
        self.assertEqual(to_str, "25.08.2026")

    def test_cascading_spool_lookback_monday(self):
        # 2026-08-24 adalah hari Senin
        monday_dt = datetime(2026, 8, 24)
        ranges = get_cascading_spool_date_ranges(monday_dt)
        self.assertEqual(len(ranges), 3)
        # Tier 1 (H-3 Jumat)
        self.assertEqual(ranges[0][1], "21.08.2026")
        self.assertEqual(ranges[0][2], "24.08.2026")
        # Tier 2 (H-5)
        self.assertEqual(ranges[1][1], "19.08.2026")
        self.assertEqual(ranges[1][2], "24.08.2026")
        # Tier 3 (H-7)
        self.assertEqual(ranges[2][1], "17.08.2026")
        self.assertEqual(ranges[2][2], "24.08.2026")

    def test_cascading_spool_lookback_weekday(self):
        # 2026-08-26 adalah hari Rabu
        wednesday_dt = datetime(2026, 8, 26)
        ranges = get_cascading_spool_date_ranges(wednesday_dt)
        self.assertEqual(len(ranges), 3)
        # Tier 1 (H-1 Selasa)
        self.assertEqual(ranges[0][1], "25.08.2026")
        self.assertEqual(ranges[0][2], "26.08.2026")


class TestSAPNumberParsing(unittest.TestCase):
    """Pengujian fungsi-fungsi normalisasi angka SAP di db_utils."""

    def test_clean_sap_number_decimal_comma(self):
        """Format 1.234,56 -> 1234.56"""
        self.assertEqual(clean_sap_number("1.234,56"), 1234.56)

    def test_clean_sap_number_trailing_minus(self):
        """Format 322.361- -> -322361.0"""
        self.assertEqual(clean_sap_number("322.361-"), -322361.0)

    def test_clean_sap_number_leading_minus(self):
        """Format -1.500 -> -1500.0"""
        self.assertEqual(clean_sap_number("-1.500"), -1500.0)

    def test_clean_sap_number_empty_or_none(self):
        """Handling None dan string kosong"""
        self.assertIsNone(clean_sap_number(None))
        self.assertIsNone(clean_sap_number(""))
        self.assertIsNone(clean_sap_number("   "))

    def test_parse_sap_int(self):
        """Format ribuan SAP dibulatkan ke int"""
        self.assertEqual(parse_sap_int("1.234,6"), 1235)
        self.assertEqual(parse_sap_int("500-"), -500)

    def test_is_sap_numeric(self):
        """Cek boolean validasi angka SAP"""
        self.assertTrue(is_sap_numeric("1.234,56"))
        self.assertTrue(is_sap_numeric("100-"))
        self.assertFalse(is_sap_numeric("abc"))
        self.assertFalse(is_sap_numeric(None))

    def test_format_sap_number_display(self):
        """Display string bersih"""
        self.assertEqual(format_sap_number_display("1.234,00"), "1234")
        self.assertEqual(format_sap_number_display(""), "")


class TestJobRunnerLogClassifier(unittest.TestCase):
    """Pengujian klasifikasi tag log dan konstanta di job_runner."""

    def test_classify_log_tag_error(self):
        self.assertEqual(classify_log_tag("[ERROR] Gagal koneksi"), "ERROR")
        self.assertEqual(classify_log_tag("Proses Gagal dikarenakan..."), "ERROR")

    def test_classify_log_tag_ok(self):
        self.assertEqual(classify_log_tag("Upload Berhasil!"), "OK")
        self.assertEqual(classify_log_tag("Proses Selesai."), "OK")

    def test_classify_log_tag_warn(self):
        self.assertEqual(classify_log_tag("[WARN] Data 0 baris"), "WARN")

    def test_classify_log_tag_info(self):
        self.assertEqual(classify_log_tag("Membaca file..."), "INFO")

    def test_status_constants(self):
        self.assertEqual(STATUS_IDLE, "idle")
        self.assertEqual(STATUS_RUNNING, "running")
        self.assertEqual(STATUS_SUCCESS, "success")
        self.assertEqual(STATUS_FAILED, "failed")


class TestKE30Scoring(unittest.TestCase):
    """Pengujian modul Scoring KE30 dan pemetaan MPG."""

    def test_resolve_scoring_paths_june(self):
        from path_resolver import resolve_scoring_paths
        p = resolve_scoring_paths("2026-06-01", base_drive="D:\\Kerja")
        self.assertEqual(p["month_int"], 6)
        self.assertEqual(p["mmm_en"], "JUN")
        self.assertEqual(p["next_full_id"], "JULI")
        self.assertIn("KE30 YTDN Scoring JUN 26.xlsx", p["scoring_master_file"])

    def test_mpg_mapping_completeness(self):
        from process_ke30_scoring import MPG_MAPPING
        # Harus ada 22 MPG
        self.assertEqual(len(MPG_MAPPING), 22)
        # E1 dan I1 harus multi divisi
        self.assertEqual(MPG_MAPPING["E1"], ["22", "27"])
        self.assertEqual(MPG_MAPPING["I1"], ["25", "26"])
        # A1 harus divisi 83
        self.assertEqual(MPG_MAPPING["A1"], ["83"])


class TestZSMR012Scheduler(unittest.TestCase):
    """Pengujian modul penjadwalan background job ZSMR012 per N hari."""

    def test_zsmr012_job_registered(self):
        """Pastikan job ZSMR012 terdaftar di SCRIPTS."""
        self.assertIn("CREATE BG JOB ZSMR012 – Split N Hari Scheduler", SCRIPTS)

    def test_generate_date_chunks_31_days_5_chunk(self):
        from schedule_zsmr012 import generate_date_chunks
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31)
        chunks = generate_date_chunks(start, end, chunk_days=5)
        # 31 hari dibagi 5 = 6 batch (5 hari) + 1 batch (1 hari) = 7 batch
        self.assertEqual(len(chunks), 7)
        self.assertEqual(chunks[0], (datetime(2026, 1, 1), datetime(2026, 1, 5)))
        self.assertEqual(chunks[1], (datetime(2026, 1, 6), datetime(2026, 1, 10)))
        self.assertEqual(chunks[5], (datetime(2026, 1, 26), datetime(2026, 1, 30)))
        self.assertEqual(chunks[6], (datetime(2026, 1, 31), datetime(2026, 1, 31)))

    def test_generate_date_chunks_single_day(self):
        from schedule_zsmr012 import generate_date_chunks
        start = datetime(2026, 5, 10)
        end = datetime(2026, 5, 10)
        chunks = generate_date_chunks(start, end, chunk_days=5)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], (start, end))

    def test_generate_date_chunks_invalid_range(self):
        from schedule_zsmr012 import generate_date_chunks
        start = datetime(2026, 5, 15)
        end = datetime(2026, 5, 10)
        with self.assertRaises(ValueError):
            generate_date_chunks(start, end, chunk_days=5)

    def test_calculate_job_schedules_interval(self):
        from schedule_zsmr012 import calculate_job_schedules
        base_time = datetime(2026, 10, 2, 17, 0)
        schedules = calculate_job_schedules(base_time, num_jobs=4, interval_minutes=5)
        self.assertEqual(len(schedules), 4)
        self.assertEqual(schedules[0], datetime(2026, 10, 2, 17, 0))
        self.assertEqual(schedules[1], datetime(2026, 10, 2, 17, 5))
        self.assertEqual(schedules[2], datetime(2026, 10, 2, 17, 10))
        self.assertEqual(schedules[3], datetime(2026, 10, 2, 17, 15))

    def test_calculate_job_schedules_midnight_rollover(self):
        from schedule_zsmr012 import calculate_job_schedules
        base_time = datetime(2026, 10, 2, 23, 50)
        schedules = calculate_job_schedules(base_time, num_jobs=3, interval_minutes=10)
        self.assertEqual(schedules[0], datetime(2026, 10, 2, 23, 50))
        self.assertEqual(schedules[1], datetime(2026, 10, 3, 0, 0))
        self.assertEqual(schedules[2], datetime(2026, 10, 3, 0, 10))

    def test_format_sap_date(self):
        from schedule_zsmr012 import format_sap_date
        dt = datetime(2026, 1, 5)
        self.assertEqual(format_sap_date(dt, "ddMMyy"), "050126")
        self.assertEqual(format_sap_date(dt, "dd.MM.yyyy"), "05.01.2026")

    def test_download_zsmr012_job_registered(self):
        """Pastikan job DOWNLOAD BG JOB ZSMR012 terdaftar di SCRIPTS."""
        self.assertIn("DOWNLOAD BG JOB ZSMR012 – SAP Background Job", SCRIPTS)

    def test_resolve_default_yesterday(self):
        """Pastikan sentinel dynamic-yesterday ter-resolusi ke H-1."""
        from job_definitions import resolve_default
        from datetime import timedelta
        y_dmy = resolve_default("dynamic-yesterday-dmy")
        expected_dmy = (datetime.now() - timedelta(days=1)).strftime("%d.%m.%Y")
        self.assertEqual(y_dmy, expected_dmy)

        y_ymd = resolve_default("dynamic-yesterday-ymd")
        expected_ymd = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        self.assertEqual(y_ymd, expected_ymd)

    def test_download_zsmr012_resolve_dates(self):
        """Pastikan resolve_dates di download_zsmr012 menangani tanggal manual dan otomatis."""
        from download_zsmr012 import resolve_dates
        # Manual tanggal
        f, t = resolve_dates("01.10.2026", "02.10.2026")
        self.assertEqual(f, "01.10.2026")
        self.assertEqual(t, "02.10.2026")
        # Format YYYY-MM-DD
        f2, t2 = resolve_dates("2026-10-01", "2026-10-02")
        self.assertEqual(f2, "01.10.2026")
        self.assertEqual(t2, "02.10.2026")

    def test_path_resolver_has_zsmr012(self):
        """Pastikan resolve_workspace_paths menyertakan direktori ZSMR012."""
        paths = resolve_workspace_paths("2026-08-01", base_drive="D:\\Kerja")
        self.assertIn("zsmr012_dir", paths)
        self.assertTrue(paths["zsmr012_dir"].endswith("ZSMR012"))


class TestIW58Scheduler(unittest.TestCase):
    """Pengujian modul penjadwalan background job IW58 per N hari."""

    def test_iw58_job_registered(self):
        """Pastikan job IW58 terdaftar di SCRIPTS."""
        self.assertIn("CREATE BG JOB IW58 – Split N Hari Scheduler", SCRIPTS)

    def test_generate_date_chunks_iw58(self):
        from schedule_iw58 import generate_date_chunks
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 15)
        chunks = generate_date_chunks(start, end, chunk_days=5)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0], (datetime(2026, 1, 1), datetime(2026, 1, 5)))
        self.assertEqual(chunks[1], (datetime(2026, 1, 6), datetime(2026, 1, 10)))
        self.assertEqual(chunks[2], (datetime(2026, 1, 11), datetime(2026, 1, 15)))

    def test_calculate_job_schedules_iw58(self):
        from schedule_iw58 import calculate_job_schedules
        base_time = datetime(2026, 10, 2, 17, 45)
        schedules = calculate_job_schedules(base_time, num_jobs=3, interval_minutes=5)
        self.assertEqual(len(schedules), 3)
        self.assertEqual(schedules[0], datetime(2026, 10, 2, 17, 45))
        self.assertEqual(schedules[1], datetime(2026, 10, 2, 17, 50))
        self.assertEqual(schedules[2], datetime(2026, 10, 2, 17, 55))

    def test_download_iw58_job_registered(self):
        """Pastikan job DOWNLOAD BG JOB IW58 terdaftar di SCRIPTS."""
        self.assertIn("DOWNLOAD BG JOB IW58 – SAP Background Job", SCRIPTS)

    def test_download_iw58_resolve_dates(self):
        """Pastikan resolve_dates di download_iw58 menangani tanggal manual dan otomatis."""
        from download_iw58 import resolve_dates
        f, t = resolve_dates("01.10.2026", "02.10.2026")
        self.assertEqual(f, "01.10.2026")
        self.assertEqual(t, "02.10.2026")

    def test_path_resolver_has_iw58(self):
        """Pastikan resolve_workspace_paths menyertakan direktori IW58."""
        paths = resolve_workspace_paths("2026-08-01", base_drive="D:\\Kerja")
        self.assertIn("iw58_dir", paths)
        self.assertTrue(paths["iw58_dir"].endswith("IW58"))


class TestIW73Scheduler(unittest.TestCase):
    """Pengujian modul penjadwalan background job IW73 per N hari."""

    def test_iw73_job_registered(self):
        """Pastikan job IW73 terdaftar di SCRIPTS."""
        self.assertIn("CREATE BG JOB IW73 – Split N Hari Scheduler", SCRIPTS)

    def test_generate_date_chunks_iw73(self):
        from schedule_iw73 import generate_date_chunks
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 15)
        chunks = generate_date_chunks(start, end, chunk_days=5)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0], (datetime(2026, 1, 1), datetime(2026, 1, 5)))
        self.assertEqual(chunks[1], (datetime(2026, 1, 6), datetime(2026, 1, 10)))
        self.assertEqual(chunks[2], (datetime(2026, 1, 11), datetime(2026, 1, 15)))

    def test_calculate_job_schedules_iw73(self):
        from schedule_iw73 import calculate_job_schedules
        base_time = datetime(2026, 10, 2, 17, 45)
        schedules = calculate_job_schedules(base_time, num_jobs=3, interval_minutes=5)
        self.assertEqual(len(schedules), 3)
        self.assertEqual(schedules[0], datetime(2026, 10, 2, 17, 45))
        self.assertEqual(schedules[1], datetime(2026, 10, 2, 17, 50))
        self.assertEqual(schedules[2], datetime(2026, 10, 2, 17, 55))

    def test_download_iw73_job_registered(self):
        """Pastikan job DOWNLOAD BG JOB IW73 terdaftar di SCRIPTS."""
        self.assertIn("DOWNLOAD BG JOB IW73 – SAP Background Job", SCRIPTS)

    def test_download_iw73_resolve_dates(self):
        """Pastikan resolve_dates di download_iw73 menangani tanggal manual dan otomatis."""
        from download_iw73 import resolve_dates
        f, t = resolve_dates("01.10.2026", "02.10.2026")
        self.assertEqual(f, "01.10.2026")
        self.assertEqual(t, "02.10.2026")

    def test_path_resolver_has_iw73(self):
        """Pastikan resolve_workspace_paths menyertakan direktori IW73."""
        paths = resolve_workspace_paths("2026-08-01", base_drive="D:\\Kerja")
        self.assertIn("iw73_dir", paths)
        self.assertTrue(paths["iw73_dir"].endswith("IW73"))


class TestProcessZSMR012(unittest.TestCase):
    """Pengujian modul ETL process_zsmr012 untuk tabel dbo.ZSMR012."""

    def test_job_registered(self):
        self.assertIn("MERAPIHKAN HASIL DOWNLOAD – ZSMR012", SCRIPTS)

    def test_parse_sap_date(self):
        from process_zsmr012 import parse_sap_date
        self.assertEqual(parse_sap_date("18.06.2024"), datetime(2024, 6, 18))
        self.assertEqual(parse_sap_date("2024-06-18"), datetime(2024, 6, 18))
        self.assertIsNone(parse_sap_date("00.00.0000"))
        self.assertIsNone(parse_sap_date(None))

    def test_parse_sap_time(self):
        from process_zsmr012 import parse_sap_time
        self.assertEqual(parse_sap_time("14:04:59"), datetime(1900, 1, 1, 14, 4, 59))
        self.assertIsNone(parse_sap_time("00:00:00"))
        self.assertIsNone(parse_sap_time(None))

    def test_clean_number(self):
        from process_zsmr012 import clean_number
        self.assertEqual(clean_number("1.234,56"), 1234.56)
        self.assertIsNone(clean_number(" - "))
        self.assertIsNone(clean_number(None))

    def test_parse_sample_zsmr012_file(self):
        import os
        from process_zsmr012 import parse_zsmr012_file, ZSMR012_DB_COLUMNS
        sample_path = r"D:\Kerja\SS\ZSMR012\ZSMR012_1.txt"
        if os.path.exists(sample_path):
            rows = parse_zsmr012_file(sample_path, "2026-10-02")
            self.assertGreater(len(rows), 0)
            first = rows[0]
            self.assertEqual(len(first), len(ZSMR012_DB_COLUMNS))
            self.assertEqual(first["FileName"], "ZSMR012")
            self.assertEqual(first["proses"], False)


class TestProcessIW58(unittest.TestCase):
    """Pengujian modul ETL process_iw58 untuk tabel dbo.Notif."""

    def test_job_registered(self):
        self.assertIn("MERAPIHKAN HASIL DOWNLOAD – IW58 (Notif)", SCRIPTS)

    def test_parse_sap_int(self):
        from process_iw58 import parse_sap_int
        self.assertEqual(parse_sap_int("100234"), 100234)
        self.assertEqual(parse_sap_int(" 1.002.345 "), 1002345)
        self.assertIsNone(parse_sap_int("-"))
        self.assertIsNone(parse_sap_int(None))

    def test_parse_sap_date(self):
        from process_iw58 import parse_sap_date
        self.assertEqual(parse_sap_date("02.10.2026"), datetime(2026, 10, 2))
        self.assertIsNone(parse_sap_date(""))

    def test_parse_sap_time(self):
        from process_iw58 import parse_sap_time
        self.assertEqual(parse_sap_time("09:15:30"), datetime(1900, 1, 1, 9, 15, 30))
        self.assertIsNone(parse_sap_time(None))

    def test_parse_mock_iw58_content(self):
        import os
        import tempfile
        from process_iw58 import parse_iw58_file, NOTIF_DB_COLUMNS
        headers = [
            "Notification", "Order", "Typ", "SysStatus", "UserStatus", "PG", "MnWkCtr",
            "CreatedOn", "CreatTme", "Notifdate", "Time", "Equipment", "Material",
            "Description", "ListName", "MaterialDesc", "Street", "BusA", "Dv",
            "Created", "Customer", "SalesDoc", "Item", "SalesOrd"
        ]
        sample_row = [
            "10001", "20002", "M1", "NOCO", "APPR", "10", "MECH",
            "01.10.2026", "08:00:00", "01.10.2026", "08:05:00", "EQ123", "MAT456",
            "Test Notif", "List A", "Test Material", "Jl. Test No 1", "BA01", "DV1",
            "USR01", "90001", "SD100", "10", "SO200"
        ]
        content = "\t".join(headers) + "\n" + "\t".join(sample_row) + "\n"
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as f:
            f.write(content)
            tmp_path = f.name
        try:
            rows = parse_iw58_file(tmp_path, "2026-10-02")
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["Notification"], 10001)
            self.assertEqual(row["Order"], 20002)
            self.assertEqual(row["Typ"], "M1")
            self.assertEqual(row["proses"], False)
            self.assertEqual(len(row), len(NOTIF_DB_COLUMNS))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_parse_iw58_with_leading_report_headers(self):
        """Memastikan parser IW58 mampu membaca file dengan judul laporan dan alias 'Notif.'."""
        import tempfile
        from process_iw58 import parse_iw58_file
        banner = [
            "Program: RIQMEL20                        Date: 04.10.2026",
            "----------------------------------------------------------",
            "Notification List Overview",
            "----------------------------------------------------------",
        ]
        headers = ["Notif.", "Order", "Typ", "SysStatus", "Created on", "Equipment"]
        sample_row = ["998877", "443322", "M1", "NOCO", "02.10.2026", "EQ555"]
        content = "\n".join(banner) + "\n" + "\t".join(headers) + "\n" + "\t".join(sample_row) + "\n"
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as f:
            f.write(content)
            tmp_path = f.name
        try:
            rows = parse_iw58_file(tmp_path, "2026-10-02")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["Notification"], 998877)
            self.assertEqual(rows[0]["Order"], 443322)
            self.assertEqual(rows[0]["Typ"], "M1")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_parse_iw58_empty_spool_message(self):
        """Memastikan file dengan 'List does not contain any data' ditangani tanpa crash."""
        import tempfile
        from process_iw58 import parse_iw58_file
        content = "RIQMEL20\nList does not contain any data\n"
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as f:
            f.write(content)
            tmp_path = f.name
        try:
            rows = parse_iw58_file(tmp_path, "2026-10-02")
            self.assertEqual(len(rows), 0)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_parse_iw58_with_sap_criteria_box_and_short_headers(self):
        """Memastikan parser IW58 mengabaikan box kriteria SAP dan membaca header tabel asli dengan alias On & Notifctn."""
        import tempfile
        from process_iw58 import parse_iw58_file
        import datetime
        raw_sap = (
            "=================================================================================\n"
            "|Selection field                  |Selection value                              |\n"
            "=================================================================================\n"
            "|Notification Type                |S1                                           |\n"
            "=================================================================================\n"
            "---------------------------------------------------------------------------------\n"
            "|  On        |CreatTme|Equipment|Notifctn |Order  |Mn.wk.ctr|Typ|Description    |\n"
            "---------------------------------------------------------------------------------\n"
            "|04.01.2016  |09:34:26|124824   |300729270|       |P21-OFF  |S1 |TEST NOTIF 01  |\n"
            "|05.01.2016  |10:00:00|124825   |300729271|100022 |P21-OFF  |S1 |TEST NOTIF 02  |\n"
            "---------------------------------------------------------------------------------\n"
        )
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as f:
            f.write(raw_sap)
            tmp_path = f.name
        try:
            rows = parse_iw58_file(tmp_path, "2026-10-04")
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["Notification"], 300729270)
            self.assertEqual(rows[0]["DatePeriode"], datetime.date(2016, 1, 4))
            self.assertEqual(rows[0]["Typ"], "S1")
            self.assertEqual(rows[0]["Equipment"], "124824")
            self.assertEqual(rows[1]["Notification"], 300729271)
            self.assertEqual(rows[1]["DatePeriode"], datetime.date(2016, 1, 5))
            self.assertEqual(rows[1]["Order"], 100022)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class TestProcessIW73(unittest.TestCase):
    """Pengujian modul ETL process_iw73 untuk tabel dbo.Service."""

    def test_job_registered(self):
        self.assertIn("MERAPIHKAN HASIL DOWNLOAD – IW73 (Service)", SCRIPTS)

    def test_parse_sap_float(self):
        from process_iw73 import parse_sap_float
        self.assertEqual(parse_sap_float("1.500.000,50"), 1500000.50)
        self.assertIsNone(parse_sap_float(" - "))
        self.assertIsNone(parse_sap_float(None))

    def test_parse_sap_int(self):
        from process_iw73 import parse_sap_int
        self.assertEqual(parse_sap_int("4000123"), 4000123)
        self.assertIsNone(parse_sap_int(None))

    def test_parse_mock_iw73_content(self):
        import os
        import tempfile
        from process_iw73 import parse_iw73_file, SERVICE_DB_COLUMNS
        headers = [
            "BscStart", "Order", "Equipment", "SerialNo", "MaterialDescription",
            "WorkCtr", "MnWkCtr", "ListName", "Description", "MAT",
            "SystemStatus", "Street", "Material", "ActStart", "CreatedOn",
            "ChangedOn", "ChangedBy", "Type", "City", "Enteredby",
            "Release", "ActTotSum", "SumTotPlan", "ActualEnd", "SchedFin",
            "BusA", "SchedStart", "PG", "RespCCtr", "UserStatus"
        ]
        sample_row = [
            "01.10.2026", "50001", "EQ999", "SN888", "Service Machine",
            "WC01", "MWC01", "List B", "Annual Maintenance", "MAT99",
            "TECO", "Jl. Sudirman", "MAT999", "01.10.2026", "01.10.2026",
            "02.10.2026", "ADM01", "SM01", "Jakarta", "ENG01",
            "01.10.2026", "500.000,00", "600.000,00", "02.10.2026", "02.10.2026",
            "1000", "01.10.2026", "PG01", "CC100", "E0001"
        ]
        content = "\t".join(headers) + "\n" + "\t".join(sample_row) + "\n"
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as f:
            f.write(content)
            tmp_path = f.name
        try:
            rows = parse_iw73_file(tmp_path, "2026-10-02")
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["Order"], 50001)
            self.assertEqual(row["Equipment"], "EQ999")
            self.assertEqual(row["ActTotSum"], 500000.0)
            self.assertEqual(row["SumTotPlan"], 600000.0)
            self.assertEqual(row["proses"], False)
            self.assertEqual(len(row), len(SERVICE_DB_COLUMNS))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_parse_iw73_with_leading_report_headers(self):
        """Memastikan parser IW73 mampu membaca file dengan judul laporan dan alias kolom Jerman/Inggris."""
        import tempfile
        from process_iw73 import parse_iw73_file
        banner = [
            "RIAUFK20 Service Orders                   Page: 1",
            "==================================================",
        ]
        headers = ["Bsc start", "Auftrag", "Equipment", "Act. start", "Work ctr"]
        sample_row = ["01.10.2026", "665544", "EQ777", "01.10.2026", "CTR01"]
        content = "\n".join(banner) + "\n" + "\t".join(headers) + "\n" + "\t".join(sample_row) + "\n"
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as f:
            f.write(content)
            tmp_path = f.name
        try:
            rows = parse_iw73_file(tmp_path, "2026-10-02")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["Order"], 665544)
            self.assertEqual(rows[0]["Equipment"], "EQ777")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_parse_iw73_empty_spool_message(self):
        """Memastikan file dengan 'List does not contain any data' ditangani tanpa crash."""
        import tempfile
        from process_iw73 import parse_iw73_file
        content = "RIAUFK20\nList does not contain any data\n"
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as f:
            f.write(content)
            tmp_path = f.name
        try:
            rows = parse_iw73_file(tmp_path, "2026-10-02")
            self.assertEqual(len(rows), 0)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_parse_iw73_with_sap_sort_box(self):
        """Memastikan parser IW73 mengabaikan box Sort criteria SAP dan mengambil header tabel asli."""
        import tempfile
        from process_iw73 import parse_iw73_file
        import datetime
        raw_sap = (
            "=================================================================================\n"
            "|Sort criteria                    |A|D|Tot|Sub|Pag|Interv.|Tot.f.col.|Subt.col. |\n"
            "=================================================================================\n"
            "|Order                            | |X|   |   |   |       |          |          |\n"
            "=================================================================================\n"
            "---------------------------------------------------------------------------------\n"
            "|Bsc start |Order     |Equipment|Act. start|Work ctr|Mn.wk.ctr|\n"
            "---------------------------------------------------------------------------------\n"
            "|04.01.2016|500123    |EQ-99    |04.01.2016|WC01    |MWC01    |\n"
            "---------------------------------------------------------------------------------\n"
        )
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as f:
            f.write(raw_sap)
            tmp_path = f.name
        try:
            rows = parse_iw73_file(tmp_path, "2026-10-04")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["Order"], 500123)
            self.assertEqual(rows[0]["DatePeriode"], datetime.date(2016, 1, 4))
            self.assertEqual(rows[0]["Equipment"], "EQ-99")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class TestDownloaderInsertSqlParam(unittest.TestCase):
    """Pengujian integrasi parameter insert-sql pada downloader ZSMR012, IW58, dan IW73."""

    def test_insert_sql_in_download_jobs(self):
        for job_name in [
            "DOWNLOAD BG JOB ZSMR012 – SAP Background Job",
            "DOWNLOAD BG JOB IW58 – SAP Background Job",
            "DOWNLOAD BG JOB IW73 – SAP Background Job",
        ]:
            param_args = [p["arg"] for p in SCRIPTS[job_name]["params"]]
            self.assertIn("insert-sql", param_args, f"'insert-sql' harus ada di params {job_name}")

    def test_build_cli_args_includes_insert_sql(self):
        params = {
            "to-date": "02.10.2026",
            "from-date": "01.10.2026",
            "job-name": "RIQMEL20",
            "save-path": "D:\\Kerja\\SS\\IW58\\",
            "file-prefix": "IW58_",
            "vbs-path": "vbs\\DownloadBGJob_IW58.vbs",
            "insert-sql": "True",
        }
        args = build_cli_args("DOWNLOAD BG JOB IW58 – SAP Background Job", params)
        self.assertIn("--insert-sql", args)
        idx = args.index("--insert-sql")
        self.assertEqual(args[idx + 1], "True")

    def test_job_config_valid(self):
        import json
        with open("job_config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
        ok, warnings = validate_job_config(cfg)
        self.assertTrue(ok, f"job_config.json harus valid, warnings: {warnings}")


class TestSequenceRunner(unittest.TestCase):
    """Pengujian modul SequenceRunner untuk eksekusi urutan job kustom."""

    def test_empty_sequence(self):
        from sequence_runner import SequenceRunner
        completed = []
        runner = SequenceRunner(
            sequence_items=[],
            on_sequence_complete=lambda ok, msg: completed.append((ok, msg))
        )
        res = runner.run()
        self.assertTrue(res)
        self.assertEqual(len(completed), 1)
        self.assertTrue(completed[0][0])

    def test_sequence_runner_abort(self):
        from sequence_runner import SequenceRunner
        runner = SequenceRunner(
            sequence_items=[
                {"name": "DOWNLOAD BG JOB ZSMR012 – SAP Background Job", "params": {}},
            ]
        )
        runner.stop()
        self.assertTrue(runner._is_aborted)


class TestMultiSessionVBS(unittest.TestCase):
    """Pengujian file VBScript memiliki alokasi multi-session dinamis."""

    def test_vbscript_has_dynamic_session_allocation(self):
        for vbs_rel in [
            r"vbs\DownloadBGJob_IW58.vbs",
            r"vbs\DownloadBGJob_IW73.vbs",
            r"vbs\DownloadBGJob_ZSMR012.vbs",
        ]:
            with open(vbs_rel, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            self.assertIn("isNewSessionCreated", content, f"{vbs_rel} harus mendukung isNewSessionCreated")
            self.assertIn("CreateSession", content, f"{vbs_rel} harus memiliki CreateSession")
            self.assertIn("SESSION_MANAGER", content, f"{vbs_rel} harus memeriksa SESSION_MANAGER")


if __name__ == "__main__":
    unittest.main()

