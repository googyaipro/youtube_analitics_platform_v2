FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MPLCONFIGDIR=/tmp/matplotlib \
    PORT=8080

WORKDIR /app

# Install security and fonts dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-privileged user and writable /tmp directories
RUN useradd -m -u 10001 sandboxuser && \
    mkdir -p /tmp/matplotlib && \
    chown -R sandboxuser:sandboxuser /app /tmp/matplotlib

COPY . .
RUN chown -R sandboxuser:sandboxuser /app

USER sandboxuser

EXPOSE 8080

# Cloud Run execution with 8080 default
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
