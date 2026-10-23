FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run serves HTTP + MCP. Firebase callables stay on functions/main.py.
CMD exec uvicorn cloudrun.app:app --host 0.0.0.0 --port ${PORT}
