@echo off
setlocal ENABLEDELAYEDEXPANSION

echo [launch_game.bat] loading config...

rem this .bat: ...\source\xzen_engine\bats\
set "BAT_DIR=%~dp0"
for %%I in ("%BAT_DIR%..\..\..") do set "APP_ROOT=%%~fI"

set "PATHS_JSON="
for %%I in (
  "%APP_ROOT%\source\profile\user_data\paths.json"
  "%APP_ROOT%\profile\user_data\paths.json"
  "%BAT_DIR%..\..\profile\user_data\paths.json"
) do (
  if not defined PATHS_JSON if exist "%%~fI" set "PATHS_JSON=%%~fI"
)

if not defined PATHS_JSON (
  echo [ERR] paths.json not found. Tried:
  echo        "%APP_ROOT%\source\profile\user_data\paths.json"
  echo        "%APP_ROOT%\profile\user_data\paths.json"
  echo        "%BAT_DIR%..\..\profile\user_data\paths.json"
  set "EXIT_CODE=1"
  goto :end_pause
)

rem --- read game_exe
for /f "usebackq delims=" %%I in (`
  powershell -NoProfile -Command ^
    "$cfg = Get-Content -Raw -ErrorAction Stop '%PATHS_JSON%' | ConvertFrom-Json;" ^
    "if(-not $cfg.game_exe){exit 10};" ^
    "$cfg.game_exe"
`) do set "GAME_EXE=%%I"

if not defined GAME_EXE (
  echo [ERR] 'game_exe' missing in paths.json
  set "EXIT_CODE=2"
  goto :end_pause
)

rem --- read assetbundles_dir
for /f "usebackq delims=" %%I in (`
  powershell -NoProfile -Command ^
    "$cfg = Get-Content -Raw -ErrorAction Stop '%PATHS_JSON%' | ConvertFrom-Json;" ^
    "if(-not $cfg.assetbundles_dir){exit 11};" ^
    "$cfg.assetbundles_dir"
`) do set "ASSETBUNDLES=%%I"

if not defined ASSETBUNDLES (
  echo [ERR] 'assetbundles_dir' missing in paths.json
  set "EXIT_CODE=3"
  goto :end_pause
)

rem --- derive SMASH LEGENDS root from AssetBundles (...\Smash_Legends_Data\StreamingAssets\AssetBundles -> go up 3)
for %%I in ("%ASSETBUNDLES%\..\..\..") do set "SMASH_ROOT=%%~fI"
set "APPID_FILE=%SMASH_ROOT%\steam_appid.txt"

set "APPID="
if exist "%APPID_FILE%" (
  for /f "usebackq delims=" %%I in (`
    powershell -NoProfile -Command ^
      "(Get-Content -Raw '%APPID_FILE%' 2>$null) -replace '\D',''"
  `) do set "APPID=%%I"
)

for %%F in ("%GAME_EXE%") do set "GAME_DIR=%%~dpF"
for %%F in ("%GAME_EXE%") do set "GAME_EXE_NAME=%%~nxF"

echo [info] game exe     : "%GAME_EXE%"
echo [info] game dir     : "%GAME_DIR%"
echo [info] bundles dir  : "%ASSETBUNDLES%"
echo [info] smash root   : "%SMASH_ROOT%"
echo [info] paths json   : "%PATHS_JSON%"
if defined APPID (
  echo [info] steam appid : %APPID%
) else (
  echo [warn] steam_appid.txt not found or unreadable
)

rem --- if running, kill and wait
echo [check] is "%GAME_EXE_NAME%" running?
tasklist /FI "IMAGENAME eq %GAME_EXE_NAME%" /NH | find /I "%GAME_EXE_NAME%" >nul
if %ERRORLEVEL%==0 (
  echo [action] game is running -> restarting...
  taskkill /F /IM "%GAME_EXE_NAME%" >nul 2>&1
  rem wait until it’s gone
  set /a _tries=0
  :wait_gone
  tasklist /FI "IMAGENAME eq %GAME_EXE_NAME%" /NH | find /I "%GAME_EXE_NAME%" >nul
  if %ERRORLEVEL%==0 (
    set /a _tries+=1
    if !_tries! GEQ 60 (
      echo [ERR] process would not exit after 60s.
      set "EXIT_CODE=4"
      goto :end_pause
    )
    timeout /t 1 /nobreak >nul
    goto :wait_gone
  )
  echo [ok] process closed.
) else (
  echo [ok] game not running.
)

rem --- launch
echo [launch] starting game...
if exist "%GAME_EXE%" (
  pushd "%GAME_DIR%"
  start "" "%GAME_EXE%"
  set "ERR=!ERRORLEVEL!"
  if not defined ERR set "ERR=0"
  popd
  if not "!ERR!"=="0" (
    echo [warn] direct launch failed with !ERR!.
  ) else (
    echo [done] launched via exe.
    set "EXIT_CODE=0"
    goto :end_pause
  )
)

if defined APPID (
  echo [fallback] launching via Steam protocol (appid %APPID%)...
  start "" "steam://rungameid/%APPID%"
  set "EXIT_CODE=%ERRORLEVEL%"
  goto :end_pause
) else (
  echo [ERR] cannot launch: exe missing and no appid available.
  set "EXIT_CODE=5"
  goto :end_pause
)

:end_pause
echo(
pause
exit /b %EXIT_CODE%
