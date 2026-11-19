import asyncio
import json
import os
import time
import uuid
from pathlib import Path

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
MARGIN = float(os.environ.get("MARGIN", "0.15"))
PORT = int(os.environ.get("PORT", 10000))
EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

# ===== Способы пополнения (разные номера) =====
PAY_METHODS = {}
if os.environ.get("DC_NUMBER"):
    PAY_METHODS["dc"] = {"title": "🏙 Душанбе Сити",
                         "number": os.environ["DC_NUMBER"],
                         "holder": os.environ.get("DC_HOLDER", "")}
if os.environ.get("ALIF_NUMBER"):
    PAY_METHODS["alif"] = {"title": "🏦 Алиф",
                           "number": os.environ["ALIF_NUMBER"],
                           "holder": os.environ.get("ALIF_HOLDER", "")}
if not PAY_METHODS and os.environ.get("CARD_NUMBER"):
    PAY_METHODS["card"] = {"title": "💳 Корт",
                           "number": os.environ["CARD_NUMBER"],
                           "holder": os.environ.get("CARD_HOLDER", "")}

API = "https://donatix.tj/api/v1"
HEADERS = {"X-API-Key": DONATIX_KEY}

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ===== База (балансы покупателей) =====
DB_FILE = Path("users.json")

def load_db():
    if DB_FILE.exists():
        return json.loads(DB_FILE.read_text())
    return {"users": {}, "topups": {}}

db = load_db()

def save_db():
    DB_FILE.write_text(json.dumps(db, ensure_ascii=False))

def get_user(uid: int, name: str) -> dict:
    uid = str(uid)
    if uid not in db["users"]:
        db["users"][uid] = {"balance": 0.0, "name": name, "orders": []}
        save_db()
    return db["users"][uid]

# ===== Живой курс USD → TJS =====
usd_tjs = 10.9
rate_at = 0.0

async def update_rate():
    global usd_tjs, rate_at
    if time.time() - rate_at < 3600:
        return
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://open.er-api.com/v6/latest/USD",
                             timeout=aiohttp.ClientTimeout(total=10)) as r:
                data = await r.json()
            if data.get("result") == "success":
                usd_tjs = data["rates"]["TJS"]
                rate_at = time.time()
                print(f"Курс: 1 USD = {usd_tjs:.2f} TJS")
    except Exception as e:
        print("Курс ошибка:", e)

def tjs_price(usd: float) -> float:
    return round(usd * usd_tjs * (1 + MARGIN), 2)

# ===== Каталог =====
catalog = {}
catalog_at = 0.0

async def load_catalog(force=False):
    global catalog, catalog_at
    if not force and catalog and time.time() - catalog_at < 600:
        return
    if not DONATIX_KEY:
        return
    await update_rate()
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{API}/products", params={"kind": "topup", "limit": 500},
                             headers=HEADERS, timeout=aiohttp.ClientTimeout(total=30)) as r:
                data = await r.json()
        catalog.clear()
        for p in data.get("items", []):
            cid = p.get("category_id")
            if cid not in catalog:
                catalog[cid] = {"name": p.get("category_name", cid), "products": []}
            p["price_tjs"] = tjs_price(float(p.get("price_usd", 0)))
            catalog[cid]["products"].append(p)
        catalog_at = time.time()
    except Exception as e:
        print("Каталог ошибка:", e)

user_state = {}

def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ===== Меню =====
async def send_menu(m: Message):
    await load_catalog()
    u = get_user(m.from_user.id, m.from_user.full_name or "")
    text = (f"🔥❤️ Хуш омадед ба магазин!\n\n"
            f"💎 Алмос ва UC — бо ID-и бозингар, пардохт бо сомонӣ.\n"
            f"⚡ Фармоиш пас аз пардохт худкор иҷро мешавад.\n\n"
            f"💰 Баланси шумо: {u['balance']:.2f} с.\n\n"
            f"Бозиро интихоб кунед 👇")
    rows = [
        [InlineKeyboardButton(text="💎 FF СНГ — алмосҳо", callback_data="game:ff_cis"),
         InlineKeyboardButton(text="🇮🇩 FF Индонезия", callback_data="game:ff_id")],
        [InlineKeyboardButton(text="🎯 PUBG Mobile — UC", callback_data="game:pubg")],
        [InlineKeyboardButton(text="🎮 Ҳамаи бозиҳо", callback_data="all_games"),
         InlineKeyboardButton(text="⭐ Stars / Premium", callback_data="tg_stars")],
        [InlineKeyboardButton(text="💰 Баланс", callback_data="balance"),
         InlineKeyboardButton(text="📦 Фармоишҳои ман", callback_data="my_orders")],
        [InlineKeyboardButton(text="🛟 Дастгирӣ", callback_data="support")],
    ]
    await m.answer(text, reply_markup=kb(rows))

@dp.message(Command("start"))
async def start(m: Message):
    await send_menu(m)

@dp.message(Command("buy"))
async def buy(m: Message):
    await send_menu(m)

@dp.message(Command("balance"))
async def balance_cmd(m: Message):
    if ADMIN_ID and m.from_user.id == ADMIN_ID:
        bal = "0.00"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{API}/balance", headers=HEADERS,
                                 timeout=aiohttp.ClientTimeout(total=10)) as r:
                    bal = (await r.json()).get("balance", "0.00")
        except Exception:
            pass
        debt = sum(u["balance"] for u in db["users"].values())
        await m.answer(f"🏦 Баланси Donatix: {bal} USD\n"
                       f"👥 Балансҳои харидорон: {debt:.2f} с.\n"
                       f"📊 Курс: 1 USD = {usd_tjs:.2f} TJS")
        return
    u = get_user(m.from_user.id, m.from_user.full_name or "")
    rows = [
        [InlineKeyboardButton(text="➕ Пур кардан", callback_data="topup")],
        [InlineKeyboardButton(text="📦 Фармоишҳои ман", callback_data="my_orders")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="menu")],
    ]
    await m.answer(f"💰 Баланси шумо: {u['balance']:.2f} с.\n\n"
                   f"Пур кунед — ва дар як клик харед!", reply_markup=kb(rows))

@dp.message(Command("help"))
async def help_cmd(m: Message):
    await m.answer("📖 Роҳнамо:\n\n"
                   "/start — Менюи асосӣ\n"
                   "/balance — Баланси шумо\n"
                   "/help — Роҳнамо\n\n"
                   "Харид: /start → бозӣ → пакет → ID → тасдиқ.\n"
                   "Пур кардан: 💰 Баланс → ➕ Пур кардан.")

# ===== Callback =====
@dp.callback_query(F.data == "menu")
async def cb_menu(c: CallbackQuery):
    await c.message.delete()
    await send_menu(c.message)
    await c.answer()

@dp.callback_query(F.data == "all_games")
async def cb_all_games(c: CallbackQuery):
    await load_catalog()
    rows, row = [], []
    for cid, g in catalog.items():
        row.append(InlineKeyboardButton(text=g["name"][:24], callback_data=f"cat:{cid}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🏠 Меню", callback_data="menu")])
    await c.message.edit_text("🎮 Ҳамаи бозиҳо:\n\nБозиро интихоб кунед 👇", reply_markup=kb(rows))
    await c.answer()

@dp.callback_query(F.data.startswith("game:"))
async def cb_game(c: CallbackQuery):
    game = c.data.split(":")[1]
    await load_catalog()
    found = None
    for cid, g in catalog.items():
        n = g["name"].lower()
        if game == "ff_cis" and ("free fire" in n or "ff" in n) and ("cis" in n or "снг" in n):
            found = cid; break
        if game == "ff_id" and ("free fire" in n or "ff" in n) and ("indon" in n or "индон" in n):
            found = cid; break
        if game == "pubg" and "pubg" in n:
            found = cid; break
    if found:
        await show_category(c, found)
    else:
        names = ", ".join(g["name"] for g in list(catalog.values())[:8])
        await c.answer(f"Ёфт нашуд. Ҳаст: {names}", show_alert=True)

@dp.callback_query(F.data.startswith("cat:"))
async def cb_cat(c: CallbackQuery):
    await show_category(c, c.data.split(":")[1])

async def show_category(c: CallbackQuery, cid: str):
    await load_catalog()
    if cid not in catalog:
        await c.answer("Ёфт нашуд", show_alert=True); return
    g = catalog[cid]
    groups = {}
    for p in g["products"]:
        n = (p.get("name", "") + " " + (p.get("title") or "")).lower()
        if "diamond" in n or "алмаз" in n or "uc" in n:
            grp = "💎 Алмос / UC"
        elif "weekly" in n or "monthly" in n or "voucher" in n or "ваучер" in n or "prime" in n or "pass" in n:
            grp = "🎫 Ваучерҳо ва пропускҳо"
        elif "level" in n or "evo" in n or "прокач" in n:
            grp = "🚀 Прокачка"
        else:
            grp = "🎁 Дигар"
        groups.setdefault(grp, []).append(p)
    text = f"{g['name']}\n━━━━━━━━━━━━━━━━━━\n\nПакетро интихоб кунед — баъд ID-и бозингарро мепурсам 👇\n"
    rows = []
    for grp, prods in groups.items():
        text += f"\n━━ {grp} ━━\n"
        line = []
        for p in prods[:12]:
            t = (p.get("title") or p.get("name", ""))[:22]
            line.append(InlineKeyboardButton(text=f"{t} — {p['price_tjs']} с.",
                                             callback_data=f"pkg:{p['product_id']}"))
            if len(line) == 2:
                rows.append(line); line = []
        if line:
            rows.append(line)
    rows.append([InlineKeyboardButton(text="🏠 Меню", callback_data="menu")])
    await c.message.edit_text(text, reply_markup=kb(rows))
    await c.answer()

@dp.callback_query(F.data.startswith("pkg:"))
async def cb_pkg(c: CallbackQuery):
    pid = c.data.split(":")[1]
    product = next((p for g in catalog.values() for p in g["products"]
                    if p["product_id"] == pid), None)
    if not product:
        await c.answer("Ёфт нашуд", show_alert=True); return
    user_state[c.from_user.id] = {"stage": "waiting_id", "product": product}
    await c.message.answer(f"📦 {product.get('title') or product.get('name')}\n"
                           f"💰 Нарх: {product['price_tjs']} с.\n\n"
                           f"🆔 ID-и бозингарро ворид кунед (рақамҳо):")
    await c.answer()

@dp.callback_query(F.data == "cancel")
async def cb_cancel(c: CallbackQuery):
    user_state.pop(c.from_user.id, None)
    await c.message.edit_text("❌ Бекор карда шуд. /start — аз нав.")
    await c.answer()

@dp.callback_query(F.data.startswith("cfm:"))
async def cb_confirm(c: CallbackQuery):
    _, pid, player_id = c.data.split(":")
    product = next((p for g in catalog.values() for p in g["products"]
                    if p["product_id"] == pid), None)
    if not product:
        await c.answer("Ёфт нашуд", show_alert=True); return
    u = get_user(c.from_user.id, c.from_user.full_name or "")
    price = product["price_tjs"]
    if u["balance"] < price:
        await c.message.answer(f"❌ Баланс кам аст!\nЛозим: {price} с.\nДоред: {u['balance']:.2f} с.\n\n"
                               f"Балансро пур кунед 👇",
                               reply_markup=kb([[InlineKeyboardButton(text="➕ Пур кардан",
                                                                      callback_data="topup")]]))
        await c.answer(); return
    if not DONATIX_KEY:
        await c.message.answer("⚠️ Donatix пайваст нест.")
        await c.answer(); return
    await c.answer("⏳ Фармоиш сохта мешавад...")
    try:
        async with aiohttp.ClientSession() as s:
            h = {**HEADERS, "Idempotency-Key": str(uuid.uuid4())}
            async with s.post(f"{API}/orders",
                              json={"product_id": pid, "fields": {"player_id": player_id}},
                              headers=h, timeout=aiohttp.ClientTimeout(total=30)) as r:
                data = await r.json()
        if data.get("ok"):
            oid = data["order"].get("order_id", "?")
            u["balance"] = round(u["balance"] - price, 2)
            u["orders"].append({"oid": oid, "title": product.get("title") or product.get("name"),
                                "price": price, "status": "processing"})
            u["orders"] = u["orders"][-20:]
            save_db()
            user_state.pop(c.from_user.id, None)
            await c.message.answer(f"✅ Фармоиш #{oid} қабул шуд!\n\n"
                                   f"📦 {product.get('title') or product.get('name')}\n"
                                   f"🆔 ID: {player_id}\n"
                                   f"💰 {price} с. аз баланс гирифта шуд.\n"
                                   f"💰 Баланси ҳозира: {u['balance']:.2f} с.\n\n"
                                   f"⏳ Алмосҳо ба зудӣ меоянд!")
            if ADMIN_ID:
                await bot.send_message(ADMIN_ID, f"💸 Фурӯш: #{oid} · {price} с. · {c.from_user.full_name}")
        else:
            await c.message.answer(f"❌ Хатои Donatix: {data.get('error', '?')}")
    except Exception as e:
        await c.message.answer(f"⚠️ Хатоӣ: {e}")

# ===== Пополнение: выбор способа → сумма → реквизиты =====
@dp.callback_query(F.data == "topup")
async def cb_topup(c: CallbackQuery):
    if not PAY_METHODS:
        await c.answer("⚠️ Рақамҳо барои пур кардан танзим нашудаанд (Render → Environment)",
                       show_alert=True)
        return
    rows = [[InlineKeyboardButton(text=m["title"], callback_data=f"tm:{key}")]
            for key, m in PAY_METHODS.items()]
    rows.append([InlineKeyboardButton(text="🏠 Меню", callback_data="menu")])
    await c.message.answer("💳 Усули пардохтро интихоб кунед:", reply_markup=kb(rows))
    await c.answer()

@dp.callback_query(F.data.startswith("tm:"))
async def cb_method(c: CallbackQuery):
    mk = c.data.split(":")[1]
    if mk not in PAY_METHODS:
        await c.answer("Ёфт нашуд", show_alert=True); return
    rows = [
        [InlineKeyboardButton(text="10 с.", callback_data=f"tamt:10:{mk}"),
         InlineKeyboardButton(text="20 с.", callback_data=f"tamt:20:{mk}"),
         InlineKeyboardButton(text="50 с.", callback_data=f"tamt:50:{mk}")],
        [InlineKeyboardButton(text="100 с.", callback_data=f"tamt:100:{mk}"),
         InlineKeyboardButton(text="200 с.", callback_data=f"tamt:200:{mk}"),
         InlineKeyboardButton(text="✏️ Дигар", callback_data=f"tamt:custom:{mk}")],
        [InlineKeyboardButton(text="‹ Бозгашт", callback_data="topup")],
    ]
    await c.message.edit_text(f"{PAY_METHODS[mk]['title']} — миқдорро интихоб кунед:",
                              reply_markup=kb(rows))
    await c.answer()

@dp.callback_query(F.data.startswith("tamt:"))
async def cb_topup_amount(c: CallbackQuery):
    _, v, mk = c.data.split(":")
    if mk not in PAY_METHODS:
        await c.answer("Ёфт нашуд", show_alert=True); return
    if v == "custom":
        user_state[c.from_user.id] = {"stage": "topup_custom", "method": mk}
        await c.message.answer("✏️ Миқдорро бо рақам нависед (масалан 35):")
        await c.answer(); return
    await start_topup(c.message, c.from_user.id, float(v), mk)
    await c.answer()

async def start_topup(msg: Message, uid: int, amount: float, mk: str):
    pm = PAY_METHODS[mk]
    tid = uuid.uuid4().hex[:8]
    db["topups"][tid] = {"uid": uid, "amount": amount, "method": mk, "status": "pending"}
    save_db()
    user_state[uid] = {"stage": "receipt", "tid": tid}
    holder = f"\n👤 {pm['holder']}" if pm["holder"] else ""
    await msg.answer(f"💳 {pm['title']} — барои пур кардан:\n\n"
                     f"1️⃣ Ба ин рақам гузаронед: <code>{pm['number']}</code>{holder}\n"
                     f"💵 Миқдор: {amount:.2f} с.\n\n"
                     f"2️⃣ Чек (акс)-ро ба ҳамин чат фиристед 📸", parse_mode="HTML")

@dp.message(F.photo)
async def got_receipt(m: Message):
    st = user_state.get(m.from_user.id)
    if not st or st.get("stage") != "receipt":
        return
    tid = st["tid"]
    topup = db["topups"].get(tid)
    if not topup:
        return
    user_state.pop(m.from_user.id, None)
    if ADMIN_ID:
        await bot.copy_message(ADMIN_ID, m.chat.id, m.message_id)
        mtitle = PAY_METHODS.get(topup.get("method", ""), {}).get("title", "💳")
        await bot.send_message(ADMIN_ID,
            f"🧾 Чеки нав!\n👤 {m.from_user.full_name} (ID {m.from_user.id})\n"
            f"💵 {topup['amount']:.2f} с. · {mtitle} (чек {tid})",
            reply_markup=kb([[InlineKeyboardButton(text="✅ Тасдиқ", callback_data=f"tok:{tid}"),
                              InlineKeyboardButton(text="❌ Рад", callback_data=f"tno:{tid}")]]))
        await m.answer("✅ Чек қабул шуд! Интизори тасдиқ бошед.")
    else:
        await m.answer("⚠️ Админ танзим нашудааст (ADMIN_ID).")

@dp.callback_query(F.data.startswith("tok:"))
async def cb_topup_ok(c: CallbackQuery):
    tid = c.data.split(":")[1]
    topup = db["topups"].get(tid)
    if not topup or topup["status"] != "pending":
        await c.answer("Аллакай кор карда шуд", show_alert=True); return
    topup["status"] = "done"
    u = get_user(topup["uid"], "")
    u["balance"] = round(u["balance"] + topup["amount"], 2)
    save_db()
    try:
        await bot.send_message(topup["uid"], f"💰 Баланси шумо пур шуд!\n"
                                             f"➕ {topup['amount']:.2f} с.\n"
                                             f"💰 Баланси ҳозира: {u['balance']:.2f} с.")
    except Exception:
        pass
    await c.message.edit_text(c.message.text + f"\n\n✅ Тасдиқ карда шуд ({c.from_user.full_name})")
    await c.answer()

@dp.callback_query(F.data.startswith("tno:"))
async def cb_topup_no(c: CallbackQuery):
    tid = c.data.split(":")[1]
    topup = db["topups"].get(tid)
    if topup:
        topup["status"] = "rejected"
        save_db()
        try:
            await bot.send_message(topup["uid"], "❌ Чек тасдиқ нашуд. Бо дастгирӣ тамос гиред.")
        except Exception:
            pass
    await c.message.edit_text(c.message.text + f"\n\n❌ Рад карда шуд ({c.from_user.full_name})")
    await c.answer()

# ===== Баланс / заказы / поддержка =====
@dp.callback_query(F.data == "balance")
async def cb_balance(c: CallbackQuery):
    u = get_user(c.from_user.id, c.from_user.full_name or "")
    rows = [
        [InlineKeyboardButton(text="➕ Пур кардан", callback_data="topup")],
        [InlineKeyboardButton(text="📦 Фармоишҳои ман", callback_data="my_orders")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="menu")],
    ]
    await c.message.edit_text(f"💰 Баланси шумо: {u['balance']:.2f} с.\n\n"
                              f"Пур кунед — ва дар як клик харед!", reply_markup=kb(rows))
    await c.answer()

@dp.callback_query(F.data == "my_orders")
async def cb_my_orders(c: CallbackQuery):
    u = get_user(c.from_user.id, c.from_user.full_name or "")
    if DONATIX_KEY:
        async with aiohttp.ClientSession() as s:
            for o in u["orders"][-8:]:
                try:
                    async with s.get(f"{API}/orders/{o['oid']}", headers=HEADERS,
                                     timeout=aiohttp.ClientTimeout(total=10)) as r:
                        d = await r.json()
                    if d.get("ok"):
                        o["status"] = d["order"].get("status", o["status"])
                except Exception:
                    pass
        save_db()
    if not u["orders"]:
        text = "📦 Фармоишҳои шумо:\n\nҲоло фармоиш нест."
    else:
        text = "📦 Фармоишҳои шумо:\n\n"
        for o in reversed(u["orders"][-10:]):
            icon = {"completed": "✅", "failed": "❌"}.get(o["status"], "⏳")
            text += f"{icon} {o['oid']} · {o['title']} · {o['price']} с.\n"
    rows = [[InlineKeyboardButton(text="🔄 Навсозӣ", callback_data="my_orders")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="menu")]]
    await c.message.edit_text(text, rep
