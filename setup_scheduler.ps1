# setup_scheduler.ps1 — Registrasi Otomatis Windows Task Scheduler untuk SAP Automation
# Menjadwalkan eksekusi run_daily.bat setiap Senin s/d Jumat pukul 08:00 Pagi

Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "  SAP AUTOMATION -- WINDOWS TASK SCHEDULER SETUP (SENIN-JUMAT 08:00)" -ForegroundColor Cyan
Write-Host "==============================================================================" -ForegroundColor Cyan

$TaskName = "SAP_Automation_Daily_Pipeline"
$ProjectDir = $PSScriptRoot
$BatPath = Join-Path $ProjectDir "run_daily.bat"

if (-not (Test-Path $BatPath)) {
    Write-Host "[ERROR] File run_daily.bat tidak ditemukan di $BatPath" -ForegroundColor Red
    exit 1
}

Write-Host "[INFO] Direktori Kerja : $ProjectDir"
Write-Host "[INFO] Target Batch    : $BatPath"
Write-Host "[INFO] Jadwal          : Setiap Senin - Jumat pukul 08:00 Pagi"

# 1. Action: Jalankan batch script
$CmdArg = "/c `"" + $BatPath + "`""
$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $CmdArg -WorkingDirectory $ProjectDir

# 2. Trigger: Setiap Senin s/d Jumat pukul 08:00
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 08:00AM

# 3. Settings: Jalankan sesegera mungkin jika laptop terlambat dinyalakan (StartWhenAvailable)
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 3) -MultipleInstances IgnoreNew

# 4. Registrasi Task ke Windows
try {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

    $TaskDescription = 'Eksekusi otomatis pipeline harian SAP Automation (6 Tahap) setiap hari kerja pukul 08:00 pagi.'
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description $TaskDescription -ErrorAction Stop | Out-Null

    Write-Host ""
    Write-Host "[BERHASIL] Task '$TaskName' berhasil didaftarkan ke Windows Task Scheduler!" -ForegroundColor Green
    Write-Host "[FITUR AKTIF] 'Start When Available' aktif: Jika laptop baru menyala lewat jam 08:00, task akan langsung dieksekusi." -ForegroundColor Yellow
}
catch {
    Write-Host ""
    Write-Host "[ERROR] Gagal mendaftarkan task: $_" -ForegroundColor Red
    Write-Host "[TIPS] Jalankan PowerShell sebagai Administrator jika membutuhkan hak akses elevated." -ForegroundColor Yellow
}

Write-Host "==============================================================================" -ForegroundColor Cyan
