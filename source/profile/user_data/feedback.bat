@echo off
setlocal

rem folder of this bat: ...\source\profile\user_data\
set "HERE=%~dp0"

rem resolve ...\source\
for %%I in ("%HERE%..\..") do set "SRC=%%~fI"

rem target script: ...\source\xzen_engine\python\feedback.py
set "SCRIPT=%SRC%\xzen_engine\python\feedback.py"

if not exist "%SCRIPT%" (
  echo [feedback] Missing script: "%SCRIPT%" 1>&2
  exit /b 1
)

rem 1) prefer venv at project root: ...\venv\Scripts\python.exe
if exist "%SRC%\..\venv\Scripts\python.exe" (
  "%SRC%\..\venv\Scripts\python.exe" "%SCRIPT%"
  exit /b %errorlevel%
)

rem 2) try python on PATH
where python >nul 2>nul
if %errorlevel%==0 (
  python "%SCRIPT%"
  exit /b %errorlevel%
)

rem 3) try Windows launcher
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%SCRIPT%"
  exit /b %errorlevel%
)

echo [feedback] No Python found on PATH. Install Python or add it to PATH. 1>&2
exit /b 1
