"""
Helper koneksi database terpusat untuk SAP Automation.

Menggantikan connection string yang sebelumnya diduplikasi di banyak script.

Cara pakai:
    from db import get_connection
    with get_connection() as conn:
        cursor = conn.cursor()
        ...

Atau dengan override kredensial (mis. dari dashboard):
    get_connection({"server": ..., "user": ..., "pwd": ..., "name": ...})
"""
import pyodbc

from config import DB_CONFIG, get_connection_string


def get_connection(cfg: dict | None = None) -> "pyodbc.Connection":
    """Buka koneksi pyodbc baru. cfg opsional untuk override DB_CONFIG."""
    return pyodbc.connect(get_connection_string(cfg or DB_CONFIG))
