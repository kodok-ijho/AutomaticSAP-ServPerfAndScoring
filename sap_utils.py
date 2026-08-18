"""sap_utils.py — Modul utilitas SAP GUI Scripting terpusat.

Menggabungkan fungsi-fungsi yang sebelumnya tersebar di:
  - automate_zsme09e.py  (verify_sap_ready, check_sap_login, run_vbs)
  - web_dashboard.py     (get_sap_status)

Ditambah fungsi baru:
  - ensure_sap_logged_in()  — login otomatis jika belum login.
"""

import os
import subprocess
import time


# ---------------------------------------------------------------------------
#  SAP GUI Status — versi detail (dict), untuk dashboard/web
# ---------------------------------------------------------------------------

def get_sap_status() -> dict:
    """Cek status SAP GUI Scripting secara read-only (tidak mengubah apa pun).

    Returns:
        dict berisi kunci:
          available (bool), connections (int), sessions (int),
          disabled_by_server (bool|None), logged_in (bool),
          messages (list[str]).
    """
    result = {
        "available": False,
        "connections": 0,
        "sessions": 0,
        "disabled_by_server": None,
        "logged_in": False,
        "messages": [],
    }
    try:
        import win32com.client
    except ImportError:
        result["messages"].append("Modul pywin32 belum terinstall.")
        return result

    try:
        sap = win32com.client.GetObject("SAPGUI")
        app_engine = sap.GetScriptingEngine
    except Exception:
        result["messages"].append(
            "SAP GUI tidak berjalan / scripting engine tidak tersedia. Buka SAP Logon dulu."
        )
        return result

    result["available"] = True
    try:
        result["connections"] = app_engine.Children.Count
    except Exception:
        result["connections"] = 0

    if result["connections"] == 0:
        result["messages"].append("SAP GUI terbuka tapi belum ada koneksi.")
        return result

    conn = app_engine.Children(0)
    try:
        result["disabled_by_server"] = bool(conn.DisabledByServer)
    except Exception:
        result["disabled_by_server"] = None
    try:
        result["sessions"] = conn.Children.Count
    except Exception:
        result["sessions"] = 0

    if result["disabled_by_server"]:
        result["messages"].append(
            "SCRIPTING DIBLOKIR SERVER (DisabledByServer=True). "
            "Minta Basis set sapgui/user_scripting=TRUE."
        )

    if result["sessions"] == 0:
        result["messages"].append("Tidak ada session yang bisa di-script.")
    else:
        try:
            sess = conn.Children(0)
            try:
                sess.findById("wnd[0]/usr/txtRSYST-BNAME")
                result["logged_in"] = False
                result["messages"].append("Session ada, tapi masih di layar login.")
            except Exception:
                result["logged_in"] = True
                result["messages"].append("Session aktif & sudah login. Scripting OK.")
        except Exception:
            pass

    return result


# ---------------------------------------------------------------------------
#  SAP GUI Check — versi sederhana (bool), untuk script CLI
# ---------------------------------------------------------------------------

def verify_sap_ready() -> bool:
    """Cek SAP GUI aktif DAN sudah login (tanpa menjalankan login otomatis).

    Mengembalikan True hanya bila: SAP GUI berjalan, ada koneksi+session,
    dan session TIDAK berada di layar login.
    """
    try:
        import win32com.client
        sap = win32com.client.GetObject("SAPGUI")
        app = sap.GetScriptingEngine
    except Exception:
        print("[ERROR] SAP GUI tidak aktif. Buka SAP GUI dan login terlebih dahulu.")
        return False

    print("[OK] SAP GUI aktif.")

    try:
        if app.Children.Count == 0:
            print("[ERROR] SAP GUI aktif tapi belum ada koneksi. Buka koneksi & login dulu.")
            return False
        conn = app.Children(0)
        # Pastikan scripting tidak diblokir server
        try:
            if bool(conn.DisabledByServer):
                print("[ERROR] Scripting diblokir server (DisabledByServer=True). Hubungi Basis.")
                return False
        except Exception:
            pass
        if conn.Children.Count == 0:
            print("[ERROR] Belum ada session SAP. Login terlebih dahulu.")
            return False
        sess = conn.Children(0)
        try:
            sess.findById("wnd[0]/usr/txtRSYST-BNAME")
            print("[ERROR] SAP masih di layar login. Login terlebih dahulu, lalu jalankan ulang.")
            return False
        except Exception:
            print("[OK] SAP sudah login.")
            return True
    except Exception as e:
        print(f"[ERROR] Gagal mengecek status SAP: {e}")
        return False


def check_sap_login() -> bool:
    """Mengecek apakah ada session SAP yang BENAR-BENAR sudah login.

    Catatan: session yang masih berada di layar login (field username
    'wnd[0]/usr/txtRSYST-BNAME' masih ada) dianggap BELUM login.
    """
    try:
        import win32com.client
        sap_gui = win32com.client.GetObject("SAPGUI")
        application = sap_gui.GetScriptingEngine
        if application.Children.Count > 0:
            connection = application.Children(0)
            if connection.Children.Count > 0:
                session = connection.Children(0)
                try:
                    # Kalau field username masih ada -> masih di layar login.
                    session.findById("wnd[0]/usr/txtRSYST-BNAME")
                    print("[INFO] SAP terbuka tapi masih di layar login (belum login).")
                    return False
                except Exception:
                    print("[INFO] SAP sudah terlogin.")
                    return True
    except Exception:
        pass
    print("[INFO] SAP belum login.")
    return False


# ---------------------------------------------------------------------------
#  VBS Runner
# ---------------------------------------------------------------------------

def run_vbs(vbs_path: str, args: list | None = None) -> bool:
    """Menjalankan file VBS dengan argumen.

    Menggunakan subprocess.run dengan daftar argumen (shell=False) agar:
    - Path dengan spasi tidak perlu di-quote manual.
    - Tidak ada risiko shell injection dari nilai argumen.
    """
    if args is None:
        args = []
    full_path = os.path.abspath(vbs_path)
    if not os.path.exists(full_path):
        print(f"[ERROR] File VBS tidak ditemukan: {full_path}")
        return False

    try:
        # Argumen sebagai list — wscript.exe menangani path dan args langsung,
        # tanpa perlu shell=True atau quoting manual.
        cmd = ["wscript.exe", full_path] + [str(a) for a in args]
        print(f"[VBS] Command: {' '.join(cmd)}")
        started = time.time()
        subprocess.run(cmd, check=True)
        print(f"[VBS] Selesai dalam {time.time() - started:.1f} detik.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Gagal menjalankan {vbs_path}: {e}")
        return False


# ---------------------------------------------------------------------------
#  Login Otomatis  (Task 2.2)
# ---------------------------------------------------------------------------

def handle_multi_login_popup() -> bool:
    """Deteksi dan tangani popup dialog multi-login (mis. wnd[1] License/Multi-Logon popup).

    Jika pengguna sudah memiliki session terbuka, SAP menampilkan dialog pilihan:
      - Terminate this logon and execute new logon
      - Continue with this logon and end any other logons
      - Continue with this logon without ending any other logons

    Fungsi ini akan menekan Enter (vkey 0) pada modal dialog `wnd[1]` jika terdeteksi.

    Returns:
        True jika popup terdeteksi dan di-dismiss, False jika tidak ada popup.
    """
    try:
        import win32com.client
        sap_gui = win32com.client.GetObject("SAPGUI")
        application = sap_gui.GetScriptingEngine
        if application.Children.Count > 0:
            connection = application.Children(0)
            if connection.Children.Count > 0:
                session = connection.Children(0)
                try:
                    # Cek modal window wnd[1]
                    dlg = session.findById("wnd[1]")
                    if dlg:
                        print("[SAP] Terdeteksi popup dialog (mis. Multi-Logon/System Message). Menutup dialog...")
                        # Tekan Enter / Send VKey 0 di wnd[1]
                        try:
                            session.findById("wnd[1]/tbar[0]/btn[0]").press()
                        except Exception:
                            session.findById("wnd[1]").sendVKey(0)
                        return True
                except Exception:
                    pass
    except Exception:
        pass
    return False


def ensure_sap_logged_in(
    vbs_login_path: str,
    timeout: int = 60,
    max_retries: int = 3,
) -> bool:
    """Pastikan SAP sudah login; jika belum, jalankan VBS login otomatis dengan retry loop.

    Langkah:
      1. Panggil verify_sap_ready() — jika sudah login, return True langsung.
      2. Jika belum, jalankan VBS login (hingga max_retries kali jika gagal).
      3. Tangani popup multi-login (jika ada).
      4. Polling check_sap_login() setiap 2 detik sampai True atau timeout.

    Args:
        vbs_login_path: Path ke file VBS login (mis. ``vbs/LoginSAP.vbs``).
        timeout: Waktu maksimal menunggu login berhasil per percobaan (detik). Default 60.
        max_retries: Maksimal percobaan login jika percobaan pertama gagal. Default 3.

    Returns:
        True jika SAP sudah login (baik sudah siap maupun berhasil login),
        False jika gagal/timeout setelah semua retries.
    """
    print("[SAP] Mengecek status SAP GUI...")
    if verify_sap_ready():
        print("[SAP] SAP sudah login dan siap. Tidak perlu login ulang.")
        return True

    for attempt in range(1, max_retries + 1):
        print(f"[SAP] Mencoba login... ({attempt}/{max_retries}) via {vbs_login_path}")
        login_ok = run_vbs(vbs_login_path)
        if not login_ok:
            print(f"[SAP] [Attempt {attempt}/{max_retries}] Gagal menjalankan VBS login.")
            if attempt < max_retries:
                time.sleep(3)
                continue
            return False

        print(f"[SAP] VBS login selesai. Menunggu SAP aktif (timeout {timeout}s)...")
        poll_interval = 2
        elapsed = 0
        while elapsed < timeout:
            time.sleep(poll_interval)
            elapsed += poll_interval

            # Cek dan tangani jika ada dialog popup multi-login
            handle_multi_login_popup()

            if check_sap_login():
                print(f"[SAP] Login berhasil pada percobaan ke-{attempt} (setelah ~{elapsed}s).")
                return True
            print(f"[SAP] Belum login ({elapsed}s/{timeout}s)...")

        print(f"[SAP] Timeout {timeout}s pada percobaan ke-{attempt}.")
        if attempt < max_retries:
            print(f"[SAP] Mencoba ulang login dalam 3 detik...")
            time.sleep(3)

    print(f"[SAP] Gagal login SAP setelah {max_retries} percobaan.")
    return False
