"""test_smoke.py — Smoke Test Dasar untuk SAP Automation.

Menguji fungsi-fungsi utilitas utama tanpa memerlukan koneksi database atau SAP GUI aktif:
  - Definisi job dan build CLI args (`job_definitions.py`)
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


class TestJobDefinitions(unittest.TestCase):
    """Pengujian untuk definisi job dan argumen CLI."""

    def test_scripts_not_empty(self):
        """Pastikan SCRIPTS terdefinisi dan tidak kosong."""
        self.assertGreater(len(SCRIPTS), 0, "Daftar SCRIPTS tidak boleh kosong")

    def test_build_cli_args_for_all_jobs(self):
        """Pastikan build_cli_args dapat menghasilkan list argumen tanpa error untuk semua job."""
        dummy_db = {"server": "localhost", "user": "sa", "pwd": "123", "name": "DB"}
        for name, info in SCRIPTS.items():
            params = {p["arg"]: p["default"] for p in info["params"]}
            args = build_cli_args(name, params, db_config=dummy_db)
            self.assertIsInstance(args, list, f"Result build_cli_args untuk '{name}' harus berupa list")

    def test_validate_job_config_valid(self):
        """Pengujian validasi struktur json konfigurasi yang valid."""
        sample_config = {
            name: {p["arg"]: "val" for p in info["params"]}
            for name, info in SCRIPTS.items()
        }
        is_valid, warnings = validate_job_config(sample_config)
        self.assertTrue(is_valid, "Sample config valid harus mengembalikan True")
        self.assertEqual(len(warnings), 0)

    def test_validate_job_config_invalid_job(self):
        """Pengujian validasi konfigurasi dengan job name yang tidak dikenal."""
        sample_config = {"NonExistentJob": {"param": "123"}}
        is_valid, warnings = validate_job_config(sample_config)
        self.assertFalse(is_valid)
        self.assertTrue(any("tidak dikenal" in w for w in warnings))


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
