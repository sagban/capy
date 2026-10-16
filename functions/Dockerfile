FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run serves HTTP + MCP; Firebase callables remain a separate deploy target.
CMD exec uvicorn service_app:app --host 0.0.0.0 --port ${PORT}
