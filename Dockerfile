FROM python:3.13-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y libpq-dev gcc

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt --user

FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y libpq-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app


COPY --chown=appuser:appuser . .

USER appuser

CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]