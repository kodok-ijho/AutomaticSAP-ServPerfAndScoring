# Rencana Implementasi: Pembuatan Skill Otomatisasi `upsert-zsmr012`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Membuat agent skill baru bernama `upsert-zsmr012` di direktori skill runtime (`C:\Users\dhaniy\.gemini\config\skills\upsert-zsmr012\SKILL.md`) agar asisten AI dapat melakukan operasi insert/upsert/replace data ZSMR012 secara instan, aman, dan presisi, baik bersumber dari file Excel (`.xlsx`), file spool teks SAP (`.txt`), maupun background job otomatis SM37.

**Architecture:** Skill dirancang sebagai panduan operasional teknis komprehensif (*standard operating procedure / runbook*) yang merangkum:
1. Pemicu kata kunci (*trigger phrases*) yang mengenali perintah user secara otomatis.
2. Decision tree pemilihan engine (Excel vs Text Spool vs SAP GUI SM37).
3. SOP keamanan data (Wajib Backup snapshot ke tabel arsip & validasi rentang tanggal riil isi file sebelum delete).
4. Kunci deduplikasi baku `[Order] + [ActivityType] + [ExecutionStart] + [ActualStart]` dan filter `WorkCenter %-OFF%`.
5. Command cheatsheet siap pakai (`--dry-run` dan `--execute`).

**Tech Stack:** Antigravity Skill System (Markdown + YAML Frontmatter), Python CLI utilities (`import_zsmr012_excel.py`, `backup_zsmr012_range.py`, `process_zsmr012.py`), SQL Server pyodbc.

**Spec:** Permintaan pengguna untuk menjadikan proses upsert ZSMR012 sebagai skill permanen agar siap dieksekusi secara cepat dan konsisten di masa mendatang.

## Global Constraints

- File skill harus disimpan di lokasi global runtime: `C:\Users\dhaniy\.gemini\config\skills\upsert-zsmr012\SKILL.md`.
- YAML Frontmatter wajib memiliki `name: upsert-zsmr012` dan `description` yang mendeskripsikan secara lengkap kondisi pemicu (*triggering conditions*) dimulai dengan *"Gunakan ketika..."* atau *"Aktifkan ketika user..."*.
- Format penulisan mengikuti standar skill Astra Graphia yang sudah ada (`kapasitas-cabang-mpg`, `kapasitas-cabang-semarang`).
- Seluruh absolute path ke script eksekusi di `D:\Kerja\Application AG\SAP AUTOMATION\` harus tertulis secara presisi.

## Review Focus

1. **Kelengkapan Trigger Phrases**: Memastikan kata kunci seperti `upsert zsmr012`, `insert zsmr012`, `import excel zsmr012`, `ganti data zsmr012`, `replace zsmr012` memicu aktivasi skill ini secara mulus.
2. **Kejelasan Runbook Multi-Format**: Panduan harus membedakan dengan jelas kapan memakai `import_zsmr012_excel.py` (untuk Excel) vs `process_zsmr012.py` (untuk file spool text).
3. **Guardrail Validasi Rentang Tanggal**: Wajib mencantumkan aturan baku untuk selalu menginspeksi tanggal riil isi file sebelum menjalankan query delete agar tidak terjadi kasus kehilangan data (seperti kasus file 010826 yang isinya hanya dari bulan September).
4. **SOP Snapshot Backup**: Wajib mencantumkan langkah backup snapshot ke tabel `dbo.ZSMR012_BACKUP_<start>_<end>` sebelum eksekusi delete riil.

---

### Task 1: Buat Direktori & Kerangka File `SKILL.md`

**Files:**
- Create: `C:\Users\dhaniy\.gemini\config\skills\upsert-zsmr012\SKILL.md`

**Deskripsi:**
Membuat direktori `upsert-zsmr012` dan file `SKILL.md` dengan metadata YAML frontmatter yang valid, nama skill baku, dan deskripsi pemicu yang komprehensif.

- [x] 1. Buat direktori `C:\Users\dhaniy\.gemini\config\skills\upsert-zsmr012\`.
- [x] 2. Tulis file `SKILL.md` dengan YAML frontmatter:
  - `name`: `upsert-zsmr012`
  - `description`: Panduan baku proses import, upsert, dan penggantian data transaksi ZSMR012 ke database DesSy SQL Server... (lengkap dengan kata kunci pemicu).
- [x] 3. Verifikasi file berhasil dibuat dan dapat dibaca.

---

### Task 2: Susun Panduan Operasional Lengkap (SOP & Runbook) di `SKILL.md`

**Files:**
- Modify: `C:\Users\dhaniy\.gemini\config\skills\upsert-zsmr012\SKILL.md`

**Deskripsi:**
Menuliskan konten standar operasional terstruktur di dalam `SKILL.md`:
1. **Bagian 1: Kata Kunci Pemicu (Trigger Phrases)**.
2. **Bagian 2: 3 Jalur Ingest Data ZSMR012**:
   - Jalur A: File Excel (`.xlsx`) via `scripts/import_zsmr012_excel.py`.
   - Jalur B: File Spool Teks SAP (`.txt`) via `process_zsmr012.py`.
   - Jalur C: Background Job SAP SM37 via `custom_sequences/zsmr012_daily_15days.json`.
3. **Bagian 3: 4 Aturan Emas Keselamatan Data (Golden Guardrails)**:
   - Rule 1: Wajib Backup Snapshot (`scripts/backup_zsmr012_range.py`).
   - Rule 2: Wajib Cek Tanggal Riil Isi File (Inspeksi min/max tanggal, jangan percaya nama file).
   - Rule 3: Composite Key Transaksi (`Order + ActivityType + ExecutionStart + ActualStart HH:mm:ss`).
   - Rule 4: Eksklusi Otomatis WorkCenter Batch Offline `%-OFF%`.
4. **Bagian 4: Cheatsheet Perintah CLI Siap Pakai**:
   - Sintaks Dry-Run (Simulasi).
   - Sintaks Live Execution (Eksekusi Nyata).
   - Sintaks Rollback Darurat (Memulihkan dari tabel backup).
5. **Bagian 5: Kamus Skema Kolom `dbo.ZSMR012` (30 Kolom Baku)**.

- [x] 1. Tuliskan seluruh seksi konten di `SKILL.md`.
- [x] 2. Pastikan seluruh path skrip dan tabel database akurat dan dapat di-copy-paste langsung oleh agent.

---

### Task 3: Verifikasi & Uji Kompatibilitas Skill

**Files:**
- Read / Inspect: `C:\Users\dhaniy\.gemini\config\skills\upsert-zsmr012\SKILL.md`

**Deskripsi:**
Memverifikasi bahwa file skill mematuhi format standar Antigravity, YAML frontmatter terbaca dengan baik, dan tidak ada path atau sintaks SQL yang patah/salah.

- [x] 1. Periksa validitas YAML frontmatter dan struktur Markdown.
- [x] 2. Uji coba pembacaan dokumen oleh sistem.
- [x] 3. Dokumentasikan ringkasan skill untuk pengguna.
