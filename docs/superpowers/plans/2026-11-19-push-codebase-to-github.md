# Rencana Implementasi: Push Codebase ke GitHub (`AutomaticSAP-ServPerfAndScoring`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Melakukan commit pada perubahan file yang belum ter-stage dan melakukan push seluruh commit terbaru cabang `main` ke repositori GitHub remote `https://github.com/kodok-ijho/AutomaticSAP-ServPerfAndScoring.git` secara aman tanpa mengekspos kredensial atau merusak test suite.

**Architecture:** Memeriksa status repositori dan git diff untuk memastikan tidak ada kredensial/token yang bocor, meng-commit seluruh perbaikan dan fitur baru (termasuk modul ZSMR012 dedup, excel importer, backup range, daily orchestrator update, dan batch runner), menjalankan unit test smoke verifikasi, lalu mengeksekusi `git push origin main`.

**Tech Stack:** Git, GitHub, Python `unittest`.

**Spec:** Permintaan pengguna untuk melakukan push codebase ke GitHub pada remote `https://github.com/kodok-ijho/AutomaticSAP-ServPerfAndScoring.git`.

## Global Constraints

- Remote target: `origin` (`https://github.com/kodok-ijho/AutomaticSAP-ServPerfAndScoring.git`).
- Cabang target: `main`.
- DILARANG commit file rahasia (`.env`, `job_config.json`, file database snapshot/backup, data `.xlsx`/`.txt` mentah). Pastikan `.gitignore` tetap melindungi file-file tersebut.
- Seluruh 78 unit test di `test_smoke.py` harus lulus 100% sebelum maupun sesudah push.

## Review Focus

1. **Pemeriksaan Kredensial**: Memastikan `vbs/LoginSAP.vbs` dan script Python lainnya tidak memuat password hardcoded.
2. **Kerapian Commit History**: Memisahkan atau merapikan commit perubahan pipeline orchestrator & runner dengan pesan commit yang informatif.
3. **Integritas Remote**: Memastikan `git push origin main` selesai dengan status sukses dan zero conflict.
4. **Validasi Status Working Tree**: Memastikan working directory bersih (*clean working tree*) pasca push.

---

### Task 1: Audit Keamanan, Staging Perubahan, & Commit

**Files:**
- Modify: `daily_orchestrator.py`, `dashboard.py`, `download_zsmr012.py`, `job_definitions.py`, `job_runner.py`, `path_resolver.py`, `vbs/LoginSAP.vbs`
- Untracked: `Sequence JOB/ZSMR012 -15 hari.json`, `run_zsmr012_daily.bat`, `docs/superpowers/plans/*.md`

**Deskripsi:**
Memeriksa bahwa tidak ada rahasia/password dalam diff yang belum di-commit, men-stage file yang valid, dan membuat commit yang deskriptif.

- [x] 1. Verifikasi isi diff dan pastikan tidak ada data sensitif yang bocor.
- [x] 2. Stage file perubahan pipeline orchestrator, VBS, runner script, sequence template, dan dokumentasi plan.
- [x] 3. Jalankan unit test `python -m unittest test_smoke.py` untuk memastikan semua pengujian lulus.
- [x] 4. Buat git commit dengan pesan yang jelas (misal: `feat(pipeline): update daily orchestrator, path resolver, and batch runners`).

---

### Task 2: Eksekusi Git Push ke Remote GitHub

**Files:**
- Remote: `origin/main` (`https://github.com/kodok-ijho/AutomaticSAP-ServPerfAndScoring.git`)

**Deskripsi:**
Mendorong (*push*) seluruh commit lokal (termasuk 8 commit fitur ZSMR012 sebelumnya + commit baru) ke remote GitHub.

- [x] 1. Jalankan `git push origin main`.
- [x] 2. Verifikasi output perintah `git push` mengonfirmasi transfer objek berhasil tanpa error.

---

### Task 3: Verifikasi Pasca-Push

**Files:**
- Repository status: `git status`, `git log`

**Deskripsi:**
Memastikan working tree berada dalam kondisi bersih dan HEAD lokal sinkron dengan `origin/main`.

- [x] 1. Jalankan `git status` dan pastikan pesan `Your branch is up to date with 'origin/main'`.
- [x] 2. Periksa `git log -1` untuk memverifikasi commit hash terakhir.
