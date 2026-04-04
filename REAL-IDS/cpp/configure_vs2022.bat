@echo off
REM REAL-IDS: CMake + NMake after vcvars64 (fixes "No CMAKE_CXX_COMPILER" in plain PowerShell).
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"

set "VCVARS=%ProgramFiles%\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
if not exist "%VCVARS%" set "VCVARS=%ProgramFiles%\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat"
if not exist "%VCVARS%" set "VCVARS=%ProgramFiles%\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat"
if not exist "%VCVARS%" (
  echo ERROR: vcvars64.bat not found. Install Visual Studio 2022 with C++ workload.
  exit /b 1
)

call "%VCVARS%" || exit /b 1

if exist build rmdir /s /q build

echo Using NMake Makefiles ^(works when plain cmake cannot find MSVC^)...
cmake -B build -G "NMake Makefiles" -DCMAKE_BUILD_TYPE=Release
if errorlevel 1 exit /b 1

cmake --build build
if errorlevel 1 exit /b 1

echo.
echo OK: %ROOT%build\real_ids_daemon.exe
