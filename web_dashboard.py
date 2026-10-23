import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
import sys
from datetime import datetime
from contextlib import asynccontextmanager

# Pastikan output stream menggunakan UTF-8 di Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config import DB_CONFIG
from job_definitions import SCRIPTS, resolve_default, build_cli_args, validate_job_config
from sap_utils import get_sap_status
from job_runner import (
    build_job_command, classify_log_tag, stop_job as jr_stop_job,
    STATUS_IDLE, STATUS_RUNNING, STATUS_SUCCESS, STATUS_FAILED,
)
import scheduler_utils
from custom_sequence_runner import resolve_dynamic_params, resolve_dynamic_value

# Config File
CONFIG_FILE = "job_config.json"

# State Global
active_jobs = {}  # job_name -> {status, start_time, end_time, logs}
listeners = {}    # job_name -> list[asyncio.Queue]
database_config = {
    "server": DB_CONFIG["server"],
    "user": DB_CONFIG["user"],
    "pwd": DB_CONFIG["pwd"],
    "name": DB_CONFIG["name"]
}

# get_sap_status() telah dipindahkan ke sap_utils.py


def log_line(job_name: str, tag: str, text: str):
    """Simpan dan sebarkan log secara real-time."""
    ts = datetime.now().strftime("[%H:%M:%S]")
    formatted_log = f"{ts} [{tag}]  {text}"
    
    if job_name in active_jobs:
        active_jobs[job_name]["logs"].append({"tag": tag, "text": formatted_log})
    
    if job_name in listeners:
        for q in listeners[job_name]:
            asyncio.create_task(q.put({"tag": tag, "text": formatted_log}))

def collect_args(name: str, params: dict) -> list[str]:
    """Kumpulkan argumen baris perintah (delegasi ke modul bersama)."""
    return build_cli_args(name, params, db_config=database_config)

def get_job_params_from_config(name: str) -> dict:
    """Ambil parameter default / tersimpan untuk penjadwalan otomatis."""
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            pass
            
    job_config = config.get(name, {})
    params = {}
    for p in SCRIPTS[name]["params"]:
        arg = p["arg"]
        val = job_config.get(arg)
        if val is None:
            val = resolve_default(p["default"])
        params[arg] = val
    return params

async def run_job_async(name: str, params: dict = None):
    """Menjalankan script Python secara asinkron."""
    if name in active_jobs and active_jobs[name]["status"] == STATUS_RUNNING:
        return
        
    if params is None:
        params = get_job_params_from_config(name)
        
    try:
        script_path, full_cmd = build_job_command(name, params, db_config=database_config)
    except FileNotFoundError:
        log_line(name, "ERROR", f"Script tidak ditemukan")
        return
    
    extra_args = full_cmd[2:]  # skip sys.executable & script_path
    
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    active_jobs[name] = {
        "status": STATUS_RUNNING,
        "start_time": start_time,
        "end_time": None,
        "logs": []
    }
    
    info = SCRIPTS[name]
    cmd_display = f"python {info['file']} " + " ".join(extra_args)
    log_line(name, "HEADER", f"{'-'*62}\n  JOB    : {name}\n  START  : {start_time}\n  CMD    : {cmd_display}\n{'-'*62}")
    
    try:
        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8"
        child_env["PYTHONUTF8"] = "1"

        proc = await asyncio.create_subprocess_exec(
            *full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=os.path.dirname(script_path),
            env=child_env
        )
        active_jobs[name]["proc"] = proc
        active_jobs[name]["pid"] = proc.pid
        
        while True:
            line_bytes = await proc.stdout.readline()
            if not line_bytes:
                break
            line = line_bytes.decode('utf-8', errors='replace').rstrip()
            if not line:
                continue
            
            tag = classify_log_tag(line)
            
            log_line(name, tag, line)
            
        await proc.wait()
        ok = proc.returncode == 0
    except Exception as e:
        log_line(name, "ERROR", f"Gagal menjalankan proses: {e}")
        ok = False
        
    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = "SUCCESS [OK]" if ok else "FAILED [ERROR]"
    status_str = STATUS_SUCCESS if ok else STATUS_FAILED
    
    active_jobs[name]["status"] = status_str
    active_jobs[name]["end_time"] = end_time
    active_jobs[name].pop("proc", None)
    active_jobs[name].pop("pid", None)
    
    log_line(name, "HEADER", f"{'-'*62}\n  SELESAI: {result}   pukul {end_time}\n{'-'*62}")
    
    if name in listeners:
        for q in list(listeners[name]):
            await q.put(None)

async def scheduler_loop():
    """Background Loop untuk memeriksa Scheduler setiap 30 detik."""
    last_triggered = {}  # job -> YYYY-MM-DD HH:MM
    while True:
        try:
            now = datetime.now()
            current_hm = now.strftime("%H:%M")
            current_date_hm = now.strftime("%Y-%m-%d %H:%M")
            
            config = {}
            if os.path.exists(CONFIG_FILE):
                try:
                    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                        config = json.load(f)
                except Exception:
                    pass
            
            for name, info in SCRIPTS.items():
                job_config = config.get(name, {})
                sch_time = job_config.get("sch-time")
                sch_day = job_config.get("sch-day")
                sch_active = job_config.get("sch-active")
                
                if sch_time is None:
                    sch_time = next((p["default"] for p in info["params"] if p["arg"] == "sch-time"), "")
                if sch_day is None:
                    sch_day = next((p["default"] for p in info["params"] if p["arg"] == "sch-day"), "*")
                if sch_active is None:
                    sch_active = next((p["default"] for p in info["params"] if p["arg"] == "sch-active"), "False")
                
                day_match = True
                if sch_day and str(sch_day).strip() not in ("*", "ALL", "all", "—", ""):
                    target_days = [d.strip().lstrip("0") for d in str(sch_day).split(",") if d.strip()]
                    day_match = str(now.day) in target_days

                if str(sch_active).lower() == "true" and day_match and sch_time == current_hm:
                    if last_triggered.get(name) != current_date_hm:
                        is_running = name in active_jobs and active_jobs[name]["status"] == STATUS_RUNNING
                        if not is_running:
                            last_triggered[name] = current_date_hm
                            # Pemicu asinkron
                            asyncio.create_task(run_job_async(name))
                            
        except Exception as e:
            print(f"Error in scheduler loop: {e}")
        await asyncio.sleep(30)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global database_config
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                if "db_settings" in config:
                    database_config.update(config["db_settings"])
            # Validasi struktur config — cetak warning jika ada key/arg tidak dikenal
            is_valid, warnings = validate_job_config(config)
            if not is_valid:
                for w in warnings:
                    print(f"[WARNING] {w}")
        except Exception:
            pass
            
    scheduler_task = asyncio.create_task(scheduler_loop())
    yield
    # Shutdown
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass

# FastAPI App
app = FastAPI(title="SAP Automation Web Dashboard", lifespan=lifespan)

# Allow CORS. Dashboard lokal tanpa autentikasi/cookie, jadi wildcard tanpa
# credentials adalah pilihan paling aman & menghindari pemblokiran request.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serves static dashboard files
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    """Nonaktifkan cache browser untuk dashboard lokal agar JS/CSS/HTML
    selalu memuat versi terbaru (mencegah masalah file usang dari cache)."""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

@app.get("/api/jobs")
async def get_jobs():
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            pass
            
    jobs_list = []
    for name, info in SCRIPTS.items():
        job_config = config.get(name, {})
        params_with_values = []
        for p in info["params"]:
            val = job_config.get(p["arg"])
            if val is None:
                val = resolve_default(p["default"])
            
            params_with_values.append({
                "arg": p["arg"],
                "label": p["label"],
                "value": val,
                "type": p["type"],
                "help": p["help"]
            })
            
        status = STATUS_IDLE
        last_run = "—"
        if name in active_jobs:
            status = active_jobs[name]["status"]
            last_run = active_jobs[name]["start_time"]
            
        jobs_list.append({
            "name": name,
            "file": info["file"],
            "desc": info["desc"],
            "params": params_with_values,
            "status": status,
            "last_run": last_run
        })
    return jobs_list

@app.get("/api/db-config")
async def get_db_config():
    return database_config

class DBConfigModel(BaseModel):
    server: str
    user: str
    pwd: str
    name: str

@app.post("/api/db-config")
async def save_db_config(db_cfg: DBConfigModel):
    global database_config
    # Simpan lengkap (termasuk pwd) di memory untuk dipakai saat runtime.
    database_config = db_cfg.dict()

    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            pass

    # Tulis ke file JSON TANPA pwd — password tidak boleh tersimpan di plaintext.
    # Saat startup berikutnya, pwd akan dibaca dari .env via config.py.
    config["db_settings"] = {
        "server": db_cfg.server,
        "user":   db_cfg.user,
        "name":   db_cfg.name,
        # "pwd" sengaja dihilangkan — jangan simpan password ke file JSON
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

    return {"message": "Database settings saved successfully"}

class ExecuteJobModel(BaseModel):
    job_name: str
    params: dict

@app.post("/api/jobs/execute")
async def execute_job(data: ExecuteJobModel, background_tasks: BackgroundTasks):
    name = data.job_name
    params = data.params
    
    if name not in SCRIPTS:
        raise HTTPException(status_code=400, detail="Job not found")
        
    if name in active_jobs and active_jobs[name]["status"] == STATUS_RUNNING:
        return {"status": "already running", "message": "Job is already executing"}
        
    # Simpan ke config file
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            pass
            
    config[name] = params
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
        
    # Jalankan di background
    background_tasks.add_task(run_job_async, name, params)
    return {"status": "started", "message": f"Job {name} started successfully"}

class StopJobModel(BaseModel):
    job_name: str

def _kill_proc_tree(pid: int):
    """Delegate ke job_runner.stop_job."""
    return jr_stop_job(pid)

@app.post("/api/jobs/stop")
async def stop_job(data: StopJobModel):
    name = data.job_name
    if name not in SCRIPTS:
        raise HTTPException(status_code=400, detail="Job not found")

    job = active_jobs.get(name)
    if not job or job.get("status") != STATUS_RUNNING:
        return {"status": "not running", "message": "Job tidak sedang berjalan"}

    pid = job.get("pid")
    proc = job.get("proc")
    if pid is None and proc is None:
        return {"status": "no process", "message": "Handle proses tidak ditemukan"}

    log_line(name, "WARN", f"Menghentikan job '{name}' atas permintaan pengguna…")
    if pid is not None:
        _kill_proc_tree(pid)
    elif proc is not None:
        try:
            proc.kill()
        except Exception:
            pass

    return {"status": "stopping", "message": f"Permintaan stop dikirim untuk job {name}"}

@app.get("/api/sap/status")
async def sap_status():
    """Endpoint cek status SAP GUI Scripting (untuk tombol Test SAP)."""
    return get_sap_status()

@app.post("/api/sap/login")
async def sap_login():
    """Menjalankan LoginSAP.vbs (login dari kredensial .env) di background."""
    import subprocess
    vbs = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vbs", "LoginSAP.vbs")
    if not os.path.exists(vbs):
        raise HTTPException(status_code=404, detail="LoginSAP.vbs tidak ditemukan")
    try:
        subprocess.Popen(["wscript.exe", vbs])
        return {
            "status": "started",
            "message": "LoginSAP.vbs dijalankan. Tunggu beberapa detik, lalu klik 'Test SAP' untuk cek status.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menjalankan LoginSAP.vbs: {e}")

@app.post("/api/jobs/save-config")
async def save_job_config(data: ExecuteJobModel):
    name = data.job_name
    params = data.params
    
    if name not in SCRIPTS:
        raise HTTPException(status_code=400, detail="Job not found")
        
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            pass
            
    config[name] = params
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
        
    return {"message": "Configuration saved successfully"}

class BrowseModel(BaseModel):
    type: str
    current_value: str = ""

@app.post("/api/utils/browse")
def browse_dialog(data: BrowseModel):
    import tkinter as tk
    from tkinter import filedialog
    
    browse_type = data.type
    curr = data.current_value
    
    # Expand environment variables if any
    expanded_curr = os.path.expandvars(curr)
    initial_dir = expanded_curr if os.path.isdir(expanded_curr) else os.path.dirname(expanded_curr)
    if not initial_dir or not os.path.exists(initial_dir):
        initial_dir = os.path.expanduser("~")
        
    try:
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes('-topmost', 1)  # Force dialog to top
        
        path = None
        if browse_type == "folder":
            path = filedialog.askdirectory(initialdir=initial_dir, title="Pilih Folder")
            if path:
                path = path.replace("/", "\\") + "\\"
        else:
            path = filedialog.askopenfilename(initialdir=initial_dir, title="Pilih File")
            if path:
                path = path.replace("/", "\\")
                
        root.destroy()
        return {"path": path}
    except Exception as e:
        print(f"Error in browse dialog: {e}")
        return {"path": None}

class InspectModel(BaseModel):
    periode: str = ""
    base_drive: str = "D:\\Kerja"

@app.post("/api/utils/inspect-variables")
def inspect_variables_api(data: InspectModel):
    from path_resolver import resolve_workspace_paths
    p_val = data.periode.strip() if data.periode else datetime.now().strftime("%Y-%m-%d")
    paths = resolve_workspace_paths(p_val, base_drive=data.base_drive)
    return {
        "periode": p_val,
        "paths": paths
    }

@app.get("/api/jobs/stream-log")
async def stream_log(job_name: str):
    if job_name not in SCRIPTS:
        raise HTTPException(status_code=400, detail="Job not found")
        
    async def event_generator():
        # Kirim log history yang ada terlebih dahulu
        if job_name in active_jobs:
            for log in active_jobs[job_name]["logs"]:
                yield f"data: {json.dumps(log)}\n\n"
                
        # Jika job tidak jalan, stop sesudah memunculkan history
        if job_name not in active_jobs or active_jobs[job_name]["status"] != STATUS_RUNNING:
            yield f"data: {json.dumps({'tag': 'SYSTEM', 'text': '[SYSTEM] Menampilkan riwayat log selesai. Job saat ini tidak berjalan.'})}\n\n"
            return
            
        q = asyncio.Queue()
        if job_name not in listeners:
            listeners[job_name] = []
        listeners[job_name].append(q)
        
        try:
            while True:
                msg = await q.get()
                if msg is None:  # Done marker
                    yield f"data: {json.dumps({'tag': 'SYSTEM', 'text': '[SYSTEM] Eksekusi job selesai.'})}\n\n"
                    break
                yield f"data: {json.dumps(msg)}\n\n"
        finally:
            listeners[job_name].remove(q)
            if not listeners[job_name]:
                del listeners[job_name]
                
    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── Windows Task Scheduler API Endpoints ────────────────────────────────────────

class SchedulerRunRequest(BaseModel):
    task_name: str

class SchedulerStateRequest(BaseModel):
    task_name: str
    enable: bool

class SchedulerDeleteRequest(BaseModel):
    task_name: str

class SchedulerRegisterRequest(BaseModel):
    task_name: str
    target_cmd: str
    run_time: str = "08:00"
    description: str = ""

@app.get("/api/scheduler/tasks")
async def get_scheduler_tasks():
    """Mengambil daftar task SAP Automation dari Windows Task Scheduler."""
    return scheduler_utils.list_sap_tasks()

@app.post("/api/scheduler/run")
async def run_scheduler_task(req: SchedulerRunRequest):
    """Memicu eksekusi task Windows Task Scheduler."""
    ok, msg = scheduler_utils.run_task(req.task_name)
    return {"success": ok, "message": msg}

@app.post("/api/scheduler/state")
async def set_scheduler_state(req: SchedulerStateRequest):
    """Mengaktifkan atau menonaktifkan task di Windows Task Scheduler."""
    ok, msg = scheduler_utils.set_task_state(req.task_name, enable=req.enable)
    return {"success": ok, "message": msg}

@app.post("/api/scheduler/delete")
async def delete_scheduler_task(req: SchedulerDeleteRequest):
    """Menghapus task dari Windows Task Scheduler."""
    ok, msg = scheduler_utils.delete_task(req.task_name)
    return {"success": ok, "message": msg}

@app.post("/api/scheduler/register")
async def register_scheduler_task(req: SchedulerRegisterRequest):
    """Mendaftarkan task harian baru ke Windows Task Scheduler."""
    ok, msg = scheduler_utils.register_daily_task(
        task_name=req.task_name,
        target_cmd=req.target_cmd,
        run_time=req.run_time,
        description=req.description,
    )
    return {"success": ok, "message": msg}


if __name__ == "__main__":
    import uvicorn
    # Jalankan server secara lokal
    print("=" * 55)
    print(" SAP Automation Web Server  |  versi 3.1 (no-cache)")
    print(" URL: http://127.0.0.1:8000")
    print("=" * 55)
    uvicorn.run(app, host="127.0.0.1", port=8000)
