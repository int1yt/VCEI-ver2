@echo off
REM Start real_ids_daemon with ML bridge URL (uvicorn must already be on port 5055).
setlocal
set "REAL_IDS_ML_BRIDGE=http://127.0.0.1:5055"
cd /d "%~dp0cpp\build"
if not exist "real_ids_daemon.exe" (
  echo ERROR: real_ids_daemon.exe not found. Build with configure_vs2022.bat first.
  pause
  exit /b 1
)
echo REAL_IDS_ML_BRIDGE=%REAL_IDS_ML_BRIDGE%
echo Starting daemon...
real_ids_daemon.exe
endlocal
