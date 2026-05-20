@echo off
setlocal

echo character icons only supports one mod at a time [ui file]

REM folder of this .bat
set "BAT_DIR=%~dp0"

REM go to: source\xzen_engine\
set "ENGINE_DIR=%BAT_DIR%..\.."

REM target python file
set "PY_FILE=%ENGINE_DIR%\python\import_handlers\import_ui_files.py"

REM run it (passes any args you give to the .bat)
pushd "%ENGINE_DIR%" >nul
py -3 "%PY_FILE%" %*
set "ERR=%ERRORLEVEL%"
popd >nul

exit /b %ERR%
