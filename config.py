"""
Konfigurasi terpusat untuk aplikasi SAP Automation.

WAJIB: Buat file .env di folder yang sama dengan script ini sebelum menjalankan
aplikasi. Salin dari .env.example dan isi dengan nilai yang sesuai.

Cara pakai:
    from config import DB_CONFIG, get_connection_string, SAP_USERNAME

Aturan:
  - Credential SENSITIF (password, user DB) WAJIB ada di .env.
    Jika tidak ditemukan, aplikasi akan berhenti dengan pesan error yang jelas.
  - Nilai non-sensitif (server, nama DB, driver, SAP connection string) memiliki
    fallback aman agar tidak perlu diubah jika environment identik.
  - JANGAN pernah hardcode credential di script ini atau file lainnya.
"""
import os

# Muat .env. Wajib ada — aplikasi tidak akan berjalan tanpa credential yang benar.
env_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
try:
    from dotenv import load_dotenv
    load_dotenv(env_file_path)
except ImportError:
    if os.path.exists(env_file_path):
        try:
            with open(env_file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass


def _env(key: str, default: str = "") -> str:
    """Ambil nilai dari environment, fallback ke default bila kosong/None."""
    val = os.environ.get(key)
    return val if val not in (None, "") else default


def _env_required(key: str) -> str:
    """
    Ambil nilai WAJIB dari environment.

    Raise ValueError dengan pesan jelas jika key tidak ditemukan atau kosong,
    sehingga aplikasi tidak pernah berjalan dengan credential yang tidak valid.
    """
    val = os.environ.get(key)
    if val in (None, ""):
        raise ValueError(
            f"\n[CONFIG ERROR] Variabel '{key}' tidak ditemukan atau kosong.\n"
            f"  Solusi: Tambahkan baris berikut ke file .env di folder project:\n"
            f"    {key}=<nilai_anda>\n"
            f"  Pastikan file .env ada dan python-dotenv sudah terinstall.\n"
        )
    return val


# ── Database (SQL Server) ──────────────────────────────────────────────────────
# Server, nama DB, dan driver: tidak sensitif — fallback ke nilai default yang umum.
# User dan password: SENSITIF — wajib ada di .env, tidak ada fallback.
DB_CONFIG = {
    "server": _env("DB_SERVER", "172.31.151.88"),
    "user":   _env_required("DB_USER"),
    "pwd":    _env_required("DB_PASSWORD"),
    "name":   _env("DB_NAME", "DesSy"),
    "driver": _env("DB_DRIVER", "ODBC Driver 17 for SQL Server"),
}


def get_connection_string(cfg: dict | None = None) -> str:
    """Bangun ODBC connection string dari konfigurasi (default: DB_CONFIG)."""
    c = cfg or DB_CONFIG
    return (
        f"DRIVER={{{c.get('driver', DB_CONFIG['driver'])}}};"
        f"SERVER={c['server']};DATABASE={c.get('name') or c.get('db')};"
        f"UID={c['user']};PWD={c['pwd']}"
    )


# ── SAP Credentials ────────────────────────────────────────────────────────────
# SAP_USERNAME: tidak terlalu sensitif, ada fallback ke user default.
# SAP_PASSWORD: SENSITIF — wajib ada di .env, tidak ada fallback.
# SAP_CONNECTION: nama koneksi di SAP Logon, bukan secret — ada fallback.
SAP_USERNAME   = _env("SAP_USERNAME", "2436dyu")
SAP_PASSWORD   = _env_required("SAP_PASSWORD")
SAP_CONNECTION = _env("SAP_CONNECTION", "SAP HANA AGDS PROD")
