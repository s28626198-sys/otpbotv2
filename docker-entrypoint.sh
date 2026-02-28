#!/usr/bin/env sh
set -eu

: "${PORT:=10000}"
: "${WEBHOOK_LISTEN:=0.0.0.0}"
: "${WEBHOOK_PATH:=/telegram-webhook}"

if [ -z "${WEBHOOK_URL:-}" ] && [ -n "${RENDER_EXTERNAL_URL:-}" ]; then
  export WEBHOOK_URL="${RENDER_EXTERNAL_URL}"
fi

if [ -z "${WEBHOOK_URL:-}" ]; then
  echo "ERROR: WEBHOOK_URL or RENDER_EXTERNAL_URL is required for web service mode."
  exit 1
fi

exec python smsbower_premium_bot.py
