@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo =========================================
echo Запуск VRPTW (Нативный Python + venv)
echo =========================================

:: 1. Проверка наличия Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ОШИБКА] Python не установлен или не добавлен в PATH!
    echo Скачайте Python 3.11+ с официального сайта python.org
    pause
    exit /b 1
)

:: 1.1 Проверка и создание папок
if not exist "data\cache" (
    mkdir "data\cache"
    echo [ИНФО] Создана директория data\cache
)

:: 2. Создание виртуального окружения (если его нет)
if not exist "venv\Scripts\activate" (
    echo [ИНФО] Создание виртуального окружения...
    python -m venv venv
)

:: 3. Активация окружения
echo [ИНФО] Активация окружения и проверка зависимостей...
call venv\Scripts\activate

:: 4. Установка библиотек только при отсутствии зависимостей
set NEED_INSTALL=0
for %%p in (fastapi uvicorn pydantic gpxpy httpx) do (
    python -m pip show %%p >nul 2>&1
    if errorlevel 1 set NEED_INSTALL=1
)

if "%NEED_INSTALL%"=="1" (
    echo [ИНФО] Установка зависимостей из requirements.txt...
    python -m pip install --disable-pip-version-check --prefer-binary -r requirements.txt
    if errorlevel 1 (
        echo [ОШИБКА] Не удалось установить зависимости: возможно, нет доступа к интернету или DNS.
        echo Проверьте сеть и DNS, затем повторите запуск.
        echo Если интернет недоступен, используйте Docker-режим через setup_and_run.bat.
        pause
        exit /b 1
    )
) else (
    echo [ИНФО] Зависимости уже установлены, пропускаем pip install.
)

:: 5. Запуск FastAPI сервера
echo.
echo =========================================
echo [УСПЕХ] Запуск микросервиса...
echo Документация API: http://localhost:8000/docs
echo Для остановки нажмите Ctrl+C
echo =========================================
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
if errorlevel 1 (
    echo.
    echo [ОШИБКА] Uvicorn завершился с ошибкой.
    echo Проверьте сообщения выше и повторите запуск.
)

pause