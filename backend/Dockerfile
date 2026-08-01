FROM python:3.14-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt 

COPY app ./app
COPY config.toml .

EXPOSE 8080
# The app does not read $PORT; the port is fixed here and matches fly's internal_port.
# app.main:app is API-only — serve:app (single-origin, bundled frontend) is the local path.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]