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
    # --- Арабский язык ---
    "ar": {
        "welcome": (
            "🔥❤️ مرحباً بك في DONATEX!\n\n"
            "💎 الماس و UC — بمعرّف اللاعب، الدفع بالسوموني.\n"
            "⚡ يتم تنفيذ الطلب تلقائياً بعد الدفع.\n"
            "🎁 مكافأة {bonus}% على أول عملية شراء!\n\n"
            "✅ أُنجز: {orders}+ طلب | 👥 العملاء: {users}+\n\n"
            "💰 رصيدك: <b>{bal}</b>\n\nاختر لعبة 👇"
        ),
        "all_games": "🎮 كل الألعاب", "stars": "⭐ Stars / Premium", "balance": "💰 الرصيد",
        "orders": "📦 طلباتي", "support": "🛟 الدعم", "promo": "🎟 رمز ترويجي",
        "ref": "👥 دعوة", "lang": "🌐 اللغة", "shop": "🛒 المتجر", "menu": "🏠 القائمة",
        "topup": "➕ شحن", "popular": "🔥 الأكثر شعبية", "news": "📢 الأخبار",
        "reviews_btn": "⭐ التقييمات",
        "blocked": "🚫 أنت محظور", "nf": "غير موجود", "unavail": "غير متاح",
        "pick_pkg": "اختر الباقة 👇",
        "enter_id": "📦 {title}\n💰 {price}\n\n🆔 أدخل معرّف اللاعب:",
        "bad_id": "❌ معرّف غير صحيح (6-15 رقم). حاول مجدداً:",
        "confirm_id": "🔎 معرّفك: <code>{pid}</code>\n\nهل هذا صحيح؟",
        "id_ok": "✅ صحيح", "id_edit": "✏️ تعديل",
        "confirm_q": "📦 {title}\n👤 {target}\n💰 {price}{promo}\n\nتأكيد؟",
        "ok": "✅ تأكيد", "cancel": "❌ إلغاء", "cancelled": "❌ تم الإلغاء.",
        "low": "❌ رصيد غير كافٍ! مطلوب: {price}، لديك: {bal}",
        "busy": "⏳ طلبك السابق لا يزال قيد المعالجة.",
        "expired": "⌛ انتهت صلاحية الطلب. ابدأ من جديد.",
        "order_ok": "✅ تم قبول الطلب #{oid}!\n💰 تم خصم {price}\n💰 الرصيد: {bal}\n⏳ سيكون جاهزاً قريباً!",
        "order_err": "❌ خطأ: {err}\n💰 تم إرجاع أموالك.",
        "order_wait": "⚠️ لا يوجد رد من الخدمة. سيتحقق الأدمن من طلبك، الأموال محفوظة.",
        "enter_uname": "💬 أدخل @username المستلم:",
        "bad_uname": "❌ اسم مستخدم غير صحيح. مثال: @username",
        "choose_pay": "💳 اختر طريقة الدفع:", "no_pay": "لم يتم تكوين بيانات الدفع",
        "choose_amt": "{title} — المبلغ:", "other": "✏️ أخرى",
        "enter_amt": "✏️ أدخل المبلغ ({min}–{max}):",
        "bad_amt": "❌ مبلغ غير صحيح. المسموح: {min}–{max}",
        "topup_instr": "💳 {title}:\n1️⃣ حوّل إلى: <code>{number}</code>{holder}\n💵 المبلغ: {amount}\n\n2️⃣ أرسل الإيصال 📸",
        "receipt_ok": "✅ تم استلام الإيصال، في انتظار التأكيد.",
        "topup_done": "💰 تم شحن الرصيد! ➕ {amount}\n💰 الآن: {bal}",
        "topup_no": "❌ لم يتم تأكيد الإيصال.",
        "bal_text": "💰 رصيدك: <b>{bal}</b>",
        "tx_title": "\n\n📋 آخر العمليات:",
        "orders_title": "📦 آخر الطلبات:", "no_orders": "😕 لا توجد طلبات.",
        "support_text": "🛟 الدعم: {contact}",
        "ref_text": "👥 ادعُ أصدقاءك واحصل على {pct}% من أول شحن لهم!\n\n🔗 {link}\n\nمدعوون: {n}\nمكتسب: {earned}",
        "ref_bonus": "🎁 مكافأة الإحالة: +{amount}",
        "promo_ask": "🎟 أدخل الرمز الترويجي:",
        "promo_ok": "✅ تم تفعيل الرمز: -{pct}% على طلبك القادم.",
        "promo_bad": "❌ رمز غير صحيح أو مستخدم.",
        "promo_line": "\n🎟 مع الرمز: -{pct}%",
        "first_bonus_line": "\n🎁 مكافأة الشراء الأول: -{pct}%",
        "lang_choose": "🌐 اختر اللغة:", "lang_set": "✅ تم تغيير اللغة.",
        "stars_title": "⭐ Telegram Stars و Premium\n\nاختر الكمية:",
        "games_title": "🎮 كل الألعاب:", "months": "شهر", "shop_hint": "🛒 افتح المتجر:",
        "help": "📖 /start — القائمة · /balance — الرصيد · /admin — لوحة الأدمن",
        "next": "➡️", "prev": "⬅️",
        "popular_title": "🔥 الأكثر شعبية:",
        "no_popular": "😕 لا توجد بيانات.",
        "review_ask": "⭐ تم تنفيذ الطلب! يرجى التقييم:",
        "review_text_ask": "✍️ اكتب تقييمك (أو /skip للتخطي):",
        "review_thanks": "🙏 شكراً على تقييمك!",
        "review_skip": "/skip",
    },
    # --- Китайский язык ---
    "zh": {
        "welcome": (
            "🔥❤️ 欢迎来到 DONATEX!\n\n"
            "💎  通过玩家ID购买钻石和UC，使用索莫尼支付。\n"
            "⚡ 付款后自动处理订单。\n"
            "🎁 首次购买享受{bonus}%优惠!\n\n"
            "✅ 已完成: {orders}+ 订单 | 👥 客户: {users}+\n\n"
            "💰 您的余额: <b>{bal}</b>\n\n请选择游戏 👇"
        ),
        "all_games": "🎮 所有游戏", "stars": "⭐ Stars / Premium", "balance": "💰 余额",
        "orders": "📦 我的订单", "support": "🛟 客服", "promo": "🎟 优惠码",
        "ref": "👥 邀请", "lang": "🌐 语言", "shop": "🛒 商店", "menu": "🏠 菜单",
        "topup": "➕ 充值", "popular": "🔥 热门", "news": "📢 新闻",
        "reviews_btn": "⭐ 评价",
        "blocked": "🚫 您已被封禁", "nf": "未找到", "unavail": "不可用",
        "pick_pkg": "请选择套餐 👇",
        "enter_id": "📦 {title}\n💰 {price}\n\n🆔 请输入玩家ID:",
        "bad_id": "❌ ID无效 (6-15位数字)。请重试:",
        "confirm_id": "🔎 您的ID: <code>{pid}</code>\n\n确认正确吗？",
        "id_ok": "✅ 正确", "id_edit": "✏️ 修改",
        "confirm_q": "📦 {title}\n👤 {target}\n💰 {price}{promo}\n\n确认？",
        "ok": "✅ 确认", "cancel": "❌ 取消", "cancelled": "❌ 已取消。",
        "low": "❌ 余额不足！需要: {price}，您有: {bal}",
        "busy": "⏳ 上一个订单还在处理中。",
        "expired": "⌛ 请求已过期。请重新开始。",
        "order_ok": "✅ 订单 #{oid} 已接受!\n💰 扣除 {price}\n💰 余额: {bal}\n⏳ 即将完成!",
        "order_err": "❌ 错误: {err}\n💰 资金已退回。",
        "order_wait": "⚠️ 未收到服务响应。管理员将检查您的订单，资金已保留。",
        "enter_uname": "💬 请输入接收者的 @username:",
        "bad_uname": "❌ 用户名无效。示例: @username",
        "choose_pay": "💳 选择支付方式:", "no_pay": "支付信息未配置",
        "choose_amt": "{title} — 金额:", "other": "✏️ 其他",
        "enter_amt": "✏️ 请输入金额 ({min}–{max}):",
        "bad_amt": "❌ 金额无效。允许: {min}–{max}",
        "topup_instr": "💳 {title}:\n1️⃣ 转账至: <code>{number}</code>{holder}\n💵 金额: {amount}\n\n2️⃣ 发送收据 📸",
        "receipt_ok": "✅ 收据已收到，等待确认。",
        "topup_done": "💰 余额已充值! ➕ {amount}\n💰 当前: {bal}",
        "topup_no": "❌ 收据未获批准。",
        "bal_text": "💰 您的余额: <b>{bal}</b>",
        "tx_title": "\n\n📋 最近交易:",
        "orders_title": "📦 最近订单:", "no_orders": "😕 暂无订单。",
        "support_text": "🛟 客服: {contact}",
        "ref_text": "👥 邀请好友，获得他们首次充值的{pct}%!\n\n🔗 {link}\n\n已邀请: {n}\n已赚取: {earned}",
        "ref_bonus": "🎁 推荐奖励: +{amount}",
        "promo_ask": "🎟 请输入优惠码:",
        "promo_ok": "✅ 优惠码已激活: 下次订单享-{pct}%。",
        "promo_bad": "❌ 优惠码无效或已使用。",
        "promo_line": "\n🎟 使用优惠码: -{pct}%",
        "first_bonus_line": "\n🎁 首次购买优惠: -{pct}%",
        "lang_choose": "🌐 选择语言:", "lang_set": "✅ 语言已更改。",
        "stars_title": "⭐ Telegram Stars 和 Premium\n\n请选择数量:",
        "games_title": "🎮 所有游戏:", "months": "月", "shop_hint": "🛒 打开商店:",
        "help": "📖 /start — 菜单 · /balance — 余额 · /admin — 管理面板",
        "next": "➡️", "prev": "⬅️",
        "popular_title": "🔥 热门商品:",
        "no_popular": "😕 暂无数据。",
        "review_ask": "⭐ 订单已完成！请评分:",
        "review_text_ask": "✍️ 写下您的评价 (或 /skip 跳过):",
        "review_thanks": "🙏 感谢您的评价！",
        "review_skip": "/skip",
    },
    # --- Хинди ---
    "hi": {
        "welcome": (
            "🔥❤️ DONATEX में आपका स्वागत है!\n\n"
            "💎 प्लेयर ID से डायमंड और UC खरीदें, सोमोनी में भुगतान।\n"
            "⚡ भुगतान के बाद ऑर्डर स्वचालित रूप से पूरा होता है।\n"
            "🎁 पहली खरीद पर {bonus}% बोनस!\n\n"
            "✅ पूर्ण: {orders}+ ऑर्डर | 👥 ग्राहक: {users}+\n\n"
            "💰 आपका बैलेंस: <b>{bal}</b>\n\nगेम चुनें 👇"
        ),
        "all_games": "🎮 सभी गेम", "stars": "⭐ Stars / Premium", "balance": "💰 बैलेंस",
        "orders": "📦 मेरे ऑर्डर", "support": "🛟 सहायता", "promo": "🎟 प्रोमो कोड",
        "ref": "👥 आमंत्रित करें", "lang": "🌐 भाषा", "shop": "🛒 दुकान", "menu": "🏠 मेनू",
        "topup": "➕ टॉप अप", "popular": "🔥 लोकप्रिय", "news": "📢 समाचार",
        "reviews_btn": "⭐ समीक्षाएं",
        "blocked": "🚫 आप ब्लॉक हैं", "nf": "नहीं मिला", "unavail": "उपलब्ध नहीं",
        "pick_pkg": "पैकेज चुनें 👇",
        "enter_id": "📦 {title}\n💰 {price}\n\n🆔 प्लेयर ID दर्ज करें:",
        "bad_id": "❌ अमान्य ID (6-15 अंक)। दोबारा कोशिश करें:",
        "confirm_id": "🔎 आपका ID: <code>{pid}</code>\n\nक्या यह सही है?",
        "id_ok": "✅ सही है", "id_edit": "✏️ बदलें",
        "confirm_q": "📦 {title}\n👤 {target}\n💰 {price}{promo}\n\nपुष्टि करें?",
        "ok": "✅ पुष्टि करें", "cancel": "❌ रद्द करें", "cancelled": "❌ रद्द किया गया।",
        "low": "❌ पर्याप्त बैलेंस नहीं! चाहिए: {price}, आपके पास: {bal}",
        "busy": "⏳ पिछला ऑर्डर अभी भी प्रोसेस हो रहा है।",
        "expired": "⌛ अनुरोध समाप्त हो गया। फिर से शुरू करें।",
        "order_ok": "✅ ऑर्डर #{oid} स्वीकार किया गया!\n💰 कटौती: {price}\n💰 बैलेंस: {bal}\n⏳ जल्द तैयार होगा!",
        "order_err": "❌ त्रुटि: {err}\n💰 पैसे वापस कर दिए गए।",
        "order_wait": "⚠️ सेवा से कोई जवाब नहीं मिला। एडमिन आपका ऑर्डर जांचेगा, पैसे सुरक्षित हैं।",
        "enter_uname": "💬 प्राप्तकर्ता का @username दर्ज करें:",
        "bad_uname": "❌ अमान्य username। उदाहरण: @username",
        "choose_pay": "💳 भुगतान विधि चुनें:", "no_pay": "भुगतान विवरण कॉन्फ़िगर नहीं है",
        "choose_amt": "{title} — राशि:", "other": "✏️ अन्य",
        "enter_amt": "✏️ राशि दर्ज करें ({min}–{max}):",
        "bad_amt": "❌ अमान्य राशि। अनुमत: {min}–{max}",
        "topup_instr": "💳 {title}:\n1️⃣ ट्रांसफर करें: <code>{number}</code>{holder}\n💵 राशि: {amount}\n\n2️⃣ रसीद भेजें 📸",
        "receipt_ok": "✅ रसीद मिल गई, पुष्टि की प्रतीक्षा करें।",
        "topup_done": "💰 बैलेंस टॉप अप हो गया! ➕ {amount}\n💰 अभी: {bal}",
        "topup_no": "❌ रसीद स्वीकृत नहीं हुई।",
        "bal_text": "💰 आपका बैलेंस: <b>{bal}</b>",
        "tx_title": "\n\n📋 हाल के लेनदेन:",
        "orders_title": "📦 हाल के ऑर्डर:", "no_orders": "😕 कोई ऑर्डर नहीं।",
        "support_text": "🛟 सहायता: {contact}",
        "ref_text": "👥 दोस्तों को आमंत्रित करें और उनके पहले टॉप अप का {pct}% पाएं!\n\n🔗 {link}\n\nआमंत्रित: {n}\nकमाया: {earned}",
        "ref_bonus": "🎁 रेफरल बोनस: +{amount}",
        "promo_ask": "🎟 प्रोमो कोड दर्ज करें:",
        "promo_ok": "✅ प्रोमो सक्रिय: अगले ऑर्डर पर -{pct}%।",
        "promo_bad": "❌ अमान्य या पहले से उपयोग किया गया प्रोमो कोड।",
        "promo_line": "\n🎟 प्रोमो के साथ: -{pct}%",
        "first_bonus_line": "\n🎁 पहली खरीद बोनस: -{pct}%",
        "lang_choose": "🌐 भाषा चुनें:", "lang_set": "✅ भाषा बदल दी गई।",
        "stars_title": "⭐ Telegram Stars और Premium\n\nमात्रा चुनें:",
        "games_title": "🎮 सभी गेम:", "months": "महीने", "shop_hint": "🛒 दुकान खोलें:",
        "help": "📖 /start — मेनू · /balance — बैलेंस · /admin — एडमिन पैनल",
        "next": "➡️", "prev": "⬅️",
        "popular_title": "🔥 लोकप्रिय आइटम:",
        "no_popular": "😕 कोई डेटा नहीं।",
        "review_ask": "⭐ ऑर्डर पूरा हो गया! कृपया रेटिंग दें:",
        "review_text_ask": "✍️ अपनी समीक्षा लिखें (या /skip करें):",
        "review_thanks": "🙏 आपकी समीक्षा के लिए धन्यवाद!",
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
            data = await get({"kind": "topup", "limit": 500})
            stars = await get({"kind": "telegram_stars", "limit": 5})
            prem = await get({"kind": "telegram_premium", "limit": 10})
        new_cat, new_prod = {}, {}
        for p in data.get("items", []):
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
        "ar": NEWS_CHANNEL_RU or NEWS_CHANNEL_EN,
        "zh": NEWS_CHANNEL_EN,
        "hi": NEWS_CHANNEL_EN,
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
        [btn("💎 FF СНГ", "game:ff_cis"), btn("🇮🇩 FF Индонезия", "game:ff_id")],
        [btn("🎯 PUBG Mobile — UC", "game:pubg")],
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
        # Строка 1: таджикский, русский, английский
        [btn("🇹🇯 Тоҷикӣ", "setlang:tg"), btn("🇷🇺 Русский", "setlang:ru"), btn("🇬🇧 English", "setlang:en")],
        # Строка 2: арабский, китайский, хинди
        [btn("🇸🇦 العربية", "setlang:ar"), btn("🇨🇳 中文", "setlang:zh"), btn("🇮🇳 हिन्दी", "setlang:hi")],
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
            # Антифрод — сначала показываем ID для подтверждения (пункт 8)
            tok = new_pending(uid=uid, pid=txt, product=p)
            user_state.pop(uid, None)
            await m.answer(
                t(uid, "confirm_id", pid=txt),
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
    await ask_confirm(c.message, uid, ptitle(p), pid, p["price_tjs"],
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
    --bg: #0d1117;
    --bg2: #161b22;
    --bg3: #1f2937;
    --accent: #7b68ee;
    --accent2: #9b8aff;
    --text: #e6edf3;
    --text2: #8b949e;
    --card-bg: #1a1f2e;
    --card-border: rgba(123,104,238,0.2);
    --shadow: 0 4px 20px rgba(123,104,238,0.15);
    --radius: 14px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, 'SF Pro Display', Segoe UI, Roboto, sans-serif;
    min-height: 100vh;
    padding-bottom: 70px;
  }

  /* ===== Анимированный заголовок DONATEX ===== */
  .header {
    background: linear-gradient(135deg, #0d1117, #1a1030);
    padding: 20px 16px 16px;
    text-align: center;
    position: sticky;
    top: 0;
    z-index: 100;
    border-bottom: 1px solid var(--card-border);
    backdrop-filter: blur(10px);
  }
  .logo {
    font-size: 28px;
    font-weight: 900;
    letter-spacing: 3px;
    background: linear-gradient(90deg, #7b68ee, #ff6b9d, #7b68ee, #00d4ff);
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
    font-size: 11px;
    color: var(--text2);
    letter-spacing: 2px;
    margin-top: 2px;
    text-transform: uppercase;
  }

  /* ===== Поиск с иконкой ===== */
  .search-wrap {
    padding: 12px 16px 8px;
    position: sticky;
    top: 80px;
    z-index: 99;
    background: var(--bg);
  }
  .search-box {
    display: flex;
    align-items: center;
    background: var(--bg2);
    border: 1px solid var(--card-border);
    border-radius: 12px;
    padding: 10px 14px;
    gap: 10px;
    transition: border-color 0.2s;
  }
  .search-box:focus-within {
    border-color: var(--accent);
  }
  .search-icon {
    font-size: 16px;
    flex-shrink: 0;
    color: var(--text2);
  }
  .search-box input {
    flex: 1;
    background: none;
    border: none;
    outline: none;
    color: var(--text);
    font-size: 15px;
  }
  .search-box input::placeholder { color: var(--text2); }

  /* ===== Лоадер ===== */
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

  /* ===== Контент ===== */
  #app { padding: 8px 16px; }

  /* ===== Заголовок категории ===== */
  .cat-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 20px 0 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--card-border);
  }
  .cat-header h3 {
    font-size: 17px;
    font-weight: 700;
    color: var(--text);
    flex: 1;
  }
  .cat-badge {
    background: rgba(123,104,238,0.15);
    color: var(--accent2);
    font-size: 11px;
    padding: 3px 8px;
    border-radius: 20px;
    font-weight: 600;
  }

  /* ===== Сетка товаров ===== */
  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }

  /* ===== Карточка товара ===== */
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
    background: linear-gradient(135deg, rgba(123,104,238,0.08), transparent);
    opacity: 0;
    transition: opacity 0.18s;
  }
  .card:active {
    transform: scale(0.96);
    border-color: var(--accent);
    box-shadow: var(--shadow);
  }
  .card:active::before { opacity: 1; }
  .card-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text);
    line-height: 1.3;
  }
  .card-price {
    font-size: 15px;
    font-weight: 800;
    color: var(--accent2);
  }
  .card-price small {
    font-size: 11px;
    font-weight: 500;
    color: var(--text2);
  }

  /* ===== Нижняя навигация ===== */
  .nav {
    position: fixed;
    bottom: 0; left: 0; right: 0;
    background: var(--bg2);
    border-top: 1px solid var(--card-border);
    display: flex;
    padding: 8px 0 env(safe-area-inset-bottom, 8px);
    z-index: 200;
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

  /* ===== Пусто ===== */
  .empty {
    text-align: center;
    padding: 40px 20px;
    color: var(--text2);
  }
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

<div id="app">
  <div id="loader">
    <div class="spinner"></div>
    <div class="loader-text">Загрузка каталога...</div>
  </div>
</div>

<div class="nav">
  <div class="nav-btn active" onclick="scrollToTop()">
    <span class="nav-icon">🏠</span>
    <span>Главная</span>
  </div>
  <div class="nav-btn" onclick="focusSearch()">
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

let data = [];

fetch('/webapp/catalog.json')
  .then(r => r.json())
  .then(d => {
    data = d;
    document.getElementById('loader').style.display = 'none';
    render('');
  })
  .catch(() => {
    document.getElementById('loader').innerHTML =
      '<div class="empty"><div class="empty-icon">😕</div><div>Ошибка загрузки</div></div>';
  });

document.getElementById('q').addEventListener('input', e => render(e.target.value.toLowerCase()));

function render(f) {
  const app = document.getElementById('app');
  app.innerHTML = '';
  let found = 0;

  data.forEach(cat => {
    const ps = cat.products.filter(p =>
      !f || p.title.toLowerCase().includes(f) || cat.name.toLowerCase().includes(f)
    );
    if (!ps.length) return;
    found += ps.length;

    // Заголовок категории
    const header = document.createElement('div');
    header.className = 'cat-header';
    header.innerHTML = `<h3>${cat.name}</h3><span class="cat-badge">${ps.length}</span>`;
    app.appendChild(header);

    // Сетка карточек
    const grid = document.createElement('div');
    grid.className = 'grid';

    ps.forEach(p => {
      const card = document.createElement('div');
      card.className = 'card';
      card.innerHTML = `
        <div class="card-title">${p.title}</div>
        <div class="card-price">${p.price} <small>с.</small></div>
      `;
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

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' });
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  event.currentTarget.classList.add('active');
}

function focusSearch() {
  document.getElementById('q').focus();
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  event.currentTarget.classList.add('active');
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
