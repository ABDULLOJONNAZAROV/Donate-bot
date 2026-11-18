import asyncio
import json
import os
import uuid
from html import escape

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (Message, CallbackQuery,
                           InlineKeyboardMarkup, InlineKeyboardButton)

# ===== Настройки (через Render → Environment) =====
BOT_TOKEN = os.environ["BOT_TOKEN"]
DONATIX_KEY = os.environ.get("DONATIX_KEY", "")   # токен Donatix (dx_live_...)
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
PORT = int(os.environ.get("PORT", 10000))
EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

API = "https://donatix.tj/api/v1"

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ===== Каталог FF пакетов (загружается один раз) =====
ff_packages: list[dict] = []
catalog_loaded_at: float = 0.0

# ===== Состояния пользователей =====
state: dict[int, dict] = {}  # {user_id: {"pkg": {...}, "stage": "id"|"confirm"}}


# ===== Каталог =====
async def load_catalog(force: bool = False):
    global ff_packages, catalog_loaded_at
    import time
    if not force and time.time() - catalog_loaded_at < 900 and ff_packages:
        return
    if not DONATIX_KEY:
        print("Donatix KEY не задан, каталог пустой")
        return
    try:
        async with aiohttp.ClientSession() as s:
            params = {"kind": "topup", "q": "ff", "limit": 500}
            headers = {"X-API-Key": DONATIX_KEY}
            async with s.get(f"{API}/products", params=params,
                             headers=headers,
                             timeout=aiohttp.ClientTimeout(total=30)) as r:
                data = await r.json()
        if data.get("ok"):
            ff_packages = data.get("items", [])
            catalog_loaded_at = time.time()
            print(f"Каталог загружен: {len(ff_packages)} пакетов")
    except Exception as e:
        print("Ошибка загрузки каталога:", e)


def kb_packages():
    if not ff_packages:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Загрузить каталог", callback_data="reload")]])
    rows = []
    for p in ff_packages[:20]:  # показываем первые 20
        title = p.get("title") or p.get("name")
        emoji = p.get("emoji") or "💎"
        price = p.get("price_usd", "?")
        rows.append([InlineKeyboardButton(
            text=f"{emoji} {title} — ${price}",
            callback_data=f"sel:{p['product_id']}")])
    rows.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="reload")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ===== Команды =====
@dp.message(Command("start"))
async def start(m: Message):
    await m.answer(
        "💎 <b>Магазин алмазов Free Fire</b>\n\n"
        "Покупай алмазы быстро и безопасно!\n\n"
        "/buy — выбрать пакет\n"
        "/balance — баланс магазина (админу)\n"
        "/help — помощь", parse_mode="HTML")


@dp.message(Command("help"))
async def help_cmd(m: Message):
    await m.answer(
        "Как купить:\n"
        "1️⃣ /buy → выбери пакет\n"
        "2️⃣ Введи свой ID игрока Free Fire\n"
        "3️⃣ Мы проверим аккаунт и покажем ник\n"
        "4️⃣ Подтверди заказ и переведи оплату по реквизитам\n"
        "5️⃣ Алмазы придут на твой ID автоматически 💎")


@dp.message(Command("buy"))
async def buy(m: Message):
    await load_catalog()
    await m.answer("Выбери пакет алмазов 💎:", reply_markup=kb_packages())


@dp.message(Command("balance"))
async def balance_cmd(m: Message):
    if ADMIN_ID and m.from_user.id != ADMIN_ID:
        return
    if not DONATIX_KEY:
        await m.answer("⚠️ Donatix не подключён")
        return
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{API}/balance",
                             headers={"X-API-Key": DONATIX_KEY},
                             timeout=aiohttp.ClientTimeout(total=20)) as r:
                data = await r.json()
        if data.get("ok"):
            await m.answer(f"💰 Баланс Donatix: <b>${data['balance']}</b>",
                           parse_mode="HTML")
        else:
            await m.answer(f"⚠️ {data.get('error', '?')}")
    except Exception as e:
        await m.answer(f"⚠️ Ошибка: {e}")


@dp.callback_query(F.data == "reload")
async def reload(c: CallbackQuery):
    await load_catalog(force=True)
    try:
        await c.message.edit_reply_markup(reply_markup=kb_packages())
    except Exception:
        pass
    await c.answer("Каталог обновлён")


@dp.callback_query(F.data.startswith("sel:"))
async def select_pkg(c: CallbackQuery):
    pid = c.data.split(":", 1)[1]
    pkg = next((p for p in ff_packages if p["product_id"] == pid), None)
    if not pkg:
        await c.answer("Пакет не найден", show_alert=True)
        return
    state[c.from_user.id] = {"pkg": pkg, "stage": "id"}
    await c.message.answer(
        f"{pkg.get('emoji','💎')} <b>{pkg.get('title') or pkg.get('name')}</b>\n"
        f"💵 Цена: ${pkg.get('price_usd', '?')}\n"
        f"🌍 Регион: {pkg.get('region_title') or pkg.get('region','?')}\n\n"
        f"🆔 Введи свой <b>ID игрока Free Fire</b> (только цифры):",
        parse_mode="HTML")
    await c.answer()


@dp.message(F.text)
async def text_handler(m: Message):
    if m.from_user.id not in state:
        await m.answer("Нажми /buy чтобы начать 💎")
        return
    s = state[m.from_user.id]
    if s["stage"] == "id":
        pid = m.text.strip()
        if not pid.isdigit() or len(pid) < 6 or len(pid) > 15:
            await m.answer("❌ ID должен содержать только цифры (6-15 знаков). Попробуй ещё раз:")
            return
        s["player_id"] = pid
        s["stage"] = "checking"
        await m.answer("🔍 Проверяю аккаунт...")
        pkg = s["pkg"]
        try:
            async with aiohttp.ClientSession() as sess:
                headers = {"X-API-Key": DONATIX_KEY,
                           "Content-Type": "application/json"}
                body = {"product_id": pkg["product_id"],
                        "fields": {"player_id": pid}}
                async with sess.post(f"{API}/accounts/check",
                                     json=body, headers=headers,
                                     timeout=aiohttp.ClientTimeout(total=30)) as r:
                    data = await r.json()
        except Exception as e:
            await m.answer(f"⚠️ Ошибка проверки: {e}")
            s["stage"] = "id"
            return
        if not data.get("ok"):
            await m.answer(f"❌ Аккаунт не найден или ошибка: {data.get('error','?')}\nВведи правильный ID:")
            s["stage"] = "id"
            return
        nick = data.get("player_name") or pid
        s["stage"] = "confirm"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить и оплатить",
                                  callback_data="confirm:yes")],
            [InlineKeyboardButton(text="❌ Отмена",
                                  callback_data="confirm:no")],
        ])
        await m.answer(
            f"✅ Аккаунт найден!\n\n"
            f"👤 Ник: <b>{escape(str(nick))}</b>\n"
            f"💎 Пакет: {pkg.get('title') or pkg.get('name')}\n"
            f"💵 К оплате: <b>${pkg.get('price_usd','?')}</b>\n\n"
            f"Проверь ник! После подтверждения — алмазы уйдут на этот аккаунт.",
            reply_markup=kb, parse_mode="HTML")


@dp.callback_query(F.data.startswith("confirm:"))
async def confirm_order(c: CallbackQuery):
    ans = c.data.split(":", 1)[1]
    if ans == "no" or c.from_user.id not in state:
        state.pop(c.from_user.id, None)
        await c.message.answer("Заказ отменён. /buy — выбрать заново.")
        await c.answer()
        return
    s = state.pop(c.from_user.id)
    pkg = s["pkg"]
    pid = s["player_id"]
    await c.answer("Создаю заказ...")
    try:
        async with aiohttp.ClientSession() as sess:
            headers = {"X-API-Key": DONATIX_KEY,
                       "Content-Type": "application/json",
                       "Idempotency-Key": str(uuid.uuid4())}
            body = {"product_id": pkg["product_id"],
                    "fields": {"player_id": pid}}
            async with sess.post(f"{API}/orders",
                                 json=body, headers=headers,
                                 timeout=aiohttp.ClientTimeout(total=30)) as r:
                data = await r.json()
    except Exception as e:
        await c.message.answer(f"⚠️ Ошибка Donatix: {e}")
        return
    if not data.get("ok"):
        await c.message.answer(f"❌ Ошибка: {data.get('error','?')}")
        return
    order = data["order"]
    oid = order.get("order_id", "?")
    await c.message.answer(
        f"🧾 Заказ <b>#{escape(str(oid))}</b> создан!\n\n"
        f"💎 {pkg.get('title') or pkg.get('name')}\n"
        f"🆔 ID: {pid}\n"
        f"💵 ${pkg.get('price_usd','?')}\n\n"
        f"Переведи оплату по реквизитам продавца, "
        f"затем нажми кнопку ниже — проверим статус.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Проверить статус",
                                  callback_data=f"stat:{oid}")]]))
    if ADMIN_ID:
        try:
            await bot.send_message(
                ADMIN_ID,
                f"🛒 <b>Новый заказ!</b>\n"
                f"🧾 #{oid}\n"
                f"👤 {c.from_user.full_name} (@{c.from_user.username or '—'})\n"
                f"💎 {pkg.get('title')}\n"
                f"🆔 {pid}\n"
                f"💵 ${pkg.get('price_usd','?')}",
                parse_mode="HTML")
        except Exception:
            pass


@dp.callback_query(F.data.startswith("stat:"))
async def check_status(c: CallbackQuery):
    oid = c.data.split(":", 1)[1]
    await c.answer("Проверяю...")
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(f"{API}/orders/{oid}",
                                headers={"X-API-Key": DONATIX_KEY},
                                timeout=aiohttp.ClientTimeout(total=20)) as r:
                data = await r.json()
    except Exception as e:
        await c.message.answer(f"⚠️ Ошибка: {e}")
        return
    if not data.get("ok"):
        await c.message.answer(f"⚠️ {data.get('error','?')}")
        return
    st = str(data["order"].get("status", "")).lower()
    msg_map = {
        "processing": "⏳ В работе, жди...",
        "completed": "✅ Готово! Алмазы зачислены на твой ID 💎",
        "failed": "❌ Заказ не выполнен (деньги не списались).",
    }
    await c.message.answer(msg_map.get(st, f"Статус: {st}"))


# ===== Веб-сервер + самопинг =====
async def health(_r):
    return web.Response(text="ok")


async def keep_alive():
    if not EXTERNAL_URL:
        return
    async with aiohttp.ClientSession() as s:
        while True:
            await asyncio.sleep(600)
            try:
                async with s.get(EXTERNAL_URL,
                                 timeout=aiohttp.ClientTimeout(total=60)) as r:
                    await r.text()
            except Exception as e:
                print("ping:", e)


async def main():
    await load_catalog()
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    asyncio.create_task(keep_alive())
    print("🚀 Магазин FF запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
