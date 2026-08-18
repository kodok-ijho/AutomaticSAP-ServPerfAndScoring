# Plan Perbaikan SAP Automation

## Ringkasan Temuan

Repo ini sudah punya fondasi yang jelas: `job_definitions.py` jadi sumber job, `dashboard.py` dan `web_dashboard.py` sama-sama menjalankan job, dan script pemrosesan data sudah bisa membaca SAP export lalu mengirim ke SQL Server.

Masalah utamanya ada di tiga area:

1. **Keamanan dan konfigurasi** masih bocor ke banyak tempat.
2. **State/configuration** bercampur dengan definisi job, jadi perilaku aplikasi mudah berubah diam-diam.
3. **Reliability dan maintainability** masih rendah karena ada duplikasi logika, process management yang kasar, dan parsing data yang masih rapuh.

## Peta Codebase

- `dashboard.py`: dashboard desktop berbasis Tkinter, menjalankan job via subprocess, scheduler lokal, dan persistence `job_config.json`.
- `web_dashboard.py`: dashboard web berbasis FastAPI, endpoint job/config/SAP status, scheduler async, server-sent event untuk log.
- `job_definitions.py`: registry job dan parameter CLI yang dipakai desktop/web.
- `config.py` dan `db.py`: konfigurasi DB/SAP dan helper koneksi SQL Server.
- `rpa_sap_1.py`, `download_zsmr007b.py`, `automate_zsme09e.py`: orkestrasi SAP GUI/VBS dan download/reporting.
- `process_reports.py`, `ProsesKE30byDiv.py`, `ProcessKE30byEq.py`: parsing output SAP, normalisasi data, output file, dan upload SQL.
- `static/`: UI web dashboard.
- `vbs/`: script SAP GUI scripting yang dipanggil dari Python.
- `RPA_SAP_1.json` dan `Download-ZSMR007B.json`: artefak legacy/OpenRPA yang masih menyimpan konfigurasi workflow lama.

## Temuan Spesifik

- `config.py` masih punya fallback credential DB yang sensitif. Ini membuat credential tetap bocor walaupun `.env` tidak disertakan.
- `job_config.json` menyimpan `db_settings.pwd` dalam plaintext. File ini juga menyimpan path absolut yang spesifik laptop/operator.
- `RPA_SAP_1.json` dan `Download-ZSMR007B.json` berisi connection string DB lama lengkap dengan user/password.
- `dashboard.py` memuat config dengan cara mengubah `SCRIPTS[*]["params"][*]["default"]`. Dampaknya, definisi job tidak lagi murni dan nilai default bisa berubah antar layar.
- `dashboard.py` dan `web_dashboard.py` punya logic runner, scheduler, stop job, dan save config masing-masing. Risiko drift sudah terlihat karena implementasinya tidak identik.
- `job_definitions.py` sudah membantu sentralisasi job, tetapi komentar `DB_ARG_SCRIPTS` tidak sepenuhnya selaras dengan isi set. Ini tanda metadata job perlu divalidasi.
- `automate_zsme09e.py` memanggil VBS dengan `shell=True`. Ini tidak perlu dan menambah risiko quoting/path injection.
- Script parsing/upload SQL punya banyak pola berulang: build connection string, delete periode, insert batch, numeric cleaning, dan handling NULL.
- Fungsi pengecekan status login SAP (`check_sap_login`, `verify_sap_ready`, `get_sap_status`) dan fungsi login (`LoginSAP.vbs`) berdiri sendiri-sendiri — tidak ada fungsi tunggal yang menggabungkan keduanya. Akibatnya, jika SAP belum login saat job dijalankan, program langsung berhenti dan meminta user login manual alih-alih melakukan auto-login.
- `static/index.html`, `static/app.js`, dan `README.md` menunjukkan karakter UI/emoji yang rusak encoding. `static/style.css` juga memakai variable `--sap-blue-focus` yang tidak didefinisikan.
- Repo kerja menyertakan `venv/`, `__pycache__/`, `logs/`, dan output laporan. Ini membuat audit, search, backup, dan distribusi project menjadi berat.

## Saran Perbaikan

### 1. Amankan konfigurasi dan kredensial

- Hapus semua default kredensial sensitif dari `config.py`.
- Pastikan `.env` menjadi satu-satunya sumber rahasia runtime.
- Bersihkan kredensial yang tertanam di artefak ekspor seperti `RPA_SAP_1.json` dan `Download-ZSMR007B.json`.
- Pisahkan `job_config.json` menjadi konfigurasi user biasa dan konfigurasi rahasia, supaya file konfigurasi tidak ikut menyimpan password tanpa kontrol.

### 2. Pisahkan definisi job dari state runtime

- Jangan mutasi `SCRIPTS[*]["params"][*]["default"]` saat load/save config.
- Jadikan `job_definitions.py` benar-benar statis, lalu letakkan state pengguna di layer persistence terpisah.
- Tambahkan validasi skema untuk `job_config.json` agar key yang rusak atau hilang tidak diam-diam diteruskan ke job.

### 3. Satukan logic runner

- `dashboard.py` dan `web_dashboard.py` sama-sama punya pola eksekusi job, logging, stop job, dan scheduler.
- Ambil satu service layer bersama untuk:
  - load config
  - build argumen CLI
  - run job
  - stop job
  - stream log
- Dengan begitu desktop UI dan web UI hanya jadi front-end, bukan implementasi yang berbeda.

### 4. Rapikan process management

- Hindari `shell=True` di `automate_zsme09e.py` saat memanggil VBS.
- Gunakan `subprocess.run([...])` yang langsung menerima argumen list.
- Buat mekanisme stop job yang konsisten di semua runner.
- Tambahkan timeout dan status gagal yang eksplisit untuk proses SAP/VBS.

### 5. Standarkan parsing dan upload SQL

- `process_reports.py`, `ProcessKE30byEq.py`, `ProsesKE30byDiv.py`, dan `automate_zsme09e.py` sama-sama melakukan cleaning data dan upload SQL dengan gaya berbeda.
- Pecah jadi helper bersama untuk:
  - koneksi DB
  - delete-by-periode
  - insert batch
  - normalisasi numerik SAP
  - deteksi encoding file
- Ini akan mengurangi bug parsing yang muncul hanya di satu skrip.

### 6. Perkuat observability

- Jadikan logging konsisten: ada level, job name, timestamp, dan path output.
- Simpan trail log ke file untuk semua job penting, bukan hanya sebagian.
- Tambahkan ringkasan hasil run: jumlah baris baca, jumlah baris insert, jumlah file diproses, dan lokasi output.

### 7. Bersihkan repo

- Jangan simpan `venv/`, `__pycache__/`, dan log hasil run ke repo.
- Rapikan `README.md` yang masih berisi encoding rusak dan instruksi yang kurang presisi.
- Perbaiki nama file dan label yang masih inkonsisten, terutama yang campur bahasa dan tanda baca.

## Rencana Perbaikan

### Fase 1 - Quick Wins

Target: mengurangi risiko paling besar tanpa mengubah arsitektur besar.

1. Hapus hardcoded credential dari `config.py`.
2. Sanitasi file ekspor workflow/JSON yang masih menyimpan connection string.
3. Ganti `shell=True` pada pemanggilan VBS di `automate_zsme09e.py`.
4. Tambahkan validasi sederhana untuk config JSON sebelum dipakai.
5. Rapikan `README.md` agar sesuai kondisi nyata repo.

### Fase 2 - Konsolidasi Core

Target: mengurangi duplikasi dan state yang saling mengganggu.

1. Buat modul shared untuk:
   - config load/save
   - db helper
   - job execution
   - log streaming
2. Jadikan `job_definitions.py` read-only.
3. Pindahkan semua parsing parameter dan penyusunan CLI ke satu jalur.
4. Samakan format status job antara desktop dan web.
5. Buat fungsi `ensure_sap_logged_in(vbs_login_path, timeout)` di modul shared (misalnya `sap_utils.py`) yang menggabungkan cek + auto-login:
   - Panggil `verify_sap_ready()` untuk cek status.
   - Jika belum login, jalankan `LoginSAP.vbs` via `subprocess.run(["wscript.exe", vbs_login_path])` (tanpa `shell=True`).
   - Setelah VBS selesai, polling ulang status login sampai True atau timeout tercapai.
   - Kembalikan `True` jika berhasil login, `False` jika timeout atau error.
   - Ganti semua titik pemanggilan `verify_sap_ready()` / `check_sap_login()` di `automate_zsme09e.py` dan script lain yang relevan dengan fungsi baru ini.

### Fase 3 - Reliability

Target: membuat job lebih tahan gagal dan lebih mudah ditelusuri.

1. Tambahkan timeout dan retry untuk koneksi DB yang rawan putus.
2. Tambahkan output validation setelah SAP export atau proses file selesai.
3. Buat mekanisme rollback/cleanup yang jelas untuk output parsial.
4. Tambahkan smoke test untuk parsing file sample dan build CLI args.
5. Perkuat `ensure_sap_logged_in()` dengan retry loop:
   - Jika login VBS gagal (misal koneksi VPN lambat), tunggu beberapa detik lalu coba lagi sampai batas maksimal retry.
   - Tambahkan logging yang jelas di setiap tahap (SAP tidak aktif / belum ada koneksi / scripting diblokir server / login berhasil).
   - Tangani popup multi-login (sesi ganda) yang bisa muncul saat login ulang.

### Fase 4 - Maintainability

Target: membuat project gampang dirawat dalam jangka panjang.

1. Pisahkan UI dari business logic secara tegas.
2. Tambahkan type hints dan linting ringan.
3. Dokumentasikan flow tiap job: input, output, dependensi, dan tabel target.
4. Buat checklist operasi harian untuk operator.

## Prioritas Eksekusi

Urutan yang paling aman:

1. Security cleanup
2. Config/state separation
3. Shared runner dan helper
4. SQL/parsing consolidation
5. Testing dan docs

## Catatan Risiko

- Repo ini sangat bergantung pada SAP GUI scripting dan Windows COM, jadi refactor harus tetap mempertahankan kompatibilitas Windows.
- Banyak path masih absolut dan spesifik laptop, jadi perlu dijadikan parameter atau environment-driven.
- Ada beberapa file legacy / eksport otomatis yang kemungkinan sudah tidak dipakai lagi, tapi sebelum dihapus harus dipastikan tidak dipanggil dari workflow lama.
