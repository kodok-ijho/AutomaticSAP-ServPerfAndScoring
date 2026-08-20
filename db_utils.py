"""db_utils.py — Modul utilitas database terpusat untuk SAP Automation.

Menggabungkan pola berulang yang sebelumnya tersebar di:
  - automate_zsme09e.py   (delete-by-periode, executemany, parse_sap_int, read_text_with_fallback)
  - ProcessKE30byEq.py    (delete-by-periode, executemany, is_sap_numeric)
  - ProsesKE30byDiv.py    (delete-by-periode, executemany, is_sap_numeric)
  - process_reports.py    (format_universal_num)
  - db.py                 (get_connection — di-extend dengan retry)

Catatan: `db.py` tetap dipertahankan sebagai alias sederhana agar import
lama (`from db import get_connection`) tidak rusak.
"""

import sys
import time
import pyodbc

from config import DB_CONFIG, get_connection_string


# ---------------------------------------------------------------------------
#  Koneksi Database
# ---------------------------------------------------------------------------

def get_connection_with_retry(
    cfg: dict | None = None,
    retries: int = 3,
    delay: int = 5,
    **kwargs,
) -> "pyodbc.Connection":
    """Buka koneksi pyodbc baru dengan mekanisme retry.

    Args:
        cfg: Dict konfigurasi DB (server, user, pwd, name/db).
             Jika None, pakai DB_CONFIG dari config.py.
        retries: Jumlah percobaan maksimal.
        delay: Jeda antar percobaan (detik).

    Returns:
        pyodbc.Connection yang sudah terbuka.

    Raises:
        pyodbc.Error: Jika semua percobaan gagal.
    """
    if "max_retries" in kwargs:
        retries = kwargs["max_retries"]
    if "base_delay" in kwargs:
        delay = int(kwargs["base_delay"])

    effective_cfg = cfg or DB_CONFIG
    conn_str = get_connection_string(effective_cfg)
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            conn = pyodbc.connect(conn_str)
            if attempt > 1:
                print(f"[DB] Koneksi berhasil pada percobaan ke-{attempt}.")
            return conn
        except pyodbc.Error as e:
            last_error = e
            if attempt < retries:
                print(
                    f"[DB] Koneksi gagal (percobaan {attempt}/{retries}): {e}. "
                    f"Retry dalam {delay}s..."
                )
                time.sleep(delay)
            else:
                print(f"[DB] Koneksi gagal setelah {retries} percobaan: {e}")

    raise last_error  # type: ignore[misc]


# ---------------------------------------------------------------------------
#  Operasi SQL — Delete & Insert Batch
# ---------------------------------------------------------------------------

def delete_by_periode(cursor, table_name: str, periode: str) -> int:
    """Hapus semua baris dari ``table_name`` yang Periode-nya cocok.

    Returns:
        Jumlah baris yang dihapus.
    """
    cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE Periode = ?", (periode,))
    existing = cursor.fetchone()[0]
    if existing > 0:
        print(f"[SQL] Ditemukan {existing} baris periode {periode} di {table_name}. Menghapus dulu...")
        cursor.execute(f"DELETE FROM {table_name} WHERE Periode = ?", (periode,))
    else:
        print(f"[SQL] Belum ada data periode {periode} di {table_name}. Langsung insert.")
    return existing


def insert_batch(
    cursor,
    table_name: str,
    columns: list[str],
    data: list[tuple],
    chunk_size: int = 1000,
) -> int:
    """Insert batch data menggunakan ``executemany`` secara bertahap (chunked).

    Membagi data ke dalam chunk (default 1000 baris) untuk mencegah C-buffer deadlock / freeze
    pada pyodbc saat mengupload dataset besar dengan banyak kolom.

    Args:
        cursor: pyodbc cursor (sebaiknya dengan ``fast_executemany = True``).
        table_name: Nama tabel tujuan.
        columns: Daftar nama kolom (urutan harus sesuai ``data``).
        data: List of tuple, tiap tuple = 1 baris data (tipe data Python native).
        chunk_size: Jumlah baris per batch (default 1000).

    Returns:
        Jumlah baris yang di-insert.
    """
    col_str = ", ".join(f"[{c}]" for c in columns)
    placeholders = ", ".join(["?"] * len(columns))
    query = f"INSERT INTO {table_name} ({col_str}) VALUES ({placeholders})"
    total = len(data)
    print(f"[SQL] Mengupload {total} baris ke {table_name}...")
    sys.stdout.flush()

    for i in range(0, total, chunk_size):
        chunk = data[i : i + chunk_size]
        cursor.executemany(query, chunk)
        print(f"[SQL] Uploaded chunk {min(i + chunk_size, total)}/{total} baris...")
        sys.stdout.flush()

    return total


# ---------------------------------------------------------------------------
#  Normalisasi Angka Format SAP
# ---------------------------------------------------------------------------

def clean_sap_number(value) -> float | None:
    """Normalisasi angka format SAP ke float Python.

    Menangani format SAP yang umum:
      - ``1.234,56`` → ``1234.56``  (titik = ribuan, koma = desimal)
      - ``322.361-`` → ``-322361``  (trailing minus)
      - ``1.234``    → ``1234``     (ribuan saja, tanpa desimal)

    Returns:
        float, atau None jika value kosong/tidak bisa diparse.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        import math
        if math.isnan(value):
            return None
        return float(value)

    text = str(value).strip()
    if text == "" or text.lower() == "nan":
        return None

    # Tangani trailing minus dari SAP
    is_negative = False
    if text.endswith("-"):
        is_negative = True
        text = text[:-1].strip()
    elif text.startswith("-"):
        is_negative = True
        text = text[1:].strip()

    # Hapus titik (ribuan), ganti koma (desimal) jadi titik
    text = text.replace(".", "").replace(",", ".")

    try:
        num = float(text)
        return -num if is_negative else num
    except ValueError:
        return None


def is_sap_numeric(value) -> bool:
    """Cek apakah ``value`` merupakan angka format SAP yang valid.

    Returns:
        True jika bisa diparsing jadi angka, False jika tidak.
    """
    return clean_sap_number(value) is not None


def parse_sap_int(value) -> int | None:
    """Konversi angka format SAP ke integer (dibulatkan).

    Returns:
        int, atau None jika gagal.
    """
    num = clean_sap_number(value)
    if num is None:
        return None
    return int(round(num))


def format_sap_number_display(value) -> str:
    """Format angka SAP ke string bersih untuk output/display.

    Sama seperti ``format_universal_num`` lama di ``process_reports.py``.
    Returns:
        String angka bersih, atau string kosong jika kosong/NaN.
    """
    num = clean_sap_number(value)
    if num is None:
        return ""
    if num == int(num):
        return str(int(num))
    return str(num)


# ---------------------------------------------------------------------------
#  Deteksi Encoding File
# ---------------------------------------------------------------------------

def detect_file_encoding(file_path: str) -> str:
    """Deteksi encoding file dengan cara mencoba membaca secara fallback.

    Urutan percobaan: utf-16, utf-8-sig, cp1252, latin1.

    Args:
        file_path: Path ke file yang mau dideteksi encoding-nya.

    Returns:
        Nama encoding yang berhasil.

    Raises:
        UnicodeError: Jika semua encoding gagal.
    """
    last_error = None
    for encoding in ("utf-16", "utf-8-sig", "cp1252", "latin1"):
        try:
            with open(file_path, "r", encoding=encoding) as fh:
                fh.read(1024)  # Cukup baca sedikit untuk validasi
            return encoding
        except UnicodeError as e:
            last_error = e
    raise last_error or UnicodeError(f"Gagal mendeteksi encoding: {file_path}")


def read_text_with_fallback(file_path: str) -> tuple[str, str]:
    """Baca seluruh isi file teks dengan encoding fallback.

    Urutan percobaan: utf-16, utf-8-sig, cp1252, latin1.

    Returns:
        Tuple (content: str, encoding_name: str).

    Raises:
        UnicodeError: Jika semua encoding gagal.
    """
    last_error = None
    for encoding in ("utf-16", "utf-8-sig", "cp1252", "latin1"):
        try:
            with open(file_path, "r", encoding=encoding) as fh:
                return fh.read(), encoding
        except UnicodeError as e:
            last_error = e
    raise last_error or UnicodeError(f"Gagal membaca file: {file_path}")
