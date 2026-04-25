#!/bin/bash
export CONFIG_PATH=/tmp/slickdeals/config.yaml
export DB_PATH=/tmp/slickdeals/deals.db
export PORT=7001

mkdir -p /tmp/slickdeals
if [ ! -f "$CONFIG_PATH" ]; then
    cp "$(dirname "$0")/config.yaml" "$CONFIG_PATH"
fi

exec .venv/bin/python -m slickdeals_tracker.web
