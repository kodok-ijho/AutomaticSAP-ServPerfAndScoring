# 📋 Spesifikasi Lengkap Modul & Job Otomatisasi

Dokumen ini berisi rincian teknis, parameter, input, output, dan perintah CLI untuk setiap job otomatisasi di dalam sistem **AutomaticSAP-ServPerfAndScoring**.

---

## 🗂️ Daftar Job & Script Reference

| No | Nama Job | File Script | Input | Output | Target Database |
|:---|:---|:---|:---|:---|:---|
| 1 | **CREATE BG JOB ZSMR007B** | `rpa_sap_1.py` | `Tb_R_SerPervEq` | Clipboard ➔ SAP BG Job | Server SAP |
| 2 | **DOWNLOAD BG JOB ZSMR007B** | `download_zsmr007b.py` | Spool SAP | `*1.txt`, `*2.txt` | File Lokal |
| 3 | **MERAPIHKAN HASIL DOWNLOAD ZSMR007B** | `process_reports.py` | `*1.txt`, `*2.txt` | `.xlsx`, `.txt` | Tabel `ZSMR007B` |
| 4 | **DOWNLOAD LAPORAN KE30 (Divisi)** | `download_ke30.py` | SAP GUI KE30 | `.dat` per divisi | File Lokal |
| 5 | **PERAPIHAN LAPORAN KE30 (Divisi)** | `ProsesKE30byDiv.py` | `.dat` per divisi | `Combined_KE30_*.xlsx` | Tabel `KE30` |
| 6 | **DOWNLOAD LAPORAN KE30 (Equipment)**| `download_ke30_eq.py` | SAP GUI KE30 | `.dat` per equipment | File Lokal |
| 7 | **PERAPIHAN LAPORAN KE30 (Equipment)**| `ProcessKE30byEq.py` | `.dat` per equipment | `Combined_KE30_ByEq_*.txt` | Tabel `KE30_ByEq` |
| 8 | **ZSME09E AUTOMATION** | `automate_zsme09e.py` | SAP GUI ZSME09E | `ZSME09E_Data_*.txt` | Tabel `ZSME09E` |
| 9 | **DOWNLOAD LAPORAN ZSMR019** | `download_zsmr019.py` | SAP GUI ZSMR019 | `ZSMR019 - *.txt` | Tabel `ZSMR019` |

---

## 💻 Panduan Perintah Baris Perintah (CLI Execution)

Setiap script dapat dijalankan secara langsung melalui command line interface (CLI) tanpa antarmuka GUI:

### 1. CREATE BG JOB ZSMR007B
```powershell
python rpa_sap_1.py --periode 2026-06-01 --max-offset 1000 --batch-size 500 --delay 10 --vbs-path "vbs\CreateBG007B-Scheduled.vbs" --sched-start-time "18:00"
```

### 2. DOWNLOAD BG JOB ZSMR007B
```powershell
python download_zsmr007b.py --tanggal "30.06.2026" --periode "2026-06-01" --vbs-path "vbs\DownloadBGJob007B.vbs" --save-path "D:\Kerja\SS\"
```

### 3. MERAPIHKAN HASIL DOWNLOAD ZSMR007B
```powershell
python process_reports.py --folder "D:\Kerja\SS\" --periode "2026-06-01" --insert-sql True
```

### 4. DOWNLOAD LAPORAN KE30 – By Divisi
```powershell
python download_ke30.py --periode "2026-06-01" --vbs-path "vbs\KE30 Get CMNWDN by Div.vbs" --save-path "D:\Kerja\2026 CSSD\03. KE30\KE30 - 06 JUN 26\AUTO\BY DIV\"
```

### 5. PERAPIHAN LAPORAN KE30 – By Divisi
```powershell
python ProsesKE30byDiv.py --folder "D:\Kerja\2026 CSSD\03. KE30\KE30 - 06 JUN 26\AUTO\BY DIV\" --periode "2026-06-01" --insert-sql True
```

### 6. DOWNLOAD LAPORAN KE30 – By Eq
```powershell
python download_ke30_eq.py --periode "2026-06-01" --vbs-path "vbs\KE30 Get CMNWDN by Eq.vbs" --save-path "D:\Kerja\2026 CSSD\03. KE30\KE30 - 06 JUN 26\"
```

### 7. PERAPIHAN LAPORAN KE30 – By Eq
```powershell
python ProcessKE30byEq.py --file "D:\Kerja\2026 CSSD\03. KE30\KE30 - 06 JUN 26\KE30_EQ.dat" --periode "2026-06-01" --insert-sql True
```

### 8. ZSME09E AUTOMATION
```powershell
python automate_zsme09e.py --periode "2026-06-01" --vbs-path "vbs\DownloadZSME09E.vbs" --save-path "D:\Kerja\SS\"
```

### 9. DOWNLOAD LAPORAN ZSMR019
```powershell
python download_zsmr019.py --periode "2026-06-01" --vbs-path "vbs\ZSMR019.vbs" --save-path "D:\Kerja\SS\" --insert-sql True
```
