FROM python:3.11-slim

# Prevent Python from generating .pyc files and allow real-time logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies needed to compile some Python libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and data
COPY data ./data
COPY docs/public/data ./docs/public/data
COPY docs/public/docs ./docs/public/docs
COPY scripts/__init__.py ./scripts/__init__.py
COPY scripts/ingest_sql.py ./scripts/ingest_sql.py
COPY scripts/ingest_rag.py ./scripts/ingest_rag.py
COPY src ./src

EXPOSE 8000

CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
