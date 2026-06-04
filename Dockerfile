FROM python:3.11-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /code

# Отключаем буферизацию (чтобы логи сразу шли в консоль Docker) и кэш Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем библиотеки
RUN pip install --no-cache-dir -r requirements.txt

# Исходный код будет пробрасываться через volume (для автообновления), 
# но для продакшена мы всё равно копируем его.
COPY ./app /code/app

# Запуск FastAPI сервера с горячей перезагрузкой (--reload)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]