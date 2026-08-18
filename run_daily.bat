@echo off
REM ==============================================================================
REM SAP AUTOMATION & SERVICE PERFORMANCE — DAILY AUTOMATED PIPELINE RUNNER
REM ==============================================================================
REM File ini dirancang untuk dijalankan manual atau via Windows Task Scheduler.
REM Mengeksekusi seluruh 6 tahapan secara berurutan dan menyimpan log ke folder logs\

setlocal enabledelayedexpansion

REM Pindah ke direktori script ini berada
cd /d "%~dp0"

REM Buat folder logs jika belum ada
if not exist "logs" mkdir "logs"

REM Ambil timestamp untuk nama file log (YYYYMMDD_HHMMSS)
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set dt=%%I
set TIMESTAMP=%dt:~0,8%_%dt:~8,6%
set LOG_FILE=logs\daily_pipeline_%TIMESTAMP%.log

echo ============================================================================== >> "%LOG_FILE%" 2>&1
echo  SAP AUTOMATION — DAILY END-TO-END PIPELINE RUNNER >> "%LOG_FILE%" 2>&1
echo  Waktu Mulai: %DATE% %TIME% >> "%LOG_FILE%" 2>&1
echo ============================================================================== >> "%LOG_FILE%" 2>&1

echo [INFO] Menjalankan Daily Orchestrator...
echo [INFO] Log dicatat ke: %LOG_FILE%

REM Cek apakah ada virtual environment venv\Scripts\python.exe
if exist "venv\Scripts\python.exe" (
    echo [INFO] Menggunakan Virtual Environment: venv\Scripts\python.exe >> "%LOG_FILE%" 2>&1
    venv\Scripts\python.exe daily_orchestrator.py >> "%LOG_FILE%" 2>&1
) else (
    echo [INFO] Menggunakan System Python >> "%LOG_FILE%" 2>&1
    python daily_orchestrator.py >> "%LOG_FILE%" 2>&1
)

set EXIT_CODE=%ERRORLEVEL%

echo ============================================================================== >> "%LOG_FILE%" 2>&1
echo  Waktu Selesai : %DATE% %TIME% >> "%LOG_FILE%" 2>&1
echo  Exit Code     : %EXIT_CODE% >> "%LOG_FILE%" 2>&1
echo ============================================================================== >> "%LOG_FILE%" 2>&1

if %EXIT_CODE% equ 0 (
    echo [SUCCESS] Daily Pipeline selesai dengan sukses!
) else (
    echo [ERROR] Daily Pipeline mengalami kegagalan (Exit code %EXIT_CODE%). Cek file log: %LOG_FILE%
)

exit /b %EXIT_CODE%
