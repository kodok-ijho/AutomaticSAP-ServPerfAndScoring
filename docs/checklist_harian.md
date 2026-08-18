# 📋 Checklist Operasional Operator — SAP Automation

Gunakan lembar checklist ini setiap kali menjalankan proses penarikan data harian maupun penutupan (closing) bulanan untuk memastikan tidak ada tahapan data yang terlewat.

---

## 📅 1. Persiapan Awal Sebelum Eksekusi

- [ ] **Koneksi Jaringan**: Pastikan kabel LAN terpasang atau VPN kantor aktif.
- [ ] **Akses Database**: Pastikan server database `172.31.151.88` dapat diakses (klik tombol **Test DB** di Dashboard).
- [ ] **SAP Logon**: Buka aplikasi SAP Logon dan pastikan user sudah login.
- [ ] **Test SAP**: Klik tombol **Test SAP** di Dashboard — pastikan status menunjukkan `Session aktif & sudah login. Scripting OK.`
- [ ] **Tabel Closing**: Pastikan tabel `Tb_R_PeriodeClosing` di database sudah memiliki baris tanggal untuk periode yang akan diproses.

---

## 🔄 2. Urutan Eksekusi Job (Closing Bulanan)

| Check | Urutan | Nama Job | Status Harapan | Tindakan Operator |
|:---:|:---:|:---|:---|:---|
| [ ] | **Langkah 1** | **CREATE BG JOB ZSMR007B** | `SUCCESS` | Pastikan offset peralatan tersalin ke clipboard dan terdaftar di SAP SM37. |
| [ ] | **Langkah 2** | *Tunggu Background Job SAP* | Selesai di SM37 | Cek transaksi `SM37` di SAP sampai status job menjadi `Finished`. |
| [ ] | **Langkah 3** | **DOWNLOAD BG JOB ZSMR007B** | `SUCCESS` | Pastikan file `*1.txt` dan `*2.txt` terunduh di folder tujuan dan ukuran > 0 KB. |
| [ ] | **Langkah 4** | **MERAPIHKAN HASIL ZSMR007B** | `SUCCESS` | Pastikan opsi *Insert ke SQL* bernilai `True`. Verifikasi baris ter-insert ke tabel `ZSMR007B`. |
| [ ] | **Langkah 5** | **DOWNLOAD LAPORAN KE30 (Divisi)** | `SUCCESS` | Pastikan seluruh file `.dat` tiap divisi terunduh ke folder target. |
| [ ] | **Langkah 6** | **PERAPIHAN KE30 (Divisi)** | `SUCCESS` | Pastikan opsi *Insert ke SQL* bernilai `True`. File `Combined_KE30_*.xlsx` berhasil dibuat. |
| [ ] | **Langkah 7** | **DOWNLOAD LAPORAN KE30 (Eq)** | `SUCCESS` | Pastikan file `.dat` rincian equipment terunduh. |
| [ ] | **Langkah 8** | **PERAPIHAN KE30 (Eq)** | `SUCCESS` | Pastikan opsi *Insert ke SQL* bernilai `True`. Data terupload ke tabel `KE30_ByEq`. |
| [ ] | **Langkah 9** | **ZSME09E AUTOMATION** | `SUCCESS` | Pastikan data pergerakan material terupload ke tabel `ZSME09E`. |
| [ ] | **Langkah 10** | **DOWNLOAD LAPORAN ZSMR019** | `SUCCESS` | Pastikan opsi *Insert ke SQL* bernilai `True`. File `ZSMR019 - *.txt` terupload ke tabel `ZSMR019`. |

---

## 🔍 3. Verifikasi Akhir di Database SQL Server

Jalankan kueri SQL berikut di SQL Server Management Studio (SSMS) atau DBeaver untuk memverifikasi kelengkapan data periode yang baru saja diproses:

```sql
DECLARE @TargetPeriode DATE = '2026-06-01';

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

*Jika semua tabel menghasilkan `TotalBaris > 0`, maka proses closing telah berhasil 100%.*
