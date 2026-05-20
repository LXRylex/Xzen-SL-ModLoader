@echo off
setlocal

echo DEBUG: skins enabled

rem folder of this .bat (always ends with backslash)
set "BAT_DIR=%~dp0"

rem target python file: ...\xzen_engine\python\SkinSwapEngine.py
set "PY_FILE=%BAT_DIR%..\python\EmoteSwapEngine.py"

rem pick a Python: venv > py -3 > python
set "VENV_PY=%BAT_DIR%..\..\venv\Scripts\python.exe"
if exist "%VENV_PY%" (
  set "PYEXE=%VENV_PY%"
) else (
  where py >nul 2>nul && (set "PYEXE=py -3") || (set "PYEXE=python")
)

echo Running: %PYEXE% "%PY_FILE%"
pushd "%BAT_DIR%\.."
%PYEXE% "%PY_FILE%"
set "ERR=%ERRORLEVEL%"
popd

echo ExitCode=%ERR%
pause
endlocal
