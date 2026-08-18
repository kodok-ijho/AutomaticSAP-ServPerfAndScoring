# Task Perbaikan SAP Automation

> Urutan pengerjaan mengikuti prioritas di `plan.md`:
> **Security → Config/State → Shared Runner → SQL → Testing & Docs**
>
> Tandai setiap task dengan `[x]` setelah selesai dikerjakan.

---

## ✅ Fase 1 — Quick Wins
**Target:** Kurangi risiko terbesar tanpa mengubah arsitektur.

---

### 🔐 1.1 Hapus Hardcoded Credential dari `config.py`
- [x] Hapus nilai default sensitif pada `DB_USER`, `DB_PASSWORD`, `SAP_USERNAME` di `config.py`
- [x] Ganti fallback dengan `raise ValueError(...)` atau string kosong `""` agar aplikasi gagal dengan pesan jelas jika `.env` tidak ada
- [x] Pastikan file `.env` sudah lengkap dan benar sebelum menghapus fallback
- [x] Tambahkan komentar di `config.py` yang menjelaskan bahwa `.env` wajib ada
- **File yang diubah:** `config.py`, `.env`

### 🗑️ 1.2 Sanitasi File JSON Legacy
- [x] Buka `RPA_SAP_1.json` — hapus atau ganti semua connection string, username, dan password dengan placeholder `"***REMOVED***"`
- [x] Buka `Download-ZSMR007B.json` — lakukan hal yang sama
- [x] Verifikasi kedua file tersebut tidak dipanggil dari script Python manapun (search `RPA_SAP_1.json` dan `Download-ZSMR007B.json` di seluruh `.py`)
- [x] Jika sudah tidak dipakai, pertimbangkan pindah ke folder `legacy/`
- **File yang diubah:** `RPA_SAP_1.json`, `Download-ZSMR007B.json`

### 🔒 1.3 Hapus Password dari `job_config.json`
- [x] Hapus field `db_settings.pwd` dari `job_config.json`
- [x] Update `_save_config()` di `dashboard.py` agar tidak menyertakan `pwd` saat write JSON
- [x] Update endpoint `POST /api/db-config` di `web_dashboard.py` agar tidak menyimpan `pwd` ke file
- [x] Pastikan password DB hanya dibaca dari `.env`, tidak pernah disimpan ke file JSON
- **File yang diubah:** `job_config.json`, `dashboard.py`, `web_dashboard.py`

### 🛡️ 1.4 Ganti `shell=True` di `automate_zsme09e.py`
- [x] Temukan fungsi `run_vbs()` di `automate_zsme09e.py`
- [x] Ubah `subprocess.run(" ".join(cmd), shell=True)` menjadi `subprocess.run(["wscript.exe", full_path] + args)`
- [x] Hapus quote manual (`f'"{a}"'`) dari daftar argumen karena tidak diperlukan saat `shell=False`
- [x] Test jalankan job ZSME09E untuk memastikan VBS masih bisa dipanggil
- **File yang diubah:** `automate_zsme09e.py`

### ✔️ 1.5 Tambahkan Validasi `job_config.json` Saat Startup
- [x] Buat fungsi `validate_job_config(config: dict) -> bool` yang mengecek struktur dasar config
- [x] Validasi: setiap key job harus ada di `SCRIPTS`, setiap arg harus dikenal
- [x] Jika ada key tidak dikenal atau struktur rusak, print warning (jangan crash aplikasi)
- [x] Panggil fungsi ini di `_load_config()` pada `dashboard.py` dan di `lifespan` pada `web_dashboard.py`
- **File yang diubah:** `job_definitions.py`, `dashboard.py`, `web_dashboard.py`

### 📝 1.6 Rapikan `README.md`
- [x] Perbaiki karakter rusak encoding (emoji dan tanda khusus yang tidak terbaca)
- [x] Update bagian "Struktur File Utama" agar mencerminkan file yang ada sekarang
- [x] Tambahkan cara menjalankan web dashboard (`python web_dashboard.py`)
- [x] Tambahkan catatan bahwa file `.env` wajib dibuat sebelum menjalankan aplikasi
- **File yang diubah:** `README.md`

---

## 🏗️ Fase 2 — Konsolidasi Core
**Target:** Hilangkan duplikasi dan stabilkan state.

---

### 📦 2.1 Buat Modul Shared `sap_utils.py`
- [x] Buat file baru `sap_utils.py` di root project
- [x] Pindahkan fungsi `verify_sap_ready()` dari `automate_zsme09e.py` ke `sap_utils.py`
- [x] Pindahkan fungsi `check_sap_login()` dari `automate_zsme09e.py` ke `sap_utils.py`
- [x] Pindahkan fungsi `get_sap_status()` dari `web_dashboard.py` ke `sap_utils.py`
- [x] Update semua import di file yang relevan agar mengambil dari `sap_utils`
- **File yang dibuat/diubah:** `sap_utils.py` (baru), `automate_zsme09e.py`, `web_dashboard.py`

### 🔑 2.2 Buat Fungsi `ensure_sap_logged_in()` di `sap_utils.py`
- [x] Buat fungsi dengan signature: `ensure_sap_logged_in(vbs_login_path: str, timeout: int = 60) -> bool`
- [x] Langkah 1 — Panggil `verify_sap_ready()`: jika sudah login, return `True` langsung
- [x] Langkah 2 — Jika belum login: jalankan `subprocess.run(["wscript.exe", vbs_login_path])` (tanpa `shell=True`)
- [x] Langkah 3 — Setelah VBS selesai: polling `check_sap_login()` setiap 2 detik sampai `True` atau timeout
- [x] Langkah 4 — Return `True` jika berhasil, `False` jika timeout atau error
- [x] Tambahkan log yang jelas di setiap tahap: `[SAP] Mencoba login...`, `[SAP] Login berhasil`, dll.
- [x] Ganti pemanggilan `verify_sap_ready()` dan `check_sap_login()` di `automate_zsme09e.py` dengan `ensure_sap_logged_in()`
- **File yang diubah:** `sap_utils.py`, `automate_zsme09e.py`

### 📦 2.3 Buat Modul Shared `db_utils.py`
- [x] Buat file baru `db_utils.py` di root project (pertimbangkan merge dengan `db.py`)
- [x] Buat fungsi `delete_by_periode(cursor, table_name: str, periode: str)` — pola berulang di 4 script
- [x] Buat fungsi `insert_batch(cursor, table_name: str, df)` — pola insert `executemany` yang sama
- [x] Buat fungsi `clean_sap_number(value) -> float | None` — normalisasi angka format SAP (`1.234,56` → `1234.56`)
- [x] Buat fungsi `detect_file_encoding(file_path: str) -> str` — deteksi encoding file
- [x] Buat fungsi `get_connection_with_retry(cfg: dict, retries: int = 3, delay: int = 5)` — koneksi DB dengan retry
- **File yang dibuat:** `db_utils.py` (baru)

### 🔧 2.4 Jadikan `job_definitions.py` Read-Only
- [x] Hapus logika mutasi `p["default"] = ...` dari `_load_config()` di `dashboard.py`
- [x] Buat dictionary `self._runtime_params: dict` di `dashboard.py` sebagai pengganti penyimpanan nilai user
- [x] Pastikan `_render_param_form()` membaca nilai dari `self._runtime_params` (bukan dari `SCRIPTS["default"]`)
- [x] Pastikan `_save_config()` membaca dari `self._runtime_params` (bukan dari `SCRIPTS`)
- [x] Verifikasi `job_definitions.py` tidak pernah diubah saat runtime
- **File yang diubah:** `dashboard.py`

### 🔄 2.5 Buat `job_runner.py` — Service Layer Bersama
- [x] Buat file baru `job_runner.py` di root project
- [x] Pindahkan logika build subprocess command ke `job_runner.py`
- [x] Buat fungsi `run_job(name, params, db_config, on_log_line: callable)` — bisa dipakai desktop & web
- [x] Buat fungsi `stop_job(pid: int)` — logika `taskkill /F /T /PID` dipindah ke sini
- [x] Update `dashboard.py` untuk memanggil `job_runner.run_job(...)` dan menerima log via callback
- [x] Update `web_dashboard.py` untuk melakukan hal yang sama
- **File yang dibuat/diubah:** `job_runner.py` (baru), `dashboard.py`, `web_dashboard.py`

### 📊 2.6 Standarkan Format Status Job
- [x] Definisikan konstanta status di satu tempat: `STATUS_IDLE`, `STATUS_RUNNING`, `STATUS_SUCCESS`, `STATUS_FAILED`
- [x] Tempatkan konstanta di `job_runner.py` (service layer)
- [x] Update `dashboard.py` untuk menggunakan konstanta (ganti string `"Success"`, `"Failed"`, dll.)
- [x] Update `web_dashboard.py` untuk menggunakan konstanta yang sama
- **File yang diubah:** `dashboard.py`, `web_dashboard.py`, `job_runner.py`

### 🔗 2.7 Konsolidasikan Script Parsing SQL
- [x] Update `process_reports.py` — ganti pola SQL berulang dengan helper dari `db_utils.py`
- [x] Update `ProsesKE30byDiv.py` — ganti pola SQL berulang dengan helper dari `db_utils.py`
- [x] Update `ProcessKE30byEq.py` — ganti pola SQL berulang dengan helper dari `db_utils.py`
- [x] Update `automate_zsme09e.py` — ganti pola SQL berulang dengan helper dari `db_utils.py`
- [x] Hapus kode duplikat yang sudah dipindahkan ke `db_utils.py`
- **File yang diubah:** `process_reports.py`, `ProsesKE30byDiv.py`, `ProcessKE30byEq.py`, `automate_zsme09e.py`

---

## 🛡️ Fase 3 — Reliability
**Target:** Job lebih tahan gagal dan lebih mudah ditelusuri.

---

### 🔁 3.1 Retry & Timeout untuk Koneksi DB
- [x] Implementasikan `get_connection_with_retry()` di `db_utils.py`
- [x] Ganti semua pemanggilan `pyodbc.connect(...)` langsung di script job dengan fungsi ini
- [x] Test: koneksi DB otomatis retry jika ada masalah jaringan sementara
- **File yang diubah:** `db_utils.py`, `process_reports.py`, `ProsesKE30byDiv.py`, `ProcessKE30byEq.py`, `automate_zsme09e.py`, `download_zsmr007b.py`

### 💪 3.2 Perkuat `ensure_sap_logged_in()` dengan Retry Loop
- [x] Tambahkan parameter `max_retries: int = 3` pada `ensure_sap_logged_in()`
- [x] Jika setelah VBS selesai SAP masih belum login, tunggu beberapa detik lalu jalankan VBS lagi (sampai `max_retries`)
- [x] Tambahkan penanganan popup multi-login: setelah login, cek apakah ada modal dialog `wnd[1]` dan dismiss
- [x] Pastikan log mencantumkan nomor percobaan: `[SAP] Mencoba login... (1/3)`, `[SAP] Login berhasil...`, dll.
- **File yang diubah:** `sap_utils.py`

### ✅ 3.3 Validasi Output Setelah SAP Export
- [x] Di `download_zsmr007b.py`: setelah VBS selesai, cek apakah file hasil download benar-benar ada dan tidak 0 byte
- [x] Di `automate_zsme09e.py`: setelah VBS selesai, cek keberadaan dan ukuran file (tidak boleh 0 byte)
- [x] Jika file tidak ada atau kosong, print error dan hentikan proses sebelum SQL dimulai
- **File yang diubah:** `download_zsmr007b.py`, `automate_zsme09e.py`

### 🧹 3.4 Mekanisme Rollback Konsisten untuk Output Parsial
- [x] Pastikan semua script upload SQL memiliki `conn.rollback()` di blok `except`
- [x] Audit `process_reports.py`, `ProsesKE30byDiv.py`, `ProcessKE30byEq.py`, `automate_zsme09e.py` — tambahkan rollback konsisten
- [x] Pastikan koneksi selalu ditutup di blok `finally` (try/finally)
- **File yang diubah:** `process_reports.py`, `ProsesKE30byDiv.py`, `ProcessKE30byEq.py`, `automate_zsme09e.py`

### 🧪 3.5 Buat Smoke Test Dasar
- [x] Buat file `test_smoke.py` di root project
- [x] Test 1: `build_cli_args()` menghasilkan argumen yang benar untuk setiap job di `SCRIPTS`
- [x] Test 2: Validasi parsing format angka SAP (`clean_sap_number`, `parse_sap_int`, `is_sap_numeric`)
- [x] Test 3: Validasi `validate_job_config()` dan `classify_log_tag()`
- [x] Run `python test_smoke.py` — 16/16 tests pass
- **File yang dibuat:** `test_smoke.py` (baru)

---

## 📚 Fase 4 — Maintainability
**Target:** Project mudah dirawat jangka panjang.

---

### 📁 4.1 Bersihkan Repo & Perbaiki `.gitignore`
- [x] Tambahkan ke `.gitignore`: `venv/`, `__pycache__/`, `*.pyc`, `logs/`, `*.log`, `*.xlsx` (output), `*.dat` (output), `ZSMR007B - */`
- [x] Jalankan `git rm -r --cached venv/` jika `venv/` sudah terlanjur di-track git
- [x] Jalankan `git rm -r --cached __pycache__/` jika sudah di-track
- [x] Pindahkan atau hapus file output laporan yang tersimpan di repo
- **File yang diubah:** `.gitignore`

### 🏷️ 4.2 Tambahkan Type Hints ke Modul Shared
- [x] Tambahkan type hints pada semua fungsi di `config.py` dan `db.py` / `db_utils.py`
- [x] Tambahkan type hints pada semua fungsi di `job_definitions.py`
- [x] Tambahkan type hints pada semua fungsi di `sap_utils.py`
- [x] Tambahkan type hints pada semua fungsi di `job_runner.py`
- **File yang diubah:** semua modul shared

### 🔍 4.3 Perbaiki CSS Variable yang Tidak Terdefinisi
- [x] Buka `static/style.css` — cari semua penggunaan `--sap-blue-focus`
- [x] Definisikan variable tersebut di blok `:root { }` atau ganti dengan nilai warna langsung
- [x] Verifikasi tampilan web dashboard di browser setelah diperbaiki
- [x] Periksa apakah ada variable CSS lain yang dipakai tapi tidak didefinisikan
- **File yang diubah:** `static/style.css`

### 📖 4.4 Dokumentasikan Flow Tiap Job
- [x] Buat folder `docs/` di root project
- [x] Buat file `docs/jobs.md` berisi tabel untuk setiap job:
  - Nama job & script
  - Parameter yang dibutuhkan
  - Input (file/folder)
  - Output (file Excel / tabel SQL)
  - Urutan eksekusi yang disarankan (jika ada dependensi antar job)
- **File yang dibuat:** `docs/jobs.md` (baru)

### 📋 4.5 Buat Checklist Operasi Harian
- [x] Buat file `docs/checklist_harian.md`
- [x] Isi dengan langkah-langkah yang harus dilakukan operator setiap periode:
  - Pastikan SAP GUI sudah login
  - Jalankan job dalam urutan yang benar
  - Verifikasi hasil di SQL Server
  - Cara membaca log jika ada error
  - Kontak person jika ada masalah teknis
- **File yang dibuat:** `docs/checklist_harian.md` (baru)

### 🔧 4.6 Pisahkan UI dari Business Logic
- [x] Audit `dashboard.py` — pastikan tidak mengandung logika bisnis langsung (SQL, parsing, SAP check)
- [x] Audit `web_dashboard.py` — pastikan semua logika bisnis sudah dipindah ke modul shared
- [x] Pastikan kedua UI hanya memanggil: `job_runner`, `sap_utils`, `db_utils`, `config`
- **File yang diubah:** `dashboard.py`, `web_dashboard.py`

---

## 📊 Ringkasan Progress

| Fase | Grup Task | Selesai |
|------|-----------|---------|
| Fase 1 — Quick Wins | 6 | 6 / 6 ✅ |
| Fase 2 — Konsolidasi Core | 7 | 7 / 7 ✅ |
| Fase 3 — Reliability | 5 | 5 / 5 ✅ |
| Fase 4 — Maintainability | 6 | 6 / 6 ✅ |
| **TOTAL** | **24** | **24 / 24 ✅** |

---

## 🗂️ File Baru yang Dibuat

| File | Dibuat di Fase | Fungsi |
|------|---------------|--------|
| `sap_utils.py` | 2.1, 2.2 | Helper SAP: cek status, `ensure_sap_logged_in()` |
| `db_utils.py` | 2.3 | Helper DB: koneksi retry, delete, insert, clean angka |
| `job_runner.py` | 2.5 | Service layer eksekusi job (shared desktop & web) |
| `test_smoke.py` | 3.5 | Smoke test dasar tanpa framework |
| `docs/TECHNICAL.md` | Dokumen Teknis | Panduan arsitektur sistem & developer |
| `docs/MANUAL_BOOK.md` | User Guide | Panduan operasional pengguna & SOP closing |
| `docs/jobs.md` | 4.4 | Dokumentasi flow, input, output tiap job & CLI reference |
| `docs/checklist_harian.md` | 4.5 | Checklist operasi harian untuk operator |
