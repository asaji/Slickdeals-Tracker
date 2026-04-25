FROM python:3.11-slim

LABEL maintainer="Slickdeals Tracker" \
      description="Monitor Slickdeals for hot deals with web dashboard and Pushover alerts"

WORKDIR /app

# supervisor manages the watcher + web UI processes
RUN apt-get update \
    && apt-get install -y --no-install-recommends supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Config and data live in a single mounted volume
RUN mkdir -p /config

VOLUME ["/config"]

EXPOSE 7001

ARG GIT_HASH=dev
ENV CONFIG_PATH=/config/config.yaml \
    DB_PATH=/config/deals.db \
    TZ=America/New_York \
    APP_VERSION=${GIT_HASH}

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7001/health')" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["supervisord", "-c", "/app/supervisord.conf", "-n"]
