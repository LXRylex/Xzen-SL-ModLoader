@echo off
setlocal

cd /d "%~dp0..\.."
REM now you're at: source\xzen_engine\bats

cd /d "%~dp0..\..\python\import_handlers"
python "import_stage_files.py"

endlocal
