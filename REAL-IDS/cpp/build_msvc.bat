@echo off
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"

set "VCVARS=%ProgramFiles%\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
if not exist "%VCVARS%" set "VCVARS=%ProgramFiles%\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat"
if not exist "%VCVARS%" set "VCVARS=%ProgramFiles%\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat"
if not exist "%VCVARS%" (
  echo ERROR: vcvars64.bat not found. Install "Desktop development with C++" in Visual Studio.
  exit /b 1
)

call "%VCVARS%" || exit /b 1

if not exist build mkdir build

cl /nologo /EHsc /std:c++17 /O2 /W3 ^
  /I "%ROOT%include" /I "%ROOT%third_party" ^
  /Fe:"%ROOT%build\real_ids_daemon.exe" ^
  "%ROOT%src\eth_buffer.cpp" "%ROOT%src\can_ids.cpp" "%ROOT%src\central_processor.cpp" "%ROOT%src\engine.cpp" "%ROOT%daemon\main.cpp" ^
  /link /SUBSYSTEM:CONSOLE ws2_32.lib

if errorlevel 1 exit /b 1
echo.
echo OK: %ROOT%build\real_ids_daemon.exe
