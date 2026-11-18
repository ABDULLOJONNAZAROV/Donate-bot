import asyncio
import json
import os
from html import escape
from pathlib import Path

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (Message, CallbackQuery, PreCheckoutQuery, LabeledPrice,
                           InlineKeyboardMarkup, InlineKeyboardButton)

# ===== Настройки (задаются на Render → Environment) =====
BOT_TOKEN = os.environ["BOT_TOKEN"]            # токен от @BotFather
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))  # твой ID — сюда приходят уведомления
DONATEPAY_KEY = os.environ.get("DONATEPAY_KEY", "")  # необязательно
GOAL = int(os.environ.get("GOAL_STARS", "10000"))    # цель сбора в звёздах
PORT = int(os.environ.get("PORT", 10000))
EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ===== Хранилище (простой JSON-файл) =====
DATA_FILE = Path("data.json")

def load_data():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return {"subs": [], "total": 0, "count": 0, "donors": {}}

data = load_data()

def save_data():
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False))

waiting_custom: set[int] = set()  # кто вводит свою сумму

def menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ 10", callback_data="donate:10"),
         InlineKeyboardButton(text="⭐ 50", callback_data="donate:50"),
         InlineKeyboardButton(text="⭐ 100", callback_data="donate:100")],
        [InlineKeyboardButton(text="⭐ 250", callback_data="donate:250"),
         InlineKeyboardButton(text="✏️ Своя сумма", callback_data="donate:custom")],
    ])

# ===== Команды =====
@dp.message(Command("start"))
async def cmd_start(m: Message):
    if m.chat.id not in data["subs"]:
        data["subs"].append(m.chat.id)
        save_data()
    await m.answer("👋 Привет! Это донат-бот.\n\n"
                   "💰 /donate — задонатить (Telegram Stars)\n"
                   "📊 /stats — статистика и топ донатов\n"
                   "🆔 /id — узнать свой ID\n"
                   "ℹ️ /help — помощь")

@dp.message(Command("help"))
async def cmd_help(m: Message):
    await m.answer("Нажми /donate, выбери сумму и оплати звёздами ⭐\n"
                   "Донаты — добровольная поддержка автора 💜")

@dp.message(Command("id"))
async def cmd_id(m: Message):
    await m.answer(f"Твой ID: <code>{m.chat.id}</code>", parse_mode="HTML")

@dp.message(Command("donate"))
async def cmd_donate(m: Message):
    await m.answer("Выбери сумму доната ⭐:", reply_markup=menu_kb())

@dp.callback_query(F.data.startswith("donate:"))
async def cb_donate(c: CallbackQuery):
    value = c.data.split(":")[1]
    if value == "custom":
        waiting_custom.add(c.from_user.id)
        await c.message.answer("✏️ Введи число — сколько звёзд (от 1 до 10000):")
    else:
        await send_invoice(c.message.chat.id, int(value))
    await c.answer()

async def send_invoice(chat_id: int, amount: int):
    amount = max(1, min(amount, 10000))
    await bot.send_invoice(
        chat_id=chat_id,
        title="Донат автору 💜",
        description=f"Поддержка проекта на {amount} ⭐. Спасибо!",
        payload=f"donate_{amount}",
        provider_token="",   # для Telegram Stars — пустая строка
        currency="XTR",      # XTR = Telegram Stars
        prices=[LabeledPrice(label="Донат", amount=amount)],
    )

@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    # ответить нужно в течение 10 секунд, иначе платёж отменится
    await bot.answer_pre_checkout_query(q.id, ok=True)

@dp.message(F.successful_payment)
async def paid(m: Message):
    amount = m.successful_payment.total_amount
    uid = str(m.from_user.id)
    name = m.from_user.full_name or "Аноним"
    data["total"] += amount
    data["count"] += 1
    donor = data["donors"].get(uid, {"name": name, "sum": 0})
    donor["name"] = name
    donor["sum"] += amount
    data["donors"][uid] = donor
    save_data()
    await m.answer(f"💜 Спасибо за {amount} ⭐! Ты лучший!")
    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID,
                f"💰 <b>Новый донат!</b>\n👤 {escape(name)}\n⭐ {amount}\n"
                f"Всего собрано: {data['total']} ⭐", parse_mode="HTML")
        except Exception:
            pass

@dp.message(Command("stats"))
async def cmd_stats(m: Message):
    total = data["total"]
    pct = min(100, int(total * 100 / GOAL)) if GOAL else 0
    bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
    lines = [f"📊 Собрано: <b>{total} ⭐</b> ({data['count']} донатов)",
             f"🎯 Цель {GOAL} ⭐: {bar} {pct}%"]
    top = sorted(data["donors"].values(), key=lambda d: d["sum"], reverse=True)[:5]
    if top:
        lines.append("\n🏆 Топ донатеров:")
        for i, d in enumerate(top, 1):
            lines.append(f"{i}. {escape(d['name'])} — {d['sum']} ⭐")
    await m.answer("\n".join(lines), parse_mode="HTML")

@dp.message(F.text)
async def any_text(m: Message):
    if m.from_user.id in waiting_custom:
        waiting_custom.discard(m.from_user.id)
        if m.text.strip().isdigit():
            await send_invoice(m.chat.id, int(m.text.strip()))
        else:
            await m.answer("Это не число 😅 Нажми /donate и попробуй снова.")
    elif m.chat.type == "private":
        await m.answer("Нажми /donate 💜")

# ===== Необязательный модуль DonatePay (включится, если задать DONATEPAY_KEY) =====
async def donatepay_watcher():
    seen, first = set(), True
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                params = {"access_token": DONATEPAY_KEY, "status": "success", "limit": 20}
                async with session.get("https://donatepay.ru/api/v1/transactions",
                                       params=params,
                                       timeout=aiohttp.ClientTimeout(total=20)) as r:
                    items = (await r.json()).get("data", [])
                for d in reversed(items):
                    did = str(d.get("id"))
                    if did in seen:
                        continue
                    seen.add(did)
                    if not first:
                        name = escape((d.get("vars") or {}).get("name") or "Аноним")
                        text = (f"💰 <b>Донат через DonatePay!</b>\n👤 {name}\n"
                                f"💵 {d.get('sum', '?')} ₽\n"
                                f"💬 {escape(d.get('comment') or '—')}")
                        for chat_id in list(data["subs"]):
                            try:
                                await bot.send_message(chat_id, text, parse_mode="HTML")
                            except Exception:
                                pass
                first = False
            except Exception as e:
                print("DonatePay error:", e)
            await asyncio.sleep(60)  # DonatePay: не чаще 1 запроса в 20 сек

# ===== Веб-сервер для Render + самопинг против засыпания =====
async def health(_request):
    return web.Response(text="Bot is alive ✅")

async def keep_alive():
    if not EXTERNAL_URL:
        return
    async with aiohttp.ClientSession() as session:
        while True:
            await asyncio.sleep(600)  # каждые 10 минут
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
    if DONATEPAY_KEY:
        asyncio.create_task(donatepay_watcher())
    asyncio.create_task(keep_alive())
    print("🚀 Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
