# Perbaikan Penjagaan Duplikasi Data ZSMR012 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Memperbaiki sistem pencegahan dan penjagaan duplikasi pada pipeline otomatisasi ZSMR012 baik pada level in-memory parsing, query SQL Server UPSERT, konfigurasi sequence runner, maupun validasi integritas database.

**Architecture:** Mengganti kunci deduplikasi lama yang mengandalkan `ConfirmationCounter` (yang tidak tersedia pada spool SAP standar) dengan composite key riil: `[Order] + [ActivityType] + [ExecutionStart] + [ActualStart]`. Memperbaiki query penghapusan data lama sebelum insert agar mendukung pencocokan waktu fleksibel (DATE vs TIME) dan mengecualikan baris `%-OFF%`. Memperbaiki konfigurasi sequence harian agar tidak terjadi double-upload pada folder yang sama.

**Tech Stack:** Python 3.10+, pyodbc, Microsoft SQL Server, Windows Task Scheduler / Custom Sequence Runner.

**Spec:** Analisis temuan audit ZSMR012: kegagalan matching `#TempZSMRKeys` karena ketiadaan kolom ConfirmationCounter di spool SAP, typo klausul `Location` vs `Portfolio`, dan eksekusi ganda Step 3 & Step 4 di `zsmr012_daily_15days.json`.

## Global Constraints

- Struktur skema tabel `dbo.ZSMR012` dan daftar kolom `ZSMR012_DB_COLUMNS` tidak boleh diubah urutannya agar kompatibel dengan view `vw_ZMSR012WKTIME` dan stored procedure existing.
- Script harus tetap menangani variasi format waktu `ActualStart` (apakah tersimpan dengan base `1900-01-01` atau `YYYY-MM-DD` aktual).
- Operasi batch SQL wajib menggunakan `fast_executemany = True` dan penanganan chunking yang aman untuk dataset besar (> 10.000 baris).

## Review Focus

1. **Kasus Spool Tanpa ConfirmationCounter**: File spool SAP standar hanya memiliki 16 kolom; pastikan proses deduplikasi in-memory dan database tidak bergantung pada kolom ini.
2. **Kesesuaian Format Waktu ActualStart**: Perbedaan penyimpanan tanggal pada `ActualStart` (1900-01-01 vs hari transaksi) harus dicocokkan dengan benar menggunakan casting waktu (`CAST(ActualStart AS TIME)`).
3. **Double Step Execution**: Pastikan `zsmr012_daily_15days.json` tidak meng-upload 2 kali pada file yang sama.
4. **Penanganan WorkCenter `%-OFF%`**: Pastikan baris duplikat batch offline dari SAP disaring sebelum masuk ke database.
5. **Idempotensi**: Menjalankan proses ulang berkali-kali pada hari dan data yang sama tidak boleh menambah jumlah baris di database.

---

### Task 1: Refactor Logika Deduplikasi & UPSERT di `process_zsmr012.py`

**Files:**
- Modify: `process_zsmr012.py`
- Test: `test_smoke.py`

**Deskripsi:**
1. Perbarui logika pembersihan baris in-memory di `parse_zsmr012_file` agar menyaring baris `WorkCenter LIKE '%-OFF%'`.
2. Perbarui composite key deduplikasi in-memory dan database:
   Kunci unik transaksi adalah `(Order, ActivityType, ExecutionStart, ActualStart_Time)`.
3. Perbarui pembuatan tabel sementara `#TempZSMRKeys` dan query `DELETE Z` di `process_and_upload_zsmr012`:
   - Simpan `Order`, `ActivityType`, `ExecutionStart`, dan string waktu `ActualStart`.
   - Lakukan penghapusan baris yang bertabrakan di `dbo.ZSMR012` sebelum `insert_batch`.
4. Perbaiki klausul delete periode agar membersihkan rentang tanggal eksekusi aktual (`min_date` s/d `max_date` yang ada dalam batch data), bukan hanya 1 tanggal hari ini saja.

- [ ] 1. Buka `process_zsmr012.py` dan tambahkan filter eksklusi `WorkCenter` berakhiran `-OFF` pada parsing baris.
- [ ] 2. Ubah `seen_zsmr` set in-memory deduplication menjadi:
  `key = (r["Order"], r.get("ActivityType"), r.get("ExecutionStart"), str(r.get("ActualStart"))[-8:] if r.get("ActualStart") else "")`.
- [ ] 3. Ubah skema `#TempZSMRKeys` menjadi:
  `CREATE TABLE #TempZSMRKeys ([Order] NVARCHAR(10), [ActivityType] NVARCHAR(255), [ExecutionStart] DATETIME, [ActualStartTime] VARCHAR(8));`
- [ ] 4. Masukkan kunci unik gabungan ke `#TempZSMRKeys` dan jalankan query `DELETE Z` dengan pencocokan:
  `Z.[Order] = T.[Order] AND Z.[ActivityType] = T.[ActivityType] AND Z.[ExecutionStart] = T.[ExecutionStart] AND CONVERT(VARCHAR(8), Z.[ActualStart], 108) = T.[ActualStartTime]`.
- [ ] 5. Hitung `min_exec` dan `max_exec` dari batch data untuk memastikan penghapusan data periode tidak hanya menghapus 1 tanggal saja jika parameter periode tidak dispesifikasikan.
- [ ] 6. Jalankan syntax check dan smoke test.

---

### Task 2: Koreksi Alur Sequence di `custom_sequences/zsmr012_daily_15days.json`

**Files:**
- Modify: `custom_sequences/zsmr012_daily_15days.json`

**Deskripsi:**
Pada sequence saat ini:
- Step 3 mendownload spool dengan `"insert-sql": "True"`.
- Step 4 memanggil `process_zsmr012.py` pada folder yang sama dengan `"periode": "2026-10-01"`.
Hal ini menyebabkan proses upload berjalan 2 kali berturut-turut pada batch file yang sama. Kita pisahkan tanggung jawab secara modular:
- Step 3 fokus download spool: ubah `"insert-sql": "False"`.
- Step 4 fokus merapikan & upload data: gunakan `"periode": "dynamic-today-ymd"`.

- [ ] 1. Buka `custom_sequences/zsmr012_daily_15days.json`.
- [ ] 2. Ubah parameter `insert-sql` pada Step 3 (`DOWNLOAD BG JOB ZSMR012`) menjadi `"False"`.
- [ ] 3. Ubah parameter `periode` pada Step 4 (`MERAPIHKAN HASIL DOWNLOAD – ZSMR012`) dari hardcoded `"2026-10-01"` menjadi `"dynamic-today-ymd"`.
- [ ] 4. Verifikasi pembacaan sequence menggunakan `python custom_sequence_runner.py --help` atau uji muat JSON.

---

### Task 3: Tambahkan Unit Test Deduplikasi di `test_smoke.py`

**Files:**
- Modify: `test_smoke.py`

**Deskripsi:**
Tambahkan skenario pengujian unit test untuk memvalidasi:
1. Deduplikasi in-memory mengenali duplikasi composite key `(Order, ActivityType, ExecutionStart, ActualStart)`.
2. Penyaringan baris dengan `WorkCenter` mengandung `-OFF`.
3. Konsistensi penanganan jika `ConfirmationCounter` bernilai `None`.

- [ ] 1. Buka `test_smoke.py` pada class `TestProcessZSMR012`.
- [ ] 2. Tambahkan test case `test_deduplication_composite_key`:
  Simulasikan 4 baris data tiruan (2 unik, 2 duplikat identik order + acttyp + execstart + actualstart) dan pastikan hasil dedup menghasilkan 2 baris.
- [ ] 3. Tambahkan test case `test_filter_off_workcenter`:
  Simulasikan baris dengan WorkCenter `TDE-CUTI-OFF` dan pastikan disaring / diabaikan.
- [ ] 4. Jalankan `python test_smoke.py` dan pastikan seluruh test PASSED.

---

### Task 4: Script Pembersihan Data Duplikat Existing di Database

**Files:**
- Create: `scripts/cleanup_zsmr012_duplicates.py`

**Deskripsi:**
Menyediakan skrip mandiri untuk membersihkan 3.739 duplikat existing di `dbo.ZSMR012` menggunakan pola `ROW_NUMBER() OVER (PARTITION BY [Order], [ActivityType], [ExecutionStart], CONVERT(VARCHAR(8), [ActualStart], 108) ORDER BY CASE WHEN ConfirmationCounter IS NOT NULL THEN 0 ELSE 1 END, ConfirmationCounter, EnteredOn DESC)`. Skrip ini dilengkapi dry-run mode dan batch delete 5.000 baris per iterasi.

- [ ] 1. Buat file `scripts/cleanup_zsmr012_duplicates.py`.
- [ ] 2. Implementasikan kalkulasi jumlah duplikat (Pre-count).
- [ ] 3. Implementasikan penghapusan batch dengan CTE dan limit 5.000 baris per commit.
- [ ] 4. Uji eksekusi skrip dalam mode `--dry-run` untuk melihat jumlah duplikat yang akan dibersihkan tanpa melakukan commit.
