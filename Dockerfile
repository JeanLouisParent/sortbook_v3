FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    EPUB_SOURCE_DIR=/data \
    DRY_RUN=true \
    N8N_WEBHOOK_URL=http://n8n:5678/webhook/epub-metadata

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY src ./src

ENTRYPOINT ["python", "src/epub_metadata.py"]
