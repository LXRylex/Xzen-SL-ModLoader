@echo off
setlocal
echo DEBUG: recover originals
set "BAT_DIR=%~dp0"
set "PY_FILE=%BAT_DIR%..\python\EmoteSwapRecover.py"
where py >nul 2>nul && (set "PYEXE=py -3") || (set "PYEXE=python")
pushd "%BAT_DIR%\.."
%PYEXE% "%PY_FILE%"
popd
pause
