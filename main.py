import asyncio, hashlib, hmac, json, os, time, uuid, urllib.parse
from pathlib import Path

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (Message, CallbackQuery, InlineKeyboardMarkup,
                           InlineKeyboardButton, MenuButtonWebApp, WebAppInfo)

# ===== Настройки =====
BOT_TOKEN = os.environ["BOT_TOKEN"]
DONATIX_KEY = os.environ.get("DONATIX_KEY", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
MARGIN = float(os.environ.get("MARGIN", "0.15"))
PORT = int(os.environ.get("PORT", 10000))
EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

PAY_METHODS = {}
if os.environ.get("DC_NUMBER"):
    PAY_METHODS["dc"] = {"title": "🏙 Душанбе Сити", "number": os.environ["DC_NUMBER"],
                        "holder": os.environ.get("DC_HOLDER", "")}
if os.environ.get("ALIF_NUMBER"):
    PAY_METHODS["alif"] = {"title": "🏦 Алиф", "number": os.environ["ALIF_NUMBER"],
                          "holder": os.environ.get("ALIF_HOLDER", "")}

API = "https://donatix.tj/api/v1"
HEADERS = {"X-API-Key": DONATIX_KEY}
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ===== База =====
DB_FILE = Path("users.json")
def load_db():
    return json.loads(DB_FILE.read_text()) if DB_FILE.exists() else {"users": {}, "topups": {}}
db = load_db()
def save_db():
    DB_FILE.write_text(json.dumps(db, ensure_ascii=False))

def get_user(uid, name=""):
    uid = str(uid)
    if uid not in db["users"]:
        db["users"][uid] = {"balance": 0.0, "name": name, "blocked": False, "orders": []}
        save_db()
    u = db["users"][uid]
    if name: u["name"] = name
    return u

def blocked(m):
    return get_user(m.from_user.id, m.from_user.full_name or "")["blocked"]

# ===== Курс =====
usd_tjs, rate_at = 10.9, 0.0
async def update_rate():
    global usd_tjs, rate_at
    if time.time() - rate_at < 3600: return
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://open.er-api.com/v6/latest/USD",
                             timeout=aiohttp.ClientTimeout(total=10)) as r:
                d = await r.json()
        if d.get("result") == "success":
            usd_tjs = d["rates"]["TJS"]; rate_at = time.time()
    except Exception as e:
        print("rate:", e)

def tjs(usd): return round(usd * usd_tjs * (1 + MARGIN), 2)

# ===== Каталог =====
catalog, special, cat_at = {}, {"stars": None, "premium": {}}, 0.0
async def load_catalog(force=False):
    global catalog, special, cat_at
    if not force and catalog and time.time() - cat_at < 600: return
    if not DONATIX_KEY: return
    await update_rate()
    try:
        async with aiohttp.ClientSession() as s:
            async def get(params):
                async with s.get(f"{API}/products", params=params, headers=HEADERS,
                                 timeout=aiohttp.ClientTimeout(total=30)) as r:
                    return await r.json()
            data = await get({"kind": "topup", "limit": 500})
            stars = await get({"kind": "telegram_stars", "limit": 5})
            prem = await get({"kind": "telegram_premium", "limit": 10})
        catalog.clear()
        for p in data.get("items", []):
            cid = p.get("category_id")
            catalog.setdefault(cid, {"name": p.get("category_name", cid), "products": []})
            p["price_tjs"] = tjs(float(p.get("price_usd", 0)))
            catalog[cid]["products"].append(p)
        for it in stars.get("items", []):
            if it.get("product_id") == "tg-stars":
                special["stars"] = {"unit": float(it["price_usd"]),
                                    "min": it.get("min_quantity", 50),
                                    "max": it.get("max_quantity", 10000)}
        special["premium"] = {p["product_id"]: p for p in prem.get("items", [])}
        cat_at = time.time()
    except Exception as e:
        print("catalog:", e)

def find_product(pid):
    for g in catalog.values():
        for p in g["products"]:
            if p["product_id"] == pid: return p
    return None

user_state = {}
def kb(rows): return InlineKeyboardMarkup(inline_keyboard=rows)

# ===== Меню =====
async def send_menu(m):
    await load_catalog()
    u = get_user(m.from_user.id, m.from_user.full_name or "")
    text = (f"🔥❤️ Хуш омадед ба магазин!\n\n"
            f"💎 Алмос ва UC — бо ID-и бозингар, пардохт бо сомонӣ.\n"
            f"⚡ Фармоиш пас аз пардохт худкор иҷро мешавад.\n\n"
            f"💰 Баланси шумо: {u['balance']:.2f} с.\n\nБозиро интихоб кунед 👇")
    rows = [
        [InlineKeyboardButton(text="💎 FF СНГ", callback_data="game:ff_cis"),
         InlineKeyboardButton(text="🇮🇩 FF Индонезия", callback_data="game:ff_id")],
        [InlineKeyboardButton(text="🎯 PUBG Mobile — UC", callback_data="game:pubg")],
        [InlineKeyboardButton(text="🎮 Ҳамаи бозиҳо", callback_data="all_games"),
         InlineKeyboardButton(text="⭐ Stars / Premium", callback_data="tg_stars")],
        [InlineKeyboardButton(text="💰 Баланс", callback_data="balance"),
         InlineKeyboardButton(text="📦 Фармоишҳои ман", callback_data="my_orders")],
        [InlineKeyboardButton(text="🛟 Дастгирӣ", callback_data="support")],
    ]
    if m.from_user.id == ADMIN_ID:
        rows.append([InlineKeyboardButton(text="🛠 Панели админ", callback_data="admin")])
    await m.answer(text, reply_markup=kb(rows))

@dp.message(Command("start"))
async def start(m): await send_menu(m)
@dp.message(Command("buy"))
async def buy(m): await send_menu(m)
@dp.message(Command("help"))
async def help_cmd(m):
    await m.answer("📖 /start — меню · /balance — баланс · Харид: бозӣ → пакет → ID → тасдиқ.")

# ===== Игры (робаст, кнопки больше не «белеют») =====
@dp.callback_query(F.data.startswith("game:"))
async def cb_game(c):
    try:
        await load_catalog()
        game = c.data.split(":")[1]
        found = None
        for cid, g in catalog.items():
            hay = (cid + " " + g["name"]).lower().replace("_", " ")
            if game == "ff_cis" and "free fire" in hay and ("cis" in hay or "снг" in hay) and "indon" not in hay:
                found = cid; break
            if game == "ff_id" and "free fire" in hay and "indon" in hay:
                found = cid; break
            if game == "pubg" and "pubg" in hay:
                found = cid; break
        if found:
            await show_category(c, found)
        else:
            names = "\n".join(f"{cid} = {g['name']}" for cid, g in list(catalog.items())[:12])
            await c.answer(f"Ёфт нашуд 👇\n{names}", show_alert=True)
    except Exception as e:
        await c.answer(f"Хато: {e}", show_alert=True)
    finally:
        try: await c.answer()
        except Exception: pass

@dp.callback_query(F.data.startswith("cat:"))
async def cb_cat(c):
    try:
        await show_category(c, c.data.split(":")[1])
    except Exception as e:
        await c.answer(f"Хато: {e}", show_alert=True)

async def show_category(c, cid):
    await load_catalog()
    if cid not in catalog:
        await c.answer("Ёфт нашуд", show_alert=True); return
    g = catalog[cid]
    groups = {}
    for p in g["products"]:
        n = (p.get("name", "") + " " + (p.get("title") or "")).lower()
        if "diamond" in n or "алмаз" in n or "uc" in n: grp = "💎 Алмос / UC"
        elif "weekly" in n or "monthly" in n or "voucher" in n or "prime" in n or "pass" in n: grp = "🎫 Ваучерҳо"
        elif "level" in n or "evo" in n: grp = "🚀 Прокачка"
        else: grp = "🎁 Дигар"
        groups.setdefault(grp, []).append(p)
    text, rows = f"{g['name']}\n━━━ Пакетро интихоб кунед 👇\n", []
    for grp, prods in groups.items():
        if len(text) > 3500: break
        text += f"\n━━ {grp} ━━\n"
        line = []
        for p in prods[:12]:
            t = (p.get("title") or p.get("name", ""))[:20]
            line.append(InlineKeyboardButton(text=f"{t} — {p['price_tjs']} с.",
                                             callback_data=f"pkg:{p['product_id']}"))
            if len(line) == 2: rows.append(line); line = []
        if line: rows.append(line)
    rows.append([InlineKeyboardButton(text="🏠 Меню", callback_data="menu")])
    try:
        await c.message.edit_text(text, reply_markup=kb(rows))
    except Exception:
        await c.message.answer(text, reply_markup=kb(rows))

@dp.callback_query(F.data.startswith("pkg:"))
async def cb_pkg(c):
    if blocked(c.message):
        await c.answer("🚫 Шумо блокир карда шудед", show_alert=True); return
    product = find_product(c.data.split(":")[1])
    if not product:
        await c.answer("Ёфт нашуд", show_alert=True); return
    user_state[c.from_user.id] = {"stage": "waiting_id", "product": product}
    await c.message.answer(f"📦 {product.get('title') or product.get('name')}\n"
                           f"💰 {product['price_tjs']} с.\n\n🆔 ID-и бозингарро ворид кунед:")
    await c.answer()

# ===== Stars / Premium (реально работают) =====
@dp.callback_query(F.data == "tg_stars")
async def cb_stars(c):
    await load_catalog()
    rows = []
    if special["stars"]:
        unit = special["stars"]["unit"]
        for q in (50, 100, 250, 500, 1000):
            rows.append([InlineKeyboardButton(text=f"⭐ {q} — {tjs(unit*q)} с.",
                                              callback_data=f"stq:{q}")])
    for pid, p in special["premium"].items():
        if pid.startswith("tg-premium-"):
            rows.append([InlineKeyboardButton(text=f"👑 Premium {pid.split('-')[-1]} моҳ — {tjs(float(p['price_usd']))} с.",
                                              callback_data=f"prq:{pid}")])
    rows.append([InlineKeyboardButton(text="🏠 Меню", callback_data="menu")])
    try:
        await c.message.edit_text("⭐ Telegram Stars ва Premium\n\nМиқдорро интихоб кунед:", reply_markup=kb(rows))
    except Exception:
        await c.message.answer("⭐ Telegram Stars ва Premium", reply_markup=kb(rows))
    await c.answer()

@dp.callback_query(F.data.startswith(("stq:", "prq:")))
async def cb_star_pick(c):
    if blocked(c.message):
        await c.answer("🚫 Шумо блокир карда шудед", show_alert=True); return
    kind, val = c.data.split(":")
    if kind == "stq":
        if not special["stars"]: await c.answer("Дастрас нест", show_alert=True); return
        price = tjs(special["stars"]["unit"] * int(val))
        user_state[c.from_user.id] = {"stage": "waiting_uname", "kind": "stars", "qty": int(val), "price": price}
        await c.message.answer(f"⭐ {val} Stars — {price} с.\n\n💬 @username-и гирандаро ворид кунед:")
    else:
        p = special["premium"].get(val)
        if not p: await c.answer("Ёфт нашуд", show_alert=True); return
        price = tjs(float(p["price_usd"]))
        user_state[c.from_user.id] = {"stage": "waiting_uname", "kind": "premium", "pid": val, "price": price}
        await c.message.answer(f"👑 {p.get('title') or p.get('name')} — {price} с.\n\n💬 @username-ро ворид кунед:")
    await c.answer()

# ===== Ввод текста (ID / username) =====
@dp.message(F.text)
async def text_handler(m):
    st = user_state.get(m.from_user.id)
    if not st: return
    if st["stage"] == "waiting_id" and m.text.strip().isdigit() and 6 <= len(m.text.strip()) <= 15:
        p = st["product"]; pid = m.text.strip()
        rows = [[InlineKeyboardButton(text="✅ Тасдиқ", callback_data=f"cfm:{p['product_id']}:{pid}"),
                 InlineKeyboardButton(text="❌ Бекор", callback_data="cancel")]]
        await m.answer(f"📦 {p.get('title') or p.get('name')}\n🆔 {pid}\n💰 {p['price_tjs']} с.\nТасдиқ мекунед?",
                       reply_markup=kb(rows))
    elif st["stage"] == "waiting_uname" and m.text.strip().startswith("@") and len(m.text.strip()) >= 5:
        uname = m.text.strip()
        if st["kind"] == "stars":
            body = {"product_id": "tg-stars", "quantity": st["qty"], "fields": {"telegram_username": uname}}
            title = f"⭐ {st['qty']} Stars"; price = st["price"]
        else:
            body = {"product_id": st["pid"], "fields": {"telegram_username": uname}}
            p = special["premium"].get(st["pid"], {})
            title = p.get("title") or p.get("name", "Premium"); price = st["price"]
        user_state.pop(m.from_user.id)
        await create_order(m.from_user.id, m.chat.id, title, price, body)
    elif st["stage"] == "topup_custom" and m.text.strip().isdigit():
        mk = st.get("method", "dc"); user_state.pop(m.from_user.id)
        await start_topup(m, m.from_user.id, float(m.text.strip()), mk)

@dp.callback_query(F.data == "cancel")
async def cb_cancel(c):
    user_state.pop(c.from_user.id, None)
    await c.message.edit_text("❌ Бекор карда шуд."); await c.answer()

# ===== Создание заказа =====
async def create_order(uid, chat_id, title, price, body):
    u = get_user(uid)
    if u["blocked"]:
        await bot.send_message(chat_id, "🚫 Шумо блокир карда шудед."); return
    if u["balance"] < price:
        await bot.send_message(chat_id, f"❌ Баланс кам! Лозим: {price} с., доред: {u['balance']:.2f} с.",
                               reply_markup=kb([[InlineKeyboardButton(text="➕ Пур кардан", callback_data="topup")]]))
        return
    try:
        async with aiohttp.ClientSession() as s:
            h = {**HEADERS, "Idempotency-Key": str(uuid.uuid4())}
            async with s.post(f"{API}/orders", json=body, headers=h,
                              timeout=aiohttp.ClientTimeout(total=30)) as r:
                data = await r.json()
        if data.get("ok"):
            oid = data["order"].get("order_id", "?")
            u["balance"] = round(u["balance"] - price, 2)
            u["orders"].append({"oid": oid, "title": title, "price": price, "status": "processing"})
            u["orders"] = u["orders"][-20:]; save_db()
            await bot.send_message(chat_id, f"✅ Фармоиш #{oid} қабул шуд!\n💰 {price} с. гирифта шуд.\n"
                                            f"💰 Баланс: {u['balance']:.2f} с.\n⏳ Ба зудӣ тайёр мешавад!")
            if ADMIN_ID:
                await bot.send_message(ADMIN_ID, f"💸 Фурӯш: #{oid} · {price} с. · {u['name']}")
        else:
            await bot.send_message(chat_id, f"❌ Хато: {data.get('error','?')}")
    except Exception as e:
        await bot.send_message(chat_id, f"⚠️ Хатоӣ: {e}")

@dp.callback_query(F.data.startswith("cfm:"))
async def cb_confirm(c):
    _, pid, player_id = c.data.split(":")
    product = find_product(pid)
    if not product: await c.answer("Ёфт нашуд", show_alert=True); return
    user_state.pop(c.from_user.id, None)
    await c.answer("⏳ Сохта мешавад...")
    await create_order(c.from_user.id, c.message.chat.id,
                       product.get("title") or product.get("name"),
                       product["price_tjs"],
                       {"product_id": pid, "fields": {"player_id": player_id}})

# ===== Пополнение =====
@dp.callback_query(F.data == "topup")
async def cb_topup(c):
    if blocked(c.message): await c.answer("🚫 Шумо блокир карда шудед", show_alert=True); return
    if not PAY_METHODS: await c.answer("Рақамҳо танзим нашудаанд", show_alert=True); return
    rows = [[InlineKeyboardButton(text=m["title"], callback_data=f"tm:{k}")] for k, m in PAY_METHODS.items()]
    rows.append([InlineKeyboardButton(text="🏠 Меню", callback_data="menu")])
    await c.message.answer("💳 Усули пардохтро интихоб кунед:", reply_markup=kb(rows)); await c.answer()

@dp.callback_query(F.data.startswith("tm:"))
async def cb_method(c):
    mk = c.data.split(":")[1]
    if mk not in PAY_METHODS: await c.answer("Ёфт нашуд", show_alert=True); return
    rows = [[InlineKeyboardButton(text=f"{v} с.", callback_data=f"tamt:{v}:{mk}") for v in (10, 20, 50)],
            [InlineKeyboardButton(text=f"{v} с.", callback_data=f"tamt:{v}:{mk}") for v in (100, 200)],
            [InlineKeyboardButton(text="✏️ Дигар", callback_data=f"tamt:custom:{mk}")]]
    await c.message.edit_text(f"{PAY_METHODS[mk]['title']} — миқдор:", reply_markup=kb(rows)); await c.answer()

@dp.callback_query(F.data.startswith("tamt:"))
async def cb_topup_amount(c):
    _, v, mk = c.data.split(":")
    if v == "custom":
        user_state[c.from_user.id] = {"stage": "topup_custom", "method": mk}
        await c.message.answer("✏️ Миқдорро бо рақам нависед:")
    else:
        await start_topup(c.message, c.from_user.id, float(v), mk)
    await c.answer()

async def start_topup(msg, uid, amount, mk):
    pm = PAY_METHODS[mk]
    tid = uuid.uuid4().hex[:8]
    db["topups"][tid] = {"uid": uid, "amount": amount, "method": mk, "status": "pending"}
    save_db(); user_state[uid] = {"stage": "receipt", "tid": tid}
    holder = f"\n👤 {pm['holder']}" if pm["holder"] else ""
    await msg.answer(f"💳 {pm['title']}:\n1️⃣ Ба рақам гузаронед: <code>{pm['number']}</code>{holder}\n"
                     f"💵 Миқдор: {amount:.2f} с.\n\n2️⃣ Чек (акс)-ро фиристед 📸", parse_mode="HTML")

@dp.message(F.photo)
async def got_receipt(m):
    st = user_state.get(m.from_user.id)
    if not st or st.get("stage") != "receipt": return
    topup = db["topups"].get(st["tid"])
    if not topup: return
    user_state.pop(m.from_user.id)
    if ADMIN_ID:
        await bot.copy_message(ADMIN_ID, m.chat.id, m.message_id)
        await bot.send_message(ADMIN_ID,
            f"🧾 Чек! 👤 {m.from_user.full_name} (ID {m.from_user.id})\n"
            f"💵 {topup['amount']:.2f} с. · {PAY_METHODS.get(topup.get('method',''),{}).get('title','')} · {st['tid']}",
            reply_markup=kb([[InlineKeyboardButton(text="✅ Тасдиқ", callback_data=f"tok:{st['tid']}"),
                              InlineKeyboardButton(text="❌ Рад", callback_data=f"tno:{st['tid']}")]]))
        await m.answer("✅ Чек қабул шуд, интизори тасдиқ.")

@dp.callback_query(F.data.startswith("tok:"))
async def cb_topup_ok(c):
    if c.from_user.id != ADMIN_ID: await c.answer("🚫", show_alert=True); return
    tid = c.data.split(":")[1]; topup = db["topups"].get(tid)
    if not topup or topup["status"] != "pending": await c.answer("Аллакай кор шуд", show_alert=True); return
    topup["status"] = "done"
    u = get_user(topup["uid"]); u["balance"] = round(u["balance"] + topup["amount"], 2); save_db()
    try:
        await bot.send_message(topup["uid"], f"💰 Баланс пур шуд! ➕ {topup['amount']:.2f} с.\n"
                                             f"💰 Ҳозира: {u['balance']:.2f} с.")
    except Exception: pass
    await c.message.edit_text(c.message.text + f"\n\n✅ Тасдиқ: {c.from_user.full_name}"); await c.answer()

@dp.callback_query(F.data.startswith("tno:"))
async def cb_topup_no(c):
    if c.from_user.id != ADMIN_ID: await c.answer("🚫", show_alert=True); return
    tid = c.data.split(":")[1]; topup = db["topups"].get(tid)
    if topup:
        topup["status"] = "rejected"; save_db()
        try: await bot.send_message(topup["uid"], "❌ Чек тасдиқ нашуд.")
        except Exception: pass
    await c.message.edit_text(c.message.text + f"\n\n❌ Рад: {c.from_user.full_name}"); await c.answer()

# ===== Панель админа =====
@dp.message(Command("admin"))
async def admin_cmd(m):
    if m.from_user.id != ADMIN_ID: return
    await cb_admin_show(m)

@dp.callback_query(F.data == "admin")
async def cb_admin(c):
    if c.from_user.id != ADMIN_ID: await c.answer("🚫", show_alert=True); return
    await c.message.delete()
    await cb_admin_show(c.message); await c.answer()

async def cb_admin_show(m):
    total_bal = sum(u["balance"] for u in db["users"].values())
    pending = sum(1 for t in db["topups"].values() if t["status"] == "pending")
    rows = [[InlineKeyboardButton(text="👥 Харидорон", callback_data="adm_users"),
             InlineKeyboardButton(text=f"🧾 Чеки нав ({pending})", callback_data="adm_pending")],
            [InlineKeyboardButton(text="📦 Фармоишҳо", callback_data="adm_orders")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="menu")]]
    msg = "🛠 Панели админ\n"
    msg += f"👥 Харидорон: {len(db['users'])}\n"
    msg += f"💰 Ҳамаи балансҳо: {total_bal:.2f} с.\n"
    msg += f"📊 Курс: 1 USD = {usd_tjs:.2f} TJS"
    await m.answer(msg, reply_markup=kb(rows))
