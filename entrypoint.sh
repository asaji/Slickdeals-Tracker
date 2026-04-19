#!/bin/sh
set -e

# Apply PUID/PGID if provided (UnRAID pattern)
PUID=${PUID:-99}
PGID=${PGID:-100}

# Copy default config on first run
CONFIG_PATH=${CONFIG_PATH:-/config/config.yaml}
if [ ! -f "$CONFIG_PATH" ]; then
    echo "No config found at $CONFIG_PATH — copying default…"
    mkdir -p "$(dirname "$CONFIG_PATH")"
    cp /app/config.yaml "$CONFIG_PATH"
fi

exec "$@"
