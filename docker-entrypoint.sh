#!/usr/bin/env sh
set -eu

: "${PORT:=10000}"
: "${WEBHOOK_LISTEN:=0.0.0.0}"
: "${WEBHOOK_PATH:=/telegram-webhook}"

if [ -z "${WEBHOOK_URL:-}" ] && [ -n "${RENDER_EXTERNAL_URL:-}" ]; then
  export WEBHOOK_URL="${RENDER_EXTERNAL_URL}"
fi

# Stable default for Render web services: polling + health server on $PORT.
if [ -n "${RENDER:-}" ] && [ -z "${BOT_TRANSPORT:-}" ]; then
  export BOT_TRANSPORT="polling"
fi
if [ -z "${ENABLE_HEALTH_SERVER:-}" ]; then
  export ENABLE_HEALTH_SERVER="1"
fi

exec python smsbower_premium_bot.py
