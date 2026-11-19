@echo off
rem ==============================================================================
rem SAP AUTOMATION - ZSMR012 DAILY AUTOMATED PIPELINE RUNNER
rem ==============================================================================
setlocal enabledelayedexpansion

cd /d "%~dp0"

if not exist "logs" mkdir "logs"

for /f "usebackq tokens=*" %%a in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"`) do set TIMESTAMP=%%a
if "%TIMESTAMP%"=="" set TIMESTAMP=%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%
set LOG_FILE=logs\zsmr012_daily_%TIMESTAMP%.log

echo ============================================================================== >> "%LOG_FILE%" 2>&1
echo  SAP AUTOMATION - ZSMR012 DAILY PIPELINE RUNNER >> "%LOG_FILE%" 2>&1
echo  Waktu Mulai: %DATE% %TIME% >> "%LOG_FILE%" 2>&1
echo ============================================================================== >> "%LOG_FILE%" 2>&1

echo [INFO] Menjalankan ZSMR012 Sequence Runner...
echo [INFO] Log dicatat ke: %LOG_FILE%

if exist "venv\Scripts\python.exe" (
    echo [INFO] Menggunakan Virtual Environment >> "%LOG_FILE%" 2>&1
    venv\Scripts\python.exe custom_sequence_runner.py --sequence-file custom_sequences\zsmr012_daily_15days.json >> "%LOG_FILE%" 2>&1
) else (
    echo [INFO] Menggunakan System Python >> "%LOG_FILE%" 2>&1
    python custom_sequence_runner.py --sequence-file custom_sequences\zsmr012_daily_15days.json >> "%LOG_FILE%" 2>&1
)

set EXIT_CODE=%ERRORLEVEL%

echo ============================================================================== >> "%LOG_FILE%" 2>&1
echo  Waktu Selesai : %DATE% %TIME% >> "%LOG_FILE%" 2>&1
echo  Exit Code     : %EXIT_CODE% >> "%LOG_FILE%" 2>&1
echo ============================================================================== >> "%LOG_FILE%" 2>&1

if %EXIT_CODE% equ 0 (
    echo [SUCCESS] ZSMR012 Pipeline selesai dengan sukses! Log: %LOG_FILE%
) else (
    echo [ERROR] ZSMR012 Pipeline mengalami kegagalan dengan exit code: %EXIT_CODE%. Cek file log: %LOG_FILE%
)

exit /b %EXIT_CODE%
