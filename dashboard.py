import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import threading
import subprocess
import os
import sys
import queue
import json
import time
from datetime import datetime, timedelta

from config import DB_CONFIG
from job_definitions import SCRIPTS, resolve_default, build_cli_args, validate_job_config
from job_runner import (
    run_job as jr_run_job, stop_job as jr_stop_job,
    STATUS_IDLE, STATUS_RUNNING, STATUS_SUCCESS, STATUS_FAILED, STATUS_DISPLAY,
)

# ── Konfigurasi File ──────────────────────────────────────────────────────────
CONFIG_FILE = "job_config.json"

# ── Warna & Font ───────────────────────────────────────────────────────────────
SAP_BLUE        = "#003A70"
SAP_BLUE_LIGHT  = "#0070BD"
SAP_GREY_BG     = "#ECF0F1"
SAP_GREY_PANEL  = "#D0D7DE"
SAP_WHITE       = "#FFFFFF"
SAP_TOOLBAR     = "#C8D0D9"
SAP_BORDER      = "#A0A8B0"
SAP_TEXT        = "#1A1A2E"
SAP_SUCCESS     = "#1B8A35"
SAP_ERROR       = "#CC0000"
SAP_RUNNING     = "#0070BD"
SAP_PARAM_BG    = "#F5F8FA"
SAP_PARAM_HDR   = "#E1E8ED"

FONT_UI    = ("Arial", 9)
FONT_BOLD  = ("Arial", 9, "bold")
FONT_TITLE = ("Arial", 10, "bold")
FONT_MONO  = ("Courier New", 9)
FONT_SMALL = ("Arial", 8)

# ── Definisi Job dipindah ke modul bersama job_definitions.py ─────────────────
# (SCRIPTS dipakai bersama oleh dashboard.py & web_dashboard.py agar selalu sinkron)

# ── State global ──────────────────────────────────────────────────────────────
running_jobs: dict = {}
log_queue:    queue.Queue = queue.Queue()


class SAPDashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SAP Automation Dashboard – Service Performance")
        self.geometry("1200x760")
        self.minsize(950, 600)
        self.configure(bg=SAP_GREY_BG)

        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        # Menyimpan widget StringVar parameter per job
        self._param_vars: dict[str, list[tk.StringVar]] = {}
        self._last_triggered: dict[str, str] = {}  # Job -> YYYY-MM-DD HH:MM
        self._procs: dict = {}  # Job -> subprocess.Popen (untuk Stop)

        # Runtime parameter overrides — menyimpan nilai user TANPA mengubah SCRIPTS.
        # Format: {job_name: {arg_name: value_str, ...}, ...}
        self._runtime_params: dict[str, dict[str, str]] = {}
        # Runtime file overrides untuk "file" field job (dari detail panel)
        self._runtime_files: dict[str, str] = {}

        # Database Settings Variables
        self._db_server = tk.StringVar(value=DB_CONFIG["server"])
        self._db_user   = tk.StringVar(value=DB_CONFIG["user"])
        self._db_pwd    = tk.StringVar(value=DB_CONFIG["pwd"])
        self._db_name   = tk.StringVar(value=DB_CONFIG["name"])

        self._load_config()
        self._build_menu()
        self._build_toolbar()
        self._build_body()
        self._build_statusbar()
        self._process_log_queue()

        # Start Scheduler Thread
        threading.Thread(target=self._scheduler_loop, daemon=True).start()

    # ── Menu ──────────────────────────────────────────────────────────────────
    def _build_menu(self):
        mb = tk.Menu(self, font=FONT_UI, bg=SAP_TOOLBAR, fg=SAP_TEXT,
                     activebackground=SAP_BLUE, activeforeground=SAP_WHITE,
                     tearoff=False)
        m_sys = tk.Menu(mb, tearoff=False, font=FONT_UI)
        m_sys.add_command(label="Refresh",  command=self._refresh)
        m_sys.add_separator()
        m_sys.add_command(label="Exit",     command=self.destroy)
        mb.add_cascade(label="System", menu=m_sys)

        m_job = tk.Menu(mb, tearoff=False, font=FONT_UI)
        for name in SCRIPTS:
            m_job.add_command(label=f"Execute: {name}",
                              command=lambda n=name: self._run_job(n))
        mb.add_cascade(label="Job", menu=m_job)

        m_help = tk.Menu(mb, tearoff=False, font=FONT_UI)
        m_help.add_command(label="About", command=self._show_about)
        mb.add_cascade(label="Help", menu=m_help)
        self.config(menu=mb)

    # ── Toolbar ───────────────────────────────────────────────────────────────
    def _build_toolbar(self):
        bar = tk.Frame(self, bg=SAP_TOOLBAR, height=36, relief="raised", bd=1)
        bar.pack(side="top", fill="x")
        bar.pack_propagate(False)

        cfg = dict(font=FONT_BOLD, bg=SAP_TOOLBAR, fg=SAP_TEXT, relief="flat",
                   padx=10, pady=4, cursor="hand2",
                   activebackground=SAP_BLUE_LIGHT, activeforeground=SAP_WHITE)

        tk.Button(bar, text="▶  Execute Job", command=self._execute_selected, **cfg
                  ).pack(side="left", padx=2, pady=3)
        tk.Frame(bar, bg=SAP_BORDER, width=1).pack(side="left", fill="y", padx=4, pady=4)
        tk.Button(bar, text="⏹  Stop Job", command=self._stop_selected, **cfg
                  ).pack(side="left", padx=2, pady=3)
        tk.Frame(bar, bg=SAP_BORDER, width=1).pack(side="left", fill="y", padx=4, pady=4)
        tk.Button(bar, text="↺  Reset Params", command=self._reset_params, **cfg
                  ).pack(side="left", padx=2, pady=3)
        tk.Frame(bar, bg=SAP_BORDER, width=1).pack(side="left", fill="y", padx=4, pady=4)
        tk.Button(bar, text="⟳  Refresh", command=self._refresh, **cfg
                  ).pack(side="left", padx=2, pady=3)
        tk.Frame(bar, bg=SAP_BORDER, width=1).pack(side="left", fill="y", padx=4, pady=4)
        tk.Button(bar, text="🗑  Clear Log", command=self._clear_log, **cfg
                  ).pack(side="left", padx=2, pady=3)

        self._clock_var = tk.StringVar()
        tk.Label(bar, textvariable=self._clock_var, font=FONT_BOLD,
                 bg=SAP_TOOLBAR, fg=SAP_BLUE).pack(side="right", padx=12)
        self._update_clock()

    # ── Body ──────────────────────────────────────────────────────────────────
    def _build_body(self):
        pane = tk.PanedWindow(self, orient="horizontal", bg=SAP_GREY_BG,
                              sashwidth=5, sashrelief="flat", sashpad=2)
        pane.pack(fill="both", expand=True)

        left = tk.Frame(pane, bg=SAP_GREY_BG)
        pane.add(left, minsize=260, width=300)
        self._build_job_list(left)

        right = tk.Frame(pane, bg=SAP_GREY_BG)
        pane.add(right, minsize=550)
        self._build_right_panel(right)

    # ── Job List (kiri) ───────────────────────────────────────────────────────
    def _build_job_list(self, parent):
        hdr = tk.Frame(parent, bg=SAP_BLUE, height=28)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  📋  Job List", font=FONT_TITLE,
                 bg=SAP_BLUE, fg=SAP_WHITE).pack(side="left", padx=6, pady=4)

        frame = tk.Frame(parent, bg=SAP_GREY_BG)
        frame.pack(fill="both", expand=True, padx=4, pady=4)

        cols = ("job", "status", "last_run")
        self._tree = ttk.Treeview(frame, columns=cols, show="headings",
                                  selectmode="browse", height=20)
        self._tree.heading("job",      text="Job Name")
        self._tree.heading("status",   text="Status")
        self._tree.heading("last_run", text="Last Run")
        self._tree.column("job",      width=130, minwidth=100)
        self._tree.column("status",   width=72,  minwidth=60,  anchor="center")
        self._tree.column("last_run", width=72,  minwidth=60,  anchor="center")

        self._tree.tag_configure("ok",      foreground=SAP_SUCCESS)
        self._tree.tag_configure("error",   foreground=SAP_ERROR)
        self._tree.tag_configure("running", foreground=SAP_RUNNING)
        self._tree.tag_configure("idle",    foreground=SAP_TEXT)

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._tree.bind("<<TreeviewSelect>>", self._on_job_select)
        self._tree.bind("<Double-1>", lambda e: self._execute_selected())

        self._job_items: dict = {}
        for name in SCRIPTS:
            short = name.split("–")[0].strip()
            iid = self._tree.insert("", "end",
                                    values=(short, STATUS_DISPLAY[STATUS_IDLE], "—"),
                                    tags=(STATUS_IDLE,))
            self._job_items[name] = iid

        first = list(self._job_items.values())[0]
        self._tree.selection_set(first)
        self._selected_job: str = list(SCRIPTS.keys())[0]

    # ── Panel Kanan ───────────────────────────────────────────────────────────
    def _build_right_panel(self, parent):
        # ── Info bar singkat ──────────────────────────────────────────────────
        info_hdr = tk.Frame(parent, bg=SAP_BLUE, height=28)
        info_hdr.pack(fill="x", padx=6, pady=(6, 0))
        info_hdr.pack_propagate(False)
        tk.Label(info_hdr, text="  🔍  Job Detail & Parameters", font=FONT_TITLE,
                 bg=SAP_BLUE, fg=SAP_WHITE).pack(side="left", padx=6, pady=4)

        card = tk.Frame(parent, bg=SAP_WHITE, relief="solid", bd=1)
        card.pack(fill="x", padx=6)

        # Baris info (2 kolom: kaki=Job/Script/Schedule, kanan=desc)
        info_row = tk.Frame(card, bg=SAP_WHITE)
        info_row.pack(fill="x", padx=10, pady=(8, 4))

        left_info = tk.Frame(info_row, bg=SAP_WHITE)
        left_info.pack(side="left", fill="x", expand=True)

        self._detail_vars: dict = {}
        for lbl, key in [("Job Name", "name"), ("Script", "file"), ("Schedule", "sched"), ("Description", "desc")]:
            row = tk.Frame(left_info, bg=SAP_WHITE)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=f"{lbl}:", font=FONT_BOLD,
                     bg=SAP_WHITE, fg=SAP_BLUE, width=12, anchor="e"
                     ).pack(side="left", padx=(0, 6))
            var = tk.StringVar(value="—")
            self._detail_vars[key] = var
            
            if key == "file":
                # Entry + Browse for Script
                ent = tk.Entry(row, textvariable=var, font=FONT_UI, bg=SAP_WHITE,
                               relief="flat", highlightthickness=0, fg=SAP_TEXT)
                ent.pack(side="left", fill="x") # expand=True looks better but might push other things
                tk.Button(
                    row, text="…", font=FONT_SMALL,
                    bg=SAP_GREY_PANEL, fg=SAP_TEXT,
                    relief="flat", padx=6, pady=1, cursor="hand2",
                    command=lambda v=var: self._make_browse_cmd(v, "script")()
                ).pack(side="left", padx=(4, 10))
                # Add trace to update memory when file changes
                var.trace_add("write", lambda *args, v=var, k=key: self._on_detail_change(k, v))
            else:
                tk.Label(row, textvariable=var, font=FONT_UI, bg=SAP_WHITE,
                         fg=SAP_TEXT, anchor="w", wraplength=450
                         ).pack(side="left", fill="x")

        # ── Database Settings (New) ───────────────────────────────────────────
        tk.Frame(card, bg=SAP_GREY_PANEL, height=1).pack(fill="x", padx=10, pady=4)
        db_hdr = tk.Frame(card, bg=SAP_WHITE)
        db_hdr.pack(fill="x", padx=10)
        tk.Label(db_hdr, text="Database Settings:", font=FONT_BOLD, bg=SAP_WHITE, fg=SAP_BLUE).pack(side="left")
        
        db_form = tk.Frame(card, bg=SAP_WHITE)
        db_form.pack(fill="x", padx=10, pady=2)
        
        for lbl, var in [("Server", self._db_server), ("User", self._db_user), ("Password", self._db_pwd), ("DB Name", self._db_name)]:
            f = tk.Frame(db_form, bg=SAP_WHITE)
            f.pack(side="left", padx=(0, 10))
            tk.Label(f, text=lbl, font=FONT_SMALL, bg=SAP_WHITE, fg=SAP_BORDER).pack(side="top", anchor="w")
            tk.Entry(f, textvariable=var, font=FONT_SMALL, width=15, relief="solid", bd=1).pack(side="top")

        # ── Separator ─────────────────────────────────────────────────────────
        tk.Frame(card, bg=SAP_GREY_PANEL, height=1).pack(fill="x", padx=10, pady=4)

        # ── PARAMETER FORM ────────────────────────────────────────────────────
        param_hdr = tk.Frame(card, bg=SAP_PARAM_HDR)
        param_hdr.pack(fill="x", padx=0)
        tk.Label(param_hdr, text="  ⚙  Parameter Eksekusi", font=FONT_BOLD,
                 bg=SAP_PARAM_HDR, fg=SAP_BLUE).pack(side="left", padx=8, pady=4)
        tk.Label(param_hdr, text="(edit nilai sebelum Execute)",
                 font=FONT_SMALL, bg=SAP_PARAM_HDR, fg=SAP_BORDER
                 ).pack(side="left")

        # Container frame untuk parameter — akan di-rebuild saat pilih job lain
        self._param_container = tk.Frame(card, bg=SAP_PARAM_BG)
        self._param_container.pack(fill="x", padx=0, pady=0)

        # ── Tombol Execute ────────────────────────────────────────────────────
        btn_row = tk.Frame(card, bg=SAP_WHITE)
        btn_row.pack(fill="x", padx=10, pady=8)

        self._exec_btn = tk.Button(
            btn_row, text="▶  Execute Job",
            font=FONT_BOLD, bg=SAP_BLUE, fg=SAP_WHITE,
            relief="flat", padx=16, pady=6, cursor="hand2",
            activebackground=SAP_BLUE_LIGHT,
            command=self._execute_selected
        )
        self._exec_btn.pack(side="left")

        self._stop_btn = tk.Button(
            btn_row, text="⏹  Stop Job",
            font=FONT_UI, bg=SAP_ERROR, fg=SAP_WHITE,
            relief="flat", padx=10, pady=6, cursor="hand2",
            activebackground="#A00000",
            state="disabled",
            command=self._stop_selected
        )
        self._stop_btn.pack(side="left", padx=(8, 0))

        reset_btn = tk.Button(
            btn_row, text="↺  Reset Default",
            font=FONT_UI, bg=SAP_GREY_PANEL, fg=SAP_TEXT,
            relief="flat", padx=10, pady=6, cursor="hand2",
            activebackground=SAP_BORDER,
            command=self._reset_params
        )
        reset_btn.pack(side="left", padx=(8, 0))
        
        save_btn = tk.Button(
            btn_row, text="💾  Save Config",
            font=FONT_UI, bg=SAP_GREY_PANEL, fg=SAP_TEXT,
            relief="flat", padx=10, pady=6, cursor="hand2",
            activebackground=SAP_BORDER,
            command=self._save_config
        )
        save_btn.pack(side="left", padx=(8, 0))

        self._status_badge = tk.Label(btn_row, text=" ⬤  Idle ", font=FONT_BOLD,
                                      bg=SAP_WHITE, fg=SAP_TEXT, padx=8)
        self._status_badge.pack(side="left", padx=10)

        # ── Log Panel ─────────────────────────────────────────────────────────
        self._build_log_panel(parent)

        # Render parameter job pertama
        self._update_detail(list(SCRIPTS.keys())[0])

    def _make_browse_cmd(self, v, arg_name):
        """Buat fungsi browse yang bind ke var & arg_name tertentu."""
        def browse():
            current = v.get().strip()
            # Folder browser jika nama mengandung 'folder'/'save' atau nilai berakhir \
            is_folder = "folder" in arg_name.lower() or "save" in arg_name.lower() or current.endswith("\\")
            
            if is_folder:
                initial = current if os.path.isdir(current) else os.path.expanduser("~")
                result = filedialog.askdirectory(initialdir=initial, title="Pilih Folder")
                if result:
                    v.set(result.replace("/", "\\") + "\\")
            else:
                # File browser
                expanded = os.path.expandvars(current)
                if not os.path.isabs(expanded):
                    expanded = os.path.join(os.path.dirname(os.path.abspath(__file__)), expanded)
                
                initial = os.path.dirname(expanded) if os.path.exists(os.path.dirname(expanded)) else os.path.expanduser("~")
                
                # Filter file type
                if "script" in arg_name.lower() or current.endswith(".py"):
                    ft = [("Python Scripts", "*.py"), ("VBS scripts", "*.vbs"), ("Excel", "*.xlsx;*.xls"), ("All files", "*.*")]
                elif current.endswith(".vbs"):
                    ft = [("VBS scripts", "*.vbs"), ("All files", "*.*")]
                else:
                    ft = [("All files", "*.*")]

                result = filedialog.askopenfilename(
                    initialdir=initial,
                    title="Pilih File",
                    filetypes=ft
                )
                if result:
                    v.set(result.replace("/", "\\"))
        return browse

    # ── Render form parameter ─────────────────────────────────────────────────
    def _render_param_form(self, name: str):
        """Hapus dan render ulang form parameter sesuai job yang dipilih."""
        for w in self._param_container.winfo_children():
            w.destroy()

        params = SCRIPTS[name]["params"]
        vars_list: list[tk.StringVar] = []

        for i, p in enumerate(params):
            row_bg = SAP_WHITE if i % 2 == 0 else SAP_PARAM_BG
            row = tk.Frame(self._param_container, bg=row_bg)
            row.pack(fill="x")

            # Label kolom kiri
            tk.Label(row, text=p["label"]+":", font=FONT_BOLD,
                     bg=row_bg, fg=SAP_TEXT, width=16, anchor="e"
                     ).pack(side="left", padx=(10, 6), pady=5)

            # Entry / UI element — baca dari _runtime_params dulu, fallback ke SCRIPTS
            initial_val = resolve_default(self._get_param_value(name, p["arg"]))
            var = tk.StringVar(value=initial_val)
            vars_list.append(var)

            if p["type"] == "bool":
                # OptionMenu untuk boolean
                cb = ttk.OptionMenu(row, var, initial_val, "True", "False")
                cb.config(width=8)
                cb.pack(side="left", padx=(0, 4), pady=5)
            elif p["type"] == "path":
                # Entry + tombol Browse
                entry = tk.Entry(row, textvariable=var, font=FONT_MONO,
                                 bg=SAP_WHITE, fg=SAP_TEXT,
                                 relief="solid", bd=1, width=36)
                entry.pack(side="left", padx=(0, 2), pady=5)
                tk.Button(
                    row, text="…", font=FONT_SMALL,
                    bg=SAP_GREY_PANEL, fg=SAP_TEXT,
                    relief="flat", padx=6, pady=1, cursor="hand2",
                    command=self._make_browse_cmd(var, p["arg"])
                ).pack(side="left", padx=(0, 8), pady=5)
            else:
                entry_w = 22
                entry = tk.Entry(row, textvariable=var, font=FONT_MONO,
                                 bg=SAP_WHITE, fg=SAP_TEXT,
                                 relief="solid", bd=1, width=entry_w)
                entry.pack(side="left", padx=(0, 8), pady=5)

            # Keterangan / help text
            tk.Label(row, text=p["help"], font=FONT_SMALL,
                     bg=row_bg, fg=SAP_BORDER, anchor="w"
                     ).pack(side="left", fill="x")

        self._param_vars[name] = vars_list

    # ── Log Panel ─────────────────────────────────────────────────────────────
    def _build_log_panel(self, parent):
        container = tk.Frame(parent, bg=SAP_GREY_BG)
        container.pack(fill="both", expand=True, padx=6, pady=(4, 6))

        hdr = tk.Frame(container, bg=SAP_BLUE_LIGHT, height=28)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  📄  Execution Log", font=FONT_TITLE,
                 bg=SAP_BLUE_LIGHT, fg=SAP_WHITE).pack(side="left", padx=6, pady=4)

        self._log = scrolledtext.ScrolledText(
            container, font=FONT_MONO, bg="#1E1E2E", fg="#D4D4D4",
            insertbackground=SAP_WHITE, wrap="word",
            relief="solid", bd=1, state="disabled"
        )
        self._log.pack(fill="both", expand=True)

        self._log.tag_config("INFO",   foreground="#9CDCFE")
        self._log.tag_config("OK",     foreground="#4EC9B0")
        self._log.tag_config("ERROR",  foreground="#F48771")
        self._log.tag_config("WARN",   foreground="#DCDCAA")
        self._log.tag_config("SYSTEM", foreground="#808080")
        self._log.tag_config("HEADER", foreground="#C586C0", font=FONT_BOLD)

        self._log_write("SYSTEM", "Dashboard siap. Edit parameter lalu klik [Execute].")

    # ── Status Bar ────────────────────────────────────────────────────────────
    def _build_statusbar(self):
        bar = tk.Frame(self, bg=SAP_BLUE, height=22)
        bar.pack(side="bottom", fill="x")
        bar.pack_propagate(False)
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(bar, textvariable=self._status_var, font=FONT_SMALL,
                 bg=SAP_BLUE, fg=SAP_WHITE, anchor="w").pack(side="left", padx=8)
        tk.Label(bar,
                 text="SAP Automation Dashboard v2.0  |  Python " + sys.version.split()[0],
                 font=FONT_SMALL, bg=SAP_BLUE, fg=SAP_WHITE
                 ).pack(side="right", padx=8)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _update_clock(self):
        self._clock_var.set(datetime.now().strftime("🕐  %d/%m/%Y   %H:%M:%S"))
        self.after(1000, self._update_clock)

    def _get_param_value(self, job_name: str, arg_name: str, default=None) -> str:
        """Ambil nilai parameter: _runtime_params > SCRIPTS default > fallback.

        Membaca dari _runtime_params terlebih dahulu. Jika tidak ada,
        ambil dari definisi default di SCRIPTS. Jika keduanya tidak ada,
        gunakan parameter ``default``.
        """
        # Cek runtime override dulu
        rt = self._runtime_params.get(job_name, {})
        if arg_name in rt:
            return rt[arg_name]
        # Fallback ke SCRIPTS default
        if job_name in SCRIPTS:
            for p in SCRIPTS[job_name]["params"]:
                if p["arg"] == arg_name:
                    return p["default"]
        # Fallback terakhir
        return default if default is not None else ""

    # ── Persistence & Scheduler ───────────────────────────────────────────────
    def _load_config(self):
        """Muat konfigurasi parameter dari file JSON."""
        if not os.path.exists(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                
                # Load DB Settings if exists
                if "db_settings" in config:
                    db = config["db_settings"]
                    self._db_server.set(db.get("server", self._db_server.get()))
                    self._db_user.set(db.get("user", self._db_user.get()))
                    self._db_pwd.set(db.get("pwd", self._db_pwd.get()))
                    self._db_name.set(db.get("name", self._db_name.get()))

                for job_name, params in config.items():
                    if job_name in SCRIPTS:
                        # Simpan nilai konfigurasi ke _runtime_params (TANPA mengubah SCRIPTS)
                        if job_name not in self._runtime_params:
                            self._runtime_params[job_name] = {}
                        for p_def in SCRIPTS[job_name]["params"]:
                            if p_def["arg"] in params:
                                self._runtime_params[job_name][p_def["arg"]] = params[p_def["arg"]]
            # Validasi struktur config — cetak warning jika ada key/arg tidak dikenal
            is_valid, warnings = validate_job_config(config)
            if not is_valid:
                for w in warnings:
                    print(f"[WARNING] {w}")
            print(f"Konfigurasi dimuat dari {CONFIG_FILE}")
        except Exception as e:
            print(f"Gagal memuat konfigurasi: {e}")

    def _save_config(self):
        """Simpan parameter saat ini dari UI ke file JSON dan update memory."""
        config = {}
        for name in SCRIPTS:
            job_params = {}
            vars_list = self._param_vars.get(name)
            params_def = SCRIPTS[name]["params"]
            for i, p in enumerate(params_def):
                if vars_list and i < len(vars_list):
                    val = vars_list[i].get()
                    job_params[p["arg"]] = val
                    # Simpan ke _runtime_params (TANPA mengubah SCRIPTS)
                    if name not in self._runtime_params:
                        self._runtime_params[name] = {}
                    self._runtime_params[name][p["arg"]] = val
                else:
                    # Ambil dari _runtime_params, fallback ke SCRIPTS default
                    job_params[p["arg"]] = self._get_param_value(name, p["arg"])
            config[name] = job_params

        # Save DB Settings — pwd TIDAK disimpan ke file JSON.
        # Password selalu dibaca dari .env melalui config.py.
        config["db_settings"] = {
            "server": self._db_server.get(),
            "user":   self._db_user.get(),
            "name":   self._db_name.get()
            # "pwd" sengaja dihilangkan — jangan simpan password ke file JSON
        }

        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)

            # Konfirmasi yang jelas: tampilkan job + nilai parameter yang tersimpan
            self._log_write("OK", f"Konfigurasi tersimpan ke {CONFIG_FILE}")
            sel = self._selected_job
            if sel:
                saved = config.get(sel, {})
                self._log_write("INFO", f"Job: {sel}")
                for arg, val in saved.items():
                    shown = val if str(val).strip() != "" else "(kosong)"
                    self._log_write("INFO", f"    • {arg} = {shown}")
                self._status_var.set(f"Konfigurasi '{sel}' tersimpan ✓")

            # Refresh detail panel untuk job yang sedang dipilih
            if self._selected_job:
                self._update_detail(self._selected_job)
        except Exception as e:
            self._log_write("ERROR", f"Gagal menyimpan konfigurasi: {e}")

    def _scheduler_loop(self):
        """Thread background untuk mengecek jadwal eksekusi."""
        while True:
            try:
                now = datetime.now()
                current_hm = now.strftime("%H:%M")
                current_date_hm = now.strftime("%Y-%m-%d %H:%M")

                for name, info in SCRIPTS.items():
                    # Cari parameter sch-time dan sch-active
                    sch_time = ""
                    sch_active = False

                    # Kita ambil nilai terbaru dari _param_vars jika sudah di-render,
                    # atau dari default SCRIPTS jika belum.
                    vars_list = self._param_vars.get(name)
                    if vars_list:
                        for i, p in enumerate(info["params"]):
                            if p["arg"] == "sch-time":
                                sch_time = vars_list[i].get().strip()
                            if p["arg"] == "sch-active":
                                sch_active = vars_list[i].get().lower() == "true"
                    else:
                        for p in info["params"]:
                            if p["arg"] == "sch-time":
                                sch_time = self._get_param_value(name, "sch-time")
                            if p["arg"] == "sch-active":
                                sch_active = str(self._get_param_value(name, "sch-active")).lower() == "true"

                    if sch_active and sch_time == current_hm:
                        if self._last_triggered.get(name) != current_date_hm:
                             if not running_jobs.get(name):
                                self._last_triggered[name] = current_date_hm
                                log_queue.put(("SYSTEM", f"AUTO-SCHEDULE: Memicu job '{name}'..."))
                                # Karena kita di thread lain, kita gunakan after() untuk panggil UI method
                                self.after(0, lambda n=name: self._run_job(n))

            except Exception as e:
                print(f"Error in scheduler loop: {e}")

            time.sleep(30)  # Cek setiap 30 detik

    def _on_job_select(self, _=None):
        sel = self._tree.selection()
        if not sel:
            return
        for name, iid in self._job_items.items():
            if iid == sel[0]:
                self._selected_job = name
                self._update_detail(name)
                break

    def _on_detail_change(self, key, var):
        """Update _runtime_files saat detail job diubah di UI (tanpa mengubah SCRIPTS)."""
        if self._selected_job and key == "file":
            self._runtime_files[self._selected_job] = var.get().strip()

    def _update_detail(self, name: str):
        info = SCRIPTS[name]
        self._detail_vars["name"].set(name)
        self._detail_vars["file"].set(
            self._runtime_files.get(name, info["file"])
        )
        
        # Cari info jadwal dari _runtime_params, fallback ke SCRIPTS default
        sch_time = self._get_param_value(name, "sch-time", default="—")
        sch_active = self._get_param_value(name, "sch-active", default="False")
        self._detail_vars["sched"].set(f"{sch_time} (Active: {sch_active})")

        self._detail_vars["desc"].set(info["desc"])
        self._render_param_form(name)
        self._set_badge(STATUS_IDLE)

    def _set_badge(self, state: str):
        badges = {
            STATUS_IDLE:    (" ⬤  Idle ",     SAP_TEXT),
            STATUS_RUNNING: (" ⬤  Running… ", SAP_RUNNING),
            "ok":      (" ⬤  Success ",  SAP_SUCCESS),
            "error":   (" ⬤  Failed ",   SAP_ERROR),
        }
        text, color = badges.get(state, badges[STATUS_IDLE])
        self._status_badge.config(text=text, fg=color)
        if state == STATUS_RUNNING:
            self._exec_btn.config(state="disabled", bg=SAP_GREY_PANEL)
            if hasattr(self, "_stop_btn"):
                self._stop_btn.config(state="normal", bg=SAP_ERROR)
        else:
            self._exec_btn.config(state="normal", bg=SAP_BLUE)
            if hasattr(self, "_stop_btn"):
                self._stop_btn.config(state="disabled", bg=SAP_GREY_PANEL)

    def _log_write(self, tag: str, text: str):
        self._log.config(state="normal")
        ts = datetime.now().strftime("[%H:%M:%S]")
        self._log.insert("end", f"{ts} [{tag}]  {text}\n", tag)
        self._log.see("end")
        self._log.config(state="disabled")

    def _clear_log(self):
        self._log.config(state="normal")
        self._log.delete("1.0", "end")
        self._log.config(state="disabled")
        self._log_write("SYSTEM", "Log dibersihkan.")

    def _refresh(self):
        self._status_var.set("Refreshing…")
        self.after(500, lambda: self._status_var.set("Ready"))
        self._log_write("INFO", "Dashboard di-refresh.")

    def _reset_params(self):
        name = self._selected_job
        params = SCRIPTS[name]["params"]
        vars_list = self._param_vars.get(name, [])
        # Hapus override runtime agar kembali ke default SCRIPTS
        if name in self._runtime_params:
            del self._runtime_params[name]
        for i, p in enumerate(params):
            if i < len(vars_list):
                vars_list[i].set(resolve_default(p["default"]))
        self._log_write("INFO", f"Parameter '{name}' direset ke nilai default.")

    def _update_tree_status(self, name: str, status: str, ts: str, tag: str):
        iid = self._job_items[name]
        short = name.split("–")[0].strip()
        self._tree.item(iid, values=(short, status, ts), tags=(tag,))

    # ── Kumpulkan parameter dari form UI ───────────────────────────────────────
    def _collect_params(self, name: str) -> dict:
        """Kumpulkan parameter (arg -> value) dari form UI."""
        params_def = SCRIPTS[name]["params"]
        vars_      = self._param_vars.get(name, [])
        params = {}
        for i, p in enumerate(params_def):
            params[p["arg"]] = vars_[i].get() if i < len(vars_) else ""
        return params

    def _get_db_config(self) -> dict:
        return {
            "server": self._db_server.get(),
            "user":   self._db_user.get(),
            "pwd":    self._db_pwd.get(),
            "name":   self._db_name.get(),
        }

    # ── Stop Job ──────────────────────────────────────────────────────────────
    def _stop_selected(self):
        name = self._selected_job
        proc = self._procs.get(name)
        if not running_jobs.get(name) or proc is None:
            messagebox.showinfo("Info", "Tidak ada job yang sedang berjalan untuk dihentikan.")
            return
        if not messagebox.askyesno("Stop Job", f"Hentikan job '{name}'?"):
            return
        log_queue.put(("WARN", f"Menghentikan job '{name}' atas permintaan pengguna…"))
        jr_stop_job(proc.pid)

    # ── Eksekusi Job ──────────────────────────────────────────────────────────
    def _execute_selected(self):
        name = self._selected_job
        if running_jobs.get(name):
            messagebox.showinfo("Info", "Job ini sedang berjalan.")
            return
        self._run_job(name)

    def _run_job(self, name: str):
        self._save_config()  # Simpan parameter setiap kali dijalankan

        params = self._collect_params(name)
        db_config = self._get_db_config()

        running_jobs[name] = True
        ts_start = datetime.now().strftime("%H:%M:%S")
        self._update_tree_status(name, STATUS_DISPLAY[STATUS_RUNNING], ts_start, STATUS_RUNNING)
        self._set_badge(STATUS_RUNNING)
        self._status_var.set(f"Executing: {name} …")

        def on_log(tag, line):
            log_queue.put((tag, line))

        def on_started(proc):
            self._procs[name] = proc

        def on_ended():
            self._procs.pop(name, None)

        def task():
            ok = jr_run_job(
                name, params, db_config=db_config,
                on_log_line=on_log,
                on_proc_started=on_started,
                on_proc_ended=on_ended,
            )
            ts_end    = datetime.now().strftime("%H:%M:%S")
            result    = "SUCCESS ✓" if ok else "FAILED ✗"
            badge_tag = "ok" if ok else "error"
            log_queue.put(("__DONE__", (name, result, ts_end, badge_tag, ok)))

        threading.Thread(target=task, daemon=True).start()

    # ── Queue Processor ───────────────────────────────────────────────────────
    def _process_log_queue(self):
        try:
            while True:
                tag, msg = log_queue.get_nowait()
                if tag == "__DONE__":
                    name, result, ts_end, badge_tag, ok = msg
                    running_jobs[name] = False
                    badge_tag = STATUS_SUCCESS if ok else STATUS_FAILED
                    self._update_tree_status(name, STATUS_DISPLAY[badge_tag], ts_end, badge_tag)
                    self._set_badge(badge_tag)
                    self._status_var.set(f"Job selesai: {name} – {result} pukul {ts_end}")
                else:
                    self._log_write(tag, msg)
        except queue.Empty:
            pass
        finally:
            self.after(200, self._process_log_queue)

    def _show_about(self):
        messagebox.showinfo("About",
                            "SAP Automation Dashboard v2.0\n\n"
                            "Python " + sys.version.split()[0] + "\n\n"
                            "Job:\n" + "\n".join(f"  • {n}" for n in SCRIPTS))


# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = SAPDashboard()
    style = ttk.Style(app)
    style.theme_use("clam")
    style.configure("Treeview",
                    background=SAP_WHITE, fieldbackground=SAP_WHITE,
                    foreground=SAP_TEXT, font=FONT_UI, rowheight=24)
    style.configure("Treeview.Heading",
                    background=SAP_GREY_PANEL, foreground=SAP_BLUE,
                    font=FONT_BOLD, relief="flat")
    style.map("Treeview",
              background=[("selected", SAP_BLUE)],
              foreground=[("selected", SAP_WHITE)])
    style.configure("TScrollbar", background=SAP_GREY_PANEL, troughcolor=SAP_WHITE)
    app.mainloop()
