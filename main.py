import asyncio
import json
import os
import time
from datetime import datetime

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (Message, CallbackQuery,
                           InlineKeyboardMarkup, InlineKeyboardButton)

# ===== Настройки (Render → Environment) =====
BOT_TOKEN = os.environ["BOT_TOKEN"]
DONATIX_KEY = os.environ.get("DONATIX_KEY", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
PORT = int(os.environ.get("PORT", 10000))
EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")
MARGIN = float(os.environ.get("MARGIN", "0.15"))  # наценка 15% (меняй как хочешь)

API = "https://donatix.tj/api/v1"
HEADERS = {"X-API-Key": DONATIX_KEY}

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ===== Живой курс USD → TJS =====
usd_tjs_rate = 10.9  # курс по умолчанию
rate_updated_at = 0.0

async def update_rate():
    global usd_tjs_rate, rate_updated_at
    if time.time() - rate_updated_at < 3600:  # обновляем раз в час
        return
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://open.er-api.com/v6/latest/USD",
                             timeout=aiohttp.ClientTimeout(total=10)) as r:
                data = await r.json()
                if data.get("result") == "success":
                    usd_tjs_rate = data["rates"]["TJS"]
                    rate_updated_at = time.time()
                    print(f"Курс обновлён: 1 USD = {usd_tjs_rate:.2f} TJS")
    except Exception as e:
        print("Ошибка обновления курса:", e)

def usd_to_tjs(usd: float) -> float:
    return round(usd * usd_tjs_rate * (1 + MARGIN), 2)

# ===== Каталог =====
catalog = {}  # {category_id: {name, products: [...]}}
catalog_loaded_at = 0.0

async def load_catalog(force=False):
    global catalog, catalog_loaded_at
    if not force and time.time() - catalog_loaded_at < 600 and catalog:
        return
    if not DONATIX_KEY:
        return
    await update_rate()
    try:
        async with aiohttp.ClientSession() as s:
            params = {"kind": "topup", "limit": 500}
            async with s.get(f"{API}/products", params=params, headers=HEADERS,
                             timeout=aiohttp.ClientTimeout(total=30)) as r:
                data = await r.json()
            items = data.get("items", [])
            catalog.clear()
            for p in items:
                cid = p.get("category_id")
                if cid not in catalog:
                    catalog[cid] = {"name": p.get("category_name", cid), "products": []}
                p["price_tjs"] = usd_to_tjs(float(p.get("price_usd", 0)))
                catalog[cid]["products"].append(p)
            catalog_loaded_at = time.time()
            print(f"Каталог загружен: {len(catalog)} игр")
    except Exception as e:
        print("Ошибка загрузки каталога:", e)

# ===== Состояния пользователей =====
user_state = {}  # {user_id: {"stage": "...", "data": {...}}}

def kb_buttons(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ===== Команды =====
@dp.message(Command("start"))
async def start(m: Message):
    await load_catalog()
    balance = await get_balance()
    text = (f"🔥❤️ Хуш омадед ба магазин!\n\n"
            f"💎 Алмосҳо ва UC — бо ID бозингар, пардохт бо сомонӣ.\n"
            f"⚡ Фармоиш худкор пас аз пардохт.\n\n"
            f"💰 Баланс: {balance} с.\n\n"
            f"Бозиро интихоб кунед 👇")
    buttons = [
        [InlineKeyboardButton(text="💎 FF СНГ — алмосҳо", callback_data="game:ff_cis"),
         InlineKeyboardButton(text="🇮🇩 FF Индонезия", callback_data="game:ff_id")],
        [InlineKeyboardButton(text="🎯 PUBG Mobile — UC", callback_data="game:pubg")],
        [InlineKeyboardButton(text="🎮 Ҳамаи бозиҳо", callback_data="all_games"),
         InlineKeyboardButton(text="⭐ Stars / Premium", callback_data="tg_stars")],
        [InlineKeyboardButton(text="💰 Баланс", callback_data="balance"),
         InlineKeyboardButton(text="📦 Фармоишҳои ман", callback_data="my_orders")],
        [InlineKeyboardButton(text="🛟 Дастгирӣ", callback_data="support")],
    ]
    await m.answer(text, reply_markup=kb_buttons(buttons))

@dp.message(Command("buy"))
async def buy(m: Message):
    await start(m)

@dp.message(Command("balance"))
async def balance_cmd(m: Message):
    if m.from_user.id != ADMIN_ID:
        await m.answer("Танҳо админ метавонад баланси мағозаро бинад.")
        return
    balance = await get_balance()
    text = (f"💰 Баланси мағоза: {balance} с.\n\n"
            f"Пур кунед — ва дар як клик харед.")
    buttons = [
        [InlineKeyboardButton(text="+ Пур кардан", url="https://donatix.tj/panel/payments")],
        [InlineKeyboardButton(text="📜 Таърих", callback_data="order_history")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="menu")],
    ]
    await m.answer(text, reply_markup=kb_buttons(buttons))

@dp.message(Command("help"))
async def help_cmd(m: Message):
    text = ("📖 Роҳнамо:\n\n"
            "/start — Менюи асосӣ\n"
            "/buy — Интихоби бозӣ\n"
            "/balance — Баланси мағоза (админ)\n"
            "/help — Роҳнамо\n\n"
            "Барои харидан: /buy → бозиро интихоб кунед → пакетро интихоб кунед → ID бозингарро ворид кунед → тасдиқ кунед.")
    await m.answer(text)

# ===== Callback-ҳо =====
@dp.callback_query(F.data == "menu")
async def menu_cb(c: CallbackQuery):
    await c.message.delete()
    await start(c.message)

@dp.callback_query(F.data == "all_games")
async def all_games(c: CallbackQuery):
    await load_catalog()
    buttons = []
    row = []
    for cid, data in catalog.items():
        btn = InlineKeyboardButton(text=data["name"], callback_data=f"cat:{cid}")
        row.append(btn)
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="‹ Бозгашт", callback_data="menu")])
    await c.message.edit_text("🎮 Ҳамаи бозиҳо:\n\nБозиро интихоб кунед 👇",
                              reply_markup=kb_buttons(buttons))
    await c.answer()

@dp.callback_query(F.data.startswith("game:"))
async def pick_game(c: CallbackQuery):
    game = c.data.split(":")[1]
    game_map = {
        "ff_cis": "free_fire_cis",
        "ff_id": "free_fire_indonesia",
        "pubg": "pubg_mobile",
    }
    cid = game_map.get(game)
    if cid and cid in catalog:
        await show_category(c, cid)
    else:
        await c.answer("Бозӣ ёфт нашуд", show_alert=True)

@dp.callback_query(F.data.startswith("cat:"))
async def pick_category(c: CallbackQuery):
    cid = c.data.split(":")[1]
    await show_category(c, cid)

async def show_category(c: CallbackQuery, cid: str):
    await load_catalog()
    if cid not in catalog:
        await c.answer("Категория ёфт нашуд", show_alert=True)
        return
    cat = catalog[cid]
    products = cat["products"]
    # Группируем по типу
    groups = {}
    for p in products:
        name = p.get("name", "")
        if "diamond" in name.lower() or "алмаз" in name.lower():
            group = "💎 Алмосҳо"
        elif "weekly" in name.lower() or "monthly" in name.lower() or "ваучер" in name.lower():
            group = "🎫 Ваучерҳо ва пропускҳо"
        elif "level" in name.lower() or "прокач" in name.lower():
            group = "🚀 Прокачка"
        else:
            group = "🎁 Дигар"
        if group not in groups:
            groups[group] = []
        groups[group].append(p)
    
    text = f"{cat['name']}\n━━━━━━━━━━━━━━━━━━━━\n\nПакетро интихоб кунед — баъд ID бозингарро мепурсам 👇\n\n"
    buttons = []
    for group_name, prods in groups.items():
        text += f"━━ {group_name} ━━\n\n"
        row = []
        for p in prods[:10]:  # максимум 10 в группе
            title = p.get("title") or p.get("name", "")
            price = p["price_tjs"]
            btn_text = f"{title} — {price} с."
            if len(btn_text) > 30:
                btn_text = btn_text[:27] + "..."
            row.append(InlineKeyboardButton(text=btn_text, callback_data=f"pkg:{p['product_id']}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        text += "\n"
    
    buttons.append([InlineKeyboardButton(text="‹ Бозгашт", callback_data="menu"),
                    InlineKeyboardButton(text="🏠 Меню", callback_data="menu")])
    await c.message.edit_text(text, reply_markup=kb_buttons(buttons))
    await c.answer()

@dp.callback_query(F.data.startswith("pkg:"))
async def pick_package(c: CallbackQuery):
    pid = c.data.split(":")[1]
    product = None
    for cat_data in catalog.values():
        for p in cat_data["products"]:
            if p["product_id"] == pid:
                product = p
                break
    if not product:
        await c.answer("Пакет ёфт нашуд", show_alert=True)
        return
    user_state[c.from_user.id] = {"stage": "waiting_id", "product": product}
    title = product.get("title") or product.get("name", "")
    price = product["price_tjs"]
    text = f"📦 {title}\n💰 Нарх: {price} с.\n\n🆔 ID бозингарро ворид кунед (танҳо рақамҳо):"
    await c.message.answer(text)
    await c.answer()

@dp.message(F.text.regexp(r"^\d{6,15}$"))
async def got_player_id(m: Message):
    if m.from_user.id not in user_state or user_state[m.from_user.id].get("stage") != "waiting_id":
        return
    state = user_state[m.from_user.id]
    product = state["product"]
    player_id = m.text.strip()
    state["player_id"] = player_id
    state["stage"] = "confirm"
    
    # Проверяем аккаунт
    valid = True
    player_name = None
    if DONATIX_KEY:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{API}/accounts/check",
                                  json={"product_id": product["product_id"],
                                        "fields": {"player_id": player_id}},
                                  headers=HEADERS,
                                  timeout=aiohttp.ClientTimeout(total=15)) as r:
                    data = await r.json()
                if data.get("ok"):
                    valid = data.get("valid", False)
                    player_name = data.get("player_name")
        except Exception:
            pass
    
    if not valid:
        del user_state[m.from_user.id]
        await m.answer("❌ Ин ID ёфт нашуд. Лутфан дуруст ворид кунед.")
        return
    
    title = product.get("title") or product.get("name", "")
    price = product["price_tjs"]
    name_text = f"\n👤 Ном: {player_name}" if player_name else ""
    text = (f"✅ Фармоишро тасдиқ кунед:\n\n"
            f"📦 {title}{name_text}\n"
            f"🆔 ID: {player_id}\n"
            f"💰 Нарх: {price} с.\n\n"
            f"Тасдиқ мекунед?")
    buttons = [
        [InlineKeyboardButton(text="✅ Харидан", callback_data=f"confirm:{product['product_id']}:{player_id}"),
         InlineKeyboardButton(text="❌ Бекор кардан", callback_data="cancel")],
    ]
    await m.answer(text, reply_markup=kb_buttons(buttons))

@dp.callback_query(F.data == "cancel")
async def cancel_order(c: CallbackQuery):
    if c.from_user.id in user_state:
        del user_state[c.from_user.id]
    await c.message.edit_text("❌ Фармоиш бекор карда шуд.\n\n/buy — аз нав оғоз кунед.")
    await c.answer()

@dp.callback_query(F.data.startswith("confirm:"))
async def confirm_order(c: CallbackQuery):
    parts = c.data.split(":")
    pid, player_id = parts[1], parts[2]
    product = None
    for cat_data in catalog.values():
        for p in cat_data["products"]:
            if p["product_id"] == pid:
                product = p
                break
    if not product:
        await c.answer("Хатоӣ", show_alert=True)
        return
    
    if not DONATIX_KEY:
        await c.message.edit_text("⚠️ Donatix пайваст нест. Лутфан DONATIX_KEY-ро илова кунед.")
        return
    
    await c.answer("⏳ Фармоиш сохта мешавад...")
    
    try:
        async with aiohttp.ClientSession() as s:
            import uuid
            headers = {**HEADERS, "Idempotency-Key": str(uuid.uuid4())}
            async with s.post(f"{API}/orders",
                              json={"product_id": pid,
                                    "fields": {"player_id": player_id}},
                              headers=headers,
                              timeout=aiohttp.ClientTimeout(total=30)) as r:
                data = await r.json()
        
        if data.get("ok"):
            order = data["order"]
            oid = order.get("order_id", "?")
            if c.from_user.id in user_state:
                del user_state[c.from_user.id]
            await c.message.edit_text(f"✅ Фармоиш #{oid} қабул шуд!\n\n"
                                      f"📦 {product.get('title') or product.get('name')}\n"
                                      f"🆔 ID: {player_id}\n\n"
                                      f"Алмосҳо ба ID фиристода мешаванд.")
            if ADMIN_ID:
                await bot.send_message(ADMIN_ID,
                    f"💰 Фармоиши нав: #{oid}\n"
                    f"📦 {product.get('title')}\n"
                    f"🆔 {player_id}\n"
                    f"💰 {product['price_tjs']} с.")
        else:
            error = data.get("error", "Номаълум")
            await c.message.edit_text(f"❌ Хатоӣ: {error}")
    except Exception as e:
        await c.message.edit_text(f"⚠️ Хатоӣ: {e}")

@dp.callback_query(F.data == "balance")
async def balance_page(c: CallbackQuery):
    balance = await get_balance()
    text = f"💰 Баланси шумо: {balance} с.\n\nПур кунед — ва дар як клик харед."
    buttons = [
        [InlineKeyboardButton(text="+ Пур кардан", url="https://donatix.tj/panel/payments")],
        [InlineKeyboardButton(text="📜 Таърих", callback_data="order_history")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="menu")],
    ]
    await c.message.edit_text(text, reply_markup=kb_buttons(buttons))
    await c.answer()

@dp.callback_query(F.data == "my_orders")
async def my_orders(c: CallbackQuery):
    if not DONATIX_KEY:
        await c.answer("Donatix пайваст нест", show_alert=True)
        return
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{API}/orders", params={"limit": 10}, headers=HEADERS,
                             timeout=aiohttp.ClientTimeout(total=15)) as r:
                data = await r.json()
        orders = data.get("items", [])
        if not orders:
            text = "📦 Фармоишҳои шумо:\n\nҲоло фармоиш нест."
        else:
            text = "📦 Фармоишҳои охирин:\n\n"
            for o in orders[:10]:
                oid = o.get("order_id", "?")
                status = o.get("status", "?")
                name = o.get("product_name", "?")
                icon = "✅" if status == "completed" else "❌" if status == "failed" else "⏳"
                text += f"{icon} {oid} · {name}\n"
        buttons = [[InlineKeyboardButton(text="🏠 Меню", callback_data="menu")]]
        await c.message.edit_text(text, reply_markup=kb_buttons(buttons))
    except Exception as e:
        await c.message.edit_text(f"⚠️ Хатоӣ: {e}")
    await c.answer()

@dp.callback_query(F.data == "order_history")
async def order_history(c: CallbackQuery):
    await my_orders(c)

@dp.callback_query(F.data == "support")
async def support(c: CallbackQuery):
    text = ("🛟 Дастгирӣ\n\n"
            "Нависед, чӣ рух дод — метавонед скриншот, чек ё овозӣ фиристод. "
            "Ҷавоб медиҳем ва огоҳинома мефиристем.")
    buttons = [
        [InlineKeyboardButton(text="💬 Навиштан ба дастгирӣ", url="https://t.me/donatix_support")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="menu")],
    ]
    await c.message.edit_text(text, reply_markup=kb_buttons(buttons))
    await c.answer()

@dp.callback_query(F.data == "tg_stars")
async def tg_stars(c: CallbackQuery):
    text = ("⭐ Telegram Stars / Premium\n\n"
            "Telegram Stars — аз 7.8 с.\n"
            "Telegram Premium — 3 моҳ: 124.72 с.\n"
            "Telegram Premium — 6 моҳ: 166.32 с.\n"
            "Telegram Premium — 12 моҳ: 301.54 с.\n\n"
            "Барои харидан ба @DonatixShop муроҷиат кунед.")
    buttons = [[InlineKeyboardButton(text="‹ Бозгашт", callback_data="menu")]]
    await c.message.edit_text(text, reply_markup=kb_buttons(buttons))
    await c.answer()

# ===== API Donatix =====
async def get_balance() -> str:
    if not DONATIX_KEY:
        return "0.00"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{API}/balance", headers=HEADERS,
                             timeout=aiohttp.ClientTimeout(total=10)) as r:
                data = await r.json()
        return data.get("balance", "0.00")
    except Exception:
        return "0.00"

# ===== Веб-сервер + самопинг =====
async def health(_request):
    return web.Response(text="Shop bot is alive ✅")

async def keep_alive():
    if not EXTERNAL_URL:
        return
    async with aiohttp.ClientSession() as session:
        while True:
            await asyncio.sleep(600)
            try:
                async with session.get(EXTERNAL_URL,
                                       timeout=aiohttp.ClientTimeout(total=60)) as r:
                    await r.text()
            except Exception as e:
                print("ping error:", e)

async def main():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    asyncio.create_task(keep_alive())
    print("🚀 Магазин запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
