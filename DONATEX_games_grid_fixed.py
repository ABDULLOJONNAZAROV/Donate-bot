import asyncio
import csv
import hashlib
import hmac
import html
import io
import json
import logging
import os
import re
import secrets
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (BufferedInputFile, InlineKeyboardButton,
                           InlineKeyboardMarkup, KeyboardButton,
                           MenuButtonCommands, ReplyKeyboardMarkup,
                           ReplyKeyboardRemove)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("shop")

# ===================== Настройки =====================
BOT_TOKEN = os.environ["BOT_TOKEN"]
DONATIX_KEY = os.environ.get("DONATIX_KEY", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
MARGIN = float(os.environ.get("MARGIN", "0.15"))
PORT = int(os.environ.get("PORT", 10000))
EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
DB_FILE = Path(os.environ.get("DB_FILE", "users.json"))
BASE_DIR = Path(__file__).resolve().parent
GAME_IMAGE_DIR = Path(os.environ.get("GAME_IMAGE_DIR", str(BASE_DIR / "game_images")))
REF_PERCENT = float(os.environ.get("REF_PERCENT", "5"))
LOW_BALANCE_USD = float(os.environ.get("LOW_BALANCE_USD", "5"))
BALANCE_PATH = os.environ.get("DONATIX_BALANCE_PATH", "/balance")
SUPPORT_CONTACT = os.environ.get("SUPPORT_CONTACT", "")
MIN_TOPUP = max(2.0, float(os.environ.get("MIN_TOPUP", "2")))
RECEIPTS_CHANNEL_ID = int(os.environ.get("RECEIPTS_CHANNEL_ID", "0"))
MAX_TOPUP = float(os.environ.get("MAX_TOPUP", "5000"))
TZ = timezone(timedelta(hours=5))  # Душанбе

# --- Новые переменные окружения ---
# Канал для отзывов (например @donatex_reviews) — ссылка-кнопка в /start
REVIEWS_CHANNEL = os.environ.get("REVIEWS_CHANNEL", "")
# ID канала для пересылки отзывов (например -1001234567890)
REVIEWS_CHANNEL_ID = int(os.environ.get("REVIEWS_CHANNEL_ID", "0"))
# Новостные каналы по языкам
NEWS_CHANNEL_TG = os.environ.get("NEWS_CHANNEL_TG", "")
NEWS_CHANNEL_RU = os.environ.get("NEWS_CHANNEL_RU", "")
NEWS_CHANNEL_EN = os.environ.get("NEWS_CHANNEL_EN", "")
PAY_METHODS = {}
if os.environ.get("DC_NUMBER"):
    PAY_METHODS["dc"] = {"title": "🏙 Душанбе Сити", "number": os.environ["DC_NUMBER"],
                         "holder": os.environ.get("DC_HOLDER", "")}
if os.environ.get("ALIF_NUMBER"):
    PAY_METHODS["alif"] = {"title": "🏦 Алиф", "number": os.environ["ALIF_NUMBER"],
                           "holder": os.environ.get("ALIF_HOLDER", "")}

API = "https://donatix.tj/api/v1"
HEADERS = {"X-API-Key": DONATIX_KEY}
bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ===================== Тексты (tg / ru / en / ar / zh / hi) =====================
T = {
    "tg": {
        "welcome": (
            "🔥❤️ Хуш омадед ба DONATEX!\n\n"
            "💎 Алмос ва UC — бо ID-и бозингар, пардохт бо сомонӣ.\n"
            "⚡ Фармоиш пас аз пардохт худкор иҷро мешавад.\n\n"
            "💰 Баланси шумо: <b>{bal}</b> с.\n\nБозиро интихоб кунед 👇"
        ),
        "all_games": "🎮 Ҳамаи бозиҳо", "stars": "⭐ Stars / Premium", "balance": "💰 Баланс",
        "orders": "📦 Фармоишҳои ман", "support": "🛟 Дастгирӣ", "promo": "🎟 Промокод",
        "ref": "👥 Даъват", "lang": "🌐 Забон", "shop": "🛒 Мағоза", "menu": "🏠 Меню",
        "topup": "➕ Пур кардан", "popular": "🔥 Маъмул", "news": "📢 Хабарҳо",
        "reviews_btn": "⭐ Баррасиҳо",
        "blocked": "🚫 Шумо блокир карда шудед", "nf": "Ёфт нашуд", "unavail": "Дастрас нест",
        "pick_pkg": "Пакетро интихоб кунед 👇",
        "enter_id": "📦 {title}\n💰 {price} с.\n\n🆔 ID-и бозингарро ворид кунед:",
        "bad_id": "❌ ID нодуруст аст (6–15 рақам). Дубора ворид кунед:",
        # Антифрод — подтверждение введённого ID
        "confirm_id": "🔎 ID-и шумо: <code>{pid}</code>\n\nДурустаст?",
        "id_ok": "✅ Дуруст", "id_edit": "✏️ Тағйир додан",
        "back": "⬅️ Бозгашт",
        "saved_hint": "👇 ID-ҳои сабтшуда. Як бор пахш кунед — ё ID-и нав нависед, вай ҳам сабт мешавад.",
        "nick_found": "👤 Ник: <b>{nick}</b>",
        "nick_not_found": "❓ Ник ёфт нашуд",
        "confirm_q": "📦 {title}\n👤 {target}\n💰 {price} с.{promo}\n\nТасдиқ мекунед?",
        "ok": "✅ Тасдиқ", "cancel": "❌ Бекор", "cancelled": "❌ Бекор карда шуд.",
        "low": "❌ Баланс кам! Лозим: {price} с., доред: {bal} с.",
        "busy": "⏳ Фармоиши пешина ҳанӯз коркард мешавад.",
        "expired": "⌛ Дархост кӯҳна шуд. Аз нав оғоз кунед.",
        "order_ok": "✅ Фармоиш #{oid} қабул шуд!\n💰 {price} с. гирифта шуд.\n💰 Баланс: {bal} с.\n⏳ Ба зудӣ тайёр мешавад!",
        "order_err": "❌ Хато: {err}\n💰 Маблағ баргардонида шуд.",
        "order_wait": "⚠️ Ҷавоби хидмат нарасид. Фармоиш аз тарафи админ санҷида мешавад, маблағ ҳифз шудааст.",
        "enter_uname": "💬 @username-и гирандаро ворид кунед:",
        "bad_uname": "❌ Username нодуруст аст. Мисол: @username",
        "choose_pay": "💳 Усули пардохтро интихоб кунед:", "no_pay": "Рақамҳо танзим нашудаанд",
        "choose_amt": "{title} — миқдор:", "other": "✏️ Дигар",
        "enter_amt": "✏️ Миқдорро бо рақам нависед ({min}–{max} с.):",
        "bad_amt": "❌ Миқдори нодуруст. Иҷозат: {min}–{max} с.",
        "topup_instr": "💳 {title}:\n1️⃣ Ба рақам гузаронед: <code>{number}</code>{holder}\n💵 Миқдор: {amount} с.\n\n2️⃣ Чек (акс)-ро фиристед 📸",
        "receipt_ok": "✅ Чек қабул шуд, интизори тасдиқ.",
        "topup_done": "💰 Баланс пур шуд! ➕ {amount} с.\n💰 Ҳозира: {bal} с.",
        "topup_no": "❌ Чек тасдиқ нашуд.",
        "bal_text": "💰 Баланси шумо: <b>{bal}</b> с.",
        "tx_title": "\n\n📋 Амалиётҳои охирин:",
        "orders_title": "📦 Фармоишҳои охирин:", "no_orders": "😕 Фармоиш нест.",
        "support_text": "🛟 Дастгирӣ: {contact}",
        "ref_text": "👥 Дӯстонро даъват кунед ва {pct}% аз аввалин пур кардани онҳоро гиред!\n\n🔗 {link}\n\nДаъватшудагон: {n}\nДаромад: {earned} с.",
        "ref_bonus": "🎁 Бонуси реферал: +{amount} с.",
        "promo_ask": "🎟 Промокодро ворид кунед:",
        "promo_ok": "✅ Промокод фаъол шуд: -{pct}% ба фармоиши навбатӣ.",
        "promo_bad": "❌ Промокод нодуруст ё истифода шудааст.",
        "promo_line": "\n🎟 Бо промокод: -{pct}%",
        "user_discount_line": "\n💸 Скидкаи шахсӣ: -{pct}%",
        "lang_choose": "🌐 Забонро интихоб кунед:", "lang_set": "✅ Забон иваз шуд.",
        "stars_title": "⭐ Telegram Stars ва Premium\n\nМиқдорро интихоб кунед:",
        "games_title": "🎮 Ҳамаи бозиҳо:", "months": "моҳ", "shop_hint": "🛒 Мағозаро кушоед:",
        "help": "📖 /start — меню · /balance — баланс · /admin — панели админ",
        "next": "➡️", "prev": "⬅️",
        "popular_title": "🔥 Маъмултарин молҳо:",
        "no_popular": "😕 Маълумот нест.",
        # Отзывы
        "review_ask": "⭐ Фармоиш иҷро шуд! Лутфан баҳо диҳед:",
        "review_text_ask": "✍️ Назари худро нависед (ё /skip барои гузаштан):",
        "review_thanks": "🙏 Ташаккур барои назари шумо!",
        "review_skip": "/skip",
    },
    "ru": {
        "welcome": (
            "🔥❤️ Добро пожаловать в DONATEX!\n\n"
            "💎 Алмазы и UC — по ID игрока, оплата в сомони.\n"
            "⚡ Заказ выполняется автоматически после оплаты.\n\n"
            "💰 Ваш баланс: <b>{bal}</b> с.\n\nВыберите игру 👇"
        ),
        "all_games": "🎮 Все игры", "stars": "⭐ Stars / Premium", "balance": "💰 Баланс",
        "orders": "📦 Мои заказы", "support": "🛟 Поддержка", "promo": "🎟 Промокод",
        "ref": "👥 Пригласить", "lang": "🌐 Язык", "shop": "🛒 Магазин", "menu": "🏠 Меню",
        "topup": "➕ Пополнить", "popular": "🔥 Популярное", "news": "📢 Новости",
        "reviews_btn": "⭐ Отзывы",
        "blocked": "🚫 Вы заблокированы", "nf": "Не найдено", "unavail": "Недоступно",
        "pick_pkg": "Выберите пакет 👇",
        "enter_id": "📦 {title}\n💰 {price} с.\n\n🆔 Введите ID игрока:",
        "bad_id": "❌ Неверный ID (6–15 цифр). Введите ещё раз:",
        "confirm_id": "🔎 Ваш ID: <code>{pid}</code>\n\nВсё верно?",
        "id_ok": "✅ Верно", "id_edit": "✏️ Исправить",
        "back": "⬅️ Назад",
        "saved_hint": "👇 Сохранённые ID. Нажмите на свой — или напишите другой ID, он тоже сохранится.",
        "nick_found": "👤 Ник: <b>{nick}</b>",
        "nick_not_found": "❓ Ник не найден",
        "confirm_q": "📦 {title}\n👤 {target}\n💰 {price} с.{promo}\n\nПодтверждаете?",
        "ok": "✅ Подтвердить", "cancel": "❌ Отмена", "cancelled": "❌ Отменено.",
        "low": "❌ Недостаточно средств! Нужно: {price} с., у вас: {bal} с.",
        "busy": "⏳ Предыдущий заказ ещё обрабатывается.",
        "expired": "⌛ Запрос устарел. Начните заново.",
        "order_ok": "✅ Заказ #{oid} принят!\n💰 Списано {price} с.\n💰 Баланс: {bal} с.\n⏳ Скоро будет готов!",
        "order_err": "❌ Ошибка: {err}\n💰 Деньги возвращены.",
        "order_wait": "⚠️ Ответ сервиса не получен. Заказ проверит админ, деньги сохранены.",
        "enter_uname": "💬 Введите @username получателя:",
        "bad_uname": "❌ Неверный username. Пример: @username",
        "choose_pay": "💳 Выберите способ оплаты:", "no_pay": "Реквизиты не настроены",
        "choose_amt": "{title} — сумма:", "other": "✏️ Другая",
        "enter_amt": "✏️ Введите сумму цифрами ({min}–{max} с.):",
        "bad_amt": "❌ Неверная сумма. Допустимо: {min}–{max} с.",
        "topup_instr": "💳 {title}:\n1️⃣ Переведите на номер: <code>{number}</code>{holder}\n💵 Сумма: {amount} с.\n\n2️⃣ Отправьте чек (фото) 📸",
        "receipt_ok": "✅ Чек принят, ожидайте подтверждения.",
        "topup_done": "💰 Баланс пополнен! ➕ {amount} с.\n💰 Сейчас: {bal} с.",
        "topup_no": "❌ Чек не подтверждён.",
        "bal_text": "💰 Ваш баланс: <b>{bal}</b> с.",
        "tx_title": "\n\n📋 Последние операции:",
        "orders_title": "📦 Последние заказы:", "no_orders": "😕 Заказов нет.",
        "support_text": "🛟 Поддержка: {contact}",
        "ref_text": "👥 Приглашайте друзей и получайте {pct}% с их первого пополнения!\n\n🔗 {link}\n\nПриглашено: {n}\nЗаработано: {earned} с.",
        "ref_bonus": "🎁 Реферальный бонус: +{amount} с.",
        "promo_ask": "🎟 Введите промокод:",
        "promo_ok": "✅ Промокод активирован: -{pct}% на следующий заказ.",
        "promo_bad": "❌ Промокод неверный или уже использован.",
        "promo_line": "\n🎟 С промокодом: -{pct}%",
        "user_discount_line": "\n💸 Персональная скидка: -{pct}%",
        "lang_choose": "🌐 Выберите язык:", "lang_set": "✅ Язык изменён.",
        "stars_title": "⭐ Telegram Stars и Premium\n\nВыберите количество:",
        "games_title": "🎮 Все игры:", "months": "мес.", "shop_hint": "🛒 Откройте магазин:",
        "help": "📖 /start — меню · /balance — баланс · /admin — панель админа",
        "next": "➡️", "prev": "⬅️",
        "popular_title": "🔥 Популярные товары:",
        "no_popular": "😕 Нет данных.",
        "review_ask": "⭐ Заказ выполнен! Пожалуйста, оцените:",
        "review_text_ask": "✍️ Напишите ваш отзыв (или /skip чтобы пропустить):",
        "review_thanks": "🙏 Спасибо за ваш отзыв!",
        "review_skip": "/skip",
    },
    "en": {
        "welcome": (
            "🔥❤️ Welcome to DONATEX!\n\n"
            "💎 Diamonds and UC by player ID, pay in somoni.\n"
            "⚡ Orders are fulfilled automatically after payment.\n\n"
            "💰 Your balance: <b>{bal}</b> TJS\n\nChoose a game 👇"
        ),
        "all_games": "🎮 All games", "stars": "⭐ Stars / Premium", "balance": "💰 Balance",
        "orders": "📦 My orders", "support": "🛟 Support", "promo": "🎟 Promo code",
        "ref": "👥 Invite", "lang": "🌐 Language", "shop": "🛒 Shop", "menu": "🏠 Menu",
        "topup": "➕ Top up", "popular": "🔥 Popular", "news": "📢 News",
        "reviews_btn": "⭐ Reviews",
        "blocked": "🚫 You are blocked", "nf": "Not found", "unavail": "Unavailable",
        "pick_pkg": "Choose a package 👇",
        "enter_id": "📦 {title}\n💰 {price} TJS\n\n🆔 Enter the player ID:",
        "bad_id": "❌ Invalid ID (6–15 digits). Try again:",
        "confirm_id": "🔎 Your ID: <code>{pid}</code>\n\nIs this correct?",
        "id_ok": "✅ Correct", "id_edit": "✏️ Change",
        "back": "⬅️ Back",
        "saved_hint": "👇 Saved IDs. Tap one — or type another ID and it will be saved too.",
        "nick_found": "👤 Nickname: <b>{nick}</b>",
        "nick_not_found": "❓ Nickname not found",
        "confirm_q": "📦 {title}\n👤 {target}\n💰 {price} TJS{promo}\n\nConfirm?",
        "ok": "✅ Confirm", "cancel": "❌ Cancel", "cancelled": "❌ Cancelled.",
        "low": "❌ Not enough balance! Need: {price} TJS, you have: {bal} TJS",
        "busy": "⏳ Your previous order is still being processed.",
        "expired": "⌛ Request expired. Please start again.",
        "order_ok": "✅ Order #{oid} accepted!\n💰 Charged {price} TJS\n💰 Balance: {bal} TJS\n⏳ It will be ready soon!",
        "order_err": "❌ Error: {err}\n💰 Your money was refunded.",
        "order_wait": "⚠️ No reply from the service. The admin will check your order; your funds are held.",
        "enter_uname": "💬 Enter the recipient's @username:",
        "bad_uname": "❌ Invalid username. Example: @username",
        "choose_pay": "💳 Choose a payment method:", "no_pay": "Payment details are not configured",
        "choose_amt": "{title} — amount:", "other": "✏️ Other",
        "enter_amt": "✏️ Enter the amount as a number ({min}–{max} TJS):",
        "bad_amt": "❌ Invalid amount. Allowed: {min}–{max} TJS",
        "topup_instr": "💳 {title}:\n1️⃣ Transfer to: <code>{number}</code>{holder}\n💵 Amount: {amount} TJS\n\n2️⃣ Send the receipt (photo) 📸",
        "receipt_ok": "✅ Receipt received, waiting for confirmation.",
        "topup_done": "💰 Balance topped up! ➕ {amount} TJS\n💰 Now: {bal} TJS",
        "topup_no": "❌ Receipt was not approved.",
        "bal_text": "💰 Your balance: <b>{bal}</b> TJS",
        "tx_title": "\n\n📋 Recent transactions:",
        "orders_title": "📦 Recent orders:", "no_orders": "😕 No orders yet.",
        "support_text": "🛟 Support: {contact}",
        "ref_text": "👥 Invite friends and get {pct}% of their first top-up!\n\n🔗 {link}\n\nInvited: {n}\nEarned: {earned} TJS",
        "ref_bonus": "🎁 Referral bonus: +{amount} TJS",
        "promo_ask": "🎟 Enter your promo code:",
        "promo_ok": "✅ Promo activated: -{pct}% on your next order.",
        "promo_bad": "❌ Invalid or already used promo code.",
        "promo_line": "\n🎟 With promo: -{pct}%",
        "user_discount_line": "\n💸 Personal discount: -{pct}%",
        "lang_choose": "🌐 Choose a language:", "lang_set": "✅ Language changed.",
        "stars_title": "⭐ Telegram Stars and Premium\n\nChoose an amount:",
        "games_title": "🎮 All games:", "months": "mo.", "shop_hint": "🛒 Open the shop:",
        "help": "📖 /start — menu · /balance — balance · /admin — admin panel",
        "next": "➡️", "prev": "⬅️",
        "popular_title": "🔥 Popular items:",
        "no_popular": "😕 No data yet.",
        "review_ask": "⭐ Order completed! Please rate it:",
        "review_text_ask": "✍️ Write your review (or /skip to skip):",
        "review_thanks": "🙏 Thank you for your review!",
        "review_skip": "/skip",
    },
}

# ===================== Хранилище =====================
DEFAULT_DB = {"users": {}, "topups": {}, "orders": [], "promos": {}, "meta": {},
              "game_scores": {}, "webapp_order_requests": {}, "reviews": []}
USER_DEFAULTS = {
    "balance": 0.0, "name": "", "username": "", "blocked": False, "lang": "tg", "ref_by": None,
    "refs": 0, "ref_earned": 0.0, "topped": False, "promo": None, "joined": 0,
    "discount_percent": 0.0,              # персональная скидка админа (%)
    "transactions": [],                   # история операций
    "saved_ids": [],                      # сохранённые ID игроков
    "customer_no": 0, "free_sensitivity_used": False, "sensitivity_credits": 0,
    "cart_items": [], "cart_select_mode": False,
}
db = json.loads(json.dumps(DEFAULT_DB))
pg_pool = None
_dirty = False


async def init_db():
    """PostgreSQL (DATABASE_URL) — постоянное хранение; иначе JSON-файл."""
    global db, pg_pool
    data = None
    if DATABASE_URL:
        import asyncpg
        pg_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3,
                                            statement_cache_size=0)
        async with pg_pool.acquire() as con:
            await con.execute("CREATE TABLE IF NOT EXISTS kv (key text PRIMARY KEY, value text NOT NULL)")
            row = await con.fetchrow("SELECT value FROM kv WHERE key='db'")
        if row:
            data = json.loads(row["value"])
        log.info("DB: PostgreSQL")
    elif DB_FILE.exists():
        data = json.loads(DB_FILE.read_text())
        log.info("DB: JSON file (данные пропадут при редеплое на Render!)")
    if data:
        db = data
    for k, v in DEFAULT_DB.items():
        db.setdefault(k, json.loads(json.dumps(v)))
    # Assign permanent customer numbers to legacy accounts, with admin first.
    if str(ADMIN_ID) in db["users"]:
        db["users"][str(ADMIN_ID)].setdefault("customer_no", 1)
        db["users"][str(ADMIN_ID)]["customer_no"] = 1
    ordered_users = sorted(((uid, user) for uid, user in db["users"].items() if uid != str(ADMIN_ID)),
                           key=lambda z: (z[1].get("joined", 0), z[0]))
    used_numbers = {1} if str(ADMIN_ID) in db["users"] else set()
    next_no = 1 if used_numbers else 0
    for uid, user in ordered_users:
        number = int(user.get("customer_no") or 0)
        if number <= 1 or number in used_numbers:
            next_no += 1
            while next_no in used_numbers:
                next_no += 1
            user["customer_no"] = next_no
            number = next_no
        used_numbers.add(number)
        user.setdefault("free_sensitivity_used", False)
        user.setdefault("sensitivity_credits", 0)
    save_db()


def save_db():
    global _dirty
    _dirty = True


async def persist():
    global _dirty
    if not _dirty:
        return
    _dirty = False
    db["orders"] = db["orders"][-5000:]
    raw = json.dumps(db, ensure_ascii=False)
    try:
        if pg_pool:
            async with pg_pool.acquire() as con:
                await con.execute(
                    "INSERT INTO kv(key,value) VALUES('db',$1) "
                    "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value", raw)
        else:
            tmp = DB_FILE.with_suffix(".tmp")
            tmp.write_text(raw)
            tmp.replace(DB_FILE)
    except Exception as e:
        _dirty = True
        log.error("persist: %s", e)


async def saver_loop():
    while True:
        await asyncio.sleep(2)
        await persist()


def get_user(uid, name="", username=""):
    uid = str(uid)
    u = db["users"].get(uid)
    if u is None:
        u = {**USER_DEFAULTS, "joined": int(time.time()), "transactions": [], "saved_ids": [], "cart_items": []}
        db["users"][uid] = u
    for k, v in USER_DEFAULTS.items():
        if k in ("transactions", "saved_ids", "cart_items"):
            u.setdefault(k, [])
        else:
            u.setdefault(k, v)
    changed = False
    if not int(u.get("customer_no") or 0):
        # Admin is customer #1; all other existing/new accounts receive stable sequence numbers.
        used = [int(x.get("customer_no") or 0) for x in db["users"].values()]
        if str(uid) == str(ADMIN_ID):
            u["customer_no"] = 1
        else:
            u["customer_no"] = max([1, *used]) + 1
        changed = True
    if name and u.get("name") != name:
        u["name"] = name
        changed = True
    if username and u.get("username") != username:
        u["username"] = username.lstrip("@")
        changed = True
    if changed:
        save_db()
    return u


def t(uid, key, **kw):
    lang = get_user(uid)["lang"]
    s = T.get(lang, T["tg"]).get(key) or T["tg"].get(key, key)
    return s.format(**kw) if kw else s


def esc(x):
    return html.escape(str(x), quote=False)


def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)


def btn(text, data):
    # Новые версии Bot API поддерживают синий стиль inline-кнопок.
    # Старые версии aiogram/Telegram-клиентов безопасно используют стандартный стиль.
    fields = getattr(InlineKeyboardButton, "model_fields", {})
    options = {"text": text, "callback_data": data}
    if "style" in fields:
        options["style"] = "primary"
    return InlineKeyboardButton(**options)


def lbtn(text, url):
    fields = getattr(InlineKeyboardButton, "model_fields", {})
    options = {"text": text, "url": url}
    if "style" in fields:
        options["style"] = "primary"
    return InlineKeyboardButton(**options)

def is_admin(uid):
    return ADMIN_ID != 0 and uid == ADMIN_ID


def sid(s):
    return hashlib.md5(str(s).encode()).hexdigest()[:8]


def now_ts():
    return int(time.time())


# ===================== Вспомогательная функция для пустых состояний =====================
def nav_row(uid, back="menu"):
    """Кнопка назад и меню вместе."""
    return [btn(t(uid, "back"), back), btn(t(uid, "menu"), "menu")]


def cta_kb(uid, back="menu"):
    """Клавиатура с призывом к действию — используется вместо тупиковых экранов."""
    return kb([nav_row(uid, back)])


# ===================== Лог транзакций =====================
def add_transaction(uid, amount, tx_type, desc=""):
    """Добавляет запись об операции в историю пользователя."""
    u = get_user(uid)
    if "transactions" not in u:
        u["transactions"] = []
    u["transactions"].append({
        "type": tx_type,   # "topup" или "order"
        "amount": amount,
        "ts": now_ts(),
        "desc": desc,
    })
    # Храним последние 50 операций
    u["transactions"] = u["transactions"][-50:]


def tx_text(uid):
    """Текст последних 5 транзакций для отображения в балансе."""
    u = get_user(uid)
    txs = u.get("transactions", [])[-5:][::-1]
    if not txs:
        return ""
    lines = []
    for tx in txs:
        sign = "➕" if tx["amount"] > 0 else "➖"
        dt = datetime.fromtimestamp(tx["ts"], TZ).strftime("%d.%m %H:%M")
        lines.append(f"{sign} {abs(tx['amount']):.2f} · {esc(tx.get('desc', ''))} · {dt}")
    return t(uid, "tx_title") + "\n" + "\n".join(lines)


# ===================== Курс =====================
usd_tjs, rate_at = 10.9, 0.0


async def update_rate():
    global usd_tjs, rate_at
    if time.time() - rate_at < 3600:
        return
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://open.er-api.com/v6/latest/USD",
                             timeout=aiohttp.ClientTimeout(total=10)) as r:
                d = await r.json(content_type=None)
        if d.get("result") == "success":
            usd_tjs = d["rates"]["TJS"]
            rate_at = time.time()
    except Exception as e:
        log.warning("rate: %s", e)


def tjs(usd):
    return round(usd * usd_tjs * (1 + MARGIN), 2)


# ===================== Каталог =====================
catalog, cat_short, prod_short = {}, {}, {}
special = {"stars": None, "premium": {}}
cat_at = 0.0


async def load_catalog(force=False):
    global catalog, cat_short, prod_short, special, cat_at
    if not force and catalog and time.time() - cat_at < 600:
        return
    if not DONATIX_KEY:
        return
    await update_rate()
    try:
        async with aiohttp.ClientSession() as s:
            async def get(params):
                async with s.get(f"{API}/products", params=params, headers=HEADERS,
                                 timeout=aiohttp.ClientTimeout(total=30)) as r:
                    return await r.json(content_type=None)

            # === ИСПРАВЛЕНИЕ: грузим ВСЕ товары, а не только первые 500 ===
            all_items, seen = [], set()
            LIMIT = 500

            async def pull(extra):
                d = await get({"kind": "topup", "limit": LIMIT, **extra})
                chunk = d.get("items", []) if isinstance(d, dict) else []
                added = 0
                for p in chunk:
                    pid = p.get("product_id")
                    if pid not in seen:
                        seen.add(pid)
                        all_items.append(p)
                        added += 1
                return added, len(chunk)

            offset = 0
            for _ in range(60):                      # пагинация через offset
                added, n = await pull({"offset": offset})
                if added == 0 or n < LIMIT:
                    break
                offset += LIMIT

            if len(all_items) <= LIMIT:              # если offset не поддерживается
                page = 2
                for _ in range(60):                  # пагинация через page
                    added, n = await pull({"page": page})
                    if added == 0 or n < LIMIT:
                        break
                    page += 1

            if len(all_items) <= LIMIT:              # запасной вариант: большой limit
                d = await get({"kind": "topup", "limit": 5000})
                for p in (d.get("items", []) if isinstance(d, dict) else []):
                    pid = p.get("product_id")
                    if pid not in seen:
                        seen.add(pid)
                        all_items.append(p)

            log.info("catalog: товаров загружено %s", len(all_items))

            stars = await get({"kind": "telegram_stars", "limit": 5})
            prem = await get({"kind": "telegram_premium", "limit": 10})

            new_cat, new_prod = {}, {}
            for p in all_items:
                cid = p.get("category_id")
                new_cat.setdefault(cid, {"name": p.get("category_name") or str(cid), "products": []})
                p["price_tjs"] = tjs(float(p.get("price_usd", 0)))
                new_cat[cid]["products"].append(p)
                new_prod[sid(p["product_id"])] = p

            new_special = {"stars": None, "premium": {}}
            for it in stars.get("items", []):
                if it.get("product_id") == "tg-stars":
                    new_special["stars"] = {"unit": float(it["price_usd"]),
                                            "min": it.get("min_quantity", 50),
                                            "max": it.get("max_quantity", 10000)}
            new_special["premium"] = {p["product_id"]: p for p in prem.get("items", [])}

            catalog, prod_short, special = new_cat, new_prod, new_special
            cat_short = {sid(cid): cid for cid in catalog}
            cat_at = time.time()
            log.info("catalog: категорий %s", len(catalog))
    except Exception as e:
        log.error("catalog: %s", e)
      
# Карта перевода типичных названий пакетов (API часто отдаёт на английском/смешанном)
_TITLE_MAP = {
    "tg": {
        r"(?i)newbie\s*bundle": "Пакет барои навкорон",
        r"(?i)level\s*up\s*package\s*(\d+)": r"Пакет Level Up \1",
        r"(?i)weekly\s*lite": "Ҳафтаина Lite",
        r"(?i)weekly": "Ҳафтаина",
        r"(?i)monthly|month": "Моҳона",
        r"(?i)voucher\s*(?:for\s*)?(?:a\s*)?week|voucher\s*на\s*неделю": "Ваучер барои ҳафта",
        r"(?i)voucher\s*(?:for\s*)?(?:a\s*)?month|voucher\s*на\s*месяц": "Ваучер барои моҳ",
        r"(?i)доступ\s*к\s*evo[-\s]*оружию|evo[-\s]*weapon|access\s*to\s*evo": "Дастрасӣ ба Evo-силоҳ",
        r"(?i)(\d+)\s*алмаз(?:ов|а|ы)?|(\d+)\s*diamonds?": r"\1\2 алмос",
        r"(?i)(\d+)\s*uc\b": r"\1 UC",
        r"(?i)telegram\s*stars|stars": "Telegram Stars",
        r"(?i)premium": "Premium",
    },
    "ru": {
        r"(?i)newbie\s*bundle": "Пакет для новичков",
        r"(?i)level\s*up\s*package\s*(\d+)": r"Пакет Level Up \1",
        r"(?i)weekly\s*lite": "Недельный Lite",
        r"(?i)weekly": "Недельный",
        r"(?i)monthly|month": "Месячный",
        r"(?i)voucher\s*(?:for\s*)?(?:a\s*)?week": "Ваучер на неделю",
        r"(?i)voucher\s*(?:for\s*)?(?:a\s*)?month": "Ваучер на месяц",
        r"(?i)доступ\s*к\s*evo[-\s]*оружию|evo[-\s]*weapon|access\s*to\s*evo": "Доступ к Evo-оружию",
        r"(?i)(\d+)\s*diamonds?": r"\1 алмазов",
        r"(?i)(\d+)\s*uc\b": r"\1 UC",
        r"(?i)telegram\s*stars|stars": "Telegram Stars",
        r"(?i)premium": "Premium",
    },
    "en": {
        r"(?i)newbie\s*bundle": "Newbie Bundle",
        r"(?i)level\s*up\s*package\s*(\d+)": r"Level Up Package \1",
        r"(?i)weekly\s*lite": "Weekly Lite",
        r"(?i)weekly": "Weekly",
        r"(?i)monthly|month": "Monthly",
        r"(?i)voucher\s*(?:for\s*)?(?:a\s*)?week|voucher\s*на\s*неделю": "Weekly Voucher",
        r"(?i)voucher\s*(?:for\s*)?(?:a\s*)?month|voucher\s*на\s*месяц": "Monthly Voucher",
        r"(?i)доступ\s*к\s*evo[-\s]*оружию|evo[-\s]*weapon|access\s*to\s*evo": "Access to Evo Weapon",
        r"(?i)(\d+)\s*алмаз(?:ов|а|ы)?": r"\1 Diamonds",
        r"(?i)(\d+)\s*uc\b": r"\1 UC",
        r"(?i)telegram\s*stars|stars": "Telegram Stars",
        r"(?i)premium": "Premium",
    },
}


def ptitle(p, lang=None):
    """Название товара с учётом языка пользователя."""
    raw = str(p.get("title") or p.get("name") or p.get("product_id") or "")
    if not lang:
        return raw
    mapping = _TITLE_MAP.get(lang) or _TITLE_MAP.get("tg") or {}
    for pattern, repl in mapping.items():
        new = re.sub(pattern, repl, raw)
        if new != raw:
            raw = new
            break
    return raw


# ===================== Популярные товары =====================
def get_popular_products(days=3650, limit=10):
    """Возвращает топ-N товаров по количеству заказов за последние N дней."""
    since = time.time() - days * 86400
    counts = {}
    titles = {}
    for o in db["orders"]:
        if o.get("status") != "done" or o.get("ts", 0) < since:
            continue
        key = str(o.get("product_id") or o.get("title", ""))
        counts[key] = counts.get(key, 0) + 1
        titles[key] = o.get("title", key)
    top = sorted(counts.items(), key=lambda x: -x[1])[:limit]
    result = []
    for key, cnt in top:
        product = next((p for p in prod_short.values()
                        if str(p.get("product_id")) == key), None)
        if product is None:  # совместимость со старыми заказами без product_id
            product = next((p for p in prod_short.values()
                            if ptitle(p) == titles.get(key)), None)
        if product is not None:
            result.append((product, cnt))
    return result


# ===================== Поиск ника игрока =====================
def _nick_from_payload(data):
    if not isinstance(data, dict):
        return ""
    basic = data.get("basicinfo") or data.get("AccountInfo") or data
    for key in ("player_name", "nickname", "Nickname", "name", "Name", "username"):
        value = basic.get(key) if isinstance(basic, dict) else None
        if not value and key in data:
            value = data.get(key)
        if value and str(value).strip() not in ("0", "None"):
            return str(value).strip()
    return ""


async def lookup_player_nick(product, player_id: str) -> str:
    """Ник через Donatix POST /accounts/check. Для Free Fire — запасной публичный поиск."""
    product_id = product.get("product_id") if isinstance(product, dict) else str(product)
    blob = ""
    if isinstance(product, dict):
        blob = " ".join(str(product.get(k) or "") for k in
                        ("title", "name", "category_name", "category_id")).lower()
    if DONATIX_KEY and product_id:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    f"{API}/accounts/check",
                    json={"product_id": product_id, "fields": {"player_id": str(player_id)}},
                    headers={**HEADERS, "Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=12),
                ) as r:
                    data = await r.json(content_type=None)
            nick = _nick_from_payload(data if isinstance(data, dict) else {})
            if nick:
                return nick
        except Exception as e:
            log.warning("accounts/check: %s", e)
    if any(word in blob for word in ("free fire", "garena", "freefire")) or re.search(r"\bff\b", blob):
        if any(word in blob for word in ("indones", "indon")):
            regions = ["id", "ind", "sg"]
        elif any(word in blob for word in ("cis", "снг", "russia", " ru", "rus")):
            regions = ["cis", "ru", "sg"]
        else:
            regions = ["cis", "sg", "id", "ind", "br", "ru"]
        for region in regions:
            try:
                nick = _nick_from_payload(await fetch_ff_player(str(player_id), region))
            except Exception:
                nick = ""
            if nick and nick != str(player_id):
                return nick
    return ""


def remember_player_id(uid, player_id, nick="", game=""):
    """Сохраняет ID игрока. Новый ID добавляется, старые не затираются."""
    u = get_user(uid)
    player_id = str(player_id).strip()
    if not re.fullmatch(r"\d{6,15}", player_id):
        return
    saved = [x for x in (u.get("saved_ids") or []) if str(x.get("id")) != player_id]
    saved.insert(0, {"id": player_id, "nick": str(nick or "")[:40],
                     "game": str(game or "")[:40], "ts": now_ts()})
    u["saved_ids"] = saved[:8]
    save_db()


# ===================== Промокоды / цены =====================
def promo_valid(p, uid=None):
    if not p or not p.get("active", True):
        return False
    if p.get("max_uses") and p.get("used", 0) >= p["max_uses"]:
        return False
    if uid is not None and str(uid) in p.get("users", []):
        return False
    return True


def final_price(uid, base):
    """Рассчитывает финальную цену с учётом промокода и персональной скидки админа."""
    u = get_user(uid)
    price = float(base)

    # Персональная скидка от админа
    user_disc = float(u.get("discount_percent") or 0)
    if user_disc > 0:
        price = round(price * (1 - user_disc / 100), 2)
        return price, None, False, user_disc

    # Промокод
    code = u.get("promo")
    p = db["promos"].get(code) if code else None
    if p and promo_valid(p, uid):
        return round(base * (1 - p["percent"] / 100), 2), code, False, 0
    return round(base, 2), None, False, 0


# ===================== Состояния =====================
user_state = {}
user_category = {}
pend = {}
user_locks = defaultdict(asyncio.Lock)
_bot_username = ""


def new_pending(**kw):
    now = time.time()
    for k in [k for k, v in pend.items() if now - v["ts"] > 3600]:
        pend.pop(k, None)
    tok = secrets.token_hex(4)
    pend[tok] = {**kw, "ts": now}
    return tok


async def edit_or_send(msg, text, markup=None, edit=True):
    if edit:
        try:
            await msg.edit_text(text, reply_markup=markup)
            return
        except Exception:
            pass
    await msg.answer(text, reply_markup=markup)


# ===================== Новостной канал по языку =====================
def get_news_channel(uid):
    """Возвращает ссылку на новостной канал в зависимости от языка пользователя."""
    lang = get_user(uid)["lang"]
    mapping = {
        "tg": NEWS_CHANNEL_TG,
        "ru": NEWS_CHANNEL_RU,
        "en": NEWS_CHANNEL_EN,
    }
    ch = mapping.get(lang, NEWS_CHANNEL_RU or NEWS_CHANNEL_TG)
    if ch and not ch.startswith("http"):
        ch = f"https://t.me/{ch.lstrip('@')}"
    return ch


# ===================== Меню =====================
async def clear_reply_keyboard(chat_id):
    """Снимает старую reply-клавиатуру (Shop / WebApp) у конкретного чата."""
    try:
        rm = await bot.send_message(chat_id, ".", reply_markup=ReplyKeyboardRemove())
        try:
            await rm.delete()
        except Exception:
            pass
    except Exception:
        pass


async def send_menu(msg, user):
    await load_catalog()
    uid = user.id
    uname = getattr(user, "username", None) or ""
    u = get_user(uid, user.full_name or "", uname)
    user_state.pop(uid, None)

    # У каждого пользователя при открытии меню снимаем старую кнопку Shop
    await clear_reply_keyboard(msg.chat.id)

    welcome_text = t(uid, "welcome", bal=f"{u['balance']:.2f}")
    reviews = db.get("reviews", [])
    if reviews:
        avg = sum(int(x.get("stars", 5)) for x in reviews) / len(reviews)
        welcome_text += f"\n\n⭐ Рейтинг харидорон: <b>{avg:.1f}/5</b> · {len(reviews)} отзыв"
    else:
        welcome_text += "\n\n⭐ Ҳанӯз фикру баҳо нест — аввалин шуда баҳо гузоред!"

    # Компактное главное меню: связанные разделы расположены в два столбца.
    rows = [
        [btn(t(uid, "popular"), "popular"), btn(t(uid, "all_games"), "allp:0")],
        [btn("🔥 FF СНГ 💎", "game:ff_cis"), btn("🇮🇩 FF Индонезия 💎", "game:ff_id")],
        [btn("🎯 PUBG Mobile US 🏆", "game:pubg_us"), btn(t(uid, "stars"), "tg_stars")],
        [btn(t(uid, "balance"), "balance"), btn("🛒 Корзина", "cart_info")],
        [btn("👤 Профиль", "profile"), btn("🎯 Настройки Free Fire", "ff_sens")],
        [btn("❓ Частые вопросы", "faq"), btn(t(uid, "ref"), "ref")],
        [btn(t(uid, "support"), "support"), btn(t(uid, "lang"), "lang")],
    ]

    # Новости и отзывы занимают одну строку, если обе ссылки доступны.
    news_ch = get_news_channel(uid)
    news_row = []
    if news_ch:
        news_row.append(lbtn(t(uid, "news"), news_ch))

    if REVIEWS_CHANNEL:
        ch_url = REVIEWS_CHANNEL if REVIEWS_CHANNEL.startswith("http") else f"https://t.me/{REVIEWS_CHANNEL.lstrip('@')}"
        news_row.append(lbtn(t(uid, "reviews_btn"), ch_url))

    if news_row:
        rows.append(news_row)

    if is_admin(uid):
        rows.append([btn("🛠 Панели админ", "admin")])

    await msg.answer(welcome_text, reply_markup=kb(rows))


@dp.message(CommandStart())
async def start(m, command: CommandObject):
    uid = m.from_user.id
    is_new = str(uid) not in db["users"]
    uname = getattr(m.from_user, "username", None) or ""
    u = get_user(uid, m.from_user.full_name or "", uname)
    if is_new and command.args and command.args.startswith("ref_"):
        rid = command.args[4:]
        if rid != str(uid) and rid in db["users"]:
            u["ref_by"] = rid
            db["users"][rid]["refs"] = db["users"][rid].get("refs", 0) + 1
    save_db()
    # Убираем Mini App menu button (если был)
    try:
        await bot.set_chat_menu_button(chat_id=uid, menu_button=MenuButtonCommands())
    except Exception:
        pass
    # send_menu сам снимет reply-клавиатуру Shop
    await send_menu(m, m.from_user)


@dp.message(Command("buy"))
async def buy(m):
    await send_menu(m, m.from_user)


@dp.message(Command("help"))
async def help_cmd(m):
    await m.answer(t(m.from_user.id, "help"))


@dp.message(Command("balance"))
async def balance_cmd(m):
    uid = m.from_user.id
    uname = getattr(m.from_user, "username", None) or ""
    u = get_user(uid, m.from_user.full_name or "", uname)
    text = t(uid, "bal_text", bal=f"{u['balance']:.2f}") + tx_text(uid)
    await m.answer(text, reply_markup=kb([
        [btn(t(uid, "topup"), "topup")],
        [btn(t(uid, "promo"), "promo"), btn(t(uid, "orders"), "my_orders")],
        [btn(t(uid, "menu"), "menu")]
    ]))


@dp.callback_query(F.data == "menu")
async def cb_menu(c):
    await c.answer()
    await send_menu(c.message, c.from_user)


@dp.callback_query(F.data == "balance")
async def cb_balance(c):
    uid = c.from_user.id
    u = get_user(uid, c.from_user.full_name or "")
    # Показываем баланс + историю транзакций (пункт 6)
    text = t(uid, "bal_text", bal=f"{u['balance']:.2f}") + tx_text(uid)
    await c.message.answer(text, reply_markup=kb([
        [btn(t(uid, "topup"), "topup")],
        [btn(t(uid, "promo"), "promo"), btn(t(uid, "orders"), "my_orders")],
        [btn(t(uid, "menu"), "menu")]
    ]))
    await c.answer()


@dp.callback_query(F.data == "my_orders")
async def cb_orders(c):
    uid = c.from_user.id
    mine = [o for o in db["orders"] if o["uid"] == uid][-10:][::-1]
    icons = {"done": "✅", "processing": "⏳", "uncertain": "⚠️", "failed": "❌"}
    if not mine:
        # Используем cta_kb вместо тупикового экрана (пункт 4)
        await c.message.answer(t(uid, "no_orders"), reply_markup=cta_kb(uid))
    else:
        text = t(uid, "orders_title") + "\n\n" + "\n".join(
            f"{icons.get(o['status'], '•')} #{esc(o['oid'])} · {esc(o['title'])} · {o['price']} · "
            f"{datetime.fromtimestamp(o['ts'], TZ):%d.%m %H:%M}" for o in mine)
        await c.message.answer(text, reply_markup=kb([[btn(t(uid, "menu"), "menu")]]))
    await c.answer()


@dp.callback_query(F.data == "support")
async def cb_support(c):
    uid = c.from_user.id
    await c.message.answer(
        "🛟 <b>Поддержка DONATEX</b>\nВыберите, кому написать:",
        reply_markup=kb([
            [lbtn("👨‍💻 Основная поддержка", "https://t.me/DONATEX_ADMIN")],
            [lbtn("🧑‍💻 Резервная поддержка", "https://t.me/DONATEX_ADMIN_2")],
            [btn(t(uid, "menu"), "menu")]
        ]))
    await c.answer()


# ===================== Новостной канал =====================
@dp.callback_query(F.data == "news_channel")
async def cb_news(c):
    uid = c.from_user.id
    ch = get_news_channel(uid)
    if ch:
        await c.answer()
        await c.message.answer(
            t(uid, "news"),
            reply_markup=kb([[lbtn("📢 →", ch)], [btn(t(uid, "menu"), "menu")]])
        )
    else:
        await c.answer("—", show_alert=True)


# ===================== Популярные товары =====================
@dp.callback_query(F.data == "popular")
async def cb_popular(c):
    await c.answer()
    await load_catalog()
    uid = c.from_user.id
    lang = get_user(uid)["lang"]
    top = get_popular_products()
    if not top:
        await c.message.answer(t(uid, "no_popular"), reply_markup=kb([
            [btn(t(uid, "all_games"), "allp:0")], [btn(t(uid, "menu"), "menu")]
        ]))
        return
    rows = []
    for p, cnt in top:
        rows.append([btn(f"🔥 {ptitle(p, lang)[:22]} — {p['price_tjs']} с. ({cnt}×)", f"pkg:{sid(p['product_id'])}")])
    rows.append([btn(t(uid, "menu"), "menu")])
    await edit_or_send(c.message, t(uid, "popular_title"), kb(rows))


# ===================== Язык =====================
@dp.callback_query(F.data == "lang")
async def cb_lang(c):
    uid = c.from_user.id
    await c.message.answer(t(uid, "lang_choose"), reply_markup=kb([
        [btn("🇹🇯 Тоҷикӣ", "setlang:tg"), btn("🇷🇺 Русский", "setlang:ru"), btn("🇬🇧 English", "setlang:en")],
    ]))
    await c.answer()


@dp.callback_query(F.data.startswith("setlang:"))
async def cb_setlang(c):
    lang = c.data.split(":")[1]
    if lang in T:
        get_user(c.from_user.id)["lang"] = lang
        save_db()
    await c.answer(t(c.from_user.id, "lang_set"))
    await send_menu(c.message, c.from_user)


# ===================== Промокод / Рефералка =====================
@dp.callback_query(F.data == "promo")
async def cb_promo(c):
    uid = c.from_user.id
    user_state[uid] = {"stage": "promo"}
    await c.message.answer(t(uid, "promo_ask"))
    await c.answer()


@dp.callback_query(F.data == "ref")
async def cb_ref(c):
    global _bot_username
    uid = c.from_user.id
    if not _bot_username:
        _bot_username = (await bot.get_me()).username
    u = get_user(uid)
    await c.message.answer(
        t(uid, "ref_text", pct=f"{REF_PERCENT:g}", link=f"https://t.me/{_bot_username}?start=ref_{uid}",
          n=u["refs"], earned=f"{u['ref_earned']:.2f}"),
        reply_markup=kb([[btn(t(uid, "menu"), "menu")]]))
    await c.answer()


# ===================== Игры =====================
GAMES_PER_PAGE = 10


def match_game(game):
    def name_for(cid, group):
        return (str(cid) + " " + group["name"]).casefold().replace("_", " ")

    entries = [(cid, name_for(cid, group)) for cid, group in catalog.items()]
    # Region-specific matches come first so Indonesia can never resolve to
    # the first generic Free Fire category in the provider's catalog.
    if game == "ff_id":
        tokens = ("indonesia", "indon", "free fire id", "free fire (id)", "ff id")
        return next((cid for cid, name in entries
                     if ("free fire" in name or "garena" in name)
                     and any(token in name for token in tokens)), None)
    if game == "ff_cis":
        tokens = ("cis", "снг", "russia", "rus", "free fire ru", "ff ru")
        return next((cid for cid, name in entries
                     if ("free fire" in name or "garena" in name)
                     and any(token in name for token in tokens)
                     and not any(token in name for token in ("indonesia", "indon"))), None)
    if game == "pubg_us":
        # Prefer the explicitly US-labelled PUBG category, but providers may
        # expose the same product simply as "PUBG Mobile" or use other region
        # labels. Fall back to a PUBG category so the menu button remains usable.
        exact = next((cid for cid, name in entries if "pubg" in name and
                      ("united states" in name or "usa" in name or
                       re.search(r"(?:^|[\s(/_-])us(?:$|[\s)/_-])", name))), None)
        if exact is not None:
            return exact
        return next((cid for cid, name in entries if "pubg" in name), None)
    if game == "pubg":
        return next((cid for cid, name in entries if "pubg" in name), None)
    if game == "standoff":
        return next((cid for cid, name in entries if "standoff" in name), None)
    if game == "cod":
        return next((cid for cid, name in entries
                     if "call of duty" in name or "cod mobile" in name or "codm" in name), None)
    if game == "capcut":
        return next((cid for cid, name in entries if "capcut" in name or "cap cut" in name), None)
    return None


# ===================== /ff команда — профиль Free Fire =====================
FF_REGIONS = ["sg", "ind", "br", "us", "vn", "th", "tw", "id", "me", "pk", "cis", "bd", "ru"]

async def fetch_ff_player(uid: str, region: str = "sg"):
    """Получает данные игрока Free Fire через публичный API."""
    apis = [
        f"https://ff-info-api.vercel.app/player?uid={uid}&region={region}",
        f"https://freefireinfo.vercel.app/api?uid={uid}&region={region}",
        f"https://ff-info.vercel.app/api/player?uid={uid}&region={region}",
    ]
    async with aiohttp.ClientSession() as s:
        for url in apis:
            try:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status == 200:
                        d = await r.json(content_type=None)
                        if isinstance(d, dict) and (d.get("basicinfo") or d.get("AccountInfo") or d.get("name")):
                            return d
            except Exception:
                continue
    return None


def fmt_ff_profile(d: dict, uid: str) -> str:
    """Форматирует ответ API в красивое сообщение."""
    # Поддержка разных форматов API
    basic = d.get("basicinfo") or d.get("AccountInfo") or d
    clan  = d.get("claninfo")  or d.get("GuildInfo")  or {}
    pet   = d.get("petinfo")   or d.get("PetInfo")    or {}
    rank  = d.get("rankinfo")  or d.get("RankInfo")   or {}
    social = d.get("socialinfo") or d.get("SocialInfo") or {}

    def g(*keys):
        for k in keys:
            v = basic.get(k) or d.get(k)
            if v not in (None, "", 0, "0"):
                return v
        return "—"

    name    = g("nickname", "Nickname", "name", "Name")
    level   = g("level", "Level", "AccountLevel")
    exp     = g("exp", "Exp", "AccountEXP")
    region  = g("region", "Region", "AccountRegion")
    liked   = g("liked", "Liked", "AccountLikes")
    created = g("createat", "CreateAt")
    last    = g("lastloginat", "LastLoginAt")
    honor   = g("honor_score", "HonorScore")
    badges  = g("badge_cnt", "BadgeCount", "badges")
    gender  = social.get("gender") or d.get("gender") or "—"
    lang    = social.get("language") or d.get("language") or "—"

    # Форматируем дату
    def fmt_ts(ts):
        try:
            return datetime.fromtimestamp(int(ts), TZ).strftime("%d %b %Y %I:%M %p")
        except Exception:
            return str(ts)

    created_str = fmt_ts(created) if str(created).isdigit() else created
    last_str    = fmt_ts(last)    if str(last).isdigit()    else last

    # Форматируем лайки
    def fmt_num(n):
        try:
            n = int(n)
            if n >= 1000:
                return f"{n/1000:.1f}K"
            return str(n)
        except Exception:
            return str(n)

    # Ранг
    br_rank = rank.get("BRRankPoint") or rank.get("br_rank") or rank.get("rankpoint", "")
    cs_rank = rank.get("CSRankPoint") or rank.get("cs_rank") or rank.get("cs_rankpoint", "")

    text = (
        f"🎮 <b>Free Fire — Информация об игроке</b>\n\n"
        f"👤 <b>Основная информация:</b>\n"
        f"• Имя: <b>{esc(str(name))}</b>\n"
        f"• UID: <code>{uid}</code>\n"
        f"• Уровень: {level}\n"
        f"• Лайки: {fmt_num(liked)}\n"
        f"• Регион: {region}\n"
        f"• EXP: {fmt_num(exp)}\n"
    )

    if honor != "—":
        text += f"• Honor Score: {honor}\n"
    if badges != "—":
        text += f"• Значков: {badges}\n"
    if created_str != "—":
        text += f"• Создан: {created_str}\n"
    if last_str != "—":
        text += f"• Последний вход: {last_str}\n"

    if br_rank or cs_rank:
        text += f"\n🏆 <b>Рейтинг:</b>\n"
        if br_rank:
            text += f"• BR Ранг: {br_rank}\n"
        if cs_rank:
            text += f"• CS Ранг: {cs_rank}\n"

    if clan:
        cn = clan.get("clanname") or clan.get("GuildName") or clan.get("name", "—")
        ci = clan.get("clanid")   or clan.get("GuildID")   or clan.get("id", "—")
        cl = clan.get("clanlevel") or clan.get("GuildLevel") or "—"
        cm = clan.get("currentmembers") or clan.get("MemberNum") or "—"
        cap = clan.get("maxmembers") or clan.get("GuildCapacity") or "—"
        text += (
            f"\n🏠 <b>Гильдия:</b>\n"
            f"• Название: {esc(str(cn))}\n"
            f"• ID: {ci}\n"
            f"• Уровень: {cl}\n"
            f"• Участники: {cm}/{cap}\n"
        )

    if pet:
        pn = pet.get("name") or pet.get("PetName") or "—"
        pl = pet.get("level") or pet.get("PetLevel") or "—"
        text += (
            f"\n🐾 <b>Питомец:</b>\n"
            f"• Имя: {esc(str(pn))}\n"
            f"• Уровень: {pl}\n"
        )

    if gender != "—" or lang != "—":
        text += f"\n🔰 <b>Социальное:</b>\n"
        if gender != "—":
            text += f"• Пол: {gender}\n"
        if lang != "—":
            text += f"• Язык: {lang}\n"

    return text


async def cmd_ff(m):
    """Команда /ff <uid> [регион] — показывает профиль игрока Free Fire."""
    uid = m.from_user.id
    args = (m.text or "").split()
    if len(args) < 2 or not args[1].isdigit():
        await m.answer(
            "🎮 <b>Free Fire — поиск игрока</b>\n\n"
            "Использование: <code>/ff UID [регион]</code>\n\n"
            "Регионы: sg, ind, br, us, vn, th, id, cis, ru\n"
            "По умолчанию: sg (если СНГ — попробуй cis или ru)\n\n"
            "Пример: <code>/ff 9905658934 cis</code>"
        )
        return
    player_uid = args[1]
    region = args[2].lower() if len(args) > 2 else "sg"

    wait_msg = await m.answer("⏳ Ищу информацию об игроке...")

    # Пробуем разные регионы если не указан явно
    regions_to_try = [region]
    if region == "sg":
        regions_to_try = ["sg", "cis", "ind", "br", "id"]

    data = None
    for reg in regions_to_try:
        data = await fetch_ff_player(player_uid, reg)
        if data:
            break

    try:
        await wait_msg.delete()
    except Exception:
        pass

    if not data:
        await m.answer(
            f"❌ Игрок с UID <code>{player_uid}</code> не найден.\n\n"
            f"Попробуй указать регион явно:\n"
            f"<code>/ff {player_uid} cis</code> — для СНГ\n"
            f"<code>/ff {player_uid} ind</code> — для Индии\n"
            f"<code>/ff {player_uid} br</code> — для Бразилии"
        )
        return

    text = fmt_ff_profile(data, player_uid)
    await m.answer(text, reply_markup=kb([[btn("🏠 Меню", "menu")]]))


# ===================== /look — аватар/аутфит игрока =====================
async def cmd_look(m):
    """/look <uid> [регион] — фото персонажа игрока."""
    args = (m.text or "").split()
    if len(args) < 2 or not args[1].isdigit():
        await m.answer(
            "👗 <b>Внешний вид персонажа</b>\n\n"
            "Использование: <code>/look UID [регион]</code>\n"
            "Пример: <code>/look 9905658934 cis</code>"
        )
        return
    player_uid = args[1]
    region = args[2].lower() if len(args) > 2 else "sg"
    wait_msg = await m.answer("⏳ Загружаю аутфит игрока...")

    # Пробуем получить фото персонажа через публичные API
    avatar_urls = [
        f"https://ff-info-api.vercel.app/outfit?uid={player_uid}&region={region}",
        f"https://freefireinfo.vercel.app/api/outfit?uid={player_uid}&region={region}",
        f"https://avatar.freefireinfo.in/outfit?uid={player_uid}&region={region}",
    ]
    # Прямые ссылки на аватар (работают без API)
    direct_avatar = [
        f"https://avatar.freefireinfo.in/avatar/{player_uid}.png",
        f"https://ff-info-api.vercel.app/avatar/{player_uid}.png",
    ]

    # Сначала пробуем получить данные игрока для имени
    regions_to_try = [region] if region != "sg" else ["sg", "cis", "ind", "br", "id"]
    data = None
    for reg in regions_to_try:
        data = await fetch_ff_player(player_uid, reg)
        if data:
            break

    try:
        await wait_msg.delete()
    except Exception:
        pass

    basic = (data or {}).get("basicinfo") or (data or {}).get("AccountInfo") or (data or {})
    name = basic.get("nickname") or basic.get("Nickname") or basic.get("name") or player_uid
    level = basic.get("level") or basic.get("Level") or "?"

    caption = (
        f"👗 <b>Аутфит игрока</b>\n\n"
        f"👤 Имя: <b>{esc(str(name))}</b>\n"
        f"🆔 UID: <code>{player_uid}</code>\n"
        f"⭐ Уровень: {level}"
    )

    # Пробуем отправить фото с аватаром
    sent = False
    async with aiohttp.ClientSession() as s:
        for url in direct_avatar:
            try:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status == 200 and "image" in r.headers.get("content-type", ""):
                        photo_bytes = await r.read()
                        await m.answer_photo(
                            BufferedInputFile(photo_bytes, "outfit.png"),
                            caption=caption,
                            reply_markup=kb([[btn("🏠 Меню", "menu")]])
                        )
                        sent = True
                        break
            except Exception:
                continue

    if not sent:
        # Если фото не удалось — показываем текст
        if data:
            await m.answer(caption + "\n\n⚠️ Фото персонажа недоступно",
                           reply_markup=kb([[btn("🏠 Меню", "menu")]]))
        else:
            await m.answer(
                f"❌ Игрок <code>{player_uid}</code> не найден.\n"
                f"Попробуй: <code>/look {player_uid} cis</code>",
                reply_markup=kb([[btn("🏠 Меню", "menu")]])
            )


# ===================== /guild — информация о гильдии =====================
async def cmd_guild(m):
    """/guild <guild_id> [регион] — информация о гильдии."""
    args = (m.text or "").split()
    if len(args) < 2 or not args[1].isdigit():
        await m.answer(
            "🏠 <b>Информация о гильдии</b>\n\n"
            "Использование: <code>/guild GUILD_ID [регион]</code>\n"
            "Пример: <code>/guild 3084953066 cis</code>\n\n"
            "💡 ID гильдии можно узнать командой <code>/ff UID</code>"
        )
        return
    guild_id = args[1]
    region = args[2].lower() if len(args) > 2 else "sg"
    wait_msg = await m.answer("⏳ Загружаю информацию о гильдии...")

    guild_data = None
    apis = [
        f"https://ff-info-api.vercel.app/guild?guildid={guild_id}&region={region}",
        f"https://freefireinfo.vercel.app/api/guild?id={guild_id}&region={region}",
    ]
    async with aiohttp.ClientSession() as s:
        for url in apis:
            try:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status == 200:
                        d = await r.json(content_type=None)
                        if isinstance(d, dict) and (d.get("GuildName") or d.get("name") or d.get("clanname")):
                            guild_data = d
                            break
            except Exception:
                continue

    try:
        await wait_msg.delete()
    except Exception:
        pass

    if not guild_data:
        await m.answer(
            f"❌ Гильдия <code>{guild_id}</code> не найдена.\n"
            f"Попробуй указать регион: <code>/guild {guild_id} cis</code>",
            reply_markup=kb([[btn("🏠 Меню", "menu")]])
        )
        return

    g = guild_data
    name   = g.get("GuildName")  or g.get("name")     or g.get("clanname",  "—")
    gid    = g.get("GuildID")    or g.get("id")        or g.get("clanid",    guild_id)
    level  = g.get("GuildLevel") or g.get("level")     or g.get("clanlevel", "—")
    mem    = g.get("MemberNum")  or g.get("currentmembers") or "—"
    cap    = g.get("GuildCapacity") or g.get("maxmembers") or "—"
    leader = g.get("GuildLeaderName") or g.get("leader") or "—"
    leader_id = g.get("GuildLeaderID") or g.get("leader_id") or "—"
    exp    = g.get("GuildExp")   or g.get("exp")       or "—"
    desc   = g.get("GuildDesc")  or g.get("description") or "—"

    text = (
        f"🏠 <b>Информация о гильдии</b>\n\n"
        f"🏷 Название: <b>{esc(str(name))}</b>\n"
        f"🆔 ID: <code>{gid}</code>\n"
        f"⭐ Уровень: {level}\n"
        f"👥 Участники: {mem}/{cap}\n"
        f"👑 Лидер: {esc(str(leader))}"
    )
    if str(leader_id) not in ("—", "0", ""):
        text += f" (<code>{leader_id}</code>)"
    if str(exp) not in ("—", "0", ""):
        text += f"\n📊 Опыт: {exp}"
    if str(desc) not in ("—", "", "null"):
        text += f"\n📝 Описание: {esc(str(desc))}"

    await m.answer(text, reply_markup=kb([[btn("🏠 Меню", "menu")]]))


# ===================== /age — возраст аккаунта =====================
async def cmd_age(m):
    """/age <uid> [регион] — возраст аккаунта Free Fire."""
    args = (m.text or "").split()
    if len(args) < 2 or not args[1].isdigit():
        await m.answer(
            "📅 <b>Возраст аккаунта</b>\n\n"
            "Использование: <code>/age UID [регион]</code>\n"
            "Пример: <code>/age 9905658934 cis</code>"
        )
        return
    player_uid = args[1]
    region = args[2].lower() if len(args) > 2 else "sg"
    wait_msg = await m.answer("⏳ Получаю данные аккаунта...")

    regions_to_try = [region] if region != "sg" else ["sg", "cis", "ind", "br", "id"]
    data = None
    for reg in regions_to_try:
        data = await fetch_ff_player(player_uid, reg)
        if data:
            break

    try:
        await wait_msg.delete()
    except Exception:
        pass

    if not data:
        await m.answer(
            f"❌ Игрок <code>{player_uid}</code> не найден.\n"
            f"Попробуй: <code>/age {player_uid} cis</code>",
            reply_markup=kb([[btn("🏠 Меню", "menu")]])
        )
        return

    basic = data.get("basicinfo") or data.get("AccountInfo") or data
    name = basic.get("nickname") or basic.get("Nickname") or basic.get("name") or player_uid
    created_ts = basic.get("createat") or basic.get("CreateAt") or basic.get("created_at")
    last_ts = basic.get("lastloginat") or basic.get("LastLoginAt") or basic.get("last_login")

    def fmt_ts(ts):
        try:
            return datetime.fromtimestamp(int(ts), TZ)
        except Exception:
            return None

    now_dt = datetime.now(TZ)
    created_dt = fmt_ts(created_ts)
    last_dt = fmt_ts(last_ts)

    text = f"📅 <b>Возраст аккаунта</b>\n\n👤 Игрок: <b>{esc(str(name))}</b>\n🆔 UID: <code>{player_uid}</code>\n\n"

    if created_dt:
        age = now_dt - created_dt
        years = age.days // 365
        months = (age.days % 365) // 30
        days = age.days % 30
        text += (
            f"🗓 Дата создания: <b>{created_dt.strftime('%d %b %Y, %H:%M')}</b>\n"
            f"⏳ Возраст аккаунта: <b>{years} г. {months} мес. {days} дн.</b>\n"
            f"📆 Дней с создания: <b>{age.days}</b>\n\n"
        )
    else:
        text += "🗓 Дата создания: не указана\n\n"

    if last_dt:
        diff = now_dt - last_dt
        if diff.days == 0:
            last_str = "сегодня"
        elif diff.days == 1:
            last_str = "вчера"
        else:
            last_str = f"{diff.days} дней назад"
        text += f"🟢 Последний вход: <b>{last_dt.strftime('%d %b %Y, %H:%M')}</b> ({last_str})"
    else:
        text += "🟢 Последний вход: неизвестно"

    await m.answer(text, reply_markup=kb([[btn("🏠 Меню", "menu")]]))


# ===================== /bio — биография игрока =====================
async def cmd_bio(m):
    """/bio <uid> [регион] — биография и описание профиля."""
    args = (m.text or "").split()
    if len(args) < 2 or not args[1].isdigit():
        await m.answer(
            "📝 <b>Биография игрока</b>\n\n"
            "Использование: <code>/bio UID [регион]</code>\n"
            "Пример: <code>/bio 9905658934 cis</code>"
        )
        return
    player_uid = args[1]
    region = args[2].lower() if len(args) > 2 else "sg"
    wait_msg = await m.answer("⏳ Загружаю профиль игрока...")

    regions_to_try = [region] if region != "sg" else ["sg", "cis", "ind", "br", "id"]
    data = None
    for reg in regions_to_try:
        data = await fetch_ff_player(player_uid, reg)
        if data:
            break

    try:
        await wait_msg.delete()
    except Exception:
        pass

    if not data:
        await m.answer(
            f"❌ Игрок <code>{player_uid}</code> не найден.\n"
            f"Попробуй: <code>/bio {player_uid} cis</code>",
            reply_markup=kb([[btn("🏠 Меню", "menu")]])
        )
        return

    basic  = data.get("basicinfo")  or data.get("AccountInfo") or data
    social = data.get("socialinfo") or data.get("SocialInfo")  or {}
    clan   = data.get("claninfo")   or data.get("GuildInfo")   or {}
    rank   = data.get("rankinfo")   or data.get("RankInfo")    or {}

    name     = basic.get("nickname")  or basic.get("Nickname")  or basic.get("name",  player_uid)
    level    = basic.get("level")     or basic.get("Level")     or "—"
    region_s = basic.get("region")    or basic.get("Region")    or "—"
    liked    = basic.get("liked")     or basic.get("Liked")     or "0"
    badges   = basic.get("badge_cnt") or basic.get("BadgeCount") or "—"
    honor    = basic.get("honor_score") or basic.get("HonorScore") or "—"
    bio_text = (social.get("bio") or social.get("Bio") or
                basic.get("bio") or basic.get("signature") or "")
    gender   = social.get("gender")   or social.get("Gender")   or basic.get("gender") or "—"
    lang     = social.get("language") or social.get("Language") or "—"
    mode     = social.get("mode_prefer") or social.get("ModePrefer") or "—"
    act_type = basic.get("accounttype") or basic.get("AccountType") or "—"

    # Лайки в красивом формате
    def fmt_num(n):
        try:
            n = int(n)
            if n >= 1000000:
                return f"{n/1000000:.1f}M"
            if n >= 1000:
                return f"{n/1000:.1f}K"
            return str(n)
        except Exception:
            return str(n)

    clan_name = clan.get("clanname") or clan.get("GuildName") or "Нет гильдии"
    br_rank   = rank.get("BRRankPoint") or rank.get("br_rank") or "—"
    cs_rank   = rank.get("CSRankPoint") or rank.get("cs_rank") or "—"

    text = (
        f"📝 <b>Профиль игрока</b>\n\n"
        f"👤 Имя: <b>{esc(str(name))}</b>\n"
        f"🆔 UID: <code>{player_uid}</code>\n"
        f"🌍 Регион: {region_s}\n"
        f"⭐ Уровень: {level}\n"
        f"❤️ Лайки: {fmt_num(liked)}\n"
        f"🏅 Значков: {badges}\n"
        f"⚖️ Honor: {honor}\n"
        f"🏠 Гильдия: {esc(str(clan_name))}\n"
        f"🏆 BR Ранг: {br_rank}\n"
        f"🎯 CS Ранг: {cs_rank}\n"
        f"⚧ Пол: {gender}\n"
        f"🗣 Язык: {lang}\n"
        f"🎮 Любимый режим: {mode}\n"
        f"👻 Тип аккаунта: {act_type}\n"
    )

    if bio_text:
        text += f"\n💬 <b>Биография:</b>\n<i>{esc(str(bio_text))}</i>"
    else:
        text += "\n💬 <b>Биография:</b> не указана"

    await m.answer(text, reply_markup=kb([[btn("🏠 Меню", "menu")]]))


@dp.callback_query(F.data.startswith("game:"))
async def cb_game(c):
    await c.answer()
    await load_catalog()
    found = match_game(c.data.split(":")[1])
    if found:
        await show_category(c, found)
    else:
        await c.message.answer(t(c.from_user.id, "nf"),
                               reply_markup=cta_kb(c.from_user.id))


@dp.callback_query(F.data.startswith("allp:"))
async def cb_allp(c):
    await c.answer()
    await load_catalog()
    await show_all_games(c, int(c.data.split(":")[1]))


async def show_all_games(c, page):
    uid = c.from_user.id
    ids = list(catalog.keys())
    priority = []
    for game_key in ("ff_cis", "ff_id", "pubg_us"):
        matched = match_game(game_key)
        if matched in ids and matched not in priority:
            priority.append(matched)
    ids = priority + [cid for cid in ids if cid not in priority]
    chunk = ids[page * GAMES_PER_PAGE:(page + 1) * GAMES_PER_PAGE]
    rows = [[btn(catalog[cid]["name"][:40], f"cat:{sid(cid)}")] for cid in chunk]
    nav = []
    if page > 0:
        nav.append(btn(t(uid, "prev"), f"allp:{page - 1}"))
    if (page + 1) * GAMES_PER_PAGE < len(ids):
        nav.append(btn(t(uid, "next"), f"allp:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([btn(t(uid, "menu"), "menu")])
    await edit_or_send(c.message, t(uid, "games_title"), kb(rows))


@dp.callback_query(F.data.startswith("cat:"))
async def cb_cat(c):
    await c.answer()
    await load_catalog()
    cid = cat_short.get(c.data.split(":")[1])
    if cid is None:
        await c.message.answer(t(c.from_user.id, "nf"), reply_markup=cta_kb(c.from_user.id))
        return
    await show_category(c, cid)


def group_of(p):
    n = (str(p.get("name", "")) + " " + str(p.get("title") or "")).lower()
    if "diamond" in n or "алмаз" in n or re.search(r"\buc\b", n):
        return "💎 Алмос / UC"
    if any(w in n for w in ("weekly", "monthly", "voucher", "prime", "pass")):
        return "🎫 Ваучерҳо"
    if "level" in n or "evo" in n:
        return "🚀 Прокачка"
    return "🎁 Дигар"


async def show_category(c, cid):
    uid = c.from_user.id
    user_category[uid] = cid
    lang = get_user(uid)["lang"]
    g = catalog.get(cid)
    if not g:
        await c.message.answer(t(uid, "nf"), reply_markup=cta_kb(uid))
        return
    groups = {}
    for p in g["products"]:
        groups.setdefault(group_of(p), []).append(p)
    text = f"<b>{esc(g['name'])}</b>\n━━━ {t(uid, 'pick_pkg')}\n"
    rows, total = [], 0
    selecting = bool(get_user(uid).get("cart_select_mode"))
    cart_items = get_user(uid).setdefault("cart_items", [])
    for grp, prods in groups.items():
        text += f"\n━━ {grp} ━━"
        product_row = []
        for p in prods:
            if total >= 90:
                break
            total += 1
            product_key = sid(p["product_id"])
            entry = next((x for x in cart_items if str(x.get("product_id")) == str(p["product_id"])), None)
            qty = int(entry.get("qty", 0)) if entry else 0
            label = f"{ptitle(p, lang)[:18]} · {p['price_tjs']} с."
            # Два товара в одной строке — компактная сетка для мобильного экрана.
            product_row.append(btn(label, f"cartadd:{product_key}" if selecting else f"pkg:{product_key}"))
            if len(product_row) == 2:
                rows.append(product_row)
                product_row = []
            if selecting and qty:
                rows.append([btn("➖", f"cartitem:{product_key}:-1"),
                             btn(f"{qty} шт.", f"cartitem:{product_key}:0"),
                             btn("➕", f"cartitem:{product_key}:1")])
        if product_row:
            rows.append(product_row)
    rows.append([btn("☑️ Выбрать несколько товаров" if not selecting else "✅ Завершить выбор",
                     "cartmode:1" if not selecting else "cartmode:0")])
    if selecting:
        rows.append([btn(f"🛒 Корзина ({sum(int(x.get('qty', 0)) for x in cart_items)})", "cart_info")])
    rows.append(nav_row(uid, "menu"))
    await edit_or_send(c.message, text, kb(rows))


async def prompt_player_id(msg, uid, product, back="menu"):
    user_state[uid] = {"stage": "waiting_id", "product": product, "back": back}
    lang = get_user(uid)["lang"]
    saved = [x for x in (get_user(uid).get("saved_ids") or []) if x.get("id")]
    rows = []
    for item in saved[:6]:
        label = str(item["id"])
        if item.get("nick"):
            label = f"{str(item['nick'])[:14]} · {item['id']}"
        rows.append([btn(label[:40], f"useid:{item['id']}")])
    text = t(uid, "enter_id", title=esc(ptitle(product, lang)), price=product["price_tjs"])
    if saved:
        text += "\n\n" + t(uid, "saved_hint")
    await msg.answer(text, reply_markup=kb(rows + [nav_row(uid, back)]))


async def offer_id_confirm(msg, uid, product, player_id):
    try:
        await msg.bot.send_chat_action(msg.chat.id, "typing")
    except Exception:
        pass
    nick = await lookup_player_nick(product, player_id)
    remember_player_id(uid, player_id, nick, ptitle(product, get_user(uid)["lang"]))
    back = user_state.get(uid, {}).get("back", "menu")
    tok = new_pending(uid=uid, pid=str(player_id), product=product, nick=nick, back=back)
    user_state.pop(uid, None)
    nick_line = f"\n{t(uid, 'nick_found', nick=esc(nick))}" if nick else f"\n{t(uid, 'nick_not_found')}"
    await msg.answer(
        t(uid, "confirm_id", pid=player_id) + nick_line,
        reply_markup=kb([[btn(t(uid, "id_ok"), f"idok:{tok}"),
                          btn(t(uid, "id_edit"), f"idedit:{tok}")],
                         nav_row(uid, "menu")]))


@dp.callback_query(F.data.startswith("pkg:"))
async def cb_pkg(c):
    uid = c.from_user.id
    u = get_user(uid, c.from_user.full_name or "")
    if u["blocked"]:
        await c.answer(t(uid, "blocked"), show_alert=True)
        return
    p = prod_short.get(c.data.split(":")[1])
    if not p:
        await c.answer(t(uid, "nf"), show_alert=True)
        return
    cid = p.get("category_id")
    back = f"cat:{sid(cid)}" if cid is not None else "menu"
    await prompt_player_id(c.message, uid, p, back=back)
    await c.answer()


# ===================== Stars / Premium =====================
@dp.callback_query(F.data == "tg_stars")
async def cb_stars(c):
    uid = c.from_user.id
    await load_catalog()
    rows = []
    if special["stars"]:
        unit = special["stars"]["unit"]
        for q in (50, 100, 250, 500, 1000):
            if special["stars"]["min"] <= q <= special["stars"]["max"]:
                rows.append([btn(f"⭐ {q} — {tjs(unit * q)} с.", f"stq:{q}")])
    for pid, p in special["premium"].items():
        if pid.startswith("tg-premium-"):
            rows.append([btn(f"👑 Premium {pid.split('-')[-1]} {t(uid, 'months')} — {tjs(float(p['price_usd']))} с.",
                             f"prq:{pid}")])
    rows.append([btn(t(uid, "menu"), "menu")])
    await edit_or_send(c.message, t(uid, "stars_title"), kb(rows))
    await c.answer()


@dp.callback_query(F.data.startswith(("stq:", "prq:")))
async def cb_star_pick(c):
    uid = c.from_user.id
    if get_user(uid, c.from_user.full_name or "")["blocked"]:
        await c.answer(t(uid, "blocked"), show_alert=True)
        return
    kind, val = c.data.split(":", 1)
    if kind == "stq":
        if not special["stars"]:
            await c.answer(t(uid, "unavail"), show_alert=True)
            return
        qty = int(val)
        s = special["stars"]
        if not (s["min"] <= qty <= s["max"]):
            await c.answer(t(uid, "unavail"), show_alert=True)
            return
        user_state[uid] = {"stage": "waiting_uname", "title": f"⭐ {qty} Stars",
                           "base": tjs(s["unit"] * qty), "cost_usd": s["unit"] * qty,
                           "body": {"product_id": "tg-stars", "quantity": qty}}
    else:
        p = special["premium"].get(val)
        if not p:
            await c.answer(t(uid, "nf"), show_alert=True)
            return
        lang = get_user(uid)["lang"]
        user_state[uid] = {"stage": "waiting_uname", "title": f"👑 {ptitle(p, lang)}",
                           "base": tjs(float(p["price_usd"])), "cost_usd": float(p["price_usd"]),
                           "body": {"product_id": val}}
    st = user_state[uid]
    await c.message.answer(f"{esc(st['title'])} — {st['base']} с.\n\n{t(uid, 'enter_uname')}")
    await c.answer()


# ===================== Web App =====================
@dp.message(F.web_app_data)
async def webapp_data(m):
    uid = m.from_user.id
    if get_user(uid, m.from_user.full_name or "")["blocked"]:
        await m.answer(t(uid, "blocked"))
        return
    try:
        pid = json.loads(m.web_app_data.data).get("p")
    except Exception:
        return
    p = prod_short.get(pid)
    if not p:
        await m.answer(t(uid, "nf"))
        return
    await prompt_player_id(m, uid, p, back="menu")


# ===================== Ввод текста =====================
def parse_amount(txt):
    try:
        v = float(txt.strip().replace(",", "."))
    except ValueError:
        return None
    return round(v, 2) if v == v and MIN_TOPUP <= v <= MAX_TOPUP else None


@dp.message(F.text)
async def text_handler(m):
    uid = m.from_user.id
    st = user_state.get(uid)
    if not st:
        return
    txt = m.text.strip()
    stage = st["stage"]
    get_user(uid, m.from_user.full_name or "")

    if stage == "waiting_id":
        if txt.isdigit() and 6 <= len(txt) <= 15:
            await offer_id_confirm(m, uid, st["product"], txt)
        else:
            await m.answer(t(uid, "bad_id"))

    elif stage == "waiting_uname":
        if re.fullmatch(r"@[A-Za-z0-9_]{5,32}", txt):
            user_state.pop(uid, None)
            body = {**st["body"], "fields": {"telegram_username": txt}}
            await ask_confirm(m, uid, st["title"], txt, st["base"], st["cost_usd"], body)
        else:
            await m.answer(t(uid, "bad_uname"))

    elif stage == "cart_wait_ids":
        if not re.fullmatch(r"\d{6,15}", txt):
            await m.answer("❌ ID должен содержать 6–15 цифр. Повторите ввод:")
            return
        idx = int(st.get("index", 0)); product = st["items"][idx]
        nick = await lookup_player_nick(product, txt)
        st["targets"].append({"id": txt, "nick": nick})
        st["index"] = idx + 1
        if st["index"] < len(st["items"]):
            pnext = st["items"][st["index"]]
            await m.answer(f"✅ ID сохранён{(' · Ник: '+esc(nick)) if nick else ''}.\nВведите ID для товара {st['index']+1}/{len(st['items'])}: <b>{esc(ptitle(pnext,get_user(uid)['lang']))}</b>")
        else:
            st["stage"] = "cart_confirm"
            lines = ["🧾 <b>Проверьте корзину перед оплатой</b>"]
            for i,(p,target) in enumerate(zip(st["items"],st["targets"]),1):
                lines.append(f"{i}. {esc(ptitle(p,get_user(uid)['lang']))} — {float(p['price_tjs']):.2f} с.\n   ID: <code>{target['id']}</code> · Ник: <b>{esc(target['nick'] or 'не найден')}</b>")
            lines.append("\nЕсли ID или ник неверный — отмените и начните заново.")
            await m.answer("\n".join(lines),reply_markup=kb([[btn("✅ Подтвердить все","cartconfirm"),btn("❌ Отмена","cancel")]]))

    elif is_admin(uid) and stage == "adm_search_user":
        query = txt.lower().strip().lstrip("@")
        matches = [(k, u) for k, u in db["users"].items()
                   if query in k or query in str(u.get("username", "")).lower()
                   or query in str(u.get("name", "")).lower()
                   or query == str(u.get("customer_no", ""))]
        user_state.pop(uid, None)
        matches = matches[:20]
        if not matches:
            await m.answer("Харидор ёфт нашуд.", reply_markup=kb([[btn("🔎 Ҷустуҷӯи дигар", "adm_search")], [btn("🔙 Админ", "admin")]]))
        else:
            rows = [[btn(f"№{u.get('customer_no', 0)} · {u.get('name') or k} · {u.get('username') and '@'+u.get('username') or k}", f"adu:{k}")] for k,u in matches]
            rows.append([btn("🔎 Ҷустуҷӯи дигар", "adm_search"), btn("🔙 Админ", "admin")])
            await m.answer(f"Натиҷаҳо: {len(matches)}", reply_markup=kb(rows))

    elif stage == "topup_custom":
        v = parse_amount(txt)
        if v is None:
            await m.answer(t(uid, "bad_amt", min=f"{MIN_TOPUP:g}", max=f"{MAX_TOPUP:g}"))
            return
        mk = st.get("method", list(PAY_METHODS.keys())[0] if PAY_METHODS else "dc")
        user_state.pop(uid, None)
        await start_topup(m, uid, v, mk)

    elif stage == "promo":
        user_state.pop(uid, None)
        code = txt.upper()
        p = db["promos"].get(code)
        if promo_valid(p, uid):
            get_user(uid)["promo"] = code
            save_db()
            await m.answer(t(uid, "promo_ok", pct=p["percent"]))
        else:
            await m.answer(t(uid, "promo_bad"))

    # ===================== Отзыв — ввод текста =====================
    elif stage == "review_text":
        user_state.pop(uid, None)
        stars = st.get("stars", 5)
        order_title = st.get("title", "")
        review_text = txt if txt != "/skip" else ""
        db.setdefault("reviews", []).append({"uid": uid, "stars": int(stars),
            "title": order_title[:120], "text": review_text[:1000], "ts": now_ts()})
        db["reviews"] = db["reviews"][-2000:]
        save_db()
        # Пересылаем отзыв в канал
        if REVIEWS_CHANNEL_ID:
            try:
                msg_text = (
                    f"⭐ {'★' * stars}{'☆' * (5 - stars)}\n"
                    f"📦 {esc(order_title)}\n"
                    f"👤 {esc(m.from_user.full_name)} (ID {uid})\n"
                    f"💬 {esc(review_text) if review_text else '—'}"
                )
                await bot.send_message(REVIEWS_CHANNEL_ID, msg_text)
            except Exception as e:
                log.warning("review send: %s", e)
        await m.answer(t(uid, "review_thanks"))

    elif is_admin(uid) and stage == "adm_addbal":
        try:
            v = float(txt.replace(",", "."))
            assert v != 0 and abs(v) <= 100000
        except Exception:
            await m.answer("❌ Рақам лозим (масалан 50 ё -20)")
            return
        target = st["target"]
        user_state.pop(uid, None)
        tu = get_user(target)
        tu["balance"] = round(tu["balance"] + v, 2)
        add_transaction(target, v, "topup", "Админ")
        save_db()
        await m.answer(f"✅ Баланс {esc(tu['name'])}: {tu['balance']:.2f} с.")
        try:
            await bot.send_message(int(target), t(target, "topup_done", amount=f"{v:.2f}",
                                                  bal=f"{tu['balance']:.2f}"))
        except Exception:
            pass

    elif is_admin(uid) and stage == "adm_setdisc":
        try:
            v = float(txt.replace(",", ".").replace("%", ""))
            assert 0 <= v <= 90
        except Exception:
            await m.answer("❌ Фоиз 0–90 лозим (масалан 10)")
            return
        target = st["target"]
        user_state.pop(uid, None)
        tu = get_user(target)
        tu["discount_percent"] = round(v, 2)
        save_db()
        await m.answer(f"✅ Скидка барои {esc(tu.get('name') or target)}: {v:g}%")

    elif is_admin(uid) and stage == "adm_promo_new":
        parts = txt.split()
        try:
            code = parts[0].upper()
            percent = int(parts[1])
            max_uses = int(parts[2]) if len(parts) > 2 else 0
            assert re.fullmatch(r"[A-Z0-9_-]{3,20}", code) and 1 <= percent <= 90 and max_uses >= 0
        except Exception:
            await m.answer("❌ Формат: КОД ПРОЦЕНТ [МАКС_ИСПОЛЬЗОВАНИЙ]\nМисол: SALE10 10 100")
            return
        user_state.pop(uid, None)
        db["promos"][code] = {"percent": percent, "max_uses": max_uses, "used": 0,
                              "active": True, "users": []}
        save_db()
        await m.answer(f"✅ Промокод <code>{code}</code>: -{percent}%, лимит: {max_uses or '∞'}")

    elif is_admin(uid) and stage == "adm_broadcast":
        user_state.pop(uid, None)
        ids = [int(k) for k, u in db["users"].items() if not u.get("blocked")]
        await m.answer(f"📢 Фиристода истодааст: {len(ids)}...")
        ok = 0
        for i in ids:
            try:
                # Вместе с рассылкой снимаем старую кнопку Shop
                await bot.send_message(i, txt, reply_markup=ReplyKeyboardRemove())
                ok += 1
            except Exception:
                pass
            await asyncio.sleep(0.05)
        await m.answer(f"✅ Расонида шуд: {ok}/{len(ids)}")


# ===================== Антифрод — подтверждение ID =====================
@dp.callback_query(F.data.startswith("useid:"))
async def cb_useid(c):
    uid = c.from_user.id
    st = user_state.get(uid)
    player_id = c.data.split(":", 1)[1]
    if not st or st.get("stage") != "waiting_id" or not re.fullmatch(r"\d{6,15}", player_id):
        await c.answer(t(uid, "expired"), show_alert=True)
        return
    await c.answer()
    await offer_id_confirm(c.message, uid, st["product"], player_id)


@dp.callback_query(F.data.startswith("idok:"))
async def cb_id_ok(c):
    """Пользователь подтвердил корректность введённого ID."""
    uid = c.from_user.id
    tok = c.data.split(":")[1]
    data = pend.get(tok)
    if not data or data["uid"] != uid:
        await c.answer(t(uid, "expired"), show_alert=True)
        return
    pend.pop(tok, None)
    await c.answer()
    p = data["product"]
    pid = data["pid"]
    lang = get_user(uid)["lang"]
    nick = data.get("nick") or await lookup_player_nick(p, pid)
    remember_player_id(uid, pid, nick, ptitle(p, lang))
    target = f"{pid} ({nick})" if nick else pid
    await ask_confirm(c.message, uid, ptitle(p, lang), target, p["price_tjs"],
                      float(p.get("price_usd", 0)),
                      {"product_id": p["product_id"], "fields": {"player_id": pid}})


@dp.callback_query(F.data.startswith("idedit:"))
async def cb_id_edit(c):
    """Пользователь хочет исправить ID — возвращаем к вводу."""
    uid = c.from_user.id
    tok = c.data.split(":")[1]
    data = pend.get(tok)
    if not data or data["uid"] != uid:
        await c.answer(t(uid, "expired"), show_alert=True)
        return
    p = data.get("product")
    pend.pop(tok, None)
    if p:
        await prompt_player_id(c.message, uid, p, back=data.get("back") or "menu")
    await c.answer()


@dp.callback_query(F.data == "cancel")
async def cb_cancel(c):
    user_state.pop(c.from_user.id, None)
    await edit_or_send(c.message, t(c.from_user.id, "cancelled"))
    await c.answer()


# ===================== Заказы =====================
async def ask_confirm(m, uid, title, target, base, cost_usd, body):
    u = get_user(uid)
    price, code, _, user_disc = final_price(uid, base)
    promo = ""
    if user_disc > 0:
        promo = t(uid, "user_discount_line", pct=f"{user_disc:g}")
    elif code:
        promo = t(uid, "promo_line", pct=db["promos"][code]["percent"])
    tok = new_pending(uid=uid, title=title, base=base, cost_usd=cost_usd, body=body)
    await m.answer(t(uid, "confirm_q", title=esc(title), target=esc(target), price=price, promo=promo),
                   reply_markup=kb([[btn(t(uid, "ok"), f"cfm:{tok}"), btn(t(uid, "cancel"), "cancel")]]))


@dp.callback_query(F.data.startswith("cfm:"))
async def cb_confirm(c):
    uid = c.from_user.id
    tok = c.data.split(":")[1]
    data = pend.get(tok)
    if not data or data["uid"] != uid:
        await c.answer(t(uid, "expired"), show_alert=True)
        return
    pend.pop(tok, None)
    await c.answer("⏳")
    try:
        await c.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await create_order(uid, c.message.chat.id, data["title"], data["base"], data["cost_usd"], data["body"])


async def refund(u, rec, price):
    u["balance"] = round(u["balance"] + price, 2)
    rec["status"] = "failed"
    save_db()


async def notify_admin(text):
    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, text)
        except Exception as e:
            log.warning("notify_admin: %s", e)


async def create_order(uid, chat_id, title, base, cost_usd, body, notify=True):
    u = get_user(uid)
    if u["blocked"]:
        if notify:
            await bot.send_message(chat_id, t(uid, "blocked"))
        return {"ok": False, "error": "blocked"}
    lock = user_locks[uid]
    if lock.locked():
        if notify:
            await bot.send_message(chat_id, t(uid, "busy"))
        return {"ok": False, "error": "busy"}
    async with lock:
        price, code, _, user_disc = final_price(uid, base)
        if u["balance"] < price:
            if notify:
                await bot.send_message(
                    chat_id, t(uid, "low", price=price, bal=f"{u['balance']:.2f}"),
                    reply_markup=kb([[btn(t(uid, "topup"), "topup")]]))
            return {"ok": False, "error": "insufficient_balance",
                    "balance": round(u["balance"], 2), "price": price}
        # Reserve funds before calling the provider.
        u["balance"] = round(u["balance"] - price, 2)
        add_transaction(uid, -price, "order", title[:30])
        idem = str(uuid.uuid4())
        rec = {"oid": "?", "idem": idem, "uid": uid, "name": u["name"], "title": title,
               "product_id": str((body or {}).get("product_id") or ""), "price": price,
               "cost_usd": round(cost_usd, 4), "rate": usd_tjs, "promo": code,
               "status": "processing", "ts": now_ts()}
        db["orders"].append(rec)
        save_db()

        http, data = 0, {}
        try:
            async with aiohttp.ClientSession() as s:
                h = {**HEADERS, "Idempotency-Key": idem}
                async with s.post(f"{API}/orders", json=body, headers=h,
                                  timeout=aiohttp.ClientTimeout(total=45)) as r:
                    http = r.status
                    data = await r.json(content_type=None)
        except aiohttp.ClientConnectorError as e:
            await refund(u, rec, price)
            if notify:
                await bot.send_message(chat_id, t(uid, "order_err", err=esc(e)))
            return {"ok": False, "error": "provider_unavailable",
                    "balance": round(u["balance"], 2)}
        except Exception as e:
            rec["status"] = "uncertain"
            save_db()
            if notify:
                await bot.send_message(chat_id, t(uid, "order_wait"))
            await notify_admin(f"⚠️ Заказ не подтверждён (таймаут/сбой): {esc(u['name'])} ({uid})\n"
                               f"{esc(title)} · {price} с. · Idempotency-Key: <code>{idem}</code>\n{esc(e)}")
            return {"ok": False, "error": "order_uncertain",
                    "balance": round(u["balance"], 2)}

        if isinstance(data, dict) and data.get("ok"):
            oid = (data.get("order") or {}).get("order_id", "?")
            rec["oid"] = oid
            rec["status"] = "done"
            # Каждая успешно завершённая покупка открывает ещё одну настройку Free Fire.
            u["sensitivity_credits"] = int(u.get("sensitivity_credits", 0)) + 1

            if code:
                p = db["promos"].get(code)
                if p:
                    p["used"] = p.get("used", 0) + 1
                    p.setdefault("users", []).append(str(uid))
                u["promo"] = None
            save_db()
            if notify:
                await bot.send_message(chat_id, t(uid, "order_ok", oid=esc(oid), price=price,
                                                  bal=f"{u['balance']:.2f}"))
            await notify_admin(f"💸 Фурӯш: #{esc(oid)} · {esc(title)} · {price} с. · {esc(u['name'])}")
            if notify:
                await request_review(uid, chat_id, title)
            return {"ok": True, "order_id": str(oid), "price": price,
                    "balance": round(u["balance"], 2)}

        if http >= 500:
            rec["status"] = "uncertain"
            save_db()
            if notify:
                await bot.send_message(chat_id, t(uid, "order_wait"))
            await notify_admin(f"⚠️ Donatix HTTP {http}: {esc(u['name'])} ({uid}) {esc(title)} · {price} с.\n"
                               f"Idempotency-Key: <code>{idem}</code>")
            return {"ok": False, "error": "order_uncertain",
                    "balance": round(u["balance"], 2)}

        err = (data.get("error") if isinstance(data, dict) else None) or f"HTTP {http}"
        await refund(u, rec, price)
        if notify:
            await bot.send_message(chat_id, t(uid, "order_err", err=esc(err)))
        low = str(err).lower()
        if any(w in low for w in ("balance", "fund", "insufficient", "баланс")):
            await notify_admin(f"🚨 Баланс Donatix, эҳтимол, тамом шуд!\n{esc(err)}")
        return {"ok": False, "error": "provider_rejected",
                "balance": round(u["balance"], 2)}


# ===================== Система отзывов (пункт 10) =====================
async def request_review(uid, chat_id, title):
    """Отправляет пользователю запрос на оценку после успешного заказа."""
    try:
        rows = [[
            btn("🔴⭐ 1", f"rv:{uid}:1:{sid(title)}"),
            btn("🟠⭐ 2", f"rv:{uid}:2:{sid(title)}"),
            btn("🟡⭐ 3", f"rv:{uid}:3:{sid(title)}"),
            btn("🟢⭐ 4", f"rv:{uid}:4:{sid(title)}"),
            btn("🔵⭐ 5", f"rv:{uid}:5:{sid(title)}"),
        ]]
        # Сохраняем заголовок заказа во временном хранилище
        db["meta"][f"rv_title_{uid}"] = title
        await bot.send_message(chat_id, t(uid, "review_ask") + "\nВыберите цветную оценку:", reply_markup=kb(rows))
    except Exception as e:
        log.warning("request_review: %s", e)


@dp.callback_query(F.data.startswith("rv:"))
async def cb_review_stars(c):
    """Пользователь выбрал количество звёзд — просим написать текст отзыва."""
    parts = c.data.split(":")
    if len(parts) < 3:
        await c.answer()
        return
    uid = c.from_user.id
    stars = int(parts[2])
    title = db["meta"].get(f"rv_title_{uid}", "")
    user_state[uid] = {"stage": "review_text", "stars": stars, "title": title}
    try:
        await c.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await c.message.answer(t(uid, "review_text_ask") + "\n(необязательно — отправьте /skip)",
                           reply_markup=kb([[btn("Пропустить отзыв", "rvskip")],
                                            [btn(t(uid, "menu"), "menu")]]))
    await c.answer()


# ===================== Пополнение (ускоренный путь — пункт 5) =====================


@dp.callback_query(F.data == "rvskip")
async def cb_review_skip(c):
    uid = c.from_user.id
    st = user_state.get(uid)
    if not st or st.get("stage") != "review_text":
        await c.answer("Сеанс отзыва завершён", show_alert=True)
        return
    user_state.pop(uid, None)
    stars = int(st.get("stars", 5))
    title = str(st.get("title", ""))
    db.setdefault("reviews", []).append({"uid": uid, "stars": stars, "title": title[:120],
                                         "text": "", "ts": now_ts()})
    db["reviews"] = db["reviews"][-2000:]
    save_db()
    if REVIEWS_CHANNEL_ID:
        try:
            await bot.send_message(REVIEWS_CHANNEL_ID,
                f"⭐ {'★' * stars}{'☆' * (5-stars)}\n📦 {esc(title)}\n👤 ID {uid}\n💬 —")
        except Exception as e:
            log.warning("review skip send: %s", e)
    await c.message.answer(t(uid, "review_thanks"), reply_markup=kb([[btn(t(uid, "menu"), "menu")]]))
    await c.answer()


@dp.callback_query(F.data == "topup")
async def cb_topup(c):
    uid = c.from_user.id
    if get_user(uid, c.from_user.full_name or "")["blocked"]:
        await c.answer(t(uid, "blocked"), show_alert=True)
        return
    if not PAY_METHODS:
        await c.answer(t(uid, "no_pay"), show_alert=True)
        return
    # First screen contains only payment providers, as in the supplied reference.
    rows = [[btn(mm["title"], f"tm:{mk}")] for mk, mm in PAY_METHODS.items()]
    rows.append([btn(t(uid, "menu"), "menu")])
    await c.message.answer(t(uid, "choose_pay"), reply_markup=kb(rows))
    await c.answer()

async def _show_topup_amounts(c, uid, mk):
    """Показывает выбор суммы для конкретного метода оплаты."""
    rows = [[btn(f"{v} с.", f"tamt:{v}:{mk}") for v in (10, 20, 50)],
            [btn(f"{v} с.", f"tamt:{v}:{mk}") for v in (100, 200)],
            [btn(t(uid, "other"), f"tamt:custom:{mk}")],
            [btn(t(uid, "menu"), "menu")]]
    await edit_or_send(c.message, t(uid, "choose_amt", title=PAY_METHODS[mk]["title"]), kb(rows))


@dp.callback_query(F.data.startswith("tm:"))
async def cb_method(c):
    uid = c.from_user.id
    mk = c.data.split(":")[1]
    if mk not in PAY_METHODS:
        await c.answer(t(uid, "nf"), show_alert=True)
        return
    await _show_topup_amounts(c, uid, mk)
    await c.answer()


@dp.callback_query(F.data.startswith("tamt:"))
async def cb_topup_amount(c):
    uid = c.from_user.id
    parts = c.data.split(":")
    if len(parts) < 3:
        await c.answer()
        return
    _, v, mk = parts[0], parts[1], parts[2]
    if mk not in PAY_METHODS:
        await c.answer(t(uid, "nf"), show_alert=True)
        return
    await c.answer()
    if v == "custom":
        user_state[uid] = {"stage": "topup_custom", "method": mk}
        await c.message.answer(t(uid, "enter_amt", min=f"{MIN_TOPUP:g}", max=f"{MAX_TOPUP:g}"),
                               reply_markup=kb([[btn(t(uid, "menu"), "menu")]]))
    else:
        amount = parse_amount(v)
        if amount is None:
            await c.message.answer(t(uid, "bad_amt", min=f"{MIN_TOPUP:g}", max=f"{MAX_TOPUP:g}"))
            return
        await start_topup(c.message, uid, amount, mk)


async def start_topup(msg, uid, amount, mk):
    pm = PAY_METHODS[mk]
    tid = uuid.uuid4().hex[:8]
    db["topups"][tid] = {"uid": uid, "amount": amount, "method": mk, "status": "pending", "ts": now_ts()}
    save_db()
    user_state[uid] = {"stage": "receipt", "tid": tid}
    holder = f"\n👤 {esc(pm['holder'])}" if pm["holder"] else ""
    await msg.answer(t(uid, "topup_instr", title=pm["title"], number=esc(pm["number"]),
                       holder=holder, amount=f"{amount:.2f}"),
                     reply_markup=kb([[btn(t(uid, "menu"), "menu")]]))


@dp.message(F.photo | F.document)
async def got_receipt(m):
    uid = m.from_user.id
    st = user_state.get(uid)
    if not st or st.get("stage") != "receipt":
        return
    topup = db["topups"].get(st["tid"])
    if not topup or topup["status"] != "pending":
        return
    user_state.pop(uid, None)
    topup["status"] = "review"
    save_db()
    if not RECEIPTS_CHANNEL_ID:
        topup["status"] = "pending"
        user_state[uid] = st
        save_db()
        await m.answer("⚠️ Канал чеков ещё не настроен. Попробуйте позже или обратитесь в поддержку.",
                       reply_markup=kb([[btn(t(uid, "menu"), "menu")]]))
        return
    user = get_user(uid, m.from_user.full_name or "", m.from_user.username or "")
    caption = (f"🧾 НОВЫЙ ЧЕК · {st['tid']}\n"
              f"👤 {esc(m.from_user.full_name)} · @{esc(m.from_user.username or '—')}\n"
              f"🆔 ID: <code>{uid}</code> · № покупателя: <b>{user['customer_no']}</b>\n"
              f"💵 Пополнение: <b>{topup['amount']:.2f} с.</b>\n"
              f"💳 {esc(PAY_METHODS.get(topup['method'], {}).get('title', ''))}")
    try:
        await bot.copy_message(
            RECEIPTS_CHANNEL_ID, m.chat.id, m.message_id,
            caption=caption,
            reply_markup=kb([[btn("✅ Подтвердить", f"tok:{st['tid']}"),
                              btn("❌ Отклонить", f"tno:{st['tid']}")]])
        )
    except Exception as e:
        topup["status"] = "pending"
        user_state[uid] = st
        save_db()
        log.warning("receipt channel delivery: %s", e)
        await m.answer("⚠️ Не удалось отправить чек в канал. Попробуйте позже.",
                       reply_markup=kb([[btn(t(uid, "menu"), "menu")]]))
        return
    await m.answer(t(uid, "receipt_ok"), reply_markup=kb([[btn(t(uid, "menu"), "menu")]]))


@dp.callback_query(F.data.startswith("tok:"))
async def cb_topup_ok(c):
    if not is_admin(c.from_user.id):
        await c.answer("🚫", show_alert=True)
        return
    tid = c.data.split(":")[1]
    topup = db["topups"].get(tid)
    if not topup or topup["status"] not in ("pending", "review"):
        await c.answer("Аллакай кор шуд", show_alert=True)
        return
    topup["status"] = "done"
    uid = topup["uid"]
    u = get_user(uid)
    u["balance"] = round(u["balance"] + topup["amount"], 2)
    # Записываем транзакцию пополнения (пункт 6)
    add_transaction(uid, topup["amount"], "topup", PAY_METHODS.get(topup.get("method", ""), {}).get("title", ""))
    # Реферальный бонус — только с первого пополнения
    if not u["topped"]:
        u["topped"] = True
        rid = u.get("ref_by")
        if rid and rid in db["users"] and REF_PERCENT > 0:
            bonus = round(topup["amount"] * REF_PERCENT / 100, 2)
            ru = get_user(rid)
            ru["balance"] = round(ru["balance"] + bonus, 2)
            ru["ref_earned"] = round(ru["ref_earned"] + bonus, 2)
            add_transaction(rid, bonus, "topup", "Реферал")
            try:
                await bot.send_message(int(rid), t(rid, "ref_bonus", amount=f"{bonus:.2f}"))
            except Exception:
                pass
    save_db()
    try:
        await bot.send_message(uid, t(uid, "topup_done", amount=f"{topup['amount']:.2f}",
                                      bal=f"{u['balance']:.2f}"),
                               reply_markup=kb([[btn(t(uid, "menu"), "menu")]]))
    except Exception:
        pass
    original = c.message.caption or c.message.text or ""
    suffix = f"\n\n✅ Подтверждено: {esc(c.from_user.full_name)}"
    if c.message.caption is not None:
        await c.message.edit_caption(original + suffix, reply_markup=None)
    else:
        await c.message.edit_text(original + suffix, reply_markup=None)
    await c.answer()


@dp.callback_query(F.data.startswith("tno:"))
async def cb_topup_no(c):
    if not is_admin(c.from_user.id):
        await c.answer("🚫", show_alert=True)
        return
    tid = c.data.split(":")[1]
    topup = db["topups"].get(tid)
    if not topup or topup["status"] not in ("pending", "review"):
        await c.answer("Аллакай кор шуд", show_alert=True)
        return
    topup["status"] = "rejected"
    save_db()
    try:
        await bot.send_message(topup["uid"], t(topup["uid"], "topup_no"))
    except Exception:
        pass
    original = c.message.caption or c.message.text or ""
    suffix = f"\n\n❌ Отклонено: {esc(c.from_user.full_name)}"
    if c.message.caption is not None:
        await c.message.edit_caption(original + suffix, reply_markup=None)
    else:
        await c.message.edit_text(original + suffix, reply_markup=None)
    await c.answer()


# ===================== DONATEX: профиль, FAQ, AI и Free Fire sensitivity =====================
@dp.callback_query(F.data == "profile")
async def cb_profile(c):
    uid = c.from_user.id
    u = get_user(uid, c.from_user.full_name or "", c.from_user.username or "")
    orders = [o for o in db.get("orders", []) if str(o.get("uid")) == str(uid)]
    done = sum(1 for o in orders if o.get("status") == "done")
    await c.message.answer(
        f"👤 <b>Профили шумо</b>\n\n🆔 ID: <code>{uid}</code>\n"
        f"🔢 Рақами харидор: <b>№{u.get('customer_no', 0)}</b>\n"
        f"📛 Ном: {esc(u.get('name') or '—')}\n"
        f"🔗 Username: @{esc(u.get('username') or '—')}\n"
        f"💰 Баланс: <b>{u['balance']:.2f} с.</b>\n"
        f"📦 Фармоишҳо: {len(orders)} (иҷрошуда: {done})\n"
        f"🎯 Танзимоти ройгони дастрас: {int(not u.get('free_sensitivity_used')) + int(u.get('sensitivity_credits', 0))}",
        reply_markup=kb([[btn("💰 Пополнить", "topup"), btn("📦 Мои заказы", "my_orders")],
                         [btn("🏠 Меню", "menu")]]))
    await c.answer()


@dp.callback_query(F.data == "faq")
async def cb_faq(c):
    text = ("❓ <b>Частые вопросы DONATEX</b>\n\n"
            "<b>Как оплатить?</b>\nВыберите игру и товар, введите ID игрока и проверьте ник. Пополните баланс или оплатите доступным способом, затем подтвердите заказ.\n\n"
            "<b>Сколько ждать?</b>\nОбычно автоматическая обработка занимает 1–2 минуты. Если статус долго не меняется — обратитесь в поддержку.\n\n"
            "<b>Можно ли отменить заказ?</b>\nПосле отправки поставщику отмена может быть невозможна. Всегда проверяйте ID и ник до подтверждения.\n\n"
            "<b>Что делать, если ошибся в ID?</b>\nНе подтверждайте заказ, если показанный ник не ваш. После выполнения поставщиком возврат может быть невозможен.\n\n"
            "<b>Как отправить чек?</b>\nСоздайте пополнение, переведите точную сумму и отправьте фото чека в этом боте. Баланс зачислит администратор после проверки.\n\n"
            "<b>Как защититься от мошенников?</b>\nНе переводите деньги по просьбе неизвестных лиц. Все платежи и заявки оформляйте только через официальный бот DONATEX.")
    await c.message.answer(text, reply_markup=kb([[btn("🛟 Поддержка", "support")], [btn("🏠 Меню", "menu")]]))
    await c.answer()


@dp.callback_query(F.data == "cart_info")
async def cb_cart_info(c):
    uid = c.from_user.id
    u = get_user(uid)
    items = u.setdefault("cart_items", [])
    if not items:
        await c.message.answer("🛒 <b>Корзина пока пуста</b>\nОткройте игру и нажимайте «🛒 +» рядом с нужными товарами. Можно добавить разные пакеты и несколько одинаковых.",
                               reply_markup=kb([[btn("🎮 Все игры", "allp:0")], [btn("🏠 Меню", "menu")]]))
    else:
        await load_catalog()
        rows = []
        total = 0.0
        lines = ["🛒 <b>Ваша корзина</b>"]
        for i, item in enumerate(items[:20]):
            p = prod_short.get(sid(str(item.get("product_id"))))
            if not p:
                continue
            qty = max(1, min(20, int(item.get("qty", 1))))
            price = float(p.get("price_tjs", 0)) * qty
            total += price
            lines.append(f"{i+1}. {esc(ptitle(p, get_user(uid)['lang']))} × {qty} — {price:.2f} с.")
            rows.append([btn("➖", f"cartqty:{i}:-1"), btn(f"{qty} шт.", f"cartqty:{i}:0"), btn("➕", f"cartqty:{i}:1"), btn("🗑", f"cartdel:{i}")])
        lines.append(f"\n💰 <b>Итого: {total:.2f} с.</b>")
        rows += [[btn("✅ Оформить корзину", "cartcheckout")],
                 [btn("🧹 Очистить", "cartclear"), btn("🎮 Добавить товары", "allp:0")],
                 [btn("🏠 Меню", "menu")]]
        await c.message.answer("\n".join(lines), reply_markup=kb(rows))
    await c.answer()



@dp.callback_query(F.data.startswith("cartmode:"))
async def cb_cart_mode(c):
    uid = c.from_user.id
    get_user(uid)["cart_select_mode"] = c.data.endswith(":1")
    save_db()
    await c.answer("Режим выбора товаров включён" if c.data.endswith(":1") else "Выбор завершён")
    cid = user_category.get(uid)
    if cid is not None:
        await show_category(c, cid)
    else:
        await c.message.answer("Откройте игру, чтобы выбрать товары.",
                               reply_markup=kb([[btn("🎮 Все игры", "allp:0")],
                                                [btn("🛒 Корзина", "cart_info")],
                                                [btn("🏠 Меню", "menu")]]))


@dp.callback_query(F.data.startswith("cartitem:"))
async def cb_cart_item_qty(c):
    _, product_key, delta_s = c.data.split(":", 2)
    uid = c.from_user.id
    await load_catalog()
    product = prod_short.get(product_key)
    if not product:
        await c.answer("Товар недоступен", show_alert=True)
        return
    items = get_user(uid).setdefault("cart_items", [])
    entry = next((x for x in items if str(x.get("product_id")) == str(product["product_id"])), None)
    delta = int(delta_s)
    if delta > 0:
        if entry:
            entry["qty"] = min(20, int(entry.get("qty", 1)) + 1)
        else:
            items.append({"product_id": product["product_id"], "qty": 1})
    elif delta < 0 and entry:
        entry["qty"] = max(0, int(entry.get("qty", 1)) - 1)
        if entry["qty"] == 0:
            items.remove(entry)
    save_db()
    await c.answer("Корзина обновлена")
    cid = user_category.get(uid)
    if cid is not None:
        await show_category(c, cid)
    else:
        await c.message.answer("Количество обновлено.",
                               reply_markup=kb([[btn("🛒 Корзина", "cart_info")],
                                                [btn("🎮 Все игры", "allp:0")]]))


@dp.callback_query(F.data.startswith("cartadd:"))
async def cb_cart_add(c):
    uid = c.from_user.id
    await load_catalog()
    p = prod_short.get(c.data.split(":",1)[1])
    if not p:
        await c.answer("Товар больше недоступен", show_alert=True); return
    items = get_user(uid).setdefault("cart_items", [])
    entry = next((x for x in items if str(x.get("product_id")) == str(p["product_id"])), None)
    if entry:
        entry["qty"] = min(20, int(entry.get("qty",1)) + 1)
    else:
        items.append({"product_id":p["product_id"],"qty":1})
    save_db()
    await c.answer("Добавлено в корзину 🛒")
    cid = user_category.get(uid)
    if cid is not None:
        await show_category(c, cid)
    else:
        await c.message.answer("Добавлено в корзину 🛒",
                               reply_markup=kb([[btn("🛒 Открыть корзину", "cart_info")],
                                                [btn("🎮 Все игры", "allp:0")],
                                                [btn("🏠 Меню", "menu")]]))

@dp.callback_query(F.data.startswith("cartqty:"))
async def cb_cart_qty(c):
    parts=c.data.split(":"); idx=int(parts[1]); delta=int(parts[2]); items=get_user(c.from_user.id).setdefault("cart_items",[])
    if 0 <= idx < len(items) and delta:
        items[idx]["qty"] = max(1,min(20,int(items[idx].get("qty",1))+delta)); save_db()
    await cb_cart_info(c)

@dp.callback_query(F.data.startswith("cartdel:"))
async def cb_cart_del(c):
    idx=int(c.data.split(":")[1]); items=get_user(c.from_user.id).setdefault("cart_items",[])
    if 0 <= idx < len(items): items.pop(idx); save_db()
    await cb_cart_info(c)

@dp.callback_query(F.data == "cartclear")
async def cb_cart_clear(c):
    get_user(c.from_user.id)["cart_items"]=[]; save_db()
    await cb_cart_info(c)

@dp.callback_query(F.data == "cartcheckout")
async def cb_cart_checkout(c):
    uid=c.from_user.id; await load_catalog(); items=[]
    for entry in get_user(uid).get("cart_items",[]):
        p=prod_short.get(sid(str(entry.get("product_id"))))
        if p:
            for _ in range(max(1,min(20,int(entry.get("qty",1))))): items.append(p)
    if not items:
        await c.answer("Корзина пуста",show_alert=True); return
    if len(items)>20:
        await c.answer("Максимум 20 единиц за один раз",show_alert=True); return
    user_state[uid]={"stage":"cart_wait_ids","items":items,"index":0,"targets":[]}
    await c.answer()
    await c.message.answer(f"🛒 В корзине {len(items)} товар(ов).\n\nВведите ID игрока для товара 1/{len(items)}: <b>{esc(ptitle(items[0],get_user(uid)['lang']))}</b>")

@dp.callback_query(F.data == "cartconfirm")
async def cb_cart_confirm(c):
    uid=c.from_user.id; st=user_state.get(uid)
    if not st or st.get("stage")!="cart_confirm":
        await c.answer("Сеанс корзины устарел",show_alert=True); return
    await c.answer("Оформляем…")
    items=st["items"]; targets=st["targets"]
    user_state.pop(uid,None)
    for p, target in zip(items,targets):
        result=await create_order(uid,uid,ptitle(p,get_user(uid)['lang']),float(p['price_tjs']),float(p.get('price_usd',0)),
            {"product_id":p["product_id"],"fields":{"player_id":target["id"]}},notify=True)
        if not result.get("ok"):
            await c.message.answer("⚠️ Корзина остановлена: один из заказов не прошёл. Остальные товары не оформлялись.")
            return
    get_user(uid)["cart_items"]=[]; save_db()
    await c.message.answer("✅ Все товары из корзины успешно отправлены в обработку.",reply_markup=kb([[btn("🏠 Меню","menu")]]))


FF_DEVICES = ["iPhone 11", "iPhone 12 / 13", "iPhone 14 / 15", "iPhone 16 / 17",
              "Samsung Galaxy", "Xiaomi / Redmi", "POCO", "Realme", "Tecno / Infinix", "Другая модель"]
FF_SENS = [("Обзор", 200), ("Коллиматор", 190), ("2x Прицел", 185),
           ("4x Прицел", 180), ("Снайперский прицел", 170), ("Кнопка свободной камеры", 160)]

@dp.callback_query(F.data == "ff_sens")
async def cb_ff_sens(c):
    rows = [[btn(d, "ffdev:" + str(i))] for i, d in enumerate(FF_DEVICES)]
    rows.append([btn("🏠 Меню", "menu")])
    await c.message.answer("🎯 <b>Настройка Free Fire</b>\nВыберите модель телефона. Подберём стартовую чувствительность; значения можно подстроить под FPS, DPI и размер экрана.", reply_markup=kb(rows))
    await c.answer()

@dp.callback_query(F.data.startswith("ffdev:"))
async def cb_ff_device(c):
    idx = int(c.data.split(":", 1)[1])
    if idx < 0 or idx >= len(FF_DEVICES):
        await c.answer("Модель не найдена", show_alert=True); return
    uid = c.from_user.id
    u = get_user(uid)
    free_left = not u.get("free_sensitivity_used")
    credits = int(u.get("sensitivity_credits", 0))
    if not free_left and credits <= 0:
        await c.answer("Бесплатная настройка уже использована. Следующая откроется после покупки.", show_alert=True)
        return
    if free_left:
        u["free_sensitivity_used"] = True
    else:
        u["sensitivity_credits"] = max(0, credits - 1)
    u["last_sensitivity_device"] = FF_DEVICES[idx]
    save_db()
    # Умеренно высокие, но не максимальные стартовые значения; адаптировать по ощущениям.
    values = [200, 190, 185, 180, 170, 160]
    details = "\n".join(f"• {name}: <b>{value}</b>" for (name, _), value in zip(FF_SENS, values))
    await c.message.answer(f"🎯 <b>Free Fire · {esc(FF_DEVICES[idx])}</b>\n\n{details}\n\n"
                           "Это стартовый пресет, а не универсальная гарантия. Проверьте в тренировке и меняйте по 3–5 пунктов.",
                           reply_markup=kb([[btn("🔄 Выбрать другой телефон", "ff_sens")], [btn("🏠 Меню", "menu")]]))
    await c.answer("Настройка открыта")


# ===================== Панель админа =====================
async def donatix_balance():
    if not DONATIX_KEY:
        return None
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{API}{BALANCE_PATH}", headers=HEADERS,
                             timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    return None
                d = await r.json(content_type=None)
    except Exception:
        return None

    def find(x):
        if isinstance(x, dict):
            for k in ("balance_usd", "balance", "available", "amount"):
                v = x.get(k)
                if isinstance(v, (int, float)):
                    return float(v)
                if isinstance(v, str):
                    try:
                        return float(v)
                    except ValueError:
                        pass
                if isinstance(v, dict):
                    r2 = find(v)
                    if r2 is not None:
                        return r2
            for v in x.values():
                if isinstance(v, dict):
                    r2 = find(v)
                    if r2 is not None:
                        return r2
        return None
    return find(d)


def sales():
    return [o for o in db["orders"] if o["status"] != "failed"]


def stats_text():
    """Расширенная статистика для админа (пункт 13)."""
    days = [(datetime.now(TZ) - timedelta(days=i)).date() for i in range(6, -1, -1)]
    by_day = {d: [0, 0.0] for d in days}
    rev = profit = 0.0
    top = {}
    for o in sales():
        d = datetime.fromtimestamp(o["ts"], TZ).date()
        rev += o["price"]
        profit += o["price"] - o.get("cost_usd", 0) * o.get("rate", usd_tjs)
        if d in by_day:
            by_day[d][0] += 1
            by_day[d][1] += o["price"]
        top[o["title"]] = top.get(o["title"], 0) + 1
    maxv = max([v[1] for v in by_day.values()] + [1])
    bars = "\n".join(f"{d:%d.%m} {'█' * int(12 * v[1] / maxv):<12} {v[1]:.0f} с. ({v[0]})"
                     for d, v in by_day.items())
    top_lines = "\n".join(f"{i + 1}. {esc(k)} — {v}" for i, (k, v) in
                          enumerate(sorted(top.items(), key=lambda x: -x[1])[:5])) or "—"

    # Новые метрики (пункт 13)
    today = datetime.now(TZ).date()
    new_today = sum(1 for u in db["users"].values()
                    if datetime.fromtimestamp(u.get("joined", 0), TZ).date() == today)
    total_sales = len(sales())
    avg_check = rev / total_sales if total_sales > 0 else 0
    # Конверсия: пользователи с хотя бы одним заказом / все пользователи
    buyers = set(o["uid"] for o in sales())
    conversion = len(buyers) / max(len(db["users"]), 1) * 100

    return (
        f"📊 <b>Омор</b>\n\n"
        f"Фармоишҳо: {total_sales}\n"
        f"Даромад: {rev:.2f} с.\n"
        f"Фоидаи тахминӣ: {profit:.2f} с.\n"
        f"Миёнаи чек: {avg_check:.2f} с.\n"
        f"Конверсия: {conversion:.1f}%\n"
        f"Нав имрӯз: {new_today} нафар\n\n"
        f"<b>7 рӯз:</b>\n<pre>{bars}</pre>\n<b>Топ:</b>\n{top_lines}"
    )


async def show_admin(m, edit=False):
    total_bal = sum(u["balance"] for u in db["users"].values())
    pending = sum(1 for x in db["topups"].values() if x["status"] in ("pending", "review"))
    rows = [[btn("👥 Харидорон", "adm_users:0"), btn("🔎 Ҷустуҷӯи харидор", "adm_search")],
            [btn("📦 Фармоишҳо", "adm_orders"), btn("📊 Омор", "adm_stats")],
            [btn("🎟 Промокодҳо", "adm_promos"), btn("📢 Рассылка", "adm_bc")],
            [btn("💼 Баланси Donatix", "adm_dbal"), btn("🧹 Убрать Shop у всех", "adm_clear_kb")],
            [btn("🏠 Меню", "menu")]]
    msg = (f"🛠 <b>Панели админ</b>\n👥 Харидорон: {len(db['users'])}\n"
           f"💰 Ҳамаи балансҳо: {total_bal:.2f} с.\n📊 Курс: 1 USD = {usd_tjs:.2f} TJS\n"
           f"💾 Хотира: {'PostgreSQL' if pg_pool else 'JSON-файл ⚠️'}")
    await edit_or_send(m, msg, kb(rows), edit=edit)


@dp.message(Command("admin"))
async def admin_cmd(m):
    if not is_admin(m.from_user.id):
        return
    await show_admin(m)


def admin_only(handler):
    async def wrapper(c):
        if not is_admin(c.from_user.id):
            await c.answer("🚫", show_alert=True)
            return
        await handler(c)
    wrapper.__name__ = handler.__name__
    return wrapper


@dp.callback_query(F.data == "admin")
@admin_only
async def cb_admin(c):
    await c.answer()
    await show_admin(c.message, edit=True)


@dp.callback_query(F.data.startswith("adm_users:"))
@admin_only
async def cb_adm_users(c):
    await c.answer()
    page = int(c.data.split(":")[1])
    per = 8
    items = sorted(db["users"].items(), key=lambda x: -x[1].get("joined", 0))
    chunk = items[page * per:(page + 1) * per]
    rows = [[btn(f"№{u.get('customer_no', 0)} {'🚫 ' if u['blocked'] else ''}{u['name'][:18] or k} — {u['balance']:.0f} с.", f"adu:{k}")]
            for k, u in chunk]
    nav = []
    if page > 0:
        nav.append(btn("⬅️", f"adm_users:{page - 1}"))
    if (page + 1) * per < len(items):
        nav.append(btn("➡️", f"adm_users:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([btn("🔙", "admin")])
    await edit_or_send(c.message, f"👥 Харидорон: {len(items)}", kb(rows))


async def show_user_card(c, k):
    u = db["users"].get(k)
    if not u:
        await c.message.answer("Ёфт нашуд")
        return
    n_orders = sum(1 for o in sales() if str(o["uid"]) == k)
    uname = (u.get("username") or "").lstrip("@")
    if uname:
        name_line = f"👤 <b>{esc(u.get('name') or k)}</b> · @{esc(uname)} · <code>{k}</code> · №{u.get('customer_no', 0)}"
    else:
        name_line = f"👤 <b>{esc(u.get('name') or k)}</b> · <code>{k}</code> · №{u.get('customer_no', 0)}"
    disc = float(u.get("discount_percent") or 0)
    text = (f"{name_line}\n💰 Баланс: {u['balance']:.2f} с.\n"
            f"📦 Фармоишҳо: {n_orders}\n👥 Даъват: {u['refs']}\n🚫 Блок: {'ҳа' if u['blocked'] else 'не'}\n"
            f"💸 Скидка: {disc:g}%")
    rows = [[btn("✅ Бикушоед" if u["blocked"] else "🚫 Блок", f"adb:{k}"),
             btn("0️⃣ Сброс баланс", f"adr:{k}")],
            [btn("➕/➖ Баланс", f"ada:{k}"), btn("💸 Скидка %", f"addisc:{k}")]]
    # Кнопка написать пользователю
    if uname:
        rows.append([lbtn("✉️ Написать", f"https://t.me/{uname}")])
    else:
        rows.append([lbtn("✉️ Написать", f"tg://user?id={k}")])
    rows.append([btn("🔙", "adm_users:0")])
    await edit_or_send(c.message, text, kb(rows))


@dp.callback_query(F.data.startswith("adu:"))
@admin_only
async def cb_adu(c):
    await c.answer()
    await show_user_card(c, c.data.split(":")[1])


@dp.callback_query(F.data.startswith("adb:"))
@admin_only
async def cb_adb(c):
    k = c.data.split(":")[1]
    if k in db["users"]:
        db["users"][k]["blocked"] = not db["users"][k]["blocked"]
        save_db()
    await c.answer("OK")
    await show_user_card(c, k)


@dp.callback_query(F.data.startswith("adr:"))
@admin_only
async def cb_adr(c):
    k = c.data.split(":")[1]
    if k in db["users"]:
        db["users"][k]["balance"] = 0.0
        save_db()
    await c.answer("Баланс = 0")
    await show_user_card(c, k)


@dp.callback_query(F.data.startswith("ada:"))
@admin_only
async def cb_ada(c):
    k = c.data.split(":")[1]
    user_state[c.from_user.id] = {"stage": "adm_addbal", "target": k}
    await c.message.answer("✏️ Миқдорро нависед (масалан 50 ё -20):")
    await c.answer()


@dp.callback_query(F.data.startswith("addisc:"))
@admin_only
async def cb_addisc(c):
    k = c.data.split(":")[1]
    user_state[c.from_user.id] = {"stage": "adm_setdisc", "target": k}
    cur = float(db["users"].get(k, {}).get("discount_percent") or 0)
    await c.message.answer(
        f"💸 Скидкаи ҷорӣ: {cur:g}%\n"
        "Фоизро нависед (0–90). Масалан: 10 — 10% арзонтар. 0 — бекор кардани скидка:"
    )
    await c.answer()


@dp.callback_query(F.data == "adm_search")
@admin_only
async def cb_adm_search(c):
    user_state[c.from_user.id] = {"stage": "adm_search_user"}
    await c.message.answer("🔎 Ҷустуҷӯ: ID Telegram, @username, ном ё рақами харидорро ворид кунед.")
    await c.answer()

@dp.callback_query(F.data == "adm_orders")
@admin_only
async def cb_adm_orders(c):
    await c.answer()
    icons = {"done": "✅", "processing": "⏳", "uncertain": "⚠️", "failed": "❌"}
    last = db["orders"][-15:][::-1]
    text = "📦 <b>Фармоишҳои охирин</b>\n\n" + ("\n".join(
        f"{icons.get(o['status'], '•')} #{esc(o['oid'])} · {esc(o['title'])} · {o['price']} с. · "
        f"{esc(o.get('name', ''))} · {datetime.fromtimestamp(o['ts'], TZ):%d.%m %H:%M}" for o in last) or "—")
    await edit_or_send(c.message, text, kb([[btn("🔙", "admin")]]))


@dp.callback_query(F.data == "adm_stats")
@admin_only
async def cb_adm_stats(c):
    await c.answer()
    await edit_or_send(c.message, stats_text(),
                       kb([[btn("📄 CSV", "adm_csv")], [btn("🔙", "admin")]]))


@dp.callback_query(F.data == "adm_csv")
@admin_only
async def cb_adm_csv(c):
    await c.answer()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["time", "order_id", "user_id", "name", "title", "price_tjs", "cost_usd", "status", "promo"])
    for o in db["orders"]:
        w.writerow([datetime.fromtimestamp(o["ts"], TZ).strftime("%Y-%m-%d %H:%M"), o["oid"], o["uid"],
                    o.get("name", ""), o["title"], o["price"], o.get("cost_usd", ""), o["status"],
                    o.get("promo") or ""])
    await c.message.answer_document(BufferedInputFile(buf.getvalue().encode("utf-8-sig"), "orders.csv"))


@dp.callback_query(F.data == "adm_promos")
@admin_only
async def cb_adm_promos(c):
    await c.answer()
    rows = [[btn(f"{'🟢' if p.get('active', True) else '⚪'} {code} -{p['percent']}% "
                 f"({p.get('used', 0)}/{p.get('max_uses') or '∞'})", f"apt:{code}")]
            for code, p in db["promos"].items()]
    rows.append([btn("➕ Нав", "adm_promo_new")])
    rows.append([btn("🔙", "admin")])
    await edit_or_send(c.message, "🎟 Промокодҳо (клик — фаъол/ғайрифаъол):", kb(rows))


@dp.callback_query(F.data.startswith("apt:"))
@admin_only
async def cb_apt(c):
    code = c.data.split(":")[1]
    if code in db["promos"]:
        db["promos"][code]["active"] = not db["promos"][code].get("active", True)
        save_db()
    await c.answer("OK")
    await cb_adm_promos(c)


@dp.callback_query(F.data == "adm_promo_new")
@admin_only
async def cb_adm_promo_new(c):
    user_state[c.from_user.id] = {"stage": "adm_promo_new"}
    await c.message.answer("✏️ Формат: КОД ПРОЦЕНТ [МАКС_ИСПОЛЬЗОВАНИЙ]\nМисол: SALE10 10 100")
    await c.answer()


@dp.callback_query(F.data == "adm_bc")
@admin_only
async def cb_adm_bc(c):
    user_state[c.from_user.id] = {"stage": "adm_broadcast"}
    await c.message.answer("📢 Матни рассылкаро нависед:")
    await c.answer()


@dp.callback_query(F.data == "adm_clear_kb")
@admin_only
async def cb_adm_clear_kb(c):
    """Разово снимает кнопку Shop / старую reply-клавиатуру у всех пользователей."""
    await c.answer("⏳")
    ids = [int(k) for k in db["users"].keys()]
    ok = 0
    for i in ids:
        try:
            rm = await bot.send_message(i, ".", reply_markup=ReplyKeyboardRemove())
            try:
                await rm.delete()
            except Exception:
                pass
            ok += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)
    await c.message.answer(f"🧹 Клавиатура снята: {ok}/{len(ids)} пользователей")


@dp.callback_query(F.data == "adm_dbal")
@admin_only
async def cb_adm_dbal(c):
    await c.answer()
    bal = await donatix_balance()
    if bal is None:
        await c.message.answer(
            f"❌ Баланси Donatix гирифта нашуд (путь <code>{esc(BALANCE_PATH)}</code>). "
            f"Дар https://donatix.tj/api-docs роҳи дурустро ёбед ва DONATIX_BALANCE_PATH-ро танзим кунед.")
    else:
        await c.message.answer(f"💼 Баланси Donatix: <b>{bal:.2f}</b> USD (≈ {bal * usd_tjs:.2f} TJS)")


# ===================== Фоновые задачи =====================
async def balance_watcher():
    fails = 0
    while True:
        await asyncio.sleep(1800)
        bal = await donatix_balance()
        if bal is None:
            fails += 1
            if fails == 3:
                log.warning("Donatix balance endpoint не отвечает — проверка баланса отключена")
                return
            continue
        fails = 0
        last = db["meta"].get("low_notified", 0)
        if bal < LOW_BALANCE_USD and time.time() - last > 6 * 3600:
            db["meta"]["low_notified"] = time.time()
            save_db()
            await notify_admin(f"🚨 Баланси Donatix кам: <b>{bal:.2f}</b> USD (ҳадди ақал {LOW_BALANCE_USD:g})")


async def keepalive():
    """Render Free засыпает через 15 мин без трафика."""
    if not EXTERNAL_URL:
        return
    while True:
        await asyncio.sleep(600)
        try:
            async with aiohttp.ClientSession() as s:
                await s.get(EXTERNAL_URL + "/", timeout=aiohttp.ClientTimeout(total=15))
        except Exception:
            pass


# ===================== Улучшенный Web App (пункт 12) =====================
WEBAPP_HTML = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>DONATEX</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
  :root {
    --bg: #0d0f1a;
    --bg2: #13162b;
    --bg3: #1a1f3a;
    --accent: #7b5ef8;
    --accent2: #a78bfa;
    --pink: #f472b6;
    --teal: #22d3ee;
    --text: #f1f5f9;
    --text2: #94a3b8;
    --card-bg: #131629;
    --card-border: rgba(123,94,248,0.18);
    --shadow: 0 8px 32px rgba(123,94,248,0.18);
    --radius: 16px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, 'SF Pro Display', Segoe UI, Roboto, sans-serif;
    min-height: 100vh;
    padding-bottom: 80px;
  }
  .header {
    background: linear-gradient(135deg, #0d0f1a 0%, #1a0f3a 100%);
    padding: 18px 16px 14px;
    text-align: center;
    position: sticky;
    top: 0;
    z-index: 100;
    border-bottom: 1px solid rgba(123,94,248,0.2);
    backdrop-filter: blur(20px);
  }
  .logo {
    font-size: 26px;
    font-weight: 900;
    letter-spacing: 4px;
    background: linear-gradient(90deg, #7b5ef8, #f472b6, #22d3ee, #7b5ef8);
    background-size: 300% 100%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: shimmer 3s linear infinite;
    text-transform: uppercase;
  }
  @keyframes shimmer {
    0% { background-position: 0% 50%; }
    100% { background-position: 300% 50%; }
  }
  .logo-sub {
    font-size: 10px;
    color: var(--text2);
    letter-spacing: 3px;
    margin-top: 2px;
    text-transform: uppercase;
  }
  .search-wrap {
    padding: 12px 16px 8px;
    position: sticky;
    top: 76px;
    z-index: 99;
    background: var(--bg);
  }
  .search-box {
    display: flex;
    align-items: center;
    background: var(--bg2);
    border: 1.5px solid var(--card-border);
    border-radius: 14px;
    padding: 11px 14px;
    gap: 10px;
    transition: border-color 0.2s;
  }
  .search-box:focus-within { border-color: var(--accent); }
  .search-icon { font-size: 16px; color: var(--text2); flex-shrink: 0; }
  .search-box input {
    flex: 1; background: none; border: none; outline: none;
    color: var(--text); font-size: 15px;
  }
  .search-box input::placeholder { color: var(--text2); }
  .top-games-section { padding: 12px 16px 4px; }
  .section-title {
    font-size: 13px;
    font-weight: 700;
    color: var(--text2);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 10px;
  }
  .top-games-scroll {
    display: flex;
    gap: 10px;
    overflow-x: auto;
    padding-bottom: 4px;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
  }
  .top-games-scroll::-webkit-scrollbar { display: none; }
  .top-game-chip {
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
  }
  .top-game-icon {
    width: 60px;
    height: 60px;
    border-radius: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 28px;
    border: 2px solid transparent;
    transition: all 0.15s;
    position: relative;
  }
  .top-game-chip:active .top-game-icon {
    transform: scale(0.92);
    border-color: var(--accent2);
  }
  .top-badge {
    position: absolute;
    top: -4px; right: -4px;
    background: linear-gradient(135deg, #f472b6, #fb923c);
    color: white;
    font-size: 8px;
    font-weight: 800;
    padding: 2px 5px;
    border-radius: 8px;
    letter-spacing: 0.5px;
  }
  .top-game-name {
    font-size: 10px;
    font-weight: 600;
    color: var(--text2);
    text-align: center;
    max-width: 70px;
    line-height: 1.2;
  }
  #loader {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 200px;
    gap: 16px;
  }
  .spinner {
    width: 44px; height: 44px;
    border: 3px solid var(--bg3);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .loader-text { color: var(--text2); font-size: 14px; }
  #app { padding: 8px 16px; }
  .cat-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 20px 0 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--card-border);
  }
  .cat-header h3 { font-size: 17px; font-weight: 700; color: var(--text); flex: 1; }
  .cat-badge {
    background: rgba(123,94,248,0.15);
    color: var(--accent2);
    font-size: 11px;
    padding: 3px 8px;
    border-radius: 20px;
    font-weight: 600;
  }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .card {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: var(--radius);
    padding: 14px 12px;
    cursor: pointer;
    transition: all 0.18s ease;
    position: relative;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .card::before {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, rgba(123,94,248,0.08), transparent);
    opacity: 0;
    transition: opacity 0.18s;
  }
  .card:active { transform: scale(0.96); border-color: var(--accent); box-shadow: var(--shadow); }
  .card:active::before { opacity: 1; }
  .card-title { font-size: 13px; font-weight: 600; color: var(--text); line-height: 1.3; }
  .card-price { font-size: 15px; font-weight: 800; color: var(--accent2); }
  .card-price small { font-size: 11px; font-weight: 500; color: var(--text2); }
  .nav {
    position: fixed;
    bottom: 0; left: 0; right: 0;
    background: rgba(13,15,26,0.95);
    border-top: 1px solid var(--card-border);
    display: flex;
    padding: 8px 0 env(safe-area-inset-bottom, 8px);
    z-index: 200;
    backdrop-filter: blur(20px);
  }
  .nav-btn {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 3px;
    padding: 6px;
    cursor: pointer;
    color: var(--text2);
    font-size: 10px;
    transition: color 0.15s;
    -webkit-tap-highlight-color: transparent;
  }
  .nav-btn.active { color: var(--accent2); }
  .nav-icon { font-size: 20px; }
  .empty { text-align: center; padding: 40px 20px; color: var(--text2); }
  .empty-icon { font-size: 48px; margin-bottom: 12px; }
</style>
</head>
<body>

<div class="header">
  <div class="logo">DONATEX</div>
  <div class="logo-sub">Gaming Shop</div>
</div>

<div class="search-wrap">
  <div class="search-box">
    <span class="search-icon">🔍</span>
    <input id="q" type="search" placeholder="Поиск товаров..." autocomplete="off">
  </div>
</div>

<div class="top-games-section">
  <div class="section-title">🔥 Топ игры</div>
  <div class="top-games-scroll" id="topGames"></div>
</div>

<div id="app">
  <div id="loader">
    <div class="spinner"></div>
    <div class="loader-text">Загрузка каталога...</div>
  </div>
</div>

<div class="nav">
  <div class="nav-btn active" onclick="showAll(event)">
    <span class="nav-icon">🏠</span>
    <span>Главная</span>
  </div>
  <div class="nav-btn" onclick="focusSearch(event)">
    <span class="nav-icon">🔍</span>
    <span>Поиск</span>
  </div>
  <div class="nav-btn" onclick="Telegram.WebApp.close()">
    <span class="nav-icon">✖️</span>
    <span>Закрыть</span>
  </div>
</div>

<script>
const tg = Telegram.WebApp;
tg.ready();
tg.expand();

let allData = [];
let currentFilter = '';

const PRIORITY_GAMES = [
  { key: 'ff_cis',   label: 'FF СНГ',         icon: '🇷🇺', bg: 'linear-gradient(135deg,#1a3a6e,#0d1f3c)', top: true },
  { key: 'ff_id',    label: 'FF Инд',          icon: '🇮🇩', bg: 'linear-gradient(135deg,#6e1a1a,#3c0d0d)', top: true },
  { key: 'pubg_us',  label: 'PUBG Mobile US',     icon: '🎯',  bg: 'linear-gradient(135deg,#4a3500,#2a1e00)', top: true },
  { key: 'mlbb',     label: 'Mobile Legends',  icon: '⚔️', bg: 'linear-gradient(135deg,#1a4a2e,#0d2a1a)', top: false },
  { key: 'standoff', label: 'Standoff 2',      icon: '🔫', bg: 'linear-gradient(135deg,#2e1a4a,#1a0d2a)', top: false },
  { key: 'telegram', label: 'TG Stars',        icon: '⭐', bg: 'linear-gradient(135deg,#003366,#001a3a)', top: false },
];

function matchGame(catName, key) {
  const n = catName.toLowerCase();
  if (key === 'ff_cis') return (n.includes('free fire') || n.includes('garena')) && (n.includes('cis') || n.includes('снг') || n.includes('rus')) && !n.includes('indo');
  if (key === 'ff_id') return (n.includes('free fire') || n.includes('garena')) && n.includes('indo');
  if (key === 'pubg_us') return n.includes('pubg') && (n.includes('united states') || n.includes('usa') || n.includes('(us)') || n.includes(' us '));
  if (key === 'pubg') return n.includes('pubg');
  if (key === 'mlbb') return n.includes('mobile legend') || n.includes('mlbb');
  if (key === 'standoff') return n.includes('standoff');
  if (key === 'telegram') return n.includes('telegram') || n.includes('stars') || n.includes('premium');
  return false;
}

function buildTopGames(data) {
  const scroll = document.getElementById('topGames');
  scroll.innerHTML = '';
  PRIORITY_GAMES.forEach(game => {
    const cat = data.find(c => matchGame(c.name, game.key));
    if (!cat) return;
    const chip = document.createElement('div');
    chip.className = 'top-game-chip';
    chip.innerHTML = '<div class="top-game-icon" style="background:' + game.bg + '">' +
      game.icon + (game.top ? '<div class="top-badge">TOP</div>' : '') + '</div>' +
      '<div class="top-game-name">' + game.label + '</div>';
    chip.addEventListener('click', () => {
      tg.HapticFeedback.impactOccurred('light');
      filterByCat(cat.name);
    });
    scroll.appendChild(chip);
  });
}

function sortData(data) {
  const priorityOrder = ['ff_cis', 'ff_id', 'pubg', 'mlbb', 'standoff', 'telegram'];
  const sorted = [];
  const rest = [...data];
  priorityOrder.forEach(key => {
    const idx = rest.findIndex(c => matchGame(c.name, key));
    if (idx !== -1) sorted.push(rest.splice(idx, 1)[0]);
  });
  return [...sorted, ...rest];
}

fetch('/webapp/catalog.json')
  .then(r => r.json())
  .then(d => {
    allData = sortData(d);
    document.getElementById('loader').style.display = 'none';
    buildTopGames(allData);
    render('');
  })
  .catch(() => {
    document.getElementById('loader').innerHTML =
      '<div class="empty"><div class="empty-icon">😕</div><div>Ошибка загрузки</div></div>';
  });

document.getElementById('q').addEventListener('input', e => {
  currentFilter = e.target.value.toLowerCase();
  render(currentFilter);
});

function render(f) {
  const app = document.getElementById('app');
  app.innerHTML = '';
  let found = 0;
  allData.forEach(cat => {
    const ps = cat.products.filter(p =>
      !f || p.title.toLowerCase().includes(f) || cat.name.toLowerCase().includes(f)
    );
    if (!ps.length) return;
    found += ps.length;
    const header = document.createElement('div');
    header.className = 'cat-header';
    header.innerHTML = '<h3>' + cat.name + '</h3><span class="cat-badge">' + ps.length + '</span>';
    app.appendChild(header);
    const grid = document.createElement('div');
    grid.className = 'grid';
    ps.forEach(p => {
      const card = document.createElement('div');
      card.className = 'card';
      card.innerHTML = '<div class="card-title">' + p.title + '</div>' +
        '<div class="card-price">' + p.price + ' <small>с.</small></div>';
      card.addEventListener('click', () => {
        tg.HapticFeedback.impactOccurred('light');
        tg.sendData(JSON.stringify({ p: p.id }));
      });
      grid.appendChild(card);
    });
    app.appendChild(grid);
  });
  if (found === 0 && f) {
    app.innerHTML = '<div class="empty"><div class="empty-icon">🔍</div><div>Ничего не найдено</div></div>';
  }
}

function filterByCat(catName) {
  document.getElementById('q').value = catName;
  currentFilter = catName.toLowerCase();
  render(currentFilter);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showAll(e) {
  document.getElementById('q').value = '';
  currentFilter = '';
  render('');
  window.scrollTo({ top: 0, behavior: 'smooth' });
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  e.currentTarget.classList.add('active');
}

function focusSearch(e) {
  document.getElementById('q').focus();
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  e.currentTarget.classList.add('active');
}
</script>
</body>
</html>"""

# Новый интерфейс заменяет старый экран с отправкой tg.sendData:
# покупка теперь подтверждается WebApp API и не закрывает Mini App.
WEBAPP_HTML = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,viewport-fit=cover">
<title>DONATEX</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
:root{--bg:#080d1b;--panel:#111a30;--panel2:#17233d;--line:#233653;--blue:#318bff;--cyan:#20d8ee;--text:#f3f7ff;--muted:#92a4c2;--orange:#ff8a32;--radius:18px}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 50% -20%,#18356a 0,#080d1b 55%);color:var(--text);font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding-bottom:calc(78px + env(safe-area-inset-bottom))}
button,input,select{font:inherit}button{border:0;cursor:pointer;color:white;font-weight:700}
.header{position:sticky;top:0;z-index:5;display:flex;align-items:center;justify-content:space-between;padding:14px 17px;background:#0b1324ed;backdrop-filter:blur(16px);border-bottom:1px solid #21395b}
.brand{font-size:23px;font-weight:900;letter-spacing:3px;color:#fff}.brand span{color:var(--cyan)}.balance-pill{background:#142543;border:1px solid #2d5b91;color:#d8edff;border-radius:20px;padding:8px 12px;font-size:13px}
.search-wrap{padding:12px 16px 4px}.search{width:100%;padding:13px 15px;border-radius:14px;background:#111a30;border:1px solid #263b5c;color:var(--text);outline:none}.search:focus{border-color:var(--cyan)}
.section{padding:12px 16px}.section-title{font-size:14px;font-weight:800;letter-spacing:.5px;margin:4px 0 12px;color:#eaf3ff}
.top-games{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.game-tile{background:var(--panel);border:1px solid var(--line);border-radius:16px;overflow:hidden;min-width:0;cursor:pointer;position:relative}.cover{display:block;width:100%;height:108px;object-fit:cover;background:#172642}.game-title{font-size:11px;font-weight:800;text-align:center;padding:8px 4px 9px;line-height:1.2}.top-tag{position:absolute;top:7px;right:7px;background:linear-gradient(135deg,#ffb548,var(--orange));color:#fff;border-radius:8px;padding:3px 6px;font-size:9px;font-weight:900}
#view{padding:4px 16px 18px}.muted{color:var(--muted);font-size:13px;line-height:1.45}.category-row{display:flex;gap:12px;align-items:center;margin:17px 0 10px;padding:9px;border-radius:15px;background:#101a2d;border:1px solid var(--line);cursor:pointer}.category-row img{width:66px;height:66px;border-radius:12px;object-fit:cover}.category-row strong{display:block;font-size:14px}.category-row small{color:var(--muted)}
.product-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.product{background:linear-gradient(145deg,#131f38,#0e1729);border:1px solid #253958;border-radius:15px;padding:12px;min-height:118px;display:flex;flex-direction:column;gap:8px}.product-name{font-size:13px;line-height:1.3;font-weight:700;flex:1}.price{font-size:16px;font-weight:900;color:#9fdcff}.small-button,.primary-button,.secondary-button,.danger-button{border-radius:12px;padding:10px 12px;background:linear-gradient(135deg,#287cf5,#14a7e8);width:100%;font-size:13px}.secondary-button{background:#182846;border:1px solid #2d4b70;color:#d9ecff}.danger-button{background:#48202a;border:1px solid #753442;color:#ffc0c7}.two-actions{display:flex;gap:7px}.two-actions button{flex:1;padding:9px 6px;font-size:11px}.back{background:transparent;color:#8fdafa;padding:8px 0 12px;font-weight:700}
.nav{position:fixed;bottom:0;left:0;right:0;z-index:9;display:flex;padding:7px 4px calc(7px + env(safe-area-inset-bottom));background:#081020f5;border-top:1px solid #243a5b;backdrop-filter:blur(16px)}.nav-btn{flex:1;background:transparent;color:#8da0bf;display:flex;flex-direction:column;align-items:center;gap:3px;padding:5px 1px;font-size:10px}.nav-btn.active{color:#55caff}.nav-icon{font-size:19px}.badge-count{font-size:9px;background:var(--orange);border-radius:9px;padding:1px 5px;margin-left:2px;color:white}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:15px;margin:10px 0}.field{width:100%;background:#0b1426;color:white;border:1px solid #294363;border-radius:12px;padding:12px;margin:6px 0 10px;outline:none}.row{display:flex;gap:9px}.row>*{flex:1}.entry{padding:11px 0;border-bottom:1px solid #23344d}.entry:last-child{border:0}.entry strong{display:block;font-size:13px}.entry small{color:var(--muted)}.leader{display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid #253650}.leader:first-child{color:#ffd270}.game-arena{width:100%;min-height:190px;font-size:28px;background:radial-gradient(circle,#164d78,#101a30 65%);border:1px solid #287aa3;border-radius:18px;margin:12px 0}.game-arena:disabled{opacity:.7}.toast{position:fixed;left:16px;right:16px;bottom:88px;background:#142946;border:1px solid #2874a8;padding:12px 15px;border-radius:12px;z-index:20;text-align:center;box-shadow:0 8px 30px #0008}.modal-backdrop{position:fixed;inset:0;background:#000a;z-index:30;display:flex;align-items:flex-end}.modal{width:100%;background:#101a2d;border:1px solid #315078;border-radius:22px 22px 0 0;padding:20px 17px calc(22px + env(safe-area-inset-bottom));max-height:88vh;overflow:auto}.modal h3{margin:0 0 7px}.hidden{display:none!important}.link-row{display:flex;flex-wrap:wrap;gap:9px;margin-top:12px}.link-row a{color:#8edbff;text-decoration:none;padding:8px 10px;background:#172846;border-radius:10px}.empty{text-align:center;padding:28px 10px;color:var(--muted)}
</style>
</head>
<body>
<header class="header"><div class="brand">DONA<span>TEX</span></div><div id="balance" class="balance-pill">Баланс: — с.</div></header>
<div id="searchWrap" class="search-wrap"><input id="search" class="search" type="search" placeholder="🔍 Поиск игры или товара"></div>
<section id="topSection" class="section"><div class="section-title">🔥 ТОП ИГРЫ</div><div id="topGames" class="top-games"></div></section>
<main id="view"><div class="empty">Загружаю магазин…</div></main>
<nav class="nav">
 <button class="nav-btn active" data-view="home"><span class="nav-icon">⌂</span>Главная</button>
 <button class="nav-btn" data-view="cart"><span class="nav-icon">🛒</span>Корзина <span id="cartCount" class="badge-count hidden"></span></button>
 <button class="nav-btn" data-view="topup"><span class="nav-icon">＋</span>Пополнить</button>
 <button class="nav-btn" data-view="history"><span class="nav-icon">◷</span>История</button>
</nav>
<div id="modalRoot"></div>
<div id="toast" class="toast hidden"></div>
<script>
const tg=window.Telegram?.WebApp;
if(tg){tg.ready();tg.expand();}
const initData=tg?.initData||'';
const view=document.getElementById('view');
let allData=[], appState=null, currentView='home', selectedCategory=null, cart=[];
try{cart=JSON.parse(localStorage.getItem('donatex_cart')||'[]')}catch(_){cart=[]}
const PRIORITY_GAMES=[
 {key:'ff_id',label:'FF Индонезия',short:'FREE FIRE ID',colors:['#9b2634','#ff9d42'],stamp:'FF'},
 {key:'pubg_us',label:'PUBG Mobile US',short:'PUBG MOBILE',colors:['#765123','#e4ba55'],stamp:'PUBG'},
 {key:'standoff',label:'Standoff 2',short:'STANDOFF 2',colors:['#342253','#e04c4f'],stamp:'S2'},
 {key:'cod',label:'Call of Duty',short:'CALL OF DUTY',colors:['#25483c','#caa953'],stamp:'COD'},
 {key:'capcut',label:'CapCut',short:'CAPCUT',colors:['#142c49','#24badd'],stamp:'CC'}
];
// Положите свои файлы в папку game_images в корне репозитория.
const GAME_IMAGE_FILES={ff_cis:'ff_cis.jpg',ff_id:'ff_id.jpg',pubg_us:'pubg_us.jpg',standoff:'standoff.jpg',cod:'cod.jpg',capcut:'capcut.jpg'};
// Если имя категории у Donatix нестандартное, впишите сюда точное имя из каталога.
const GAME_CATEGORY_ALIASES={ff_cis:[],ff_id:[],pubg_us:[],standoff:[],cod:[],capcut:[]};
function newRequestId(){return crypto.randomUUID?.()||Date.now()+'-'+Math.random().toString(36).slice(2)}
const escXml=s=>String(s||'').replace(/[<>&"]/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}[c]));
function artUrl(key,label){
 let game=PRIORITY_GAMES.find(g=>g.key===key);
 if(!game){let hash=0;for(const ch of String(label||'GAME'))hash=(hash*31+ch.charCodeAt(0))>>>0;const hue=hash%360;game={colors:[`hsl(${hue} 62% 27%)`,`hsl(${(hue+58)%360} 74% 48%)`],stamp:String(label||'GAME').split(/\s+/).slice(0,2).map(x=>x.slice(0,1)).join('').toUpperCase()}}
 const [a,b]=game.colors, title=escXml(String(label||game.short).toUpperCase().slice(0,22));
 const svg=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 420"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="${a}"/><stop offset="1" stop-color="${b}"/></linearGradient><radialGradient id="r"><stop stop-color="#fff" stop-opacity=".55"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient></defs><rect width="640" height="420" fill="url(#g)"/><circle cx="500" cy="85" r="205" fill="url(#r)" opacity=".65"/><path d="M-20 350 180 105l100 115 115-150 280 300v80H-20z" fill="#07101d" opacity=".48"/><path d="M55 0h90l-55 150h75L40 310l35-125H10z" fill="#fff" opacity=".14"/><circle cx="510" cy="272" r="94" fill="none" stroke="#fff" stroke-opacity=".22" stroke-width="7"/><circle cx="510" cy="272" r="57" fill="none" stroke="#fff" stroke-opacity=".28" stroke-width="5"/><text x="320" y="210" text-anchor="middle" font-family="Arial,sans-serif" font-size="76" font-weight="900" fill="#fff" stroke="#08111e" stroke-opacity=".3" stroke-width="2">${game.stamp}</text><text x="320" y="370" text-anchor="middle" font-family="Arial,sans-serif" font-size="24" font-weight="800" letter-spacing="4" fill="#fff">${title}</text></svg>`;
 return 'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(svg);
}
function gameMatch(name,key){
 const n=String(name||'').toLowerCase();
 if(key==='ff_id')return /(free fire|garena)/.test(n)&&/(indonesia|indon|free fire id|ff id|\(id\))/.test(n);
 if(key==='ff_cis')return /(free fire|garena)/.test(n)&&/(cis|снг|russia|rus|free fire ru|ff ru)/.test(n)&&!/(indonesia|indon)/.test(n);
 if(key==='pubg_us')return n.includes('pubg')&&/(united states|\busa\b|\(us\)|\bus\b)/.test(n);
 if(key==='standoff')return n.includes('standoff');
 if(key==='cod')return n.includes('call of duty')||n.includes('cod mobile')||n.includes('codm');
 if(key==='capcut')return n.includes('capcut')||n.includes('cap cut');
 return false;
}
function categoryFor(key){
 const aliases=GAME_CATEGORY_ALIASES[key]||[];
 const manual=allData.find(c=>aliases.some(alias=>String(c.name).toLowerCase().includes(String(alias).toLowerCase())));
 if(manual)return manual;
 let found=allData.find(c=>gameMatch(c.name,key));
 if(!found&&key==='pubg_us')found=allData.find(c=>String(c.name).toLowerCase().includes('pubg'));
 return found||null;
}
function categoryKey(name){return PRIORITY_GAMES.find(g=>gameMatch(name,g.key))?.key||'generic'}
function api(path,body){
 return fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...body,init_data:initData})})
  .then(async r=>{
   const text=await r.text();let data={};
   try{data=JSON.parse(text)}catch(_){}
   if(!r.ok&&!data.message)data.message=`Сервер ответил HTTP ${r.status}. Проверьте, что Render запустил обновлённый файл.`;
   return {ok:r.ok,data,status:r.status};
  }).catch(()=>({ok:false,status:0,data:{message:'Нет связи с сервером Render. Проверьте интернет и откройте Mini App ещё раз.'}}));
}
function toast(text){const el=document.getElementById('toast');el.textContent=text;el.classList.remove('hidden');setTimeout(()=>el.classList.add('hidden'),3000)}
function saveCart(){localStorage.setItem('donatex_cart',JSON.stringify(cart));const b=document.getElementById('cartCount');b.textContent=cart.length;b.classList.toggle('hidden',!cart.length)}
function button(text,cls,fn){const b=document.createElement('button');b.className=cls;b.textContent=text;b.onclick=fn;return b}
function gameCover(key,label){
 const img=document.createElement('img');img.className='cover';img.alt=label;
 const fallback=artUrl(key,label);const filename=GAME_IMAGE_FILES[key];
 img.onerror=()=>{img.onerror=null;img.src=fallback};
 img.src=filename?'/webapp/images/'+encodeURIComponent(filename):fallback;
 return img
}
function buildTopGames(){
 const root=document.getElementById('topGames');root.innerHTML='';
 PRIORITY_GAMES.forEach(g=>{
  const cat=categoryFor(g.key);
  if(!cat) return;
  const tile=document.createElement('div');tile.className='game-tile';tile.appendChild(gameCover(g.key,g.short));
  const badge=document.createElement('span');badge.className='top-tag';badge.textContent='TOP';tile.appendChild(badge);
  const title=document.createElement('div');title.className='game-title';title.textContent=g.label;tile.appendChild(title);
  tile.onclick=()=>selectCategory(cat);
  root.appendChild(tile);
 });
 if(!root.children.length) document.getElementById('topSection')?.classList.add('hidden');
}
function setTab(tab){
 currentView=tab;selectedCategory=null;
 document.querySelectorAll('.nav-btn').forEach(b=>b.classList.toggle('active',b.dataset.view===tab));
 document.getElementById('searchWrap').classList.toggle('hidden',tab!=='home');
 document.getElementById('topSection').classList.toggle('hidden',tab!=='home');
 if(tab==='home')renderHome();if(tab==='cart')renderCart();if(tab==='topup')renderTopup();if(tab==='history')renderHistory();if(tab==='game')renderGame();
}
document.querySelectorAll('.nav-btn').forEach(b=>b.addEventListener('click',()=>setTab(b.dataset.view)));
function renderHome(){
 currentView='home';document.getElementById('searchWrap').classList.remove('hidden');document.getElementById('topSection').classList.remove('hidden');
 const q=document.getElementById('search').value.trim().toLowerCase();view.innerHTML='';
 if(selectedCategory){
  const back=button('← Все игры','back',()=>{selectedCategory=null;renderHome()});view.appendChild(back);
  const hero=document.createElement('div');hero.className='category-row';hero.appendChild(gameCover(categoryKey(selectedCategory.name),selectedCategory.name));
  const title=document.createElement('strong');title.textContent=selectedCategory.name;hero.appendChild(title);view.appendChild(hero);
  renderProducts(selectedCategory.products.filter(p=>!q||p.title.toLowerCase().includes(q)),selectedCategory.name);return;
 }
  const play=document.createElement('div');play.className='card';
  const playTitle=document.createElement('strong');playTitle.textContent='🎮 Игра с другими игроками';play.appendChild(playTitle);
  const playText=document.createElement('p');playText.className='muted';playText.textContent='Сыграйте 10 секунд и попадите в общий рейтинг.';play.appendChild(playText);
  play.appendChild(button('Играть','primary-button',()=>setTab('game')));view.appendChild(play);
  const grid=document.createElement('div');grid.className='top-games';
  const categoryRank=cat=>{const exact=PRIORITY_GAMES.findIndex(g=>gameMatch(cat.name,g.key));if(exact>=0)return exact;if(String(cat.name).toLowerCase().includes('pubg'))return 2;return 100};
  [...allData].sort((a,b)=>categoryRank(a)-categoryRank(b)).filter(c=>!q||c.name.toLowerCase().includes(q)||c.products.some(p=>p.title.toLowerCase().includes(q))).forEach(cat=>{
  const tile=document.createElement('div');tile.className='game-tile';tile.appendChild(gameCover(categoryKey(cat.name),cat.name));
  const title=document.createElement('div');title.className='game-title';title.textContent=cat.name;tile.appendChild(title);
  tile.onclick=()=>selectCategory(cat);grid.appendChild(tile);
 });
 if(!allData.length){view.innerHTML='<div class="empty">Каталог временно недоступен</div>';return}
 view.appendChild(grid);
 const note=document.createElement('p');note.className='muted';note.textContent='Выберите игру — товары и покупка откроются здесь, без перехода в чат.';view.appendChild(note);
}
function selectCategory(cat){selectedCategory=cat;document.getElementById('search').value='';renderHome();window.scrollTo({top:0,behavior:'smooth'})}
function renderProducts(products,categoryName){
 const grid=document.createElement('div');grid.className='product-grid';
 products.forEach(p=>{
  const card=document.createElement('div');card.className='product';
  const name=document.createElement('div');name.className='product-name';name.textContent=p.title;card.appendChild(name);
  const price=document.createElement('div');price.className='price';price.textContent=Number(p.price).toFixed(2)+' с.';card.appendChild(price);
  const actions=document.createElement('div');actions.className='two-actions';
  actions.appendChild(button('В корзину','secondary-button',()=>{const old=cart.find(x=>x.id===p.id);if(old)old.qty=(old.qty||1)+1;else cart.push({id:p.id,title:p.title,category:categoryName,qty:1});saveCart();toast('Добавлено в корзину')}));
  actions.appendChild(button('Купить','small-button',()=>openBuyModal(p,categoryName)));card.appendChild(actions);grid.appendChild(card);
 });
 view.appendChild(grid);
 if(!products.length)view.insertAdjacentHTML('beforeend','<div class="empty">Ничего не найдено</div>');
}
function openBuyModal(p,cat){
 const root=document.getElementById('modalRoot');root.innerHTML='';
 const back=document.createElement('div');back.className='modal-backdrop';back.onclick=e=>{if(e.target===back)root.innerHTML=''};
 const box=document.createElement('div');box.className='modal';const title=document.createElement('h3');title.textContent=p.title;box.appendChild(title);
 const info=document.createElement('p');info.className='muted';info.textContent=cat+' · '+Number(p.price).toFixed(2)+' с.';box.appendChild(info);
 const input=document.createElement('input');input.className='field';input.inputMode='numeric';input.placeholder='ID игрока (6–15 цифр)';input.maxLength=15;box.appendChild(input);
  box.appendChild(button('Купить сейчас','primary-button',async()=>{if(!/^\d{6,15}$/.test(input.value.trim())){toast('Введите UID из 6–15 цифр');return}await buyProduct(p.id,input.value.trim(),root)}));
 box.appendChild(button('Добавить в корзину','secondary-button',()=>{const old=cart.find(x=>x.id===p.id);if(old)old.qty=(old.qty||1)+1;else cart.push({id:p.id,title:p.title,category:cat,qty:1});saveCart();root.innerHTML='';toast('Добавлено в корзину')}));
 box.appendChild(button('Закрыть','secondary-button',()=>root.innerHTML=''));back.appendChild(box);root.appendChild(back);input.focus();
}
async function buyProduct(id,playerId,modalRoot){
 if(!initData){toast('Откройте магазин через Telegram');return}
 const btn=modalRoot.querySelector('.primary-button');if(btn){btn.disabled=true;btn.textContent='Обрабатываю…'}
 try{
   const {ok,data}=await api('/webapp/api/order',{product_id:id,player_id:playerId,request_id:newRequestId()});
   if(!ok){if(data.error==='insufficient_balance'){modalRoot.innerHTML='';toast('Недостаточно средств — откройте «Пополнить»');setTab('topup')}else if(data.error==='order_uncertain')toast('Заказ проверяется поддержкой; не отправляйте его повторно');else toast('Не удалось оформить заказ: '+(data.message||data.error||'ошибка'));return}
  modalRoot.innerHTML='';toast('Заказ #'+data.order_id+' принят');await refreshState();
 }catch(_){toast('Нет связи с магазином')}
 finally{if(btn){btn.disabled=false;btn.textContent='Купить сейчас'}}
}
function renderCart(){
 view.innerHTML='<h2>Корзина</h2>';if(!cart.length){view.insertAdjacentHTML('beforeend','<div class="empty">Корзина пока пустая</div>');return}
 const form=document.createElement('div');
 cart.forEach((item,i)=>{const card=document.createElement('div');card.className='card';const title=document.createElement('strong');title.textContent=item.title;card.appendChild(title);const sub=document.createElement('small');sub.className='muted';sub.textContent=item.category;card.appendChild(sub);
  const qty=document.createElement('div');qty.className='two-actions';qty.appendChild(button('−','secondary-button',()=>{item.qty=Math.max(1,(item.qty||1)-1);saveCart();renderCart()}));const q=document.createElement('strong');q.textContent='Количество: '+(item.qty||1);qty.appendChild(q);qty.appendChild(button('+','secondary-button',()=>{item.qty=Math.min(20,(item.qty||1)+1);saveCart();renderCart()}));card.appendChild(qty);
  const input=document.createElement('input');input.className='field';input.placeholder='UID игрока';input.inputMode='numeric';input.maxLength=15;input.dataset.index=i;card.appendChild(input);
  const remove=button('Убрать','danger-button',()=>{cart.splice(i,1);saveCart();renderCart()});card.appendChild(remove);form.appendChild(card)});
 view.appendChild(form);view.appendChild(button('Оформить покупки','primary-button',()=>buyCart(form)));
}
async function buyCart(form){
 const inputs=[...form.querySelectorAll('input')];if(inputs.some(i=>!/^\d{6,15}$/.test(i.value.trim()))){toast('Для каждого товара нужен UID из 6–15 цифр');return}
 const queue=inputs.map(input=>({item:cart[Number(input.dataset.index)],playerId:input.value.trim()})).filter(x=>x.item).flatMap(x=>Array.from({length:Math.max(1,Math.min(20,x.item.qty||1))},()=>({...x}))); 
 for(const entry of queue){const {ok,data}=await api('/webapp/api/order',{product_id:entry.item.id,player_id:entry.playerId,request_id:newRequestId()});if(!ok){toast(data.error==='insufficient_balance'?'Недостаточно средств — откройте «Пополнить»':'Покупка остановлена: '+(data.message||data.error));if(data.error==='insufficient_balance')setTab('topup');return}const inCart=cart.find(x=>x.id===entry.item.id);if(inCart){inCart.qty=Math.max(0,(inCart.qty||1)-1);if(!inCart.qty)cart=cart.filter(x=>x.id!==entry.item.id)}saveCart();await refreshState()}
 toast('Все покупки оформлены');renderCart();
}
function renderTopup(){
 view.innerHTML='<h2>Пополнить баланс</h2><p class="muted">Выберите способ и сумму. После перевода отправьте чек прямо здесь.</p>';
 if(!appState){view.insertAdjacentHTML('beforeend','<div class="empty">Сначала откройте Mini App кнопкой DONATEX в чате и дождитесь загрузки баланса.</div>');return}
 if(!appState.topup_methods?.length){view.insertAdjacentHTML('beforeend','<div class="empty">Нет способов оплаты. В Render → Environment добавьте непустой DC_NUMBER или ALIF_NUMBER, затем нажмите Manual Deploy.</div>');return}
 if(!appState.topup_receipts_enabled){view.insertAdjacentHTML('beforeend','<div class="empty">Для проверки чеков укажите ADMIN_ID в Render → Environment.</div>');return}
 const select=document.createElement('select');select.className='field';appState.topup_methods.forEach(m=>{const o=document.createElement('option');o.value=m.key;o.textContent=m.title;select.appendChild(o)});view.appendChild(select);
 const amount=document.createElement('input');amount.className='field';amount.type='number';amount.min=appState.min_topup;amount.max=appState.max_topup;amount.value=String(Math.max(2,Number(appState.min_topup)||2));amount.placeholder='Сумма в сомони';view.appendChild(amount);
 const instructions=document.createElement('div');view.appendChild(instructions);
 view.appendChild(button('Продолжить','primary-button',async()=>{
  const {ok,data}=await api('/webapp/api/topup/create',{method:select.value,amount:Number(amount.value)});
  if(!ok){toast(data.message||'Не удалось начать пополнение');return}
   instructions.innerHTML='';const info=document.createElement('div');info.className='card';info.textContent=data.title+'\nПереведите '+Number(data.amount).toFixed(2)+' с. на '+data.number+(data.holder?'\nПолучатель: '+data.holder:'')+'\nПосле перевода загрузите чек:';instructions.appendChild(info);
  const file=document.createElement('input');file.type='file';file.accept='image/jpeg,image/png,image/webp';file.className='field';instructions.appendChild(file);
  instructions.appendChild(button('Отправить чек','primary-button',async()=>{
   if(!file.files?.[0]){toast('Выберите изображение чека');return}
   const dataForm=new FormData();dataForm.append('init_data',initData);dataForm.append('tid',data.tid);dataForm.append('receipt',file.files[0]);
   const res=await fetch('/webapp/api/topup/receipt',{method:'POST',body:dataForm});const result=await res.json().catch(()=>({}));
   if(!res.ok){toast(result.message||'Чек не отправлен');return}instructions.innerHTML='<div class="card">Чек отправлен на проверку. Баланс обновится после подтверждения.</div>';
  }));
 }));
}
function addEntry(parent,title,sub){const el=document.createElement('div');el.className='entry';const strong=document.createElement('strong');strong.textContent=title;el.appendChild(strong);const small=document.createElement('small');small.textContent=sub||'';el.appendChild(small);parent.appendChild(el)}
function renderHistory(){
 view.innerHTML='<h2>История</h2><div class="card"><strong>Заказы</strong></div>';
 const orders=(appState?.orders||[]);if(!orders.length)view.insertAdjacentHTML('beforeend','<div class="empty">Заказов пока нет</div>');
 else orders.forEach(o=>addEntry(view,(o.title||'Товар')+' · '+Number(o.price||0).toFixed(2)+' с.','№ '+(o.oid||'—')+' · '+(o.status||'')+' · '+new Date((o.ts||0)*1000).toLocaleString()));
 const tx=document.createElement('div');tx.className='card';tx.innerHTML='<strong>Операции баланса</strong>';view.appendChild(tx);
 (appState?.transactions||[]).forEach(x=>addEntry(tx,(Number(x.amount)>0?'+':'')+Number(x.amount).toFixed(2)+' с.',(x.desc||'Операция')+' · '+new Date((x.ts||0)*1000).toLocaleString()));
 if(!(appState?.transactions||[]).length)addEntry(tx,'Операций пока нет','');
 const links=document.createElement('div');links.className='card';links.innerHTML='<strong>Поддержка и новости</strong><div id="linkRow" class="link-row"></div>';view.appendChild(links);
 const row=links.querySelector('#linkRow');
 if(!appState){const note=document.createElement('small');note.className='muted';note.textContent='Ссылки появятся после проверки Telegram и загрузки настроек.';row.appendChild(note);return}
 [['Поддержка',appState.support_url,'SUPPORT_CONTACT'],['Отзывы',appState.reviews_url,'REVIEWS_CHANNEL'],['Канал новостей',appState.news_url,'NEWS_CHANNEL_TG / NEWS_CHANNEL_RU / NEWS_CHANNEL_EN']].forEach(([label,url,setting])=>{if(url){const a=document.createElement('a');a.href=url;a.target='_blank';a.rel='noopener';a.textContent=label;row.appendChild(a)}else{const note=document.createElement('small');note.className='muted';note.textContent=label+': задайте '+setting+' в Render → Environment';row.appendChild(note)}});
}
let timerHandle=null,stateErrorToastShown=false;
function renderGame(){
 view.innerHTML='<h2>Игра с игроками</h2><p class="muted">10 секунд на клики. Результат попадёт в общий рейтинг реальных участников Telegram.</p>';
 const score=document.createElement('div');score.className='card';score.textContent='Ваш лучший результат: '+(appState?.my_score||0);view.appendChild(score);
 const arena=button('Начать игру','game-arena',()=>startGame(arena,score));view.appendChild(arena);
 const timer=document.createElement('div');timer.className='muted';timer.textContent='';view.appendChild(timer);
 const board=document.createElement('div');board.className='card';board.innerHTML='<strong>🏆 Общий рейтинг</strong>';(appState?.leaderboard||[]).forEach((p,i)=>{const row=document.createElement('div');row.className='leader';row.textContent=(i+1)+'. '+p.name;const val=document.createElement('b');val.textContent=p.score;row.appendChild(val);board.appendChild(row)});if(!(appState?.leaderboard||[]).length)addEntry(board,'Пока нет результатов','Станьте первым участником');view.appendChild(board);
 async function startGame(btn,scoreCard){
  if(!initData){toast('Откройте магазин через Telegram');return}
  const {ok,data}=await api('/webapp/api/game/start',{});if(!ok){toast(data.message||'Не удалось начать игру');return}
  let count=0,seconds=10;btn.textContent='Нажимайте! · '+count;btn.disabled=false;timer.textContent='Осталось: '+seconds+' сек.';
  btn.onclick=()=>{if(seconds>0){count++;btn.textContent='Нажимайте! · '+count}};
  timerHandle=setInterval(async()=>{seconds--;timer.textContent='Осталось: '+Math.max(seconds,0)+' сек.';if(seconds<=0){clearInterval(timerHandle);btn.disabled=true;btn.textContent='Счёт: '+count;
    const result=await api('/webapp/api/game/finish',{session_id:data.session_id,score:count});
    if(!result.ok){toast(result.data.message||'Результат не принят');return}
    toast('Результат сохранён');await refreshState();renderGame();
  }},1000);
 }
}
async function refreshState(){
 if(!initData){document.getElementById('balance').textContent='Откройте через DONATEX';if(!stateErrorToastShown){toast('Нажмите /start в боте, затем откройте кнопку DONATEX рядом с полем сообщения.');stateErrorToastShown=true}return}
 const {ok,data}=await api('/webapp/api/state',{});
 if(!ok){document.getElementById('balance').textContent='Telegram не подтверждён';if(!stateErrorToastShown){toast(data.message||'Не удалось получить данные Telegram');stateErrorToastShown=true}return}
 stateErrorToastShown=false;
 appState=data;document.getElementById('balance').textContent='Баланс: '+Number(data.balance||0).toFixed(2)+' с.';
}
document.getElementById('search').addEventListener('input',()=>{if(currentView==='home')renderHome()});
async function loadCatalog(){
 try{const res=await fetch('/webapp/catalog.json');if(!res.ok)throw new Error('catalog');allData=await res.json();if(!Array.isArray(allData))throw new Error('invalid catalog');buildTopGames();renderHome()}catch(_){view.innerHTML='<div class="empty">Не удалось загрузить каталог. Попробуйте позже.</div>'}
}
saveCart();refreshState();loadCatalog();
setInterval(()=>refreshState(),30000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refreshState()});
</script>
</body>
</html>"""


async def h_health(request):
    return web.Response(text="ok")


async def h_webapp(request):
    return web.Response(text=WEBAPP_HTML, content_type="text/html")


async def h_catalog(request):
    await load_catalog()
    out = [{"name": g["name"],
            "products": [{"id": sid(p["product_id"]), "title": ptitle(p), "price": p["price_tjs"]}
                         for p in g["products"]]} for g in catalog.values()]
    return web.json_response(out)


def webapp_identity(init_data):
    """Verify Telegram WebApp initData; never trust initDataUnsafe sent by a client."""
    if not isinstance(init_data, str) or not init_data or len(init_data) > 8192:
        raise ValueError("Откройте Mini App через Telegram.")
    from urllib.parse import parse_qsl
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=False)
    except Exception:
        raise ValueError("Некорректные данные Telegram.")
    values = {}
    for key, value in pairs:
        if key in values:
            raise ValueError("Некорректные данные Telegram.")
        values[key] = value
    received_hash = values.pop("hash", "")
    # С 2025 Telegram добавляет поле signature. Хеш считается БЕЗ него.
    values.pop("signature", None)
    if not received_hash:
        raise ValueError("Telegram не подтвердил пользователя.")
    check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(received_hash, expected_hash):
        raise ValueError("Не удалось подтвердить данные Telegram.")
    try:
        auth_date = int(values.get("auth_date", "0"))
        identity = json.loads(values.get("user", "{}"))
        uid = int(identity.get("id", 0))
    except (TypeError, ValueError, json.JSONDecodeError):
        raise ValueError("Некорректный профиль Telegram.")
    now = int(time.time())
    if not uid or auth_date > now + 60 or now - auth_date > 86400:
        raise ValueError("Сеанс Telegram устарел. Закройте и снова откройте Mini App.")
    return {"id": uid, "first_name": str(identity.get("first_name") or ""),
            "username": str(identity.get("username") or "")}


def webapp_link(value):
    value = str(value or "").strip()
    if not value:
        return ""
    if value.startswith(("https://", "http://", "tg://")):
        return value
    return "https://t.me/" + value.lstrip("@")


def webapp_leaderboard():
    scores = db.get("game_scores", {})
    ordered = sorted(scores.values(), key=lambda item: (-int(item.get("score", 0)),
                                                        int(item.get("ts", 0))))[:20]
    return [{"name": str(item.get("name") or "Игрок")[:32],
             "score": int(item.get("score", 0))}
            for item in ordered]


async def _webapp_json(request):
    try:
        body = await request.json()
    except Exception:
        raise ValueError("Некорректный запрос.")
    if not isinstance(body, dict):
        raise ValueError("Некорректный запрос.")
    return body


async def h_webapp_state(request):
    try:
        body = await _webapp_json(request)
        identity = webapp_identity(body.get("init_data"))
    except ValueError as e:
        log.warning("webapp state rejected: %s", e)
        return web.json_response({"message": str(e)}, status=401)
    uid = identity["id"]
    u = get_user(uid, identity["first_name"] or identity["username"])
    if u["blocked"]:
        return web.json_response({"message": t(uid, "blocked")}, status=403)
    try:
        orders = [o for o in db.get("orders", []) if str(o.get("uid")) == str(uid)][-20:][::-1]
        txs = u.get("transactions", [])[-20:][::-1]
        news = webapp_link(get_news_channel(uid))
        review_url = webapp_link(REVIEWS_CHANNEL)
        return web.json_response({
            "balance": round(float(u.get("balance", 0)), 2),
            "customer_no": int(u.get("customer_no", 0)),
            "sensitivity_credits": int(u.get("sensitivity_credits", 0)),
            "free_sensitivity_available": not bool(u.get("free_sensitivity_used")),
            "orders": [{"oid": str(o.get("oid", "")), "title": str(o.get("title", "")),
                        "price": float(o.get("price", 0)), "status": str(o.get("status", "")),
                        "ts": int(o.get("ts", 0))} for o in orders],
            "transactions": [{"amount": float(x.get("amount", 0)),
                              "desc": str(x.get("desc", "")), "ts": int(x.get("ts", 0))}
                             for x in txs],
            "topup_methods": [{"key": key, "title": item["title"]}
                              for key, item in PAY_METHODS.items()],
            "topup_receipts_enabled": bool(ADMIN_ID),
            "min_topup": MIN_TOPUP, "max_topup": MAX_TOPUP,
            "support_url": webapp_link(SUPPORT_CONTACT),
            "reviews_url": review_url, "news_url": news,
            "leaderboard": webapp_leaderboard(),
            "my_score": int(db.get("game_scores", {}).get(str(uid), {}).get("score", 0)),
            "saved_ids": [{"id": str(x.get("id") or ""), "nick": str(x.get("nick") or ""),
                           "game": str(x.get("game") or "")}
                          for x in (u.get("saved_ids") or [])[:8] if x.get("id")],
        })
    except Exception as e:
        log.exception("webapp state: %s", e)
        return web.json_response({"message": "Не удалось загрузить данные аккаунта."}, status=500)


async def h_webapp_order(request):
    try:
        body = await _webapp_json(request)
        identity = webapp_identity(body.get("init_data"))
    except ValueError as e:
        return web.json_response({"message": str(e)}, status=401)
    uid = identity["id"]
    u = get_user(uid, identity["first_name"] or identity["username"])
    if u["blocked"]:
        return web.json_response({"error": "blocked", "message": t(uid, "blocked")}, status=403)
    player_id = str(body.get("player_id", "")).strip()
    if not re.fullmatch(r"\d{6,15}", player_id):
        return web.json_response({"message": "Введите ID игрока из 6–15 цифр."}, status=400)
    await load_catalog()
    product = prod_short.get(str(body.get("product_id", "")))
    if not product:
        return web.json_response({"message": "Товар больше недоступен. Обновите каталог."}, status=404)
    request_id = str(body.get("request_id", ""))
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,80}", request_id):
        return web.json_response({"message": "Обновите экран и повторите покупку."}, status=400)
    requests = db.setdefault("webapp_order_requests", {})
    request_key = f"{uid}:{request_id}"
    previous = requests.get(request_key)
    if previous:
        if previous.get("status") == "processing":
            return web.json_response({"error": "busy",
                                      "message": "Этот заказ уже обрабатывается."}, status=409)
        return web.json_response(previous.get("result", {}),
                                 status=int(previous.get("http_status", 200)))
    requests[request_key] = {"status": "processing", "ts": now_ts()}
    save_db()
    try:
        nick = await lookup_player_nick(product, player_id)
        remember_player_id(uid, player_id, nick, ptitle(product))
        result = await create_order(
            uid, uid, ptitle(product), float(product["price_tjs"]),
            float(product.get("price_usd", 0)),
            {"product_id": product["product_id"], "fields": {"player_id": player_id}},
            notify=False,
        )
    except Exception as e:
        log.exception("webapp order request failed: %s", e)
        await notify_admin(f"⚠️ Mini App: ошибка обработки заказа пользователя {uid}; "
                           "проверьте статус заказа перед повторной попыткой.")
        result = {"ok": False, "error": "order_uncertain"}
    if result.get("ok"):
        status = 200
    else:
        result["message"] = {
            "blocked": "Аккаунт заблокирован.",
            "busy": "Предыдущий заказ ещё обрабатывается.",
            "insufficient_balance": "Недостаточно средств на балансе.",
            "provider_unavailable": "Поставщик временно недоступен. Деньги возвращены.",
            "order_uncertain": "Платёж проверяется. Не отправляйте этот заказ повторно.",
            "provider_rejected": "Поставщик отклонил заказ. Деньги возвращены.",
        }.get(result.get("error"), "Не удалось оформить заказ.")
        status = 409 if result.get("error") in ("busy", "insufficient_balance", "order_uncertain") else 400
    requests[request_key] = {"status": "done", "result": result,
                             "http_status": status, "ts": now_ts()}
    if len(requests) > 1000:
        for old_key, _ in sorted(requests.items(), key=lambda item: item[1].get("ts", 0))[:-800]:
            requests.pop(old_key, None)
    save_db()
    return web.json_response(result, status=status)


async def h_webapp_topup_create(request):
    try:
        body = await _webapp_json(request)
        identity = webapp_identity(body.get("init_data"))
    except ValueError as e:
        return web.json_response({"message": str(e)}, status=401)
    uid = identity["id"]
    if get_user(uid)["blocked"]:
        return web.json_response({"message": t(uid, "blocked")}, status=403)
    method = str(body.get("method", ""))
    if method not in PAY_METHODS:
        return web.json_response({"message": "Выберите доступный способ оплаты."}, status=400)
    try:
        amount = float(body.get("amount"))
    except (TypeError, ValueError):
        amount = 0
    if not MIN_TOPUP <= amount <= MAX_TOPUP:
        return web.json_response({"message": f"Сумма должна быть от {MIN_TOPUP:g} до {MAX_TOPUP:g} с."},
                                 status=400)
    tid = uuid.uuid4().hex[:10]
    db["topups"][tid] = {"uid": uid, "amount": round(amount, 2), "method": method,
                         "status": "pending", "ts": now_ts()}
    save_db()
    payment = PAY_METHODS[method]
    return web.json_response({"tid": tid, "amount": round(amount, 2),
                              "title": payment["title"], "number": payment["number"],
                              "holder": payment.get("holder", "")})


async def h_webapp_topup_receipt(request):
    try:
        form = await request.post()
        identity = webapp_identity(form.get("init_data", ""))
    except ValueError as e:
        return web.json_response({"message": str(e)}, status=401)
    except Exception:
        return web.json_response({"message": "Не удалось прочитать чек."}, status=400)
    tid = str(form.get("tid", ""))
    topup = db.get("topups", {}).get(tid)
    if not topup or str(topup.get("uid")) != str(identity["id"]) or topup.get("status") != "pending":
        return web.json_response({"message": "Заявка не найдена или чек уже отправлен."}, status=404)
    if get_user(identity["id"])["blocked"]:
        return web.json_response({"message": t(identity["id"], "blocked")}, status=403)
    if not RECEIPTS_CHANNEL_ID:
        return web.json_response({"message": "Канал чеков не настроен. Обратитесь в поддержку."},
                                 status=503)
    file = form.get("receipt")
    if not hasattr(file, "file") or not hasattr(file, "content_type"):
        return web.json_response({"message": "Прикрепите изображение чека."}, status=400)
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        return web.json_response({"message": "Поддерживаются JPG, PNG и WEBP."}, status=400)
    file_bytes = file.file.read(5 * 1024 * 1024 + 1)
    if not file_bytes or len(file_bytes) > 5 * 1024 * 1024:
        return web.json_response({"message": "Размер изображения должен быть не больше 5 МБ."},
                                 status=400)
    uid = identity["id"]
    pm = PAY_METHODS.get(topup.get("method"), {})
    user = get_user(uid, identity["first_name"], identity["username"])
    caption = (f"🧾 ЧЕК ИЗ MINI APP · {tid}\n👤 {esc(identity['first_name'] or identity['username'])} "
               f"· @{esc(identity['username'] or '—')}\n🆔 ID: <code>{uid}</code> · № харидор: <b>{user['customer_no']}</b>"
               f"\n💵 Хочет пополнить: <b>{topup['amount']:.2f} с.</b> · {esc(pm.get('title', ''))}")
    topup["status"] = "uploading"
    save_db()
    try:
        filename = Path(file.filename or "receipt.jpg").name[:80]
        await bot.send_photo(
            RECEIPTS_CHANNEL_ID, BufferedInputFile(file_bytes, filename),
            caption=caption,
            reply_markup=kb([[btn("✅ Тасдиқ", f"tok:{tid}"),
                              btn("❌ Рад", f"tno:{tid}")]]),
        )
    except Exception as e:
        topup["status"] = "pending"
        save_db()
        log.warning("webapp receipt delivery: %s", e)
        return web.json_response({"message": "Не удалось передать чек на проверку."}, status=502)
    topup["status"] = "review"
    save_db()
    return web.json_response({"ok": True})


webapp_game_sessions = {}


async def h_webapp_game_start(request):
    try:
        body = await _webapp_json(request)
        identity = webapp_identity(body.get("init_data"))
    except ValueError as e:
        return web.json_response({"message": str(e)}, status=401)
    uid = identity["id"]
    if get_user(uid)["blocked"]:
        return web.json_response({"message": t(uid, "blocked")}, status=403)
    session_id = secrets.token_urlsafe(18)
    webapp_game_sessions[str(uid)] = {"id": session_id, "started": time.time()}
    return web.json_response({"session_id": session_id})


async def h_webapp_game_finish(request):
    try:
        body = await _webapp_json(request)
        identity = webapp_identity(body.get("init_data"))
    except ValueError as e:
        return web.json_response({"message": str(e)}, status=401)
    uid = identity["id"]
    session = webapp_game_sessions.get(str(uid))
    if not session or not hmac.compare_digest(str(body.get("session_id", "")), session["id"]):
        return web.json_response({"message": "Игра не найдена. Начните заново."}, status=409)
    elapsed = time.time() - session["started"]
    webapp_game_sessions.pop(str(uid), None)
    score = body.get("score")
    if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 160:
        return web.json_response({"message": "Результат не прошёл проверку."}, status=400)
    if elapsed < 8.5 or elapsed > 35:
        return web.json_response({"message": "Время игры истекло. Попробуйте ещё раз."}, status=400)
    u = get_user(uid, identity["first_name"] or identity["username"])
    scores = db.setdefault("game_scores", {})
    previous = scores.get(str(uid), {})
    if score > int(previous.get("score", 0)):
        scores[str(uid)] = {"score": score, "name": u.get("name") or "Игрок", "ts": now_ts()}
        save_db()
    return web.json_response({
        "score": int(scores.get(str(uid), {}).get("score", 0)),
        "leaderboard": webapp_leaderboard(),
    })


async def main():
    await init_db()
    GAME_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    app = web.Application(client_max_size=6 * 1024 * 1024)
    app.add_routes([web.get("/", h_health), web.get("/webapp", h_webapp),
                    web.get("/webapp/catalog.json", h_catalog),
                    web.post("/webapp/api/state", h_webapp_state),
                    web.post("/webapp/api/order", h_webapp_order),
                    web.post("/webapp/api/topup/create", h_webapp_topup_create),
                    web.post("/webapp/api/topup/receipt", h_webapp_topup_receipt),
                    web.post("/webapp/api/game/start", h_webapp_game_start),
                    web.post("/webapp/api/game/finish", h_webapp_game_finish)])
    app.router.add_static("/webapp/images/", str(GAME_IMAGE_DIR), show_index=False)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    log.info("web on :%s", PORT)

    tasks = [asyncio.create_task(saver_loop()), asyncio.create_task(balance_watcher()),
             asyncio.create_task(keepalive())]
    await load_catalog(force=True)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        # Регистрируем команды в меню бота
        from aiogram.types import BotCommand
        await bot.set_my_commands([
            BotCommand(command="start",   description="🏠 Главное меню"),
            BotCommand(command="balance", description="💰 Мой баланс"),
            BotCommand(command="help",    description="📖 Помощь"),
        ])
        # Убираем кнопку Mini App — только стандартное меню команд
        try:
            await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        except Exception as e:
            log.warning("set_chat_menu_button: %s", e)
        await dp.start_polling(bot)
    finally:
        for tk in tasks:
            tk.cancel()
        global _dirty
        _dirty = True
        await persist()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
