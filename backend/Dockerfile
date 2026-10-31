FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# libgomp1: LightGBM runtime. tesseract-ocr: optional screenshot OCR (instrument/timeframe/price-axis reading).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN useradd --create-home app && mkdir -p /app/data/models /app/data/uploads && chown -R app:app /app/data
USER app

# Hosts such as Railway inject $PORT; locally and in docker compose it stays 8000.
ENV PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD python -c "import os, urllib.request as u; u.urlopen('http://localhost:%s/api/v1/health' % os.environ.get('PORT', '8000'), timeout=4)"
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
