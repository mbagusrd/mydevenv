@echo off
setlocal enabledelayedexpansion

set "COMPOSE_FILE=D:\Users\Bagus\Documents\hermes-work\prototypes\mydevenv\docker-compose.yml"
set "SERVICE=php74"
set "HOST_DIR=D:\Users\Bagus\Documents\dev\projects-web"
set "WORKDIR=/srv"
set "CURR=%CD%"

if /i "%CURR:~0,41%"=="%HOST_DIR%" (
    set "REL=%CURR:~41%"
    set "REL=!REL:\=/!"
    set "WORKDIR=/srv!REL!"
)

docker compose -f "%COMPOSE_FILE%" exec -w "!WORKDIR!" %SERVICE% php %*
exit /b %errorlevel%
