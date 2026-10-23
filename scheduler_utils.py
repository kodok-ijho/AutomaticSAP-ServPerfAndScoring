"""scheduler_utils.py — Utilitas Manajemen Windows Task Scheduler untuk SAP Automation.

Menyediakan fungsi Python untuk:
1. Melihat daftar task terjadwal SAP Automation (list/query).
2. Menjalankan task sekarang (run now).
3. Mengaktifkan/menonaktifkan task (enable/disable).
4. Menghapus task (delete).
5. Mendaftarkan task baru ke Windows Task Scheduler (register).
"""

import os
import sys
import json
import subprocess
from datetime import datetime


def list_sap_tasks() -> list[dict]:
    """Mengambil daftar task di Windows Task Scheduler yang terkait dengan SAP Automation."""
    ps_script = """
    Get-ScheduledTask | Where-Object { $_.TaskName -like '*SAP*' } | ForEach-Object {
        $info = Get-ScheduledTaskInfo -TaskName $_.TaskName -ErrorAction SilentlyContinue
        $trig = $_.Triggers | ForEach-Object {
            if ($_.StartBoundary) { $_.StartBoundary.Substring(11, 5) }
            elseif ($_.Repetition.Interval) { "Interval " + $_.Repetition.Interval }
            else { "Custom" }
        }
        [PSCustomObject]@{
            TaskName = $_.TaskName
            State = $_.State.ToString()
            Description = if ($_.Description) { $_.Description } else { "—" }
            TriggerTime = if ($trig) { ($trig -join ', ') } else { "Manual" }
            NextRunTime = if ($info.NextRunTime -and $info.NextRunTime.Year -gt 2000) { $info.NextRunTime.ToString('yyyy-MM-dd HH:mm:ss') } else { "—" }
            LastRunTime = if ($info.LastRunTime -and $info.LastRunTime.Year -gt 2000) { $info.LastRunTime.ToString('yyyy-MM-dd HH:mm:ss') } else { "—" }
            LastTaskResult = if ($null -ne $info.LastTaskResult) { $info.LastTaskResult } else { -1 }
            Action = ($_.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -join '; '
        }
    } | ConvertTo-Json -Depth 3
    """
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True,
            text=True,
            check=False,
        )
        out = res.stdout.strip()
        if not out:
            return []
        data = json.loads(out)
        if isinstance(data, dict):
            return [data]
        elif isinstance(data, list):
            return data
        return []
    except Exception as e:
        print(f"[SCHEDULER ERROR] Gagal membaca Task Scheduler: {e}")
        return []


def run_task(task_name: str) -> tuple[bool, str]:
    """Menjalankan task Windows Task Scheduler secara langsung."""
    try:
        res = subprocess.run(
            ["schtasks", "/run", "/tn", task_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            return True, f"Task '{task_name}' berhasil dipicu untuk berjalan di latar belakang."
        return False, res.stderr.strip() or res.stdout.strip()
    except Exception as e:
        return False, str(e)


def set_task_state(task_name: str, enable: bool = True) -> tuple[bool, str]:
    """Mengaktifkan atau menonaktifkan task Windows Task Scheduler."""
    action = "/enable" if enable else "/disable"
    try:
        res = subprocess.run(
            ["schtasks", "/change", "/tn", task_name, action],
            capture_output=True,
            text=True,
            check=False,
        )
        state_str = "diaktifkan" if enable else "dinonaktifkan"
        if res.returncode == 0:
            return True, f"Task '{task_name}' berhasil {state_str}."
        return False, res.stderr.strip() or res.stdout.strip()
    except Exception as e:
        return False, str(e)


def delete_task(task_name: str) -> tuple[bool, str]:
    """Menghapus task dari Windows Task Scheduler."""
    try:
        res = subprocess.run(
            ["schtasks", "/delete", "/tn", task_name, "/f"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            return True, f"Task '{task_name}' berhasil dihapus dari Windows Task Scheduler."
        return False, res.stderr.strip() or res.stdout.strip()
    except Exception as e:
        return False, str(e)


def register_daily_task(
    task_name: str,
    target_cmd: str,
    run_time: str = "08:00",
    work_dir: str | None = None,
    description: str = "",
) -> tuple[bool, str]:
    """Mendaftarkan task harian baru ke Windows Task Scheduler.
    
    Args:
        task_name: Nama task (contoh: 'SAP_ZSMR012_Daily_15Days')
        target_cmd: Perintah command line yang akan dieksekusi
        run_time: Jam eksekusi format HH:mm (contoh: '07:30')
        work_dir: Direktori kerja
        description: Deskripsi tugas
    """
    if not task_name.startswith("SAP_"):
        task_name = f"SAP_{task_name}"

    clean_time = run_time.strip()
    # Validasi format HH:mm
    try:
        parts = clean_time.split(":")
        if len(parts) != 2:
            raise ValueError
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
        clean_time = f"{h:02d}:{m:02d}"
    except Exception:
        return False, f"Format jam tidak valid: '{run_time}'. Gunakan format HH:mm (contoh: 07:30)."

    effective_dir = work_dir or os.path.dirname(os.path.abspath(__file__))

    # Gunakan PowerShell Register-ScheduledTask untuk support WorkingDirectory & Description dengan rapi
    ps_cmd = f"""
    $action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument '/c {target_cmd}' -WorkingDirectory '{effective_dir}'
    $trigger = New-ScheduledTaskTrigger -Daily -At '{clean_time}'
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    Register-ScheduledTask -TaskName '{task_name}' -Action $action -Trigger $trigger -Settings $settings -Description '{description}' -Force | Out-Null
    """

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            return True, f"Task '{task_name}' berhasil didaftarkan ke Windows Task Scheduler untuk dijalankan setiap hari pukul {clean_time}."
        return False, res.stderr.strip() or res.stdout.strip()
    except Exception as e:
        return False, str(e)


def update_task_time(task_name: str, new_time: str) -> tuple[bool, str]:
    """Mengubah jam eksekusi harian untuk task yang sudah terdaftar di Windows Task Scheduler."""
    clean_time = new_time.strip()
    try:
        parts = clean_time.split(":")
        if len(parts) != 2:
            raise ValueError
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
        clean_time = f"{h:02d}:{m:02d}"
    except Exception:
        return False, f"Format jam tidak valid: '{new_time}'. Gunakan format HH:mm (contoh: 07:30)."

    ps_cmd = f"""
    $trig = New-ScheduledTaskTrigger -Daily -At '{clean_time}'
    Set-ScheduledTask -TaskName '{task_name}' -Trigger $trig | Out-Null
    """
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            return True, f"Jadwal task '{task_name}' berhasil diubah menjadi pukul {clean_time} setiap hari."
        return False, res.stderr.strip() or res.stdout.strip()
    except Exception as e:
        return False, str(e)


if __name__ == "__main__":
    tasks = list_sap_tasks()
    print(f"Ditemukan {len(tasks)} task SAP Automation di Task Scheduler:")
    for t in tasks:
        print(f" - {t['TaskName']} | State: {t['State']} | Trigger: {t['TriggerTime']} | Next: {t['NextRunTime']}")
