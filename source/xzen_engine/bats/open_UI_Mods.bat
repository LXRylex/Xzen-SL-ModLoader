@echo off
setlocal

echo DEBUG: UI Mods Panel said womp womp

REM folder of this .bat (ends with \)
set "BAT_DIR=%~dp0"

REM go to: source\xzen_engine\
set "ENGINE_DIR=%BAT_DIR%..\"

REM target python file
set "PY_FILE=%ENGINE_DIR%python\UI_Mods_Panel.py"

REM run it (passes any args you give to the .bat)
pushd "%ENGINE_DIR%" >nul
py -3 "%PY_FILE%" %*
set "ERR=%ERRORLEVEL%"
popd >nul

exit /b %ERR%
