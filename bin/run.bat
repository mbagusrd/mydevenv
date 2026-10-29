@echo off
setlocal
cd /d "%~dp0\.."

:: 1. Deteksi executable Python yang valid (hindari WindowsApps alias)
set "PY_CMD="

:: Cek UV bawaan hermes
if exist "%LOCALAPPDATA%\hermes\bin\uv.exe" (
    set PY_CMD="%LOCALAPPDATA%\hermes\bin\uv.exe" run python
    goto found_py
)

:: Cek py launcher
where py >nul 2>nul
if %errorlevel%==0 (
    set PY_CMD=py
    goto found_py
)

:: Cek instalasi standar Python Windows
for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
    if exist "%%d\python.exe" (
        set PY_CMD="%%d\python.exe"
        goto found_py
    )
)
for /d %%d in ("C:\Python*") do (
    if exist "%%d\python.exe" (
        set PY_CMD="%%d\python.exe"
        goto found_py
    )
)

:: Cek python di PATH selain WindowsApps
for /f "tokens=*" %%i in ('where python 2^>nul') do (
    echo %%i | findstr /i "WindowsApps" >nul
    if errorlevel 1 (
        set PY_CMD="%%i"
        goto found_py
    )
)

:found_py
if not defined PY_CMD (
    echo [ERROR] Python tidak ditemukan di sistem.
    echo Solusi: Matikan alias Store di Windows:
    echo   Settings -^> Apps -^> Advanced app settings -^> App execution aliases
    echo   Matikan toggle untuk "python.exe" dan "python3.exe"
    pause
    exit /b 1
)

if "%1"=="up" goto cmd_up
if "%1"=="down" goto cmd_down
if "%1"=="restart" goto cmd_restart
if "%1"=="sync" goto cmd_sync
if "%1"=="setup" goto cmd_setup
if "%1"=="repair" goto cmd_repair
if "%1"=="uninstall" goto cmd_uninstall
if "%1"=="ps" goto cmd_ps
if "%1"=="exec" goto cmd_exec
if "%1"=="alias" goto cmd_alias
if "%1"=="php" goto cmd_php
if "%1"=="composer" goto cmd_composer
if "%1"=="mysqldump" goto cmd_mysqldump

:: Jika tanpa argumen, tampilkan menu interaktif
%PY_CMD% bin\sync.py
goto end

:cmd_up
docker compose up -d
%PY_CMD% bin\sync.py --auto
goto end

:cmd_down
docker compose down
goto end

:cmd_restart
docker compose restart
goto end

:cmd_sync
%PY_CMD% bin\sync.py --sync
goto end

:cmd_setup
%PY_CMD% bin\sync.py --setup
goto end

:cmd_repair
%PY_CMD% bin\sync.py --repair
goto end

:cmd_uninstall
%PY_CMD% bin\sync.py --uninstall
goto end

:cmd_ps
docker compose ps
goto end

:cmd_exec
for /f "tokens=1* delims= " %%a in ("%*") do set "EXEC_ARGS=%%b"
docker compose exec %EXEC_ARGS%
goto end

:cmd_alias
%PY_CMD% bin\sync.py --alias
goto end

:cmd_php
for /f "tokens=1* delims= " %%a in ("%*") do set "PHP_ARGS=%%b"
docker compose exec php82 php %PHP_ARGS%
goto end

:cmd_composer
for /f "tokens=1* delims= " %%a in ("%*") do set "COMPOSER_ARGS=%%b"
docker compose exec php82 composer %COMPOSER_ARGS%
goto end

:cmd_mysqldump
for /f "tokens=1* delims= " %%a in ("%*") do set "MYSQLDUMP_ARGS=%%b"
docker compose exec mariadb mysqldump %MYSQLDUMP_ARGS%
goto end

:end
