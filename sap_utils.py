"""sap_utils.py — Modul utilitas SAP GUI Scripting terpusat.

Menggabungkan fungsi-fungsi yang sebelumnya tersebar di:
  - automate_zsme09e.py  (verify_sap_ready, check_sap_login, run_vbs)
  - web_dashboard.py     (get_sap_status)

Ditambah fungsi baru:
  - ensure_sap_logged_in()  — login otomatis jika belum login.
"""

import os
import sys
import subprocess
import time

# Pastikan output stream menggunakan UTF-8 di Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


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


def get_cscript_cmd() -> str:
    """Gunakan 32-bit cscript jika ada di SysWOW64 untuk kompatibilitas SAP GUI 32-bit."""
    syswow64 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "SysWOW64", "cscript.exe")
    if os.path.isfile(syswow64):
        return syswow64
    return "cscript.exe"


def get_wscript_cmd() -> str:
    """Gunakan 32-bit wscript jika ada di SysWOW64 untuk kompatibilitas SAP GUI 32-bit."""
    syswow64 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "SysWOW64", "wscript.exe")
    if os.path.isfile(syswow64):
        return syswow64
    return "wscript.exe"


# ---------------------------------------------------------------------------
#  SAP GUI Check — versi andal via VBScript COM
# ---------------------------------------------------------------------------

def verify_sap_ready() -> bool:
    """Cek SAP GUI aktif DAN sudah login (tanpa menjalankan login otomatis).

    Mengembalikan True hanya bila: SAP GUI berjalan, ada koneksi+session,
    dan session TIDAK berada di layar login.
    """
    vbs_check = os.path.abspath(os.path.join(os.path.dirname(__file__), "vbs", "CheckSAPStatus.vbs"))
    if not os.path.exists(vbs_check):
        vbs_check = os.path.abspath(os.path.join("vbs", "CheckSAPStatus.vbs"))
    try:
        cscript_exe = get_cscript_cmd()
        res = subprocess.run([cscript_exe, "//Nologo", vbs_check], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            print("[OK] SAP GUI aktif dan sudah login.")
            return True
        else:
            out = res.stdout.strip()
            if "LOGIN_SCREEN" in out:
                print("[INFO] SAP terbuka tapi masih di layar login.")
            elif "NO_CONN" in out or "NO_SESS" in out:
                print("[INFO] SAP Logon terbuka tapi belum ada session koneksi aktif.")
            else:
                print(f"[INFO] SAP GUI belum login ({out or 'tidak ada respon'}).")
            return False
    except Exception as e:
        print(f"[WARN] Pengecekan status SAP: {e}")
        return False


def check_sap_login() -> bool:
    """Mengecek apakah ada session SAP yang BENAR-BENAR sudah login."""
    return verify_sap_ready()


# ---------------------------------------------------------------------------
#  VBS Runner
# ---------------------------------------------------------------------------

def run_vbs(vbs_path: str, args: list | None = None, interactive: bool = False) -> bool:
    """Menjalankan file VBS dengan argumen.

    Args:
        vbs_path: Path ke file VBS.
        args: Argumen tambahan.
        interactive: Jika True, gunakan wscript.exe (bisa menampilkan jendela GUI),
                     Jika False, gunakan cscript.exe //Nologo (background, output ke stdout).
    """
    if args is None:
        args = []
    full_path = os.path.abspath(vbs_path)
    if not os.path.exists(full_path):
        print(f"[ERROR] File VBS tidak ditemukan: {full_path}")
        return False

    try:
        if interactive:
            # wscript.exe: bisa membuka GUI window (SAP Logon), tapi tidak ada stdout capture
            cmd = [get_wscript_cmd(), full_path] + [str(a) for a in args]
            print(f"[VBS] Command (interactive): {' '.join(cmd)}")
            started = time.time()
            res = subprocess.run(cmd, capture_output=False, timeout=120)
            print(f"[VBS] Selesai dalam {time.time() - started:.1f} detik (Exit Code: {res.returncode}).")
            return res.returncode == 0
        else:
            # cscript.exe: tidak bisa membuka GUI window baru, tapi stdout ter-capture
            cmd = [get_cscript_cmd(), "//Nologo", full_path] + [str(a) for a in args]
            print(f"[VBS] Command: {' '.join(cmd)}")
            started = time.time()
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if res.stdout and res.stdout.strip():
                for line in res.stdout.strip().splitlines():
                    print(f"[VBS OUT] {line}")
            if res.stderr and res.stderr.strip():
                for line in res.stderr.strip().splitlines():
                    print(f"[VBS ERR] {line}")
            print(f"[VBS] Selesai dalam {time.time() - started:.1f} detik (Exit Code: {res.returncode}).")
            return res.returncode == 0
    except Exception as e:
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
        # PENTING: gunakan wscript.exe (interactive=True) agar jendela SAP Logon
        # bisa tampil di layar pengguna. cscript.exe tidak bisa membuka GUI window baru.
        login_ok = run_vbs(vbs_login_path, interactive=True)
        if not login_ok:
            print(f"[SAP] [Attempt {attempt}/{max_retries}] Gagal menjalankan VBS login.")
            if attempt < max_retries:
                time.sleep(3)
                continue
            return False

        print(f"[SAP] VBS login selesai. Menunggu SAP aktif (timeout {timeout}s)...")
        # Polling via CheckSAPStatus.vbs (cscript) untuk konfirmasi login berhasil
        poll_interval = 2
        elapsed = 0
        while elapsed < timeout:
            time.sleep(poll_interval)
            elapsed += poll_interval

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
