# 📋 Checklist Operasional Operator — SAP Automation

Gunakan lembar checklist ini setiap kali menjalankan proses penarikan data harian maupun penutupan (closing) bulanan untuk memastikan seluruh tahapan berjalan sukses.

---

## 📅 1. Persiapan Awal Sebelum Eksekusi

- [ ] **Koneksi Jaringan**: Pastikan kabel LAN terpasang atau VPN kantor aktif.
- [ ] **Akses Database**: Pastikan server database `172.31.151.88` dapat diakses (klik tombol **Test DB** di Dashboard).
- [ ] **SAP Logon**: Buka aplikasi SAP Logon dan pastikan user sudah login.
- [ ] **Test SAP**: Klik tombol **Test SAP** di Dashboard — pastikan status menunjukkan `Session aktif & sudah login. Scripting OK.`
- [ ] **Tabel Closing**: Pastikan tabel `Tb_R_PeriodeClosing` di database sudah memiliki baris tanggal untuk periode yang akan diproses.
- [ ] **Inspeksi Variabel**: Lakukan dry-run / inspeksi path folder (`python daily_orchestrator.py --dry-run`).

---

## 🚀 2. Metode Eksekusi yang Tersedia

### Opsi A: Eksekusi 1-Click Otomatisasi Harian Terpadu (Direkomendasikan)
Cukup jalankan job **`DAILY AUTOMATION PIPELINE – Full 6 Stages`** di Dashboard (atau via `run_daily.bat`). Sistem akan otomatis menjalankan 6 tahapan secara berurutan:

| Check | Tahap | Deskripsi Tahapan | Status Target |
|:---:|:---:|:---|:---|
| [ ] | **Tahap 1** | **CREATE BG JOB ZSMR007B** (Batch 1.000 Equipment) | `[OK] SUKSES` |
| [ ] | **Tahap 2** | **DOWNLOAD & UPSERT ZSMR007B** (Merge `*1` & `*2` ➔ Tb `ZSMR007B`) | `[OK] SUKSES` |
| [ ] | **Tahap 3** | **DOWNLOAD & UPSERT KE30 DIVISI** (Excel COM ➔ Tb `KE30`) | `[OK] SUKSES` |
| [ ] | **Tahap 4** | **DOWNLOAD & UPSERT KE30 EQUIPMENT** (Parse Eq ➔ Tb `KE30_ByEq`) | `[OK] SUKSES` |
| [ ] | **Tahap 5** | **DOWNLOAD & UPSERT ZSME09E** (Material Movement ➔ Tb `ZSME09E`) | `[OK] SUKSES` |
| [ ] | **Tahap 6** | **DOWNLOAD & UPSERT ZSMR019** (Service Order ➔ Tb `ZSMR019`) | `[OK] SUKSES` |

---

### Opsi B: Eksekusi Manual Bertahap (Step-by-Step)
Jika hanya ingin menjalankan atau mengulang tahapan tertentu secara terpisah:
1. `rpa_sap_1.py` (Create BG Job ZSMR007B)
2. `download_zsmr007b.py` ➔ `process_reports.py` (Download & Upsert ZSMR007B)
3. `download_ke30.py` ➔ `ProsesKE30byDiv.py` (Download & Upsert KE30 Divisi)
4. `download_ke30_eq.py` ➔ `ProcessKE30byEq.py` (Download & Upsert KE30 Equipment)
5. `automate_zsme09e.py` (Download & Upsert ZSME09E)
6. `download_zsmr019.py` (Download & Upsert ZSMR019)

---

## 🔍 3. Verifikasi Akhir di Database SQL Server

Jalankan kueri SQL berikut di SQL Server Management Studio (SSMS) atau DBeaver untuk memverifikasi kelengkapan data periode yang baru saja diproses:

```sql
DECLARE @TargetPeriode DATE = '2026-08-01';

SELECT 'ZSMR007B' AS Tabel, COUNT(*) AS TotalBaris FROM ZSMR007B WHERE Periode = @TargetPeriode
UNION ALL
SELECT 'KE30' AS Tabel, COUNT(*) AS TotalBaris FROM KE30 WHERE Periode = @TargetPeriode
UNION ALL
SELECT 'KE30_ByEq' AS Tabel, COUNT(*) AS TotalBaris FROM KE30_ByEq WHERE Periode = @TargetPeriode
UNION ALL
SELECT 'ZSME09E' AS Tabel, COUNT(*) AS TotalBaris FROM ZSME09E WHERE Periode = @TargetPeriode
UNION ALL
SELECT 'ZSMR019' AS Tabel, COUNT(*) AS TotalBaris FROM ZSMR019 WHERE Periode = @TargetPeriode;
```

*Jika semua tabel menghasilkan `TotalBaris > 0`, maka proses harian/closing telah berhasil 100%.*
