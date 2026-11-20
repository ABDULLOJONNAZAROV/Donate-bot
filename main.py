import asyncio
import csv
import hashlib
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
                           ReplyKeyboardMarkup, WebAppInfo)

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
REF_PERCENT = float(os.environ.get("REF_PERCENT", "5"))
LOW_BALANCE_USD = float(os.environ.get("LOW_BALANCE_USD", "5"))
BALANCE_PATH = os.environ.get("DONATIX_BALANCE_PATH", "/balance")
SUPPORT_CONTACT = os.environ.get("SUPPORT_CONTACT", "")
MIN_TOPUP = float(os.environ.get("MIN_TOPUP", "5"))
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
# Процент бонуса на первую покупку (скидка)
FIRST_BONUS_PERCENT = float(os.environ.get("FIRST_BONUS_PERCENT", "10"))

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
        # Добавлен текст про бонус на первую покупку и статистику
        "welcome": (
            "🔥❤️ Хуш омадед ба DONATEX!\n\n"
            "💎 Алмос ва UC — бо ID-и бозингар, пардохт бо сомонӣ.\n"
            "⚡ Фармоиш пас аз пардохт худкор иҷро мешавад.\n"
            "🎁 Бонус {bonus}% ба аввалин харид!\n\n"
            "✅ Иҷро шуд: {orders}+ фармоиш | 👥 Муштариён: {users}+\n\n"
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
        "first_bonus_line": "\n🎁 Бонуси аввалин харид: -{pct}%",
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
            "⚡ Заказ выполняется автоматически после оплаты.\n"
            "🎁 Бонус {bonus}% на первую покупку!\n\n"
            "✅ Выполнено: {orders}+ заказов | 👥 Клиентов: {users}+\n\n"
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
        "first_bonus_line": "\n🎁 Бонус первой покупки: -{pct}%",
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
            "⚡ Orders are fulfilled automatically after payment.\n"
            "🎁 {bonus}% bonus on your first purchase!\n\n"
            "✅ Completed: {orders}+ orders | 👥 Customers: {users}+\n\n"
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
        "first_bonus_line": "\n🎁 First purchase bonus: -{pct}%",
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
DEFAULT_DB = {"users": {}, "topups": {}, "orders": [], "promos": {}, "meta": {}}
# Добавлены новые поля: first_purchase_bonus_used, transactions
USER_DEFAULTS = {
    "balance": 0.0, "name": "", "blocked": False, "lang": "tg", "ref_by": None,
    "refs": 0, "ref_earned": 0.0, "topped": False, "promo": None, "joined": 0,
    "first_purchase_bonus_used": False,  # флаг бонуса на первую покупку
    "transactions": [],                   # история операций
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


def get_user(uid, name=""):
    uid = str(uid)
    u = db["users"].get(uid)
    if u is None:
        u = {**USER_DEFAULTS, "joined": int(time.time()), "transactions": []}
        db["users"][uid] = u
    for k, v in USER_DEFAULTS.items():
        if k == "transactions":
            u.setdefault(k, [])
        else:
            u.setdefault(k, v)
    if name and u["name"] != name:
        u["name"] = name
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
    return InlineKeyboardButton(text=text, callback_data=data)


def lbtn(text, url):
    """Кнопка-ссылка"""
    return InlineKeyboardButton(text=text, url=url)


def is_admin(uid):
    return ADMIN_ID != 0 and uid == ADMIN_ID


def sid(s):
    return hashlib.md5(str(s).encode()).hexdigest()[:8]


def now_ts():
    return int(time.time())


# ===================== Вспомогательная функция для пустых состояний =====================
def cta_kb(uid):
    """Клавиатура с призывом к действию — используется вместо тупиковых экранов."""
    return kb([[btn(t(uid, "popular"), "popular"), btn(t(uid, "menu"), "menu")]])


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
      
def ptitle(p):
    return str(p.get("title") or p.get("name") or p.get("product_id"))


# ===================== Популярные товары =====================
def get_popular_products(days=30, limit=10):
    """Возвращает топ-N товаров по количеству заказов за последние N дней."""
    since = time.time() - days * 86400
    counts = {}
    for o in db["orders"]:
        if o.get("status") == "failed":
            continue
        if o.get("ts", 0) < since:
            continue
        title = o.get("title", "")
        counts[title] = counts.get(title, 0) + 1
    # Сортируем по убыванию
    top = sorted(counts.items(), key=lambda x: -x[1])[:limit]
    # Находим товары в каталоге по названию
    result = []
    for title, cnt in top:
        for p in prod_short.values():
            if ptitle(p) == title:
                result.append((p, cnt))
                break
    return result


# ===================== Поиск ника игрока =====================
async def lookup_player_nick(product_id: str, player_id: str) -> str:
    """Пытается найти ник игрока через Donatix API."""
    if not DONATIX_KEY:
        return ""
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"{API}/player",
                params={"product_id": product_id, "player_id": player_id},
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status != 200:
                    return ""
                d = await r.json(content_type=None)
        if isinstance(d, dict):
            nick = (d.get("nickname") or d.get("name") or d.get("username") or
                    d.get("player_name") or d.get("playerName") or "")
            return str(nick).strip()
    except Exception as e:
        log.debug("lookup_player_nick: %s", e)
    return ""


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
    """Рассчитывает финальную цену с учётом промокода и бонуса на первую покупку."""
    u = get_user(uid)

    # Проверяем бонус на первую покупку
    if not u.get("first_purchase_bonus_used", False):
        discount = FIRST_BONUS_PERCENT / 100
        return round(base * (1 - discount), 2), None, True  # цена, промокод, is_first_bonus

    # Иначе проверяем промокод
    code = u.get("promo")
    p = db["promos"].get(code) if code else None
    if p and promo_valid(p, uid):
        return round(base * (1 - p["percent"] / 100), 2), code, False
    return round(base, 2), None, False


# ===================== Состояния =====================
user_state = {}
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
async def send_menu(msg, user):
    await load_catalog()
    uid = user.id
    u = get_user(uid, user.full_name or "")
    user_state.pop(uid, None)

    # Динамическая статистика для приветствия (пункт 3)
    total_orders = len([o for o in db["orders"] if o.get("status") == "done"])
    total_users = len(db["users"])

    welcome_text = t(uid, "welcome",
                     bonus=f"{FIRST_BONUS_PERCENT:g}",
                     orders=total_orders,
                     users=total_users,
                     bal=f"{u['balance']:.2f}")

    rows = [
        # Кнопка "Популярное" первой (пункт 2)
        [btn(t(uid, "popular"), "popular")],
        [btn("🔥 FF СНГ 💎", "game:ff_cis"), btn("🇮🇩 FF Индонезия 💎", "game:ff_id")],
        [btn("🎯 PUBG Mobile UC 🏆", "game:pubg")],
        [btn(t(uid, "all_games"), "allp:0"), btn(t(uid, "stars"), "tg_stars")],
        [btn(t(uid, "balance"), "balance"), btn(t(uid, "orders"), "my_orders")],
        [btn(t(uid, "promo"), "promo"), btn(t(uid, "ref"), "ref")],
        [btn(t(uid, "support"), "support"), btn(t(uid, "lang"), "lang")],
    ]

    # Кнопка новостей (пункт 11)
    news_ch = get_news_channel(uid)
    if news_ch:
        rows.append([btn(t(uid, "news"), "news_channel")])

    if is_admin(uid):
        rows.append([btn("🛠 Панели админ", "admin")])

    markup = kb(rows)

    # Добавляем кнопку отзывов если есть канал (пункт 3)
    if REVIEWS_CHANNEL:
        ch_url = REVIEWS_CHANNEL if REVIEWS_CHANNEL.startswith("http") else f"https://t.me/{REVIEWS_CHANNEL.lstrip('@')}"
        # Добавляем кнопку-ссылку — делаем отдельное сообщение с этой кнопкой
        await msg.answer(welcome_text, reply_markup=kb(
            rows[:-1] + [[lbtn(t(uid, "reviews_btn"), ch_url)]] + [rows[-1]] if is_admin(uid)
            else rows + [[lbtn(t(uid, "reviews_btn"), ch_url)]]
        ))
    else:
        await msg.answer(welcome_text, reply_markup=markup)


@dp.message(CommandStart())
async def start(m, command: CommandObject):
    uid = m.from_user.id
    is_new = str(uid) not in db["users"]
    u = get_user(uid, m.from_user.full_name or "")
    if is_new and command.args and command.args.startswith("ref_"):
        rid = command.args[4:]
        if rid != str(uid) and rid in db["users"]:
            u["ref_by"] = rid
            db["users"][rid]["refs"] = db["users"][rid].get("refs", 0) + 1
    save_db()
    await send_menu(m, m.from_user)
    if EXTERNAL_URL:
        await m.answer(t(uid, "shop_hint"), reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=t(uid, "shop"),
                                      web_app=WebAppInfo(url=f"{EXTERNAL_URL}/webapp"))]],
            resize_keyboard=True))


@dp.message(Command("buy"))
async def buy(m):
    await send_menu(m, m.from_user)


@dp.message(Command("help"))
async def help_cmd(m):
    await m.answer(t(m.from_user.id, "help"))


@dp.message(Command("balance"))
async def balance_cmd(m):
    uid = m.from_user.id
    u = get_user(uid, m.from_user.full_name or "")
    text = t(uid, "bal_text", bal=f"{u['balance']:.2f}") + tx_text(uid)
    await m.answer(text, reply_markup=kb([[btn(t(uid, "topup"), "topup")]]))


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
    contact = esc(SUPPORT_CONTACT) if SUPPORT_CONTACT else "—"
    await c.message.answer(t(uid, "support_text", contact=contact),
                           reply_markup=kb([[btn(t(uid, "menu"), "menu")]]))
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
    top = get_popular_products()
    if not top:
        # Если статистики нет — показываем случайные из каталога
        all_prods = list(prod_short.values())[:10]
        if not all_prods:
            await c.message.answer(t(uid, "no_popular"), reply_markup=cta_kb(uid))
            return
        rows = []
        for p in all_prods:
            rows.append([btn(f"{ptitle(p)[:25]} — {p['price_tjs']} с.", f"pkg:{sid(p['product_id'])}")])
        rows.append([btn(t(uid, "menu"), "menu")])
        await edit_or_send(c.message, t(uid, "popular_title"), kb(rows))
        return
    rows = []
    for p, cnt in top:
        rows.append([btn(f"🔥 {ptitle(p)[:22]} — {p['price_tjs']} с. ({cnt}×)", f"pkg:{sid(p['product_id'])}")])
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
    for cid, g in catalog.items():
        hay = (str(cid) + " " + g["name"]).lower().replace("_", " ")
        if game == "ff_cis" and "free fire" in hay and ("cis" in hay or "снг" in hay) and "indon" not in hay:
            return cid
        if game == "ff_id" and "free fire" in hay and "indon" in hay:
            return cid
        if game == "pubg" and "pubg" in hay:
            return cid
    return None


# ===================== /ff команда — профиль Free Fire =====================
FF_REGIONS = ["sg", "ind", "br", "us", "vn", "th", "tw", "id", "me", "pk", "cis", "bd", "ru"]

async def fetch_ff_player(uid: str, region: str = "sg"):
    """
    Пробует несколько живых API с GitHub.
    Возвращает словарь с данными или None.
    """
    apis = [
        # BIELVENDAs/free-ff-api — самый надёжный вариант
        f"https://free-ff-api-src-5plp.onrender.com/api/v1/account?region={region}&uid={uid}",
        # PRINCE-LKTEAM/Free-Fire-API — запасной вариант через поиск
        f"https://freefireinfo-zy9l.onrender.com/api/v1/search-players?keyword={uid}&server={region}",
    ]
    async with aiohttp.ClientSession() as session:
        for url in apis:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json(content_type=None)
                    # Приводим ответ к единому виду, который ждёт ваш fmt_ff_profile
                    if isinstance(data, dict):
                        # BIELVENDAs обычно отдаёт {"profileInfo": {...}, ...}
                        if "profileInfo" in data:
                            return data
                        # PRINCE-LKTEAM отдаёт {"infos": [ {...} ]}
                        if "infos" in data and data["infos"]:
                            return {"basicinfo": data["infos"][0]}
            except Exception as e:
                log.debug("FF API %s: %s", url, e)
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


@dp.message(Command("ff"))
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
@dp.message(Command("look"))
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
@dp.message(Command("guild"))
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
@dp.message(Command("age"))
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
@dp.message(Command("bio"))
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
        await show_all_games(c, 0)


@dp.callback_query(F.data.startswith("allp:"))
async def cb_allp(c):
    await c.answer()
    await load_catalog()
    await show_all_games(c, int(c.data.split(":")[1]))


async def show_all_games(c, page):
    uid = c.from_user.id
    ids = list(catalog.keys())
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
    g = catalog.get(cid)
    if not g:
        await c.message.answer(t(uid, "nf"), reply_markup=cta_kb(uid))
        return
    groups = {}
    for p in g["products"]:
        groups.setdefault(group_of(p), []).append(p)
    text = f"<b>{esc(g['name'])}</b>\n━━━ {t(uid, 'pick_pkg')}\n"
    rows, total = [], 0
    for grp, prods in groups.items():
        text += f"\n━━ {grp} ━━"
        line = []
        for p in prods:
            if total >= 90:
                break
            total += 1
            line.append(btn(f"{ptitle(p)[:20]} — {p['price_tjs']} с.", f"pkg:{sid(p['product_id'])}"))
            if len(line) == 2:
                rows.append(line)
                line = []
        if line:
            rows.append(line)
    rows.append([btn(t(uid, "menu"), "menu")])
    await edit_or_send(c.message, text, kb(rows))


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
    user_state[uid] = {"stage": "waiting_id", "product": p}
    await c.message.answer(t(uid, "enter_id", title=esc(ptitle(p)), price=p["price_tjs"]))
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
        user_state[uid] = {"stage": "waiting_uname", "title": f"👑 {ptitle(p)}",
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
    user_state[uid] = {"stage": "waiting_id", "product": p}
    await m.answer(t(uid, "enter_id", title=esc(ptitle(p)), price=p["price_tjs"]))


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
            p = st["product"]
            # Ищем ник игрока автоматически
            nick = await lookup_player_nick(p["product_id"], txt)
            tok = new_pending(uid=uid, pid=txt, product=p, nick=nick)
            user_state.pop(uid, None)
            nick_line = f"\n{t(uid, 'nick_found', nick=esc(nick))}" if nick else f"\n{t(uid, 'nick_not_found')}"
            await m.answer(
                t(uid, "confirm_id", pid=txt) + nick_line,
                reply_markup=kb([[btn(t(uid, "id_ok"), f"idok:{tok}"),
                                  btn(t(uid, "id_edit"), f"idedit:{tok}")]])
            )
        else:
            await m.answer(t(uid, "bad_id"))

    elif stage == "waiting_uname":
        if re.fullmatch(r"@[A-Za-z0-9_]{5,32}", txt):
            user_state.pop(uid, None)
            body = {**st["body"], "fields": {"telegram_username": txt}}
            await ask_confirm(m, uid, st["title"], txt, st["base"], st["cost_usd"], body)
        else:
            await m.answer(t(uid, "bad_uname"))

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
                await bot.send_message(i, txt)
                ok += 1
            except Exception:
                pass
            await asyncio.sleep(0.05)
        await m.answer(f"✅ Расонида шуд: {ok}/{len(ids)}")


# ===================== Антифрод — подтверждение ID =====================
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
    # Используем ник из pending или ищем заново
    nick = data.get("nick") or await lookup_player_nick(p["product_id"], pid)
    target = f"{pid} ({nick})" if nick else pid
    await ask_confirm(c.message, uid, ptitle(p), target, p["price_tjs"],
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
        user_state[uid] = {"stage": "waiting_id", "product": p}
        await c.message.answer(t(uid, "enter_id", title=esc(ptitle(p)), price=p["price_tjs"]))
    await c.answer()


@dp.callback_query(F.data == "cancel")
async def cb_cancel(c):
    user_state.pop(c.from_user.id, None)
    await edit_or_send(c.message, t(c.from_user.id, "cancelled"))
    await c.answer()


# ===================== Заказы =====================
async def ask_confirm(m, uid, title, target, base, cost_usd, body):
    u = get_user(uid)
    price, code, is_first_bonus = final_price(uid, base)
    promo = ""
    if is_first_bonus:
        promo = t(uid, "first_bonus_line", pct=f"{FIRST_BONUS_PERCENT:g}")
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


async def create_order(uid, chat_id, title, base, cost_usd, body):
    u = get_user(uid)
    if u["blocked"]:
        await bot.send_message(chat_id, t(uid, "blocked"))
        return
    lock = user_locks[uid]
    if lock.locked():
        await bot.send_message(chat_id, t(uid, "busy"))
        return
    async with lock:
        price, code, is_first_bonus = final_price(uid, base)
        if u["balance"] < price:
            await bot.send_message(chat_id, t(uid, "low", price=price, bal=f"{u['balance']:.2f}"),
                                   reply_markup=kb([[btn(t(uid, "topup"), "topup")]]))
            return
        # Резервируем сумму ДО запроса
        u["balance"] = round(u["balance"] - price, 2)
        # Записываем транзакцию списания (пункт 6)
        add_transaction(uid, -price, "order", title[:30])
        idem = str(uuid.uuid4())
        rec = {"oid": "?", "idem": idem, "uid": uid, "name": u["name"], "title": title, "price": price,
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
            await bot.send_message(chat_id, t(uid, "order_err", err=esc(e)))
            return
        except Exception as e:
            rec["status"] = "uncertain"
            save_db()
            await bot.send_message(chat_id, t(uid, "order_wait"))
            await notify_admin(f"⚠️ Заказ не подтверждён (таймаут/сбой): {esc(u['name'])} ({uid})\n"
                               f"{esc(title)} · {price} с. · Idempotency-Key: <code>{idem}</code>\n{esc(e)}")
            return

        if isinstance(data, dict) and data.get("ok"):
            oid = (data.get("order") or {}).get("order_id", "?")
            rec["oid"] = oid
            rec["status"] = "done"

            # Применяем бонус первой покупки (пункт 1)
            if is_first_bonus:
                u["first_purchase_bonus_used"] = True

            if code:
                p = db["promos"].get(code)
                if p:
                    p["used"] = p.get("used", 0) + 1
                    p.setdefault("users", []).append(str(uid))
                u["promo"] = None
            save_db()
            await bot.send_message(chat_id, t(uid, "order_ok", oid=esc(oid), price=price,
                                              bal=f"{u['balance']:.2f}"))
            await notify_admin(f"💸 Фурӯш: #{esc(oid)} · {esc(title)} · {price} с. · {esc(u['name'])}")

            # Запрашиваем отзыв после успешного заказа (пункт 10)
            await request_review(uid, chat_id, title)

        elif http >= 500:
            rec["status"] = "uncertain"
            save_db()
            await bot.send_message(chat_id, t(uid, "order_wait"))
            await notify_admin(f"⚠️ Donatix HTTP {http}: {esc(u['name'])} ({uid}) {esc(title)} · {price} с.\n"
                               f"Idempotency-Key: <code>{idem}</code>")
        else:
            err = (data.get("error") if isinstance(data, dict) else None) or f"HTTP {http}"
            await refund(u, rec, price)
            await bot.send_message(chat_id, t(uid, "order_err", err=esc(err)))
            low = str(err).lower()
            if any(w in low for w in ("balance", "fund", "insufficient", "баланс")):
                await notify_admin(f"🚨 Баланс Donatix, эҳтимол, тамом шуд!\n{esc(err)}")


# ===================== Система отзывов (пункт 10) =====================
async def request_review(uid, chat_id, title):
    """Отправляет пользователю запрос на оценку после успешного заказа."""
    try:
        rows = [[
            btn("⭐1", f"rv:{uid}:1:{sid(title)}"),
            btn("⭐2", f"rv:{uid}:2:{sid(title)}"),
            btn("⭐3", f"rv:{uid}:3:{sid(title)}"),
            btn("⭐4", f"rv:{uid}:4:{sid(title)}"),
            btn("⭐5", f"rv:{uid}:5:{sid(title)}"),
        ]]
        # Сохраняем заголовок заказа во временном хранилище
        db["meta"][f"rv_title_{uid}"] = title
        await bot.send_message(chat_id, t(uid, "review_ask"), reply_markup=kb(rows))
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
    await c.message.answer(t(uid, "review_text_ask"))
    await c.answer()


# ===================== Пополнение (ускоренный путь — пункт 5) =====================
@dp.callback_query(F.data == "topup")
async def cb_topup(c):
    uid = c.from_user.id
    if get_user(uid, c.from_user.full_name or "")["blocked"]:
        await c.answer(t(uid, "blocked"), show_alert=True)
        return
    if not PAY_METHODS:
        await c.answer(t(uid, "no_pay"), show_alert=True)
        return

    # Если метод оплаты один — сразу показываем суммы (сокращение пути)
    if len(PAY_METHODS) == 1:
        mk = list(PAY_METHODS.keys())[0]
        await _show_topup_amounts(c, uid, mk)
    else:
        # Показываем методы, но сразу со встроенными суммами
        rows = []
        for mk, mm in PAY_METHODS.items():
            rows.append([btn(mm["title"], f"tm:{mk}")])
            # Добавляем быстрые суммы прямо под каждым методом
            rows.append([btn(f"10с", f"tamt:10:{mk}"), btn(f"20с", f"tamt:20:{mk}"),
                         btn(f"50с", f"tamt:50:{mk}")])
            rows.append([btn(f"100с", f"tamt:100:{mk}"), btn(f"200с", f"tamt:200:{mk}"),
                         btn(t(uid, "other"), f"tamt:custom:{mk}")])
        rows.append([btn(t(uid, "menu"), "menu")])
        await c.message.answer(t(uid, "choose_pay"), reply_markup=kb(rows))
    await c.answer()


async def _show_topup_amounts(c, uid, mk):
    """Показывает выбор суммы для конкретного метода оплаты."""
    rows = [[btn(f"{v} с.", f"tamt:{v}:{mk}") for v in (10, 20, 50)],
            [btn(f"{v} с.", f"tamt:{v}:{mk}") for v in (100, 200)],
            [btn(t(uid, "other"), f"tamt:custom:{mk}")]]
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
        await c.message.answer(t(uid, "enter_amt", min=f"{MIN_TOPUP:g}", max=f"{MAX_TOPUP:g}"))
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
                       holder=holder, amount=f"{amount:.2f}"))


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
    if ADMIN_ID:
        await bot.copy_message(ADMIN_ID, m.chat.id, m.message_id)
        await bot.send_message(
            ADMIN_ID,
            f"🧾 Чек! 👤 {esc(m.from_user.full_name)} (ID {uid})\n"
            f"💵 {topup['amount']:.2f} с. · {esc(PAY_METHODS.get(topup['method'], {}).get('title', ''))} · {st['tid']}",
            reply_markup=kb([[btn("✅ Тасдиқ", f"tok:{st['tid']}"), btn("❌ Рад", f"tno:{st['tid']}")]]))
    await m.answer(t(uid, "receipt_ok"))


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
                                      bal=f"{u['balance']:.2f}"))
    except Exception:
        pass
    await c.message.edit_text((c.message.html_text or "") + f"\n\n✅ Тасдиқ: {esc(c.from_user.full_name)}")
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
    await c.message.edit_text((c.message.html_text or "") + f"\n\n❌ Рад: {esc(c.from_user.full_name)}")
    await c.answer()


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
    rows = [[btn("👥 Харидорон", "adm_users:0"), btn(f"🧾 Чеки нав ({pending})", "adm_pending")],
            [btn("📦 Фармоишҳо", "adm_orders"), btn("📊 Омор", "adm_stats")],
            [btn("🎟 Промокодҳо", "adm_promos"), btn("📢 Рассылка", "adm_bc")],
            [btn("💼 Баланси Donatix", "adm_dbal"), btn("🏠 Меню", "menu")]]
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
    rows = [[btn(f"{'🚫 ' if u['blocked'] else ''}{u['name'][:22] or k} — {u['balance']:.0f} с.", f"adu:{k}")]
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
    text = (f"👤 <b>{esc(u['name'] or k)}</b> (<code>{k}</code>)\n💰 Баланс: {u['balance']:.2f} с.\n"
            f"📦 Фармоишҳо: {n_orders}\n👥 Даъват: {u['refs']}\n🚫 Блок: {'ҳа' if u['blocked'] else 'не'}\n"
            f"🎁 Бонус истифода: {'ҳа' if u.get('first_purchase_bonus_used') else 'не'}")
    rows = [[btn("✅ Бикушоед" if u["blocked"] else "🚫 Блок", f"adb:{k}"),
             btn("0️⃣ Сброс баланс", f"adr:{k}")],
            [btn("➕/➖ Баланс", f"ada:{k}")],
            [btn("🔙", "adm_users:0")]]
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


@dp.callback_query(F.data == "adm_pending")
@admin_only
async def cb_adm_pending(c):
    await c.answer()
    items = [(k, x) for k, x in db["topups"].items() if x["status"] in ("pending", "review")][-10:]
    if not items:
        await c.message.answer("🧾 Чеки нав нест.")
        return
    for k, x in items:
        u = get_user(x["uid"])
        await c.message.answer(
            f"🧾 {esc(u['name'])} (ID {x['uid']})\n💵 {x['amount']:.2f} с. · {k}"
            f"{' · чек нест (pending)' if x['status'] == 'pending' else ''}",
            reply_markup=kb([[btn("✅ Тасдиқ", f"tok:{k}"), btn("❌ Рад", f"tno:{k}")]]))


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
  { key: 'pubg',     label: 'PUBG Mobile',     icon: '🎯',  bg: 'linear-gradient(135deg,#4a3500,#2a1e00)', top: true },
  { key: 'mlbb',     label: 'Mobile Legends',  icon: '⚔️', bg: 'linear-gradient(135deg,#1a4a2e,#0d2a1a)', top: false },
  { key: 'standoff', label: 'Standoff 2',      icon: '🔫', bg: 'linear-gradient(135deg,#2e1a4a,#1a0d2a)', top: false },
  { key: 'telegram', label: 'TG Stars',        icon: '⭐', bg: 'linear-gradient(135deg,#003366,#001a3a)', top: false },
];

function matchGame(catName, key) {
  const n = catName.toLowerCase();
  if (key === 'ff_cis') return (n.includes('free fire') || n.includes('garena')) && (n.includes('cis') || n.includes('снг') || n.includes('rus')) && !n.includes('indo');
  if (key === 'ff_id') return (n.includes('free fire') || n.includes('garena')) && n.includes('indo');
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


async def main():
    await init_db()
    app = web.Application()
    app.add_routes([web.get("/", h_health), web.get("/webapp", h_webapp),
                    web.get("/webapp/catalog.json", h_catalog)])
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
            BotCommand(command="ff",      description="🎮 Инфо об игроке FF по UID"),
            BotCommand(command="look",    description="👗 Аутфит персонажа FF"),
            BotCommand(command="guild",   description="🏠 Информация о гильдии FF"),
            BotCommand(command="age",     description="📅 Возраст аккаунта FF"),
            BotCommand(command="bio",     description="📝 Профиль и биография FF"),
            BotCommand(command="help",    description="📖 Помощь"),
        ])
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
