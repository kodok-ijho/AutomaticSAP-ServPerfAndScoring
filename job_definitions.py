"""
Definisi job terpusat untuk SAP Automation.

Sebelumnya dictionary SCRIPTS diduplikasi (dan mulai berbeda) antara
dashboard.py (desktop) dan web_dashboard.py. Modul ini menjadikannya satu
sumber kebenaran sehingga keduanya selalu sinkron.

Berisi:
- SCRIPTS          : definisi semua job + parameternya
- DB_ARG_SCRIPTS   : script yang menerima argumen --db-* (untuk upload SQL)
- resolve_default  : mengubah sentinel tanggal dinamis jadi tanggal hari ini
- build_cli_args   : membangun daftar argumen CLI dari parameter + db_config
"""
from datetime import datetime, timedelta

# Script yang menerima argumen koneksi DB (--db-server, dst) untuk upload SQL.
# Script lain (rpa_sap_1.py, download_zsmr007b.py, ProcessKE30byEq.py) TIDAK
# menerima argumen ini — rpa/download membaca kredensial langsung dari .env.
DB_ARG_SCRIPTS = {
    "daily_orchestrator.py",
    "process_reports.py",
    "automate_zsme09e.py",
    "ProsesKE30byDiv.py",
    "ProcessKE30byEq.py",
    "download_zsmr019.py",
    "process_ke30_scoring.py",
    "download_zsmr012.py",
    "download_iw58.py",
    "download_iw73.py",
    "process_zsmr012.py",
    "process_iw58.py",
    "process_iw73.py",
}

SCRIPTS = {
    "DAILY AUTOMATION PIPELINE – Full 6 Stages": {
        "file": "daily_orchestrator.py",
        "desc": "Otomatisasi Harian Terpadu: Menjalankan 6 Tahap (Create BG 007B batch 1.000 eq, Download & Upsert 007B, KE30 Divisi, KE30 Equipment, ZSME09E, ZSMR019) dengan auto-folder D:\\Kerja\\.",
        "params": [
            {"arg": "periode",          "label": "Target Periode",  "default": "dynamic-today-ymd", "type": "date", "help": "Format YYYY-MM-DD (Default: auto-detect dari DB)"},
            {"arg": "sched-start-time", "label": "Sched BG Start",  "default": "17:00",             "type": "str",  "help": "Jam mulai eksekusi Background Job SAP Tahap 1 di server (contoh: 10:00 atau 17:00)"},
            {"arg": "base-drive",       "label": "Base Drive Work", "default": "D:\\Kerja",        "type": "path", "help": "Root folder kerja Astragraphia"},
            {"arg": "stages",           "label": "Pilihan Tahap",   "default": "1,2,3,4,5,6",       "type": "str",  "help": "Daftar tahap yang dijalankan (contoh: 1,2,3,4,5,6)"},
            {"arg": "batch-size",       "label": "Batch Size Eq",   "default": "1000",              "type": "int",  "help": "Jumlah equipment per batch untuk Tahap 1"},
            {"arg": "sch-time",         "label": "Sch Time",        "default": "08:00",             "type": "sch",  "help": "Waktu eksekusi otomatis harian (HH:mm)"},
            {"arg": "sch-active",       "label": "Sch Active",      "default": "False",             "type": "bool", "help": "Aktifkan jadwal otomatis harian"},
        ],
    },
    "CREATE BG JOB ZSMR007B – Equipment Batch Clipboard": {
        "file": "rpa_sap_1.py",
        "desc": "Mengambil data EQUIPMENT dari Tb_R_SerPervEq, salin ke Clipboard per-batch, lalu jalankan SecondRecord.vbs.",
        "params": [
            {"arg": "periode",    "label": "Periode",      "default": "2026-01-01", "type": "date", "help": "Format YYYY-MM-DD"},
            {"arg": "max-offset", "label": "Max Offset",   "default": "0",          "type": "int",  "help": "Batas atas offset (0 = seluruh data)"},
            {"arg": "batch-size", "label": "Batch Size",   "default": "1000",       "type": "int",  "help": "Jumlah per batch (default 1.000)"},
            {"arg": "delay",            "label": "Delay (detik)",       "default": "10",         "type": "int",  "help": "Jeda antar iterasi"},
            {"arg": "vbs-path",         "label": "Path VBS",            "default": "vbs\\CreateBG007B-Scheduled.vbs", "type": "path", "help": "Lokasi VBS"},
            {"arg": "sched-start-time", "label": "Sched BG Start", "default": "17:00",      "type": "str",  "help": "Jam mulai jadwal SAP BG Job (17:00)"},
            {"arg": "sch-time",         "label": "Sch Time",            "default": "08:00",      "type": "sch",  "help": "Waktu eksekusi (HH:mm)"},
            {"arg": "sch-active",       "label": "Sch Active",          "default": "False",      "type": "bool", "help": "Aktifkan jadwal otomatis"},
        ],
    },
    "DOWNLOAD BG JOB ZSMR007B – SAP Background Job": {
        "file": "download_zsmr007b.py",
        "desc": "Ambil Periode aktif dari Tb_R_PeriodeClosing, lalu jalankan DownloadBGJob007B.vbs.",
        "params": [
            {"arg": "tanggal",    "label": "Tanggal (To Date)", "default": "dynamic-today-dmy", "type": "str",  "help": "Format dd.MM.yyyy (From Date = H-1 otomatis)"},
            {"arg": "periode",    "label": "Periode Override",  "default": "",        "type": "str",  "help": "YYYY-MM-DD (opsional)"},
            {"arg": "vbs-path",   "label": "Path VBS",          "default": "vbs\\DownloadBGJob007B.vbs", "type": "path", "help": "Lokasi VBS"},
            {"arg": "save-path",  "label": "Save Path",         "default": "D:\\Kerja\\SS\\", "type": "path", "help": "Folder tujuan simpan file (wajib ada trailing \\)"},
            {"arg": "sch-time",   "label": "Sch Time",          "default": "07:00",   "type": "sch",  "help": "Waktu eksekusi (HH:mm)"},
            {"arg": "sch-active", "label": "Sch Active",        "default": "False",   "type": "bool", "help": "Aktifkan jadwal otomatis"},
        ],
    },
    "MERAPIHKAN HASIL DOWNLOAD – ZSMR007B": {
        "file": "process_reports.py",
        "desc": "Merapihkan hasil download .txt menjadi format Excel. Menggabungkan file *1 dan *2, lalu mengkolaborasikannya.",
        "params": [
            {"arg": "folder", "label": "Folder Laporan", "default": "", "type": "path", "help": "Folder tempat file .txt (A1.txt, A2.txt, dll) disimpan"},
            {"arg": "periode", "label": "Periode Override", "default": "", "type": "str", "help": "yyyy-MM-dd (opsional, jika kosong ambil dari DB)"},
            {"arg": "insert-sql", "label": "Insert ke SQL", "default": "False", "type": "bool", "help": "Upload hasil gabungan ke tabel ZSMR007B"},
        ],
    },
    "DOWNLOAD LAPORAN KE30 – By Divisi": {
        "file": "download_ke30.py",
        "desc": "Download otomatis laporan KE30 per Divisi dari SAP GUI menggunakan VBScript.",
        "params": [
            {"arg": "periode",   "label": "Periode",   "default": "dynamic-today-ymd", "type": "date", "help": "Format YYYY-MM-DD"},
            {"arg": "vbs-path",  "label": "Path VBS",  "default": "vbs\\KE30 Get CMNWDN by Div.vbs", "type": "path", "help": "Lokasi VBS"},
            {"arg": "save-path", "label": "Save Path", "default": "D:\\Kerja\\2026 CSSD\\03. KE30\\KE30 - 06 JUN 26\\AUTO\\BY DIV\\", "type": "path", "help": "Folder simpan file download"},
            {"arg": "sch-time",  "label": "Sch Time",  "default": "07:30", "type": "sch",  "help": "Waktu eksekusi (HH:mm)"},
            {"arg": "sch-active","label": "Sch Active","default": "False", "type": "bool", "help": "Aktifkan jadwal otomatis"},
        ],
    },
    "By Divisi PERAPIHAN LAPORAN KE30 – By Divisi": {
        "file": "ProsesKE30byDiv.py",
        "desc": "Merapihkan file RAW Excel KE30 dengan menambahkan 20 parameter baru, membuang baris header, dan automapping data Div/MBU.",
        "params": [
            {"arg": "folder", "label": "Folder Laporan", "default": "D:\\Kerja\\2026 CSSD\\03. KE30\\KE30 - 04 APR 26\\All Div\\CMNW-DN", "type": "path", "help": "Folder tempat file Excel disimpan"},
            {"arg": "periode", "label": "Periode", "default": "2026-04-01", "type": "str", "help": "Target periode (yyyy-MM-dd)"},
            {"arg": "insert-sql", "label": "Insert ke SQL", "default": "False", "type": "bool", "help": "Upload hasil ke tabel KE30"},
        ],
    },
    "DOWNLOAD LAPORAN KE30 – By Eq": {
        "file": "download_ke30_eq.py",
        "desc": "Download otomatis laporan KE30 per Equipment dari SAP GUI menggunakan VBScript.",
        "params": [
            {"arg": "periode",    "label": "Periode",      "default": "dynamic-today-ymd", "type": "date", "help": "Format YYYY-MM-DD"},
            {"arg": "vbs-path",   "label": "Path VBS",     "default": "vbs\\KE30 Get CMNWDN by Eq.vbs", "type": "path", "help": "Lokasi VBS"},
            {"arg": "save-path",  "label": "Save Path",    "default": "D:\\Kerja\\2026 CSSD\\03. KE30\\KE30 - 06 JUN 26\\", "type": "path", "help": "Folder simpan file download"},
            {"arg": "sch-time",   "label": "Sch Time",     "default": "07:45",      "type": "sch",  "help": "Waktu eksekusi (HH:mm)"},
            {"arg": "sch-active", "label": "Sch Active",   "default": "False",      "type": "bool", "help": "Aktifkan jadwal otomatis"},
        ],
    },
    "By Eq PERAPIHAN LAPORAN KE30 – By Eq": {
        "file": "ProcessKE30byEq.py",
        "desc": "Merapihkan file RAW Excel KE30 by Equipment dengan menambahkan 20 parameter baru dan automapping data.",
        "params": [
            {"arg": "folder", "label": "Folder Laporan", "default": "D:\\Kerja\\2026 CSSD\\03. KE30\\KE30 - 05 MAY 26", "type": "path", "help": "Folder tempat file dat disimpan"},
            {"arg": "periode", "label": "Periode", "default": "2026-05-01", "type": "str", "help": "Target periode (yyyy-MM-dd)"},
            {"arg": "insert-sql", "label": "Insert ke SQL", "default": "False", "type": "bool", "help": "Upload hasil ke tabel KE30ByEq"},
        ],
    },
    "DOWNLOAD LAPORAN ZSME09E – Batch Loop Spool": {
        "file": "automate_zsme09e.py",
        "desc": "Otomasi ZSME09E: Auto-download spool per-batch (35 equipment) dari SAP GUI menggunakan VBScript, lalu bersihkan dan simpan ke Excel & SQL.",
        "params": [
            {"arg": "periode",    "label": "Periode",      "default": "dynamic-today-ymd", "type": "date", "help": "Format YYYY-MM-DD (harus ada di Tb_R_PeriodeClosing)"},
            {"arg": "vbs-path",   "label": "Path VBS",     "default": "vbs\\DownloadZSME09E.vbs", "type": "path", "help": "File VBS utama untuk ZSME09E"},
            {"arg": "save-path",  "label": "Save Path",    "default": "D:\\Kerja\\SS\\", "type": "path", "help": "Folder simpan hasil download"},
            {"arg": "sch-time",   "label": "Sch Time",     "default": "08:00",      "type": "sch",  "help": "Waktu eksekusi (HH:mm)"},
            {"arg": "sch-active", "label": "Sch Active",   "default": "False",      "type": "bool", "help": "Aktifkan jadwal otomatis"},
        ],
    },
    "DOWNLOAD LAPORAN ZSMR019 – SAP GUI Report": {
        "file": "download_zsmr019.py",
        "desc": "ZSMR019: Ambil StartDate & EndDate dari Tb_R_PeriodeClosing berdasarkan 1 tanggal Periode, download via VBScript (nama file otomatis ZSMR019 - MMyy - ddMMyy.txt), lalu update ke tabel ZSMR019.",
        "params": [
            {"arg": "periode",    "label": "Periode",      "default": "dynamic-today-ymd", "type": "date", "help": "Format YYYY-MM-DD (mis. 2026-06-01)"},
            {"arg": "vbs-path",   "label": "Path VBS",     "default": "vbs\\ZSMR019.vbs", "type": "path", "help": "File VBS ZSMR019"},
            {"arg": "save-path",  "label": "Save Path",    "default": "D:\\Kerja\\SS\\", "type": "path", "help": "Folder simpan hasil download"},
            {"arg": "insert-sql", "label": "Insert ke SQL", "default": "True",        "type": "bool", "help": "Upload ke tabel ZSMR019 (Delete periode lama + Insert)"},
            {"arg": "sch-time",   "label": "Sch Time",     "default": "08:15",      "type": "sch",  "help": "Waktu eksekusi (HH:mm)"},
            {"arg": "sch-active", "label": "Sch Active",   "default": "False",      "type": "bool", "help": "Aktifkan jadwal otomatis"},
        ],
    },
    "KE30 Report - Generate Master & Split 22 MPG for Scoring": {
        "file": "process_ke30_scoring.py",
        "desc": "Membuat file master KE30 YTDN Scoring bulanan dari database SQL Server, memecah 22 file per MPG/Team (A1 s/d Z1), serta opsi pengiriman email otomatis ke masing-masing CSM.",
        "params": [
            {"arg": "periode",     "label": "Periode",          "default": "dynamic-today-ymd", "type": "date", "help": "Format YYYY-MM-DD (contoh: 2026-07-01)"},
            {"arg": "send-email",  "label": "Kirim Email CSM",  "default": "False",             "type": "bool", "help": "Kirim email hasil scoring per MPG ke masing-masing CSM via Outlook"},
            {"arg": "test-mode",   "label": "Mode Test",        "default": "True",              "type": "bool", "help": "Jika True: Hanya kirim ke dhani.yudhiantoro@astragraphia.co.id tanpa CC/BCC. Jika False: Kirim ke email CSM & CC team."},
            {"arg": "email-draft", "label": "Simpan sbg Draft", "default": "True",              "type": "bool", "help": "Simpan di Drafts Outlook (True) atau langsung kirim (False)"},
            {"arg": "sch-day",     "label": "Sch Tanggal",      "default": "1",                 "type": "str",  "help": "Tanggal eksekusi bulanan (misal 1 untuk setiap tanggal 1, atau * untuk setiap hari)"},
            {"arg": "sch-time",    "label": "Sch Time",         "default": "08:30",             "type": "sch",  "help": "Waktu eksekusi otomatis (HH:mm)"},
            {"arg": "sch-active",  "label": "Sch Active",       "default": "False",             "type": "bool", "help": "Aktifkan jadwal otomatis"},
        ],
    },
    "CREATE BG JOB ZSMR012 – Split N Hari Scheduler": {
        "file": "schedule_zsmr012.py",
        "desc": "Membuat Background Job ZSMR012 di SAP per rentang N hari (default: 5 hari), dijadwalkan bertahap dengan jeda waktu teratur antar-job.",
        "params": [
            {"arg": "start-date",        "label": "Tanggal Awal",      "default": "2026-01-01", "type": "date", "help": "Format YYYY-MM-DD (Tanggal awal data laporan)"},
            {"arg": "end-date",          "label": "Tanggal Akhir",     "default": "2026-01-31", "type": "date", "help": "Format YYYY-MM-DD (Tanggal akhir data laporan)"},
            {"arg": "chunk-days",        "label": "Pecah per N Hari",  "default": "5",          "type": "int",  "help": "Ukuran rentang hari per background job (default 5)"},
            {"arg": "sched-start-date",  "label": "Tanggal Sched SAP", "default": "dynamic-today-ymd", "type": "date", "help": "Tanggal background job mulai dieksekusi di SAP"},
            {"arg": "sched-start-time",  "label": "Jam Sched Mulai",   "default": "17:00",      "type": "str",  "help": "Jam mulai BG job pertama (HH:MM)"},
            {"arg": "interval-minutes",  "label": "Interval Antar Job","default": "5",          "type": "int",  "help": "Jarak antar jadwal BG job di SAP (menit)"},
            {"arg": "delay-seconds",     "label": "Delay Submit (s)",  "default": "5",          "type": "int",  "help": "Jeda waktu antar submit script ke SAP (detik)"},
            {"arg": "vbs-path",          "label": "Path VBS",          "default": "vbs\\ZSMR012-per 5 hari.vbs", "type": "path", "help": "Lokasi file VBScript ZSMR012"},
            {"arg": "sch-time",          "label": "Sch Time",          "default": "08:00",      "type": "sch",  "help": "Waktu eksekusi otomatis dashboard (HH:mm)"},
            {"arg": "sch-active",        "label": "Sch Active",        "default": "False",      "type": "bool", "help": "Aktifkan jadwal otomatis dashboard"},
        ],
    },
    "DOWNLOAD BG JOB ZSMR012 – SAP Background Job": {
        "file": "download_zsmr012.py",
        "desc": "Download hasil spool Background Job ZSMR012 dari SM37 (Job Name: ZAGDSM_R00012, status FINISHED, From Date H-1 s/d To Date Hari Ini).",
        "params": [
            {"arg": "to-date",      "label": "Tanggal (To Date)", "default": "dynamic-today-dmy",     "type": "str",  "help": "Format dd.MM.yyyy (Tanggal akhir pencarian di SM37)"},
            {"arg": "from-date",    "label": "From Date (H-1)",   "default": "dynamic-yesterday-dmy", "type": "str",  "help": "Format dd.MM.yyyy (Tanggal awal pencarian di SM37, default H-1)"},
            {"arg": "job-name",     "label": "Job Name SM37",     "default": "ZAGDSM_R00012",         "type": "str",  "help": "Nama background job di SM37"},
            {"arg": "save-path",    "label": "Save Path",         "default": "D:\\Kerja\\SS\\ZSMR012\\", "type": "path", "help": "Folder tujuan simpan file spool (wajib trailing \\)"},
            {"arg": "file-prefix",  "label": "File Prefix",       "default": "ZSMR012_",               "type": "str",  "help": "Awalan nama file output (misal ZSMR012_)"},
            {"arg": "vbs-path",     "label": "Path VBS",          "default": "vbs\\DownloadBGJob_ZSMR012.vbs", "type": "path", "help": "Lokasi VBS download ZSMR012"},
            {"arg": "insert-sql",   "label": "Upload SQL DesSy",  "default": "True",                  "type": "bool", "help": "Upload data ke database DesSy setelah download"},
            {"arg": "sch-time",     "label": "Sch Time",          "default": "07:15",                 "type": "sch",  "help": "Waktu eksekusi otomatis (HH:mm)"},
            {"arg": "sch-active",   "label": "Sch Active",        "default": "False",                 "type": "bool", "help": "Aktifkan jadwal otomatis"},
        ],
    },
    "CREATE BG JOB IW58 – Split N Hari Scheduler": {
        "file": "schedule_iw58.py",
        "desc": "Membuat Background Job IW58 di SAP per rentang N hari (default: 5 hari), dijadwalkan bertahap dengan jeda waktu teratur antar-job.",
        "params": [
            {"arg": "start-date",        "label": "Tanggal Awal",      "default": "2026-01-01", "type": "date", "help": "Format YYYY-MM-DD (Tanggal awal data laporan)"},
            {"arg": "end-date",          "label": "Tanggal Akhir",     "default": "2026-01-31", "type": "date", "help": "Format YYYY-MM-DD (Tanggal akhir data laporan)"},
            {"arg": "chunk-days",        "label": "Pecah per N Hari",  "default": "5",          "type": "int",  "help": "Ukuran rentang hari per background job (default 5)"},
            {"arg": "sched-start-date",  "label": "Tanggal Sched SAP", "default": "dynamic-today-ymd", "type": "date", "help": "Tanggal background job mulai dieksekusi di SAP"},
            {"arg": "sched-start-time",  "label": "Jam Sched Mulai",   "default": "17:45",      "type": "str",  "help": "Jam mulai BG job pertama (HH:MM)"},
            {"arg": "interval-minutes",  "label": "Interval Antar Job","default": "5",          "type": "int",  "help": "Jarak antar jadwal BG job di SAP (menit)"},
            {"arg": "delay-seconds",     "label": "Delay Submit (s)",  "default": "5",          "type": "int",  "help": "Jeda waktu antar submit script ke SAP (detik)"},
            {"arg": "vbs-path",          "label": "Path VBS",          "default": "vbs\\IW58-per 5 hari.vbs", "type": "path", "help": "Lokasi file VBScript IW58"},
            {"arg": "sch-time",          "label": "Sch Time",          "default": "08:00",      "type": "sch",  "help": "Waktu eksekusi otomatis dashboard (HH:mm)"},
            {"arg": "sch-active",        "label": "Sch Active",        "default": "False",      "type": "bool", "help": "Aktifkan jadwal otomatis dashboard"},
        ],
    },
    "DOWNLOAD BG JOB IW58 – SAP Background Job": {
        "file": "download_iw58.py",
        "desc": "Download hasil spool Background Job IW58 dari SM37 (Job Name: RIQMEL20, status FINISHED, From Date H-1 s/d To Date Hari Ini).",
        "params": [
            {"arg": "to-date",      "label": "Tanggal (To Date)", "default": "dynamic-today-dmy",     "type": "str",  "help": "Format dd.MM.yyyy (Tanggal akhir pencarian di SM37)"},
            {"arg": "from-date",    "label": "From Date (H-1)",   "default": "dynamic-yesterday-dmy", "type": "str",  "help": "Format dd.MM.yyyy (Tanggal awal pencarian di SM37, default H-1)"},
            {"arg": "job-name",     "label": "Job Name SM37",     "default": "RIQMEL20",              "type": "str",  "help": "Nama background job di SM37"},
            {"arg": "save-path",    "label": "Save Path",         "default": "D:\\Kerja\\SS\\IW58\\",   "type": "path", "help": "Folder tujuan simpan file spool (wajib trailing \\)"},
            {"arg": "file-prefix",  "label": "File Prefix",       "default": "IW58_",                 "type": "str",  "help": "Awalan nama file output (misal IW58_)"},
            {"arg": "vbs-path",     "label": "Path VBS",          "default": "vbs\\DownloadBGJob_IW58.vbs", "type": "path", "help": "Lokasi VBS download IW58"},
            {"arg": "insert-sql",   "label": "Upload SQL DesSy",  "default": "True",                  "type": "bool", "help": "Upload data ke database DesSy setelah download"},
            {"arg": "sch-time",     "label": "Sch Time",          "default": "07:20",                 "type": "sch",  "help": "Waktu eksekusi otomatis (HH:mm)"},
            {"arg": "sch-active",   "label": "Sch Active",        "default": "False",                 "type": "bool", "help": "Aktifkan jadwal otomatis"},
        ],
    },
    "CREATE BG JOB IW73 – Split N Hari Scheduler": {
        "file": "schedule_iw73.py",
        "desc": "Memecah rentang tanggal (GSTRP-LOW s/d GSTRP-HIGH) menjadi batch per-N hari dan menjadwalkan eksekusi background job di SAP IW73 secara bertahap.",
        "params": [
            {"arg": "start-date",        "label": "Tanggal Awal",      "default": "2026-01-01", "type": "date", "help": "Format YYYY-MM-DD (Tanggal awal rentang filter GSTRP)"},
            {"arg": "end-date",          "label": "Tanggal Akhir",     "default": "2026-01-31", "type": "date", "help": "Format YYYY-MM-DD (Tanggal akhir rentang filter GSTRP)"},
            {"arg": "chunk-days",        "label": "Pecah per N Hari",  "default": "5",          "type": "int",  "help": "Jumlah hari per batch (default 5 hari)"},
            {"arg": "sched-start-date",  "label": "Tanggal Sched SAP", "default": "dynamic-today-ymd", "type": "date", "help": "Format YYYY-MM-DD (Tanggal eksekusi job pertama di server SAP)"},
            {"arg": "sched-start-time",  "label": "Jam Mulai Sched",   "default": "17:45",      "type": "str",  "help": "Jam mulai job pertama di server SAP (HH:mm)"},
            {"arg": "interval-minutes",  "label": "Interval (menit)",  "default": "5",          "type": "int",  "help": "Jarak antar job SAP dalam satuan menit"},
            {"arg": "delay-seconds",     "label": "Delay Submit (dtk)","default": "5",          "type": "int",  "help": "Jeda antar pengiriman batch ke SAP GUI"},
            {"arg": "vbs-path",          "label": "Path VBS",          "default": "vbs\\IW73-per 5 hari.vbs", "type": "path", "help": "Lokasi file VBScript IW73"},
            {"arg": "sch-time",          "label": "Sch Time",          "default": "08:00",      "type": "sch",  "help": "Waktu eksekusi otomatis dashboard (HH:mm)"},
            {"arg": "sch-active",        "label": "Sch Active",        "default": "False",      "type": "bool", "help": "Aktifkan jadwal otomatis dashboard"},
        ],
    },
    "DOWNLOAD BG JOB IW73 – SAP Background Job": {
        "file": "download_iw73.py",
        "desc": "Download hasil spool Background Job IW73 dari SM37 (Job Name: RIAUFK20, status FINISHED, From Date H-1 s/d To Date Hari Ini).",
        "params": [
            {"arg": "to-date",      "label": "Tanggal (To Date)", "default": "dynamic-today-dmy",     "type": "str",  "help": "Format dd.MM.yyyy (Tanggal akhir pencarian di SM37)"},
            {"arg": "from-date",    "label": "From Date (H-1)",   "default": "dynamic-yesterday-dmy", "type": "str",  "help": "Format dd.MM.yyyy (Tanggal awal pencarian di SM37, default H-1)"},
            {"arg": "job-name",     "label": "Job Name SM37",     "default": "RIAUFK20",              "type": "str",  "help": "Nama background job di SM37"},
            {"arg": "save-path",    "label": "Save Path",         "default": "D:\\Kerja\\SS\\IW73\\",   "type": "path", "help": "Folder tujuan simpan file spool (wajib trailing \\)"},
            {"arg": "file-prefix",  "label": "File Prefix",       "default": "IW73_",                 "type": "str",  "help": "Awalan nama file output (misal IW73_)"},
            {"arg": "vbs-path",     "label": "Path VBS",          "default": "vbs\\DownloadBGJob_IW73.vbs", "type": "path", "help": "Lokasi VBS download IW73"},
            {"arg": "insert-sql",   "label": "Upload SQL DesSy",  "default": "True",                  "type": "bool", "help": "Upload data ke database DesSy setelah download"},
            {"arg": "sch-time",     "label": "Sch Time",          "default": "07:25",                 "type": "sch",  "help": "Waktu eksekusi otomatis (HH:mm)"},
            {"arg": "sch-active",   "label": "Sch Active",        "default": "False",                 "type": "bool", "help": "Aktifkan jadwal otomatis"},
        ],
    },
    "MERAPIHKAN HASIL DOWNLOAD – ZSMR012": {
        "file": "process_zsmr012.py",
        "desc": "Membaca file teks ZSMR012_*.txt di folder, normalisasi tanggal/jam & angka, lalu upload ke tabel dbo.ZSMR012 di database DesSy.",
        "params": [
            {"arg": "folder",  "label": "Folder",  "default": "D:\\Kerja\\SS\\ZSMR012\\", "type": "path", "help": "Folder penyimpanan file teks ZSMR012"},
            {"arg": "periode", "label": "Periode", "default": "dynamic-today-ymd",        "type": "date", "help": "Tanggal penanda periode di database (YYYY-MM-DD)"},
        ],
    },
    "MERAPIHKAN HASIL DOWNLOAD – IW58 (Notif)": {
        "file": "process_iw58.py",
        "desc": "Membaca file teks IW58_*.txt di folder, normalisasi data notifikasi, lalu upload ke tabel dbo.Notif di database DesSy.",
        "params": [
            {"arg": "folder",  "label": "Folder",  "default": "D:\\Kerja\\SS\\IW58\\", "type": "path", "help": "Folder penyimpanan file teks IW58"},
            {"arg": "periode", "label": "Periode", "default": "dynamic-today-ymd",     "type": "date", "help": "Tanggal penanda periode di database (YYYY-MM-DD)"},
        ],
    },
    "MERAPIHKAN HASIL DOWNLOAD – IW73 (Service)": {
        "file": "process_iw73.py",
        "desc": "Membaca file teks IW73_*.txt di folder, normalisasi data order service, lalu upload ke tabel dbo.Service di database DesSy.",
        "params": [
            {"arg": "folder",  "label": "Folder",  "default": "D:\\Kerja\\SS\\IW73\\", "type": "path", "help": "Folder penyimpanan file teks IW73"},
            {"arg": "periode", "label": "Periode", "default": "dynamic-today-ymd",     "type": "date", "help": "Tanggal penanda periode di database (YYYY-MM-DD)"},
        ],
    },
}


def resolve_default(default):
    """Ubah sentinel tanggal dinamis menjadi tanggal hari ini atau kemarin."""
    if default == "dynamic-today-dmy":
        return datetime.now().strftime("%d.%m.%Y")
    if default == "dynamic-today-ymd":
        return datetime.now().strftime("%Y-%m-%d")
    if default == "dynamic-yesterday-dmy":
        return (datetime.now() - timedelta(days=1)).strftime("%d.%m.%Y")
    if default == "dynamic-yesterday-ymd":
        return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    return default


# Kunci yang diizinkan pada level atas job_config.json (selain nama job)
_ALLOWED_TOP_LEVEL_KEYS = {"db_settings"}


def validate_job_config(config: dict) -> tuple[bool, list[str]]:
    """
    Validasi struktur dasar job_config.json.

    Aturan yang diperiksa:
    1. Setiap key di level atas config harus berupa nama job di SCRIPTS
       atau salah satu key sistem yang diizinkan (``_ALLOWED_TOP_LEVEL_KEYS``).
    2. Setiap arg yang tersimpan untuk sebuah job harus dikenal oleh
       definisi job tersebut di SCRIPTS.
    3. ``db_settings`` (jika ada) harus berupa dict.

    Fungsi ini TIDAK menghentikan aplikasi — ia hanya mengumpulkan warning
    dan mengembalikannya bersama flag boolean.

    Returns:
        (is_valid, warnings)
        - is_valid  : True jika tidak ada warning sama sekali.
        - warnings  : Daftar string pesan peringatan.
    """
    warnings: list[str] = []

    if not isinstance(config, dict):
        return False, ["[validate_job_config] Config bukan dict — file mungkin rusak."]

    known_job_args: dict[str, set[str]] = {
        name: {p["arg"] for p in info["params"]}
        for name, info in SCRIPTS.items()
    }

    for key, value in config.items():
        # Lewati kunci sistem yang diizinkan
        if key in _ALLOWED_TOP_LEVEL_KEYS:
            if key == "db_settings" and not isinstance(value, dict):
                warnings.append(
                    f"[validate_job_config] 'db_settings' bukan dict — nilai: {value!r}"
                )
            continue

        # Key harus merupakan nama job yang dikenal
        if key not in SCRIPTS:
            warnings.append(
                f"[validate_job_config] Key tidak dikenal di config: '{key}'"
            )
            continue

        # Setiap arg dalam job harus dikenal
        if not isinstance(value, dict):
            warnings.append(
                f"[validate_job_config] Nilai job '{key}' bukan dict — nilai: {value!r}"
            )
            continue

        allowed_args = known_job_args[key]
        for arg in value:
            if arg not in allowed_args:
                warnings.append(
                    f"[validate_job_config] Job '{key}': arg tidak dikenal '{arg}'"
                )

    return len(warnings) == 0, warnings


def build_cli_args(name: str, params: dict, db_config: dict | None = None) -> list[str]:
    """
    Bangun daftar argumen CLI untuk subprocess.

    - Parameter berawalan 'sch-' (scheduling internal dashboard) di-skip.
    - Argumen --db-* hanya ditambahkan untuk script di DB_ARG_SCRIPTS.
    """
    args: list[str] = []
    for p in SCRIPTS[name]["params"]:
        arg = p["arg"]
        val = str(params.get(arg, "")).strip()
        if val and not arg.startswith("sch-"):
            args += [f"--{arg}", val]

    if db_config and SCRIPTS[name]["file"] in DB_ARG_SCRIPTS:
        args += ["--db-server", str(db_config.get("server", ""))]
        args += ["--db-user", str(db_config.get("user", ""))]
        args += ["--db-pwd", str(db_config.get("pwd", ""))]
        args += ["--db-name", str(db_config.get("name", ""))]

    return args
