import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog, simpledialog
import threading
import subprocess
import os
import sys
import queue
import json
import time
import re
from datetime import datetime, timedelta

# Pastikan output stream menggunakan UTF-8 di Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config import DB_CONFIG
from job_definitions import SCRIPTS, resolve_default, build_cli_args, validate_job_config
from job_runner import (
    run_job as jr_run_job, stop_job as jr_stop_job,
    STATUS_IDLE, STATUS_RUNNING, STATUS_SUCCESS, STATUS_FAILED, STATUS_DISPLAY,
)
from sequence_runner import SequenceRunner
import scheduler_utils
from custom_sequence_runner import resolve_dynamic_params, resolve_dynamic_value

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

        m_seq = tk.Menu(mb, tearoff=False, font=FONT_UI)
        m_seq.add_command(label="📅 Windows Task Scheduler Manager...", command=self._open_task_scheduler_manager)
        m_seq.add_command(label="⚡ Customize Sequence Job...", command=self._open_sequence_builder)
        mb.add_cascade(label="Schedule", menu=m_seq)

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
        tk.Button(bar, text="📅 Task Scheduler", command=self._open_task_scheduler_manager,
                  font=FONT_BOLD, bg=SAP_BLUE, fg=SAP_WHITE, relief="raised", bd=1,
                  padx=10, pady=3, cursor="hand2",
                  activebackground=SAP_BLUE_LIGHT, activeforeground=SAP_WHITE
                  ).pack(side="left", padx=3, pady=3)
        tk.Frame(bar, bg=SAP_BORDER, width=1).pack(side="left", fill="y", padx=4, pady=4)
        tk.Button(bar, text="⚡ Customize Sequence", command=self._open_sequence_builder,
                  font=FONT_BOLD, bg=SAP_TOOLBAR, fg=SAP_TEXT, relief="flat",
                  padx=10, pady=3, cursor="hand2",
                  activebackground=SAP_BLUE_LIGHT, activeforeground=SAP_WHITE
                  ).pack(side="left", padx=3, pady=3)
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
                current_day = str(now.day)

                for name, info in SCRIPTS.items():
                    # Cari parameter sch-time, sch-day, dan sch-active
                    sch_time = ""
                    sch_day = "*"
                    sch_active = False

                    # Kita ambil nilai terbaru dari _param_vars jika sudah di-render,
                    # atau dari default SCRIPTS jika belum.
                    vars_list = self._param_vars.get(name)
                    if vars_list:
                        for i, p in enumerate(info["params"]):
                            if p["arg"] == "sch-time":
                                sch_time = vars_list[i].get().strip()
                            elif p["arg"] == "sch-day":
                                sch_day = vars_list[i].get().strip()
                            elif p["arg"] == "sch-active":
                                sch_active = vars_list[i].get().lower() == "true"
                    else:
                        for p in info["params"]:
                            if p["arg"] == "sch-time":
                                sch_time = self._get_param_value(name, "sch-time")
                            elif p["arg"] == "sch-day":
                                sch_day = self._get_param_value(name, "sch-day", default="*")
                            elif p["arg"] == "sch-active":
                                sch_active = str(self._get_param_value(name, "sch-active")).lower() == "true"

                    # Cek kesesuaian hari/tanggal
                    day_match = True
                    if sch_day and str(sch_day).strip() not in ("*", "ALL", "all", "—", ""):
                        target_days = [d.strip().lstrip("0") for d in str(sch_day).split(",") if d.strip()]
                        day_match = current_day in target_days

                    if sch_active and day_match and sch_time == current_hm:
                        if self._last_triggered.get(name) != current_date_hm:
                            if not running_jobs.get(name):
                                self._last_triggered[name] = current_date_hm
                                log_queue.put(("SYSTEM", f"AUTO-SCHEDULE: Memicu job '{name}' (Tgl {current_day}, Pukul {current_hm})..."))
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
        sch_day = self._get_param_value(name, "sch-day", default="*")
        sch_active = self._get_param_value(name, "sch-active", default="False")
        if sch_day and sch_day != "*":
            self._detail_vars["sched"].set(f"{sch_time} (Tgl: {sch_day}, Active: {sch_active})")
        else:
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
        """Kumpulkan parameter (arg -> value) dari form UI atau konfigurasi runtime."""
        params_def = SCRIPTS[name]["params"]
        vars_      = self._param_vars.get(name, [])
        params = {}
        for i, p in enumerate(params_def):
            if vars_ and i < len(vars_):
                params[p["arg"]] = vars_[i].get()
            else:
                params[p["arg"]] = resolve_default(self._get_param_value(name, p["arg"]))
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

    def _open_sequence_builder(self):
        """Buka dialog penyusun sequence eksekusi job kustom."""
        SequenceBuilderDialog(self)

    def _open_task_scheduler_manager(self):
        """Buka dialog pengelola Windows Task Scheduler untuk SAP Automation."""
        TaskSchedulerDialog(self)

    def _show_about(self):
        messagebox.showinfo("About",
                            "SAP Automation Dashboard v2.0\n\n"
                            "Python " + sys.version.split()[0] + "\n\n"
                            "Job:\n" + "\n".join(f"  • {n}" for n in SCRIPTS))


# ── Dialog Tambah / Ubah Jeda Waktu (Wait Step) ─────────────────────────────────

class WaitStepDialog(tk.Toplevel):
    """Dialog untuk menambah atau mengubah jeda waktu (wait step) pada sequence."""

    def __init__(self, parent, initial_seconds: int = 120, initial_desc: str = "", on_save=None):
        super().__init__(parent)
        self.parent = parent
        self.on_save = on_save
        self.title("Jeda Waktu (Wait Step)")
        self.geometry("520x300")
        self.minsize(480, 260)
        self.configure(bg=SAP_GREY_BG)
        self.transient(parent)
        self.grab_set()

        # Posisi tengah
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = 520, 300
        x = max(0, px + (pw - w) // 2)
        y = max(0, py + (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        self._build_ui(initial_seconds, initial_desc)

    def _build_ui(self, initial_seconds: int, initial_desc: str):
        # Header banner
        hdr = tk.Frame(self, bg=SAP_BLUE, height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(
            hdr, text="  ⏳ Pengaturan Jeda Waktu (Wait / Delay Step)",
            font=("Segoe UI" if sys.platform == "win32" else "Arial", 10, "bold"),
            bg=SAP_BLUE, fg=SAP_WHITE
        ).pack(side="left", padx=10, pady=10)

        body = tk.Frame(self, bg=SAP_GREY_BG, padx=16, pady=12)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="Durasi Tunggu / Jeda (Detik):", font=FONT_BOLD, bg=SAP_GREY_BG, fg=SAP_TEXT).pack(anchor="w")

        row_dur = tk.Frame(body, bg=SAP_GREY_BG)
        row_dur.pack(fill="x", pady=(4, 8))

        self._sec_var = tk.StringVar(value=str(initial_seconds))
        ent_sec = tk.Entry(row_dur, textvariable=self._sec_var, font=FONT_BOLD, width=10, relief="solid", bd=1)
        ent_sec.pack(side="left")
        ent_sec.focus_set()

        def _set_sec(s: int):
            self._sec_var.set(str(s))

        tk.Button(row_dur, text="30s", font=FONT_SMALL, command=lambda: _set_sec(30), relief="groove", cursor="hand2").pack(side="left", padx=(8, 2))
        tk.Button(row_dur, text="1 Menit (60s)", font=FONT_SMALL, command=lambda: _set_sec(60), relief="groove", cursor="hand2").pack(side="left", padx=2)
        tk.Button(row_dur, text="2 Menit (120s)", font=FONT_SMALL, command=lambda: _set_sec(120), relief="groove", cursor="hand2").pack(side="left", padx=2)
        tk.Button(row_dur, text="5 Menit (300s)", font=FONT_SMALL, command=lambda: _set_sec(300), relief="groove", cursor="hand2").pack(side="left", padx=2)
        tk.Button(row_dur, text="10 Menit (600s)", font=FONT_SMALL, command=lambda: _set_sec(600), relief="groove", cursor="hand2").pack(side="left", padx=2)

        tk.Label(body, text="Keterangan / Alasan Jeda:", font=FONT_BOLD, bg=SAP_GREY_BG, fg=SAP_TEXT).pack(anchor="w", pady=(8, 0))
        self._desc_var = tk.StringVar(value=initial_desc or "Menunggu proses Background Job di server SAP selesai")
        ent_desc = tk.Entry(body, textvariable=self._desc_var, font=FONT_UI, relief="solid", bd=1)
        ent_desc.pack(fill="x", pady=(4, 12))

        tk.Label(
            body,
            text="💡 Tips: Jeda waktu diperlukan jika langkah sebelumnya membuat Background Job (SM36/SM37)\nagar proses di server SAP tuntas sebelum langkah pengunduhan spool (SM37) dimulai.",
            font=FONT_SMALL, bg=SAP_GREY_BG, fg=SAP_BORDER, justify="left", wraplength=480
        ).pack(fill="x", anchor="w")

        # Bottom Bar
        bar = tk.Frame(self, bg=SAP_TOOLBAR, height=42, relief="raised", bd=1)
        bar.pack(fill="x", side="bottom")

        tk.Button(bar, text="Batal", font=FONT_UI, bg=SAP_GREY_PANEL, fg=SAP_TEXT, relief="flat", padx=12, pady=3, cursor="hand2", command=self.destroy).pack(side="right", padx=(4, 12), pady=6)
        tk.Button(bar, text="✔ Simpan Jeda", font=FONT_BOLD, bg=SAP_BLUE, fg=SAP_WHITE, activebackground=SAP_BLUE_LIGHT, relief="raised", bd=1, padx=14, pady=3, cursor="hand2", command=self._save).pack(side="right", padx=4, pady=6)

    def _save(self):
        try:
            val = int(self._sec_var.get().strip())
            if val <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Durasi jeda harus berupa angka bulat positif (detik).", parent=self)
            return
        desc = self._desc_var.get().strip() or f"Tunggu {val} detik"
        if self.on_save:
            self.on_save(val, desc)
        self.destroy()


# ── Dialog Edit Parameter Step Sequence ─────────────────────────────────────────

class SequenceParamEditorDialog(tk.Toplevel):
    """Dialog untuk mengedit parameter step job sequence, lengkap dengan preset token dinamis."""

    def __init__(self, parent, item: dict, on_save=None):
        super().__init__(parent)
        self.parent = parent
        self.item = item
        self.job_name = item.get("name", "")
        self.on_save = on_save
        self.title(f"Edit Parameter – {self.job_name}")
        self.geometry("780x600")
        self.minsize(720, 500)
        self.configure(bg=SAP_GREY_BG)
        self.transient(parent)
        self.grab_set()

        # Posisi tengah
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = 780, 600
        x = max(0, px + (pw - w) // 2)
        y = max(0, py + (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        self._param_vars: dict[str, tk.Variable] = {}
        self._preview_labels: dict[str, tk.Label] = {}
        self._build_ui()

    def _build_ui(self):
        # Header banner
        hdr = tk.Frame(self, bg=SAP_BLUE, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(
            hdr, text=f"  ✏ Edit Parameter: {self.job_name}",
            font=("Segoe UI" if sys.platform == "win32" else "Arial", 10, "bold"),
            bg=SAP_BLUE, fg=SAP_WHITE
        ).pack(side="left", padx=10, pady=(6, 2))
        tk.Label(
            hdr, text="Gunakan tombol preset di bawah setiap kolom untuk menyisipkan parameter dinamis otomatis.",
            font=FONT_SMALL, bg=SAP_BLUE, fg="#D0E1F9"
        ).pack(side="left", padx=10, pady=(10, 0))

        # Main scrollable canvas container
        container = tk.Frame(self, bg=SAP_GREY_BG)
        container.pack(fill="both", expand=True, padx=10, pady=8)

        canvas = tk.Canvas(container, bg=SAP_WHITE, highlightthickness=1, highlightbackground=SAP_BORDER)
        sb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=SAP_WHITE, padx=12, pady=10)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Mousewheel scroll support
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self.bind("<Destroy>", lambda _: canvas.unbind_all("<MouseWheel>"))

        # Info tips box
        tips_box = tk.Frame(scrollable_frame, bg="#E8F0FE", bd=1, relief="solid", padx=10, pady=8)
        tips_box.pack(fill="x", pady=(0, 10))
        tk.Label(
            tips_box, text="💡 Panduan Token Dinamis untuk Task Scheduler:",
            font=FONT_BOLD, bg="#E8F0FE", fg=SAP_BLUE
        ).pack(anchor="w")
        tk.Label(
            tips_box,
            text="• dynamic-today-ymd (YYYY-MM-DD) atau dynamic-today-dmy (DD.MM.YYYY) : Tanggal eksekusi hari ini\n"
                 "• dynamic-15-days-ago-ymd / dynamic-15-days-ago-dmy : 15 Hari sebelum tanggal eksekusi (H-15)\n"
                 "• dynamic-yesterday-ymd / dynamic-yesterday-dmy : Kemarin (H-1)\n"
                 "• dynamic-now-plus-1m / dynamic-now-plus-5m : Waktu mulai penjadwalan (HH:mm) sekarang + 1 atau 5 menit\n"
                 "Saat dijalankan terjadwal, token di atas otomatis diterjemahkan menjadi tanggal/jam riil.",
            font=FONT_SMALL, bg="#E8F0FE", fg=SAP_TEXT, justify="left"
        ).pack(anchor="w", pady=(2, 0))

        # Fields per parameter
        job_def = SCRIPTS.get(self.job_name, {})
        params_meta = job_def.get("params", [])
        current_params = self.item.get("params", {})

        for p in params_meta:
            arg = p["arg"]
            if arg.startswith("sch-"):
                continue

            lbl = p.get("label", arg)
            p_type = p.get("type", "str")
            desc = p.get("desc", "")
            curr_val = current_params.get(arg, p.get("default", ""))

            p_box = tk.LabelFrame(scrollable_frame, text=f" {lbl} (--{arg}) ", font=FONT_BOLD,
                                  bg=SAP_WHITE, fg=SAP_BLUE, bd=1, relief="solid", padx=8, pady=6)
            p_box.pack(fill="x", pady=6)

            if desc:
                tk.Label(p_box, text=desc, font=FONT_SMALL, bg=SAP_WHITE, fg=SAP_BORDER).pack(anchor="w", pady=(0, 4))

            if p_type == "bool":
                b_var = tk.BooleanVar(value=str(curr_val).lower() in ("true", "1", "yes"))
                self._param_vars[arg] = b_var
                tk.Checkbutton(p_box, text=f"Aktifkan opsi ini (--{arg} True)", variable=b_var, font=FONT_UI, bg=SAP_WHITE).pack(anchor="w")
            else:
                s_var = tk.StringVar(value=str(curr_val))
                self._param_vars[arg] = s_var

                ent_row = tk.Frame(p_box, bg=SAP_WHITE)
                ent_row.pack(fill="x")

                ent = tk.Entry(ent_row, textvariable=s_var, font=FONT_UI, bg=SAP_PARAM_BG, relief="solid", bd=1)
                ent.pack(side="left", fill="x", expand=True)

                # Preview label untuk token dinamis
                prev_lbl = tk.Label(p_box, text="", font=FONT_SMALL, bg=SAP_WHITE, fg="#0B6623")
                prev_lbl.pack(anchor="w", pady=(2, 0))
                self._preview_labels[arg] = prev_lbl

                def _update_prev(var=s_var, plbl=prev_lbl):
                    val = var.get().strip()
                    res = resolve_dynamic_value(val)
                    if res != val:
                        plbl.config(text=f"👉 Runtime saat ini: {res}")
                    else:
                        plbl.config(text="")

                s_var.trace_add("write", lambda *_, u=_update_prev: u())
                _update_prev()

                # Tombol-tombol preset token dinamis
                is_date_field = any(k in arg.lower() for k in ["date", "tanggal", "periode"])
                is_time_field = any(k in arg.lower() for k in ["time", "waktu", "jam"])

                if is_date_field or is_time_field:
                    preset_bar = tk.Frame(p_box, bg=SAP_WHITE)
                    preset_bar.pack(fill="x", pady=(4, 0))

                    def _set_token(target_var, token_str):
                        target_var.set(token_str)

                    if is_date_field:
                        tk.Label(preset_bar, text="Preset Token:", font=FONT_SMALL, bg=SAP_WHITE, fg=SAP_TEXT).pack(side="left", padx=(0, 4))
                        tk.Button(preset_bar, text="Hari Ini (Y-M-D)", font=FONT_SMALL, bg="#E8F0FE", fg="#1967D2", relief="groove", cursor="hand2",
                                  command=lambda v=s_var: _set_token(v, "dynamic-today-ymd")).pack(side="left", padx=2)
                        tk.Button(preset_bar, text="Hari Ini (D.M.Y)", font=FONT_SMALL, bg="#E8F0FE", fg="#1967D2", relief="groove", cursor="hand2",
                                  command=lambda v=s_var: _set_token(v, "dynamic-today-dmy")).pack(side="left", padx=2)
                        tk.Button(preset_bar, text="H-15 (Y-M-D)", font=FONT_SMALL, bg="#E8F0FE", fg="#1967D2", relief="groove", cursor="hand2",
                                  command=lambda v=s_var: _set_token(v, "dynamic-15-days-ago-ymd")).pack(side="left", padx=2)
                        tk.Button(preset_bar, text="H-15 (D.M.Y)", font=FONT_SMALL, bg="#E8F0FE", fg="#1967D2", relief="groove", cursor="hand2",
                                  command=lambda v=s_var: _set_token(v, "dynamic-15-days-ago-dmy")).pack(side="left", padx=2)
                        tk.Button(preset_bar, text="Kemarin (Y-M-D)", font=FONT_SMALL, bg="#E8F0FE", fg="#1967D2", relief="groove", cursor="hand2",
                                  command=lambda v=s_var: _set_token(v, "dynamic-yesterday-ymd")).pack(side="left", padx=2)
                        tk.Button(preset_bar, text="Awal Bulan", font=FONT_SMALL, bg="#E8F0FE", fg="#1967D2", relief="groove", cursor="hand2",
                                  command=lambda v=s_var: _set_token(v, "dynamic-first-day-ymd")).pack(side="left", padx=2)

                    if is_time_field:
                        tk.Label(preset_bar, text="Preset Token:", font=FONT_SMALL, bg=SAP_WHITE, fg=SAP_TEXT).pack(side="left", padx=(0, 4))
                        tk.Button(preset_bar, text="Sekarang +1 Mnt", font=FONT_SMALL, bg="#E8F0FE", fg="#1967D2", relief="groove", cursor="hand2",
                                  command=lambda v=s_var: _set_token(v, "dynamic-now-plus-1m")).pack(side="left", padx=2)
                        tk.Button(preset_bar, text="Sekarang +5 Mnt", font=FONT_SMALL, bg="#E8F0FE", fg="#1967D2", relief="groove", cursor="hand2",
                                  command=lambda v=s_var: _set_token(v, "dynamic-now-plus-5m")).pack(side="left", padx=2)
                        tk.Button(preset_bar, text="Jam Sekarang", font=FONT_SMALL, bg="#E8F0FE", fg="#1967D2", relief="groove", cursor="hand2",
                                  command=lambda v=s_var: _set_token(v, "dynamic-now-time")).pack(side="left", padx=2)

        # Bottom Bar
        bar = tk.Frame(self, bg=SAP_TOOLBAR, height=44, relief="raised", bd=1)
        bar.pack(fill="x", side="bottom")

        tk.Button(bar, text="Batal", font=FONT_UI, bg=SAP_GREY_PANEL, fg=SAP_TEXT, relief="flat", padx=12, pady=3, cursor="hand2", command=self.destroy).pack(side="right", padx=(4, 12), pady=6)
        tk.Button(bar, text="✔ Simpan Perubahan", font=FONT_BOLD, bg=SAP_BLUE, fg=SAP_WHITE, activebackground=SAP_BLUE_LIGHT, relief="raised", bd=1, padx=16, pady=3, cursor="hand2", command=self._save_changes).pack(side="right", padx=4, pady=6)

    def _save_changes(self):
        new_params = dict(self.item.get("params", {}))
        for arg, var in self._param_vars.items():
            val = var.get()
            if isinstance(val, bool):
                new_params[arg] = str(val)
            else:
                new_params[arg] = str(val).strip()

        self.item["params"] = new_params

        # Rebuild summary string
        summary_parts = []
        for p_k, p_v in new_params.items():
            if str(p_k).startswith("sch-"):
                continue
            if p_v is not None and str(p_v).strip() != "":
                summary_parts.append(f"{p_k}={p_v}")
        summ = ", ".join(summary_parts[:4])
        if len(summary_parts) > 4:
            summ += "..."
        self.item["summary"] = summ or "(default)"

        self.destroy()
        if self.on_save:
            self.on_save()


# ── Dialog Daftarkan Sequence ke Task Scheduler ─────────────────────────────────

class RegisterTaskSchedulerDialog(tk.Toplevel):
    """Dialog formulir pendaftaran sequence kustom ke Windows Task Scheduler."""

    def __init__(self, parent, sequence_items: list[dict], on_success=None):
        super().__init__(parent)
        self.parent = parent
        self.sequence_items = sequence_items
        self.on_success = on_success
        self.title("Daftarkan ke Windows Task Scheduler")
        self.geometry("680x560")
        self.minsize(620, 500)
        self.configure(bg=SAP_GREY_BG)
        self.transient(parent)
        self.grab_set()

        # Posisi tengah
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = 680, 560
        x = max(0, px + (pw - w) // 2)
        y = max(0, py + (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        self._build_ui()

    def _build_ui(self):
        # Header banner
        hdr = tk.Frame(self, bg=SAP_BLUE, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(
            hdr, text="  📅 Pendaftaran Sequence ke Windows Task Scheduler",
            font=("Segoe UI" if sys.platform == "win32" else "Arial", 10, "bold"),
            bg=SAP_BLUE, fg=SAP_WHITE
        ).pack(side="left", padx=10, pady=(6, 2))
        tk.Label(
            hdr, text="Otomatisasi akan berjalan harian di latar belakang Windows tanpa perlu membuka GUI.",
            font=FONT_SMALL, bg=SAP_BLUE, fg="#D0E1F9"
        ).pack(side="left", padx=10, pady=(10, 0))

        body = tk.Frame(self, bg=SAP_GREY_BG, padx=16, pady=12)
        body.pack(fill="both", expand=True)

        # Form fields
        # 1. Nama Task
        tk.Label(body, text="Nama Task Windows (Otomatis diawali 'SAP_'):", font=FONT_BOLD, bg=SAP_GREY_BG, fg=SAP_TEXT).pack(anchor="w")
        default_task_name = "SAP_Custom_Sequence"
        if any("ZSMR012" in it.get("name", "") for it in self.sequence_items):
            default_task_name = "SAP_ZSMR012_Daily_15Days"
        self._task_name_var = tk.StringVar(value=default_task_name)
        ent_task = tk.Entry(body, textvariable=self._task_name_var, font=FONT_BOLD, bg=SAP_WHITE, relief="solid", bd=1)
        ent_task.pack(fill="x", pady=(2, 8))

        # 2. Jam Eksekusi (Harian)
        tk.Label(body, text="Jam Eksekusi Harian (Format HH:mm):", font=FONT_BOLD, bg=SAP_GREY_BG, fg=SAP_TEXT).pack(anchor="w")
        row_time = tk.Frame(body, bg=SAP_GREY_BG)
        row_time.pack(fill="x", pady=(2, 8))

        self._run_time_var = tk.StringVar(value="04:30")
        ent_time = tk.Entry(row_time, textvariable=self._run_time_var, font=FONT_BOLD, width=8, bg=SAP_WHITE, relief="solid", bd=1)
        ent_time.pack(side="left")

        def _set_time(t: str):
            self._run_time_var.set(t)

        tk.Label(row_time, text="Pilihan Cepat:", font=FONT_SMALL, bg=SAP_GREY_BG, fg=SAP_BORDER).pack(side="left", padx=(8, 4))
        for t_val in ["04:00", "04:30", "05:00", "06:00", "07:30", "08:00"]:
            tk.Button(row_time, text=t_val, font=FONT_SMALL, command=lambda tv=t_val: _set_time(tv), relief="groove", cursor="hand2").pack(side="left", padx=2)

        # 3. Nama File Simpan Sequence JSON
        tk.Label(body, text="Nama File Konfigurasi Sequence (disimpan di folder custom_sequences/):", font=FONT_BOLD, bg=SAP_GREY_BG, fg=SAP_TEXT).pack(anchor="w")
        default_file = "zsmr012_daily_15days.json" if "ZSMR012" in default_task_name else "custom_sequence_1.json"
        self._file_name_var = tk.StringVar(value=default_file)
        ent_file = tk.Entry(body, textvariable=self._file_name_var, font=FONT_UI, bg=SAP_WHITE, relief="solid", bd=1)
        ent_file.pack(fill="x", pady=(2, 8))

        # 4. Deskripsi Task
        tk.Label(body, text="Deskripsi Task:", font=FONT_BOLD, bg=SAP_GREY_BG, fg=SAP_TEXT).pack(anchor="w")
        default_desc = "Otomatisasi Harian ZSMR012: Buat BG Job (H-15) -> Tunggu 2 Menit -> Download Spool & Auto Upsert SQL" if "ZSMR012" in default_task_name else "Eksekusi Pipeline SAP Sequence Otomatis"
        self._desc_var = tk.StringVar(value=default_desc)
        ent_desc = tk.Entry(body, textvariable=self._desc_var, font=FONT_UI, bg=SAP_WHITE, relief="solid", bd=1)
        ent_desc.pack(fill="x", pady=(2, 10))

        # Preview Ringkasan Step
        summary_frame = tk.LabelFrame(body, text=f" 📋 Ringkasan Sequence ({len(self.sequence_items)} Langkah) ", font=FONT_BOLD,
                                      bg=SAP_WHITE, fg=SAP_BLUE, bd=1, relief="solid", padx=8, pady=6)
        summary_frame.pack(fill="both", expand=True, pady=(0, 6))

        txt_preview = tk.Text(summary_frame, font=FONT_MONO, height=5, bg=SAP_PARAM_BG, fg=SAP_TEXT, relief="flat")
        txt_preview.pack(fill="both", expand=True)

        for idx, it in enumerate(self.sequence_items):
            it_type = it.get("type", "job")
            if it_type in ("wait", "delay") or it.get("name", "").startswith("⏳"):
                txt_preview.insert("end", f"[{idx+1}] ⏳ WAIT: {it.get('seconds', 60)} detik — {it.get('desc', '')}\n")
            else:
                txt_preview.insert("end", f"[{idx+1}] 🚀 JOB: {it.get('name')} | {it.get('summary', '')}\n")
        txt_preview.config(state="disabled")

        # Bottom Bar
        bar = tk.Frame(self, bg=SAP_TOOLBAR, height=44, relief="raised", bd=1)
        bar.pack(fill="x", side="bottom")

        tk.Button(bar, text="Batal", font=FONT_UI, bg=SAP_GREY_PANEL, fg=SAP_TEXT, relief="flat", padx=12, pady=3, cursor="hand2", command=self.destroy).pack(side="right", padx=(4, 12), pady=6)
        tk.Button(bar, text="✔ Daftarkan ke Task Scheduler", font=FONT_BOLD, bg=SAP_BLUE, fg=SAP_WHITE, activebackground=SAP_BLUE_LIGHT, relief="raised", bd=1, padx=16, pady=3, cursor="hand2", command=self._do_register).pack(side="right", padx=4, pady=6)

    def _do_register(self):
        task_name = self._task_name_var.get().strip()
        run_time = self._run_time_var.get().strip()
        file_name = self._file_name_var.get().strip()
        desc = self._desc_var.get().strip()

        if not task_name:
            messagebox.showerror("Error", "Nama task tidak boleh kosong.", parent=self)
            return

        if not file_name.endswith(".json"):
            file_name += ".json"

        # Simpan file sequence JSON ke folder custom_sequences/
        os.makedirs("custom_sequences", exist_ok=True)
        full_json_path = os.path.join("custom_sequences", file_name)

        clean_items = []
        for it in self.sequence_items:
            it_type = it.get("type", "job").lower()
            if it_type in ("wait", "delay") or ((it.get("name") or "").startswith("⏳")):
                clean_items.append({
                    "type": "wait",
                    "name": it.get("name") or "⏳ JEDA WAKTU (WAIT)",
                    "seconds": it.get("seconds", 60),
                    "desc": it.get("desc", ""),
                })
            else:
                clean_items.append({
                    "type": "job",
                    "name": it.get("name") or "Job SAP",
                    "params": it.get("params", {}),
                })

        seq_payload = {
            "name": task_name,
            "description": desc,
            "items": clean_items,
        }

        try:
            with open(full_json_path, "w", encoding="utf-8") as f:
                json.dump(seq_payload, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("Error", f"Gagal menyimpan file konfigurasi sequence:\n{e}", parent=self)
            return

        # Target perintah dieksekusi oleh Windows Task Scheduler
        target_cmd = f'python custom_sequence_runner.py --sequence-file "custom_sequences\\{file_name}"'

        ok, msg = scheduler_utils.register_daily_task(
            task_name=task_name,
            target_cmd=target_cmd,
            run_time=run_time,
            description=desc,
        )

        if ok:
            messagebox.showinfo("Berhasil", f"Task '{task_name}' berhasil didaftarkan!\n\n{msg}", parent=self)
            if self.on_success:
                self.on_success()
            self.destroy()
        else:
            messagebox.showerror("Gagal", f"Gagal mendaftarkan task ke Windows Task Scheduler:\n\n{msg}", parent=self)


# ── Dialog Penyusun Sequence Job Kustom ─────────────────────────────────────────

class SequenceBuilderDialog(tk.Toplevel):
    """Window dialog untuk menyusun urutan (sequence) eksekusi job secara kustom."""

    def __init__(self, parent, initial_items: list[dict] | None = None, initial_file: str | None = None, on_saved=None):
        super().__init__(parent)
        self.parent = parent
        self.title("Customize Sequence Job – Pipeline Builder")
        self.geometry("1040x650")
        self.minsize(920, 540)
        self.configure(bg=SAP_GREY_BG)
        self.transient(parent)
        self.grab_set()

        self._current_file: str | None = os.path.abspath(initial_file) if initial_file else None
        self._on_saved = on_saved
        self._hdr_title_var = tk.StringVar(value="  🛠  Customize Job Execution Sequence")

        # Posisi tengah relatif terhadap parent window
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = 1040, 650
        x = max(0, px + (pw - w) // 2)
        y = max(0, py + (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        # Normalisasi seluruh items yang masuk
        self._sequence_items: list[dict] = []
        for it in (initial_items or []):
            item_copy = dict(it)
            it_type = item_copy.get("type", "job").lower()
            if it_type in ("wait", "delay") or ((item_copy.get("name") or "").startswith("⏳")):
                item_copy["type"] = "wait"
                item_copy["name"] = item_copy.get("name") or "⏳ JEDA WAKTU (WAIT)"
                sec = int(item_copy.get("seconds", 60))
                dsc = item_copy.get("desc", "")
                item_copy["seconds"] = sec
                item_copy["desc"] = dsc
                if not item_copy.get("summary"):
                    item_copy["summary"] = f"Tunggu {sec} detik ({sec//60}m {sec%60}s) – {dsc}" if sec >= 60 else f"Tunggu {sec} detik – {dsc}"
            else:
                item_copy["type"] = "job"
                item_copy["name"] = item_copy.get("name") or "Job SAP"
                if "params" not in item_copy or not isinstance(item_copy["params"], dict):
                    item_copy["params"] = {}
                if not item_copy.get("summary"):
                    summary_parts = []
                    for p_k, p_v in item_copy.get("params", {}).items():
                        if not str(p_k).startswith("sch-") and p_v:
                            summary_parts.append(f"{p_k}={p_v}")
                    item_copy["summary"] = ", ".join(summary_parts[:4]) or "(default)"
            self._sequence_items.append(item_copy)

        self._stop_on_error_var = tk.BooleanVar(value=True)

        self._build_ui()
        self._load_available_jobs()
        if self._sequence_items:
            self._refresh_seq_tree()
        self._update_header_title()

    def _update_header_title(self):
        if self._current_file:
            fn = os.path.basename(self._current_file)
            self._hdr_title_var.set(f"  🛠  Customize Sequence — [{fn}]")
        else:
            self._hdr_title_var.set("  🛠  Customize Job Execution Sequence")

    def _build_ui(self):
        # Header banner
        hdr = tk.Frame(self, bg=SAP_BLUE, height=48)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(
            hdr, textvariable=self._hdr_title_var,
            font=("Segoe UI" if sys.platform == "win32" else "Arial", 11, "bold"),
            bg=SAP_BLUE, fg=SAP_WHITE
        ).pack(side="left", padx=10, pady=(6, 2))
        tk.Label(
            hdr, text="Pilih job, tambahkan jeda (wait), sesuaikan parameter dinamis, atau daftarkan langsung ke Windows Task Scheduler.",
            font=FONT_SMALL, bg=SAP_BLUE, fg="#D0E1F9"
        ).pack(side="left", padx=10, pady=(10, 0))

        # Body container
        body = tk.Frame(self, bg=SAP_GREY_BG, padx=10, pady=8)
        body.pack(fill="both", expand=True)

        # ── Kolom Kiri: Available Jobs ──
        left_box = tk.LabelFrame(body, text=" 📋 Available Jobs (Daftar Job Tersedia) ", font=FONT_BOLD,
                                 bg=SAP_WHITE, fg=SAP_BLUE, bd=1, relief="solid")
        left_box.pack(side="left", fill="both", expand=True, padx=(0, 6))

        # Search bar
        search_frame = tk.Frame(left_box, bg=SAP_WHITE, padx=6, pady=4)
        search_frame.pack(fill="x")
        tk.Label(search_frame, text="🔍", bg=SAP_WHITE, font=FONT_UI).pack(side="left")
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._filter_available_jobs())
        search_ent = tk.Entry(search_frame, textvariable=self._search_var, font=FONT_UI, bg=SAP_PARAM_BG, relief="solid", bd=1)
        search_ent.pack(side="left", fill="x", expand=True, padx=4)

        # Treeview for Available Jobs
        tree_avail_frame = tk.Frame(left_box, bg=SAP_WHITE)
        tree_avail_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        self._tree_avail = ttk.Treeview(tree_avail_frame, columns=("name",), show="", selectmode="browse")
        self._tree_avail.column("name", anchor="w")
        sb_left = ttk.Scrollbar(tree_avail_frame, orient="vertical", command=self._tree_avail.yview)
        self._tree_avail.configure(yscrollcommand=sb_left.set)
        self._tree_avail.pack(side="left", fill="both", expand=True)
        sb_left.pack(side="right", fill="y")
        self._tree_avail.bind("<Double-1>", lambda _: self._add_selected_job())

        tk.Label(left_box, text="💡 Tips: Klik ganda pada nama job untuk langsung menambahkan ke antrean.",
                 font=FONT_SMALL, bg=SAP_WHITE, fg=SAP_BORDER).pack(fill="x", padx=6, pady=(0, 4))

        # ── Kolom Tengah: Action Buttons ──
        mid_box = tk.Frame(body, bg=SAP_GREY_BG, padx=4)
        mid_box.pack(side="left", fill="y", pady=40)

        tk.Button(
            mid_box, text="Tambah ➔", font=FONT_BOLD, bg=SAP_BLUE, fg=SAP_WHITE,
            activebackground=SAP_BLUE_LIGHT, activeforeground=SAP_WHITE,
            relief="raised", bd=1, padx=8, pady=6, cursor="hand2",
            command=self._add_selected_job
        ).pack(fill="x", pady=4)

        tk.Button(
            mid_box, text="⏳ + Jeda (Wait)...", font=FONT_BOLD, bg="#D97706", fg=SAP_WHITE,
            activebackground="#B45309", activeforeground=SAP_WHITE,
            relief="raised", bd=1, padx=8, pady=6, cursor="hand2",
            command=self._add_wait_step
        ).pack(fill="x", pady=4)

        tk.Button(
            mid_box, text="⬅ Hapus", font=FONT_BOLD, bg=SAP_GREY_PANEL, fg=SAP_TEXT,
            relief="raised", bd=1, padx=8, pady=6, cursor="hand2",
            command=self._remove_selected_seq
        ).pack(fill="x", pady=4)

        # ── Kolom Kanan: Sequence Queue ──
        right_box = tk.LabelFrame(body, text=" ⚡ Sequence Queue (Urutan yang Akan Dikerjakan) ", font=FONT_BOLD,
                                  bg=SAP_WHITE, fg=SAP_BLUE, bd=1, relief="solid")
        right_box.pack(side="left", fill="both", expand=True, padx=(6, 0))

        # Template buttons row
        tmpl_row = tk.Frame(right_box, bg=SAP_WHITE, padx=6, pady=4)
        tmpl_row.pack(fill="x")
        tk.Label(tmpl_row, text="File Sequence:", font=FONT_BOLD, bg=SAP_WHITE, fg=SAP_BLUE).pack(side="left", padx=2)
        tk.Button(tmpl_row, text="💾 Simpan File Ini", font=FONT_BOLD, bg="#E8F0FE", fg=SAP_BLUE,
                  relief="groove", padx=8, pady=1, cursor="hand2", command=lambda: self._save_current_file(silent=False)).pack(side="left", padx=2)
        tk.Button(tmpl_row, text="📂 Buka Template...", font=FONT_SMALL, bg=SAP_GREY_PANEL, fg=SAP_TEXT,
                  relief="groove", padx=6, pady=1, cursor="hand2", command=self._load_template_file).pack(side="left", padx=2)
        tk.Button(tmpl_row, text="💾 Simpan Sebagai...", font=FONT_SMALL, bg=SAP_GREY_PANEL, fg=SAP_TEXT,
                  relief="groove", padx=6, pady=1, cursor="hand2", command=self._save_template_file).pack(side="left", padx=2)

        tree_seq_frame = tk.Frame(right_box, bg=SAP_WHITE)
        tree_seq_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        cols = ("step", "name", "params")
        self._tree_seq = ttk.Treeview(tree_seq_frame, columns=cols, show="headings", selectmode="browse")
        self._tree_seq.heading("step", text="Step #")
        self._tree_seq.heading("name", text="Nama Job")
        self._tree_seq.heading("params", text="Parameter Tersimpan")

        self._tree_seq.column("step", width=55, anchor="center")
        self._tree_seq.column("name", width=250, anchor="w")
        self._tree_seq.column("params", width=220, anchor="w")

        sb_right = ttk.Scrollbar(tree_seq_frame, orient="vertical", command=self._tree_seq.yview)
        self._tree_seq.configure(yscrollcommand=sb_right.set)
        self._tree_seq.pack(side="left", fill="both", expand=True)
        sb_right.pack(side="right", fill="y")

        self._tree_seq.bind("<Double-1>", lambda _: self._edit_selected_step())

        # Reorder / Management Buttons under Right Tree
        btn_row = tk.Frame(right_box, bg=SAP_WHITE, padx=6, pady=4)
        btn_row.pack(fill="x")

        tk.Button(btn_row, text="⬆ Naik (Up)", font=FONT_SMALL, bg=SAP_GREY_PANEL, fg=SAP_TEXT,
                  relief="flat", padx=6, pady=2, cursor="hand2", command=self._move_up).pack(side="left", padx=2)
        tk.Button(btn_row, text="⬇ Turun (Down)", font=FONT_SMALL, bg=SAP_GREY_PANEL, fg=SAP_TEXT,
                  relief="flat", padx=6, pady=2, cursor="hand2", command=self._move_down).pack(side="left", padx=2)
        tk.Button(btn_row, text="✏ Edit Parameter", font=FONT_BOLD, bg="#E8F0FE", fg=SAP_BLUE,
                  relief="groove", padx=8, pady=2, cursor="hand2", command=self._edit_selected_step).pack(side="left", padx=4)
        tk.Button(btn_row, text="🗑 Hapus", font=FONT_SMALL, bg=SAP_GREY_PANEL, fg=SAP_ERROR,
                  relief="flat", padx=6, pady=2, cursor="hand2", command=self._remove_selected_seq).pack(side="left", padx=2)
        tk.Button(btn_row, text="🧹 Bersihkan Semua", font=FONT_SMALL, bg=SAP_GREY_PANEL, fg=SAP_TEXT,
                  relief="flat", padx=6, pady=2, cursor="hand2", command=self._clear_all_seq).pack(side="right", padx=2)

        # ── Bottom Bar ──
        bottom_bar = tk.Frame(self, bg=SAP_TOOLBAR, height=44, relief="raised", bd=1)
        bottom_bar.pack(fill="x", side="bottom")

        tk.Checkbutton(
            bottom_bar, text="Hentikan sequence jika ada job yang gagal (Stop on error)",
            variable=self._stop_on_error_var, font=FONT_UI, bg=SAP_TOOLBAR, fg=SAP_TEXT,
            activebackground=SAP_TOOLBAR
        ).pack(side="left", padx=12, pady=8)

        tk.Button(
            bottom_bar, text="Batal / Tutup", font=FONT_UI, bg=SAP_GREY_PANEL, fg=SAP_TEXT,
            relief="flat", padx=12, pady=4, cursor="hand2", command=self.destroy
        ).pack(side="right", padx=(4, 12), pady=6)

        tk.Button(
            bottom_bar, text="▶  Start Sequence", font=FONT_BOLD, bg=SAP_SUCCESS, fg=SAP_WHITE,
            activebackground="#2E7D32", activeforeground=SAP_WHITE,
            relief="raised", bd=1, padx=14, pady=4, cursor="hand2", command=self._start_sequence
        ).pack(side="right", padx=4, pady=6)

        tk.Button(
            bottom_bar, text="📅 Daftarkan ke Task Scheduler...", font=FONT_BOLD, bg=SAP_BLUE, fg=SAP_WHITE,
            activebackground=SAP_BLUE_LIGHT, activeforeground=SAP_WHITE,
            relief="raised", bd=1, padx=12, pady=4, cursor="hand2", command=self._register_to_scheduler
        ).pack(side="right", padx=4, pady=6)

    def _load_available_jobs(self):
        for name in SCRIPTS:
            self._tree_avail.insert("", "end", iid=name, values=(name,))

    def _filter_available_jobs(self):
        query = self._search_var.get().strip().lower()
        for item in self._tree_avail.get_children():
            self._tree_avail.delete(item)
        for name in SCRIPTS:
            if not query or query in name.lower():
                self._tree_avail.insert("", "end", iid=name, values=(name,))

    def _add_selected_job(self):
        sel = self._tree_avail.selection()
        if not sel:
            return
        job_name = sel[0]

        # Ambil snapshot parameter saat ini dari form dashboard parent
        params = self.parent._collect_params(job_name)

        # Buat ringkasan parameter
        summary_parts = []
        for p in SCRIPTS.get(job_name, {}).get("params", []):
            arg = p["arg"]
            if arg.startswith("sch-"):
                continue
            val = params.get(arg)
            if val is not None and str(val).strip() != "":
                summary_parts.append(f"{arg}={val}")
        params_summary = ", ".join(summary_parts[:4])
        if len(summary_parts) > 4:
            params_summary += "..."

        self._sequence_items.append({
            "type": "job",
            "name": job_name,
            "params": params,
            "summary": params_summary or "(default)",
        })
        self._refresh_seq_tree()

    def _add_wait_step(self):
        WaitStepDialog(self, on_save=self._append_wait_step)

    def _append_wait_step(self, seconds: int, desc: str):
        summ = f"Tunggu {seconds} detik ({seconds//60}m {seconds%60}s) – {desc}" if seconds >= 60 else f"Tunggu {seconds} detik – {desc}"
        self._sequence_items.append({
            "type": "wait",
            "name": "⏳ JEDA WAKTU (WAIT)",
            "seconds": seconds,
            "desc": desc,
            "summary": summ,
        })
        self._refresh_seq_tree()

    def _save_current_file(self, silent: bool = False) -> bool:
        """Menyimpan seluruh sequence ke file JSON yang sedang aktif dibuka."""
        if not self._current_file:
            return self._save_template_file()

        if not self._sequence_items:
            messagebox.showwarning("Perhatian", "Belum ada langkah job dalam sequence.", parent=self)
            return False

        try:
            clean_items = []
            for it in self._sequence_items:
                it_type = it.get("type", "job").lower()
                if it_type in ("wait", "delay") or ((it.get("name") or "").startswith("⏳")):
                    clean_items.append({
                        "type": "wait",
                        "name": it.get("name") or "⏳ JEDA WAKTU (WAIT)",
                        "seconds": it.get("seconds", 60),
                        "desc": it.get("desc", ""),
                    })
                else:
                    clean_items.append({
                        "type": "job",
                        "name": it.get("name") or "Job SAP",
                        "params": it.get("params", {}),
                    })

            seq_name = os.path.splitext(os.path.basename(self._current_file))[0]
            seq_desc = "Custom sequence template"
            if os.path.exists(self._current_file):
                try:
                    with open(self._current_file, "r", encoding="utf-8") as f:
                        old_d = json.load(f)
                        seq_name = old_d.get("name", seq_name)
                        seq_desc = old_d.get("description", seq_desc)
                except Exception:
                    pass

            payload = {
                "name": seq_name,
                "description": seq_desc,
                "items": clean_items,
            }
            with open(self._current_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)

            if not silent:
                fn = os.path.basename(self._current_file)
                messagebox.showinfo("Berhasil Disimpan", f"Perubahan sequence berhasil disimpan ke file:\n{fn}", parent=self)
            if self._on_saved:
                self._on_saved()
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Gagal menyimpan sequence ke file:\n{e}", parent=self)
            return False

    def _edit_selected_step(self):
        sel = self._tree_seq.selection()
        if not sel:
            messagebox.showinfo("Informasi", "Pilih langkah (step) yang ingin diedit terlebih dahulu.", parent=self)
            return
        idx = int(sel[0])
        if not (0 <= idx < len(self._sequence_items)):
            return
        item = self._sequence_items[idx]
        item_type = item.get("type", "job").lower()

        def _on_step_updated():
            self._refresh_seq_tree()
            self._tree_seq.selection_set(str(idx))
            if self._current_file:
                self._save_current_file(silent=False)
            else:
                messagebox.showinfo("Tersimpan", "Parameter berhasil diperbarui pada antrean sequence.", parent=self)

        if item_type in ("wait", "delay") or (item.get("name") and item.get("name").startswith("⏳")):
            def _save_wait(s, d):
                item["seconds"] = s
                item["desc"] = d
                item["summary"] = f"Tunggu {s} detik ({s//60}m {s%60}s) – {d}" if s >= 60 else f"Tunggu {s} detik – {d}"
                _on_step_updated()

            WaitStepDialog(self, initial_seconds=item.get("seconds", 120), initial_desc=item.get("desc", ""), on_save=_save_wait)
        else:
            SequenceParamEditorDialog(self, item=item, on_save=_on_step_updated)

    def _load_template_file(self):
        os.makedirs("custom_sequences", exist_ok=True)
        file_path = filedialog.askopenfilename(
            parent=self,
            initialdir=os.path.abspath("custom_sequences"),
            title="Buka Template Sequence JSON",
            filetypes=[("Sequence JSON", "*.json"), ("Semua File", "*.*")]
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            items = data.get("items", [])
            if not items:
                messagebox.showwarning("Perhatian", "File template tidak memiliki daftar step 'items'.", parent=self)
                return
            self._sequence_items = []
            for it in items:
                it_type = it.get("type", "job").lower()
                if it_type in ("wait", "delay") or (it.get("name") and it.get("name").startswith("⏳")):
                    sec = int(it.get("seconds", 60))
                    dsc = it.get("desc", "Menunggu jeda")
                    summ = f"Tunggu {sec} detik ({sec//60}m {sec%60}s) – {dsc}" if sec >= 60 else f"Tunggu {sec} detik – {dsc}"
                    self._sequence_items.append({
                        "type": "wait",
                        "name": "⏳ JEDA WAKTU (WAIT)",
                        "seconds": sec,
                        "desc": dsc,
                        "summary": summ,
                    })
                else:
                    name = it.get("name", "")
                    params = it.get("params", {})
                    summary_parts = []
                    for p_k, p_v in params.items():
                        if str(p_k).startswith("sch-"):
                            continue
                        if p_v is not None and str(p_v).strip() != "":
                            summary_parts.append(f"{p_k}={p_v}")
                    summ = ", ".join(summary_parts[:4])
                    if len(summary_parts) > 4:
                        summ += "..."
                    self._sequence_items.append({
                        "type": "job",
                        "name": name,
                        "params": params,
                        "summary": summ or "(default)",
                    })
            self._current_file = os.path.abspath(file_path)
            self._refresh_seq_tree()
            self._update_header_title()
            messagebox.showinfo("Sukses", f"Berhasil memuat template:\n{os.path.basename(file_path)} ({len(self._sequence_items)} langkah)", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Gagal membaca file template:\n{e}", parent=self)

    def _save_template_file(self):
        if not self._sequence_items:
            messagebox.showwarning("Perhatian", "Belum ada job dalam sequence untuk disimpan sebagai template.", parent=self)
            return
        os.makedirs("custom_sequences", exist_ok=True)
        file_path = filedialog.asksaveasfilename(
            parent=self,
            initialdir=os.path.abspath("custom_sequences"),
            title="Simpan Template Sequence JSON",
            defaultextension=".json",
            filetypes=[("Sequence JSON", "*.json")]
        )
        if not file_path:
            return
        try:
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            clean_items = []
            for it in self._sequence_items:
                it_type = it.get("type", "job").lower()
                if it_type in ("wait", "delay") or ((it.get("name") or "").startswith("⏳")):
                    clean_items.append({
                        "type": "wait",
                        "name": it.get("name") or "⏳ JEDA WAKTU (WAIT)",
                        "seconds": it.get("seconds", 60),
                        "desc": it.get("desc", ""),
                    })
                else:
                    clean_items.append({
                        "type": "job",
                        "name": it.get("name") or "Job SAP",
                        "params": it.get("params", {}),
                    })
            payload = {
                "name": base_name,
                "description": f"Custom sequence template {base_name}",
                "items": clean_items,
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            messagebox.showinfo("Sukses", f"Template sequence berhasil disimpan:\n{file_path}", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Gagal menyimpan template:\n{e}", parent=self)

    def _register_to_scheduler(self):
        if not self._sequence_items:
            messagebox.showwarning("Perhatian", "Belum ada job dalam urutan sequence.\nSilakan susun job atau muat template terlebih dahulu.", parent=self)
            return

        def _on_reg():
            if messagebox.askyesno("Task Scheduler", "Sequence berhasil didaftarkan!\n\nApakah Anda ingin membuka Windows Task Scheduler Manager sekarang untuk melihat jadwal?"):
                self.parent._open_task_scheduler_manager()

        RegisterTaskSchedulerDialog(self, self._sequence_items, on_success=_on_reg)

    def _refresh_seq_tree(self):
        for item in self._tree_seq.get_children():
            self._tree_seq.delete(item)
        for idx, item in enumerate(self._sequence_items):
            step_name = item.get("name")
            if not step_name:
                if item.get("type") in ("wait", "delay") or ((item.get("name") or "").startswith("⏳")):
                    sec = item.get("seconds", 60)
                    step_name = f"⏳ JEDA WAKTU ({sec}s)"
                else:
                    step_name = "Job SAP"
            self._tree_seq.insert(
                "", "end", iid=str(idx),
                values=(f"#{idx + 1}", step_name, item.get("summary", "(default)"))
            )
        if self._sequence_items:
            last_iid = str(len(self._sequence_items) - 1)
            self._tree_seq.selection_set(last_iid)
            self._tree_seq.see(last_iid)

    def _remove_selected_seq(self):
        sel = self._tree_seq.selection()
        if not sel:
            return
        idx = int(sel[0])
        if 0 <= idx < len(self._sequence_items):
            self._sequence_items.pop(idx)
            self._refresh_seq_tree()

    def _clear_all_seq(self):
        self._sequence_items.clear()
        self._refresh_seq_tree()

    def _move_up(self):
        sel = self._tree_seq.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx > 0:
            self._sequence_items[idx - 1], self._sequence_items[idx] = (
                self._sequence_items[idx], self._sequence_items[idx - 1]
            )
            self._refresh_seq_tree()
            self._tree_seq.selection_set(str(idx - 1))

    def _move_down(self):
        sel = self._tree_seq.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx < len(self._sequence_items) - 1:
            self._sequence_items[idx + 1], self._sequence_items[idx] = (
                self._sequence_items[idx], self._sequence_items[idx + 1]
            )
            self._refresh_seq_tree()
            self._tree_seq.selection_set(str(idx + 1))

    def _start_sequence(self):
        if not self._sequence_items:
            messagebox.showwarning("Perhatian", "Belum ada job dalam urutan sequence.\nSilakan pilih job dari panel kiri terlebih dahulu.")
            return

        stop_on_error = self._stop_on_error_var.get()
        items_copy = list(self._sequence_items)
        db_config = self.parent._get_db_config()

        # Tutup dialog penyusun sequence
        self.destroy()

        # Buka dialog pemantau progress sequence
        SequenceProgressDialog(self.parent, items_copy, db_config, stop_on_error)


# ── Dialog Pemantau Progress Sequence ──────────────────────────────────────────

class SequenceProgressDialog(tk.Toplevel):
    """Window dialog pemantau eksekusi antrean sequence secara real-time."""

    def __init__(self, parent, sequence_items: list[dict], db_config: dict, stop_on_error: bool = True):
        super().__init__(parent)
        self.parent = parent

        normalized_items = []
        for it in (sequence_items or []):
            it_copy = dict(it)
            if not it_copy.get("name"):
                if it_copy.get("type") in ("wait", "delay") or ((it_copy.get("name") or "").startswith("⏳")):
                    sec = it_copy.get("seconds", 60)
                    it_copy["name"] = f"⏳ JEDA WAKTU ({sec}s)"
                else:
                    it_copy["name"] = "Job SAP"
            normalized_items.append(it_copy)
        self.sequence_items = normalized_items

        self.db_config = db_config
        self.stop_on_error = stop_on_error
        self.runner: SequenceRunner | None = None
        self._is_running = True
        self._ui_queue = queue.Queue()

        self.title("Sequence Execution Progress")
        self.geometry("880x600")
        self.minsize(780, 500)
        self.configure(bg=SAP_GREY_BG)
        self.transient(parent)
        self.grab_set()

        # Posisi tengah relatif terhadap parent
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = 880, 600
        x = max(0, px + (pw - w) // 2)
        y = max(0, py + (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        self.protocol("WM_DELETE_WINDOW", self._on_close_attempt)

        self._build_ui()
        self._start_execution()

    def _build_ui(self):
        # Header banner
        hdr = tk.Frame(self, bg=SAP_BLUE, height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        top_hdr = tk.Frame(hdr, bg=SAP_BLUE)
        top_hdr.pack(fill="x", padx=10, pady=(6, 2))

        tk.Label(
            top_hdr, text="⚡ Sequence Execution Progress",
            font=("Segoe UI" if sys.platform == "win32" else "Arial", 11, "bold"),
            bg=SAP_BLUE, fg=SAP_WHITE
        ).pack(side="left")

        self._step_counter_var = tk.StringVar(value=f"Menunggu mulai (0 / {len(self.sequence_items)} Selesai)")
        tk.Label(
            top_hdr, textvariable=self._step_counter_var,
            font=FONT_BOLD, bg=SAP_BLUE, fg="#FFD54F"
        ).pack(side="right")

        # Progress bar
        self._pbar = ttk.Progressbar(hdr, orient="horizontal", mode="determinate")
        self._pbar.pack(fill="x", padx=10, pady=(2, 6))
        self._pbar["maximum"] = len(self.sequence_items)
        self._pbar["value"] = 0

        # Body paned container (Atas: Steps list, Bawah: Log)
        body = tk.PanedWindow(self, orient="vertical", bg=SAP_GREY_BG, sashwidth=4)
        body.pack(fill="both", expand=True, padx=8, pady=6)

        # Upper frame: Step Status Treeview
        upper = tk.Frame(body, bg=SAP_WHITE, bd=1, relief="solid")
        body.add(upper, minsize=140, height=180)

        tk.Label(upper, text="  📌 Status Antrean Job", font=FONT_BOLD, bg=SAP_PARAM_HDR, fg=SAP_BLUE, anchor="w").pack(fill="x")

        tree_frame = tk.Frame(upper, bg=SAP_WHITE)
        tree_frame.pack(fill="both", expand=True)

        cols = ("step", "name", "status", "duration")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="none")
        self._tree.heading("step", text="Step")
        self._tree.heading("name", text="Nama Job")
        self._tree.heading("status", text="Status")
        self._tree.heading("duration", text="Durasi")

        self._tree.column("step", width=55, anchor="center")
        self._tree.column("name", width=420, anchor="w")
        self._tree.column("status", width=140, anchor="center")
        self._tree.column("duration", width=90, anchor="center")

        self._tree.tag_configure("pending", foreground="#78909C")
        self._tree.tag_configure("running", foreground="#0288D1", font=FONT_BOLD)
        self._tree.tag_configure("success", foreground=SAP_SUCCESS, font=FONT_BOLD)
        self._tree.tag_configure("failed",  foreground=SAP_ERROR, font=FONT_BOLD)
        self._tree.tag_configure("cancelled", foreground="#E65100")

        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        for idx, item in enumerate(self.sequence_items):
            step_name = item.get("name") or f"Step #{idx + 1}"
            self._tree.insert(
                "", "end", iid=str(idx),
                values=(f"#{idx + 1}", step_name, "⏸ PENDING", "—"),
                tags=("pending",)
            )

        # Lower frame: Live Log Console
        lower = tk.Frame(body, bg="#1E1E2E", bd=1, relief="solid")
        body.add(lower, minsize=180, height=260)

        log_hdr = tk.Frame(lower, bg="#2A2A3E", height=24)
        log_hdr.pack(fill="x")
        log_hdr.pack_propagate(False)
        tk.Label(log_hdr, text="  📄 Live Execution Log", font=FONT_BOLD, bg="#2A2A3E", fg="#A0B0C0").pack(side="left")

        self._log = scrolledtext.ScrolledText(
            lower, font=FONT_MONO, bg="#1E1E2E", fg="#D4D4D4",
            insertbackground=SAP_WHITE, wrap="word", relief="flat", state="disabled"
        )
        self._log.pack(fill="both", expand=True)
        self._log.tag_configure("HEADER", foreground="#64B5F6", font=FONT_BOLD)
        self._log.tag_configure("ERROR",  foreground="#FF5252", font=FONT_BOLD)
        self._log.tag_configure("OK",     foreground="#69F0AE", font=FONT_BOLD)
        self._log.tag_configure("WARN",   foreground="#FFD740")
        self._log.tag_configure("INFO",   foreground="#D4D4D4")

        # Bottom Bar
        bottom = tk.Frame(self, bg=SAP_TOOLBAR, height=44, relief="raised", bd=1)
        bottom.pack(fill="x", side="bottom")

        self._stop_btn = tk.Button(
            bottom, text="⏹  Batalkan Sequence", font=FONT_BOLD, bg=SAP_ERROR, fg=SAP_WHITE,
            activebackground="#D32F2F", activeforeground=SAP_WHITE,
            relief="raised", bd=1, padx=14, pady=4, cursor="hand2", command=self._on_stop
        )
        self._stop_btn.pack(side="left", padx=12, pady=6)

        self._close_btn = tk.Button(
            bottom, text="Tutup", font=FONT_UI, bg=SAP_GREY_PANEL, fg=SAP_TEXT,
            state="disabled", relief="flat", padx=16, pady=4, cursor="hand2", command=self.destroy
        )
        self._close_btn.pack(side="right", padx=12, pady=6)

    def _start_execution(self):
        def _on_start(step_idx, total_steps, job_name):
            self._ui_queue.put(("STEP_START", (step_idx, total_steps, job_name)))

        def _on_log(tag, line):
            self._ui_queue.put(("LOG", (tag, line)))

        def _on_end(step_idx, total_steps, job_name, success, elapsed_str):
            self._ui_queue.put(("STEP_END", (step_idx, total_steps, job_name, success, elapsed_str)))

        def _on_seq_complete(all_success, summary_status):
            self._ui_queue.put(("SEQ_COMPLETE", (all_success, summary_status)))

        self.runner = SequenceRunner(
            sequence_items=self.sequence_items,
            db_config=self.db_config,
            stop_on_error=self.stop_on_error,
            on_step_start=_on_start,
            on_log_line=_on_log,
            on_step_end=_on_end,
            on_sequence_complete=_on_seq_complete,
        )

        threading.Thread(target=self.runner.run, daemon=True).start()
        self.after(50, self._process_ui_queue)

    def _process_ui_queue(self):
        try:
            while True:
                msg_type, data = self._ui_queue.get_nowait()
                if msg_type == "STEP_START":
                    step_idx, total_steps, job_name = data
                    self._step_counter_var.set(f"Menjalankan Step {step_idx + 1} dari {total_steps}: {job_name}")
                    self._pbar["value"] = step_idx
                    self._tree.item(str(step_idx), values=(f"#{step_idx + 1}", job_name, "▶ RUNNING...", "—"), tags=("running",))
                    self._tree.see(str(step_idx))

                elif msg_type == "STEP_END":
                    step_idx, total_steps, job_name, success, elapsed_str = data
                    status_text = "✓ SUCCESS" if success else "✗ FAILED"
                    tag = "success" if success else "failed"
                    self._tree.item(str(step_idx), values=(f"#{step_idx + 1}", job_name, status_text, elapsed_str), tags=(tag,))
                    self._pbar["value"] = step_idx + 1

                elif msg_type == "LOG":
                    tag, line = data
                    self._log.config(state="normal")
                    ts = datetime.now().strftime("[%H:%M:%S]")
                    self._log.insert("end", f"{ts} [{tag}]  {line}\n", tag)
                    self._log.see("end")
                    self._log.config(state="disabled")

                elif msg_type == "SEQ_COMPLETE":
                    all_success, summary_status = data
                    self._is_running = False
                    self._stop_btn.config(state="disabled", bg=SAP_GREY_PANEL)
                    self._close_btn.config(state="normal", bg=SAP_BLUE, fg=SAP_WHITE)

                    # Tandai sisa step jika ada yang belum berjalan
                    for item in self._tree.get_children():
                        vals = self._tree.item(item, "values")
                        if "PENDING" in vals[2]:
                            self._tree.item(item, values=(vals[0], vals[1], "CANCELLED", "—"), tags=("cancelled",))

                    if all_success:
                        self._step_counter_var.set("Seluruh sequence selesai dengan SUKSES ✓")
                        self._pbar["value"] = len(self.sequence_items)
                    else:
                        self._step_counter_var.set(f"Sequence {summary_status} ✗")
        except queue.Empty:
            pass
        finally:
            if self._is_running:
                self.after(50, self._process_ui_queue)

    def _on_stop(self):
        if not self._is_running:
            return
        if messagebox.askyesno("Konfirmasi Batal", "Apakah Anda yakin ingin membatalkan seluruh urutan sequence yang sedang berjalan?"):
            if self.runner:
                self.runner.stop()
            self._stop_btn.config(state="disabled")

    def _on_close_attempt(self):
        if self._is_running:
            if messagebox.askyesno("Konfirmasi", "Sequence masih sedang berjalan.\nBatalkan sequence dan tutup jendela?"):
                if self.runner:
                    self.runner.stop()
                self.destroy()
        else:
            self.destroy()


# ── Dialog Pengelola Windows Task Scheduler ─────────────────────────────────────

class TaskSchedulerDialog(tk.Toplevel):
    """Window dialog untuk memantau, menguji, dan mengelola Task SAP di Windows Task Scheduler."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Windows Task Scheduler – SAP Automation Manager")
        self.geometry("1100x660")
        self.minsize(960, 540)
        self.configure(bg=SAP_GREY_BG)
        self.transient(parent)

        # Posisi tengah
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = 1100, 660
        x = max(0, px + (pw - w) // 2)
        y = max(0, py + (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        self._tasks: list[dict] = []
        self._seqs: list[dict] = []
        self._is_loading = False

        self._build_ui()
        self._load_tasks_async()

    def _build_ui(self):
        # Header banner
        hdr = tk.Frame(self, bg=SAP_BLUE, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(
            hdr, text="  📅 Windows Task Scheduler & Sequence Manager",
            font=("Segoe UI" if sys.platform == "win32" else "Arial", 11, "bold"),
            bg=SAP_BLUE, fg=SAP_WHITE
        ).pack(side="left", padx=10, pady=(6, 2))
        tk.Label(
            hdr, text="Pantau jadwal otomatisasi Windows Task Scheduler (SAP_*) dan kelola berkas sequence kustom.",
            font=FONT_SMALL, bg=SAP_BLUE, fg="#D0E1F9"
        ).pack(side="left", padx=10, pady=(10, 0))

        # Notebook Tab Container
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=8, pady=6)

        tab_tasks = tk.Frame(self._nb, bg=SAP_GREY_BG)
        tab_seqs = tk.Frame(self._nb, bg=SAP_GREY_BG)

        self._nb.add(tab_tasks, text="  📅 Task Terjadwal di Windows (Task Scheduler)  ")
        self._nb.add(tab_seqs, text="  ⚡ Koleksi File Sequence Kustom (custom_sequences/)  ")

        # ══════════════════════════════════════════════════════════════════
        # ── TAB 1: WINDOWS TASK SCHEDULER ──
        # ══════════════════════════════════════════════════════════════════
        toolbar_t1 = tk.Frame(tab_tasks, bg=SAP_TOOLBAR, height=40, padx=8, pady=4)
        toolbar_t1.pack(fill="x")

        tk.Button(
            toolbar_t1, text="⟳ Segarkan", font=FONT_BOLD, bg=SAP_BLUE, fg=SAP_WHITE,
            activebackground=SAP_BLUE_LIGHT, activeforeground=SAP_WHITE, relief="raised", bd=1,
            padx=10, pady=3, cursor="hand2", command=self._load_tasks_async
        ).pack(side="left", padx=4)

        tk.Button(
            toolbar_t1, text="▶ Jalankan Sekarang", font=FONT_BOLD, bg=SAP_SUCCESS, fg=SAP_WHITE,
            activebackground="#2E7D32", activeforeground=SAP_WHITE, relief="raised", bd=1,
            padx=10, pady=3, cursor="hand2", command=self._run_selected_task
        ).pack(side="left", padx=4)

        tk.Button(
            toolbar_t1, text="⏸ Aktif / Nonaktifkan", font=FONT_UI, bg=SAP_GREY_PANEL, fg=SAP_TEXT,
            relief="raised", bd=1, padx=8, pady=3, cursor="hand2", command=self._toggle_selected_task
        ).pack(side="left", padx=4)

        tk.Button(
            toolbar_t1, text="⏰ Ubah Jam Eksekusi", font=FONT_UI, bg=SAP_GREY_PANEL, fg=SAP_TEXT,
            relief="raised", bd=1, padx=8, pady=3, cursor="hand2", command=self._change_task_trigger_time
        ).pack(side="left", padx=4)

        tk.Button(
            toolbar_t1, text="✏ Edit Parameter Sequence...", font=FONT_BOLD, bg="#E8F0FE", fg=SAP_BLUE,
            relief="raised", bd=1, padx=8, pady=3, cursor="hand2", command=self._edit_task_sequence
        ).pack(side="left", padx=4)

        tk.Button(
            toolbar_t1, text="🗑 Hapus Task Windows", font=FONT_UI, bg=SAP_GREY_PANEL, fg=SAP_ERROR,
            relief="raised", bd=1, padx=8, pady=3, cursor="hand2", command=self._delete_selected_task
        ).pack(side="left", padx=4)

        ttk.Separator(toolbar_t1, orient="vertical").pack(side="left", fill="y", padx=8, pady=2)

        tk.Button(
            toolbar_t1, text="⚡ Buat Customize Sequence Baru...", font=FONT_BOLD, bg=SAP_BLUE_LIGHT, fg=SAP_WHITE,
            activebackground=SAP_BLUE, activeforeground=SAP_WHITE, relief="raised", bd=1,
            padx=10, pady=3, cursor="hand2", command=self._open_new_sequence_builder
        ).pack(side="left", padx=4)

        body_t1 = tk.PanedWindow(tab_tasks, orient="vertical", bg=SAP_GREY_BG, sashwidth=4)
        body_t1.pack(fill="both", expand=True, padx=4, pady=4)

        # Upper frame Tab 1: Treeview Tasks
        upper_t1 = tk.Frame(body_t1, bg=SAP_WHITE, bd=1, relief="solid")
        body_t1.add(upper_t1, minsize=160, height=260)

        tree_tasks_frame = tk.Frame(upper_t1, bg=SAP_WHITE)
        tree_tasks_frame.pack(fill="both", expand=True)

        cols_t1 = ("name", "type", "state", "trigger", "next_run", "last_run", "last_result", "desc")
        self._tree_tasks = ttk.Treeview(tree_tasks_frame, columns=cols_t1, show="headings", selectmode="browse")

        self._tree_tasks.heading("name", text="Nama Task Windows")
        self._tree_tasks.heading("type", text="Tipe")
        self._tree_tasks.heading("state", text="Status")
        self._tree_tasks.heading("trigger", text="Jadwal")
        self._tree_tasks.heading("next_run", text="Jadwal Berikutnya")
        self._tree_tasks.heading("last_run", text="Jadwal Terakhir")
        self._tree_tasks.heading("last_result", text="Hasil Terakhir")
        self._tree_tasks.heading("desc", text="Deskripsi")

        self._tree_tasks.column("name", width=220, anchor="w")
        self._tree_tasks.column("type", width=125, anchor="center")
        self._tree_tasks.column("state", width=80, anchor="center")
        self._tree_tasks.column("trigger", width=90, anchor="center")
        self._tree_tasks.column("next_run", width=130, anchor="center")
        self._tree_tasks.column("last_run", width=130, anchor="center")
        self._tree_tasks.column("last_result", width=90, anchor="center")
        self._tree_tasks.column("desc", width=240, anchor="w")

        self._tree_tasks.tag_configure("ready", foreground="#0B6623", font=FONT_BOLD)
        self._tree_tasks.tag_configure("disabled", foreground="#888888")
        self._tree_tasks.tag_configure("running", foreground="#0056B3", font=FONT_BOLD)

        sb_tasks_y = ttk.Scrollbar(tree_tasks_frame, orient="vertical", command=self._tree_tasks.yview)
        sb_tasks_x = ttk.Scrollbar(tree_tasks_frame, orient="horizontal", command=self._tree_tasks.xview)
        self._tree_tasks.configure(yscrollcommand=sb_tasks_y.set, xscrollcommand=sb_tasks_x.set)

        self._tree_tasks.pack(side="left", fill="both", expand=True)
        sb_tasks_y.pack(side="right", fill="y")
        sb_tasks_x.pack(side="bottom", fill="x")

        self._tree_tasks.bind("<<TreeviewSelect>>", self._on_task_tree_select)
        self._tree_tasks.bind("<Double-1>", lambda _: self._show_task_details())

        # Lower frame Tab 1: Detail Task Pane
        lower_t1 = tk.LabelFrame(body_t1, text=" 📌 Detail Task Windows Terpilih ", font=FONT_BOLD,
                                 bg=SAP_WHITE, fg=SAP_BLUE, bd=1, relief="solid", padx=10, pady=6)
        body_t1.add(lower_t1, minsize=130, height=160)

        self._detail_task_text = scrolledtext.ScrolledText(
            lower_t1, font=FONT_MONO, bg=SAP_PARAM_BG, fg=SAP_TEXT,
            relief="flat", wrap="word", height=5
        )
        self._detail_task_text.pack(fill="both", expand=True)
        self._detail_task_text.insert("end", "Pilih task pada tabel di atas untuk melihat detail konfigurasi dan perintah eksekusi.")
        self._detail_task_text.config(state="disabled")

        # ══════════════════════════════════════════════════════════════════
        # ── TAB 2: CUSTOM SEQUENCE FILES ──
        # ══════════════════════════════════════════════════════════════════
        toolbar_t2 = tk.Frame(tab_seqs, bg=SAP_TOOLBAR, height=40, padx=8, pady=4)
        toolbar_t2.pack(fill="x")

        tk.Button(
            toolbar_t2, text="⟳ Segarkan", font=FONT_BOLD, bg=SAP_BLUE, fg=SAP_WHITE,
            activebackground=SAP_BLUE_LIGHT, activeforeground=SAP_WHITE, relief="raised", bd=1,
            padx=10, pady=3, cursor="hand2", command=self._load_tasks_async
        ).pack(side="left", padx=4)

        tk.Button(
            toolbar_t2, text="📅 Daftarkan ke Task Scheduler...", font=FONT_BOLD, bg=SAP_BLUE_LIGHT, fg=SAP_WHITE,
            activebackground=SAP_BLUE, activeforeground=SAP_WHITE, relief="raised", bd=1,
            padx=10, pady=3, cursor="hand2", command=self._register_selected_sequence
        ).pack(side="left", padx=4)

        tk.Button(
            toolbar_t2, text="▶ Jalankan Sequence Sekarang", font=FONT_BOLD, bg=SAP_SUCCESS, fg=SAP_WHITE,
            activebackground="#2E7D32", activeforeground=SAP_WHITE, relief="raised", bd=1,
            padx=10, pady=3, cursor="hand2", command=self._run_selected_sequence_now
        ).pack(side="left", padx=4)

        tk.Button(
            toolbar_t2, text="✏ Buka di Sequence Builder", font=FONT_UI, bg=SAP_GREY_PANEL, fg=SAP_TEXT,
            relief="raised", bd=1, padx=8, pady=3, cursor="hand2", command=self._edit_selected_sequence
        ).pack(side="left", padx=4)

        tk.Button(
            toolbar_t2, text="🗑 Hapus File Sequence", font=FONT_UI, bg=SAP_GREY_PANEL, fg=SAP_ERROR,
            relief="raised", bd=1, padx=8, pady=3, cursor="hand2", command=self._delete_selected_sequence
        ).pack(side="left", padx=4)

        ttk.Separator(toolbar_t2, orient="vertical").pack(side="left", fill="y", padx=8, pady=2)

        tk.Button(
            toolbar_t2, text="➕ Buat Sequence Baru...", font=FONT_BOLD, bg=SAP_BLUE, fg=SAP_WHITE,
            relief="raised", bd=1, padx=10, pady=3, cursor="hand2", command=self._open_new_sequence_builder
        ).pack(side="left", padx=4)

        body_t2 = tk.PanedWindow(tab_seqs, orient="vertical", bg=SAP_GREY_BG, sashwidth=4)
        body_t2.pack(fill="both", expand=True, padx=4, pady=4)

        # Upper frame Tab 2: Treeview Sequences
        upper_t2 = tk.Frame(body_t2, bg=SAP_WHITE, bd=1, relief="solid")
        body_t2.add(upper_t2, minsize=160, height=260)

        tree_seqs_frame = tk.Frame(upper_t2, bg=SAP_WHITE)
        tree_seqs_frame.pack(fill="both", expand=True)

        cols_t2 = ("filename", "name", "status", "steps", "desc")
        self._tree_seqs = ttk.Treeview(tree_seqs_frame, columns=cols_t2, show="headings", selectmode="browse")

        self._tree_seqs.heading("filename", text="Nama File JSON")
        self._tree_seqs.heading("name", text="Nama Sequence")
        self._tree_seqs.heading("status", text="Status di Task Scheduler")
        self._tree_seqs.heading("steps", text="Jumlah Step")
        self._tree_seqs.heading("desc", text="Deskripsi")

        self._tree_seqs.column("filename", width=220, anchor="w")
        self._tree_seqs.column("name", width=200, anchor="w")
        self._tree_seqs.column("status", width=240, anchor="w")
        self._tree_seqs.column("steps", width=100, anchor="center")
        self._tree_seqs.column("desc", width=280, anchor="w")

        self._tree_seqs.tag_configure("reg_yes", foreground="#0B6623", font=FONT_BOLD)
        self._tree_seqs.tag_configure("reg_no", foreground="#7F8C8D")

        sb_seqs_y = ttk.Scrollbar(tree_seqs_frame, orient="vertical", command=self._tree_seqs.yview)
        sb_seqs_x = ttk.Scrollbar(tree_seqs_frame, orient="horizontal", command=self._tree_seqs.xview)
        self._tree_seqs.configure(yscrollcommand=sb_seqs_y.set, xscrollcommand=sb_seqs_x.set)

        self._tree_seqs.pack(side="left", fill="both", expand=True)
        sb_seqs_y.pack(side="right", fill="y")
        sb_seqs_x.pack(side="bottom", fill="x")

        self._tree_seqs.bind("<<TreeviewSelect>>", self._on_seq_tree_select)
        self._tree_seqs.bind("<Double-1>", lambda _: self._edit_selected_sequence())

        # Lower frame Tab 2: Sequence Breakdown Pane
        lower_t2 = tk.LabelFrame(body_t2, text=" 📌 Rincian Langkah Sequence Terpilih ", font=FONT_BOLD,
                                 bg=SAP_WHITE, fg=SAP_BLUE, bd=1, relief="solid", padx=10, pady=6)
        body_t2.add(lower_t2, minsize=130, height=160)

        self._detail_seq_text = scrolledtext.ScrolledText(
            lower_t2, font=FONT_MONO, bg=SAP_PARAM_BG, fg=SAP_TEXT,
            relief="flat", wrap="word", height=5
        )
        self._detail_seq_text.pack(fill="both", expand=True)
        self._detail_seq_text.insert("end", "Pilih file sequence pada tabel di atas untuk melihat rincian langkah job dan parameter.")
        self._detail_seq_text.config(state="disabled")

        # ══════════════════════════════════════════════════════════════════
        # ── FOOTER STATUS BAR ──
        # ══════════════════════════════════════════════════════════════════
        footer = tk.Frame(self, bg=SAP_TOOLBAR, height=28)
        footer.pack(fill="x", side="bottom")

        self._status_var = tk.StringVar(value="Memuat data task dan sequence...")
        tk.Label(footer, textvariable=self._status_var, font=FONT_SMALL, bg=SAP_TOOLBAR, fg=SAP_TEXT).pack(side="left", padx=10, pady=4)

        tk.Button(footer, text="Tutup", font=FONT_SMALL, bg=SAP_GREY_PANEL, fg=SAP_TEXT, relief="flat", padx=10, pady=1, cursor="hand2", command=self.destroy).pack(side="right", padx=10, pady=3)

    def _scan_custom_sequences(self) -> list[dict]:
        seqs = []
        folder = "custom_sequences"
        if not os.path.exists(folder):
            return seqs
        for fn in sorted(os.listdir(folder)):
            if fn.endswith(".json"):
                fp = os.path.join(folder, fn)
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    items = data.get("items", [])
                    for it in items:
                        if not it.get("name"):
                            if it.get("type") in ("wait", "delay") or ((it.get("name") or "").startswith("⏳")):
                                it["type"] = "wait"
                                it["name"] = "⏳ JEDA WAKTU (WAIT)"
                            else:
                                it["type"] = "job"
                                it["name"] = "Job SAP"
                    seqs.append({
                        "filename": fn,
                        "filepath": fp,
                        "name": data.get("name", fn),
                        "description": data.get("description", "—"),
                        "items": items,
                        "steps_count": len(items),
                    })
                except Exception as e:
                    print(f"Error reading sequence {fn}: {e}")
        return seqs

    def _load_tasks_async(self):
        if self._is_loading:
            return
        self._is_loading = True
        self._status_var.set("⏳ Membaca task dari Windows Task Scheduler & folder custom_sequences/...")

        def _worker():
            tasks = scheduler_utils.list_sap_tasks()
            seqs = self._scan_custom_sequences()
            self.after(0, self._populate_all, tasks, seqs)

        threading.Thread(target=_worker, daemon=True).start()

    def _populate_all(self, tasks: list[dict], seqs: list[dict]):
        self._is_loading = False
        self._tasks = tasks
        self._seqs = seqs

        # ── 1. Populate Tab 1: Windows Task Scheduler ──
        for item in self._tree_tasks.get_children():
            self._tree_tasks.delete(item)

        for idx, t in enumerate(tasks):
            t_name = t.get("TaskName", "")
            t_state = t.get("State", "")
            t_trig = t.get("TriggerTime", "—")
            t_next = t.get("NextRunTime", "—")
            t_last = t.get("LastRunTime", "—")
            res_code = t.get("LastTaskResult", -1)
            t_desc = t.get("Description", "—")
            action = t.get("Action", "")

            # Klasifikasi tipe task
            is_seq = "custom_sequence_runner" in action.lower()
            t_type = "⚡ Sequence Kustom" if is_seq else "📦 Batch Pipeline"

            if res_code == 0:
                t_res = "0 (Sukses)"
            elif res_code in (-1, None):
                t_res = "—"
            else:
                t_res = f"{res_code} (Error)"

            tag = "disabled" if t_state.lower() == "disabled" else ("running" if t_state.lower() == "running" else "ready")

            self._tree_tasks.insert(
                "", "end", iid=str(idx),
                values=(t_name, t_type, t_state, t_trig, t_next, t_last, t_res, t_desc),
                tags=(tag,)
            )

        # ── 2. Populate Tab 2: Custom Sequences ──
        for item in self._tree_seqs.get_children():
            self._tree_seqs.delete(item)

        for idx, s in enumerate(seqs):
            fn = s["filename"]
            s_name = s["name"]
            steps_cnt = f"{s['steps_count']} Langkah"
            s_desc = s["description"]

            # Cek apakah terdaftar di Windows Task Scheduler
            matched_task = None
            for t in tasks:
                if fn.lower() in t.get("Action", "").lower():
                    matched_task = t
                    break

            if matched_task:
                s["registered_task"] = matched_task
                reg_status = f"🟢 Terdaftar ({matched_task.get('TaskName')} @ {matched_task.get('TriggerTime')})"
                tag = "reg_yes"
            else:
                s["registered_task"] = None
                reg_status = "⚪ Belum Terdaftar"
                tag = "reg_no"

            self._tree_seqs.insert(
                "", "end", iid=str(idx),
                values=(fn, s_name, reg_status, steps_cnt, s_desc),
                tags=(tag,)
            )

        ts = datetime.now().strftime("%H:%M:%S")
        self._status_var.set(
            f"Ditemukan {len(tasks)} task SAP di Windows Task Scheduler | {len(seqs)} template di custom_sequences/ | Disegarkan: {ts}"
        )

        # Update tab label
        self._nb.tab(0, text=f"  📅 Task Terjadwal di Windows ({len(tasks)})  ")
        self._nb.tab(1, text=f"  ⚡ File Sequence Kustom ({len(seqs)})  ")

        if tasks and not self._tree_tasks.selection():
            self._tree_tasks.selection_set("0")
            self._on_task_tree_select()
        if seqs and not self._tree_seqs.selection():
            self._tree_seqs.selection_set("0")
            self._on_seq_tree_select()

    # ── Handlers Tab 1 (Windows Task Scheduler) ──

    def _get_selected_task(self) -> dict | None:
        sel = self._tree_tasks.selection()
        if not sel:
            messagebox.showinfo("Perhatian", "Pilih task pada tabel terlebih dahulu.", parent=self)
            return None
        idx = int(sel[0])
        if 0 <= idx < len(self._tasks):
            return self._tasks[idx]
        return None

    def _on_task_tree_select(self, event=None):
        sel = self._tree_tasks.selection()
        if not sel:
            return
        idx = int(sel[0])
        if not (0 <= idx < len(self._tasks)):
            return
        t = self._tasks[idx]

        self._detail_task_text.config(state="normal")
        self._detail_task_text.delete("1.0", "end")

        lines = [
            f"Nama Task       : {t.get('TaskName')}",
            f"Status          : {t.get('State')}",
            f"Jadwal Trigger  : {t.get('TriggerTime')}",
            f"Next Run Time   : {t.get('NextRunTime')}",
            f"Last Run Time   : {t.get('LastRunTime')}",
            f"Last Task Result: {t.get('LastTaskResult')}",
            f"Deskripsi       : {t.get('Description')}",
            f"Perintah Action : {t.get('Action')}",
        ]
        self._detail_task_text.insert("end", "\n".join(lines))
        self._detail_task_text.config(state="disabled")

    def _run_selected_task(self):
        t = self._get_selected_task()
        if not t:
            return
        task_name = t.get("TaskName", "")
        if messagebox.askyesno("Konfirmasi Eksekusi", f"Jalankan task '{task_name}' sekarang di latar belakang?", parent=self):
            ok, msg = scheduler_utils.run_task(task_name)
            if ok:
                messagebox.showinfo("Sukses", f"Perintah eksekusi berhasil dikirim ke Windows Task Scheduler:\n\n{msg}", parent=self)
            else:
                messagebox.showerror("Gagal", f"Gagal menjalankan task:\n\n{msg}", parent=self)
            self._load_tasks_async()

    def _toggle_selected_task(self):
        t = self._get_selected_task()
        if not t:
            return
        task_name = t.get("TaskName", "")
        current_state = t.get("State", "").lower()
        new_enable = (current_state == "disabled")

        action_str = "mengaktifkan" if new_enable else "menonaktifkan"
        if messagebox.askyesno("Konfirmasi", f"Apakah Anda yakin ingin {action_str} task '{task_name}'?", parent=self):
            ok, msg = scheduler_utils.set_task_state(task_name, enable=new_enable)
            if ok:
                messagebox.showinfo("Sukses", msg, parent=self)
            else:
                messagebox.showerror("Gagal", msg, parent=self)
            self._load_tasks_async()

    def _delete_selected_task(self):
        t = self._get_selected_task()
        if not t:
            return
        task_name = t.get("TaskName", "")
        if messagebox.askyesno("Konfirmasi Hapus", f"PERINGATAN:\nApakah Anda yakin ingin MENGHAPUS task '{task_name}' dari Windows Task Scheduler secara permanen?", parent=self):
            ok, msg = scheduler_utils.delete_task(task_name)
            if ok:
                messagebox.showinfo("Sukses", msg, parent=self)
            else:
                messagebox.showerror("Gagal", msg, parent=self)
            self._load_tasks_async()

    def _show_task_details(self):
        t = self._get_selected_task()
        if not t:
            return
        t_name = t.get("TaskName", "")
        action = t.get("Action", "")
        desc = t.get("Description", "")
        messagebox.showinfo(
            f"Rincian Task: {t_name}",
            f"Nama Task:\n{t_name}\n\nStatus: {t.get('State')}\nJadwal: {t.get('TriggerTime')}\nNext Run: {t.get('NextRunTime')}\n\nPerintah:\n{action}\n\nDeskripsi:\n{desc}",
            parent=self
        )

    def _change_task_trigger_time(self):
        t = self._get_selected_task()
        if not t:
            return
        task_name = t.get("TaskName", "")
        curr_time = t.get("TriggerTime", "04:30")
        if curr_time in ("—", "", None):
            curr_time = "04:30"

        new_time = simpledialog.askstring(
            "Ubah Jam Eksekusi",
            f"Masukkan jam eksekusi baru untuk task '{task_name}':\nFormat 24 jam HH:mm (contoh: 04:30 atau 23:15)",
            initialvalue=curr_time,
            parent=self
        )
        if not new_time:
            return
        new_time = new_time.strip()
        if not re.match(r"^\d{1,2}:\d{2}$", new_time):
            messagebox.showerror("Format Jam Salah", "Format waktu harus HH:mm (contoh: 04:30 atau 23:15).", parent=self)
            return

        ok, msg = scheduler_utils.update_task_time(task_name, new_time)
        if ok:
            messagebox.showinfo("Sukses", f"Jadwal task '{task_name}' berhasil diubah!\n\n{msg}", parent=self)
            self._load_tasks_async()
        else:
            messagebox.showerror("Gagal", f"Gagal mengubah jam eksekusi:\n\n{msg}", parent=self)

    def _edit_task_sequence(self):
        t = self._get_selected_task()
        if not t:
            return
        action = t.get("Action", "")
        m = re.search(r'--sequence-file\s+["\']?([^"\']+)["\']?', action, re.IGNORECASE)
        if not m:
            messagebox.showinfo(
                "Bukan Task Sequence Kustom",
                f"Task '{t.get('TaskName')}' tidak dikonfigurasi dengan sequence runner kustom (--sequence-file).\n\n"
                f"Perintah Action:\n{action}",
                parent=self
            )
            return

        seq_rel_path = m.group(1).strip()
        seq_abs_path = os.path.abspath(seq_rel_path)
        if not os.path.exists(seq_abs_path):
            messagebox.showerror(
                "File Tidak Ditemukan",
                f"File konfigurasi sequence tidak ditemukan di path:\n{seq_rel_path}",
                parent=self
            )
            return

        try:
            with open(seq_abs_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            items = data.get("items", [])
        except Exception as e:
            messagebox.showerror("Error", f"Gagal membaca file sequence:\n{e}", parent=self)
            return

        SequenceBuilderDialog(
            self.parent,
            initial_items=items,
            initial_file=seq_abs_path,
            on_saved=self._load_tasks_async
        )

    # ── Handlers Tab 2 (Custom Sequences) ──

    def _get_selected_sequence(self) -> dict | None:
        sel = self._tree_seqs.selection()
        if not sel:
            messagebox.showinfo("Perhatian", "Pilih file sequence pada tabel terlebih dahulu.", parent=self)
            return None
        idx = int(sel[0])
        if 0 <= idx < len(self._seqs):
            return self._seqs[idx]
        return None

    def _on_seq_tree_select(self, event=None):
        sel = self._tree_seqs.selection()
        if not sel:
            return
        idx = int(sel[0])
        if not (0 <= idx < len(self._seqs)):
            return
        s = self._seqs[idx]

        self._detail_seq_text.config(state="normal")
        self._detail_seq_text.delete("1.0", "end")

        reg_info = "Belum terdaftar di Windows Task Scheduler"
        if s.get("registered_task"):
            rt = s["registered_task"]
            reg_info = f"🟢 Terdaftar di Windows Task Scheduler (Task: {rt.get('TaskName')}, Pukul: {rt.get('TriggerTime')})"

        lines = [
            f"File Sequence : {s.get('filename')}",
            f"Nama Sequence : {s.get('name')}",
            f"Status Jadwal : {reg_info}",
            f"Deskripsi     : {s.get('description')}",
            "",
            f"Daftar Langkah ({s.get('steps_count')} Langkah):",
        ]
        for step_idx, it in enumerate(s.get("items", [])):
            it_type = it.get("type", "job")
            if it_type in ("wait", "delay") or it.get("name", "").startswith("⏳"):
                lines.append(f"  [{step_idx + 1}] ⏳ JEDA WAKTU: {it.get('seconds', 60)} detik — {it.get('desc', '')}")
            else:
                lines.append(f"  [{step_idx + 1}] 🚀 JOB SAP: {it.get('name')}")
                params = it.get("params", {})
                for pk, pv in params.items():
                    if not str(pk).startswith("sch-"):
                        lines.append(f"        • {pk} = {pv}")

        self._detail_seq_text.insert("end", "\n".join(lines))
        self._detail_seq_text.config(state="disabled")

    def _register_selected_sequence(self):
        s = self._get_selected_sequence()
        if not s:
            return
        RegisterTaskSchedulerDialog(self, s["items"], on_success=self._load_tasks_async)

    def _run_selected_sequence_now(self):
        s = self._get_selected_sequence()
        if not s:
            return
        seq_name = s.get("name", s.get("filename"))
        if messagebox.askyesno("Konfirmasi Eksekusi", f"Jalankan sequence '{seq_name}' sekarang di layar monitor GUI?", parent=self):
            SequenceProgressDialog(
                parent=self.parent,
                sequence_items=list(s["items"]),
                db_config=self.parent._get_db_config(),
                stop_on_error=True
            )

    def _edit_selected_sequence(self):
        s = self._get_selected_sequence()
        if not s:
            return
        SequenceBuilderDialog(
            self.parent,
            initial_items=s["items"],
            initial_file=s.get("filepath"),
            on_saved=self._load_tasks_async
        )

    def _delete_selected_sequence(self):
        s = self._get_selected_sequence()
        if not s:
            return
        fn = s.get("filename")
        if messagebox.askyesno("Konfirmasi Hapus", f"Apakah Anda yakin ingin menghapus file template sequence '{fn}'?", parent=self):
            try:
                os.remove(s["filepath"])
                messagebox.showinfo("Sukses", f"File '{fn}' berhasil dihapus.", parent=self)
            except Exception as e:
                messagebox.showerror("Error", f"Gagal menghapus file:\n{e}", parent=self)
            self._load_tasks_async()

    def _open_new_sequence_builder(self):
        SequenceBuilderDialog(self.parent, on_saved=self._load_tasks_async)


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
