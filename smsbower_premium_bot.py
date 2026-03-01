import asyncio
import atexit
import base64
import json
import logging
import os
import re
import sqlite3
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlparse

import httpx
from supabase import create_client
from telegram import (
    BotCommand,
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, NetworkError, TimedOut
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    TypeHandler,
    filters,
)
from telegram.helpers import escape_markdown

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

try:
    import pycountry
except Exception:
    pycountry = None

try:
    from telegram import CopyTextButton

    HAS_COPY = True
except Exception:
    CopyTextButton = None
    HAS_COPY = False


BOT_TOKEN = os.getenv("BOT_TOKEN", "")
API_KEY = os.getenv("TEMPLINE_API_KEY", os.getenv("SMSBOWER_API_KEY", ""))
BASE_URL = os.getenv("TEMPLINE_BASE_URL", os.getenv("SMSBOWER_BASE_URL", "https://smsbower.app/web/stubs/handler_api.php"))
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "5742928021"))
POLL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "4"))
SEARCH_STATE = 1
DEPOSIT_AMOUNT_STATE = 2
DEPOSIT_PROOF_STATE = 3
BROADCAST_STATE = 4
PAYMENT_EDIT_STATE = 5
PROFIT_EDIT_STATE = 6
PAGE_SIZE = 10
LOCK_FILE_PATH = os.getenv("BOT_LOCK_FILE", ".templine_bot.lock")
LOCK_HANDLE = None
CANCEL_LOCK_SECONDS = int(os.getenv("CANCEL_LOCK_SECONDS", "180"))
MAX_MONITOR_SECONDS = int(os.getenv("MAX_MONITOR_SECONDS", "1500"))
MIN_DEPOSIT_USD = Decimal(os.getenv("MIN_DEPOSIT_USD", "0.5"))

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD", "").strip()
SUPABASE_DB_USER = os.getenv("SUPABASE_DB_USER", "postgres").strip()
SUPABASE_DB_NAME = os.getenv("SUPABASE_DB_NAME", "postgres").strip()
SUPABASE_DB_PORT = int(os.getenv("SUPABASE_DB_PORT", "5432"))
SUPABASE_DB_HOST = os.getenv("SUPABASE_DB_HOST", "").strip()
SUPABASE_DB_DSN = os.getenv("SUPABASE_DB_DSN", "").strip()
SUPABASE_DB_SSLMODE = os.getenv("SUPABASE_DB_SSLMODE", "require").strip() or "require"
SUPABASE_DB_HOSTADDR = os.getenv("SUPABASE_DB_HOSTADDR", "").strip()
SUPABASE_FORCE_IPV4 = os.getenv("SUPABASE_FORCE_IPV4", "1").strip().lower() in {"1", "true", "yes", "on"}
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
SUPABASE_KEY = (
    SUPABASE_SERVICE_ROLE_KEY
    or os.getenv("SUPABASE_KEY", "").strip()
    or os.getenv("SUPABASE_SECRET_KEY", "").strip()
)

ROLE_ADMIN = "admin"
ROLE_USER = "user"
ROLE_SUPER = "super_user"
ROLE_PENDING = "pending"
ROLE_BLOCKED = "blocked"
APPROVED_ROLES = {ROLE_ADMIN, ROLE_USER, ROLE_SUPER}

LANGS = ["en", "bn", "hi", "ar", "ru"]
LANG_LABEL = {
    "en": "🇺🇸 English",
    "bn": "🇧🇩 বাংলা",
    "hi": "🇮🇳 हिन्दी",
    "ar": "🇸🇦 العربية",
    "ru": "🇷🇺 Русский",
}

TR = {
    "en": {
        "m_select": "📋 Select Service",
        "m_search": "🔍 Search Service",
        "m_balance": "💰 Check Balance",
        "welcome": "🔥 Templine Premium OTP Bot\n📱 Buy numbers fast\n💰 Check balance instantly\n✅ Use the menu below",
        "lang_pick": "🌐 Choose your language:",
        "lang_saved": "✅ Language updated.",
        "load_services": "📋 Loading services...",
        "services": "📋 Select Service",
        "services_empty": "⚠️ No services found right now.",
        "search_prompt": "🔍 Reply with service name (facebook / telegram / whatsapp)",
        "search_empty": "❌ No matching service found.",
        "prices": "🌍 Choose country/provider for {service}",
        "prices_empty": "⚠️ No prices available for this service.",
        "load_prices": "🌍 Loading prices...",
        "active_exists": "⚠️ You already have an active activation. Cancel it first.",
        "number": "✅ Number Ready\n📱 Number: {phone}\n🆔 Activation: {aid}\n🌍 Country: {country}\n🏷️ Provider: {provider}\n🔥 Waiting for OTP...",
        "otp": "🔥 OTP Received\n📨 OTP: {otp}",
        "copy_num": "📋 Copy Number",
        "copy_otp": "📋 Copy OTP",
        "cancel": "🛑 Cancel Activation",
        "cancelled": "✅ Activation cancelled.",
        "no_active": "⚠️ No active activation found.",
        "bal_loading": "💰 Loading balance...",
        "bal": "💰 Templine Balance\n✅ ${balance} USD",
        "refresh_bal": "🔄 Refresh Balance",
        "prev": "⬅️ Previous",
        "next": "Next ➡️",
        "unknown": "⚠️ Use the menu buttons below.",
        "expired": "⚠️ This button expired. Please select again.",
        "wait": "⏳ Waiting for SMS...",
        "home": "🏠 Main Menu",
        "fallback_country": "Unknown Country",
        "fallback_provider": "Any Provider",
        "generic_fail": "❌ Request failed. Try again.",
        "bad_key": "🚫 Invalid API key.",
        "bad_action": "🚫 Invalid API action.",
        "bad_service": "🚫 Invalid service.",
        "bad_country": "🚫 Invalid country.",
        "bad_status": "🚫 Invalid status.",
        "no_balance": "💸 Insufficient balance.",
        "no_activation_err": "⚠️ Activation not found.",
        "early_cancel_denied": "⏱️ Early cancel denied.",
        "admin_only": "🔒 Admin only bot. Access denied.",
    },
    "bn": {
        "m_select": "📋 সার্ভিস নির্বাচন",
        "m_search": "🔍 সার্ভিস খুঁজুন",
        "m_balance": "💰 ব্যালেন্স দেখুন",
        "welcome": "🔥 Templine প্রিমিয়াম OTP বট\n📱 দ্রুত নাম্বার কিনুন\n💰 ব্যালেন্স দেখুন\n✅ নিচের মেনু ব্যবহার করুন",
        "lang_pick": "🌐 ভাষা নির্বাচন করুন:",
        "lang_saved": "✅ ভাষা আপডেট হয়েছে।",
        "search_prompt": "🔍 সার্ভিস নাম লিখুন (facebook / telegram / whatsapp)",
        "search_empty": "❌ কোনো সার্ভিস পাওয়া যায়নি।",
        "services_empty": "⚠️ কোনো সার্ভিস পাওয়া যায়নি।",
        "unknown": "⚠️ নিচের মেনু বাটন ব্যবহার করুন।",
        "admin_only": "🔒 এই বট শুধু এডমিনের জন্য। আপনার এক্সেস নেই।",
    },
    "hi": {
        "m_select": "📋 सर्विस चुनें",
        "m_search": "🔍 सर्विस खोजें",
        "m_balance": "💰 बैलेंस देखें",
        "welcome": "🔥 Templine प्रीमियम OTP बॉट\n📱 तेज नंबर खरीद\n💰 तुरंत बैलेंस\n✅ नीचे मेनू उपयोग करें",
        "lang_pick": "🌐 भाषा चुनें:",
        "lang_saved": "✅ भाषा अपडेट हुई।",
        "search_prompt": "🔍 सर्विस नाम भेजें (facebook / telegram / whatsapp)",
        "search_empty": "❌ कोई सर्विस नहीं मिली।",
        "services_empty": "⚠️ अभी कोई सर्विस उपलब्ध नहीं है।",
        "unknown": "⚠️ नीचे मेनू बटन उपयोग करें।",
        "admin_only": "🔒 यह बॉट केवल एडमिन के लिए है।",
    },
    "ar": {
        "m_select": "📋 اختيار الخدمة",
        "m_search": "🔍 بحث خدمة",
        "m_balance": "💰 فحص الرصيد",
        "welcome": "🔥 بوت Templine المميز OTP\n📱 شراء سريع للأرقام\n💰 فحص فوري للرصيد\n✅ استخدم القائمة بالأسفل",
        "lang_pick": "🌐 اختر اللغة:",
        "lang_saved": "✅ تم تحديث اللغة.",
        "search_prompt": "🔍 اكتب اسم الخدمة (facebook / telegram / whatsapp)",
        "search_empty": "❌ لا توجد نتائج.",
        "services_empty": "⚠️ لا توجد خدمات متاحة الآن.",
        "unknown": "⚠️ استخدم أزرار القائمة بالأسفل.",
        "admin_only": "🔒 هذا البوت متاح للأدمن فقط.",
    },
    "ru": {
        "m_select": "📋 Выбрать сервис",
        "m_search": "🔍 Поиск сервиса",
        "m_balance": "💰 Баланс",
        "welcome": "🔥 Премиум OTP бот Templine\n📱 Быстрая покупка номеров\n💰 Мгновенный баланс\n✅ Используйте меню ниже",
        "lang_pick": "🌐 Выберите язык:",
        "lang_saved": "✅ Язык обновлен.",
        "search_prompt": "🔍 Введите сервис (facebook / telegram / whatsapp)",
        "search_empty": "❌ Ничего не найдено.",
        "services_empty": "⚠️ Сейчас нет доступных сервисов.",
        "unknown": "⚠️ Используйте кнопки меню ниже.",
        "admin_only": "🔒 Этот бот доступен только администратору.",
    },
}

TR["en"].update(
    {
        "m_deposit": "🏦 Deposit",
        "m_wallet": "💼 Wallet Balance",
        "m_admin": "🛠 Admin Panel",
        "pending_approval": "⏳ Your account is pending admin approval.",
        "approved_user": "✅ You are approved as User. Enjoy Templine.",
        "approved_super": "✅ You are approved as Super User. Enjoy Templine.",
        "rejected_user": "🚫 Your access has been rejected by admin.",
        "role_updated": "✅ User role updated.",
        "admin_panel": "🛠 Admin Panel",
        "admin_pending": "👥 Pending Users",
        "admin_broadcast": "📣 Broadcast",
        "admin_payments": "💳 Payment Settings",
        "admin_profit": "📈 Profit %",
        "admin_stats": "📊 User Stats",
        "pending_none": "✅ No pending users.",
        "approve_user": "✅ Approve User",
        "approve_super": "⚡ Approve Super",
        "approve_cancel": "🚫 Cancel",
        "new_user_alert": "🆕 New user request\n👤 {name}\n🆔 {user_id}\n🌐 {user_lang}",
        "broadcast_prompt": "📣 Send the broadcast message now.",
        "broadcast_done": "✅ Broadcast sent to {ok}/{total}.",
        "payment_show": "💳 Payment Settings\n\n{lines}",
        "payment_prompt": "✍️ Send payment settings lines:\n`telegram_username=@name`\n`binance=...`\n`bkash=...`\n`nagad=...`\nYou can add any new key too.",
        "payment_saved": "✅ Payment settings updated.",
        "profit_current": "📈 Current profit: {pct}%",
        "profit_prompt": "✍️ Send new profit percentage (0-500).",
        "profit_saved": "✅ Profit updated to {pct}%.",
        "wallet": "💼 Wallet Balance\n✅ ${balance} USD",
        "insufficient_wallet": "💸 Insufficient wallet balance.",
        "deposit_prompt_amount": "🏦 Enter deposit amount in USD (minimum ${min}).",
        "deposit_min": "⚠️ Minimum deposit is ${min}.",
        "deposit_created": "✅ Deposit request created for ${amount}.",
        "deposit_payment_info": "💳 Send payment to:\n{lines}",
        "deposit_send_proof": "📤 Send TXID and screenshot (photo with TXID in caption).",
        "deposit_waiting_photo": "📷 Screenshot is required. Send photo with TXID in caption.",
        "deposit_waiting_txid": "🧾 TXID is required in message/caption.",
        "deposit_sent": "⏳ Deposit submitted. Waiting admin review.",
        "deposit_notify_admin": "💰 New deposit request\n👤 User: {user_id}\n💵 Amount: ${amount}\n🧾 TXID: {txid}",
        "deposit_approve": "✅ Approve Deposit",
        "deposit_reject": "🚫 Reject Deposit",
        "deposit_approved_user": "✅ Your deposit ${amount} has been approved.",
        "deposit_rejected_user": "🚫 Your deposit ${amount} has been rejected.",
        "deposit_reviewed": "✅ Deposit updated.",
        "deposit_not_found": "⚠️ Deposit not found or already reviewed.",
        "refund_done": "✅ Auto refund added: ${amount}",
        "otp_timeout_refund": "⏰ OTP not received in 25 minutes. Full refund: ${amount}",
    }
)

SERVICE_ALIAS = {
    "facebook": ["facebook", "fb", "ফেসবুক", "फेसबुक", "فيسبوك", "фейсбук"],
    "telegram": ["telegram", "tg", "টেলিগ্রাম", "टेलीग्राम", "تيليجرام", "телеграм"],
    "whatsapp": ["whatsapp", "wa", "হোয়াটসঅ্যাপ", "व्हाट्सऐप", "واتساب", "ватсап"],
    "instagram": ["instagram", "insta", "ইনস্টাগ্রাম", "इंस्टाग्राम", "انستغرام", "инстаграм"],
    "google": ["google", "gmail", "গুগল", "गूगल", "جوجل", "гугл"],
}

ERR_MAP = {
    "BAD_KEY": "bad_key",
    "BAD_ACTION": "bad_action",
    "BAD_SERVICE": "bad_service",
    "BAD_COUNTRY": "bad_country",
    "BAD_STATUS": "bad_status",
    "NO_BALANCE": "no_balance",
    "NO_ACTIVATION": "no_activation_err",
    "EARLY_CANCEL_DENIED": "early_cancel_denied",
}

COUNTRY_NAME_ALIASES = {
    "papua new gvineya": "Papua New Guinea",
    "great britain": "United Kingdom",
    "england": "United Kingdom",
    "usa": "United States",
    "u.s.a": "United States",
    "u.s.": "United States",
    "south korea": "Korea, Republic of",
    "north korea": "Korea, Democratic People's Republic of",
    "russia": "Russian Federation",
    "laos": "Lao People's Democratic Republic",
    "moldova": "Moldova, Republic of",
    "syria": "Syrian Arab Republic",
    "venezuela": "Venezuela, Bolivarian Republic of",
    "bolivia": "Bolivia, Plurinational State of",
    "tanzania": "Tanzania, United Republic of",
    "iran": "Iran, Islamic Republic of",
    "vietnam": "Viet Nam",
    "brunei": "Brunei Darussalam",
    "united states virtual": "United States",
    "argentinas": "Argentina",
    "cote d ivoire ivory coast": "Cote d'Ivoire",
    "lao people s": "Lao People's Democratic Republic",
    "macau": "Macao",
    "cape verde": "Cabo Verde",
    "congo dem republic": "Congo, The Democratic Republic of the",
    "swaziland": "Eswatini",
}

logger = logging.getLogger("templine_bot")


def acquire_instance_lock(lock_path: str) -> bool:
    global LOCK_HANDLE
    p = Path(lock_path)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent / p
    p.parent.mkdir(parents=True, exist_ok=True)

    if os.name == "nt":
        import msvcrt

        f = open(p, "a+b")
        f.seek(0, os.SEEK_SET)
        if f.tell() == 0:
            f.write(b"0")
            f.flush()
            f.seek(0, os.SEEK_SET)
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            f.close()
            return False
        LOCK_HANDLE = f
        return True

    import fcntl

    f = open(p, "a+")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return False
    LOCK_HANDLE = f
    return True


def release_instance_lock() -> None:
    global LOCK_HANDLE
    if LOCK_HANDLE is None:
        return
    try:
        if os.name == "nt":
            import msvcrt

            LOCK_HANDLE.seek(0, os.SEEK_SET)
            msvcrt.locking(LOCK_HANDLE.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(LOCK_HANDLE.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        LOCK_HANDLE.close()
    except Exception:
        pass
    LOCK_HANDLE = None


def md(v: Any) -> str:
    return escape_markdown(str(v), version=2)


def cd(v: Any) -> str:
    return f"`{escape_markdown(str(v), version=2, entity_type='code')}`"


def now_ts() -> int:
    return int(time.time())


def dec(v: Any, fallback: str = "0") -> Decimal:
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(fallback)


def money(v: Any) -> str:
    q = dec(v).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    s = format(q, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s if s else "0"


def role_of(row: Optional[Dict[str, Any]]) -> str:
    if not row:
        return ROLE_PENDING
    x = str(row.get("role") or ROLE_PENDING).lower()
    if x in {ROLE_ADMIN, ROLE_USER, ROLE_SUPER, ROLE_PENDING, ROLE_BLOCKED}:
        return x
    return ROLE_PENDING


def is_approved_role(role: str) -> bool:
    return role in APPROVED_ROLES


def build_supabase_pg_dsn() -> str:
    if SUPABASE_DB_DSN:
        return SUPABASE_DB_DSN
    if not SUPABASE_DB_PASSWORD:
        raise SystemExit("SUPABASE_DB_PASSWORD is required")
    host = SUPABASE_DB_HOST
    if not host:
        if not SUPABASE_URL:
            raise SystemExit("Set SUPABASE_URL or SUPABASE_DB_HOST")
        parsed = urlparse(SUPABASE_URL)
        ref = parsed.netloc.split(".")[0]
        if not ref:
            raise SystemExit("Invalid SUPABASE_URL")
        host = f"db.{ref}.supabase.co"
    hostaddr = SUPABASE_DB_HOSTADDR
    if not hostaddr and SUPABASE_FORCE_IPV4:
        try:
            infos = socket.getaddrinfo(host, SUPABASE_DB_PORT, socket.AF_INET, socket.SOCK_STREAM)
            if infos:
                hostaddr = infos[0][4][0]
        except Exception:
            hostaddr = ""

    parts = [
        f"host={host}",
        f"port={SUPABASE_DB_PORT}",
        f"dbname={SUPABASE_DB_NAME}",
        f"user={SUPABASE_DB_USER}",
        f"password={SUPABASE_DB_PASSWORD}",
        f"sslmode={SUPABASE_DB_SSLMODE}",
    ]
    if hostaddr:
        parts.append(f"hostaddr={hostaddr}")
    return " ".join(parts)


def profit_percent_from_settings(s: Dict[str, Any]) -> Decimal:
    pct = dec(s.get("profit_percent", "20"), "20")
    if pct < 0:
        return Decimal("0")
    if pct > 500:
        return Decimal("500")
    return pct


def payment_settings_to_lines(settings: Dict[str, Any]) -> str:
    if not settings:
        return "telegram_username: -\nbinance: -\nbkash: -\nnagad: -"
    keys = list(settings.keys())
    pref = ["telegram_username", "binance", "bkash", "nagad"]
    ordered = [k for k in pref if k in settings] + [k for k in keys if k not in pref]
    lines = [f"{k}: {settings.get(k) or '-'}" for k in ordered]
    return "\n".join(lines)


def jwt_role(token: str) -> Optional[str]:
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1]
        padding = "=" * (-len(payload) % 4)
        raw = base64.urlsafe_b64decode(payload + padding).decode("utf-8")
        obj = json.loads(raw)
        role = obj.get("role")
        return str(role) if role is not None else None
    except Exception:
        return None


def tt(lang: str, key: str, **kw: Any) -> str:
    base = TR.get(lang, TR["en"])
    val = base.get(key, TR["en"].get(key, key))
    return val.format(**kw) if isinstance(val, str) else str(val)


def lang_from_code(code: Optional[str]) -> str:
    if not code:
        return "en"
    x = code.split("-")[0].lower()
    return x if x in LANGS else "en"


def detect_action(text: str) -> Optional[str]:
    cleaned = text.strip()
    for lg in LANGS:
        if cleaned == tt(lg, "m_select"):
            return "select"
        if cleaned == tt(lg, "m_search"):
            return "search"
        if cleaned == tt(lg, "m_balance"):
            return "balance"
        if cleaned == tt(lg, "m_wallet"):
            return "wallet"
        if cleaned == tt(lg, "m_deposit"):
            return "deposit"
        if cleaned == tt(lg, "m_admin"):
            return "admin_panel"
    return None


def main_menu(lang: str, role: str = ROLE_USER) -> ReplyKeyboardMarkup:
    rows: List[List[str]] = [[tt(lang, "m_select")], [tt(lang, "m_search")]]
    if role == ROLE_ADMIN:
        rows.append([tt(lang, "m_balance")])
        rows.append([tt(lang, "m_admin")])
    elif role in {ROLE_USER, ROLE_SUPER}:
        rows.append([tt(lang, "m_wallet")])
        rows.append([tt(lang, "m_deposit")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, is_persistent=True)


def lang_keyboard() -> InlineKeyboardMarkup:
    rows, row = [], []
    for i, lg in enumerate(LANGS, start=1):
        row.append(InlineKeyboardButton(LANG_LABEL[lg], callback_data=f"lg:{lg}"))
        if i % 2 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def copy_button(label: str, text: str, fallback_cb: str) -> InlineKeyboardButton:
    if HAS_COPY and CopyTextButton:
        return InlineKeyboardButton(label, copy_text=CopyTextButton(text=text))
    return InlineKeyboardButton(label, callback_data=fallback_cb)


def to_flag(iso2: Optional[str]) -> str:
    if not iso2 or len(iso2) != 2 or not iso2.isalpha():
        return "🌍"
    s = iso2.upper()
    return chr(127397 + ord(s[0])) + chr(127397 + ord(s[1]))


def normalize_country_name(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9 ]+", " ", name or "")
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def country_name_to_iso2(name: str) -> Optional[str]:
    if not name:
        return None
    normalized = normalize_country_name(name)
    alias_name = COUNTRY_NAME_ALIASES.get(normalized, name)
    if not pycountry:
        return None
    try:
        hit = pycountry.countries.search_fuzzy(alias_name)[0]
        code = getattr(hit, "alpha_2", None)
        return str(code).upper() if code else None
    except Exception:
        pass
    try:
        hit = pycountry.countries.get(name=alias_name)
        code = getattr(hit, "alpha_2", None) if hit else None
        return str(code).upper() if code else None
    except Exception:
        return None


def fmt_mmss(total_seconds: int) -> str:
    secs = max(0, int(total_seconds))
    m, s = divmod(secs, 60)
    return f"{m:02d}:{s:02d}"


def cancel_remaining_seconds(row: Dict[str, Any]) -> int:
    started = row.get("created_at") or row.get("activation_started_at") or row.get("updated")
    if started is None:
        # If timestamp is unavailable, keep cancellation locked by default.
        return CANCEL_LOCK_SECONDS
    try:
        age = int(time.time()) - int(started)
    except Exception:
        return CANCEL_LOCK_SECONDS
    return max(0, CANCEL_LOCK_SECONDS - max(0, age))


def can_cancel_activation(row: Dict[str, Any]) -> bool:
    return cancel_remaining_seconds(row) == 0


def another_one_label(lang: str) -> str:
    val = tt(lang, "another_one")
    return val if val != "another_one" else "🆕 Another One"


def cancel_lock_message(lang: str, remaining_seconds: int) -> str:
    remaining = fmt_mmss(remaining_seconds)
    tpl = tt(lang, "cancel_lock")
    if tpl == "cancel_lock":
        if lang == "bn":
            return f"⏳ ৩ মিনিট আগে ক্যানসেল করা যাবে না। বাকি: {remaining}"
        return f"⏳ You can cancel after 3 minutes. Remaining: {remaining}"
    try:
        return tpl.format(remaining=remaining)
    except Exception:
        return f"⏳ You can cancel after 3 minutes. Remaining: {remaining}"


def otp_received_cancel_message(lang: str) -> str:
    if lang == "bn":
        return "✅ এই নাম্বারে OTP রিসিভ হয়েছে, তাই এখন ক্যানসেল করা যাবে না।"
    return "✅ OTP already received for this activation. It can no longer be canceled."


def json_maybe(raw: str) -> Any:
    t = raw.strip()
    if t.startswith("{") or t.startswith("["):
        try:
            return json.loads(t)
        except Exception:
            return t
    return t


def _is_stale_query_error(exc: BadRequest) -> bool:
    m = str(exc).lower()
    return "query is too old" in m or "query id is invalid" in m or "response timeout expired" in m


async def safe_answer_callback(q, text: Optional[str] = None, show_alert: bool = False) -> None:
    for attempt in range(2):
        try:
            if text is None:
                await q.answer()
            else:
                await q.answer(text, show_alert=show_alert)
            return
        except BadRequest as e:
            if _is_stale_query_error(e):
                logger.info("Ignored stale callback query")
                return
            raise
        except TimedOut:
            if attempt == 0:
                await asyncio.sleep(0.25)
                continue
            logger.warning("answerCallbackQuery timed out")
            return
        except NetworkError as e:
            logger.warning("answerCallbackQuery network error: %s", e)
            return


async def safe_reply_markdown(message, text: str, reply_markup=None) -> None:
    try:
        await message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=reply_markup)
    except BadRequest as e:
        logger.warning("Markdown send failed, falling back to plain text: %s", e)
        plain = re.sub(r"\\([_\\*\\[\\]()~`>#+\\-=|{}.!])", r"\1", text)
        await message.reply_text(plain, reply_markup=reply_markup)


async def adb(fn, *args, **kwargs):
    return await asyncio.to_thread(fn, *args, **kwargs)


@dataclass
class PriceOption:
    service_code: str
    service_name: str
    country_code: str
    country_name: str
    country_iso2: Optional[str]
    provider_id: Optional[str]
    provider_name: Optional[str]
    price: str
    base_price: str = "0"

    @property
    def label(self) -> str:
        base = f"{to_flag(self.country_iso2)} {self.country_name}"
        if self.provider_name:
            base += f" • {self.provider_name}"
        return f"{base} - ${self.price}"


class DB:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.RLock()
        self.init()

    def conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    def init(self) -> None:
        with self.lock:
            c = self.conn()
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS users(
                  user_id INTEGER PRIMARY KEY,
                  chat_id INTEGER,
                  lang TEXT NOT NULL DEFAULT 'en',
                  activation_id TEXT,
                  activation_started_at INTEGER,
                  service_code TEXT,
                  country_code TEXT,
                  provider_id TEXT,
                  phone TEXT,
                  polling INTEGER NOT NULL DEFAULT 0,
                  updated INTEGER NOT NULL DEFAULT (strftime('%s','now'))
                )
                """
            )
            cols = {r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()}
            if "activation_started_at" not in cols:
                c.execute("ALTER TABLE users ADD COLUMN activation_started_at INTEGER")
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS activations(
                  activation_id TEXT PRIMARY KEY,
                  user_id INTEGER NOT NULL,
                  chat_id INTEGER NOT NULL,
                  service_code TEXT,
                  country_code TEXT,
                  provider_id TEXT,
                  phone TEXT,
                  status TEXT NOT NULL DEFAULT 'active',
                  otp_code TEXT,
                  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
                  updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
                )
                """
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_activations_user_status ON activations(user_id, status)")
            c.execute(
                """
                INSERT INTO activations(
                  activation_id, user_id, chat_id, service_code, country_code, provider_id, phone, status, otp_code, created_at, updated_at
                )
                SELECT
                  activation_id, user_id, chat_id, service_code, country_code, provider_id, phone, 'active', NULL,
                  COALESCE(activation_started_at, strftime('%s','now')),
                  strftime('%s','now')
                FROM users
                WHERE polling=1
                  AND activation_id IS NOT NULL
                  AND chat_id IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM activations a WHERE a.activation_id = users.activation_id
                  )
                """
            )
            c.commit()
            c.close()

    def get(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self.lock:
            c = self.conn()
            row = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
            c.close()
            return dict(row) if row else None

    def upsert(self, user_id: int, chat_id: int, lang: Optional[str] = None) -> Dict[str, Any]:
        with self.lock:
            c = self.conn()
            row = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
            if row is None:
                c.execute(
                    "INSERT INTO users(user_id, chat_id, lang, updated) VALUES (?,?,?,strftime('%s','now'))",
                    (user_id, chat_id, lang or "en"),
                )
            elif lang:
                c.execute(
                    "UPDATE users SET chat_id=?, lang=?, updated=strftime('%s','now') WHERE user_id=?",
                    (chat_id, lang, user_id),
                )
            else:
                c.execute(
                    "UPDATE users SET chat_id=?, updated=strftime('%s','now') WHERE user_id=?",
                    (chat_id, user_id),
                )
            c.commit()
            out = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
            c.close()
            return dict(out) if out else {}

    def set_lang(self, user_id: int, chat_id: int, lang: str) -> None:
        self.upsert(user_id, chat_id, lang)

    def set_activation(
        self,
        user_id: int,
        chat_id: int,
        aid: str,
        service: str,
        country: str,
        provider_id: Optional[str],
        phone: str,
    ) -> None:
        with self.lock:
            c = self.conn()
            c.execute(
                """
                INSERT INTO users(
                  user_id, chat_id, lang, activation_id, activation_started_at, service_code, country_code, provider_id, phone, polling, updated
                )
                VALUES(?,?,COALESCE((SELECT lang FROM users WHERE user_id=?),'en'),?,strftime('%s','now'),?,?,?,?,1,strftime('%s','now'))
                ON CONFLICT(user_id) DO UPDATE SET
                  chat_id=excluded.chat_id,
                  activation_id=excluded.activation_id,
                  activation_started_at=strftime('%s','now'),
                  service_code=excluded.service_code,
                  country_code=excluded.country_code,
                  provider_id=excluded.provider_id,
                  phone=excluded.phone,
                  polling=1,
                  updated=strftime('%s','now')
                """,
                (user_id, chat_id, user_id, aid, service, country, provider_id, phone),
            )
            c.commit()
            c.close()

    def clear_activation(self, user_id: int) -> None:
        with self.lock:
            c = self.conn()
            c.execute(
                """
                UPDATE users SET
                  activation_id=NULL, activation_started_at=NULL, service_code=NULL, country_code=NULL, provider_id=NULL, phone=NULL, polling=0,
                  updated=strftime('%s','now')
                WHERE user_id=?
                """,
                (user_id,),
            )
            c.commit()
            c.close()

    def active_rows(self) -> List[Dict[str, Any]]:
        with self.lock:
            c = self.conn()
            rows = c.execute(
                "SELECT * FROM users WHERE polling=1 AND activation_id IS NOT NULL AND chat_id IS NOT NULL"
            ).fetchall()
            c.close()
            return [dict(r) for r in rows]

    def add_activation(
        self,
        user_id: int,
        chat_id: int,
        activation_id: str,
        service_code: str,
        country_code: str,
        provider_id: Optional[str],
        phone: str,
    ) -> None:
        with self.lock:
            c = self.conn()
            c.execute(
                """
                INSERT INTO activations(
                  activation_id, user_id, chat_id, service_code, country_code, provider_id, phone, status, otp_code, created_at, updated_at
                )
                VALUES(?,?,?,?,?,?,?,'active',NULL,strftime('%s','now'),strftime('%s','now'))
                ON CONFLICT(activation_id) DO UPDATE SET
                  user_id=excluded.user_id,
                  chat_id=excluded.chat_id,
                  service_code=excluded.service_code,
                  country_code=excluded.country_code,
                  provider_id=excluded.provider_id,
                  phone=excluded.phone,
                  status='active',
                  otp_code=NULL,
                  updated_at=strftime('%s','now')
                """,
                (activation_id, user_id, chat_id, service_code, country_code, provider_id, phone),
            )
            c.commit()
            c.close()

    def get_activation(self, activation_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            c = self.conn()
            row = c.execute("SELECT * FROM activations WHERE activation_id=?", (activation_id,)).fetchone()
            c.close()
            return dict(row) if row else None

    def set_activation_status(self, activation_id: str, status: str, otp_code: Optional[str] = None) -> None:
        with self.lock:
            c = self.conn()
            c.execute(
                """
                UPDATE activations
                SET status=?, otp_code=COALESCE(?, otp_code), updated_at=strftime('%s','now')
                WHERE activation_id=?
                """,
                (status, otp_code, activation_id),
            )
            if status != "active":
                c.execute(
                    "UPDATE users SET polling=0, updated=strftime('%s','now') WHERE activation_id=?",
                    (activation_id,),
                )
            c.commit()
            c.close()

    def list_active_activations(self) -> List[Dict[str, Any]]:
        with self.lock:
            c = self.conn()
            rows = c.execute("SELECT * FROM activations WHERE status='active'").fetchall()
            c.close()
            return [dict(r) for r in rows]

    def latest_active_activation_for_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self.lock:
            c = self.conn()
            row = c.execute(
                """
                SELECT * FROM activations
                WHERE user_id=? AND status='active'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            c.close()
            return dict(row) if row else None


class SupabaseDB:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.lock = threading.RLock()
        self.init()

    def conn(self, autocommit: bool = True):
        return psycopg.connect(self.dsn, autocommit=autocommit)

    def init(self) -> None:
        with self.lock:
            with self.conn() as c:
                with c.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS users(
                          user_id BIGINT PRIMARY KEY,
                          chat_id BIGINT,
                          username TEXT,
                          full_name TEXT,
                          lang TEXT NOT NULL DEFAULT 'en',
                          role TEXT NOT NULL DEFAULT 'pending',
                          approval_notified BOOLEAN NOT NULL DEFAULT FALSE,
                          approved_by BIGINT,
                          approved_at BIGINT,
                          balance NUMERIC(18,6) NOT NULL DEFAULT 0,
                          activation_id TEXT,
                          activation_started_at BIGINT,
                          service_code TEXT,
                          country_code TEXT,
                          provider_id TEXT,
                          phone TEXT,
                          polling INTEGER NOT NULL DEFAULT 0,
                          created BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM now())::BIGINT,
                          updated BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM now())::BIGINT
                        )
                        """
                    )
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS settings(
                          key TEXT PRIMARY KEY,
                          value TEXT NOT NULL,
                          updated BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM now())::BIGINT
                        )
                        """
                    )
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
                    cur.execute(
                        """
                        INSERT INTO settings(key, value, updated)
                        VALUES('profit_percent', '20', %s)
                        ON CONFLICT (key) DO NOTHING
                        """,
                        (now_ts(),),
                    )
                    cur.execute(
                        """
                        INSERT INTO settings(key, value, updated)
                        VALUES('payment_methods', %s, %s)
                        ON CONFLICT (key) DO NOTHING
                        """,
                        (json.dumps({}), now_ts()),
                    )

                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS activations(
                          activation_id TEXT PRIMARY KEY,
                          user_id BIGINT NOT NULL,
                          chat_id BIGINT NOT NULL,
                          service_code TEXT,
                          country_code TEXT,
                          provider_id TEXT,
                          phone TEXT,
                          status TEXT NOT NULL DEFAULT 'active',
                          otp_code TEXT,
                          base_price NUMERIC(18,6) NOT NULL DEFAULT 0,
                          charged_price NUMERIC(18,6) NOT NULL DEFAULT 0,
                          refunded BOOLEAN NOT NULL DEFAULT FALSE,
                          refund_amount NUMERIC(18,6) NOT NULL DEFAULT 0,
                          created_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM now())::BIGINT,
                          updated_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM now())::BIGINT
                        )
                        """
                    )
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_activations_user_status ON activations(user_id, status)")

                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS deposits(
                          id BIGSERIAL PRIMARY KEY,
                          user_id BIGINT NOT NULL,
                          amount NUMERIC(18,6) NOT NULL,
                          txid TEXT,
                          screenshot_file_id TEXT,
                          status TEXT NOT NULL DEFAULT 'awaiting_proof',
                          reviewed_by BIGINT,
                          reviewed_at BIGINT,
                          note TEXT,
                          created_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM now())::BIGINT,
                          updated_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM now())::BIGINT
                        )
                        """
                    )
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_deposits_status ON deposits(status)")

        self.ensure_admin_user(ADMIN_USER_ID)

    def get(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self.lock:
            with self.conn() as c:
                with c.cursor(row_factory=dict_row) as cur:
                    cur.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
                    row = cur.fetchone()
                    return dict(row) if row else None

    def upsert(
        self,
        user_id: int,
        chat_id: int,
        lang: Optional[str] = None,
        role: Optional[str] = None,
        username: Optional[str] = None,
        full_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self.lock:
            with self.conn() as c:
                with c.cursor(row_factory=dict_row) as cur:
                    cur.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
                    row = cur.fetchone()
                    ts = now_ts()
                    if row is None:
                        cur.execute(
                            """
                            INSERT INTO users(user_id, chat_id, username, full_name, lang, role, created, updated)
                            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                            """,
                            (user_id, chat_id, username, full_name, lang or "en", role or ROLE_PENDING, ts, ts),
                        )
                    else:
                        cur.execute(
                            """
                            UPDATE users
                            SET chat_id=%s,
                                username=%s,
                                full_name=%s,
                                lang=COALESCE(%s, lang),
                                role=COALESCE(%s, role),
                                updated=%s
                            WHERE user_id=%s
                            """,
                            (
                                chat_id,
                                username if username is not None else row.get("username"),
                                full_name if full_name is not None else row.get("full_name"),
                                lang,
                                role,
                                ts,
                                user_id,
                            ),
                        )
                    cur.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
                    out = cur.fetchone()
                    return dict(out) if out else {}

    def set_lang(self, user_id: int, chat_id: int, lang: str) -> None:
        self.upsert(user_id, chat_id, lang=lang)

    def ensure_admin_user(self, user_id: int) -> None:
        with self.lock:
            with self.conn() as c:
                with c.cursor(row_factory=dict_row) as cur:
                    ts = now_ts()
                    cur.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
                    row = cur.fetchone()
                    if row is None:
                        cur.execute(
                            """
                            INSERT INTO users(user_id, chat_id, lang, role, approval_notified, approved_by, approved_at, created, updated)
                            VALUES(%s,%s,'en',%s,TRUE,%s,%s,%s,%s)
                            """,
                            (user_id, user_id, ROLE_ADMIN, user_id, ts, ts, ts),
                        )
                    else:
                        cur.execute(
                            """
                            UPDATE users
                            SET role=%s, approval_notified=TRUE, approved_by=%s, approved_at=COALESCE(approved_at,%s), updated=%s
                            WHERE user_id=%s
                            """,
                            (ROLE_ADMIN, user_id, ts, ts, user_id),
                        )

    def mark_approval_notified(self, user_id: int) -> None:
        with self.lock:
            with self.conn() as c:
                with c.cursor() as cur:
                    cur.execute("UPDATE users SET approval_notified=TRUE, updated=%s WHERE user_id=%s", (now_ts(), user_id))

    def set_role(self, user_id: int, role: str, approved_by: Optional[int] = None) -> None:
        with self.lock:
            with self.conn() as c:
                with c.cursor() as cur:
                    ts = now_ts()
                    cur.execute(
                        """
                        UPDATE users
                        SET role=%s,
                            approval_notified=TRUE,
                            approved_by=COALESCE(%s, approved_by),
                            approved_at=CASE WHEN %s IN ('admin','user','super_user') THEN %s ELSE approved_at END,
                            updated=%s
                        WHERE user_id=%s
                        """,
                        (role, approved_by, role, ts, ts, user_id),
                    )

    def list_pending_users(self) -> List[Dict[str, Any]]:
        with self.lock:
            with self.conn() as c:
                with c.cursor(row_factory=dict_row) as cur:
                    cur.execute("SELECT * FROM users WHERE role=%s ORDER BY created ASC LIMIT 200", (ROLE_PENDING,))
                    return [dict(r) for r in cur.fetchall()]

    def list_all_users(self, include_blocked: bool = True) -> List[Dict[str, Any]]:
        with self.lock:
            with self.conn() as c:
                with c.cursor(row_factory=dict_row) as cur:
                    if include_blocked:
                        cur.execute("SELECT * FROM users ORDER BY created ASC")
                    else:
                        cur.execute("SELECT * FROM users WHERE role<>%s ORDER BY created ASC", (ROLE_BLOCKED,))
                    return [dict(r) for r in cur.fetchall()]

    def user_stats(self) -> Dict[str, int]:
        out = {"total": 0, "pending": 0, "user": 0, "super_user": 0, "admin": 0, "blocked": 0}
        with self.lock:
            with self.conn() as c:
                with c.cursor(row_factory=dict_row) as cur:
                    cur.execute("SELECT role, COUNT(*) AS c FROM users GROUP BY role")
                    rows = cur.fetchall()
                    total = 0
                    for r in rows:
                        role = str(r.get("role") or ROLE_PENDING)
                        cnt = int(r.get("c") or 0)
                        out[role] = cnt
                        total += cnt
                    out["total"] = total
        return out

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self.lock:
            with self.conn() as c:
                with c.cursor() as cur:
                    cur.execute("SELECT value FROM settings WHERE key=%s", (key,))
                    row = cur.fetchone()
                    return row[0] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.lock:
            with self.conn() as c:
                with c.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO settings(key, value, updated)
                        VALUES(%s,%s,%s)
                        ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value, updated=EXCLUDED.updated
                        """,
                        (key, value, now_ts()),
                    )

    def get_profit_percent(self) -> Decimal:
        raw = self.get_setting("profit_percent", "20")
        return profit_percent_from_settings({"profit_percent": raw})

    def set_profit_percent(self, pct: Decimal) -> None:
        p = max(Decimal("0"), min(Decimal("500"), dec(pct)))
        self.set_setting("profit_percent", money(p))

    def get_payment_settings(self) -> Dict[str, str]:
        raw = self.get_setting("payment_methods", "{}") or "{}"
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except Exception:
            pass
        return {}

    def update_payment_settings(self, items: Dict[str, str]) -> Dict[str, str]:
        cur = self.get_payment_settings()
        for k, v in items.items():
            kk = str(k or "").strip().lower()
            if not kk:
                continue
            cur[kk] = str(v or "").strip()
        self.set_setting("payment_methods", json.dumps(cur, ensure_ascii=False))
        return cur

    def adjust_balance(self, user_id: int, delta: Decimal, require_non_negative: bool = False) -> Optional[Decimal]:
        with self.lock:
            with self.conn() as c:
                with c.cursor() as cur:
                    if require_non_negative:
                        cur.execute(
                            """
                            UPDATE users
                            SET balance=balance+%s, updated=%s
                            WHERE user_id=%s AND balance+%s >= 0
                            RETURNING balance
                            """,
                            (dec(delta), now_ts(), user_id, dec(delta)),
                        )
                    else:
                        cur.execute(
                            """
                            UPDATE users
                            SET balance=balance+%s, updated=%s
                            WHERE user_id=%s
                            RETURNING balance
                            """,
                            (dec(delta), now_ts(), user_id),
                        )
                    row = cur.fetchone()
                    return dec(row[0]) if row else None

    def get_balance(self, user_id: int) -> Decimal:
        row = self.get(user_id) or {}
        return dec(row.get("balance", "0"))

    def set_activation(
        self,
        user_id: int,
        chat_id: int,
        aid: str,
        service: str,
        country: str,
        provider_id: Optional[str],
        phone: str,
    ) -> None:
        with self.lock:
            ts = now_ts()
            with self.conn() as c:
                with c.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE users
                        SET chat_id=%s,
                            activation_id=%s,
                            activation_started_at=%s,
                            service_code=%s,
                            country_code=%s,
                            provider_id=%s,
                            phone=%s,
                            polling=1,
                            updated=%s
                        WHERE user_id=%s
                        """,
                        (chat_id, aid, ts, service, country, provider_id, phone, ts, user_id),
                    )

    def clear_activation(self, user_id: int) -> None:
        with self.lock:
            with self.conn() as c:
                with c.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE users SET
                          activation_id=NULL, activation_started_at=NULL, service_code=NULL, country_code=NULL, provider_id=NULL, phone=NULL, polling=0,
                          updated=%s
                        WHERE user_id=%s
                        """,
                        (now_ts(), user_id),
                    )

    def active_rows(self) -> List[Dict[str, Any]]:
        with self.lock:
            with self.conn() as c:
                with c.cursor(row_factory=dict_row) as cur:
                    cur.execute("SELECT * FROM users WHERE polling=1 AND activation_id IS NOT NULL AND chat_id IS NOT NULL")
                    return [dict(r) for r in cur.fetchall()]

    def add_activation(
        self,
        user_id: int,
        chat_id: int,
        activation_id: str,
        service_code: str,
        country_code: str,
        provider_id: Optional[str],
        phone: str,
        base_price: Any = 0,
        charged_price: Any = 0,
    ) -> None:
        with self.lock:
            ts = now_ts()
            with self.conn() as c:
                with c.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO activations(
                          activation_id, user_id, chat_id, service_code, country_code, provider_id, phone, status, otp_code,
                          base_price, charged_price, refunded, refund_amount, created_at, updated_at
                        )
                        VALUES(%s,%s,%s,%s,%s,%s,%s,'active',NULL,%s,%s,FALSE,0,%s,%s)
                        ON CONFLICT(activation_id) DO UPDATE SET
                          user_id=EXCLUDED.user_id,
                          chat_id=EXCLUDED.chat_id,
                          service_code=EXCLUDED.service_code,
                          country_code=EXCLUDED.country_code,
                          provider_id=EXCLUDED.provider_id,
                          phone=EXCLUDED.phone,
                          status='active',
                          otp_code=NULL,
                          base_price=EXCLUDED.base_price,
                          charged_price=EXCLUDED.charged_price,
                          refunded=FALSE,
                          refund_amount=0,
                          updated_at=EXCLUDED.updated_at
                        """,
                        (
                            activation_id,
                            user_id,
                            chat_id,
                            service_code,
                            country_code,
                            provider_id,
                            phone,
                            dec(base_price),
                            dec(charged_price),
                            ts,
                            ts,
                        ),
                    )

    def get_activation(self, activation_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            with self.conn() as c:
                with c.cursor(row_factory=dict_row) as cur:
                    cur.execute("SELECT * FROM activations WHERE activation_id=%s", (activation_id,))
                    row = cur.fetchone()
                    return dict(row) if row else None

    def set_activation_status(self, activation_id: str, status: str, otp_code: Optional[str] = None) -> None:
        with self.lock:
            with self.conn() as c:
                with c.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE activations
                        SET status=%s, otp_code=COALESCE(%s, otp_code), updated_at=%s
                        WHERE activation_id=%s
                        """,
                        (status, otp_code, now_ts(), activation_id),
                    )
                    if status != "active":
                        cur.execute("UPDATE users SET polling=0, updated=%s WHERE activation_id=%s", (now_ts(), activation_id))

    def list_active_activations(self) -> List[Dict[str, Any]]:
        with self.lock:
            with self.conn() as c:
                with c.cursor(row_factory=dict_row) as cur:
                    cur.execute("SELECT * FROM activations WHERE status='active'")
                    return [dict(r) for r in cur.fetchall()]

    def latest_active_activation_for_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self.lock:
            with self.conn() as c:
                with c.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        SELECT * FROM activations
                        WHERE user_id=%s AND status='active'
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        (user_id,),
                    )
                    row = cur.fetchone()
                    return dict(row) if row else None

    def refund_activation_if_needed(self, activation_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            with self.conn(autocommit=False) as c:
                with c.cursor(row_factory=dict_row) as cur:
                    cur.execute("SELECT * FROM activations WHERE activation_id=%s FOR UPDATE", (activation_id,))
                    act = cur.fetchone()
                    if not act:
                        c.rollback()
                        return None
                    charged = dec(act.get("charged_price", "0"))
                    if bool(act.get("refunded")) or charged <= 0:
                        c.rollback()
                        return None
                    uid = int(act.get("user_id"))
                    ts = now_ts()
                    cur.execute(
                        """
                        UPDATE activations
                        SET refunded=TRUE, refund_amount=%s, updated_at=%s
                        WHERE activation_id=%s
                        """,
                        (charged, ts, activation_id),
                    )
                    cur.execute("UPDATE users SET balance=balance+%s, updated=%s WHERE user_id=%s", (charged, ts, uid))
                    c.commit()
                    return {"user_id": uid, "amount": money(charged)}

    def create_deposit(self, user_id: int, amount: Decimal) -> int:
        with self.lock:
            with self.conn() as c:
                with c.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO deposits(user_id, amount, status, created_at, updated_at)
                        VALUES(%s,%s,'awaiting_proof',%s,%s)
                        RETURNING id
                        """,
                        (user_id, dec(amount), now_ts(), now_ts()),
                    )
                    row = cur.fetchone()
                    return int(row[0])

    def set_deposit_proof(self, deposit_id: int, txid: str, screenshot_file_id: str) -> None:
        with self.lock:
            with self.conn() as c:
                with c.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE deposits
                        SET txid=%s, screenshot_file_id=%s, status='pending', updated_at=%s
                        WHERE id=%s
                        """,
                        (txid, screenshot_file_id, now_ts(), deposit_id),
                    )

    def get_deposit(self, deposit_id: int) -> Optional[Dict[str, Any]]:
        with self.lock:
            with self.conn() as c:
                with c.cursor(row_factory=dict_row) as cur:
                    cur.execute("SELECT * FROM deposits WHERE id=%s", (deposit_id,))
                    row = cur.fetchone()
                    return dict(row) if row else None

    def latest_open_deposit_for_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self.lock:
            with self.conn() as c:
                with c.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        SELECT * FROM deposits
                        WHERE user_id=%s AND status='awaiting_proof'
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        (user_id,),
                    )
                    row = cur.fetchone()
                    return dict(row) if row else None

    def update_deposit_status(self, deposit_id: int, status: str, reviewed_by: int, note: Optional[str] = None) -> bool:
        with self.lock:
            with self.conn(autocommit=False) as c:
                with c.cursor(row_factory=dict_row) as cur:
                    cur.execute("SELECT * FROM deposits WHERE id=%s FOR UPDATE", (deposit_id,))
                    dep = cur.fetchone()
                    if not dep:
                        c.rollback()
                        return False
                    if str(dep.get("status")) not in {"pending", "awaiting_proof"}:
                        c.rollback()
                        return False
                    ts = now_ts()
                    cur.execute(
                        """
                        UPDATE deposits
                        SET status=%s, reviewed_by=%s, reviewed_at=%s, note=%s, updated_at=%s
                        WHERE id=%s
                        """,
                        (status, reviewed_by, ts, note, ts, deposit_id),
                    )
                    if status == "approved":
                        cur.execute(
                            "UPDATE users SET balance=balance+%s, updated=%s WHERE user_id=%s",
                            (dec(dep.get("amount", "0")), ts, int(dep.get("user_id"))),
                        )
                    c.commit()
                    return True


class SupabaseRESTDB:
    def __init__(self):
        self.lock = threading.RLock()
        if not SUPABASE_URL:
            raise SystemExit("SUPABASE_URL is required")
        if not SUPABASE_KEY:
            raise SystemExit("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY or SUPABASE_SECRET_KEY is required")
        role = jwt_role(SUPABASE_KEY)
        if role and role != "service_role":
            raise SystemExit(
                "Supabase key role is not service_role. "
                "Use Secret/Service Role key (not Publishable/Anon key)."
            )
        self.sb = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.init()

    @staticmethod
    def _rows(resp: Any) -> List[Dict[str, Any]]:
        data = getattr(resp, "data", None)
        if isinstance(data, list):
            return [dict(x) for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            return [dict(data)]
        return []

    @classmethod
    def _one(cls, resp: Any) -> Optional[Dict[str, Any]]:
        rows = cls._rows(resp)
        return rows[0] if rows else None

    def _require_schema(self) -> None:
        try:
            self.sb.table("users").select("user_id").limit(1).execute()
            self.sb.table("activations").select("activation_id").limit(1).execute()
            self.sb.table("deposits").select("id").limit(1).execute()
            self.sb.table("settings").select("key").limit(1).execute()
        except Exception as e:
            raise SystemExit(
                "Supabase tables are missing. Run SQL from `supabase_schema.sql` in Supabase SQL Editor. "
                f"Details: {e}"
            )

    def init(self) -> None:
        self._require_schema()
        try:
            self.set_setting("profit_percent", self.get_setting("profit_percent", "20") or "20")
            self.set_setting("payment_methods", self.get_setting("payment_methods", "{}") or "{}")
        except Exception as e:
            msg = str(e)
            if "row-level security policy" in msg.lower() or "42501" in msg:
                raise SystemExit(
                    "Supabase RLS denied access. Use Service Role key and run updated supabase_schema.sql "
                    "(RLS disabled for bot tables)."
                )
            raise
        self.ensure_admin_user(ADMIN_USER_ID)

    def get(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self.lock:
            return self._one(self.sb.table("users").select("*").eq("user_id", int(user_id)).limit(1).execute())

    def upsert(
        self,
        user_id: int,
        chat_id: int,
        lang: Optional[str] = None,
        role: Optional[str] = None,
        username: Optional[str] = None,
        full_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self.lock:
            old = self.get(user_id)
            ts = now_ts()
            if not old:
                self.sb.table("users").insert(
                    {
                        "user_id": int(user_id),
                        "chat_id": int(chat_id),
                        "username": username,
                        "full_name": full_name,
                        "lang": lang or "en",
                        "role": role or ROLE_PENDING,
                        "created": ts,
                        "updated": ts,
                    }
                ).execute()
            else:
                payload: Dict[str, Any] = {
                    "chat_id": int(chat_id),
                    "username": username if username is not None else old.get("username"),
                    "full_name": full_name if full_name is not None else old.get("full_name"),
                    "updated": ts,
                }
                if lang is not None:
                    payload["lang"] = lang
                if role is not None:
                    payload["role"] = role
                self.sb.table("users").update(payload).eq("user_id", int(user_id)).execute()
            return self.get(user_id) or {}

    def set_lang(self, user_id: int, chat_id: int, lang: str) -> None:
        self.upsert(user_id, chat_id, lang=lang)

    def ensure_admin_user(self, user_id: int) -> None:
        with self.lock:
            ts = now_ts()
            row = self.get(user_id)
            if not row:
                self.sb.table("users").insert(
                    {
                        "user_id": int(user_id),
                        "chat_id": int(user_id),
                        "lang": "en",
                        "role": ROLE_ADMIN,
                        "approval_notified": True,
                        "approved_by": int(user_id),
                        "approved_at": ts,
                        "created": ts,
                        "updated": ts,
                    }
                ).execute()
            else:
                self.sb.table("users").update(
                    {
                        "role": ROLE_ADMIN,
                        "approval_notified": True,
                        "approved_by": int(user_id),
                        "approved_at": row.get("approved_at") or ts,
                        "updated": ts,
                    }
                ).eq("user_id", int(user_id)).execute()

    def mark_approval_notified(self, user_id: int) -> None:
        with self.lock:
            self.sb.table("users").update({"approval_notified": True, "updated": now_ts()}).eq("user_id", int(user_id)).execute()

    def set_role(self, user_id: int, role: str, approved_by: Optional[int] = None) -> None:
        with self.lock:
            ts = now_ts()
            payload: Dict[str, Any] = {"role": role, "approval_notified": True, "updated": ts}
            if approved_by is not None:
                payload["approved_by"] = int(approved_by)
            if role in {ROLE_ADMIN, ROLE_USER, ROLE_SUPER}:
                payload["approved_at"] = ts
            self.sb.table("users").update(payload).eq("user_id", int(user_id)).execute()

    def list_pending_users(self) -> List[Dict[str, Any]]:
        with self.lock:
            return self._rows(self.sb.table("users").select("*").eq("role", ROLE_PENDING).order("created", desc=False).limit(200).execute())

    def list_all_users(self, include_blocked: bool = True) -> List[Dict[str, Any]]:
        with self.lock:
            q = self.sb.table("users").select("*").order("created", desc=False)
            if not include_blocked:
                q = q.neq("role", ROLE_BLOCKED)
            return self._rows(q.execute())

    def user_stats(self) -> Dict[str, int]:
        out = {"total": 0, "pending": 0, "user": 0, "super_user": 0, "admin": 0, "blocked": 0}
        rows = self.list_all_users(include_blocked=True)
        out["total"] = len(rows)
        for r in rows:
            k = role_of(r)
            out[k] = out.get(k, 0) + 1
        return out

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self.lock:
            row = self._one(self.sb.table("settings").select("value").eq("key", key).limit(1).execute())
            return str(row.get("value")) if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.lock:
            self.sb.table("settings").upsert({"key": key, "value": str(value), "updated": now_ts()}, on_conflict="key").execute()

    def get_profit_percent(self) -> Decimal:
        return profit_percent_from_settings({"profit_percent": self.get_setting("profit_percent", "20")})

    def set_profit_percent(self, pct: Decimal) -> None:
        p = max(Decimal("0"), min(Decimal("500"), dec(pct)))
        self.set_setting("profit_percent", money(p))

    def get_payment_settings(self) -> Dict[str, str]:
        raw = self.get_setting("payment_methods", "{}") or "{}"
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                return {str(k): str(v) for k, v in obj.items()}
        except Exception:
            pass
        return {}

    def update_payment_settings(self, items: Dict[str, str]) -> Dict[str, str]:
        cur = self.get_payment_settings()
        for k, v in items.items():
            kk = str(k or "").strip().lower()
            if kk:
                cur[kk] = str(v or "").strip()
        self.set_setting("payment_methods", json.dumps(cur, ensure_ascii=False))
        return cur

    def adjust_balance(self, user_id: int, delta: Decimal, require_non_negative: bool = False) -> Optional[Decimal]:
        with self.lock:
            row = self.get(user_id)
            if not row:
                return None
            new_bal = dec(row.get("balance", "0")) + dec(delta)
            if require_non_negative and new_bal < 0:
                return None
            self.sb.table("users").update({"balance": money(new_bal), "updated": now_ts()}).eq("user_id", int(user_id)).execute()
            return new_bal

    def get_balance(self, user_id: int) -> Decimal:
        return dec((self.get(user_id) or {}).get("balance", "0"))

    def set_activation(self, user_id: int, chat_id: int, aid: str, service: str, country: str, provider_id: Optional[str], phone: str) -> None:
        with self.lock:
            self.sb.table("users").update(
                {
                    "chat_id": int(chat_id),
                    "activation_id": str(aid),
                    "activation_started_at": now_ts(),
                    "service_code": str(service),
                    "country_code": str(country),
                    "provider_id": provider_id,
                    "phone": phone,
                    "polling": 1,
                    "updated": now_ts(),
                }
            ).eq("user_id", int(user_id)).execute()

    def clear_activation(self, user_id: int) -> None:
        with self.lock:
            self.sb.table("users").update(
                {
                    "activation_id": None,
                    "activation_started_at": None,
                    "service_code": None,
                    "country_code": None,
                    "provider_id": None,
                    "phone": None,
                    "polling": 0,
                    "updated": now_ts(),
                }
            ).eq("user_id", int(user_id)).execute()

    def active_rows(self) -> List[Dict[str, Any]]:
        rows = self._rows(self.sb.table("users").select("*").eq("polling", 1).execute())
        return [r for r in rows if r.get("activation_id") and r.get("chat_id")]

    def add_activation(self, user_id: int, chat_id: int, activation_id: str, service_code: str, country_code: str, provider_id: Optional[str], phone: str, base_price: Any = 0, charged_price: Any = 0) -> None:
        with self.lock:
            ts = now_ts()
            self.sb.table("activations").upsert(
                {
                    "activation_id": str(activation_id),
                    "user_id": int(user_id),
                    "chat_id": int(chat_id),
                    "service_code": str(service_code),
                    "country_code": str(country_code),
                    "provider_id": provider_id,
                    "phone": phone,
                    "status": "active",
                    "otp_code": None,
                    "base_price": money(dec(base_price)),
                    "charged_price": money(dec(charged_price)),
                    "refunded": False,
                    "refund_amount": "0",
                    "created_at": ts,
                    "updated_at": ts,
                },
                on_conflict="activation_id",
            ).execute()

    def get_activation(self, activation_id: str) -> Optional[Dict[str, Any]]:
        return self._one(self.sb.table("activations").select("*").eq("activation_id", str(activation_id)).limit(1).execute())

    def set_activation_status(self, activation_id: str, status: str, otp_code: Optional[str] = None) -> None:
        with self.lock:
            payload: Dict[str, Any] = {"status": status, "updated_at": now_ts()}
            if otp_code is not None:
                payload["otp_code"] = otp_code
            self.sb.table("activations").update(payload).eq("activation_id", str(activation_id)).execute()
            if status != "active":
                self.sb.table("users").update({"polling": 0, "updated": now_ts()}).eq("activation_id", str(activation_id)).execute()

    def list_active_activations(self) -> List[Dict[str, Any]]:
        return self._rows(self.sb.table("activations").select("*").eq("status", "active").execute())

    def latest_active_activation_for_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self._one(self.sb.table("activations").select("*").eq("user_id", int(user_id)).eq("status", "active").order("created_at", desc=True).limit(1).execute())

    def refund_activation_if_needed(self, activation_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            act = self.get_activation(activation_id)
            if not act:
                return None
            charged = dec(act.get("charged_price", "0"))
            if bool(act.get("refunded")) or charged <= 0:
                return None
            self.sb.table("activations").update({"refunded": True, "refund_amount": money(charged), "updated_at": now_ts()}).eq("activation_id", str(activation_id)).eq("refunded", False).execute()
            uid = int(act.get("user_id"))
            self.adjust_balance(uid, charged, require_non_negative=False)
            return {"user_id": uid, "amount": money(charged)}

    def create_deposit(self, user_id: int, amount: Decimal) -> int:
        resp = self.sb.table("deposits").insert({"user_id": int(user_id), "amount": money(dec(amount)), "status": "awaiting_proof", "created_at": now_ts(), "updated_at": now_ts()}).execute()
        row = self._one(resp)
        if not row:
            raise RuntimeError("failed to create deposit")
        return int(row["id"])

    def set_deposit_proof(self, deposit_id: int, txid: str, screenshot_file_id: str) -> None:
        self.sb.table("deposits").update({"txid": txid, "screenshot_file_id": screenshot_file_id, "status": "pending", "updated_at": now_ts()}).eq("id", int(deposit_id)).execute()

    def get_deposit(self, deposit_id: int) -> Optional[Dict[str, Any]]:
        return self._one(self.sb.table("deposits").select("*").eq("id", int(deposit_id)).limit(1).execute())

    def latest_open_deposit_for_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self._one(self.sb.table("deposits").select("*").eq("user_id", int(user_id)).eq("status", "awaiting_proof").order("created_at", desc=True).limit(1).execute())

    def update_deposit_status(self, deposit_id: int, status: str, reviewed_by: int, note: Optional[str] = None) -> bool:
        dep = self.get_deposit(deposit_id)
        if not dep:
            return False
        if str(dep.get("status")) not in {"pending", "awaiting_proof"}:
            return False
        self.sb.table("deposits").update({"status": status, "reviewed_by": int(reviewed_by), "reviewed_at": now_ts(), "note": note, "updated_at": now_ts()}).eq("id", int(deposit_id)).execute()
        if status == "approved":
            self.adjust_balance(int(dep.get("user_id")), dec(dep.get("amount", "0")), require_non_negative=False)
        return True


class TemplineAPI:
    def __init__(self, api_key: str, base_url: str):
        self.key = api_key
        self.base = base_url
        self.base_urls = self._build_base_urls(base_url)
        self.http = httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=6.0), follow_redirects=True)

    @staticmethod
    def _build_base_urls(primary: str) -> List[str]:
        out: List[str] = []

        def add(url: Optional[str]) -> None:
            u = str(url or "").strip()
            if not u or u in out:
                return
            out.append(u)

        add(primary)
        if "smsbower.page/stubs/handler_api.php" in primary:
            add(primary.replace("https://smsbower.page/stubs/handler_api.php", "https://smsbower.app/web/stubs/handler_api.php"))
        elif "smsbower.app/web/stubs/handler_api.php" in primary:
            add(primary.replace("https://smsbower.app/web/stubs/handler_api.php", "https://smsbower.page/stubs/handler_api.php"))
        else:
            add("https://smsbower.app/web/stubs/handler_api.php")
            add("https://smsbower.page/stubs/handler_api.php")

        extras = os.getenv("TEMPLINE_FALLBACK_BASE_URLS", "").strip()
        if extras:
            for x in extras.split(","):
                add(x)
        return out

    async def close(self) -> None:
        await self.http.aclose()

    async def call(self, action: str, **kwargs: Any) -> Any:
        params = {"api_key": self.key, "action": action}
        params.update({k: v for k, v in kwargs.items() if v is not None and v != ""})
        last = None
        for base in self.base_urls:
            for _ in range(2):
                try:
                    r = await self.http.get(base, params=params)
                    r.raise_for_status()
                    return json_maybe(r.text.strip())
                except Exception as e:
                    last = e
                    await asyncio.sleep(0.35)
            logger.warning("API endpoint failed for action=%s url=%s err=%s", action, base, last)
        raise RuntimeError(f"request failed: {last}")


def parse_services(payload: Any) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    if isinstance(payload, dict):
        if isinstance(payload.get("services"), list):
            src = payload["services"]
        elif isinstance(payload.get("data"), list):
            src = payload["data"]
        else:
            src = None
        if src is not None:
            for x in src:
                if isinstance(x, dict):
                    code = str(x.get("code") or x.get("id") or "").strip()
                    name = str(x.get("name") or x.get("title") or code).strip()
                    if code:
                        items.append({"code": code, "name": name or code})
        else:
            for k, v in payload.items():
                if k in {"status", "success", "message"}:
                    continue
                if isinstance(v, str):
                    items.append({"code": str(k), "name": v})
                elif isinstance(v, dict):
                    code = str(v.get("code") or k)
                    name = str(v.get("name") or v.get("title") or code)
                    items.append({"code": code, "name": name})
    if isinstance(payload, list):
        for x in payload:
            if isinstance(x, dict):
                code = str(x.get("code") or x.get("id") or "").strip()
                name = str(x.get("name") or x.get("title") or code).strip()
                if code:
                    items.append({"code": code, "name": name or code})
    seen, out = set(), []
    for s in items:
        if s["code"] in seen:
            continue
        seen.add(s["code"])
        out.append(s)
    out.sort(key=lambda z: z["name"].lower())
    return out


def parse_countries(payload: Any) -> Dict[str, Dict[str, Optional[str]]]:
    out: Dict[str, Dict[str, Optional[str]]] = {}
    src = None
    if isinstance(payload, dict):
        if isinstance(payload.get("countries"), list):
            src = payload["countries"]
        elif isinstance(payload.get("data"), list):
            src = payload["data"]
        if src is None:
            for k, v in payload.items():
                if k in {"status", "success", "message"}:
                    continue
                if isinstance(v, str):
                    name = str(v).strip() or str(k)
                    out[str(k)] = {"name": name, "iso2": country_name_to_iso2(name)}
                elif isinstance(v, dict):
                    name = str(
                        v.get("name")
                        or v.get("title")
                        or v.get("eng")
                        or v.get("rus")
                        or v.get("country_name")
                        or k
                    ).strip()
                    iso2 = str(
                        v.get("iso")
                        or v.get("iso2")
                        or v.get("countryCode")
                        or v.get("alpha2")
                        or ""
                    ).upper() or None
                    if not iso2:
                        iso2 = country_name_to_iso2(name)
                    out[str(k)] = {
                        "name": name,
                        "iso2": iso2,
                    }
            return out
    if src is None and isinstance(payload, list):
        src = payload
    if src:
        for x in src:
            if not isinstance(x, dict):
                continue
            cid = str(x.get("id") or x.get("country") or x.get("code") or "").strip()
            if not cid:
                continue
            name = str(
                x.get("name")
                or x.get("title")
                or x.get("eng")
                or x.get("rus")
                or x.get("country_name")
                or cid
            ).strip()
            iso2 = str(
                x.get("iso")
                or x.get("iso2")
                or x.get("countryCode")
                or x.get("alpha2")
                or ""
            ).upper() or None
            if not iso2:
                iso2 = country_name_to_iso2(name)
            out[cid] = {
                "name": name,
                "iso2": iso2,
            }
    return out


def parse_balance(payload: Any) -> Tuple[Optional[str], Optional[str]]:
    if isinstance(payload, str):
        if payload.startswith("ACCESS_BALANCE:"):
            return payload.split(":", 1)[1], None
        return None, payload
    if isinstance(payload, dict):
        for k in ("balance", "amount", "value"):
            if k in payload:
                return str(payload[k]), None
        return None, str(payload.get("error") or payload.get("message") or "UNKNOWN")
    return None, "UNKNOWN"


def normalize_phone(phone: Any) -> str:
    raw = str(phone or "").strip()
    if not raw:
        return raw
    cleaned = re.sub(r"[^\d+]", "", raw)
    if cleaned.startswith("00"):
        cleaned = cleaned[2:]
    if cleaned.startswith("+"):
        digits = re.sub(r"\D", "", cleaned[1:])
        return f"+{digits}" if digits else raw
    digits = re.sub(r"\D", "", cleaned)
    return f"+{digits}" if digits else raw


def parse_number(payload: Any) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if isinstance(payload, str):
        if payload.startswith("ACCESS_NUMBER:"):
            p = payload.split(":", 2)
            if len(p) == 3:
                return p[1], normalize_phone(p[2]), None
        return None, None, payload
    if isinstance(payload, dict):
        aid = payload.get("activationId") or payload.get("id") or payload.get("activation_id")
        phone = payload.get("phoneNumber") or payload.get("phone") or payload.get("number")
        if aid and phone:
            return str(aid), normalize_phone(phone), None
        return None, None, str(payload.get("error") or payload.get("message") or "UNKNOWN")
    return None, None, "UNKNOWN"


def parse_status(payload: Any) -> Tuple[str, Optional[str]]:
    if isinstance(payload, str):
        if payload.startswith("STATUS_OK:"):
            return "OK", payload.split(":", 1)[1]
        if payload.startswith("STATUS_WAIT_RETRY:"):
            return "WAIT", None
        if payload == "STATUS_WAIT_CODE":
            return "WAIT", None
        if payload == "STATUS_CANCEL":
            return "CANCEL", None
        return "ERROR", payload
    if isinstance(payload, dict):
        st = str(payload.get("status", "")).upper()
        if st in {"OK", "SUCCESS"}:
            return "OK", str(payload.get("code") or payload.get("otp") or "")
        return "ERROR", str(payload.get("error") or payload.get("message") or "UNKNOWN")
    return "ERROR", "UNKNOWN"


def api_error(lang: str, raw: str) -> str:
    key = ERR_MAP.get(raw, "generic_fail")
    return tt(lang, key) if key in TR["en"] else f"{tt(lang, 'generic_fail')} ({raw})"


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def match_services(query: str, services: List[Dict[str, str]]) -> List[Dict[str, str]]:
    q = norm(query)
    if not q:
        return []
    canon_hits = {c for c, aliases in SERVICE_ALIAS.items() if q == c or q in aliases}
    out = []
    for s in services:
        name = norm(s["name"])
        code = norm(s["code"])
        if q in name or q == code:
            out.append(s)
            continue
        if any(c in name for c in canon_hits):
            out.append(s)
    seen, uniq = set(), []
    for x in out:
        if x["code"] in seen:
            continue
        seen.add(x["code"])
        uniq.append(x)
    return uniq


def _collect_price_nodes(rows: List[Dict[str, Any]], country: str, node: Any, hint: Optional[str] = None) -> None:
    if isinstance(node, dict):
        price = None
        for k in ("cost", "price", "activationCost", "activation_cost"):
            if k in node:
                price = node.get(k)
                break
        if price is not None:
            pid = node.get("providerId") or node.get("provider_id")
            pname = node.get("providerName") or node.get("provider_name") or node.get("provider") or node.get("operator")
            if pid is None and hint and hint.isdigit():
                pid = hint
            if pname is None and hint and not hint.isdigit():
                pname = hint
            rows.append({"country": country, "price": str(price), "pid": pid, "pname": pname})
        for k, v in node.items():
            if isinstance(v, (dict, list)):
                _collect_price_nodes(rows, country, v, str(k))
    elif isinstance(node, list):
        for v in node:
            _collect_price_nodes(rows, country, v, hint)


def parse_prices(
    payload: Any,
    service_code: str,
    service_name: str,
    countries: Dict[str, Dict[str, Optional[str]]],
    lang: str,
) -> List[PriceOption]:
    data = payload["data"] if isinstance(payload, dict) and isinstance(payload.get("data"), (dict, list)) else payload
    rows: List[Dict[str, Any]] = []
    if isinstance(data, dict):
        for c, v in data.items():
            if str(c).lower() in {"status", "success", "message", "error"}:
                continue
            node = v.get(service_code) if isinstance(v, dict) and service_code in v else v
            _collect_price_nodes(rows, str(c), node)
    elif isinstance(data, list):
        for v in data:
            if not isinstance(v, dict):
                continue
            cc = str(v.get("country") or v.get("countryCode") or "")
            if cc:
                _collect_price_nodes(rows, cc, v)

    dedupe, out = set(), []
    for r in rows:
        cc, price = str(r["country"]).strip(), str(r["price"]).strip()
        if not cc or not price:
            continue
        key = (cc, str(r.get("pid") or ""), str(r.get("pname") or ""), price)
        if key in dedupe:
            continue
        dedupe.add(key)
        c = countries.get(cc, {})
        out.append(
            PriceOption(
                service_code=service_code,
                service_name=service_name,
                country_code=cc,
                country_name=str(c.get("name") or tt(lang, "fallback_country")),
                country_iso2=c.get("iso2"),
                provider_id=str(r.get("pid")) if r.get("pid") else None,
                provider_name=str(r.get("pname")) if r.get("pname") else None,
                price=price,
                base_price=price,
            )
        )
    out.sort(key=lambda x: (float(x.price) if re.match(r"^\d+(\.\d+)?$", x.price) else 999999.0, x.country_name))
    return out


def apply_role_prices(opts: List[PriceOption], role: str, profit_pct: Decimal) -> List[PriceOption]:
    out: List[PriceOption] = []
    mult = Decimal("1") + (profit_pct / Decimal("100"))
    for x in opts:
        base = dec(x.base_price or x.price, "0")
        final = base
        if role == ROLE_USER:
            final = (base * mult).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        out.append(
            PriceOption(
                service_code=x.service_code,
                service_name=x.service_name,
                country_code=x.country_code,
                country_name=x.country_name,
                country_iso2=x.country_iso2,
                provider_id=x.provider_id,
                provider_name=x.provider_name,
                price=money(final),
                base_price=money(base),
            )
        )
    return out


async def ensure_user(update: Update, db: Any) -> Tuple[int, int, str, str, bool]:
    user = update.effective_user
    chat = update.effective_chat
    if user is None or chat is None:
        raise RuntimeError("missing user/chat")
    username = user.username or ""
    full_name = user.full_name or ""
    old = await adb(db.get, user.id)
    if old:
        forced_role = ROLE_ADMIN if user.id == ADMIN_USER_ID else None
        row = await adb(
            db.upsert,
            user.id,
            chat.id,
            lang=None,
            role=forced_role,
            username=username,
            full_name=full_name,
        )
        return user.id, chat.id, lang_from_code(row.get("lang")), role_of(row), False
    lg = lang_from_code(user.language_code)
    initial_role = ROLE_ADMIN if user.id == ADMIN_USER_ID else ROLE_PENDING
    row = await adb(
        db.upsert,
        user.id,
        chat.id,
        lg,
        role=initial_role,
        username=username,
        full_name=full_name,
    )
    return user.id, chat.id, lg, role_of(row), True


async def cached_services(context: ContextTypes.DEFAULT_TYPE) -> List[Dict[str, str]]:
    b = context.application.bot_data
    c = b.get("svc_cache")
    now = time.time()
    if c and now - c["ts"] < 600:
        return c["items"]
    api: TemplineAPI = b["api"]
    items = parse_services(await api.call("getServicesList"))
    b["svc_cache"] = {"ts": now, "items": items, "map": {s["code"]: s["name"] for s in items}}
    return items


async def cached_countries(context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Dict[str, Optional[str]]]:
    b = context.application.bot_data
    c = b.get("country_cache")
    now = time.time()
    if c and now - c["ts"] < 1800:
        return c["items"]
    api: TemplineAPI = b["api"]
    items = parse_countries(await api.call("getCountries"))
    b["country_cache"] = {"ts": now, "items": items}
    return items


def svc_keyboard(items: List[Dict[str, str]], page: int, lang: str, mode: str) -> InlineKeyboardMarkup:
    start, end = page * PAGE_SIZE, (page + 1) * PAGE_SIZE
    rows = []
    for s in items[start:end]:
        rows.append([InlineKeyboardButton(f"📱 {s['name']}", callback_data=f"sv:{s['code']}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(tt(lang, "prev"), callback_data=f"sp:{mode}:{page - 1}"))
    if end < len(items):
        nav.append(InlineKeyboardButton(tt(lang, "next"), callback_data=f"sp:{mode}:{page + 1}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(rows)


def price_keyboard(opts: List[PriceOption], page: int, lang: str) -> InlineKeyboardMarkup:
    start, end = page * PAGE_SIZE, (page + 1) * PAGE_SIZE
    rows = []
    for i in range(start, min(end, len(opts))):
        rows.append([InlineKeyboardButton(opts[i].label, callback_data=f"by:{opts[i].service_code}:{i}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(tt(lang, "prev"), callback_data=f"pp:{opts[0].service_code}:{page - 1}"))
    if end < len(opts):
        nav.append(InlineKeyboardButton(tt(lang, "next"), callback_data=f"pp:{opts[0].service_code}:{page + 1}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(rows)


async def show_service_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    lang: str,
    items: List[Dict[str, str]],
    page: int,
    mode: str,
    title: str,
    role: str = ROLE_USER,
) -> None:
    context.user_data[f"svc_{mode}"] = items
    pages = (len(items) - 1) // PAGE_SIZE + 1 if items else 1
    text = f"📋 *{md(title)}*\n{md(f'Page {page + 1}/{pages}')}"
    if not items:
        text = f"⚠️ {md(tt(lang, 'services_empty' if mode == 'all' else 'search_empty'))}"
        await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=main_menu(lang, role))
        return
    await update.effective_message.reply_text(
        text=text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=svc_keyboard(items, page, lang, mode),
    )


async def show_prices(query, context: ContextTypes.DEFAULT_TYPE, lang: str, service_code: str, page: int = 0) -> None:
    b = context.application.bot_data
    api: TemplineAPI = b["api"]
    db = b["db"]
    name = b.get("svc_cache", {}).get("map", {}).get(service_code, service_code)
    countries = await cached_countries(context)
    payload = None
    for a in ("getPricesV3", "getPricesV2", "getPrices"):
        try:
            payload = await api.call(a, service=service_code)
            if payload:
                break
        except Exception:
            continue
    opts = parse_prices(payload, service_code, name, countries, lang) if payload else []
    user_id = query.from_user.id if query and query.from_user else 0
    user_row = await adb(db.get, user_id) if user_id else None
    role = role_of(user_row)
    profit_pct = await adb(db.get_profit_percent) if hasattr(db, "get_profit_percent") else Decimal("20")
    opts = apply_role_prices(opts, role, profit_pct)
    if not opts:
        await query.edit_message_text(f"⚠️ {md(tt(lang, 'prices_empty'))}", parse_mode=ParseMode.MARKDOWN_V2)
        return
    context.user_data[f"price_{service_code}"] = opts
    pages = (len(opts) - 1) // PAGE_SIZE + 1
    text = f"🌍 *{md(tt(lang, 'prices', service=name))}*\n{md(f'Page {page + 1}/{pages}')}"
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=price_keyboard(opts, page, lang))


async def start_poll_task(app: Application, aid: str) -> None:
    db = app.bot_data["db"]
    api: TemplineAPI = app.bot_data["api"]
    tasks: Dict[str, asyncio.Task] = app.bot_data["tasks"]

    async def run() -> None:
        while True:
            await asyncio.sleep(POLL_SECONDS)
            act = await adb(db.get_activation, aid)
            if not act:
                break
            if act.get("status") != "active":
                break
            created_at = int(act.get("created_at") or time.time())
            if int(time.time()) - created_at >= MAX_MONITOR_SECONDS:
                await adb(db.set_activation_status, aid, "expired")
                refund = await adb(db.refund_activation_if_needed, aid)
                if refund:
                    user_row = await adb(db.get, int(act.get("user_id"))) or {}
                    lang = lang_from_code(user_row.get("lang"))
                    await app.bot.send_message(
                        int(act.get("chat_id")),
                        md(tt(lang, "otp_timeout_refund", amount=refund.get("amount"))),
                        parse_mode=ParseMode.MARKDOWN_V2,
                        reply_markup=main_menu(lang, role_of(user_row)),
                    )
                break

            user_id = int(act.get("user_id"))
            chat_id = int(act.get("chat_id"))
            user_row = await adb(db.get, user_id) or {}
            lang = lang_from_code(user_row.get("lang"))
            try:
                st, val = parse_status(await api.call("getStatus", id=aid))
            except Exception:
                continue
            if st == "WAIT":
                continue
            if st == "OK" and val:
                otp = str(val)
                kb = InlineKeyboardMarkup(
                    [
                        [copy_button(tt(lang, "copy_otp"), otp, f"cp:otp:{user_id}")],
                        [InlineKeyboardButton(tt(lang, "home"), callback_data="hm")],
                    ]
                )
                msg = tt(lang, "otp", otp=otp)
                await app.bot.send_message(
                    chat_id,
                    md(msg).replace(md(otp), cd(otp)),
                    parse_mode=ParseMode.MARKDOWN_V2,
                    reply_markup=kb,
                )
                try:
                    await api.call("setStatus", id=aid, status=6)
                except Exception:
                    pass
                await adb(db.set_activation_status, aid, "otp_received", otp)
                break
            if st == "CANCEL":
                await adb(db.set_activation_status, aid, "cancelled")
                refund = await adb(db.refund_activation_if_needed, aid)
                txt = tt(lang, "cancelled")
                if refund:
                    txt = f"{txt}\n{tt(lang, 'refund_done', amount=refund.get('amount'))}"
                await app.bot.send_message(
                    chat_id,
                    md(txt),
                    parse_mode=ParseMode.MARKDOWN_V2,
                    reply_markup=main_menu(lang, role_of(user_row)),
                )
                break
            if st == "ERROR":
                await adb(db.set_activation_status, aid, "error")
                refund = await adb(db.refund_activation_if_needed, aid)
                txt = api_error(lang, val or "UNKNOWN")
                if refund:
                    txt = f"{txt}\n{tt(lang, 'refund_done', amount=refund.get('amount'))}"
                await app.bot.send_message(
                    chat_id,
                    md(txt),
                    parse_mode=ParseMode.MARKDOWN_V2,
                    reply_markup=main_menu(lang, role_of(user_row)),
                )
                break
        tasks.pop(str(aid), None)

    cur = tasks.get(str(aid))
    if cur and not cur.done():
        cur.cancel()
    tasks[str(aid)] = asyncio.create_task(run())


def approval_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(tt("en", "approve_user"), callback_data=f"ua:{user_id}:{ROLE_USER}"),
                InlineKeyboardButton(tt("en", "approve_super"), callback_data=f"ua:{user_id}:{ROLE_SUPER}"),
            ],
            [InlineKeyboardButton(tt("en", "approve_cancel"), callback_data=f"ua:{user_id}:{ROLE_BLOCKED}")],
        ]
    )


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(tt("en", "admin_pending"), callback_data="ad:pending")],
            [InlineKeyboardButton(tt("en", "admin_broadcast"), callback_data="ad:broadcast")],
            [InlineKeyboardButton(tt("en", "admin_payments"), callback_data="ad:payments")],
            [InlineKeyboardButton(tt("en", "admin_profit"), callback_data="ad:profit")],
            [InlineKeyboardButton(tt("en", "admin_stats"), callback_data="ad:stats")],
        ]
    )


def deposit_review_keyboard(dep_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(tt("en", "deposit_approve"), callback_data=f"dp:ap:{dep_id}"),
                InlineKeyboardButton(tt("en", "deposit_reject"), callback_data=f"dp:rj:{dep_id}"),
            ]
        ]
    )


async def notify_admin_new_user(context: ContextTypes.DEFAULT_TYPE, row: Dict[str, Any]) -> None:
    db = context.application.bot_data["db"]
    if not row:
        return
    if bool(row.get("approval_notified")):
        return
    uid = int(row["user_id"])
    name = row.get("full_name") or row.get("username") or f"user_{uid}"
    lang = row.get("lang") or "en"
    text = tt("en", "new_user_alert", name=name, user_id=uid, user_lang=lang)
    try:
        await context.bot.send_message(
            ADMIN_USER_ID,
            md(text),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=approval_keyboard(uid),
        )
        await adb(db.mark_approval_notified, uid)
    except Exception as e:
        logger.warning("failed to notify admin for new user %s: %s", uid, e)


async def h_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = context.application.bot_data["db"]
    user_id, _, lang, role, is_new = await ensure_user(update, db)
    row = await adb(db.get, user_id) or {}
    role = role_of(row) if row else role
    logger.info("Received /start from user_id=%s", update.effective_user.id if update.effective_user else None)
    if role == ROLE_PENDING and (is_new or not bool(row.get("approval_notified"))):
        await notify_admin_new_user(context, row)
    if role == ROLE_BLOCKED:
        await safe_reply_markdown(update.effective_message, md(tt(lang, "rejected_user")))
        return
    if role == ROLE_PENDING:
        await safe_reply_markdown(update.effective_message, md(tt(lang, "pending_approval")))
        await safe_reply_markdown(update.effective_message, md(tt(lang, "lang_pick")), reply_markup=lang_keyboard())
        return
    await safe_reply_markdown(
        update.effective_message,
        md(tt(lang, "welcome")),
        reply_markup=main_menu(lang, role),
    )
    await safe_reply_markdown(update.effective_message, md(tt(lang, "lang_pick")), reply_markup=lang_keyboard())


async def h_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = context.application.bot_data["db"]
    await ensure_user(update, db)
    row = await adb(db.get, update.effective_user.id) or {}
    lang = lang_from_code(row.get("lang"))
    await safe_reply_markdown(update.effective_message, md(tt(lang, "lang_pick")), reply_markup=lang_keyboard())


async def cb_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not q.message or not q.from_user:
        return
    await safe_answer_callback(q)
    db = context.application.bot_data["db"]
    lg = q.data.split(":", 1)[1] if ":" in q.data else "en"
    if lg not in LANGS:
        lg = "en"
    await adb(db.set_lang, q.from_user.id, q.message.chat_id, lg)
    row = await adb(db.get, q.from_user.id) or {}
    await q.message.reply_text(
        md(tt(lg, "lang_saved")),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=main_menu(lg, role_of(row)),
    )


async def h_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = context.application.bot_data["db"]
    _, _, lang, role, _ = await ensure_user(update, db)
    if not context.application.bot_data.get("svc_cache"):
        await update.effective_message.reply_text(
            md(tt(lang, "load_services")),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=main_menu(lang, role),
        )
    try:
        items = await cached_services(context)
    except Exception:
        await update.effective_message.reply_text(
            md(tt(lang, "generic_fail")),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=main_menu(lang, role),
        )
        return
    await show_service_list(update, context, lang, items, 0, "all", tt(lang, "services"), role)


async def h_search_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    db = context.application.bot_data["db"]
    _, _, lang, _, _ = await ensure_user(update, db)
    await update.effective_message.reply_text(
        md(tt(lang, "search_prompt")),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=ForceReply(selective=True),
    )
    return SEARCH_STATE


async def h_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    db = context.application.bot_data["db"]
    _, _, lang, role, _ = await ensure_user(update, db)
    query = (update.effective_message.text or "").strip()
    if not query:
        await update.effective_message.reply_text(
            md(tt(lang, "search_empty")),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=main_menu(lang, role),
        )
        return ConversationHandler.END
    try:
        items = await cached_services(context)
    except Exception:
        await update.effective_message.reply_text(
            md(tt(lang, "generic_fail")),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=main_menu(lang, role),
        )
        return ConversationHandler.END
    matched = match_services(query, items)
    if not matched:
        await update.effective_message.reply_text(
            md(tt(lang, "search_empty")),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=main_menu(lang, role),
        )
        return ConversationHandler.END
    await show_service_list(update, context, lang, matched, 0, "search", tt(lang, "services"), role)
    return ConversationHandler.END


async def cb_service_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not q.from_user:
        return
    await safe_answer_callback(q)
    db: DB = context.application.bot_data["db"]
    row = await adb(db.get, q.from_user.id) or {}
    lang = lang_from_code(row.get("lang"))
    try:
        _, mode, p = q.data.split(":")
        page = max(0, int(p))
    except Exception:
        await safe_answer_callback(q, tt(lang, "expired"), show_alert=True)
        return
    items = context.user_data.get(f"svc_{mode}") or []
    if not items:
        await safe_answer_callback(q, tt(lang, "expired"), show_alert=True)
        return
    pages = (len(items) - 1) // PAGE_SIZE + 1
    text = f"📋 *{md(tt(lang, 'services'))}*\n{md(f'Page {page + 1}/{pages}')}"
    await q.edit_message_text(text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=svc_keyboard(items, page, lang, mode))


async def cb_service_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not q.from_user:
        return
    await safe_answer_callback(q)
    db = context.application.bot_data["db"]
    row = await adb(db.get, q.from_user.id) or {}
    lang = lang_from_code(row.get("lang"))
    service_code = q.data.split(":", 1)[1] if ":" in q.data else ""
    if not service_code:
        await safe_answer_callback(q, tt(lang, "expired"), show_alert=True)
        return
    await q.edit_message_text(md(tt(lang, "load_prices")), parse_mode=ParseMode.MARKDOWN_V2)
    try:
        await show_prices(q, context, lang, service_code, 0)
    except Exception:
        await q.message.reply_text(
            md(tt(lang, "generic_fail")),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=main_menu(lang, role_of(row)),
        )


async def cb_price_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not q.from_user:
        return
    await safe_answer_callback(q)
    db: DB = context.application.bot_data["db"]
    row = await adb(db.get, q.from_user.id) or {}
    lang = lang_from_code(row.get("lang"))
    try:
        _, code, p = q.data.split(":")
        page = max(0, int(p))
    except Exception:
        await safe_answer_callback(q, tt(lang, "expired"), show_alert=True)
        return
    opts = context.user_data.get(f"price_{code}") or []
    if not opts:
        await safe_answer_callback(q, tt(lang, "expired"), show_alert=True)
        return
    pages = (len(opts) - 1) // PAGE_SIZE + 1
    text = f"🌍 *{md(tt(lang, 'prices', service=opts[0].service_name))}*\n{md(f'Page {page + 1}/{pages}')}"
    await q.edit_message_text(text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=price_keyboard(opts, page, lang))


async def cb_buy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not q.from_user or not q.message:
        return
    await safe_answer_callback(q)
    db = context.application.bot_data["db"]
    api: TemplineAPI = context.application.bot_data["api"]
    row = await adb(db.get, q.from_user.id) or {}
    lang = lang_from_code(row.get("lang"))
    role = role_of(row)

    try:
        _, code, idx_raw = q.data.split(":")
        idx = int(idx_raw)
    except Exception:
        await safe_answer_callback(q, tt(lang, "expired"), show_alert=True)
        return
    opts = context.user_data.get(f"price_{code}") or []
    if idx < 0 or idx >= len(opts):
        await safe_answer_callback(q, tt(lang, "expired"), show_alert=True)
        return

    opt: PriceOption = opts[idx]
    charge = dec(opt.price, "0")
    base_cost = dec(opt.base_price or opt.price, "0")
    deducted = False
    if role in {ROLE_USER, ROLE_SUPER}:
        bal = await adb(db.adjust_balance, q.from_user.id, -charge, require_non_negative=True)
        if bal is None:
            await safe_answer_callback(q, tt(lang, "insufficient_wallet"), show_alert=True)
            return
        deducted = True
    await q.edit_message_text(md(tt(lang, "wait")), parse_mode=ParseMode.MARKDOWN_V2)
    try:
        buy_args: Dict[str, Any] = {
            "service": opt.service_code,
            "country": opt.country_code,
            "providerIds": opt.provider_id,
        }
        if base_cost > 0:
            buy_args["fixPrice"] = money(base_cost)
        payload = await api.call("getNumber", **buy_args)
    except Exception as e:
        logger.warning("getNumber failed (buy) user=%s args=%s err=%s", q.from_user.id, buy_args, e)
        if deducted:
            await adb(db.adjust_balance, q.from_user.id, charge)
        await q.message.reply_text(md(tt(lang, "generic_fail")), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=main_menu(lang, role))
        return
    aid, phone, err = parse_number(payload)
    if err or not aid or not phone:
        if deducted:
            await adb(db.adjust_balance, q.from_user.id, charge)
        await q.message.reply_text(md(api_error(lang, err or "UNKNOWN")), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=main_menu(lang, role))
        return

    await adb(
        db.add_activation,
        q.from_user.id,
        q.message.chat_id,
        aid,
        opt.service_code,
        opt.country_code,
        opt.provider_id,
        phone,
        base_price=base_cost,
        charged_price=charge if role in {ROLE_USER, ROLE_SUPER} else 0,
    )
    await adb(db.set_activation, q.from_user.id, q.message.chat_id, aid, opt.service_code, opt.country_code, opt.provider_id, phone)

    provider = opt.provider_name or tt(lang, "fallback_provider")
    countries = context.application.bot_data.get("country_cache", {}).get("items") or {}
    cinfo = countries.get(str(opt.country_code), {}) if isinstance(countries, dict) else {}
    resolved_name = str(
        cinfo.get("name")
        or opt.country_name
        or tt(lang, "fallback_country")
    ).strip()
    resolved_iso2 = (
        cinfo.get("iso2")
        or opt.country_iso2
        or country_name_to_iso2(resolved_name)
    )
    country_display = f"{to_flag(resolved_iso2)} {resolved_name} ({opt.country_code})"

    text = tt(lang, "number", phone=phone, aid=aid, country=country_display, provider=provider)
    text = text.replace(phone, f"{phone}").replace(aid, f"{aid}")
    provider_token = opt.provider_id if opt.provider_id else "none"
    another_cb = f"an:{opt.service_code}:{opt.country_code}:{provider_token}"
    kb = InlineKeyboardMarkup(
        [
            [copy_button(tt(lang, "copy_num"), phone, f"cp:num:{q.from_user.id}")],
            [InlineKeyboardButton(another_one_label(lang), callback_data=another_cb)],
            [InlineKeyboardButton(tt(lang, "cancel"), callback_data=f"cx:{aid}")],
        ]
    )
    await q.message.reply_text(
        md(text).replace(md(phone), cd(phone)).replace(md(aid), cd(aid)),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=kb,
    )
    await start_poll_task(context.application, aid)


async def cb_another(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not q.from_user or not q.message:
        return
    await safe_answer_callback(q)
    db = context.application.bot_data["db"]
    api: TemplineAPI = context.application.bot_data["api"]
    row = await adb(db.get, q.from_user.id) or {}
    lang = lang_from_code(row.get("lang"))
    role = role_of(row)

    try:
        _, service_code, country_code, provider_token = q.data.split(":", 3)
    except Exception:
        await safe_answer_callback(q, tt(lang, "expired"), show_alert=True)
        return

    provider_id: Optional[str] = None if provider_token in {"", "none", "null"} else provider_token

    await q.message.reply_text(
        md(tt(lang, "wait")),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    price_map: Dict[Tuple[str, str, str], PriceOption] = {}
    for v in (context.user_data.get(f"price_{service_code}") or []):
        k = (str(v.service_code), str(v.country_code), str(v.provider_id or "none"))
        price_map[k] = v
    opt = price_map.get((service_code, country_code, provider_token))
    if opt is None:
        opt = price_map.get((service_code, country_code, "none"))
    charge = dec(opt.price, "0") if opt else Decimal("0")
    base_cost = dec(opt.base_price or opt.price, "0") if opt else Decimal("0")
    deducted = False
    if role in {ROLE_USER, ROLE_SUPER}:
        bal = await adb(db.adjust_balance, q.from_user.id, -charge, require_non_negative=True)
        if bal is None:
            await safe_answer_callback(q, tt(lang, "insufficient_wallet"), show_alert=True)
            return
        deducted = True
    try:
        buy_args: Dict[str, Any] = {
            "service": service_code,
            "country": country_code,
            "providerIds": provider_id,
        }
        if base_cost > 0:
            buy_args["fixPrice"] = money(base_cost)
        payload = await api.call("getNumber", **buy_args)
    except Exception as e:
        logger.warning("getNumber failed (another) user=%s args=%s err=%s", q.from_user.id, buy_args, e)
        if deducted:
            await adb(db.adjust_balance, q.from_user.id, charge)
        await q.message.reply_text(md(tt(lang, "generic_fail")), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=main_menu(lang, role))
        return

    aid, phone, err = parse_number(payload)
    if err or not aid or not phone:
        if deducted:
            await adb(db.adjust_balance, q.from_user.id, charge)
        await q.message.reply_text(md(api_error(lang, err or "UNKNOWN")), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=main_menu(lang, role))
        return

    await adb(
        db.add_activation,
        q.from_user.id,
        q.message.chat_id,
        aid,
        service_code,
        country_code,
        provider_id,
        phone,
        base_price=base_cost,
        charged_price=charge if role in {ROLE_USER, ROLE_SUPER} else 0,
    )
    await adb(db.set_activation, q.from_user.id, q.message.chat_id, aid, service_code, country_code, provider_id, phone)

    countries = context.application.bot_data.get("country_cache", {}).get("items") or {}
    cinfo = countries.get(str(country_code), {}) if isinstance(countries, dict) else {}
    resolved_name = str(cinfo.get("name") or tt(lang, "fallback_country")).strip()
    resolved_iso2 = cinfo.get("iso2") or country_name_to_iso2(resolved_name)
    country_display = f"{to_flag(resolved_iso2)} {resolved_name} ({country_code})"
    provider = f"Provider {provider_id}" if provider_id else tt(lang, "fallback_provider")

    text = tt(lang, "number", phone=phone, aid=aid, country=country_display, provider=provider)
    provider_token_new = provider_id if provider_id else "none"
    another_cb = f"an:{service_code}:{country_code}:{provider_token_new}"
    kb = InlineKeyboardMarkup(
        [
            [copy_button(tt(lang, "copy_num"), phone, f"cp:num:{q.from_user.id}")],
            [InlineKeyboardButton(another_one_label(lang), callback_data=another_cb)],
            [InlineKeyboardButton(tt(lang, "cancel"), callback_data=f"cx:{aid}")],
        ]
    )
    await q.message.reply_text(md(text).replace(md(phone), cd(phone)).replace(md(aid), cd(aid)), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)
    await start_poll_task(context.application, aid)


async def h_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = context.application.bot_data["db"]
    _, _, lang, role, _ = await ensure_user(update, db)
    if role in {ROLE_USER, ROLE_SUPER}:
        bal = money(await adb(db.get_balance, update.effective_user.id))
        await update.effective_message.reply_text(
            md(tt(lang, "wallet", balance=bal)),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=main_menu(lang, role),
        )
        return
    api: TemplineAPI = context.application.bot_data["api"]
    try:
        bal, err = parse_balance(await api.call("getBalance"))
    except Exception:
        bal, err = None, "UNKNOWN"
    if err or bal is None:
        await update.effective_message.reply_text(
            md(api_error(lang, err or "UNKNOWN")),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=main_menu(lang, role),
        )
        return
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(tt(lang, "refresh_bal"), callback_data="br")]])
    await update.effective_message.reply_text(md(tt(lang, "bal", balance=bal)), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)


async def cb_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not q.from_user:
        return
    await safe_answer_callback(q)
    db = context.application.bot_data["db"]
    row = await adb(db.get, q.from_user.id) or {}
    lang = lang_from_code(row.get("lang"))
    role = role_of(row)
    if role in {ROLE_USER, ROLE_SUPER}:
        bal = money(await adb(db.get_balance, q.from_user.id))
        await q.message.reply_text(
            md(tt(lang, "wallet", balance=bal)),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=main_menu(lang, role),
        )
        return
    api: TemplineAPI = context.application.bot_data["api"]
    try:
        bal, err = parse_balance(await api.call("getBalance"))
    except Exception:
        bal, err = None, "UNKNOWN"
    if err or bal is None:
        await q.message.reply_text(md(api_error(lang, err or "UNKNOWN")), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=main_menu(lang, role))
        return
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(tt(lang, "refresh_bal"), callback_data="br")]])
    await q.message.reply_text(md(tt(lang, "bal", balance=bal)), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)


async def cancel_core(context: ContextTypes.DEFAULT_TYPE, aid: str, user_id: Optional[int] = None) -> None:
    db = context.application.bot_data["db"]
    api: TemplineAPI = context.application.bot_data["api"]
    tasks: Dict[str, asyncio.Task] = context.application.bot_data["tasks"]
    try:
        await api.call("setStatus", id=aid, status=8)
    except Exception:
        pass
    tsk = tasks.get(str(aid))
    if tsk and not tsk.done():
        tsk.cancel()
        tasks.pop(str(aid), None)
    await adb(db.set_activation_status, str(aid), "cancelled")
    refund = await adb(db.refund_activation_if_needed, str(aid))
    if user_id is not None:
        row = await adb(db.get, user_id) or {}
        if str(row.get("activation_id") or "") == str(aid):
            await adb(db.clear_activation, user_id)
        if refund and int(refund.get("user_id") or 0) == int(user_id):
            lang = lang_from_code(row.get("lang"))
            try:
                await context.bot.send_message(
                    row.get("chat_id") or user_id,
                    md(tt(lang, "refund_done", amount=refund.get("amount"))),
                    parse_mode=ParseMode.MARKDOWN_V2,
                    reply_markup=main_menu(lang, role_of(row)),
                )
            except Exception:
                pass


async def cb_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not q.from_user:
        return
    db = context.application.bot_data["db"]
    row = await adb(db.get, q.from_user.id) or {}
    lang = lang_from_code(row.get("lang"))
    aid = q.data.split(":", 1)[1] if ":" in q.data else None
    if not aid:
        await safe_answer_callback(q, tt(lang, "expired"), show_alert=True)
        return

    act = await adb(db.get_activation, str(aid))
    if not act:
        legacy_aid = row.get("activation_id")
        if str(legacy_aid or "") == str(aid) and int(row.get("polling") or 0) == 1:
            act = {
                "activation_id": str(aid),
                "user_id": q.from_user.id,
                "chat_id": q.message.chat_id if q.message else row.get("chat_id"),
                "status": "active",
                "created_at": row.get("activation_started_at"),
                "activation_started_at": row.get("activation_started_at"),
            }
        else:
            await safe_answer_callback(q, tt(lang, "no_active"), show_alert=True)
            return

    if int(act.get("user_id") or 0) != q.from_user.id:
        await safe_answer_callback(q, tt(lang, "no_active"), show_alert=True)
        return

    status = str(act.get("status") or "active").lower()
    if status == "otp_received":
        await safe_answer_callback(q, otp_received_cancel_message(lang), show_alert=True)
        return
    if status != "active":
        await safe_answer_callback(q, tt(lang, "no_active"), show_alert=True)
        return

    if not can_cancel_activation(act):
        remaining = cancel_remaining_seconds(act)
        await safe_answer_callback(q, cancel_lock_message(lang, remaining), show_alert=True)
        return
    await safe_answer_callback(q)
    await cancel_core(context, str(aid), user_id=q.from_user.id)
    await q.message.reply_text(
        md(tt(lang, "cancelled")),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=main_menu(lang, role_of(row)),
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    db = context.application.bot_data["db"]
    _, _, lang, role, _ = await ensure_user(update, db)
    act = await adb(db.latest_active_activation_for_user, update.effective_user.id)
    if not act:
        row = await adb(db.get, update.effective_user.id) or {}
        aid = row.get("activation_id")
        if aid and int(row.get("polling") or 0) == 1:
            act = {
                "activation_id": str(aid),
                "user_id": update.effective_user.id,
                "status": "active",
                "created_at": row.get("activation_started_at"),
                "activation_started_at": row.get("activation_started_at"),
            }
    if not act:
        await update.effective_message.reply_text(
            md(tt(lang, "no_active")),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=main_menu(lang, role),
        )
        return ConversationHandler.END
    if not can_cancel_activation(act):
        remaining = cancel_remaining_seconds(act)
        await update.effective_message.reply_text(
            md(cancel_lock_message(lang, remaining)),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=main_menu(lang, role),
        )
        return ConversationHandler.END
    await cancel_core(context, str(act["activation_id"]), user_id=update.effective_user.id)
    await update.effective_message.reply_text(
        md(tt(lang, "cancelled")),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=main_menu(lang, role),
    )
    return ConversationHandler.END


async def cb_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not q.from_user:
        return
    await safe_answer_callback(q)
    db = context.application.bot_data["db"]
    row = await adb(db.get, q.from_user.id) or {}
    lang = lang_from_code(row.get("lang"))
    await q.message.reply_text(
        md(tt(lang, "welcome")),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=main_menu(lang, role_of(row)),
    )


async def cb_copy_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q:
        return
    await safe_answer_callback(q, "Copy button not supported on this Telegram version.", show_alert=True)


async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = context.application.bot_data["db"]
    _, _, lang, role, _ = await ensure_user(update, db)
    if await process_text_state(update, context):
        return
    action = detect_action(update.effective_message.text or "")
    if action == "select":
        await h_select(update, context)
        return
    if action == "search":
        await h_search_entry(update, context)
        return
    if action == "balance":
        await h_balance(update, context)
        return
    if action == "wallet":
        await h_balance(update, context)
        return
    if action == "deposit":
        await h_deposit_entry(update, context)
        return
    if action == "admin_panel":
        await h_admin_panel(update, context)
        return
    await update.effective_message.reply_text(
        md(tt(lang, "unknown")),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=main_menu(lang, role),
    )


def is_admin(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id == ADMIN_USER_ID)


def _clear_admin_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("admin_state", None)


def _clear_deposit_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("dep_state", None)
    context.user_data.pop("dep_id", None)
    context.user_data.pop("dep_amount", None)
    context.user_data.pop("dep_txid", None)


async def gate_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user:
        logger.info("Incoming message update from user_id=%s", update.effective_user.id)
    if not update.effective_user or not update.effective_message:
        return
    db = context.application.bot_data["db"]
    row = await adb(db.get, update.effective_user.id)
    if not row:
        txt = update.effective_message.text or ""
        if txt.startswith("/start") or txt.startswith("/language"):
            return
        lang = lang_from_code(update.effective_user.language_code if update.effective_user else None)
        await update.effective_message.reply_text(md(tt(lang, "pending_approval")), parse_mode=ParseMode.MARKDOWN_V2)
        raise ApplicationHandlerStop
    role = role_of(row)
    lang = lang_from_code(row.get("lang"))
    txt = update.effective_message.text or ""
    if role == ROLE_BLOCKED:
        await update.effective_message.reply_text(md(tt(lang, "rejected_user")), parse_mode=ParseMode.MARKDOWN_V2)
        raise ApplicationHandlerStop
    if role == ROLE_PENDING:
        if txt.startswith("/start") or txt.startswith("/language"):
            return
        await update.effective_message.reply_text(md(tt(lang, "pending_approval")), parse_mode=ParseMode.MARKDOWN_V2)
        raise ApplicationHandlerStop


async def gate_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not q.from_user:
        return
    logger.info("Incoming callback from user_id=%s data=%s", q.from_user.id, q.data)
    db = context.application.bot_data["db"]
    row = await adb(db.get, q.from_user.id)
    if not row:
        return
    role = role_of(row)
    lang = lang_from_code(row.get("lang"))
    data = q.data or ""
    if role == ROLE_BLOCKED:
        await safe_answer_callback(q, tt(lang, "rejected_user"), show_alert=True)
        raise ApplicationHandlerStop
    if role == ROLE_PENDING and not data.startswith("lg:"):
        await safe_answer_callback(q, tt(lang, "pending_approval"), show_alert=True)
        raise ApplicationHandlerStop


async def cb_user_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not q.from_user:
        return
    if q.from_user.id != ADMIN_USER_ID:
        await safe_answer_callback(q, tt("en", "admin_only"), show_alert=True)
        return
    try:
        _, uid_raw, role = (q.data or "").split(":", 2)
        uid = int(uid_raw)
    except Exception:
        await safe_answer_callback(q, tt("en", "expired"), show_alert=True)
        return
    if role not in {ROLE_USER, ROLE_SUPER, ROLE_BLOCKED}:
        await safe_answer_callback(q, tt("en", "expired"), show_alert=True)
        return
    db = context.application.bot_data["db"]
    await adb(db.set_role, uid, role, approved_by=q.from_user.id)
    await safe_answer_callback(q, tt("en", "role_updated"))
    target = await adb(db.get, uid) or {}
    chat_id = target.get("chat_id")
    if chat_id:
        msg_key = "approved_user" if role == ROLE_USER else "approved_super"
        if role == ROLE_BLOCKED:
            msg_key = "rejected_user"
        lang = lang_from_code(target.get("lang"))
        await context.bot.send_message(
            int(chat_id),
            md(tt(lang, msg_key)),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=main_menu(lang, role_of(target)),
        )
    try:
        await q.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass


async def h_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user:
        return
    if not is_admin(update):
        db = context.application.bot_data["db"]
        row = await adb(db.get, update.effective_user.id) or {}
        lang = lang_from_code(row.get("lang"))
        await update.effective_message.reply_text(md(tt(lang, "admin_only")), parse_mode=ParseMode.MARKDOWN_V2)
        return
    await update.effective_message.reply_text(
        md(tt("en", "admin_panel")),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=admin_panel_keyboard(),
    )


async def cb_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not q.from_user:
        return
    if q.from_user.id != ADMIN_USER_ID:
        await safe_answer_callback(q, tt("en", "admin_only"), show_alert=True)
        return
    db = context.application.bot_data["db"]
    action = (q.data or "").split(":", 1)[1] if ":" in (q.data or "") else ""
    await safe_answer_callback(q)
    if action == "pending":
        items = await adb(db.list_pending_users)
        if not items:
            await q.message.reply_text(md(tt("en", "pending_none")), parse_mode=ParseMode.MARKDOWN_V2)
            return
        for r in items[:20]:
            name = r.get("full_name") or r.get("username") or f"user_{r['user_id']}"
            txt = tt("en", "new_user_alert", name=name, user_id=r["user_id"], user_lang=r.get("lang") or "en")
            await q.message.reply_text(md(txt), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=approval_keyboard(int(r["user_id"])))
        return
    if action == "broadcast":
        context.user_data["admin_state"] = BROADCAST_STATE
        await q.message.reply_text(md(tt("en", "broadcast_prompt")), parse_mode=ParseMode.MARKDOWN_V2)
        return
    if action == "payments":
        context.user_data["admin_state"] = PAYMENT_EDIT_STATE
        settings = await adb(db.get_payment_settings)
        lines = payment_settings_to_lines(settings)
        await q.message.reply_text(md(tt("en", "payment_show", lines=lines)), parse_mode=ParseMode.MARKDOWN_V2)
        await q.message.reply_text(md(tt("en", "payment_prompt")), parse_mode=ParseMode.MARKDOWN_V2)
        return
    if action == "profit":
        context.user_data["admin_state"] = PROFIT_EDIT_STATE
        pct = money(await adb(db.get_profit_percent))
        await q.message.reply_text(md(tt("en", "profit_current", pct=pct)), parse_mode=ParseMode.MARKDOWN_V2)
        await q.message.reply_text(md(tt("en", "profit_prompt")), parse_mode=ParseMode.MARKDOWN_V2)
        return
    if action == "stats":
        s = await adb(db.user_stats)
        text = (
            f"📊 Users\n"
            f"Total: {s.get('total', 0)}\n"
            f"Pending: {s.get('pending', 0)}\n"
            f"User: {s.get('user', 0)}\n"
            f"Super: {s.get('super_user', 0)}\n"
            f"Admin: {s.get('admin', 0)}\n"
            f"Blocked: {s.get('blocked', 0)}"
        )
        await q.message.reply_text(md(text), parse_mode=ParseMode.MARKDOWN_V2)
        return


async def cb_deposit_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not q.from_user:
        return
    if q.from_user.id != ADMIN_USER_ID:
        await safe_answer_callback(q, tt("en", "admin_only"), show_alert=True)
        return
    try:
        _, action, dep_raw = (q.data or "").split(":", 2)
        dep_id = int(dep_raw)
    except Exception:
        await safe_answer_callback(q, tt("en", "expired"), show_alert=True)
        return
    db = context.application.bot_data["db"]
    dep = await adb(db.get_deposit, dep_id)
    if not dep:
        await safe_answer_callback(q, tt("en", "deposit_not_found"), show_alert=True)
        return
    status = "approved" if action == "ap" else "rejected"
    ok = await adb(db.update_deposit_status, dep_id, status, q.from_user.id)
    if not ok:
        await safe_answer_callback(q, tt("en", "deposit_not_found"), show_alert=True)
        return
    await safe_answer_callback(q, tt("en", "deposit_reviewed"))
    usr = await adb(db.get, int(dep["user_id"])) or {}
    lang = lang_from_code(usr.get("lang"))
    key = "deposit_approved_user" if status == "approved" else "deposit_rejected_user"
    try:
        await context.bot.send_message(
            int(usr.get("chat_id") or dep["user_id"]),
            md(tt(lang, key, amount=money(dep.get("amount", "0")))),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=main_menu(lang, role_of(usr)),
        )
    except Exception:
        pass
    try:
        await q.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass


async def h_deposit_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = context.application.bot_data["db"]
    row = await adb(db.get, update.effective_user.id) or {}
    role = role_of(row)
    lang = lang_from_code(row.get("lang"))
    if role not in {ROLE_USER, ROLE_SUPER}:
        return
    _clear_deposit_state(context)
    context.user_data["dep_state"] = DEPOSIT_AMOUNT_STATE
    await update.effective_message.reply_text(
        md(tt(lang, "deposit_prompt_amount", min=money(MIN_DEPOSIT_USD))),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=main_menu(lang, role),
    )


async def h_photo_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    db = context.application.bot_data["db"]
    row = await adb(db.get, update.effective_user.id) or {}
    role = role_of(row)
    lang = lang_from_code(row.get("lang"))
    dep_state = context.user_data.get("dep_state")
    dep_id = context.user_data.get("dep_id")
    if dep_state != DEPOSIT_PROOF_STATE or not dep_id:
        open_dep = await adb(db.latest_open_deposit_for_user, update.effective_user.id)
        if not open_dep:
            return
        dep_id = int(open_dep["id"])
        context.user_data["dep_state"] = DEPOSIT_PROOF_STATE
        context.user_data["dep_id"] = dep_id
    if not dep_id:
        _clear_deposit_state(context)
        return
    txid = (update.effective_message.caption or "").strip() or str(context.user_data.get("dep_txid") or "").strip()
    if not txid:
        await update.effective_message.reply_text(md(tt(lang, "deposit_waiting_txid")), parse_mode=ParseMode.MARKDOWN_V2)
        return
    photos = update.effective_message.photo or []
    if not photos:
        await update.effective_message.reply_text(md(tt(lang, "deposit_waiting_photo")), parse_mode=ParseMode.MARKDOWN_V2)
        return
    file_id = photos[-1].file_id
    await adb(db.set_deposit_proof, int(dep_id), txid, file_id)
    dep = await adb(db.get_deposit, int(dep_id)) or {}
    _clear_deposit_state(context)
    await update.effective_message.reply_text(
        md(tt(lang, "deposit_sent")),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=main_menu(lang, role),
    )
    admin_text = tt("en", "deposit_notify_admin", user_id=update.effective_user.id, amount=money(dep.get("amount", "0")), txid=txid)
    try:
        await context.bot.send_photo(
            chat_id=ADMIN_USER_ID,
            photo=file_id,
            caption=admin_text,
            reply_markup=deposit_review_keyboard(int(dep_id)),
        )
    except Exception:
        await context.bot.send_message(
            ADMIN_USER_ID,
            md(admin_text),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=deposit_review_keyboard(int(dep_id)),
        )


async def process_text_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.effective_user or not update.effective_message:
        return False
    db = context.application.bot_data["db"]
    row = await adb(db.get, update.effective_user.id) or {}
    role = role_of(row)
    lang = lang_from_code(row.get("lang"))
    text = (update.effective_message.text or "").strip()
    if not text:
        return False

    admin_state = context.user_data.get("admin_state")
    if update.effective_user.id == ADMIN_USER_ID and admin_state == BROADCAST_STATE:
        users = await adb(db.list_all_users, include_blocked=False)
        ok = 0
        total = 0
        for u in users:
            chat_id = u.get("chat_id")
            if not chat_id:
                continue
            total += 1
            try:
                await context.bot.send_message(int(chat_id), text)
                ok += 1
            except Exception:
                pass
        _clear_admin_state(context)
        await update.effective_message.reply_text(md(tt("en", "broadcast_done", ok=ok, total=total)), parse_mode=ParseMode.MARKDOWN_V2)
        return True
    if update.effective_user.id == ADMIN_USER_ID and admin_state == PAYMENT_EDIT_STATE:
        parsed: Dict[str, str] = {}
        for line in text.splitlines():
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            parsed[k.strip()] = v.strip()
        if parsed:
            await adb(db.update_payment_settings, parsed)
            await update.effective_message.reply_text(md(tt("en", "payment_saved")), parse_mode=ParseMode.MARKDOWN_V2)
        _clear_admin_state(context)
        return True
    if update.effective_user.id == ADMIN_USER_ID and admin_state == PROFIT_EDIT_STATE:
        try:
            pct = dec(text)
            await adb(db.set_profit_percent, pct)
            await update.effective_message.reply_text(md(tt("en", "profit_saved", pct=money(pct))), parse_mode=ParseMode.MARKDOWN_V2)
        except Exception:
            await update.effective_message.reply_text(md(tt("en", "generic_fail")), parse_mode=ParseMode.MARKDOWN_V2)
        _clear_admin_state(context)
        return True

    dep_state = context.user_data.get("dep_state")
    if dep_state != DEPOSIT_AMOUNT_STATE and dep_state != DEPOSIT_PROOF_STATE:
        open_dep = await adb(db.latest_open_deposit_for_user, update.effective_user.id)
        if open_dep:
            dep_state = DEPOSIT_PROOF_STATE
            context.user_data["dep_state"] = DEPOSIT_PROOF_STATE
            context.user_data["dep_id"] = int(open_dep["id"])
    if dep_state == DEPOSIT_AMOUNT_STATE and role in {ROLE_USER, ROLE_SUPER}:
        amount = dec(text, "-1")
        if amount < MIN_DEPOSIT_USD:
            await update.effective_message.reply_text(md(tt(lang, "deposit_min", min=money(MIN_DEPOSIT_USD))), parse_mode=ParseMode.MARKDOWN_V2)
            return True
        dep_id = await adb(db.create_deposit, update.effective_user.id, amount)
        context.user_data["dep_state"] = DEPOSIT_PROOF_STATE
        context.user_data["dep_id"] = dep_id
        context.user_data["dep_amount"] = money(amount)
        pay = await adb(db.get_payment_settings)
        if not pay.get("telegram_username"):
            admin_row = await adb(db.get, ADMIN_USER_ID) or {}
            admin_un = str(admin_row.get("username") or "").strip()
            if admin_un:
                pay["telegram_username"] = f"@{admin_un}" if not admin_un.startswith("@") else admin_un
        lines = payment_settings_to_lines(pay)
        await update.effective_message.reply_text(md(tt(lang, "deposit_created", amount=money(amount))), parse_mode=ParseMode.MARKDOWN_V2)
        await update.effective_message.reply_text(md(tt(lang, "deposit_payment_info", lines=lines)), parse_mode=ParseMode.MARKDOWN_V2)
        await update.effective_message.reply_text(md(tt(lang, "deposit_send_proof")), parse_mode=ParseMode.MARKDOWN_V2)
        return True
    if dep_state == DEPOSIT_PROOF_STATE and role in {ROLE_USER, ROLE_SUPER}:
        context.user_data["dep_txid"] = text
        await update.effective_message.reply_text(md(tt(lang, "deposit_waiting_photo")), parse_mode=ParseMode.MARKDOWN_V2)
        return True
    return False


def menu_regex(key: str) -> str:
    return "^(" + "|".join(re.escape(tt(lg, key)) for lg in LANGS) + ")$"


async def log_raw_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        uid = update.effective_user.id if update.effective_user else None
        txt = update.effective_message.text if update.effective_message else None
        logger.info(
            "RAW update received: update_id=%s user_id=%s has_message=%s has_callback=%s text=%s",
            getattr(update, "update_id", None),
            uid,
            bool(update.effective_message),
            bool(update.callback_query),
            txt,
        )
    except Exception:
        pass


async def post_init(app: Application) -> None:
    logger.info("Templine bot post-init started (admin_user_id=%s)", ADMIN_USER_ID)
    db = app.bot_data["db"]
    await adb(db.ensure_admin_user, ADMIN_USER_ID)
    await app.bot.set_my_commands(
        [
            BotCommand("start", "Start"),
            BotCommand("language", "Change language"),
            BotCommand("cancel", "Cancel activation"),
            BotCommand("admin", "Admin panel"),
        ]
    )
    db = app.bot_data["db"]
    api: TemplineAPI = app.bot_data["api"]
    try:
        svc_res, ctry_res = await asyncio.gather(
            api.call("getServicesList"),
            api.call("getCountries"),
            return_exceptions=True,
        )
        now = time.time()
        if not isinstance(svc_res, Exception):
            services = parse_services(svc_res)
            app.bot_data["svc_cache"] = {
                "ts": now,
                "items": services,
                "map": {s["code"]: s["name"] for s in services},
            }
        if not isinstance(ctry_res, Exception):
            countries = parse_countries(ctry_res)
            app.bot_data["country_cache"] = {"ts": now, "items": countries}
    except Exception as e:
        logger.warning("cache warm-up failed: %s", e)

    for row in await adb(db.list_active_activations):
        try:
            await start_poll_task(app, str(row["activation_id"]))
        except Exception as e:
            logger.warning("resume polling failed user=%s err=%s", row.get("user_id"), e)
    logger.info("Templine bot post-init complete")


async def post_shutdown(app: Application) -> None:
    tasks: Dict[str, asyncio.Task] = app.bot_data.get("tasks", {})
    for tsk in list(tasks.values()):
        if not tsk.done():
            tsk.cancel()
    api: TemplineAPI = app.bot_data.get("api")
    if api:
        await api.close()


async def app_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = context.error
    if isinstance(err, BadRequest) and _is_stale_query_error(err):
        logger.info("Ignored stale callback error in global handler")
        return
    if isinstance(err, TimedOut):
        logger.warning("Telegram request timed out: %s", err)
        return
    logger.exception("Unhandled bot error: %s", err)


def validate_telegram_token(token: str) -> None:
    if not token or "YOUR_REAL_BOT_TOKEN" in token:
        raise SystemExit("BOT_TOKEN is placeholder. Set real token from BotFather.")
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        r = httpx.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise SystemExit(f"Invalid BOT_TOKEN: {data}")
        logger.info("Telegram auth OK for bot @%s", data.get("result", {}).get("username"))
    except httpx.TimeoutException:
        logger.warning("Telegram token validation skipped: network timeout to api.telegram.org")
    except Exception as e:
        raise SystemExit(f"Telegram token validation failed: {e}")


def clear_telegram_webhook_if_polling(token: str) -> None:
    del_url = f"https://api.telegram.org/bot{token}/deleteWebhook"
    info_url = f"https://api.telegram.org/bot{token}/getWebhookInfo"

    last_err = None
    for i in range(1, 4):
        try:
            r1 = httpx.get(del_url, params={"drop_pending_updates": "true"}, timeout=25)
            r1.raise_for_status()
            logger.info("deleteWebhook attempt %s OK: %s", i, r1.text)
            break
        except Exception as e:
            last_err = e
            logger.warning("deleteWebhook attempt %s failed: %s", i, e)
            time.sleep(2)
    else:
        logger.warning("Could not clear webhook before polling after retries: %s", last_err)

    try:
        r2 = httpx.get(info_url, timeout=25)
        r2.raise_for_status()
        body = r2.json()
        wh_url = ((body or {}).get("result") or {}).get("url")
        pending = ((body or {}).get("result") or {}).get("pending_update_count")
        logger.info("Webhook info after clear: url=%s pending=%s", wh_url or "<empty>", pending)
        if wh_url:
            logger.warning("Webhook still active. Polling may not receive updates until webhook is removed.")
    except Exception as e:
        logger.warning("Could not fetch webhook info: %s", e)


def build_app() -> Application:
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .concurrent_updates(True)
        .get_updates_connect_timeout(10)
        .get_updates_read_timeout(20)
        .get_updates_write_timeout(20)
        .get_updates_pool_timeout(10)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    app.bot_data["db"] = SupabaseRESTDB()
    app.bot_data["api"] = TemplineAPI(API_KEY, BASE_URL)
    app.bot_data["tasks"] = {}

    app.add_handler(TypeHandler(Update, log_raw_update), group=-2)
    app.add_handler(CallbackQueryHandler(gate_user_callback), group=-1)
    app.add_handler(
        MessageHandler(filters.ALL, gate_user_message),
        group=-1,
    )

    search_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.Regex(menu_regex("m_search")),
                h_search_entry,
            )
        ],
        states={SEARCH_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, h_search_input)]},
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", h_start))
    app.add_handler(CommandHandler("language", h_lang))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("admin", h_admin_panel))
    app.add_handler(search_conv)

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(menu_regex("m_select")), h_select))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(menu_regex("m_balance")), h_balance))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, h_photo_state))

    app.add_handler(CallbackQueryHandler(cb_lang, pattern=r"^lg:"))
    app.add_handler(CallbackQueryHandler(cb_user_approval, pattern=r"^ua:"))
    app.add_handler(CallbackQueryHandler(cb_admin_panel, pattern=r"^ad:"))
    app.add_handler(CallbackQueryHandler(cb_deposit_review, pattern=r"^dp:"))
    app.add_handler(CallbackQueryHandler(cb_service_page, pattern=r"^sp:"))
    app.add_handler(CallbackQueryHandler(cb_service_select, pattern=r"^sv:"))
    app.add_handler(CallbackQueryHandler(cb_price_page, pattern=r"^pp:"))
    app.add_handler(CallbackQueryHandler(cb_buy, pattern=r"^by:"))
    app.add_handler(CallbackQueryHandler(cb_another, pattern=r"^an:"))
    app.add_handler(CallbackQueryHandler(cb_balance, pattern=r"^br$"))
    app.add_handler(CallbackQueryHandler(cb_cancel, pattern=r"^cx:"))
    app.add_handler(CallbackQueryHandler(cb_home, pattern=r"^hm$"))
    app.add_handler(CallbackQueryHandler(cb_copy_fallback, pattern=r"^cp:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback))
    app.add_error_handler(app_error_handler)
    return app


def env_truthy(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def should_use_webhook() -> bool:
    mode = os.getenv("BOT_TRANSPORT", "auto").strip().lower()
    if mode == "polling":
        return False
    if mode == "webhook":
        return True
    if env_truthy("FORCE_POLLING", default=False):
        return False
    return bool(os.getenv("WEBHOOK_URL", "").strip())


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = b"OK"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def start_health_server_if_needed(use_webhook: bool) -> Optional[ThreadingHTTPServer]:
    if use_webhook:
        return None
    if not env_truthy("ENABLE_HEALTH_SERVER", default=bool(os.getenv("RENDER"))):
        return None
    port_raw = os.getenv("PORT", "").strip()
    if not port_raw:
        return None
    try:
        port = int(port_raw)
    except ValueError:
        logger.warning("Invalid PORT for health server: %s", port_raw)
        return None
    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), _HealthHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True, name="health-server")
        t.start()
        logger.info("Health server listening on 0.0.0.0:%s", port)
        return server
    except OSError as e:
        logger.warning("Health server bind failed on port %s: %s", port, e)
        return None


def main() -> None:
    logging.basicConfig(format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN missing (.env or environment variable required)")
    if not API_KEY:
        raise SystemExit("TEMPLINE_API_KEY/SMSBOWER_API_KEY missing (.env or environment variable required)")
    if not SUPABASE_URL:
        raise SystemExit("SUPABASE_URL missing (.env or environment variable required)")
    if not SUPABASE_KEY:
        raise SystemExit("SUPABASE_SERVICE_ROLE_KEY বা SUPABASE_KEY বা SUPABASE_SECRET_KEY missing")
    if "YOUR_REAL_SMSBOWER_API_KEY" in API_KEY:
        raise SystemExit("SMSBOWER API key is placeholder. Set real API key.")
    validate_telegram_token(BOT_TOKEN)
    if not acquire_instance_lock(LOCK_FILE_PATH):
        raise SystemExit(
            "Another Templine bot instance is already running. "
            "Stop the old process first, then run again."
        )
    atexit.register(release_instance_lock)
    try:
        parts = [int(p) for p in str(httpx.__version__).split(".")[:2]]
        if (parts[0], parts[1]) >= (0, 28):
            raise SystemExit(
                f"Incompatible httpx version {httpx.__version__}. "
                "Use httpx>=0.27,<0.28 for python-telegram-bot 21.x."
            )
    except ValueError:
        pass

    logger.info(
        "Startup config: ADMIN_USER_ID=%s | BASE_URL=%s | SUPABASE_URL=%s | MODE=supabase-py",
        ADMIN_USER_ID,
        BASE_URL,
        SUPABASE_URL,
    )
    use_webhook = should_use_webhook()
    health_server = start_health_server_if_needed(use_webhook)
    app = build_app()
    logger.info("Templine bot boot complete. Role-based mode enabled. Admin user_id=%s", ADMIN_USER_ID)
    webhook_url = os.getenv("WEBHOOK_URL", "").strip()
    try:
        if use_webhook and webhook_url:
            path = os.getenv("WEBHOOK_PATH", "/telegram-webhook")
            logger.info("Starting webhook mode at %s%s", webhook_url.rstrip("/"), path)
            app.run_webhook(
                listen=os.getenv("WEBHOOK_LISTEN", "0.0.0.0"),
                port=int(os.getenv("PORT", "8443")),
                webhook_url=f"{webhook_url.rstrip('/')}{path}",
                webhook_path=path,
                drop_pending_updates=True,
            )
        else:
            if use_webhook and not webhook_url:
                logger.warning("BOT_TRANSPORT=webhook but WEBHOOK_URL is empty. Falling back to polling mode.")
            logger.info("Starting polling mode")
            clear_telegram_webhook_if_polling(BOT_TOKEN)
            print("Templine bot is running in polling mode. Press Ctrl+C to stop.", flush=True)
            app.run_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES,
                poll_interval=0.5,
                timeout=15,
            )
    finally:
        if health_server is not None:
            try:
                health_server.shutdown()
                health_server.server_close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
