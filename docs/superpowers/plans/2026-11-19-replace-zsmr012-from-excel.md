# Rencana Implementasi: Penggantian Data ZSMR012 dari File Excel (1 September – 18 November 2026)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Menghapus data transaksi `dbo.ZSMR012` dalam rentang tanggal `ExecutionStart` 1 September 2026 s/d 18 November 2026 di database `DesSy` (dengan backup aman terlebih dahulu ke tabel arsip), kemudian mengimpor seluruh data dari file Excel `"D:\Kerja\2026 CSSD\02. REPORTING 2026\11 NOV 2026 REPORTING\ZSMR012 - 010826-181126.xlsx"` secara akurat, ternormalisasi, dan bebas duplikasi. Data bulan Agustus 2026 dan sebelumnya tetap utuh dan aman di database.

**Architecture:** Membangun utility script mandiri berstandar ETL pipeline (`scripts/import_zsmr012_excel.py` dan `scripts/backup_zsmr012_range.py`) yang membaca file Excel menggunakan `openpyxl` streaming/read-only mode, memetakan 28 kolom Excel ke 30 kolom skema `dbo.ZSMR012`, menormalisasi tipe data jam/tanggal/float, menyaring duplikasi in-memory dan baris `%-OFF%`, melakukan backup data existing (51.257 baris) ke tabel arsip `dbo.ZSMR012_BACKUP_20260901_20261118`, menghapus data periode September–November dalam transaksi aman, dan melakukan batch insert via pyodbc `fast_executemany`.

**Tech Stack:** Python 3.10+, openpyxl, pyodbc, Microsoft SQL Server (DesSy database).

**Spec:** Kesepakatan dengan pengguna bahwa pembersihan dan penggantian data difokuskan khusus pada periode September s/d 18 November 2026 (`2026-09-01` s/d `2026-11-18`), menyesuaikan isi data aktual di file Excel `ZSMR012 - 010826-181126.xlsx`.

## Global Constraints

- **Tabel Skema DB**: Kolom wajib mengikuti urutan `ZSMR012_DB_COLUMNS` (30 kolom) tanpa modifikasi urutan agar kompatibel dengan view `vw_ZMSR012WKTIME` dan stored procedure existing.
- **Wajib Backup**: Data yang akan dihapus di database (51.257 baris periode 1 September–18 November 2026) wajib di-backup ke tabel backup permanen `dbo.ZSMR012_BACKUP_20260901_20261118` sebelum query delete dieksekusi.
- **Keutuhan Data Agustus**: Data transaksi dengan `ExecutionStart < '2026-09-01'` (termasuk 23.138 baris bulan Agustus 2026) TIDAK BOLEH disentuh atau terhapus.
- **Format Jam SQL Server**: Kolom `ActualStart`, `FinishExecution`, dan `Time` yang bertipe `datetime.time` dari Excel harus dikonversi ke format SQL Server standar base `1900-01-01 HH:mm:ss` agar konsisten dengan `parse_sap_time`.
- **Dua Kolom Confirmati**: Di file Excel terdapat 2 kolom bernama `Confirmati`. Kolom ke-1 (index 16) dipetakan ke `ConfirmationCounter`, sedangkan kolom ke-2 (index 18) dipetakan ke `ConfirmationCounterOfCanceled`.

## Review Focus

1. **Rentang Tanggal Delete Eksak**: Memastikan query delete membatasi hanya pada `[ExecutionStart] >= '2026-09-01' AND [ExecutionStart] < '2026-11-19'` sehingga data Agustus tidak ikut terhapus.
2. **Mapping 28 Kolom Excel ke 30 Kolom DB**: Pastikan seluruh kolom (termasuk MatnrEQ, MatEQGrp, PlannerGrp, Portfolio, DetailPort, SalesType, Location, Family) terisi dengan benar tanpa tergeser.
3. **Pembersihan String (Whitespace Strip)**: SAP Excel export sering kali memiliki trailing spaces (misal `'4108004 '`, `'I1      '`). Wajib dilakukan `strip()` pada seluruh field string.
4. **Penyaringan WorkCenter `%-OFF%`**: Memfilter 1.998 baris batch offline dari SAP sebelum masuk ke database.
5. **Deduplikasi In-Memory**: Mengeliminasi baris duplikat internal pada Excel menggunakan composite key `(Order, ActivityType, ExecutionStart, ActualStart_Time)`.
6. **Keamanan Transaksi**: Operasi DELETE dan INSERT dijalankan dalam satu sesi koneksi dengan mekanisme `commit()` dan `rollback()` jika terjadi kendala.

---

### Task 1: Script Backup Data Periode Target (`scripts/backup_zsmr012_range.py`)

**Files:**
- Create: `scripts/backup_zsmr012_range.py`

**Deskripsi:**
Menyediakan utilitas mandiri untuk mencadangkan (backup) seluruh record di `dbo.ZSMR012` rentang 1 September 2026 s/d 18 November 2026 ke tabel arsip `dbo.ZSMR012_BACKUP_20260901_20261118`.
Tabel backup ini menjadi *safety net* permanen jika sewaktu-waktu pengguna memerlukan kembali data lama tersebut.

- [ ] 1. Buat file `scripts/backup_zsmr012_range.py`.
- [ ] 2. Parameterkan rentang tanggal: `--start-date` (default: `2026-09-01`) dan `--end-date` (default: `2026-11-18`).
- [ ] 3. Periksa apakah tabel `dbo.ZSMR012_BACKUP_20260901_20261118` sudah ada:
  - Jika belum ada: Jalankan `SELECT * INTO dbo.ZSMR012_BACKUP_20260901_20261118 FROM dbo.ZSMR012 WHERE [ExecutionStart] >= ? AND [ExecutionStart] < ?`.
  - Jika sudah ada: Berikan opsi `--overwrite` untuk menimpa atau beri info tabel sudah tersedia.
- [ ] 4. Verifikasi jumlah baris yang berhasil dicadangkan (harus sama dengan `SELECT COUNT(*)` data rentang 1 Sept–18 Nov di `dbo.ZSMR012`, yaitu 51.257 baris).
- [ ] 5. Uji jalankan script backup.

---

### Task 2: Script Importer & ETL Excel ZSMR012 (`scripts/import_zsmr012_excel.py`)

**Files:**
- Create: `scripts/import_zsmr012_excel.py`

**Deskripsi:**
Membangun engine ETL untuk membaca file Excel 9.28 MB secara efisien menggunakan `openpyxl.load_workbook(..., read_only=True)`, melakukan normalisasi dan validasi data, lalu mengeksekusi operasi penggantian data di database:
1. Parsing dan pembersihan 28 kolom Excel.
2. Konversi format waktu Excel `datetime.time` -> `datetime(1900, 1, 1, h, m, s)`.
3. Filter WorkCenter berakhiran `-OFF` (default: exclude).
4. Deduplikasi internal batch berbasis composite key `(Order, ActivityType, ExecutionStart, ActualStartTime)`.
5. Menghapus data lama di database khusus rentang tanggal 1 September s/d 18 November 2026 (`[ExecutionStart] >= '2026-09-01' AND [ExecutionStart] < '2026-11-19'`).
6. Batch insert data baru ke `dbo.ZSMR012` menggunakan `insert_batch` pyodbc dengan `fast_executemany = True` (chunk size 2.000).

- [ ] 1. Buat file `scripts/import_zsmr012_excel.py` dengan CLI arguments:
  - `--excel-path`: Default `"D:\Kerja\2026 CSSD\02. REPORTING 2026\11 NOV 2026 REPORTING\ZSMR012 - 010826-181126.xlsx"`
  - `--delete-start`: Tanggal awal hapus (default: `2026-09-01`)
  - `--delete-end`: Tanggal akhir hapus (default: `2026-11-18`)
  - `--exclude-off`: Filter baris `%-OFF%` (default: `True`)
  - `--batch-size`: Ukuran batch pyodbc (default: `2000`)
  - `--dry-run`: Mode simulasi tanpa delete/insert (default jika `--execute` tidak diberikan)
  - `--execute`: Flag konfirmasi eksekusi riil
- [ ] 2. Implementasikan fungsi `parse_excel_zsmr012(excel_path, exclude_off=True)`:
  - Buka workbook read-only streaming.
  - Baca baris header dan petakan indeks kolom secara dinamis.
  - Tangani 2 kolom `Confirmati` (index 16 -> `ConfirmationCounter`, index 18 -> `ConfirmationCounterOfCanceled`).
  - Strip seluruh field string, handle `None` / empty values.
  - Konversi kolom jam (`Act. start`, `Act. Fin.`, `Time`) ke base `1900-01-01`.
  - Set `FileName = 'ZSMR012'`, `DatePeriode = ExecutionStart.date()`, `proses = False`.
- [ ] 3. Implementasikan in-memory deduplication `(Order, ActivityType, ExecutionStart, ActualStartTime)`.
- [ ] 4. Implementasikan fungsi `replace_zsmr012_data(...)`:
  - Sambungkan koneksi ke database `DesSy` via `get_connection_with_retry`.
  - Jika `--dry-run`: tampilkan jumlah data yang akan dihapus di DB (51.257 baris) dan jumlah data yang siap diinsert dari Excel (~58.052 baris unik non-OFF), lalu keluar tanpa memodifikasi DB.
  - Jika `--execute`:
    - Jalankan `DELETE FROM dbo.ZSMR012 WHERE [ExecutionStart] >= ? AND [ExecutionStart] < ?`.
    - Jalankan batch insert via `insert_batch`.
    - Lakukan `conn.commit()`.
- [ ] 5. Tampilkan ringkasan eksekusi: total dihapus, total dimasukkan, verifikasi post-count di database.

---

### Task 3: Unit Test & Validasi Parser Excel di `test_smoke.py`

**Files:**
- Modify: `test_smoke.py`

**Deskripsi:**
Menambahkan skenario unit test untuk menguji fungsi parsing dan mapping kolom Excel `parse_excel_zsmr012` agar terbukti akurat dan tidak terjadi salah geser kolom atau gagal konversi waktu.

- [ ] 1. Buka `test_smoke.py` dan buat kelas baru `TestImportZSMR012Excel`.
- [ ] 2. Tambahkan test case `test_excel_column_mapping`:
  Buat file Excel mini sementara dengan 28 kolom dan 2 baris data sampel, panggil parser, lalu verifikasi:
  - 30 field database terpetakan lengkap (`len(row) == 30`).
  - `ConfirmationCounter` terisi dari kolom Confirmati pertama.
  - `ConfirmationCounterOfCanceled` terisi dari kolom Confirmati kedua.
  - `WorkCenter` dengan `-OFF` disaring jika `exclude_off=True`.
  - `ActualStart` bertipe `datetime` dengan tahun `1900`.
- [ ] 3. Bersihkan file Excel mini sementara.
- [ ] 4. Jalankan `python test_smoke.py` dan pastikan seluruh test suite lolos.

---

### Task 4: Eksekusi Pre-Flight & Verifikasi Dry-Run

**Files:**
- Test / Run: `scripts/backup_zsmr012_range.py` dan `scripts/import_zsmr012_excel.py`

**Deskripsi:**
Menjalankan pengujian pre-flight terhadap file Excel riil di drive D: dan database `DesSy` dalam mode aman (`--dry-run`), mencocokkan jumlah record, dan memastikan tidak ada error koneksi atau tipe data sebelum eksekusi final.

- [ ] 1. Jalankan `python scripts/import_zsmr012_excel.py --dry-run`.
- [ ] 2. Periksa output log:
  - Total baris yang dibaca dari Excel: 60.055 baris.
  - Baris `-OFF` yang difilter: 1.998 baris.
  - Baris duplikat in-memory yang disaring: 5 baris.
  - Data bersih siap di-insert: 58.052 baris.
  - Data existing yang akan dihapus di database: 51.257 baris (September s/d 18 November 2026).
  - Data Agustus 2026 di database: 23.138 baris (tetap aman, 0 terhapus).
- [ ] 3. Dokumentasikan petunjuk eksekusi akhir untuk pengguna.
