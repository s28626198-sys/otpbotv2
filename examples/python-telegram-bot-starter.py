"""
Python Telegram Bot Starter for SMSBower API

Requirements:
  pip install python-telegram-bot==21.* requests python-dotenv

Run:
  python python-telegram-bot-starter.py
"""

import os
import time
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
API_KEY = os.getenv("SMSBOWER_API_KEY", "")
BASE_URL = os.getenv("SMSBOWER_BASE_URL", "https://smsbower.page/stubs/handler_api.php")


def api_call(params: dict) -> str:
    payload = {"api_key": API_KEY, **params}
    r = requests.get(BASE_URL, params=payload, timeout=15)
    r.raise_for_status()
    return r.text.strip()


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "SMSBower Bot Ready.\n"
        "Commands:\n"
        "/balance\n"
        "/buy <service> <country> [maxPrice]"
    )


async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        result = api_call({"action": "getBalance"})
        await update.message.reply_text(f"💰 {result}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def buy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /buy tg 1 0.2
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /buy <service> <country> [maxPrice]")
        return

    service = args[0]
    country = args[1]
    max_price = args[2] if len(args) > 2 else None

    try:
        params = {
            "action": "getNumber",
            "service": service,
            "country": country,
        }
        if max_price:
            params["maxPrice"] = max_price

        result = api_call(params)
        if not result.startswith("ACCESS_NUMBER:"):
            await update.message.reply_text(f"❌ Failed: {result}")
            return

        _, activation_id, phone = result.split(":", 2)
        await update.message.reply_text(f"📱 Number: {phone}\nActivation: {activation_id}")

        # Optional: mark number ready
        try:
            api_call({"action": "setStatus", "id": activation_id, "status": 1})
        except Exception:
            pass

        # Poll status with simple backoff
        intervals = [3, 5, 8, 10, 12, 15]
        total_wait = 0
        timeout_sec = 120

        while total_wait < timeout_sec:
            status = api_call({"action": "getStatus", "id": activation_id})

            if status.startswith("STATUS_OK:"):
                code = status.replace("STATUS_OK:", "", 1)
                await update.message.reply_text(f"✅ OTP: {code}")
                api_call({"action": "setStatus", "id": activation_id, "status": 6})
                return

            if status == "STATUS_CANCEL":
                await update.message.reply_text("⚠️ Activation canceled by provider")
                return

            wait_for = intervals[min(total_wait // 20, len(intervals) - 1)]
            time.sleep(wait_for)
            total_wait += wait_for

        await update.message.reply_text("⌛ Timeout waiting for SMS")

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


if __name__ == "__main__":
    if not BOT_TOKEN or not API_KEY:
        raise SystemExit("Please set BOT_TOKEN and SMSBOWER_API_KEY in .env")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("buy", buy_cmd))

    print("Bot is running...")
    app.run_polling()
