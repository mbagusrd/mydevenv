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
if "%1"=="container" goto cmd_container
if "%1"=="containers" goto cmd_container
if "%1"=="start" goto cmd_start
if "%1"=="stop" goto cmd_stop
if "%1"=="sync" goto cmd_sync
if "%1"=="setup" goto cmd_setup
if "%1"=="repair" goto cmd_repair
if "%1"=="uninstall" goto cmd_uninstall
if "%1"=="ps" goto cmd_ps
if "%1"=="exec" goto cmd_exec
if "%1"=="switch" goto cmd_switch
if "%1"=="use" goto cmd_switch
if "%1"=="alias" goto cmd_alias
if "%1"=="enable" goto cmd_enable
if "%1"=="disable" goto cmd_disable
if "%1"=="domain" goto cmd_domain
if "%1"=="projects" goto cmd_domain
if "%1"=="php" goto cmd_php
if "%1"=="composer" goto cmd_composer
if "%1"=="mysql" goto cmd_mysql
if "%1"=="mysqldump" goto cmd_mysqldump

:: Jika tanpa argumen, tampilkan menu interaktif
%PY_CMD% bin\sync.py
goto end

:cmd_up
%PY_CMD% bin\sync.py --up-custom
%PY_CMD% bin\sync.py --auto
goto end

:cmd_container
%PY_CMD% bin\sync.py --container %2
goto end

:cmd_start
%PY_CMD% bin\sync.py --start %2
goto end

:cmd_stop
%PY_CMD% bin\sync.py --stop %2
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

:cmd_switch
%PY_CMD% bin\sync.py --switch %2
goto end

:cmd_alias
%PY_CMD% bin\sync.py --alias
goto end

:cmd_enable
%PY_CMD% bin\sync.py --enable %2
goto end

:cmd_disable
%PY_CMD% bin\sync.py --disable %2
goto end

:cmd_domain
%PY_CMD% bin\sync.py --domain
goto end

:cmd_php
set "PHP_CMD_TARGET=php82"
if exist "config\settings.json" (
    for /f "tokens=2 delims=:," %%v in ('findstr /i "default_php" config\settings.json') do (
        set "VAL_RAW=%%v"
        set "VAL_RAW=!VAL_RAW: =!"
        set "VAL_RAW=!VAL_RAW:"=!"
        if "!VAL_RAW!"=="5.6" set "PHP_CMD_TARGET=php56"
        if "!VAL_RAW!"=="5" set "PHP_CMD_TARGET=php56"
        if "!VAL_RAW!"=="7.4" set "PHP_CMD_TARGET=php74"
        if "!VAL_RAW!"=="7" set "PHP_CMD_TARGET=php74"
        if "!VAL_RAW!"=="8.2" set "PHP_CMD_TARGET=php82"
        if "!VAL_RAW!"=="8" set "PHP_CMD_TARGET=php82"
        if "!VAL_RAW!"=="8.3" set "PHP_CMD_TARGET=php83"
        if "!VAL_RAW!"=="8.4" set "PHP_CMD_TARGET=php84"
    )
)
for /f "tokens=1* delims= " %%a in ("%*") do set "PHP_ARGS=%%b"
docker compose exec %PHP_CMD_TARGET% php %PHP_ARGS%
goto end

:cmd_composer
set "PHP_CMD_TARGET=php82"
if exist "config\settings.json" (
    for /f "tokens=2 delims=:," %%v in ('findstr /i "default_php" config\settings.json') do (
        set "VAL_RAW=%%v"
        set "VAL_RAW=!VAL_RAW: =!"
        set "VAL_RAW=!VAL_RAW:"=!"
        if "!VAL_RAW!"=="5.6" set "PHP_CMD_TARGET=php56"
        if "!VAL_RAW!"=="5" set "PHP_CMD_TARGET=php56"
        if "!VAL_RAW!"=="7.4" set "PHP_CMD_TARGET=php74"
        if "!VAL_RAW!"=="7" set "PHP_CMD_TARGET=php74"
        if "!VAL_RAW!"=="8.2" set "PHP_CMD_TARGET=php82"
        if "!VAL_RAW!"=="8" set "PHP_CMD_TARGET=php82"
        if "!VAL_RAW!"=="8.3" set "PHP_CMD_TARGET=php83"
        if "!VAL_RAW!"=="8.4" set "PHP_CMD_TARGET=php84"
    )
)
for /f "tokens=1* delims= " %%a in ("%*") do set "COMPOSER_ARGS=%%b"
docker compose exec %PHP_CMD_TARGET% composer %COMPOSER_ARGS%
goto end

:cmd_mysql
for /f "tokens=1* delims= " %%a in ("%*") do set "MYSQL_ARGS=%%b"
docker compose exec mariadb mysql %MYSQL_ARGS%
goto end

:cmd_mysqldump
for /f "tokens=1* delims= " %%a in ("%*") do set "MYSQLDUMP_ARGS=%%b"
docker compose exec mariadb mysqldump %MYSQLDUMP_ARGS%
goto end

:end
