@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo =========================================
echo Инициализация проекта VRPTW (Python + 1C)
echo =========================================

set "COMPOSE_CMD="

:: 1. Проверка установки Docker
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ПРЕДУПРЕЖДЕНИЕ] Docker не найден в PATH.
    goto :FALLBACK_NATIVE
)

:: 2. Определяем доступную команду compose
docker compose version >nul 2>&1
if %errorlevel% equ 0 (
    set "COMPOSE_CMD=docker compose"
) else (
    docker-compose --version >nul 2>&1
    if %errorlevel% equ 0 (
        set "COMPOSE_CMD=docker-compose"
    )
)

if "%COMPOSE_CMD%"=="" (
    echo [ПРЕДУПРЕЖДЕНИЕ] Команда Docker Compose не найдена.
    goto :FALLBACK_NATIVE
)

:: 3. Проверка запущен ли демон Docker
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ПРЕДУПРЕЖДЕНИЕ] Docker daemon недоступен. Возможно, Docker Desktop не запущен.
    goto :FALLBACK_NATIVE
)

:: 4. Проверка и создание папок
echo [ИНФО] Проверка структуры директорий...
if not exist "data\cache" (
    mkdir "data\cache"
    echo [ИНФО] Создана директория data\cache
)

:: 5. Сборка и запуск контейнеров
echo [ИНФО] Сборка и запуск Docker-контейнеров через: %COMPOSE_CMD%
call %COMPOSE_CMD% up -d --build
if %errorlevel% neq 0 (
    echo [ОШИБКА] Не удалось запустить контейнеры через Docker.
    goto :FALLBACK_NATIVE
)

echo.
echo =========================================
echo [УСПЕХ] Контейнер успешно запущен!
echo.
echo Проверка статуса: http://localhost:8000
echo Документация API: http://localhost:8000/docs
echo.
pause
exit /b 0

:FALLBACK_NATIVE
echo.
echo =========================================
echo [ИНФО] Переключение на нативный запуск (Python + venv).
echo Это удобно, если Docker Desktop не установлен или не запущен.
echo =========================================
if exist "run_native.bat" (
    call run_native.bat
    exit /b %errorlevel%
)

echo [ОШИБКА] Не найден run_native.bat для fallback-запуска.
pause
exit /b 1
