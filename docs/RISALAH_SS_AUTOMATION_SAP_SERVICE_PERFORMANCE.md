# 📄 RISALAH INOVASI SISTEM SARAN (SS) — ASTRA GROUP 2026
## Kategori: Sistem Saran (Individual Improvement)
### Konvensi Mutu & Inovasi: Q! InnovAstra 36 – 2026

---

<div align="center">

# "TRANSFORMASI REPORTING SERVICE PERFORMANCE & SCORING: DARI BULANAN (2-3 HARI) MENJADI OTOMATISASI HARIAN REAL-TIME BERBASIS RPA SAP & SQL SERVER"

**Inovator (Pelaksana Tunggal):**  
**Dhani Yudhiantoro**  
*Departemen: Customer Service & Support Department (CSSD)*  
*Perusahaan: PT Astragraphia Tbk*  
*Tahun Pelaksanaan: 2026*

</div>

---

## RINGKASAN EKSEKUTIF (EXECUTIVE SUMMARY)

Laporan *Service Performance & Equipment Scoring* merupakan instrumen analitis paling vital di Customer Service & Support Department (CSSD) PT Astragraphia Tbk untuk memonitor produktivitas teknisi cabang, profitabilitas mesin di pelanggan, utilisasi suku cadang, dan pemenuhan *Service Level Agreement* (SLA) secara nasional. 

Sebelum adanya inovasi ini, proses penarikan, penggabungan, dan kalkulasi laporan dilakukan secara manual dengan mengekstrak berbagai transaksi SAP ERP (`ZSMR007B`, `KE30 Divisi`, `KE30 Equipment`, `ZSME09E`, `ZSMR019`) ke dalam file Excel yang terpisah-pisah. Proses klerikal ini membutuhkan waktu **2 hingga 3 hari kerja penuh (16 – 24 jam kerja)** pada setiap periode *closing* akhir bulan. Akibat tingginya beban dan lamanya durasi pemrosesan, pelaporan **hanya dapat dilakukan satu kali dalam sebulan (bulanan)**, sehingga data performa selalu terlambat (*lagging indicator*) hingga 30 hari dan manajemen tidak memiliki visibilitas harian terhadap kendala operasional teknisi di lapangan.

Melalui inisiatif Sistem Saran (SS) mandiri ini, inovator merancang, membangun, dan mengimplementasikan **Automatic SAP – Service Performance & Scoring Automation Platform**: sebuah platform otomasi robotik (*Robotic Process Automation* / RPA) dan *Extract, Transform, Load* (ETL) terintegrasi berbasis Python, SAP GUI Scripting COM API, normalisasi desimal otomatis, pengunggahan paralel ke Microsoft SQL Server (`DesSy`), serta dilengkapi antarmuka *Desktop GUI* dan *Web Dashboard* dengan *Background Scheduler*.

**Hasil yang Dicapai:**
1. **Efisiensi Waktu (Lead Time):** Waktu pembuatan laporan dipangkas dari **2–3 hari kerja (16–24 jam)** menjadi hanya **15–20 menit secara otomatis per hari** (efisiensi waktu **98,3%**).
2. **Transformasi Frekuensi:** Frekuensi reporting bertransformasi dari **Bulanan (1x/bulan)** menjadi **Harian (Daily Update)** setiap pagi pukul 08:30 WIB.
3. **Kualitas Data:** Meniadakan risiko *human error* pada sanitasi angka desimal SAP dan formula Excel (Akurasi data 100%).
4. **Dampak Finansial (NQI):** Menghasilkan penghematan biaya tenaga kerja dan lembur sebesar **Rp 48.000.000,- / tahun** dengan biaya investasi hanya Rp 1.500.000,-, menghasilkan **Net Quality Income (NQI) sebesar Rp 46.500.000,-** dan **NQI Ratio 31,0x**.

---

## BAB I: MENENTUKAN TEMA & SASARAN (LANGKAH 1)

### 1.1 Profil Inovator
* **Nama Inovator**: Dhani Yudhiantoro
* **Departemen / Divisi**: Customer Service & Support Department (CSSD)
* **Kategori Inovasi**: Sistem Saran (SS) / Individual Continuous Improvement
* **Perusahaan**: PT Astragraphia Tbk – Head Office

### 1.2 Latar Belakang & Alur Proses Eksisting
Customer Service & Support Department (CSSD) bertanggung jawab menjaga kelancaran ribuan mesin multifungsi dan perangkat cetak produksi di seluruh pelanggan korporasi PT Astragraphia Tbk di seluruh Indonesia. Keberhasilan operasional diukur melalui indikator *Service Performance* yang mencakup:
1. *Response Time* & *Repair Time* penanganan tiket servis.
2. Profitabilitas per unit mesin (*Equipment Profitability* via modul CO-PA).
3. Tingkat konsumsi dan pergerakan suku cadang (*Material Movement / Return*).
4. Pemenuhan rasio panggilan darurat (*Emergency Call Ratio*).

Untuk menyusun laporan konsolidasi tersebut, staf analis harus mengekstrak data dari sistem SAP ERP melalui 5 transaksi utama:
- **T-Code `ZSMR007B`**: Rekap service performance equipment (harus dipecah batch per 1.000 equipment melalui background job).
- **T-Code `KE30` (Divisi)**: Profitability analysis tingkat divisi bisnis.
- **T-Code `KE30` (Equipment)**: Profitability analysis rincian per nomor equipment.
- **T-Code `ZSME09E`**: Monitoring status pengembalian material/spare part teknisi.
- **T-Code `ZSMR019`**: Rekap order dan notifikasi servis (32 kolom data).

```mermaid
flowchart TD
    subgraph SEBELUM["Alur Kerja Manual Sebelum Perbaikan (2 - 3 Hari Kerja)"]
        A1["1. Copy batch 1.000 Eq ke SAP<br/>(Manual berulang puluhan kali)"] --> A2["2. Tunggu Spool SM37<br/>(Manual cek status)"]
        A2 --> A3["3. Download Spool ke TXT<br/>(File terpecah *1.txt & *2.txt)"]
        A3 --> A4["4. Download KE30 Divisi & Eq<br/>(Export format .dat)"]
        A4 --> A5["5. Download ZSME09E & ZSMR019<br/>(Export format spreadsheet)"]
        A5 --> A6["6. Buka Excel, Bersihkan Format Angka<br/>(Titik ribuan, Koma desimal, Minus belakang)"]
        A6 --> A7["7. VLOOKUP & Manual Join Data<br/>(File Excel berat, rentan crash)"]
        A7 --> A8["8. Laporan Selesai di H+3 Closing<br/>(Hanya bisa 1x per bulan)"]
    end
```

### 1.3 Voice of Business (VOB) & Penyelarasan Strategis
Inisiatif ini selaras dengan pilar strategis manajemen PT Astragraphia Tbk dan Astra International:
* **Astra 2030 Vision**: *Drive Digitalization, Operational Agility, and Data-Driven Decision Making*.
* **President Letter Astragraphia**: Penguatan keunggulan operasional (*Operational Excellence*) melalui otomatisasi proses internal dan efisiensi biaya.
* **Customer First & Service Excellence**: Kecepatan pemantauan performa harian memungkinkan penanganan preventif sebelum pelanggan mengajukan eskalasi keluhan.

### 1.4 Identifikasi Masalah & Analisis Kondisi Awal (Baseline Data)
Melalui observasi dan pencatatan waktu kerja selama 3 periode *closing* (Januari – Maret 2026), ditemukan fakta kuantitatif berikut:

1. **Lead Time Pembuatan Laporan:**
   - Proses pembuatan laporan membutuhkan waktu **16 hingga 24 jam kerja** (rata-rata 20 jam kerja, setara 2,5 – 3 hari kerja penuh).
2. **Keterbatasan Frekuensi Pelaporan:**
   - Karena prosesnya sangat melelahkan dan menyita waktu, reporting hanya dapat di-generate **1 kali per bulan**. Manajemen baru menerima laporan performa pada hari ke-3 atau ke-4 bulan berikutnya. Ketiadaan data harian menyebabkan inefisiensi teknisi di lapangan tidak dapat dimitigasi secara cepat.
3. **Penyiksaan Format Data SAP:**
   - SAP menggunakan standar desimal Eropa (koma sebagai desimal, titik sebagai ribuan, misal `1.234,56`) dan meletakkan tanda minus di akhir angka (misal `322.361-`). Ketika di-copy ke Excel Indonesia/US, angka tersebut berubah menjadi teks atau terbaca salah, memerlukan pembersihan manual baris demi baris.
4. **Keterbatasan SAP GUI:**
   - SAP membatasi input clipboard maksimal 1.000 baris. Untuk memproses >10.000 nomor equipment, operator harus memecah batch dan melakukan copy-paste berulang kali.

### 1.5 Penetapan Target Sasaran Berdasarkan Kaidah S-M-A-R-T
*Catatan: Disusun secara runut sesuai kaidah baku dewan juri Astra (S -> M -> A -> R -> T):*

1. **S - Specific**:  
   Membangun sistem otomasi end-to-end terpadu (RPA & ETL) yang mengotomatisasi seluruh siklus ekstraksi SAP, pembersihan data, dan pengunggahan ke database SQL Server secara mandiri tanpa intervensi manual.
2. **M - Measurable**:  
   - Memangkas waktu pembuatan laporan dari **2–3 hari (20 jam)** menjadi **$\le 20$ menit per hari** (efisiensi $\ge 98\%$).  
   - Meningkatkan frekuensi pembaruan data dari **Bulanan (1x/bulan)** menjadi **Harian (Daily 20x/bulan)**.  
   - Akurasi sanitasi angka dan row count mencapai **100%**.
3. **A - Achievable**:  
   Sangat realistis untuk dicapai dengan mengintegrasikan SAP GUI Scripting COM API, pemrosesan paralel Python, pustaka `pyodbc` dengan `fast_executemany`, dan Windows Task Scheduler.
4. **R - Relevant**:  
   Sangat relevan dengan sasaran operasional CSSD dalam mewujudkan *daily monitoring dashboard* performa mesin dan teknisi nasional.
5. **T - Time-Bound**:  
   Rancang bangun sistem diselesaikan dalam 6 minggu, dan implementasi operasional penuh tercapai dalam waktu 3 bulan (April – Juni 2026).

---

## BAB II: MENGIDENTIFIKASI PENYEBAB (LANGKAH 2)

Untuk membedah faktor-faktor penyebab lamanya durasi pelaporan manual, inovator menggunakan alat analisis **Diagram Tulang Ikan (Fishbone Diagram / Ishikawa)** dengan kategori 4M + 1E:

```mermaid
flowchart LR
    subgraph MAN["MANPOWER"]
        M1["Hanya mengandalkan 1 operator ahli"]
        M2["Kelelahan kognitif saat closing"]
        M3["Risiko human error copy-paste"]
    end
    subgraph METHOD["METHOD"]
        ME1["Proses manual bertahap 8 langkah"]
        ME2["Pemecahan batch 1.000 eq manual"]
        ME3["Formula Excel VLOOKUP berat & lambat"]
    end
    subgraph MACHINE["MACHINE / SYSTEM"]
        MC1["Format desimal koma & minus belakang khas SAP"]
        MC2["Belum ada bridge integrasi SAP ke SQL"]
        MC3["SAP GUI timeout bila data terlalu besar"]
    end
    subgraph MATERIAL["MATERIAL / DATA"]
        MT1["Format file bervariasi (.txt, .dat, .xlsx)"]
        MT2["Struktur delimiter pipe | tidak standar"]
    end
    subgraph ENV["ENVIRONMENT"]
        E1["Tekanan batas waktu closing akhir bulan"]
    end

    AKAR["AKAR MASALAH:<br/>Pembuatan Laporan Service Performance Butuh Waktu 2-3 Hari & Hanya Bisa Diperbarui Sebulan Sekali"]

    MAN --> AKAR
    METHOD --> AKAR
    MACHINE --> AKAR
    MATERIAL --> AKAR
    ENV --> AKAR
```

---

## BAB III: MENENTUKAN AKAR PENYEBAB DOMINAN (LANGKAH 3)

### 3.1 Matriks Analisis 5W + 1H Terhadap Akar Penyebab
Berdasarkan diagram Ishikawa, dilakukan verifikasi faktual menggunakan matriks 8 kolom baku standar konvensi mutu Astra:

| Kategori | Root Cause (Akar Masalah) | What | Where | Why | Who | When | How |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Method** | **Ketiadaan Pipeline Otomatis** | Ekstraksi 5 laporan SAP dijalankan manual satu per satu | SAP GUI & Workstation PC | Belum ada script orkestrasi yang merantai proses | Inovator (Staf Analis) | Setiap akhir bulan | Menjalankan klik manual selama berjam-jam |
| **Method** | **Pemecahan Batch Manual** | Input data equipment dibatasi maks 1.000 baris di SAP | SAP GUI T-Code ZSMR007B | Keterbatasan memori clipboard antarmuka GUI SAP | Inovator | Hari ke-1 Closing | Membagi baris Excel manual dan paste berulang kali |
| **Machine** | **Format Angka SAP Tidak Standar** | Angka ribuan koma/titik dan tanda minus di akhir string (`1.234,56-`) | File raw export SAP | Karakteristik regional setting SAP kernel ERP | Inovator | Hari ke-2 Closing | Melakukan *find & replace* manual di Excel |
| **Machine** | **Database Belum Terkoneksi Langsung** | Hasil unduhan tersimpan di file lokal, tidak terpusat | Penyimpanan lokal laptop | Belum ada pipeline ETL otomatis ke database SQL | Inovator | Hari ke-2 & 3 Closing | Mengunggah manual satu per satu via wizard |
| **Manpower** | **Ketergantungan Operator Tunggal** | Bila operator berhalangan, reporting terhenti total | Operasional CSSD | Pengetahuan logika merge hanya dipegang 1 orang | Inovator | Periode Closing | Memerlukan dokumentasi dan otomatisasi headless |

### 3.2 Rumusan Masalah Utama (Problem Statement)
> *"Bagaimana merancang sebuah sistem otomatisasi mandiri (RPA & ETL Pipeline) yang mampu mengekstrak multi-laporan SAP GUI, menormalisasi anomali format angka desimal secara otomatis, dan mengunggahnya ke database SQL Server secara terjadwal setiap hari, sehingga waktu pembuatan laporan Service Performance dipangkas dari 2–3 hari menjadi kurang dari 20 menit dan data dapat diperbarui secara harian?"*

---

## BAB IV: MERENCANAKAN PERBAIKAN (LANGKAH 4)

Inovator menyusun rencana perbaikan komprehensif menggunakan matriks **5W + 2H (Action Plan)**:

| No | Tahapan Rencana | What (Aktivitas) | Why (Tujuan) | Where (Lokasi) | When (Jadwal) | Who (PIC) | How (Metode Teknis) | How Much (Biaya) |
|:--:|:---|:---|:---|:---|:---|:---|:---|:--:|
| 1 | **Desain Arsitektur & BRD** | Menyusun Business Requirement Document & alur data pipeline | Memastikan seluruh kebutuhan bisnis tercakup | CSSD HO | Minggu 1 (Apr 2026) | Dhani Y. | Pemetaan modul & database schema | Rp 0 |
| 2 | **SAP Scripting Bridge** | Mengembangkan script VBS & Python COM untuk interaksi SAP GUI | Mengotomasi klik, login, dan download laporan SAP | SAP S/4HANA & Python | Minggu 2 (Apr 2026) | Dhani Y. | Modul `sap_utils.py` & VBS wrapper | Rp 0 |
| 3 | **Batching & Spool Engine** | Membuat modul pemecah batch equipment & ekstraksi spool otomatis | Mengatasi limit 1.000 equipment di SAP ZSMR007B | Python Scripting | Minggu 3 (Apr 2026) | Dhani Y. | Modul `rpa_sap_1.py` & `download_zsmr007b.py` | Rp 0 |
| 4 | **Data Sanitizer & Normalizer** | Membangun parser regex pembersih koma desimal dan minus belakang | Mencegah error tipe data saat masuk SQL Server | Python Regex Engine | Minggu 4 (Mei 2026) | Dhani Y. | Modul `db_utils.py` & `process_reports.py` | Rp 0 |
| 5 | **SQL Server Parallel ETL** | Membangun layer database dengan batch chunking 1.000 baris | Mempercepat upload tanpa buffer lock database | SQL Server `DesSy` | Minggu 5 (Mei 2026) | Dhani Y. | Pustaka `pyodbc` dengan `fast_executemany` | Rp 0 |
| 6 | **Dual User Interface** | Membangun antarmuka Desktop GUI (Tkinter) & Web UI (FastAPI SSE) | Memudahkan monitoring bagi user non-teknis | Workstation & Browser | Minggu 6 (Mei 2026) | Dhani Y. | `dashboard.py` & `web_dashboard.py` | Rp 0 |
| 7 | **Automated Scheduler** | Mengkonfigurasi Windows Task Scheduler dengan fitur laptop-ready | Memastikan laporan berjalan otomatis setiap jam 08:00 | Windows OS | Minggu 7 (Jun 2026) | Dhani Y. | Skrip PowerShell `setup_scheduler.ps1` | Rp 0 |
| 8 | **Testing & Standarisasi** | Melakukan smoke testing (16 test suites) & penyusunan Manual Book | Memastikan sistem stabil dan terstandarisasi | Production | Minggu 8 (Jun 2026) | Dhani Y. | `test_smoke.py` & Manual Book v1.0 | Rp 1.500.000 (Konsumsi dev) |

---

## BAB V: MELAKSANAKAN PERBAIKAN (LANGKAH 5)

Inovator mengeksekusi pembangunan platform **Automatic SAP** dengan arsitektur 5-Layer tingkat enterprise:

```mermaid
flowchart TD
    subgraph L1["1. USER INTERFACE LAYER"]
        GUI["Desktop GUI (Tkinter)<br/>dashboard.py"]
        WEB["Modern Web Dashboard (FastAPI + SSE)<br/>web_dashboard.py"]
    end
    subgraph L2["2. ORCHESTRATION SERVICE"]
        DO["Daily Orchestrator (6-Stage Pipeline)<br/>daily_orchestrator.py"]
        PR["Dynamic Path Resolver (D:\Kerja\)<br/>path_resolver.py"]
        SCH["Windows Task Scheduler / Background Loop<br/>(Start When Available 08:00 AM)"]
    end
    subgraph L3["3. SAP AUTOMATION BRIDGE"]
        COM["SAP GUI COM Scripting Engine (win32com)<br/>Deteksi Multi-Login wnd[1] & Session"]
        VBS["WScript VBScript Modular Executor<br/>(shell=False, Anti-Injection)"]
    end
    subgraph L4["4. ETL & DATA SANITIZATION LAYER"]
        SAN["Universal Number Sanitizer:<br/>- Koma ke Titik: 1.234,56 -> 1234.56<br/>- Minus Belakang: 322.361- -> -322361.0<br/>- Encoding Auto-Detect: UTF-16 / CP1252"]
    end
    subgraph L5["5. PERSISTENCE STORAGE LAYER"]
        SQL["Microsoft SQL Server (DesSy @ 172.31.151.88)<br/>ODBC Driver 17 - pyodbc fast_executemany<br/>Batch 1.000 Rows Chunking & Idempotent Cleanup"]
    end

    GUI --> DO
    WEB --> DO
    SCH --> DO
    DO --> PR
    DO --> COM
    DO --> VBS
    COM --> SAN
    VBS --> SAN
    SAN --> SQL
```

### Inovasi Kunci yang Diterapkan:
1. **6-Stage Daily Automation Pipeline (`daily_orchestrator.py`)**:
   - Mengintegrasikan seluruh siklus kerja hanya dalam 1-Klik / 1-Jadwal:
     - *Tahap 1*: Generate Background Job ZSMR007B per 1.000 equipment otomatis.
     - *Tahap 2*: Download hasil spool ZSMR007B, merge `*1` dan `*2`, lalu simpan ke database `ZSMR007B`.
     - *Tahap 3*: Ekstraksi profitabilitas KE30 Divisi ke tabel `KE30`.
     - *Tahap 4*: Ekstraksi profitabilitas KE30 Equipment, parse composite string, ke tabel `KE30_ByEq`.
     - *Tahap 5*: Ekstraksi material return ZSME09E ke tabel `ZSME09E`.
     - *Tahap 6*: Ekstraksi 32 kolom notifikasi & service order ZSMR019 ke tabel `ZSMR019`.
2. **Dynamic Path Resolver (`path_resolver.py`)**:
   - Robot secara cerdas mendeteksi tahun dan bulan aktif, lalu membuat pohon folder kerja secara otomatis di direktori `D:\Kerja\{YYYY} CSSD\02. REPORTING {YYYY}\` tanpa perlu konfigurasi manual dari user.
3. **Pembersihan Angka SAP Universal (`db_utils.py`)**:
   - Menerapkan algoritma regex yang mengubah format desimal Eropa dan memindahkan tanda minus dari belakang ke depan secara instan, mencegah kegagalan *casting* tipe data SQL Server.
4. **Smart Scheduler Lookback di Hari Senin**:
   - Penjadwal otomatis mendeteksi hari: pada Selasa–Jumat menarik data H-1 (kemarin sore), sedangkan pada hari Senin secara otomatis mundur menarik data H-3 (Jumat sore), memastikan tidak ada data transaksi akhir pekan yang terlewat.
5. **Zero-Trust Security**:
   - Kredensial SAP dan database dienkapsulasi penuh di file `.env`, tidak pernah terekspos di source code maupun Git repository.

---

## BAB VI: MENGEVALUASI HASIL / BENEFIT (LANGKAH 6)

### 6.1 Evaluasi Kinerja (Sebelum vs Setelah Perbaikan)

| Indikator Evaluasi | Sebelum Perbaikan (Manual) | Target Sasaran (SMART) | Setelah Perbaikan (Otomatis) | Hasil Pencapaian |
| :--- | :---: | :---: | :---: | :---: |
| **Waktu Proses Pembuatan Laporan** | **16 – 24 Jam** (2 – 3 Hari Kerja) | $\le 30$ Menit | **15 – 20 Menit** (Unattended) | **Terlampaui (Efisiensi 98,3%)** |
| **Frekuensi Ketersediaan Laporan** | **1 Kali per Bulan** (Bulanan) | Harian | **Setiap Hari Kerja** (Daily @ 08:30) | **Terlampaui (Naik 20x Lipat)** |
| **Intervensi Fisik Operator** | Penuh (Ribuan Klik & Paste) | 1-Klik / Tanpa Klik | **0 Klik** (Terjadwal Task Scheduler) | **Terlampaui (Otomatisasi 100%)** |
| **Keterlambatan Informasi (*Lagging*)** | 30 Hari (H+3 Akhir Bulan) | Real-time H+1 | **H+1 Setiap Pagi** | **Data Selalu Aktual** |
| **Akurasi Data Angka Desimal** | Rawan Kesalahan Human Error | 100% Valid | **100% Konsisten Tervalidasi SQL** | **Zero Defect** |

```mermaid
xychart-beta
    title "Perbandingan Durasi Pembuatan Laporan (dalam Jam Kerja)"
    x-axis ["Sebelum Perbaikan (Manual)", "Target SMART", "Setelah Perbaikan (Automated SAP)"]
    y-axis "Durasi (Jam Kerja)" 0 --> 25
    bar [20, 0.5, 0.33]
```

---

### 6.2 Evaluasi Finansial (Net Quality Income / NQI)

Sesuai kaidah standar evaluasi finansial Astra InnovAstra, kalkulasi keuntungan finansial (*Cost Reduction*) dihitung secara transparan:

#### A. Komponen Penghematan (Cost Reduction / Benefit):
1. **Penghematan Jam Kerja Reguler Staf Analis:**
   - Waktu manual sebelum perbaikan: 20 jam / bulan.
   - Waktu setelah perbaikan: 0,33 jam $\times$ 20 hari = 6,6 jam / bulan (berjalan otomatis di background).
   - Efisiensi jam kerja staf: $20 - 0 = 20$ jam kerja produktif / bulan.
   - Total jam kerja staf dihemat: $20 \text{ jam} \times 12 \text{ bulan} = 240 \text{ jam/tahun}$.
   - Biaya standar per jam kerja staf (Standar CSSD): Rp 150.000,- / jam.
   - **Nilai Efisiensi Manhour:** $240 \text{ jam} \times \text{Rp } 150.000,- = \mathbf{\text{Rp } 36.000.000,- / \text{tahun}}$.
2. **Penghematan Biaya Lembur (*Overtime Elimination*) Closing Akhir Bulan:**
   - Rata-rata lembur staf closing: 8 jam lembur / bulan.
   - Rata-rata upah lembur: Rp 125.000,- / jam lembur.
   - Efisiensi lembur: $8 \text{ jam} \times \text{Rp } 125.000,- \times 12 \text{ bulan} = \mathbf{\text{Rp } 12.000.000,- / \text{tahun}}$.
3. **Total Manfaat Bruto (*Gross Benefit*):**  
   $$\text{Gross Benefit} = \text{Rp } 36.000.000 + \text{Rp } 12.000.000 = \mathbf{\text{Rp } 48.000.000,- / \text{tahun}}$$

#### B. Komponen Biaya Investasi Inovasi (*Investment Cost*):
1. Perangkat lunak (Python, FastAPI, pyodbc, Open-Source): Rp 0,-
2. Lisensi Microsoft SQL Server & SAP GUI (Infrastruktur Eksisting Perusahaan): Rp 0,-
3. Biaya konsumsi & sarana selama pengujian mandiri: Rp 1.500.000,-
4. **Total Biaya Inovasi (*Cost*):** **Rp 1.500.000,-**

#### C. Perhitungan NQI & NQI Ratio:
$$\text{Net Quality Income (NQI)} = \text{Benefit} - \text{Cost}$$
$$\text{NQI} = \text{Rp } 48.000.000 - \text{Rp } 1.500.000 = \mathbf{\text{Rp } 46.500.000,- / \text{tahun}}$$

$$\text{NQI Ratio} = \frac{\text{Benefit} - \text{Cost}}{\text{Cost}} = \frac{\text{Rp } 46.500.000}{\text{Rp } 1.500.000} = \mathbf{31,00\times}$$

> [!NOTE]
> Sistem Saran ini menghasilkan nilai tambah bersih (**NQI**) sebesar **Rp 46.500.000,- per tahun** dengan efektivitas investasi sebesar **31,0 kali lipat** dari biaya yang dikeluarkan.

---

### 6.3 Evaluasi Non-Finansial (QCDSM)

| Pilar QCDSM | Dampak Positif Sebelum vs Sesudah Inovasi |
| :--- | :--- |
| **Quality (Mutu)** | Sanitasi angka 100% akurat. Menghilangkan risiko kesalahan koma desimal atau minus belakang yang sering terjadi pada pemrosesan manual di Excel. |
| **Cost (Biaya)** | Meniadakan pengeluaran lembur operasional closing akhir bulan bagi departemen CSSD. |
| **Delivery (Kecepatan)** | Ketersediaan data dipercepat dari H+3 setiap bulan menjadi **setiap pagi jam 08:30 WIB (Daily Real-Time)**, memberikan visibilitas harian bagi seluruh Service Manager cabang di Indonesia. |
| **Safety (Keselamatan/Kesehatan)** | Mengurangi risiko kelelahan fisik, stres kognitif, dan ketegangan mata operator akibat bekerja di depan layar Excel hingga larut malam pada saat periode closing. |
| **Morale (Semangat Kerja)** | Kepuasan dan semangat kerja staf meningkat karena terbebas dari tugas repetitif klerikal dan dapat berfokus pada pekerjaan analitis bernilai tambah tinggi. |

---

## BAB VII: MENSTANDARISASI (LANGKAH 7)

Untuk menjamin keberlanjutan (*sustainability*) sistem dan mencegah kembalinya proses manual, inovator menetapkan standarisasi resmi:

1. **Standarisasi Prosedur Operasional (SOP)**:
   - Menerbitkan **[Manual Book Pengoperasian Aplikasi v1.0.0](file:///D:/Kerja/Application%20AG/SAP%20AUTOMATION/docs/MANUAL_BOOK.md)** lengkap dengan panduan diagnostik mandiri.
   - Menyusun **[Checklist Harian & SOP Closing](file:///D:/Kerja/Application%20AG/SAP%20AUTOMATION/docs/checklist_harian.md)** untuk verifikasi integritas baris data di SQL Server.
2. **Standarisasi Otomasi Sistem Operasi**:
   - Mendaftarkan *task scheduler* baku melalui skrip `setup_scheduler.ps1` pada Windows Task Scheduler dengan konfigurasi *Start When Available* setiap hari kerja pukul 08:00 WIB.
3. **Standarisasi Keamanan Kredensial**:
   - Membakukan isolasi kredensial melalui template `.env.example` berstandar *Zero-Trust Security*.
4. **Automated Smoke Testing**:
   - Membakukan skrip validasi mandiri `test_smoke.py` (16 unit test) untuk memverifikasi kesiapan fungsi sebelum sistem beroperasi.

---

## BAB VIII: MENETAPKAN RENCANA BERIKUTNYA (LANGKAH 8)

Sebagai wujud komitmen perbaikan berkesinambungan (*Kaizen / Continuous Improvement*), inovator merumuskan rencana inovasi fase berikutnya (PDCA Siklus II):

```mermaid
flowchart TD
    S1["Siklus I (Selesai):<br/>Otomatisasi Ekstraksi & Sinkronisasi SAP ke SQL Server (Daily Update)"] --> S2["Siklus II (Next Plan Q3-Q4 2026):<br/>1. Integrasi Predictive Machine Learning Scoring untuk Early Warning Kerusakan Mesin.<br/>2. Otomasi Pengiriman Executive Daily WhatsApp / Email Alert ke Service Manager Cabang.<br/>3. Replikasi Platform ke Reporting Modul Logistik & Spare Parts Nasional."]
```

1. **Implementasi Early Warning Predictive Scoring**:
   - Membangun model machine learning berbasis data tabel `KE30_ByEq` dan `ZSMR019` untuk memprediksi mesin pelanggan yang berpotensi rugi (*unprofitable*) atau mengalami *breakdown* berulang sebelum akhir bulan.
2. **Automated Executive Notification**:
   - Mengintegrasikan modul pengiriman ringkasan KPI harian via bot WhatsApp / Email terenkripsi langsung ke para Service Manager Cabang setiap jam 09:00 WIB.
3. **Ekspansi Modul**:
   - Mereplikasi arsitektur otomatisasi SAP ini untuk modul pelaporan persediaan gudang logistik dan suku cadang nasional.

---

<div align="center">

**"Inovasi ini adalah wujud nyata kontribusi mandiri dalam mentransformasi proses kerja konvensional menjadi cerdas, cepat, dan akurat demi mendukung keunggulan operasional PT Astragraphia Tbk dan mewujudkan Visi Astra: Menjadi yang Terbaik."**

*Jakarta, Oktober 2026*  
**Inovator (Sistem Saran)**  

*(Dhani Yudhiantoro)*

</div>
