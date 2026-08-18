"""test_smoke.py — Smoke Test Dasar untuk SAP Automation.

Menguji fungsi-fungsi utilitas utama tanpa memerlukan koneksi database atau SAP GUI aktif:
  - Definisi job dan build CLI args (`job_definitions.py`)
  - Resolusi path dinamis workspace Astragraphia (`path_resolver.py`)
  - Parsing angka format SAP (`db_utils.py`)
  - Klasifikasi log tag (`job_runner.py`)
  - Validasi konfigurasi (`job_definitions.py`)

Jalankan dengan: python test_smoke.py
"""

import sys
import unittest
from job_definitions import SCRIPTS, build_cli_args, validate_job_config
from db_utils import clean_sap_number, parse_sap_int, is_sap_numeric, format_sap_number_display
from job_runner import classify_log_tag, STATUS_IDLE, STATUS_RUNNING, STATUS_SUCCESS, STATUS_FAILED
from path_resolver import resolve_workspace_paths, parse_period_date, get_smart_spool_date_range
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


if __name__ == "__main__":
    unittest.main()
