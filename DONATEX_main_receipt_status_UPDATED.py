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
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from aiogram.types import WebAppInfo
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F, BaseMiddleware
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
# Дополнительные администраторы: ADMIN_IDS="123456789,987654321".
# Старый ADMIN_ID автоматически остаётся главным администратором.
ADMIN_IDS = {int(x.strip()) for x in os.environ.get("ADMIN_IDS", "").split(",")
             if x.strip().isdigit()}
if ADMIN_ID:
    ADMIN_IDS.add(ADMIN_ID)
MARGIN = float(os.environ.get("MARGIN", "0.15"))
PORT = int(os.environ.get("PORT", 10000))
EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
DB_FILE = Path(os.environ.get("DB_FILE", "users.json"))
BASE_DIR = Path(__file__).resolve().parent
AVATAR_DIR = Path(os.environ.get("AVATAR_DIR", str(BASE_DIR / "uploads" / "avatars")))
REF_PERCENT = float(os.environ.get("REF_PERCENT", "5"))
LOW_BALANCE_USD = float(os.environ.get("LOW_BALANCE_USD", "5"))
BALANCE_PATH = os.environ.get("DONATIX_BALANCE_PATH", "/balance")
SUPPORT_CONTACT = os.environ.get("SUPPORT_CONTACT", "")
MIN_TOPUP = max(2.0, float(os.environ.get("MIN_TOPUP", "2")))
RECEIPTS_CHANNEL_ID = int(os.environ.get("RECEIPTS_CHANNEL_ID", "0"))
MAX_TOPUP = float(os.environ.get("MAX_TOPUP", "5000"))
TZ = timezone(timedelta(hours=5))  # Душанбе

# --- Новые переменные окружения ---да
# Канал для отзывов (например @donatex_reviews) — ссылка-кнопка в /start
REVIEWS_CHANNEL = os.environ.get("REVIEWS_CHANNEL", "")
# ID канала для пересылки отзывов (например -1001234567890)
REVIEWS_CHANNEL_ID = int(os.environ.get("REVIEWS_CHANNEL_ID", "0"))
# Новостные каналы по языкам
NEWS_CHANNEL_TG = os.environ.get("NEWS_CHANNEL_TG", "")
NEWS_CHANNEL_RU = os.environ.get("NEWS_CHANNEL_RU", "")
NEWS_CHANNEL_EN = os.environ.get("NEWS_CHANNEL_EN", "")
DC_PAY_URL = os.environ.get("DC_PAY_URL", "https://pay.dc.tj/?a=9762000129734579&c=Donatix%20%239586&f1=133&s=20.01")
EXPRESS_PAY_URL = os.environ.get("EXPRESS_PAY_URL", "http://pay.expresspay.tj/?A=9762000239541922&s=&c=&f1=133&FIELD2=&FIELD3=")
DC_TRANSFER_PHONE = os.environ.get("DC_TRANSFER_PHONE", "+992987070941")
INSTAGRAM_URL = os.environ.get(
    "INSTAGRAM_URL",
    "https://www.instagram.com/donatex.ff?fqnt=dTl1MXQ0ajZuN3I=",
)
TIKTOK_URL = os.environ.get(
    "TIKTOK_URL",
    "https://www.tiktok.com/@abdullojon.america?_r=1&_t=ZT-9BgjLyZQTOw",
)

GAME_ICONS = {
    "8 Ball Pool": "https://is3-ssl.mzstatic.com/image/thumb/Purple113/v4/f2/7b/42/f27b4235-0c73-f2d6-8889-17d64970e8cd/AppIcon-0-0-1x_U007emarketing-0-0-0-7-0-85-220.png/512x512bb.png",
    "AFK Journey": "https://img.game8.jp/10116629/120257ae76fa2b692a366fb22620c5df.png/show",
    "Ace Racer": "https://dl.memuplay.com/new_market/img/com.netease.racerhmt.icon.2024-12-30-17-07-43.png",
    "Acecraft": "https://is1-ssl.mzstatic.com/image/thumb/Purple221/v4/f3/7c/5f/f37c5fba-c20e-883a-94d8-446d36544316/AppIcon-0-0-1x_U007emarketing-0-8-0-85-220.png/512x512bb.webp",
    "Age of Empire Mobile": "https://cdn.salla.sa/NDVOD/mOqtx3EyHdJaLEscerMpVSjVlT1jfOAyIrIUVzBV.png",
    "Age of Magic": "https://is4-ssl.mzstatic.com/image/thumb/Purple116/v4/e7/92/ec/e792ec25-1034-474b-dfa6-1a988bf8b690/AppIcon-1x_U007emarketing-0-7-0-85-220.png/512x512bb.webp",
    "Arena Breakout": "https://static.gg.in.th/files/gamestore/editor-images/202605/YtsZFDstCrlnkfFGyR9p4ChmevKjGGWIOeFbEH2l.png",
    "Arena Breakout: Infinite": "https://cdn.epinpay.com/image/ep/2025/11/category/arena-breakout-infinite-60.webp",
    "Arena of Valor (EU)": "https://www.kyytopup.web.id/_next/image?url=%2Fimages%2Flogo-games%2Farena-of-valor.png&w=1536&q=75",
    "Arena of Valor (ID)": "https://www.kyytopup.web.id/_next/image?url=%2Fimages%2Flogo-games%2Farena-of-valor.png&w=1536&q=75",
    "Arena of Valor (TH)": "https://www.kyytopup.web.id/_next/image?url=%2Fimages%2Flogo-games%2Farena-of-valor.png&w=1536&q=75",
    "Arknight: Endfield (Auto Via Login)": "https://is1-ssl.mzstatic.com/image/thumb/Purple211/v4/99/fc/ba/99fcba67-2a34-2873-8350-037cbf55f8ca/AppIcon-0-0-1x_U007emarketing-0-8-0-85-220.png/512x512bb.webp",
    "Asphalt 9: Legends": "https://is1-ssl.mzstatic.com/image/thumb/Purple116/v4/e7/32/cc/e732cc5b-0e21-0693-9018-d4244ce38d32/AppIcon-2x-4-85-220.png/512x512bb.png",
    "Astral Guardians: Cyber Fantasy": "https://cdn-www.bluestacks.com/bs-images/d9df307dff026a091c271cd25c904f9b.png",
    "Azur Lane": "https://is1-ssl.mzstatic.com/image/thumb/Purple221/v4/67/5d/7f/675d7f89-e56f-8894-3e46-a57d31c93604/AppIcon-0-0-1x_U007emarketing-0-7-0-85-220.png/512x512bb.png",
    "Badlanders": "https://arjangame.ir/665-large_default/badlanders-mobile.jpg",
    "Ballistic Hero VNG": "https://play-lh.googleusercontent.com/-kWePinvD_95UHJnInBoS-1KBYYKrwMTMp6zS9C59KnTBCsjBl6GqQ1g-9bfhi-ka0Sn7ime13G24ckJ1dLjWUo=s256-br30",
    "Be The King": "https://play-lh.googleusercontent.com/NGP4WNrwmc7tcH6U3rTVOQ0W7iHyHSWzcDkxTUbTbjI-_I5zOzeP2lPj2Frcg3Jr0fpweLtQbAKQz1u1y9on6Q=s256-br30",
    "Bigo Live": "https://cdn.epinpay.com/image/ep/2025/10/category/bigo-live-diamonds-33.webp",
    "Black Clover M (Asia)": "https://dl.memuplay.com/new_market/img/com.garena.game.bc.icon.2023-12-29-10-50-01.png",
    "Bleach: Soul Resonance (Americas)": "https://play-lh.googleusercontent.com/GguGHeUe0tZFjvPdVzll1dKQ2uyiIMNQU0xqXBifcsUPd2YOLCi1QhPKq4lRFNVvm_y7iW4NTk5JaHkDlA4JDRg=s256-br30",
    "Bleach: Soul Resonance (Europe)": "https://play-lh.googleusercontent.com/GguGHeUe0tZFjvPdVzll1dKQ2uyiIMNQU0xqXBifcsUPd2YOLCi1QhPKq4lRFNVvm_y7iW4NTk5JaHkDlA4JDRg=s256-br30",
    "Bleach: Soul Resonance (SEA)": "https://play-lh.googleusercontent.com/GguGHeUe0tZFjvPdVzll1dKQ2uyiIMNQU0xqXBifcsUPd2YOLCi1QhPKq4lRFNVvm_y7iW4NTk5JaHkDlA4JDRg=s256-br30",
    "Blood Strike": "https://www.arilstore.com/assets/img/icons/blood-strike-1785945498.png",
    "Blood Strike (Mena)": "https://www.arilstore.com/assets/img/icons/blood-strike-1785945498.png",
    "Bullet Echo": "https://is1-ssl.mzstatic.com/image/thumb/Purple221/v4/25/f7/d2/25f7d2fd-1a67-7f3f-9fb4-04c5efc7946c/AppIcon-0-0-1x_U007emarketing-0-11-0-85-220.png/512x512bb.png",
    "CATS: Crash Arena Turbo Stars": "https://play-lh.googleusercontent.com/JBjC3-ztV1LX8nT2sumjHZqPi97NOuKFhIJy6i7Z0NcGvZbXpP50mwFv7SguTeNMspC6Y4HmO2qAAATi65Rl1Q=s256-br30",
    "Call of Duty Mobile - Activision (IN)": "https://media.zid.store/cdn-cgi/image/w=1200,h=630,q=90/https://media.zid.store/d17406b9-7e45-411a-aa40-719b34321d63/b7af59ef-e1bf-4f92-b9fd-ff5d5de37c6c.png",
    "CapCut": "https://neon-plan-boost.lovable.app/assets/icon-capcut-CVML67h-.webp",
    "Captain Tsubasa: Ace": "https://play-lh.googleusercontent.com/H4yzwXgQOWbg1SyfclqgfdY2fPoPV524m_NtCnyP4NxnVQ2p3R1Bd7CubLAqj6D-_xWfYf-up9k7gTK1Pw9h=s256-br30",
    "Chamet": "https://yemencard.net/upload/121.webp",
    "Civilization: Eras & Allies": "https://play-lh.googleusercontent.com/8GDZEtGjNRN98QD5FZgMj5aTZWJa34YAKZpx_1q2GiksujlEYUw8LJiDige9PM-50HvrbWFH-nnlEADjsitiJJE=s256-br30",
    "Clash Of Plants": "https://play-lh.googleusercontent.com/bP9wEVyjwryZAxOhj-0UqMmZKzstPoLC6gRMfrKRaMs-dBr8HqqKLnHRaqmSibgrfWIRWngvxpLW3n8Nx-ONnA=s256-br30",
    "Conquer Online": "https://play-lh.googleusercontent.com/aEf0DEQVdOxvYTOaurPVmv-BCCSLF7O0Kt-fJK5a_bcCYHYHuA0lQiLAaW4AErbFBPIPJZzcCQNS8H2EFuYO=s256-br30",
    "Crossfire: Legend": "https://static.upoint.id/images/contents/crossfire_legend.png",
    "Crossout Mobile": "https://play-lh.googleusercontent.com/bt7JMYIJDQgQjkfGPCQomYgNbtNkkvME1xP1WuYouiDiia1BxNnQtq9esfUsTFFhA1H3OVl3j8_XICLkzBcakvM=s256-br30",
    "Crystal of Atlan": "https://media.allkeypay.com/media/PEqJ1nTrwo6d4PVkBRZ44.webp",
    "Dazz Live": "https://play-lh.googleusercontent.com/A3W6LhYBQFbwJrHHDdn-F9lJspW0wiDdQZr_OrYzc214RHUdB1sbLiTcoJhdaeu0sgidKfY2-H91TYG_jjmSkfQ=s256-br30",
    "Delta Force": "https://buycashgame.ru/wp-content/uploads/2025/09/icon_DeltaForce.png",
    "Destiny: Rising": "https://persshop.com/_next/image?url=%2Fcovers%2Ftopup_destiny_rising.webp&w=2048&q=75",
    "Devil May Cry: Peak of Combat": "https://is1-ssl.mzstatic.com/image/thumb/Purple221/v4/c2/91/16/c29116d2-391f-0da3-14fb-65aed69a90b9/AppIcon-0-1x_U007emarketing-0-8-0-85-220-0.png/512x512bb.png",
    "Dragon Nest M Classic (SEA)": "https://play-lh.googleusercontent.com/vxFcD3Ten9CyDfSzHuBaNi4R3yqMIawuWyNMDgz9vgxJfQ5NOiw0p6ANpbnnPEOt-dsB2qNdBjnLV2Gzg__dWOU=s256-br30",
    "Dragon Nest M Classic (TW/HK/MO)": "https://play-lh.googleusercontent.com/vxFcD3Ten9CyDfSzHuBaNi4R3yqMIawuWyNMDgz9vgxJfQ5NOiw0p6ANpbnnPEOt-dsB2qNdBjnLV2Gzg__dWOU=s256-br30",
    "Dragon Raja (SEA)": "https://api.duniagames.co.id/api/product/upload/image/15682858771731573284.png",
    "Dragonheir: Silent Gods": "https://play-lh.googleusercontent.com/3MLqOvrKT5vzvRyvhN-mYvnOMBCa3Vkv7i2jZaVtdM80L4MWuowNbJ8djcMAvyrr10WpKM4HQ-FgfjId2aTOHA=s256-br30",
    "Dream and Lethe Record": "https://play-lh.googleusercontent.com/qTiQmzX2cRvFsN-5Zkqztx-VopH5xqbxWtey8t8U_fUHxdRVPUf5cCFkiVm9EWurRYArswoEugod-KdMhJE_7W0=s256-br30",
    "Duet Night Abyss": "https://play-lh.googleusercontent.com/wNyltcXoUMKz7txb1KGz0MN4-B-HXv6-iVC6n39cry5FNukJxtoJyQ-sC-KMrg-CNO1a_Ed3r8AaUJNuHWGsjA=s256-br30",
    "Dunk City Dynasty": "https://is1-ssl.mzstatic.com/image/thumb/Purple211/v4/66/95/06/6695061b-a5ca-2f27-7d02-c9a2a12baeef/AppIcon-0-0-1x_U007emarketing-0-8-0-0-85-220.png/512x512bb.jpg",
    "Dynasty Heroes: Legend Samkok": "https://play-lh.googleusercontent.com/40Ky3ggi4vXfpc0GevxWnJ_xeJZuwpd8W3CeJUE1mJ56rV_lO__PGuTxQCaAQHpNGiHKUo4BUHjel7eVxaX4=s256-br30",
    "EAFC Mobile (ID)": "https://play-lh.googleusercontent.com/uT1JkXWK9pv1DWWOuVebnsbATHMZmhG4LUDkvoXne9H2MDF1im00_-U4taZPifIBpJ47sA0i8IoCh5aEVuUG5JI=s256-br30",
    "EAFC Mobile (KH)": "https://play-lh.googleusercontent.com/uT1JkXWK9pv1DWWOuVebnsbATHMZmhG4LUDkvoXne9H2MDF1im00_-U4taZPifIBpJ47sA0i8IoCh5aEVuUG5JI=s256-br30",
    "EAFC Mobile (MY)": "https://play-lh.googleusercontent.com/uT1JkXWK9pv1DWWOuVebnsbATHMZmhG4LUDkvoXne9H2MDF1im00_-U4taZPifIBpJ47sA0i8IoCh5aEVuUG5JI=s256-br30",
    "EAFC Mobile (SG)": "https://play-lh.googleusercontent.com/uT1JkXWK9pv1DWWOuVebnsbATHMZmhG4LUDkvoXne9H2MDF1im00_-U4taZPifIBpJ47sA0i8IoCh5aEVuUG5JI=s256-br30",
    "EVE Echoes": "https://play-lh.googleusercontent.com/f1bmRQE7Yvd_xvYZpulkJRHrlgYFB0qfIjWsX2edOSsU4-L8qtg2mXzXLSJB-wANjvA5gh_oWEO8ancqtMrIYA=s256-br30",
    "Eggy Party": "https://dl.memuplay.com/new_market/img/com.netease.eggypartyen.icon.2024-03-08-10-32-02.png",
    "Enhypen World": "https://play-lh.googleusercontent.com/1CsLndh7yAWiqwrxsrcZQXQRZ-iPaJZ6O1h47WxcdrHoldlLprEJ04w42vSQf_1Grd0MixzNEfqy7cnBnxDQkQ=s256-br30",
    "Ensemble Stars Music": "https://play-lh.googleusercontent.com/qdDvJfQ6E5-lKffUPoohxst-P9GJ8ghGQlhWATQXVt3IkVh6NAbS4YIM3D0OgPRK_m6gpqh9cCI0X9lfppFKgA=s256-br30",
    "Etheria Restart": "https://play-lh.googleusercontent.com/J0OdzAXwvOR3E4cp3ay-Ilmz31_kaN79O3pMtQ03IMf4ptA4YZLyUDAnFaWbB0E7GzitaR6kLWwpyHMmIuk2TTU=s256-br30",
    "FF BD": "/webapp/assets/free-fire-max.png",
    "FF BR": "/webapp/assets/free-fire-max.png",
    "FF EU": "/webapp/assets/free-fire-max.png",
    "FF LATAM": "/webapp/assets/free-fire-max.png",
    "FF MENA": "/webapp/assets/free-fire-max.png",
    "FF MY/SG": "/webapp/assets/free-fire-max.png",
    "FF PH": "/webapp/assets/free-fire-max.png",
    "FF SG": "/webapp/assets/free-fire-max.png",
    "FF TH": "/webapp/assets/free-fire-max.png",
    "FF TW": "/webapp/assets/free-fire-max.png",
    "FF VN": "/webapp/assets/free-fire-max.png",
    "FF Инд": "/webapp/assets/free-fire-max.png",
    "FF СНГ": "/webapp/assets/free-fire-max.png",
    "FRAG Pro Shooter": "https://play-lh.googleusercontent.com/18DPC2VKF_9bYqnvcf2Jbas4W4pah5-mJ0rJ4lpx-7ACShqJLWRi3u-aIo-xduaYzesL5EmJK7i0yYa4fi_k=s256-br30",
    "Farlight 84": "https://is1-ssl.mzstatic.com/image/thumb/Purple211/v4/41/03/28/4103286b-3e18-3557-0f6e-bee6e8a32b64/AppIcon-0-0-1x_U007emarketing-0-8-0-85-220.png/512x512bb.png",
    "Fashion Dream": "https://play-lh.googleusercontent.com/cLRMYHVgHGScBaN81aarEHYPl5xhRf0V90BuSpWPUZsDqTEyZS7rs4jSyphQEAc4FtnkwkiZi2KdH4wBZ21d=s256-br30",
    "Football Master 2": "https://play-lh.googleusercontent.com/8jvY5SWCsOPwXR8H-WD86gET-1Nm3EWY80zRT0_UurXuMOQpQ6-OmqwfDdNRUKpyixDQ2Xf8iG1hM3iFkgCggz8=s256-br30",
    "Garena Delta Force (Indonesia)": "https://buycashgame.ru/wp-content/uploads/2025/09/icon_DeltaForce.png",
    "Garena Delta Force (MY)": "https://buycashgame.ru/wp-content/uploads/2025/09/icon_DeltaForce.png",
    "Garena Speed Drifters": "https://play-lh.googleusercontent.com/u4HdUp8YR4m3T7hG_ntWYR41rI3ZQqKg2NbbWaxyWj0sCv_IfqLbAzjG0DpOVsGhyZJv3-kzSe7whglBUw1bHJc=s256-br30",
    "Garena Undawn (Global)": "https://play-lh.googleusercontent.com/yUEGrnalpru2fAANkR_jzbNS22bPP1F0dnT70sPoMiC1Yv5fz_eparahw1B7noL7NiddLlkOkrusLtELtKT_xg=s256-br30",
    "Garena Undawn (Indonesia)": "https://play-lh.googleusercontent.com/yUEGrnalpru2fAANkR_jzbNS22bPP1F0dnT70sPoMiC1Yv5fz_eparahw1B7noL7NiddLlkOkrusLtELtKT_xg=s256-br30",
    "Garena Undawn (SG)": "https://play-lh.googleusercontent.com/yUEGrnalpru2fAANkR_jzbNS22bPP1F0dnT70sPoMiC1Yv5fz_eparahw1B7noL7NiddLlkOkrusLtELtKT_xg=s256-br30",
    "Genshin Impact (Auto Via Login)": "https://cdn.files.salla.network/homepage/240140947/a71921fe-1de2-4344-b4d0-6f34adb573ee.webp",
    "Genshin Impact (Global)": "https://cdn.files.salla.network/homepage/240140947/a71921fe-1de2-4344-b4d0-6f34adb573ee.webp",
    "Ghost Story: Love Destiny": "https://play-lh.googleusercontent.com/WEdNosMDBTiA8zTIAGrzjk6ithiULRTyvQi18i0ManTnOlGxfny1Cx8akP3dwK7JCQQOu2VXnGqX4AWZ6h6acsQ=s256-br30",
    "Goddess of Victory: NIKKE": "https://pgem.shop/_next/image?url=%2Fimages%2Fgames%2Fnikke-top-up.webp&w=2048&q=75",
    "Golden Spatula": "https://play-lh.googleusercontent.com/l7RBr0YFThkRf6sySBdqvpJpV1tUxFI2398zjOGuP8n4AN8v-uYbSFGhcfrHfLBqBqqbs9CVlLp78_vGPTaZ1Q=s256-br30",
    "Growtopia": "https://cdn.growtopiawiki.com/uploads/7/74/Growtopia.png?20141203135150",
    "Guns of Glory": "https://play-lh.googleusercontent.com/cII5BvrG8aTmWQ9K3cYtlQTC8HNYKDarmvNks5JQzMvWlrusf4uGLlzD7QjvoEfxDeZ3OI6pSF4R_Cf0QoRV3D8=s256-br30",
    "Hago Diamonds": "https://play-lh.googleusercontent.com/igfqct-vw4I87Eg9Mi8CMbQh2XzOyFfE551sFdx2ZOcz0Bv-ZBX9ChXRdBvrqJq8QUcE8nZOhMRjReiNy1CeQw=s256-br30",
    "Haikyu!! Fly High (SEA)": "https://play-lh.googleusercontent.com/HbrLLRg2m7bCxoFqNeO9qvsYhyQ4NtwCd7xAGE7PDCt8k8PzlK7hdi9d12cpm-dZwz7T47Y_xKW8M84AXf-3xg=s256-br30",
    "Harry Potter: Magic Awakened": "https://gameplay.id/app/assets/uploads/brand/1768769024_47e4b6ee05797753d36c.png",
    "Hatsune Miku: Colorful Stage": "https://play-lh.googleusercontent.com/Y9yBy-25QmwMeWPWMQWislfKJFKl5hZJHdqTuZkRR8gI9iVzRmxHPOx4z2RC7rx62C9AWeVuD7T4AfBvdIvAvQ=s256-br30",
    "Heartopia": "https://play-lh.googleusercontent.com/FtZNAkKn4faEpRU4UjtRRUk-aQP5zwiN1Kg4FzAcQBN7S8-PfDo7ODxmjaPlMu3HOFJ6-1WhzXxwKA6q1bOw=s256-br30",
    "Heaven Burns Red": "https://play-lh.googleusercontent.com/HPqajcNJwKlVMxZgig0J_US0aBJcJB1C6mFy8pENBSHGLHhsWCbbRdFJDLmim098Q7mdoPe1cXgX4Q6rs6ITaHc=s256-br30",
    "Hero Clash": "https://play-lh.googleusercontent.com/QcK92YDvZvO12YdulWud9qkTmVyVXKWKZKEfzgsEqo1SAzsK5k-m5OjOiqXazJjsvz3wCG42oSu4sKYN1Qnpzg=s256-br30",
    "Heroes Evolved": "https://play-lh.googleusercontent.com/dNgP7XNUcBI-bQzTjbX31kOGJNq--LZqjCjUIBi9piUl34KC_xyv1d5z0fpzisEFIudd7rlvnrq7wAMuYi9N=s256-br30",
    "Honkai Impact 3rd (Asia)": "https://play-lh.googleusercontent.com/hTMlfgsf_lKP7URBWrrdpoqL_AhXwuvIbeU-5Gn2R-8RE58z4Y28mfduo6MkfEBpP7Mtef7bnrXo5R9g1puG=s256-br30",
    "Honkai Impact 3rd (ID)": "https://play-lh.googleusercontent.com/hTMlfgsf_lKP7URBWrrdpoqL_AhXwuvIbeU-5Gn2R-8RE58z4Y28mfduo6MkfEBpP7Mtef7bnrXo5R9g1puG=s256-br30",
    "Honkai Impact 3rd (KH)": "https://play-lh.googleusercontent.com/hTMlfgsf_lKP7URBWrrdpoqL_AhXwuvIbeU-5Gn2R-8RE58z4Y28mfduo6MkfEBpP7Mtef7bnrXo5R9g1puG=s256-br30",
    "Honkai Impact 3rd (MY)": "https://play-lh.googleusercontent.com/hTMlfgsf_lKP7URBWrrdpoqL_AhXwuvIbeU-5Gn2R-8RE58z4Y28mfduo6MkfEBpP7Mtef7bnrXo5R9g1puG=s256-br30",
    "Honkai Impact 3rd (PH)": "https://play-lh.googleusercontent.com/hTMlfgsf_lKP7URBWrrdpoqL_AhXwuvIbeU-5Gn2R-8RE58z4Y28mfduo6MkfEBpP7Mtef7bnrXo5R9g1puG=s256-br30",
    "Honkai Impact 3rd (SG)": "https://play-lh.googleusercontent.com/hTMlfgsf_lKP7URBWrrdpoqL_AhXwuvIbeU-5Gn2R-8RE58z4Y28mfduo6MkfEBpP7Mtef7bnrXo5R9g1puG=s256-br30",
    "Honkai Impact 3rd (TH)": "https://play-lh.googleusercontent.com/hTMlfgsf_lKP7URBWrrdpoqL_AhXwuvIbeU-5Gn2R-8RE58z4Y28mfduo6MkfEBpP7Mtef7bnrXo5R9g1puG=s256-br30",
    "Honkai: Star Rail (Global)": "https://is1-ssl.mzstatic.com/image/thumb/Purple211/v4/fd/65/dc/fd65dc18-c4b6-7b64-8266-a423f3f113e0/AppIcon-0-0-1x_U007emarketing-0-8-0-85-220.png/512x512bb.jpg",
    "Honor of Kings": "https://is1-ssl.mzstatic.com/image/thumb/Purple221/v4/6c/9c/73/6c9c73a3-b6d8-6f98-a7c2-00de2f82a240/AppIcon-1x_U007emarketing-0-7-0-85-220-0.png/512x512bb.jpg",
    "IMO": "https://play-lh.googleusercontent.com/h3meMiv4LWSpzYC3Dpi0MFIXMJI1sQSG_QUDXNCxjVhlUxEAyquWqUVlPk3NL6N33kKEjoMcUfOjjiZeXg8TfCE=s256-br30",
    "Identity V": "https://pgem.shop/_next/image?url=%2Fimages%2Fgames%2Fidentity-v-top-up.webp&w=640&q=75",
    "Idol Party": "https://play-lh.googleusercontent.com/akcSBboESburBnYYZBBnjzYNxok88UKhO6BEhb-zqEZlt9upGXqbyiXYVYcwOOCs2C5NkhEcE_6wNHVu4lzF=s256-br30",
    "Infinite Lagrange": "https://play-lh.googleusercontent.com/J6nCBnFgeVole3RZ79rBg7EgsVTxFUfo2w0PBinsRSjmjMW1eaMNVkd-CW_z_GTyzQ=s256",
    "Jaco": "https://play-lh.googleusercontent.com/ZBI1VqtTaHB4rJWnRp3DSSeoy8sEgjsf4X50KKixO1eUEB9kVt5xUghTsuKWQUY9GV1H4ZwsphXPr1BjE5ojyg=s256-br30",
    "Jade Dynasty: New Fantasy": "https://play-lh.googleusercontent.com/XF_WFNiad-oljgiV72d97ylZtEYgO9BhboLK_OLwOGGQj6LtFbF0A16DqCglF_ea1s0hiQS3nkOOyMbIViB2Bg=s256-br30",
    "Journey Renewed: Fate Fantasy": "https://play-lh.googleusercontent.com/XF_WFNiad-oljgiV72d97ylZtEYgO9BhboLK_OLwOGGQj6LtFbF0A16DqCglF_ea1s0hiQS3nkOOyMbIViB2Bg=s256-br30",
    "Kings Choice (SEA)": "https://play-lh.googleusercontent.com/Dmdruh7RUeZ8rgFNzMJ6T342W3xm6aucHdIiIguOLF-G2lYAMRpcb3B9_8inxCZxyRQe55YZxSeC-yUZWF99=s256-br30",
    "Kingshot": "https://www.centurygames.com/wp-content/uploads/2025/04/kingshot-logo.png",
    "Knives Out": "https://cdn.donatov.net/cover/good-264-1767947975.webp",
    "Kuroko Street Rivals": "https://play-lh.googleusercontent.com/2oOhZbG4Tb8QIXkjCPLK5t0AjBVPrcswYxhc9a8qrB_kV_B4ki8p9sdK1Pac_z8842uI9TMNY4KfsID7Lo0r=s256-br30",
    "League of Legends (ID)": "https://getandroid.ir/uploads/posts/2020-04/1588195358_league-of-legends-wild-rift-icon.png",
    "League of Legends (KH)": "https://getandroid.ir/uploads/posts/2020-04/1588195358_league-of-legends-wild-rift-icon.png",
    "League of Legends (MY)": "https://getandroid.ir/uploads/posts/2020-04/1588195358_league-of-legends-wild-rift-icon.png",
    "League of Legends (PH)": "https://getandroid.ir/uploads/posts/2020-04/1588195358_league-of-legends-wild-rift-icon.png",
    "League of Legends (SG)": "https://getandroid.ir/uploads/posts/2020-04/1588195358_league-of-legends-wild-rift-icon.png",
    "League of Legends (TH)": "https://getandroid.ir/uploads/posts/2020-04/1588195358_league-of-legends-wild-rift-icon.png",
    "League of Legends (VN)": "https://getandroid.ir/uploads/posts/2020-04/1588195358_league-of-legends-wild-rift-icon.png",
    "Legacy of Discord - FuriousWings": "https://play-lh.googleusercontent.com/moeIV2ndtQGi1Zy5fiD0atLH7MhPXiKYaUdyO589ml_V11RPq5O2E_yqprnlQzXyLld08nxoAC-eTbsg0BQe=s256-br30",
    "Legend of Neverland": "https://play-lh.googleusercontent.com/cl9yr_Ez5fsQOYFUEE496zSV7QG7JmZbf7zYp4MxVxtF28Ncmmc7tLCyx1fpDi3opefMjp3jo6njeTRgEowQ3oY=s256-br30",
    "Legend of Neverland (NAEU)": "https://play-lh.googleusercontent.com/cl9yr_Ez5fsQOYFUEE496zSV7QG7JmZbf7zYp4MxVxtF28Ncmmc7tLCyx1fpDi3opefMjp3jo6njeTRgEowQ3oY=s256-br30",
    "Legend of the Phoenix": "https://play-lh.googleusercontent.com/_2roJjqb_Lvs3r16GvvTHLoYOtcHwqdu9g-qgPCvhooqiMwhwuGLM-2mfH4wRCm87yiF3-2V_xsRS6iEYMmkupg=s256-br30",
    "Legends of Runeterra (Indonesia)": "https://play-lh.googleusercontent.com/Snrqky9RhNHdWbL1KivZWLYA_17C4Ac9LQ0kKMJJsrZ4EPvrdRS778T1W9Qc_8bClmEnzqD3oLrOMcLZg28SrpQ=s256-br30",
    "Legends of Runeterra (Malaysia)": "https://play-lh.googleusercontent.com/Snrqky9RhNHdWbL1KivZWLYA_17C4Ac9LQ0kKMJJsrZ4EPvrdRS778T1W9Qc_8bClmEnzqD3oLrOMcLZg28SrpQ=s256-br30",
    "Legends of Runeterra (Philippines)": "https://play-lh.googleusercontent.com/Snrqky9RhNHdWbL1KivZWLYA_17C4Ac9LQ0kKMJJsrZ4EPvrdRS778T1W9Qc_8bClmEnzqD3oLrOMcLZg28SrpQ=s256-br30",
    "Legends of Runeterra (Singapore)": "https://play-lh.googleusercontent.com/Snrqky9RhNHdWbL1KivZWLYA_17C4Ac9LQ0kKMJJsrZ4EPvrdRS778T1W9Qc_8bClmEnzqD3oLrOMcLZg28SrpQ=s256-br30",
    "Legends of Runeterra (Thailand)": "https://play-lh.googleusercontent.com/Snrqky9RhNHdWbL1KivZWLYA_17C4Ac9LQ0kKMJJsrZ4EPvrdRS778T1W9Qc_8bClmEnzqD3oLrOMcLZg28SrpQ=s256-br30",
    "Legends of Runeterra (United States)": "https://play-lh.googleusercontent.com/Snrqky9RhNHdWbL1KivZWLYA_17C4Ac9LQ0kKMJJsrZ4EPvrdRS778T1W9Qc_8bClmEnzqD3oLrOMcLZg28SrpQ=s256-br30",
    "Life Makeover (Global)": "https://play-lh.googleusercontent.com/nKNQitcqpFTeRzD-x03nNW14NqsRQ85YNpUYRr3QpDj3OTDWBg3zDUxHU2I_yDth6ApLzh3KvbYK61o4DPWMhg=s256-br30",
    "LifeAfter": "https://cdn.fireflazz.com/seni-game/demo-arena-lifeafter-v2.webp",
    "Likee": "https://cdn.salla.sa/xvmYY/5TI09VAnhx1tjV0BZArTOVQwPf8HL1nj97yrhHCA.jpg",
    "Lineage W": "https://play-lh.googleusercontent.com/VvwlyO5rMOgeedcbDmvBQv-vDoCeHqxBdSHqTrA3xUZAEuRcAwTBznrJBwkj3_xvhUTkLJ4D98RT1fZTtu8W=s256-br30",
    "Lineage2M": "https://play-lh.googleusercontent.com/5sVdvmtchQ2F_-mGlZnwJRdK_2nMOpZjHiLShfqI0oCZk5RWg1PK-t5TJdgbfSJ3bDn2rwVeTqOvF_37OLNCxA=s256-br30",
    "Lita": "https://play-lh.googleusercontent.com/uTEmKPZU6_NM47_7OB3oHPNij9Vmw-CsUB9piLRQxYihzkiTDahfj66shpFmtYh7-zwdd_oC41z77JgC43Bz=s256-br30",
    "Livu Coins": "https://play-lh.googleusercontent.com/CM2ukI9O7tsAIIQ7pqT7Azn_YQKY6WVp3D84z5L7IANxP0QBf4lXx9e1dnVc1_bAI6K0vpWqcT9gaXNIXrWLzQ=s256-br30",
    "Lords Mobile": "https://cdn.epinpay.com/image/ep/2025/1/category/lords-mobile-12.webp",
    "Love Nikki": "https://play-lh.googleusercontent.com/7uLMqhb__clOgh0nVDDO2KJkvKmTPbMBmI-M5CVHhMkRxTiXCCe2a6VAplCI-2u24X5zN4R9hldQu1aSd8BowHA=s256-br30",
    "Love and Deepspace": "https://is1-ssl.mzstatic.com/image/thumb/Purple221/v4/ab/2c/05/ab2c0519-4b4e-02f2-d790-574e98b7907e/AppIcon-0-0-1x_U007emarketing-0-8-0-85-220.png/512x512bb.png",
    "Love and Deepspace (Auto Via Login)": "https://is1-ssl.mzstatic.com/image/thumb/Purple221/v4/ab/2c/05/ab2c0519-4b4e-02f2-d790-574e98b7907e/AppIcon-0-0-1x_U007emarketing-0-8-0-85-220.png/512x512bb.png",
    "Ludus Strategy PVP": "https://play-lh.googleusercontent.com/DbnSgl-ou7WzVsDQkOY7Yi1_3OScfEUh39DL50fSIrMb2ywuB_FyN23nPTfPKL302q1lxHIldP9e0qp-RRJvcg=s256-br30",
    "MICO Coins": "https://play-lh.googleusercontent.com/yDnZiDBszKXpyMqqcmONJrfv7u6UGrakxlPSqHrm2fICQAge3caJC59i27Go7k_ORi_UQ6ASYav-cNujPE4BHg=s256",
    "MU Ascension": "https://play-lh.googleusercontent.com/luPRvZ8yPiTFAFpDgAAAeiJnUSAQ-9HSYJJ3ji1LVIMrL_5yufTKpV94G1oTVSoEThQRAcvlCsikscl6iLVkWA=s256-br30",
    "MU ORIGIN 3 Asia": "https://play-lh.googleusercontent.com/Oi00ld5-CbS-fP-WTQvUkMEmnJ2e0__G0DJctVDec8sGo_I8Xsd9dCxPoWXbdkfj7SuPLNaaWsXD8Xk1PrGyIw=s256",
    "Magic Chess Go Go (Global)": "https://play-lh.googleusercontent.com/uCoc4iwT9cUgSVK47Zvnbyu10JDudzNnNkky-9Suz5tU9cGKat4A23YfohUXzJh-wnlz0VWI-G58XHBFM2OBdA=s256",
    "Magic Chess Go Go (Indonesia)": "https://play-lh.googleusercontent.com/uCoc4iwT9cUgSVK47Zvnbyu10JDudzNnNkky-9Suz5tU9cGKat4A23YfohUXzJh-wnlz0VWI-G58XHBFM2OBdA=s256",
    "Magic Chess Go Go (Malaysia)": "https://play-lh.googleusercontent.com/uCoc4iwT9cUgSVK47Zvnbyu10JDudzNnNkky-9Suz5tU9cGKat4A23YfohUXzJh-wnlz0VWI-G58XHBFM2OBdA=s256",
    "Magic Chess Go Go (RU)": "https://play-lh.googleusercontent.com/uCoc4iwT9cUgSVK47Zvnbyu10JDudzNnNkky-9Suz5tU9cGKat4A23YfohUXzJh-wnlz0VWI-G58XHBFM2OBdA=s256",
    "MangaToon - Read Comics Novel": "https://play-lh.googleusercontent.com/twLcvROtMsx-MIGdT4CUTmlarMmeS1LZJfl90eL64iskTJ8p_CnxcECKkCNJn7crvs6_KKZzzb2mpoqaI9ojGA=s256-br30",
    "MapleStory M": "https://play-lh.googleusercontent.com/X2kbYjVmGFSiaashu0IJNDrIr0kAowd_GM78rkN4z8XN_tI4dLD_FNHoA9GZi24pT1zoKeWc-wZffLo8DNzs=s256",
    "Marvel Duel": "https://play-lh.googleusercontent.com/GrJ98v-AeUYyTs_GM5GbRufK8uqy8lKR0kITLZkYxXWqxhrrRl-ck14_P1DrwpA0NEaLkSQtstoJmpgXrQPI_Q=s256-br30",
    "Marvel Rivals": "https://cdn2.steamgriddb.com/icon_thumb/9f648b75489aa3215259f0df0be7312a.png",
    "Mecha Break": "https://cerebral-overload.com/wp-content/uploads/2024/06/Mecha-Break.png",
    "Metal Slug Awakening (SEA)": "https://play-lh.googleusercontent.com/us3WDrKGmvYGXVXyL2vIDvfaFAbncqEhNvi38Udes9v7LR_1_PAJ6JvIhFPO1B-geZHB67ifviKdG1-dUL4y3vk=s256",
    "Migo Live": "https://play-lh.googleusercontent.com/oNqaNpmR0Gkmrp08WuVgij70VMUboZ2fYJlf9kQ1uA-9TgVmcsPu4MhiVaHB9mo-1X_L38zmwkUW-KdecEoY_vY=s256",
    "Mirage: Perfect Skyline": "https://play-lh.googleusercontent.com/heZzfgVXZklaMDEFK8iLHfGwB-FKxNqLaLpiLxTc9cUYcQOvJ-gOXGhddq-6XcNeKtlwexpCkRtcmeu91flm-Q=s256-br30",
    "Mobile Legends (Brazil)": "https://play-lh.googleusercontent.com/F9cgJKcHDpODaCSGVMYjQMuCp3Bh8ithjTmfotUTRqXe_7jMZM81lrlxo6RAz9vroK8=s256",
    "Mobile Legends (Exclusive)": "https://play-lh.googleusercontent.com/F9cgJKcHDpODaCSGVMYjQMuCp3Bh8ithjTmfotUTRqXe_7jMZM81lrlxo6RAz9vroK8=s256",
    "Mobile Legends (Global)": "https://play-lh.googleusercontent.com/F9cgJKcHDpODaCSGVMYjQMuCp3Bh8ithjTmfotUTRqXe_7jMZM81lrlxo6RAz9vroK8=s256",
    "Mobile Legends (Indonesia)": "https://play-lh.googleusercontent.com/F9cgJKcHDpODaCSGVMYjQMuCp3Bh8ithjTmfotUTRqXe_7jMZM81lrlxo6RAz9vroK8=s256",
    "Mobile Legends (Malaysia)": "https://play-lh.googleusercontent.com/F9cgJKcHDpODaCSGVMYjQMuCp3Bh8ithjTmfotUTRqXe_7jMZM81lrlxo6RAz9vroK8=s256",
    "Mobile Legends (Philippines)": "https://play-lh.googleusercontent.com/F9cgJKcHDpODaCSGVMYjQMuCp3Bh8ithjTmfotUTRqXe_7jMZM81lrlxo6RAz9vroK8=s256",
    "Mobile Legends (RU)": "https://play-lh.googleusercontent.com/F9cgJKcHDpODaCSGVMYjQMuCp3Bh8ithjTmfotUTRqXe_7jMZM81lrlxo6RAz9vroK8=s256",
    "Mobile Legends (Singapore)": "https://play-lh.googleusercontent.com/F9cgJKcHDpODaCSGVMYjQMuCp3Bh8ithjTmfotUTRqXe_7jMZM81lrlxo6RAz9vroK8=s256",
    "Mobile Legends (Special)": "https://play-lh.googleusercontent.com/F9cgJKcHDpODaCSGVMYjQMuCp3Bh8ithjTmfotUTRqXe_7jMZM81lrlxo6RAz9vroK8=s256",
    "Mobile Legends (Turkey)": "https://play-lh.googleusercontent.com/F9cgJKcHDpODaCSGVMYjQMuCp3Bh8ithjTmfotUTRqXe_7jMZM81lrlxo6RAz9vroK8=s256",
    "Mobile Legends (United States)": "https://play-lh.googleusercontent.com/F9cgJKcHDpODaCSGVMYjQMuCp3Bh8ithjTmfotUTRqXe_7jMZM81lrlxo6RAz9vroK8=s256",
    "Mobile Legends: Adventure": "https://cdn.now.gg/apps-content/com.moonton.mobilehero/icon/mobile-legends-adventure.png",
    "Modern Strike Online": "https://play-lh.googleusercontent.com/HwwwZypetLfttJGNmEjVX3Bb0YpOj9GU75ENsHHTwYHLIlHNR1QfnkoOzsfoSwvAVIHAQzTF_XNVx75CszfbzPo=s256",
    "Modern Warships: Naval Battles": "https://play-lh.googleusercontent.com/CbJIZbma9S7zhK6PYYcYMwnoGWPY9WgOTYi1tEPl7APVmRuZGKVQRKXi4_TY_RuhWxa43JrM6gYAO29PuFHXuWQ=s256",
    "Mongil: Star Dive (Auto Via Login)": "https://play-lh.googleusercontent.com/wLsarVh8SzjFRyaJQLO-LspghFofkwqNFjXsFSy-tLay4HB-IOtVeAhqQbBSj5JeWjot581oFkdawPRtbDnp=s256",
    "My Singing Monsters": "https://play-lh.googleusercontent.com/GR6KDIyH7oaG4mFEOfGY9iKHiDl-VLPETlKtny12m0jgn3I5_zX8dh8qsbRu3ZWBtg=s256",
    "Neverness to Everness (Auto Via Login)": "https://play-lh.googleusercontent.com/TGl3DdDbi4hty6ooOhEvv_2s5tkpGLbL6derP8y5hK-_Bw--Ve375b08ba9HHQ9ueRpoQ9oye1T_T24BJriLUmw=s256-br30",
    "Nimo TV": "https://play-lh.googleusercontent.com/h3meMiv4LWSpzYC3Dpi0MFIXMJI1sQSG_QUDXNCxjVhlUxEAyquWqUVlPk3NL6N33kKEjoMcUfOjjiZeXg8TfCE=s256-br30",
    "Once Human": "https://oncehuman.site/lander/games-oncehuman/logo.png",
    "Onmyoji Arena": "https://play-lh.googleusercontent.com/9Q_fxr4mZhHoYQyYriRtHJt2-KbWDSD8jdwy25C916x6QKCkOIgvcl87VPMcIQZGnPblhT1rEcWuGCMcJy4uxhI=s256-br30",
    "Overmortal Idle (Global)": "https://play-lh.googleusercontent.com/fD2uXCxootc8XpK9QqwfG9G8zNKH1yjzYdbPI7UD8fZYDtHEPH7dMagBXh1Vjfs2cEuRLcgyzluu0j6w7gbNrw=s256-br30",
    "Overmortal Idle (SEA)": "https://play-lh.googleusercontent.com/fD2uXCxootc8XpK9QqwfG9G8zNKH1yjzYdbPI7UD8fZYDtHEPH7dMagBXh1Vjfs2cEuRLcgyzluu0j6w7gbNrw=s256-br30",
    "Oxide Survival Island": "https://play-lh.googleusercontent.com/angXGBMMY51cmjEacSarq1uV5Olbui9cCQr9BaRNpGcRNv1JrK0Y0JRRq5KqD1pT7jjgWYO1p6BFNlgmME-O=s256-br30",
    "PUBG Mobile (Auto)": "https://upload.wikimedia.org/wikipedia/commons/2/2f/Icon_PUBGM.jpg",
    "PUBG Mobile (Manual)": "https://upload.wikimedia.org/wikipedia/commons/2/2f/Icon_PUBGM.jpg",
    "PUBG Mobile (Reserve)": "https://upload.wikimedia.org/wikipedia/commons/2/2f/Icon_PUBGM.jpg",
    "PUBG: New State": "https://play-lh.googleusercontent.com/sZ2d6_SNtbzGF-LUsIhGqxnqceEphqIv5cThn7v_kuhfKjJD3lCDhMhdyYL0OwvK4HZj56IuHLyR_SvCBIgwndQ=s256-br30",
    "Path to Nowhere": "https://play-lh.googleusercontent.com/ZnYy6QxhRiX01XfsTcoyJwbc-XQhWu13VegUWKSuUPnwH2XJPsZRbNIgYeqna6ERLxupgQlbCrtVonJ5Rc-h6vU=s256-br30",
    "Pixel Gun 3D": "https://play-lh.googleusercontent.com/1bpPoAURFISDh7KGmHRLnsirYIBahntg2_k2hQg2psKlnRV-SX5ZEZt1NPVJXwO4HxS29aMfi3BmSL7g8UTpMA=s256-br30",
    "Poppo Live": "https://play-lh.googleusercontent.com/uxMEM4LC3Z-HMeReIkBNZ1wlpxRcBkwOZ-xIRH2IxsuNmezceugiPWOANSipi2JKXrIfVhSPaN4RPreWhJnX6A=s256-br30",
    "Project Entropy": "https://play-lh.googleusercontent.com/U9bmFzR--zlexANRz68MafWh1KeCFXInLc6zVkVHn15FIV5gxOdYscj6vmC-FB3kctbn8_dbMXMQWEjH5BLC3Z4=s256-br30",
    "Punishing: Gray Raven": "https://www.arilstore.com/assets/img/icons/punishing-gray-raven-1785670042.png",
    "Puzzles & Survival": "https://play-lh.googleusercontent.com/ummlqp5oiU1hRPrz9pt-XYFhbMIITY_b-viFnnMu-RgtdH--uFrcFoEEGrXpRrOTVf94f8GCDQwEK-VBln18=s256-br30",
    "Racing Master (LATAM)": "https://play-lh.googleusercontent.com/4o-PjYZemP3rIoC1tqO7Xy534utcQbyKTmy7Rov8r7MJGhHGV46TZXVj0qyqRHjNsrKdnqOdOI6UYu7yUQ-uIQ=s256-br30",
    "Racing Master (SEA)": "https://play-lh.googleusercontent.com/4o-PjYZemP3rIoC1tqO7Xy534utcQbyKTmy7Rov8r7MJGhHGV46TZXVj0qyqRHjNsrKdnqOdOI6UYu7yUQ-uIQ=s256-br30",
    "Ragnarok Crush": "https://play-lh.googleusercontent.com/nm5Y9aGGUTnLZn9mIE6PFY-zs58c3XvAMm5YmRGFl8mSVDGdkvyivu6TgoFGSLQdL5KfJPasKqb6LNKwRwgGPA=s256-br30",
    "Ragnarok Idle Adventure Plus": "https://play-lh.googleusercontent.com/8SCSJRsqjY_IVjReG9R-R-SfANT6V_uSIhgEro5HOzUfv07gODIAbkF_sOP7pEdGHVASbcl8mDVFWzrXULLG0gk=s256-br30",
    "Ragnarok M: Classic (SEA)": "https://play-lh.googleusercontent.com/3cCoyAWCrq8zn_P50kP2VWxQzexj3bh0cAftcZgpsPTyenZ9xvn-rVkLpAAga3FSczSMNGw0vnu4qlsz2y-6i4o=s256-br30",
    "Ragnarok M: Eternal Love (SEA)": "https://play-lh.googleusercontent.com/CI_w0g2Ou85eoR9H9D2AQnFzSNC3olR4qcstyr-mbsk9sW5eo_nryZd1Y55cGLuu3g5GHwdp-IJypGabB63T=s256-br30",
    "Ragnarok Origin": "https://i.17173cdn.com/0561y4/YWxqaGBf/gamebase/game-cover-square/DIVmNVbpaCnfsDA.png",
    "Ragnarok Tactics": "https://play-lh.googleusercontent.com/nm5Y9aGGUTnLZn9mIE6PFY-zs58c3XvAMm5YmRGFl8mSVDGdkvyivu6TgoFGSLQdL5KfJPasKqb6LNKwRwgGPA=s256-br30",
    "Ragnarok X: Next Generation": "https://play-lh.googleusercontent.com/ploZ5a-s3_jIA4zi-9oICMasgnmKevk_8_GpO_bK2X4g9ejrmJi7GGezdfn06uBYwTnaPdWs3RMWpvOaUqygYA=s256-br30",
    "Ragnarok: The Lost Memories": "https://play-lh.googleusercontent.com/CI_w0g2Ou85eoR9H9D2AQnFzSNC3olR4qcstyr-mbsk9sW5eo_nryZd1Y55cGLuu3g5GHwdp-IJypGabB63T=s256-br30",
    "Rainbow Six Mobile (Global)": "https://play-lh.googleusercontent.com/ToIBUUKye6KvvzgqS__jJpTygpHJBwNjeDgwJtFZEULzu0f0wDmG6fHe6hyG03ZLYEKqnLAV_QuNtCpVSZV3=s256-br30",
    "Rainbow Six Mobile (SG)": "https://play-lh.googleusercontent.com/ToIBUUKye6KvvzgqS__jJpTygpHJBwNjeDgwJtFZEULzu0f0wDmG6fHe6hyG03ZLYEKqnLAV_QuNtCpVSZV3=s256-br30",
    "Realms of Pixel": "https://dl.memuplay.com/new_market/img/com.realmsofpixel.ng.icon.2025-01-24-19-42-13.png",
    "Rememento: White Shadows": "https://cdn.ditusi.co.id/storage/games/01JZQ74N749H5VVS1P650N28KR-small.webp",
    "Revelation: Infinite Journey": "https://storage.qoo-img.com/game/12508/0Eyvctu7FLhdOf7I7b1XpP6y4nGdNC9D.png",
    "SUGO: Online Chat Party": "https://play-lh.googleusercontent.com/D81CX9WcYfG8lyqVh7pml2mG6KrGXHCiXiqACktAj0CCgd0mbV-wQ3q1iNy1CW6CQai6SJDaROK_X6Ej6_-IAg=s256-br30",
    "Sausage Man": "https://is1-ssl.mzstatic.com/image/thumb/Purple211/v4/cf/78/f6/cf78f6cd-4cdc-c70f-af72-6b69f0ee3929/AppIcon-0-0-1x_U007emarketing-0-8-0-85-220.png/512x512bb.jpg",
    "Sawa Play": "https://play-lh.googleusercontent.com/H0F7jsUI7N-8bTfMHZ8Sni0fQzj3hjsxk72BnTv_WdVphu25R6g8lJrHYLiMdWrzJ7b7VcUbYZ5oD685fS6myw=s256-br30",
    "Shining Nikki": "https://play-lh.googleusercontent.com/OB883CxCjWzzkf6C6kgPK-bU4iStPOp4nQMHPdxc0MnhMS7Xb-RmJSd3Tv9uHDOdE14ImMXgWz1fsfc-Ci61hPs=s256-br30",
    "Silver and Blood": "https://cdn.gameboost.com/games/logos/silver-and-blood.png",
    "Sky: Children of the Light": "https://i.pinimg.com/736x/17/2d/f5/172df5f8fef6a3512e7996add17da21a.jpg",
    "Slam Dunk": "https://is1-ssl.mzstatic.com/image/thumb/Purple211/v4/f7/68/d6/f768d649-2886-c16a-5ac1-f7af64427f67/AppIcon-1x_U007emarketing-0-8-0-85-220-0.png/512x512bb.png",
    "Snowbreak: Containment Zone": "https://cdn.donatov.net/cover/good-281-1767947763.webp",
    "Solo Leveling: Arise (Auto Via Login)": "https://is1-ssl.mzstatic.com/image/thumb/Purple211/v4/09/61/a3/0961a388-145b-6c35-0a3f-f85da8367465/AppIcon-0-0-1x_U007emarketing-0-8-0-85-220.png/512x512bb.jpg",
    "Soul Land: New World": "https://dl.memuplay.com/new_market/img/com.lrgame.dldl.sea.icon.2024-12-12-12-32-05.png",
    "SoulChill": "https://cha7n.pro/assets/images/games/soulchill.webp?v=1785853394",
    "Spring Valley: Farm Adventures": "https://is1-ssl.mzstatic.com/image/thumb/Purple211/v4/3e/69/15/3e69152b-daca-e56b-a32a-65f670d121d9/AppIcon-0-0-1x_U007emarketing-0-8-0-85-220.png/512x512bb.png",
    "Standoff 2": "https://is1-ssl.mzstatic.com/image/thumb/Purple211/v4/41/9e/88/419e8863-04c7-f1f2-405a-47d05ccb598c/AppIcon-0-0-1x_U007emarketing-0-8-0-85-220.png/512x512bb.png",
    "Star Resonance": "https://play-lh.googleusercontent.com/UKX3IajKF92N6Z6f8VRFH_OUFKUx_Qj-H6U8hCGO7pVkgZPRPA5-p-_7cxv3sVxAxwFY2CVBFDGLnD5Rktk_Tg=s256-br30",
    "StarMaker": "https://icons.appfigures.com/6017596/512",
    "Starfall Fantasy: Neverland": "https://play-lh.googleusercontent.com/u8Gn64w94PKzsw9Q93mJLvbqcKq4RI7DwnTt1CjeA5a_AX7Opx8YmPNkjax9bsOE4PORCaTAokKg1RMbE8l3=s256-br30",
    "State of Survival": "https://pub-c39e89399e904c93ad235e987fadb15f.r2.dev/games/ffef7c32-cd9f-449a-a6aa-13d4ee06d74b.webp",
    "Stella Sora": "https://play-lh.googleusercontent.com/_Or4TdlnY_3gKuR04BEs_DS99kKeVnyEcdOF1Pf9GvWxSnp0Mb8aDqy8YVyqjAZoQ3aW8evgVeOzFKvCyI6e7tM=s256-br30",
    "Stormshot": "https://play-lh.googleusercontent.com/p3ooyvsRUzLrv6482L0a3lcVFeNGnFX0F7vUQNP6-44Bo2cSZV2t8uFMeFl46S8dnt_xEof9Clmv_OyPDcd6YQ=s256-br30",
    "Stumble Guys": "https://re-store.landing.paydigital.shop/_next/image?url=https%3A%2F%2Fs3.api.foreignpay.ru%2Fproducts-images%2Ficon_StumbleGuys.png&w=384&q=50",
    "Super Sus": "https://modsmaniac.com/wp-content/uploads/2024/03/super-sus-who-is-the-impostor.png",
    "Super Sus (Indonesia)": "https://modsmaniac.com/wp-content/uploads/2024/03/super-sus-who-is-the-impostor.png",
    "Super Sus (Malaysia)": "https://modsmaniac.com/wp-content/uploads/2024/03/super-sus-who-is-the-impostor.png",
    "Super Sus (Philippines)": "https://modsmaniac.com/wp-content/uploads/2024/03/super-sus-who-is-the-impostor.png",
    "Sword of Justice (EU)": "https://www.braumvault.com/game/icon/swordofjustice_eu",
    "Sword of Justice (NA)": "https://www.braumvault.com/game/icon/swordofjustice_eu",
    "Sword of Justice (SEA)": "https://cdn.indexgame.in.th/game-assets/eb2939fc-2a14-45f9-85ea-d3ed801ea7f8.webp",
    "T3 Arena": "https://play-lh.googleusercontent.com/KcRK-HN_TrWsQHHI5SjIUVk9CaFSwiWUbIUfyDq3voAiw0jjk1YsWUiarTz7Mnpa8aFOzXYNcWXxzQ8ijHRJLw=s256-br30",
    "TFT Mobile (ID)": "https://cdn.gameboost.com/games/logos/teamfight-tactics.png",
    "TFT Mobile (MY)": "https://cdn.gameboost.com/games/logos/teamfight-tactics.png",
    "TFT Mobile (PH)": "https://cdn.gameboost.com/games/logos/teamfight-tactics.png",
    "TFT Mobile (SG)": "https://cdn.gameboost.com/games/logos/teamfight-tactics.png",
    "TFT Mobile (TH)": "https://cdn.gameboost.com/games/logos/teamfight-tactics.png",
    "Teen Patti Gold": "https://play-lh.googleusercontent.com/EwjLBe0Ngx9a8aonwoYC0_Iws6Y5zI8nNDXSJJZ9jKN6alqe6SGdELKl1io6Hx7yEDoC2LFPUs6TjlJJbLb7ews=s256-br30",
    "The Ants: Underground Kingdom": "https://play-lh.googleusercontent.com/q1iMkNWtSDukrL75MJtK9uVXTYN6DBXcB745SCJaxeL88cmZRl2qLUFyj4apNsYkp82He5B9VRZWLvhip9Un=s256-br30",
    "The Division Resurgence": "https://play-lh.googleusercontent.com/QsLsOlzB53d31jGSXdTl68gXgnjUDMk8wmam8_ynuhrG5MtqTYqz2K82y52aTa3tTXWmMthQElAhyofCTjkNoZI=s256-br30",
    "Tom and Jerry: Chase": "https://play-lh.googleusercontent.com/B90YjxC-GKw5PPGzEreJvIabWvgJiWy8-LgQCvF0REaVtZA-QKUQ9fsX-9QlAn0vxUe6_XfJ7APQ7-tJUztQ=s256-br30",
    "Tomb Busters": "https://play-lh.googleusercontent.com/fLZ9Tx97Yrd7_JK-uPrqRCy8sV_6vTa7_69N3aFUEJHjKebGwNXm99A9YVvnIwz9s5TJvsfi03-sHQIMSi7Vkg=s256-br30",
    "TopTop": "https://play-lh.googleusercontent.com/bA3CEqiiiIo-WHuNk0CSNtAEXSatH6BzIzIepQY6tUFhgXvMfz6IZslTdKepNnTVX0cvcMO6hwxV0xmoat8UEw=s256-br30",
    "Tower of Fantasy (Auto Via Login)": "https://psnobj.prod.dl.playstation.net/psnobj/NPWR30185_00/8310b8b4-aa00-46ec-abdd-0795a52a47f0.png",
    "Ulala: Idle Adventure": "https://play-lh.googleusercontent.com/RFAQfw-TZyS3bh3oQpkWE31aB3peYPZCSNxkaAWIiMgDLL8IlNv-gynJtETL7L1raBbyisdwOyUGzFoAPG3J=s256-br30",
    "Undawn (EU)": "https://play-lh.googleusercontent.com/yUEGrnalpru2fAANkR_jzbNS22bPP1F0dnT70sPoMiC1Yv5fz_eparahw1B7noL7NiddLlkOkrusLtELtKT_xg=s256-br30",
    "Undawn Global": "https://play-lh.googleusercontent.com/yUEGrnalpru2fAANkR_jzbNS22bPP1F0dnT70sPoMiC1Yv5fz_eparahw1B7noL7NiddLlkOkrusLtELtKT_xg=s256-br30",
    "Valorant (ID)": "https://static.polymarket.us/images/esports/game-tiles/valorant.png",
    "Valorant (KH)": "https://static.polymarket.us/images/esports/game-tiles/valorant.png",
    "Valorant (MY)": "https://static.polymarket.us/images/esports/game-tiles/valorant.png",
    "Valorant (PH)": "https://static.polymarket.us/images/esports/game-tiles/valorant.png",
    "Valorant (SG)": "https://static.polymarket.us/images/esports/game-tiles/valorant.png",
    "Valorant (TH)": "https://static.polymarket.us/images/esports/game-tiles/valorant.png",
    "Valorant (VN)": "https://static.polymarket.us/images/esports/game-tiles/valorant.png",
    "Watcher of Realms": "https://cdn-bgp.bluestacks.com/BGP/de/logo_com.td.watcherofrealms.png",
    "WeSing": "https://p.kg.qq.com/wsingmvf/600_4d1fcfdd83594a3b047e47ef83f9fafc598146af/0",
    "Where Winds Meet": "https://play-lh.googleusercontent.com/374Q5GLONgIy3k91Ghtef8p-BGVg4naIDsmlTJ8eqYQIAEHhY2A15WUfq8oCpXbnfddedT_T64nIy2zLEQxk=s256-br30",
    "Whiteout Survival": "https://cdn.wegame.tech/default-game-webp/whiteout-survival.webp",
    "Wild Rift (ID)": "https://getandroid.ir/uploads/posts/2020-04/1588195358_league-of-legends-wild-rift-icon.png",
    "Wild Rift (KH)": "https://getandroid.ir/uploads/posts/2020-04/1588195358_league-of-legends-wild-rift-icon.png",
    "Wild Rift (MY)": "https://getandroid.ir/uploads/posts/2020-04/1588195358_league-of-legends-wild-rift-icon.png",
    "Wild Rift (PH)": "https://getandroid.ir/uploads/posts/2020-04/1588195358_league-of-legends-wild-rift-icon.png",
    "Wild Rift (SG)": "https://getandroid.ir/uploads/posts/2020-04/1588195358_league-of-legends-wild-rift-icon.png",
    "Wild Rift (TH)": "https://getandroid.ir/uploads/posts/2020-04/1588195358_league-of-legends-wild-rift-icon.png",
    "Wild Rift (VN)": "https://getandroid.ir/uploads/posts/2020-04/1588195358_league-of-legends-wild-rift-icon.png",
    "Wuthering Waves": "https://pgem.shop/_next/image?url=%2Fimages%2Fgames%2Fwuthering-waves-top-up.webp&w=828&q=75",
    "X-Clash: Survival Challenge": "https://play-lh.googleusercontent.com/angXGBMMY51cmjEacSarq1uV5Olbui9cCQr9BaRNpGcRNv1JrK0Y0JRRq5KqD1pT7jjgWYO1p6BFNlgmME-O=s256-br30",
    "Yalla": "https://play-lh.googleusercontent.com/eQYyiDwn5aHCvEpwW0O3OiecANKQeKhR-QAQOUqcrshnGxCsGSNEUrs3PrwgVdSbRWXD1W5vZHm6xZ6bck36Fw=s256-br30",
    "Yalla Ludo": "https://invidious.zephyron.app/ggpht/rPbLG611BMz6IhctsUaLSElQXJx9PbQQqGY1s5ZFhmgeT3YdlVaDuYCVem7lz6_FnOxlwQYD-w=s900-c-k-c0x00ffffff-no-rj",
    "YoHo: Group Voice Chat Room": "https://play-lh.googleusercontent.com/DwurZKy8M-beYIPEK7AdIFBUyTQkQrlLQtQLyjSDAv3VcTDHcb_LP8XCtQBRPx10nsWtCw0GiXe7GfLFHVYV2w=s256-br30",
    "Zenless Zone Zero (Global)": "https://latestlogo.com/wp-content/uploads/2024/06/zenless-zone-zero-logo.png",
    "Zepeto": "https://cdn.gameboost.com/games/zepeto/logo/icon.svg",
}

# Логотипы для Mini App: используем favicon официальных страниц как компактные иконки.
# Важно: переданные ссылки — страницы игр, а не прямые ссылки на JPG/PNG.
GAME_ICON_DOMAINS = {
    "blade x": "taptap.io",
    "crystalfall": "crystalfall.com",
    "extraordinary ones": "eo-moba.herogame.com",
    "firefly live": "firefly.live",
    "hyper front": "materium.gg",
    "isekai feast": "game.eyougame.com",
    "moonlight blade": "moonlightbladem.vnggames.com",
    "omega legends": "facebook.com",
    "point blank": "pointblank.id",
    "qq coin": "pay.qq.com",
    "sword of fire and ice": "facebook.com",
    "telegram stars": "telegram.org",
    "lord of the rings": "lotr-risetowar.com",
    "tik tok": "douyin.com",
    "tiktok": "douyin.com",
    "warborne": "warborne.qoolandgames.com",
    "ff bd": "facebook.com",
    "ff br": "ff.garena.com",
    "ff eu": "ff.garena.com",
    "ff latam": "ff.garena.com",
    "ff mena": "facebook.com",
    "ff my/sg": "ff.garena.com",
    "ff ph": "facebook.com",
    "ff sg": "fairplay.freefiremobile.com",
    "ff th": "esports.freefire.in.th",
    "ff tw": "ff.garena.com",
    "ff vn": "ff.garena.com",
    "ff инд": "ffindia.garenaind.com",
    "ff снг": "vk.ru",
}

def get_game_icon_url(game_name: str) -> str:
    """Возвращает URL компактного логотипа по названию категории."""
    name = str(game_name or "").strip().lower()
    # Сначала точное/частичное совпадение по специально заданным официальным доменам.
    for key, domain in GAME_ICON_DOMAINS.items():
        if key in name:
            return f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
    # Старые прямые иконки сохраняем для остальных игр.
    return GAME_ICONS.get(game_name) or GAME_ICONS.get(str(game_name or "").strip()) or ""


def payment_url(method, amount):
    """Создаёт ссылку оплаты с выбранной суммой; подтверждение остаётся ручным."""
    base = DC_PAY_URL if method == "dc" else ""
    if not base:
        return ""
    parts = urlsplit(base)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["s"] = f"{float(amount):.2f}"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

PAY_METHODS = {}
# Способы оплаты задаются через переменные окружения — номера карт не хранятся в коде.
_dc_card_number = os.environ.get("DC_CARD_NUMBER") or os.environ.get("DC_NUMBER") or DC_TRANSFER_PHONE
_alif_card_number = os.environ.get("ALIF_CARD_NUMBER") or os.environ.get("ALIF_NUMBER", "")
if _dc_card_number:
    PAY_METHODS["dc"] = {"title": "🏙 Душанбе Сити", "number": _dc_card_number,
                         "holder": os.environ.get("DC_HOLDER", "")}
if _alif_card_number:
    PAY_METHODS["alif"] = {"title": "💳 Алиф", "number": _alif_card_number,
                           "holder": os.environ.get("ALIF_HOLDER", "")}

API = "https://donatix.tj/api/v1"
HEADERS = {"X-API-Key": DONATIX_KEY}
bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

class TemporaryBlockMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = getattr(event, 'from_user', None)
        if user and not is_admin(user.id):
            u = get_user(user.id)
            if u.get('blocked'):
                msg = '⛔ Ваш аккаунт временно заблокирован.'
                if hasattr(event, 'answer'):
                    try: await event.answer(msg, show_alert=True)
                    except TypeError: await event.answer(msg)
                elif hasattr(event, 'message') and event.message:
                    await event.message.answer(msg)
                return None
        return await handler(event, data)

dp.message.outer_middleware(TemporaryBlockMiddleware())
dp.callback_query.outer_middleware(TemporaryBlockMiddleware())

# ===================== Тексты (tg / ru / en / ar / zh / hi) =====================
T = {
    "tg": {
        "welcome": (
            "🔥❤️ Хуш омадед ба DONATEX!\n\n"
            "💎 Алмос ва UC — бо ID-и бозингар, пардохт бо сомонӣ.\n"
            "⚡ Фармоиш пас аз пардохт худкор иҷро мешавад.\n\n"
            "💰 Баланси шумо: <b>{bal}</b> с.\n\nБозиро интихоб кунед 👇"
        ),
        "phone_required": "📱 Барои оғоз рақами телефони худро фиристед. Барои идома тугмаи поёнро пахш кунед.",
        "share_phone": "📱 Рақами худро фиристодан", "phone_received": "✅ Рақам қабул шуд! Хуш омадед.",
        "all_games": "🎮 Ҳамаи бозиҳо", "stars": "⭐ Stars / Premium", "balance": "💰 Баланс",
        "orders": "📦 Фармоишҳои ман", "support": "🛟 Дастгирӣ", "faq": "❓ Саволҳои зуд-зуд", "promo": "🎟 Промокод",
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
        "topup_amount_prompt": "{title} — маблағи пуркунӣ\n\n💰 Маблағро бо тугма интихоб кунед ё худатон бо паём нависед (аз {min} то {max} с.).",
        "pay_alif": "💳 Алиф", "pay_dc": "🏙 Душанбе Сити",
        "topup_after_transfer": "\n\n📸 Пас аз пардохт акси чекро ба ҳамин ҷо фиристед. Администратор пардохтро месанҷад ва маблағро ба баланс мегузаронад. Як чекро такроран нафиристед.",
        "open_dc": "🏙 Кушодани Душанбе Сити",
        "enter_amt": "✏️ Миқдорро бо рақам нависед ({min}–{max} с.):",
        "bad_amt": "❌ Миқдори нодуруст. Иҷозат: {min}–{max} с.",
        "topup_instr": "💳 {title}:\n1️⃣ Ба рақами корт гузаронед: <code>{number}</code>{holder}\n💵 Миқдор: {amount} с.\n\n2️⃣ Чек (акс)-ро фиристед 📸",
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
        "phone_required": "📱 Чтобы начать, отправьте свой номер телефона. Нажмите кнопку ниже.",
        "share_phone": "📱 Отправить свой номер", "phone_received": "✅ Номер получен! Добро пожаловать.",
        "all_games": "🎮 Все игры", "stars": "⭐ Stars / Premium", "balance": "💰 Баланс",
        "orders": "📦 Мои заказы", "support": "🛟 Поддержка", "faq": "❓ Частые вопросы", "promo": "🎟 Промокод",
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
        "topup_amount_prompt": "{title} — сумма пополнения\n\n💰 Выберите сумму кнопкой или отправьте её сообщением (от {min} до {max} с.).",
        "pay_alif": "💳 Алиф", "pay_dc": "🏙 Душанбе Сити",
        "topup_after_transfer": "\n\n📸 После оплаты отправьте сюда фото чека. Администратор проверит платёж и зачислит деньги на баланс. Не отправляйте один чек повторно.",
        "open_dc": "🏙 Открыть Душанбе Сити",
        "enter_amt": "✏️ Введите сумму цифрами ({min}–{max} с.):",
        "bad_amt": "❌ Неверная сумма. Допустимо: {min}–{max} с.",
        "topup_instr": "💳 {title}:\n1️⃣ Переведите на номер карты: <code>{number}</code>{holder}\n💵 Сумма: {amount} с.\n\n2️⃣ Отправьте чек (фото) 📸",
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
        "phone_required": "📱 To get started, share your phone number using the button below.",
        "share_phone": "📱 Share my phone number", "phone_received": "✅ Number received! Welcome.",
        "all_games": "🎮 All games", "stars": "⭐ Stars / Premium", "balance": "💰 Balance",
        "orders": "📦 My orders", "support": "🛟 Support", "faq": "❓ FAQ", "promo": "🎟 Promo code",
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
        "topup_amount_prompt": "{title} — top-up amount\n\n💰 Choose an amount using a button or send it as a message ({min}–{max} TJS).",
        "pay_alif": "💳 Alif", "pay_dc": "🏙 Dushanbe City",
        "topup_after_transfer": "\n\n📸 After payment, send a photo of the receipt here. An administrator will verify the payment and add the funds to your balance. Do not send the same receipt twice.",
        "open_dc": "🏙 Open Dushanbe City",
        "enter_amt": "✏️ Enter the amount as a number ({min}–{max} TJS):",
        "bad_amt": "❌ Invalid amount. Allowed: {min}–{max} TJS",
        "topup_instr": "💳 {title}:\n1️⃣ Transfer to card number: <code>{number}</code>{holder}\n💵 Amount: {amount} TJS\n\n2️⃣ Send the receipt (photo) 📸",
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
              "reviews": [],
              "receipt_fingerprints": {}, "price_snapshots": {}}
USER_DEFAULTS = {
    "balance": 0.0, "name": "", "username": "", "blocked": False, "lang": "tg", "ref_by": None,
    "refs": 0, "ref_earned": 0.0, "topped": False, "promo": None, "joined": 0,
    "discount_percent": 0.0,              # персональная скидка админа (%)
    "transactions": [],                   # история операций
    "saved_ids": [],                      # сохранённые ID игроков
    "customer_no": 0, "free_sensitivity_used": False, "sensitivity_credits": 0,
    "cart_items": [], "cart_select_mode": False, "phone_verified": False, "phone_number": "",
    "support_last_ts": 0, "wishlist": [], "favorite_games": [], "notifications": [],
    "blocked_until": 0, "achievements": [], "topup_reminded_at": 0, "favorites": [], "saved_payment_method": "", "custom_avatar_url": "",
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

    # One-time migration: require every account that existed before this update
    # to share its own Telegram contact on its next /start.
    if not db["meta"].get("phone_verification_required_v1"):
        for user in db["users"].values():
            user["phone_verified"] = False
        db["meta"]["phone_verification_required_v1"] = True

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
    # Автоматически снимаем временную блокировку после истечения срока.
    until = int(u.get("blocked_until") or 0)
    if until:
        if until > int(time.time()): u["blocked"] = True
        else:
            u["blocked"] = False
            u["blocked_until"] = 0
            save_db()
    for k, v in USER_DEFAULTS.items():
        if k in ("transactions", "saved_ids", "cart_items", "wishlist", "favorite_games", "notifications", "achievements"):
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
    """Проверяет главного и всех дополнительных администраторов."""
    try:
        return int(uid) in ADMIN_IDS
    except (TypeError, ValueError):
        return False


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
    if p.get("assigned_uid") and str(uid) != str(p.get("assigned_uid")):
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


async def edit_or_send(msg, text, markup=None, edit=True, reply_markup=None):
    # Поддерживаем оба имени аргумента для совместимости с вызовами aiogram.
    if reply_markup is not None:
        markup = reply_markup
    # Единый слегка наклонённый стиль для экранов бота (HTML italic Telegram).
    # Не оборачиваем повторно, если текст уже полностью оформлен курсивом.
    text = str(text)
    if not (text.startswith("<i>") and text.endswith("</i>")):
        text = f"<i>{text}</i>"
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
    """Снимает старую reply-клавиатуру у конкретного чата."""
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

    # Компактное главное меню. Mini App — в самом низу (красная).
    # Панель админа только у админа, сразу под кнопкой Mini App.
    rows = [
        [btn(t(uid, "popular"), "popular"), btn(t(uid, "all_games"), "allp:0")],
        [btn("🔥 FF СНГ 💎", "game:ff_cis"), btn("🇮🇩 FF Индонезия 💎", "game:ff_id")],
        [btn("🎯 PUBG Mobile US 🏆", "game:pubg_us"), btn(t(uid, "stars"), "tg_stars")],
        [btn(t(uid, "balance"), "balance"), btn("🛒 Корзина", "cart_info")],
        [btn("👤 Профиль", "profile"), btn("🎯 Настройки Free Fire", "ff_sens")],
        [btn(t(uid, "faq"), "faq"), btn(t(uid, "ref"), "ref")],
        [btn(t(uid, "support"), "support"), btn(t(uid, "lang"), "lang")],
    ]

    news_ch = get_news_channel(uid)
    news_row = []
    if news_ch:
        news_row.append(lbtn(t(uid, "news"), news_ch))
    if REVIEWS_CHANNEL:
        ch_url = REVIEWS_CHANNEL if REVIEWS_CHANNEL.startswith("http") else f"https://t.me/{REVIEWS_CHANNEL.lstrip('@')}"
        news_row.append(lbtn(t(uid, "reviews_btn"), ch_url))
    if news_row:
        rows.append(news_row)
    # Красная кнопка Mini App в самом низу
    mini_opts = {
        "text": "🔴 Открыть DONATEX Mini App",
        "web_app": WebAppInfo(url=(EXTERNAL_URL or "").rstrip("/") + "/webapp/"),
    }
    _fields = getattr(InlineKeyboardButton, "model_fields", {})
    if "style" in _fields:
        mini_opts["style"] = "danger"
    rows.append([InlineKeyboardButton(**mini_opts)])

    if is_admin(uid):
        rows.append([btn("🛠 Панели админ", "admin")])

    try:
        await msg.edit_text(welcome_text, reply_markup=kb(rows))
    except Exception:
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
    if is_new:
        u["phone_verified"] = False
    save_db()
    # Сбрасываем пользовательскую кнопку меню Telegram, если она была настроена.
    try:
        await bot.set_chat_menu_button(chat_id=uid, menu_button=MenuButtonCommands())
    except Exception:
        pass
    # Новым покупателям сначала предлагаем поделиться собственным контактом.
    if not u.get("phone_verified", True):
        contact_kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=t(uid, "share_phone"), request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
            input_field_placeholder=t(uid, "share_phone"),
        )
        await m.answer(t(uid, "phone_required"), reply_markup=contact_kb)
        return
    # Deep-link из Mini App: admin / ff_sens
    arg = (command.args or "").strip()
    if arg == "admin" and is_admin(uid):
        await show_admin(m)
        return
    if arg == "ff_sens":
        # Переиспользуем callback-обработчик через имитацию
        class _C:
            def __init__(self, message, from_user):
                self.message = message
                self.from_user = from_user
            async def answer(self, *a, **k):
                pass
        await cb_ff_sens(_C(m, m.from_user))
        return
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
    await edit_or_send(c.message, text, kb([
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
        await edit_or_send(c.message, t(uid, "no_orders"), cta_kb(uid))
    else:
        text = t(uid, "orders_title") + "\n\n" + "\n".join(
            f"{icons.get(o['status'], '•')} #{esc(o['oid'])} · {esc(o['title'])} · {o['price']} · "
            f"{datetime.fromtimestamp(o['ts'], TZ):%d.%m %H:%M}" for o in mine)
        await edit_or_send(c.message, text, kb([[btn(t(uid, "menu"), "menu")]]))
    await c.answer()


@dp.callback_query(F.data == "support")
async def cb_support(c):
    uid = c.from_user.id
    social_row = []
    if INSTAGRAM_URL:
        social_row.append(lbtn("📸 Instagram", INSTAGRAM_URL))
    if TIKTOK_URL:
        social_row.append(lbtn("🎵 TikTok", TIKTOK_URL))
    support_rows = [[btn("✍️ Написать в поддержку", "support_write")]]
    if social_row:
        support_rows.append(social_row)
    support_rows.append([btn(t(uid, "menu"), "menu")])
    await edit_or_send(c.message,
        "🛟 <b>Поддержка DONATEX</b>\n\nНапишите сообщение одним текстом. Оно будет передано администратору прямо здесь, в боте. Не отправляйте пароли, коды подтверждения или полные данные банковской карты.",
        reply_markup=kb(support_rows))
    await c.answer()


@dp.callback_query(F.data == "support_write")
async def cb_support_write(c):
    user_state[c.from_user.id] = {"stage": "support_message"}
    await edit_or_send(c.message, "✍️ Напишите ваш вопрос. Администратор ответит вам в этом чате.",
                       kb([[btn("❌ Отмена", "support")]]))
    await c.answer()


@dp.callback_query(F.data.startswith("support_reply:"))
async def cb_support_reply(c):
    if not is_admin(c.from_user.id):
        await c.answer("🚫", show_alert=True)
        return
    target = c.data.split(":", 1)[1]
    if target not in db["users"]:
        await c.answer("Пользователь не найден", show_alert=True)
        return
    user_state[c.from_user.id] = {"stage": "admin_support_reply", "target": target}
    await c.answer()
    await c.message.answer(f"✍️ Напишите ответ пользователю <code>{target}</code> одним сообщением.")


# ===================== Новостной канал =====================
@dp.callback_query(F.data == "news_channel")
async def cb_news(c):
    uid = c.from_user.id
    ch = get_news_channel(uid)
    if ch:
        await c.answer()
        await edit_or_send(c.message, 
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
        await edit_or_send(c.message, t(uid, "no_popular"), reply_markup=kb([
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
    await edit_or_send(c.message, t(uid, "lang_choose"), reply_markup=kb([
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
    await edit_or_send(c.message, t(uid, "promo_ask"), kb([[btn(t(uid, "menu"), "menu")]]))
    await c.answer()


@dp.callback_query(F.data == "ref")
async def cb_ref(c):
    global _bot_username
    uid = c.from_user.id
    if not _bot_username:
        _bot_username = (await bot.get_me()).username
    u = get_user(uid)
    await edit_or_send(c.message, 
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
    def _is_ff(name: str) -> bool:
        # Не путать Garena Delta Force с Free Fire
        if "delta force" in name or "deltaforce" in name:
            return False
        return ("free fire" in name or "freefire" in name or re.search(r"\bff\b", name) is not None)

    if game == "ff_id":
        tokens = ("indonesia", "indon", "free fire id", "free fire (id)", "ff id")
        return next((cid for cid, name in entries
                     if _is_ff(name) and any(token in name for token in tokens)), None)
    if game == "ff_cis":
        tokens = ("cis", "снг", "russia", "rus", "free fire ru", "ff ru")
        # Сначала регион СНГ/RU; если нет — любой FF кроме Indonesia
        found = next((cid for cid, name in entries
                      if _is_ff(name) and any(token in name for token in tokens)
                      and not any(token in name for token in ("indonesia", "indon"))), None)
        if found is not None:
            return found
        return next((cid for cid, name in entries
                     if _is_ff(name) and not any(token in name for token in ("indonesia", "indon"))), None)
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
    if game == "fc_mobile":
        return next((cid for cid, name in entries
                     if "fc mobile" in name or "fifa mobile" in name), None)
    if game == "delta_force":
        return next((cid for cid, name in entries
                     if "delta force" in name or "deltaforce" in name), None)
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
        await edit_or_send(c.message, t(c.from_user.id, "nf"),
                               reply_markup=cta_kb(c.from_user.id))


@dp.callback_query(F.data.startswith("allp:"))
async def cb_allp(c):
    await c.answer()
    await load_catalog()
    await show_all_games(c, int(c.data.split(":")[1]))


@dp.callback_query(F.data == "gamesearch")
async def cb_gamesearch(c):
    uid = c.from_user.id
    user_state[uid] = {"stage": "game_search"}
    await c.answer()
    await edit_or_send(c.message, "🔎 Введите название игры для быстрого поиска:",
                       kb([[btn("⬅️ Все игры", "allp:0")], [btn(t(uid, "menu"), "menu")]]))


async def show_all_games(c, page):
    uid = c.from_user.id
    ids = list(catalog.keys())

    def game_rank(cid):
        name = str(catalog.get(cid, {}).get("name", "")).strip().casefold()
        # Сначала все доступные регионы Free Fire, затем все регионы PUBG Mobile.
        if (re.search(r"\bfree\s*fire\b", name)
                or re.search(r"\bfreefire\b", name)
                or re.search(r"\bff\b", name)
                or re.search(r"\bфри\s*фаер\b", name)):
            return (0, name)
        if "pubg" in name:
            return (1, name)
        # Далее игры в указанном порядке; прочие игры остаются ниже по алфавиту.
        priorities = ("fc mobile", "fifa mobile", "standoff", "capcut", "delta force", "deltaforce")
        for rank, token in enumerate(priorities, start=2):
            if token in name:
                return (rank, name)
        return (20, name)

    ids = sorted(ids, key=game_rank)
    chunk = ids[page * GAMES_PER_PAGE:(page + 1) * GAMES_PER_PAGE]
    rows = [[btn("🔎 Поиск игр", "gamesearch")]]
    rows.extend([[btn(catalog[cid]["name"][:40], f"cat:{sid(cid)}")] for cid in chunk])
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
        await edit_or_send(c.message, t(c.from_user.id, "nf"), reply_markup=cta_kb(c.from_user.id))
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
        await edit_or_send(c.message, t(uid, "nf"), reply_markup=cta_kb(uid))
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
        player_id = str(item["id"])
        label = player_id
        if item.get("nick"):
            label = f"{str(item['nick'])[:14]} · {player_id}"
        rows.append([btn(label[:40], f"useid:{player_id}"), btn("🗑", f"delid:{player_id}")])
    text = t(uid, "enter_id", title=esc(ptitle(product, lang)), price=product["price_tjs"])
    if saved:
        text += "\n\n" + t(uid, "saved_hint")
    await msg.answer(text, reply_markup=kb(rows + [nav_row(uid, back)]))


@dp.callback_query(F.data.startswith("delid:"))
async def cb_delete_saved_id(c):
    uid = c.from_user.id
    player_id = c.data.split(":", 1)[1]
    u = get_user(uid)
    before = u.get("saved_ids") or []
    u["saved_ids"] = [x for x in before if str(x.get("id")) != player_id]
    save_db()
    st = user_state.get(uid, {})
    if st.get("stage") != "waiting_id":
        await c.answer("Список ID обновлён")
        return
    saved = [x for x in u["saved_ids"] if x.get("id")]
    rows = []
    for item in saved[:6]:
        pid = str(item["id"])
        label = f"{str(item.get('nick') or '')[:14]} · {pid}" if item.get("nick") else pid
        rows.append([btn(label[:40], f"useid:{pid}"), btn("🗑", f"delid:{pid}")])
    rows.append(nav_row(uid, st.get("back", "menu")))
    product = st.get("product") or {}
    text = t(uid, "enter_id", title=esc(ptitle(product, get_user(uid)["lang"])),
             price=product.get("price_tjs", "—"))
    if saved:
        text += "\n\n" + t(uid, "saved_hint")
    await c.message.edit_text(text, reply_markup=kb(rows))
    await c.answer("ID удалён" if len(before) != len(u["saved_ids"]) else "ID не найден")


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
    await edit_or_send(c.message, f"{esc(st['title'])} — {st['base']} с.\n\n{t(uid, 'enter_uname')}")
    await c.answer()


# ===================== Подтверждение телефона новых пользователей =====================
@dp.message(F.contact)
async def contact_handler(m):
    uid = m.from_user.id
    u = get_user(uid, m.from_user.full_name or "", getattr(m.from_user, "username", None) or "")
    contact = m.contact
    # Принимаем только контакт самого пользователя, а не чужой номер из адресной книги.
    if not contact or contact.user_id != uid:
        await m.answer(t(uid, "phone_required"))
        return
    u["phone_number"] = contact.phone_number
    u["phone_verified"] = True
    save_db()
    await m.answer(t(uid, "phone_received"), reply_markup=ReplyKeyboardRemove())
    await send_menu(m, m.from_user)


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
        txt0=(m.text or '').strip().lower()
        faq_map=[(('пополн','оплат','чек','top up'), 'Чтобы пополнить баланс: откройте «Пополнить», выберите сумму и способ оплаты, затем отправьте чек в этот бот.'),
                 (('заказ','долго','статус'), 'Обычно заказ выполняется автоматически. Проверьте «Мои заказы»; если статус долго не меняется, напишите в поддержку.'),
                 (('id','ник','ошиб'), 'Перед подтверждением проверьте игровой ID и отображаемый ник. Если данные неверны, не подтверждайте заказ.'),
                 (('возврат','отмен'), 'После отправки поставщику отмена может быть невозможна. Обратитесь в поддержку для проверки конкретного заказа.'),
                 (('поддерж','оператор'), 'Напишите @' + str(SUPPORT_CONTACT).lstrip('@') if SUPPORT_CONTACT else 'Напишите администратору через раздел «Поддержка».')]
        for keys,answer in faq_map:
            if any(k in txt0 for k in keys):
                await m.answer(answer); return
        return
    txt = m.text.strip()
    stage = st["stage"]
    get_user(uid, m.from_user.full_name or "")

    if stage == "game_search":
        user_state.pop(uid, None)
        await load_catalog()
        query = txt.casefold().strip()
        matches = [
            cid for cid, group in catalog.items()
            if query in str(group.get("name", "")).casefold()
            or any(query in str(p.get("title") or p.get("name") or "").casefold()
                   for p in group.get("products", []))
        ] if query else []
        if not matches:
            await m.answer("😕 Игры не найдены. Попробуйте другое название.",
                           reply_markup=kb([[btn("🔎 Искать ещё", "gamesearch")],
                                            [btn("🎮 Все игры", "allp:0")],
                                            [btn(t(uid, "menu"), "menu")]]))
            return
        rows = [[btn(str(catalog[cid]["name"])[:40], f"cat:{sid(cid)}")] for cid in matches[:80]]
        rows.append([btn("🔎 Искать ещё", "gamesearch")])
        rows.append([btn("🎮 Все игры", "allp:0"), btn(t(uid, "menu"), "menu")])
        await m.answer(f"🔎 Найдено игр: {len(matches)}. Выберите нужную:", reply_markup=kb(rows))
        return

    if stage == "support_message":
        u = get_user(uid)
        if time.time() - float(u.get("support_last_ts", 0)) < 20:
            await m.answer("⏳ Подождите немного перед следующим обращением.")
            return
        if len(txt) > 3000:
            await m.answer("Сообщение слишком длинное. Максимум — 3000 символов.")
            return
        user_state.pop(uid, None)
        if not ADMIN_ID:
            await m.answer("Поддержка временно недоступна. Попробуйте позже.")
            return
        u = get_user(uid, m.from_user.full_name or "", m.from_user.username or "")
        u["support_last_ts"] = time.time()
        save_db()
        try:
            await bot.send_message(ADMIN_ID,
                f"🛟 <b>Обращение в поддержку</b>\n👤 {esc(u.get('name') or 'Клиент')} · @{esc(u.get('username') or '—')}\n"
                f"🆔 <code>{uid}</code> · №{u.get('customer_no', 0)}\n\n{esc(txt)}",
                reply_markup=kb([[btn("↩️ Ответить", f"support_reply:{uid}")]]))
            await m.answer("✅ Сообщение передано поддержке. Ответ придёт сюда в бот.",
                           reply_markup=kb([[btn(t(uid, "menu"), "menu")]]))
        except Exception:
            user_state[uid] = st
            await m.answer("Не удалось передать сообщение. Попробуйте ещё раз позже.")
        return

    elif stage == "admin_support_reply" and is_admin(uid):
        target = str(st.get("target", ""))
        user_state.pop(uid, None)
        if target not in db["users"]:
            await m.answer("Пользователь не найден.")
            return
        try:
            await bot.send_message(int(target), f"🛟 <b>Ответ поддержки DONATEX</b>\n\n{esc(txt)}",
                                   reply_markup=kb([[btn(t(int(target), "menu"), "menu")]]))
            await m.answer("✅ Ответ отправлен клиенту.")
        except Exception as e:
            log.warning("support reply failed: %s", e)
            await m.answer("Не удалось отправить ответ клиенту.")
        return

    elif stage == "waiting_id":
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
            await m.answer(
                t(uid, "bad_amt", min=f"{MIN_TOPUP:g}", max=f"{MAX_TOPUP:g}") +
                "\\nМожно попробовать ещё раз — просто напишите сумму сообщением."
            )
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
        try:
            stars = int(st.get("stars", 5))
        except (TypeError, ValueError):
            stars = 5
        stars = max(1, min(5, stars))
        order_title = st.get("title", "")
        review_text = txt if txt != "/skip" else ""
        db.setdefault("reviews", []).append({"uid": uid, "stars": stars,
            "title": order_title[:120], "text": review_text[:1000], "ts": now_ts()})
        db["reviews"] = db["reviews"][-2000:]
        save_db()
        # Пересылаем отзыв в канал
        if REVIEWS_CHANNEL_ID:
            try:
                msg_text = (
                    f"{'⭐' * int(stars)}{'☆' * (5 - int(stars))}\n"
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
            _push_notice(uid, 'Заказ проверяется', f'{title}: ожидаем подтверждение поставщика', 'order', {'oid':str(rec.get('oid','?'))})
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
            _push_notice(uid, 'Заказ выполнен', f'{title} · #{oid}', 'order', {'oid':str(oid)})
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
    if len(parts) != 4:
        await c.answer("Некорректная оценка", show_alert=True)
        return
    uid = c.from_user.id
    try:
        target_uid = int(parts[1])
        stars = int(parts[2])
    except (TypeError, ValueError):
        await c.answer("Некорректная оценка", show_alert=True)
        return
    if target_uid != uid or stars not in range(1, 6):
        await c.answer("Эта оценка предназначена другому пользователю", show_alert=True)
        return
    title = db["meta"].get(f"rv_title_{uid}", "")
    user_state[uid] = {"stage": "review_text", "stars": stars, "title": title}
    try:
        await c.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await edit_or_send(c.message, t(uid, "review_text_ask") + "\n(необязательно — отправьте /skip)",
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
    await edit_or_send(c.message, t(uid, "review_thanks"), reply_markup=kb([[btn(t(uid, "menu"), "menu")]]))
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
    # Единственный доступный способ пополнения — Душанбе Сити.
    rows = [[btn(t(uid, "pay_alif" if mk == "alif" else "pay_dc") if mk in ("alif", "dc") else mm["title"], f"tm:{mk}")] for mk, mm in PAY_METHODS.items()]
    rows.append([btn(t(uid, "menu"), "menu")])
    await edit_or_send(c.message, t(uid, "choose_pay"), kb(rows))
    await c.answer()

async def _show_topup_amounts(c, uid, mk):
    """Быстрые суммы; произвольную сумму можно сразу написать в чат."""
    user_state[uid] = {"stage": "topup_custom", "method": mk}
    rows = [
        [btn("10 с.", f"tamt:10:{mk}"), btn("20 с.", f"tamt:20:{mk}"), btn("50 с.", f"tamt:50:{mk}")],
        [btn("100 с.", f"tamt:100:{mk}"), btn("200 с.", f"tamt:200:{mk}")],
        [btn(t(uid, "other"), f"tamt:custom:{mk}")],
        [btn(t(uid, "menu"), "menu")],
    ]
    method_title = t(uid, "pay_alif" if mk == "alif" else "pay_dc") if mk in ("alif", "dc") else PAY_METHODS[mk]["title"]
    prompt = t(uid, "topup_amount_prompt", title=method_title,
               min=f"{MIN_TOPUP:g}", max=f"{MAX_TOPUP:g}")
    await edit_or_send(c.message, prompt, kb(rows))


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
        await edit_or_send(
            c.message,
            t(uid, "enter_amt", min=f"{MIN_TOPUP:g}", max=f"{MAX_TOPUP:g}"),
            kb([[btn(t(uid, "back"), f"tm:{mk}")], [btn(t(uid, "menu"), "menu")]])
        )
    else:
        amount = parse_amount(v)
        if amount is None:
            await edit_or_send(c.message, t(uid, "bad_amt", min=f"{MIN_TOPUP:g}", max=f"{MAX_TOPUP:g}"))
            return
        await start_topup(c.message, uid, amount, mk)


async def start_topup(msg, uid, amount, mk):
    pm = PAY_METHODS[mk]
    tid = uuid.uuid4().hex[:8]
    db["topups"][tid] = {"uid": uid, "amount": amount, "method": mk, "status": "pending", "ts": now_ts()}
    save_db()
    user_state[uid] = {"stage": "receipt", "tid": tid}
    holder = f"\n👤 {esc(pm['holder'])}" if pm["holder"] else ""
    method_title = t(uid, "pay_alif" if mk == "alif" else "pay_dc") if mk in ("alif", "dc") else pm["title"]
    instr = t(uid, "topup_instr", title=method_title, number=esc(pm["number"]),
              holder=holder, amount=f"{amount:.2f}")
    instr += t(uid, "topup_after_transfer")
    pay_url = payment_url(mk, amount) if mk == "dc" else ""
    rows = []
    if pay_url:
        rows.append([lbtn(t(uid, "open_dc"), pay_url)])
    rows.append([btn(t(uid, "menu"), "menu")])
    await edit_or_send(msg, instr, kb(rows))


@dp.message(F.photo | F.document)
async def got_receipt(m):
    uid = m.from_user.id
    if get_user(uid)["blocked"]:
        await m.answer(t(uid, "blocked"))
        return
    st = user_state.get(uid)
    if not st or st.get("stage") != "receipt":
        return
    topup = db["topups"].get(st["tid"])
    if not topup or topup["status"] != "pending":
        return
    media = (m.photo[-1] if m.photo else m.document)
    if m.document:
        mime = (m.document.mime_type or "").lower()
        if mime not in ("image/jpeg", "image/png", "image/webp", "application/pdf"):
            await m.answer("❌ Принимаются только фото чека или PDF-файл.")
            return
        if m.document.file_size and m.document.file_size > 5 * 1024 * 1024:
            await m.answer("❌ Размер файла не должен превышать 5 МБ.")
            return
    fingerprint = str(getattr(media, "file_unique_id", "") or "")
    fingerprints = db.setdefault("receipt_fingerprints", {})
    if fingerprint and fingerprint in fingerprints:
        await m.answer("⚠️ Этот чек уже отправлялся. Повторная отправка одного чека запрещена.")
        return
    if not RECEIPTS_CHANNEL_ID:
        await m.answer("⚠️ Канал чеков ещё не настроен. Обратитесь в поддержку.",
                       reply_markup=kb([[btn(t(uid, "menu"), "menu")]]))
        return
    user_state.pop(uid, None)
    topup["status"] = "uploading"
    if fingerprint:
        fingerprints[fingerprint] = {"uid": str(uid), "tid": st["tid"], "ts": now_ts()}
    # Risk alert: multiple distinct receipts from one user in a rolling 24h window.
    recent_checks = [x for x in fingerprints.values()
                     if str(x.get("uid")) == str(uid) and now_ts() - int(x.get("ts", 0)) < 86400]
    if len(recent_checks) >= 2:
        await notify_admin(f"⚠️ <b>Подозрительная активность</b>\nПользователь {uid} отправил {len(recent_checks)} чека за 24 часа.")
    save_db()
    user = get_user(uid, m.from_user.full_name or "", m.from_user.username or "")
    caption = (f"🧾 НОВЫЙ ЧЕК · {st['tid']}\n"
              f"👤 {esc(m.from_user.full_name)} · @{esc(m.from_user.username or '—')}\n"
              f"🆔 ID: <code>{uid}</code> · № покупателя: <b>{user['customer_no']}</b>\n"
              f"📱 Телефон: <code>{esc(user.get('phone_number') or 'не указан')}</code>\n"
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
        if fingerprint:
            fingerprints.pop(fingerprint, None)
        save_db()
        log.warning("receipt channel delivery: %s", e)
        await m.answer("⚠️ Не удалось отправить чек в канал. Попробуйте позже.",
                       reply_markup=kb([[btn(t(uid, "menu"), "menu")]]))
        return
    topup["status"] = "review"
    save_db()
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
    _push_notice(uid, "Баланс пополнен", f"На баланс зачислено {topup['amount']:.2f} TJS", "topup")
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
    # Keep the original receipt and its caption intact; only append a final status line.
    original = c.message.caption if c.message.caption is not None else (c.message.text or "")
    footer = "✅ ЧЕК ПОДТВЕРЖДЕН"
    # Remove an old status footer if this message was edited before, then add the final one.
    lines = original.splitlines()
    lines = [line for line in lines if line.strip() not in (
        "✅ ЧЕК ПОДТВЕРЖДЕН", "❌ ЧЕК ОТКЛОНЕН",
    ) and not line.strip().startswith(("✅ Подтверждено:", "❌ Отклонено:"))]
    updated = "\n".join(lines).rstrip() + "\n\n" + footer
    if c.message.caption is not None:
        await c.message.edit_caption(caption=updated, reply_markup=None)
    else:
        await c.message.edit_text(text=updated, reply_markup=None)
    await c.answer("Чек подтверждён")


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
    # Do not delete/replace the submitted receipt text: append a clear status at the bottom.
    original = c.message.caption if c.message.caption is not None else (c.message.text or "")
    footer = "❌ ЧЕК ОТКЛОНЕН"
    lines = original.splitlines()
    lines = [line for line in lines if line.strip() not in (
        "✅ ЧЕК ПОДТВЕРЖДЕН", "❌ ЧЕК ОТКЛОНЕН",
    ) and not line.strip().startswith(("✅ Подтверждено:", "❌ Отклонено:"))]
    updated = "\n".join(lines).rstrip() + "\n\n" + footer
    if c.message.caption is not None:
        await c.message.edit_caption(caption=updated, reply_markup=None)
    else:
        await c.message.edit_text(text=updated, reply_markup=None)
    await c.answer("Чек отклонён")


# ===================== DONATEX: профиль, FAQ, AI и Free Fire sensitivity =====================
@dp.callback_query(F.data == "profile")
async def cb_profile(c):
    uid = c.from_user.id
    u = get_user(uid, c.from_user.full_name or "", c.from_user.username or "")
    orders = [o for o in db.get("orders", []) if str(o.get("uid")) == str(uid)]
    done = sum(1 for o in orders if o.get("status") == "done")
    await edit_or_send(c.message, 
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
    uid = c.from_user.id
    lang = get_user(uid).get("lang", "tg")
    faq_texts = {
        "tg": (
            "❓ <b>Саволҳои зуд-зуд · DONATEX</b>\n\n"
            "<b>Чӣ тавр пардохт кунам?</b>\n"
            "Бозиро интихоб кунед, маҳсулоти лозимиро интихоб намуда, ID-и бозингарро ворид кунед. "
            "Никро санҷед ва фармоишро тасдиқ намоед. Барои пардохт балансро пур кунед ё усули дастрасро истифода баред.\n\n"
            "<b>Фармоиш чанд вақт мегирад?</b>\n"
            "Одатан фармоиш дар давоми 10–30 сония иҷро мешавад. Агар дер шавад, ба дастгирӣ муроҷиат кунед.\n\n"
            "<b>Фармоишро бекор кардан мумкин аст?</b>\n"
            "Пас аз фиристодани фармоиш ба таъминкунанда бекор кардан мумкин нест. Пеш аз тасдиқ ID ва никро бодиққат санҷед.\n\n"
            "<b>Агар ID-ро хато ворид карда бошам, чӣ кор кунам?</b>\n"
            "Агар ник нодуруст бошад, фармоишро тасдиқ накунед. Агар фармоиш иҷро шуда бошад, баргардонидани маблағ мумкин набошад.\n\n"
            "<b>Чекро чӣ тавр фиристам?</b>\n"
            "Дархости пур кардани балансро созед, маблағи дақиқро гузаронед ва акси чекро дар ҳамин бот фиристед. "
            "Администратор пардохтро месанҷад ва баъд балансро пур мекунад.\n\n"
            "<b>Чӣ тавр аз қаллобӣ эмин бошам?</b>\n"
            "Ба шахсони ношинос пул нафиристед. Ҳамаи пардохтҳо ва фармоишҳоро танҳо тавассути боти расмии DONATEX анҷом диҳед."
        ),
        "ru": (
            "❓ <b>Частые вопросы · DONATEX</b>\n\n"
            "<b>Как оплатить?</b>\n"
            "Выберите игру и товар, введите ID игрока и проверьте ник. Подтвердите заказ. "
            "Для оплаты пополните баланс или используйте доступный способ оплаты.\n\n"
            "<b>Сколько времени занимает заказ?</b>\n"
            "Обычно заказ выполняется за 10–30 секунд. Если заказ долго не меняет статус, обратитесь в поддержку.\n\n"
            "<b>Можно ли отменить заказ?</b>\n"
            "После отправки поставщику отмена может быть невозможна. Перед подтверждением внимательно проверьте ID и ник.\n\n"
            "<b>Что делать, если я ошибся в ID?</b>\n"
            "Если ник отображается неправильно, не подтверждайте заказ. После выполнения заказа возврат может быть невозможен.\n\n"
            "<b>Как отправить чек?</b>\n"
            "Создайте заявку на пополнение, переведите точную сумму и отправьте фото чека в этот бот. "
            "Администратор проверит платёж и зачислит средства на баланс.\n\n"
            "<b>Как защититься от мошенников?</b>\n"
            "Не переводите деньги незнакомым людям. Оформляйте платежи и заказы только через официальный бот DONATEX."
        ),
        "en": (
            "❓ <b>Frequently Asked Questions · DONATEX</b>\n\n"
            "<b>How do I pay?</b>\n"
            "Choose a game and product, enter your player ID, and check the nickname. Confirm the order. "
            "Top up your balance or use an available payment method.\n\n"
            "<b>How long does an order take?</b>\n"
            "Orders are usually completed in 10–30 seconds. If the status does not change for a long time, contact support.\n\n"
            "<b>Can I cancel an order?</b>\n"
            "Cancellation may not be possible after the order is sent to the supplier. Always check the ID and nickname before confirming.\n\n"
            "<b>What if I entered the wrong ID?</b>\n"
            "Do not confirm the order if the displayed nickname is incorrect. A refund may not be possible after the order is completed.\n\n"
            "<b>How do I send a payment receipt?</b>\n"
            "Create a balance top-up request, transfer the exact amount, and send a photo of the receipt in this bot. "
            "An administrator will verify the payment and add the funds to your balance.\n\n"
            "<b>How can I avoid scams?</b>\n"
            "Do not send money to strangers. Make payments and orders only through the official DONATEX bot."
        ),
    }
    text = faq_texts.get(lang, faq_texts["tg"])
    await edit_or_send(
        c.message,
        text,
        reply_markup=kb([
            [btn(t(uid, "support"), "support")],
            [btn(t(uid, "menu"), "menu")]
        ])
    )
    await c.answer()


@dp.callback_query(F.data == "cart_info")
async def cb_cart_info(c):
    uid = c.from_user.id
    u = get_user(uid)
    items = u.setdefault("cart_items", [])
    if not items:
        await edit_or_send(c.message, "🛒 <b>Корзина пока пуста</b>\nОткройте игру и нажимайте «🛒 +» рядом с нужными товарами. Можно добавить разные пакеты и несколько одинаковых.",
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
        await edit_or_send(c.message, "\n".join(lines), reply_markup=kb(rows))
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
        await edit_or_send(c.message, "Откройте игру, чтобы выбрать товары.",
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
        await edit_or_send(c.message, "Количество обновлено.",
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
        await edit_or_send(c.message, "Добавлено в корзину 🛒",
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
    await edit_or_send(c.message, f"🛒 В корзине {len(items)} товар(ов).\n\nВведите ID игрока для товара 1/{len(items)}: <b>{esc(ptitle(items[0],get_user(uid)['lang']))}</b>")

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
            await edit_or_send(c.message, "⚠️ Корзина остановлена: один из заказов не прошёл. Остальные товары не оформлялись.")
            return
    get_user(uid)["cart_items"]=[]; save_db()
    await edit_or_send(c.message, "✅ Все товары из корзины успешно отправлены в обработку.",reply_markup=kb([[btn("🏠 Меню","menu")]]))


FF_DEVICES = ["iPhone 11", "iPhone 12 / 13", "iPhone 14 / 15", "iPhone 16 / 17",
              "Samsung Galaxy", "Xiaomi / Redmi", "POCO", "Realme", "Tecno / Infinix", "Другая модель"]
FF_SENS = [("Обзор", 200), ("Коллиматор", 190), ("2x Прицел", 185),
           ("4x Прицел", 180), ("Снайперский прицел", 170), ("Кнопка свободной камеры", 160)]

@dp.callback_query(F.data == "ff_sens")
async def cb_ff_sens(c):
    rows = [[btn(d, "ffdev:" + str(i))] for i, d in enumerate(FF_DEVICES)]
    rows.append([btn("🏠 Меню", "menu")])
    await edit_or_send(c.message, "🎯 <b>Настройка Free Fire</b>\nВыберите модель телефона. Подберём стартовую чувствительность; значения можно подстроить под FPS, DPI и размер экрана.", reply_markup=kb(rows))
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
    await edit_or_send(c.message, f"🎯 <b>Free Fire · {esc(FF_DEVICES[idx])}</b>\n\n{details}\n\n"
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
    rows = [[btn("👥 Харидорон", "adm_users:0")],
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
    rows = [[btn(f"№{u.get('customer_no', 0)} {'🚫 ' if u['blocked'] else ''}{u['name'][:14] or k} · {str(u.get('phone_number') or 'нет телефона')[:18]}",
                 f"adu:{k}")]
            for k, u in chunk]
    nav = []
    if page > 0:
        nav.append(btn("⬅️", f"adm_users:{page - 1}"))
    if (page + 1) * per < len(items):
        nav.append(btn("➡️", f"adm_users:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([btn("🔎 Ҷустуҷӯи харидор", "adm_search")])
    rows.append([btn("🗑 Удалить сохранённые ID (все/по одному)", "adm_saved_ids")])
    rows.append([btn("🔙", "admin")])
    await edit_or_send(c.message, f"👥 Харидорон: {len(items)}", kb(rows))


async def show_user_card(c, k):
    u = db["users"].get(k)
    if not u:
        await edit_or_send(c.message, "Ёфт нашуд")
        return
    n_orders = sum(1 for o in sales() if str(o["uid"]) == k)
    uname = (u.get("username") or "").lstrip("@")
    if uname:
        name_line = f"👤 <b>{esc(u.get('name') or k)}</b> · @{esc(uname)} · <code>{k}</code> · №{u.get('customer_no', 0)}"
    else:
        name_line = f"👤 <b>{esc(u.get('name') or k)}</b> · <code>{k}</code> · №{u.get('customer_no', 0)}"
    disc = float(u.get("discount_percent") or 0)
    phone = u.get("phone_number") or "Не указан"
    text = (f"{name_line}\n📱 Телефон: <code>{esc(phone)}</code>\n"
            f"💰 Баланс: {u['balance']:.2f} с.\n"
            f"📦 Фармоишҳо: {n_orders}\n👥 Даъват: {u['refs']}\n🚫 Блок: {'ҳа' if u['blocked'] else 'не'}\n"
            f"💸 Скидка: {disc:g}%")
    rows = [[btn("✅ Бикушоед" if u["blocked"] else "🚫 Блок", f"adb:{k}"),
             btn("0️⃣ Сброс баланс", f"adr:{k}")],
            [btn("➕/➖ Баланс", f"ada:{k}"), btn("💸 Скидка %", f"addisc:{k}")]]
    saved_ids = [x for x in (u.get("saved_ids") or []) if x.get("id")]
    if saved_ids:
        text += "\n\n<b>🎮 Сохранённые ID:</b>"
        for item in saved_ids[:8]:
            text += f"\n• {esc(item.get('nick') or 'Без ника')} · <code>{esc(item['id'])}</code>"
            rows.append([btn(f"🗑 Удалить ID {str(item['id'])[:18]}", f"ad_del_sid:{k}:{item['id']}")])
        rows.append([btn("🗑 Удалить все ID этого клиента", f"ad_del_sid_all:{k}")])
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
    await edit_or_send(c.message, "✏️ Миқдорро нависед (масалан 50 ё -20):")
    await c.answer()


@dp.callback_query(F.data.startswith("addisc:"))
@admin_only
async def cb_addisc(c):
    k = c.data.split(":")[1]
    user_state[c.from_user.id] = {"stage": "adm_setdisc", "target": k}
    cur = float(db["users"].get(k, {}).get("discount_percent") or 0)
    await edit_or_send(c.message, 
        f"💸 Скидкаи ҷорӣ: {cur:g}%\n"
        "Фоизро нависед (0–90). Масалан: 10 — 10% арзонтар. 0 — бекор кардани скидка:"
    )
    await c.answer()


@dp.callback_query(F.data == "adm_search")
@admin_only
async def cb_adm_search(c):
    user_state[c.from_user.id] = {"stage": "adm_search_user"}
    await edit_or_send(c.message, "🔎 Ҷустуҷӯ: ID Telegram, @username, ном ё рақами харидорро ворид кунед.")
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
    rows = []
    for code, p in db["promos"].items():
        rows.append([btn(f"{'🟢' if p.get('active', True) else '⚪'} {code} -{p['percent']}% ({p.get('used', 0)}/{p.get('max_uses') or '∞'})", f"apt:{code}"),
                     btn("🗑", f"apdel:{code}")])
    if db["promos"]:
        rows.append([btn("🗑 Удалить ВСЕ промокоды", "apdel_all")])
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


@dp.callback_query(F.data == "adm_saved_ids")
@admin_only
async def cb_adm_saved_ids(c):
    await c.answer()
    rows = [[btn("🗑 Удалить сохранённые ID у ВСЕХ", "adm_saved_ids_all")]]
    for k, u in sorted(db["users"].items(), key=lambda x: -x[1].get("joined", 0)):
        count = len([x for x in (u.get("saved_ids") or []) if x.get("id")])
        if count:
            rows.append([btn(f"{u.get('name') or k} · {count} ID", f"ad_del_sid_all:{k}")])
    rows.append([btn("🔎 Поиск клиента", "adm_search"), btn("🔙 Клиенты", "adm_users:0")])
    await edit_or_send(c.message, "🗑 Управление сохранёнными ID", kb(rows))


@dp.callback_query(F.data == "adm_saved_ids_all")
@admin_only
async def cb_adm_saved_ids_all(c):
    total = 0
    for u in db["users"].values():
        total += len(u.get("saved_ids") or [])
        u["saved_ids"] = []
    save_db()
    await c.answer(f"Удалено ID: {total}", show_alert=True)
    await cb_adm_saved_ids(c)


@dp.callback_query(F.data.startswith("ad_del_sid_all:"))
@admin_only
async def cb_ad_del_sid_all(c):
    k = c.data.split(":", 1)[1]
    if k in db["users"]:
        n = len(db["users"][k].get("saved_ids") or [])
        db["users"][k]["saved_ids"] = []
        save_db()
        await c.answer(f"Удалено: {n}")
        await show_user_card(c, k)
    else:
        await c.answer("Клиент не найден", show_alert=True)


@dp.callback_query(F.data.startswith("ad_del_sid:"))
@admin_only
async def cb_ad_del_sid(c):
    _, k, player_id = c.data.split(":", 2)
    if k not in db["users"]:
        await c.answer("Клиент не найден", show_alert=True); return
    before = db["users"][k].get("saved_ids") or []
    db["users"][k]["saved_ids"] = [x for x in before if str(x.get("id")) != player_id]
    save_db()
    await c.answer("ID удалён" if len(before) != len(db["users"][k]["saved_ids"]) else "ID не найден")
    await show_user_card(c, k)


@dp.callback_query(F.data.startswith("apdel:"))
@admin_only
async def cb_apdel(c):
    code = c.data.split(":", 1)[1]
    existed = db["promos"].pop(code, None) is not None
    save_db()
    await c.answer("Промокод удалён" if existed else "Не найден", show_alert=True)
    await cb_adm_promos(c)


@dp.callback_query(F.data == "apdel_all")
@admin_only
async def cb_apdel_all(c):
    n = len(db["promos"])
    db["promos"].clear()
    save_db()
    await c.answer(f"Удалено промокодов: {n}", show_alert=True)
    await cb_adm_promos(c)


@dp.callback_query(F.data == "adm_promo_new")
@admin_only
async def cb_adm_promo_new(c):
    user_state[c.from_user.id] = {"stage": "adm_promo_new"}
    await edit_or_send(c.message, "✏️ Формат: КОД ПРОЦЕНТ [МАКС_ИСПОЛЬЗОВАНИЙ]\nМисол: SALE10 10 100")
    await c.answer()


@dp.callback_query(F.data == "adm_bc")
@admin_only
async def cb_adm_bc(c):
    user_state[c.from_user.id] = {"stage": "adm_broadcast"}
    await edit_or_send(c.message, "📢 Матни рассылкаро нависед:")
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
    await edit_or_send(c.message, f"🧹 Клавиатура снята: {ok}/{len(ids)} пользователей")


@dp.callback_query(F.data == "adm_dbal")
@admin_only
async def cb_adm_dbal(c):
    await c.answer()
    bal = await donatix_balance()
    if bal is None:
        await edit_or_send(c.message, 
            f"❌ Баланси Donatix гирифта нашуд (путь <code>{esc(BALANCE_PATH)}</code>). "
            f"Дар https://donatix.tj/api-docs роҳи дурустро ёбед ва DONATIX_BALANCE_PATH-ро танзим кунед.")
    else:
        await edit_or_send(c.message, f"💼 Баланси Donatix: <b>{bal:.2f}</b> USD (≈ {bal * usd_tjs:.2f} TJS)")


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


async def h_health(request):
    return web.Response(text="ok")


# ═══════════════════════════════════════════════════════
#  ВЕБ-АВТОРИЗАЦИЯ — для сайта в Chrome (не Telegram)
# ═══════════════════════════════════════════════════════
async def h_web_login(request):
    """Регистрация/вход по имени и телефону с сайта."""
    try:
        data  = await request.json()
        phone = str(data.get("phone", "")).strip()
        name  = str(data.get("name",  "")).strip()

        if not phone or not name:
            return web.json_response(
                {"message": "Заполните имя и телефон"}, status=400
            )

        # Ищем существующего пользователя по номеру телефона
        uid = None
        for u_id, u in db["users"].items():
            if u.get("phone_number") == phone:
                uid = u_id
                break

        # Если не нашли — создаём нового
        if uid is None:
            uid = "web_" + hashlib.md5(phone.encode()).hexdigest()[:10]
            db["users"][uid] = dict(USER_DEFAULTS)
            db["users"][uid]["name"]           = name
            db["users"][uid]["phone_number"]   = phone
            db["users"][uid]["phone_verified"] = True
            db["users"][uid]["joined"]         = now_ts()
            save_db()
            log.info("web_login: новый пользователь %s %s", uid, phone)
        else:
            # Обновляем имя если изменилось
            if name and not db["users"][uid].get("name"):
                db["users"][uid]["name"] = name
                save_db()

        u = db["users"][uid]

        # Создаём токен сессии
        token = secrets.token_hex(20)
        db["meta"][f"web_token_{token}"] = {
            "uid": uid,
            "ts":  now_ts(),
            "exp": now_ts() + 86400 * 30  # 30 дней
        }
        save_db()

        return web.json_response({
            "ok":    True,
            "token": token,
            "user": {
                "id":      uid,
                "name":    u.get("name", name),
                "phone":   phone,
                "bal":     round(float(u.get("balance", 0)), 2),
                "isAdmin": is_admin(ADMIN_ID),
            }
        })

    except Exception as e:
        log.error("h_web_login error: %s", e)
        return web.json_response({"message": str(e)}, status=500)

# ═══════════════════════════════════════════════════════════════════
#  DONATEX Mini App — дополнения к main.py
#
#  Инструкция по интеграции:
#  1. Добавьте этот код в конец main.py (перед async def main())
#  2. В функции main() добавьте новые маршруты в app.add_routes([...])
#  3. Скопируйте donatex_miniapp.html в папку проекта
#  4. В send_menu() добавьте кнопку WebApp (см. конец файла)
# ═══════════════════════════════════════════════════════════════════

import hashlib
import hmac
import json
import os
from urllib.parse import parse_qsl
from pathlib import Path
from aiohttp import web
from aiogram.types import WebAppInfo, InlineKeyboardButton


# ─── Путь к HTML файлу Mini App ───────────────────────────────────
MINIAPP_HTML = Path(__file__).resolve().parent / "donatex_miniapp.html"
FREE_FIRE_MAX_IMAGE = Path(__file__).resolve().parent / "free-fire-max.png"


# ─── Вспомогательная: проверка подписи Telegram WebApp ────────────
def verify_tg_initdata(init_data: str, bot_token: str) -> dict | None:
    """
    Проверяет подпись initData от Telegram WebApp.
    Возвращает dict с данными пользователя или None если подпись неверна.
    """
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = pairs.pop("hash", "")
        # data_check_string: отсортированные пары key=value через \n
        data_check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        # secret_key = HMAC-SHA256(bot_token, "WebAppData")
        secret = hmac.new("WebAppData".encode(), bot_token.encode(), hashlib.sha256).digest()
        # Вычисляем ожидаемый хэш
        expected = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, received_hash):
            return None
        # Декодируем user
        user_json = pairs.get("user", "{}")
        return json.loads(user_json)
    except Exception as e:
        log.warning("verify_tg_initdata error: %s", e)
        return None


def get_or_create_user_by_tg(tg_user: dict) -> tuple[str, dict]:
    """Находит или создаёт пользователя по Telegram user dict."""
    uid = str(tg_user.get("id", ""))
    if not uid:
        return "", {}
    u = get_user(int(uid), 
                 tg_user.get("first_name", "") + (" " + tg_user.get("last_name", "") if tg_user.get("last_name") else ""),
                 tg_user.get("username", ""))
    return uid, u


# ═══════════════════════════════════════════════════════════════════
#  МАРШРУТЫ MINI APP
# ═══════════════════════════════════════════════════════════════════

async def h_miniapp_html(request: web.Request) -> web.Response:
    """Отдаёт HTML страницу Mini App."""
    if not MINIAPP_HTML.exists():
        return web.Response(text="Mini App HTML not found. Place donatex_miniapp.html next to main.py.", status=404)
    return web.FileResponse(MINIAPP_HTML)


async def h_free_fire_max_image(request: web.Request) -> web.Response:
    """Отдаёт локальную обложку Free Fire MAX для всех регионов."""
    if not FREE_FIRE_MAX_IMAGE.exists():
        return web.Response(text="Free Fire image not found. Place free-fire-max.png next to main.py.", status=404)
    return web.FileResponse(FREE_FIRE_MAX_IMAGE, headers={"Cache-Control": "public, max-age=86400"})


async def h_webapp_init(request: web.Request) -> web.Response:
    """
    POST /webapp/api/init
    Body: { initData: string }
    Response: { ok, user: {...}, links: {...} }
    """
    try:
        body = await request.json()
        init_data = body.get("initData", "")

        tg_user = None
        if init_data:
            tg_user = verify_tg_initdata(init_data, BOT_TOKEN)
            if tg_user is None and not os.environ.get("DEV_MODE"):
                return web.json_response({"message": "Invalid initData"}, status=401)

        photo_url = ""
        if tg_user:
            uid, u = get_or_create_user_by_tg(tg_user)
            photo_url = tg_user.get("photo_url") or ""
        else:
            pairs = dict(parse_qsl(init_data, keep_blank_values=True))
            raw_user = json.loads(pairs.get("user", "{}"))
            uid = str(raw_user.get("id", "dev"))
            u = get_user(int(uid) if uid.isdigit() else 0,
                         raw_user.get("first_name", "Dev"),
                         raw_user.get("username", ""))
            photo_url = raw_user.get("photo_url") or ""

        order_count = sum(1 for o in db["orders"] if str(o.get("uid")) == uid)
        uid_int = int(uid) if str(uid).isdigit() else 0

        # Ссылки для профиля Mini App
        news_ch = get_news_channel(uid_int) if uid_int else (NEWS_CHANNEL_TG or NEWS_CHANNEL_RU or "")
        reviews_url = ""
        if REVIEWS_CHANNEL:
            reviews_url = REVIEWS_CHANNEL if REVIEWS_CHANNEL.startswith("http") else f"https://t.me/{REVIEWS_CHANNEL.lstrip('@')}"
        bot_username = ""
        try:
            me = await bot.get_me()
            bot_username = me.username or ""
        except Exception:
            bot_username = ""
        ref_link = f"https://t.me/{bot_username}?start=ref_{uid}" if bot_username else ""

        return web.json_response({
            "ok": True,
            "user": {
                "id":        uid,
                "name":      u.get("name", ""),
                "username":  u.get("username", ""),
                "balance":   round(float(u.get("balance", 0)), 2),
                "lang":      u.get("lang", "tg"),
                "orders":    order_count,
                "photo_url": u.get("custom_avatar_url") or photo_url,
                "is_admin":  is_admin(uid_int),
                "customer_no": u.get("customer_no", 0),
                "vip": user_vip(uid),
                "achievements": refresh_achievements(uid),
                "wishlist_count": len(u.get("wishlist", [])),
            },
            "links": {
                "news":      news_ch or "",
                "reviews":   reviews_url,
                "support":   SUPPORT_CONTACT or "",
                "ref":       ref_link,
                "instagram": INSTAGRAM_URL or "",
                "tiktok":    TIKTOK_URL or "",
            },
        })
    except Exception as e:
        log.error("h_webapp_init: %s", e)
        return web.json_response({"message": str(e)}, status=500)


async def h_webapp_catalog(request: web.Request) -> web.Response:
    """
    GET /webapp/api/catalog
    Response: { categories: [...], popular: [...] }
    """
    try:
        await load_catalog()

        # Иконки игр (emoji + ключи для оригинальных логотипов на клиенте)
        ICONS = [
            ("delta force", "🪖"), ("deltaforce", "🪖"),
            ("free fire", "🔥"), ("freefire", "🔥"),
            ("pubg", "🎯"), ("mobile legends", "⚔️"), ("mlbb", "⚔️"),
            ("genshin", "✨"), ("honor of kings", "👑"), ("clash", "🏰"),
            ("telegram", "⭐"), ("stars", "⭐"), ("premium", "💜"),
            ("standoff", "🔫"), ("afk", "🗡️"), ("capcut", "🎬"),
            ("8 ball", "🎱"), ("ace racer", "🏎️"), ("arena", "🏟️"),
            ("age of", "🏰"), ("cod", "💥"), ("fc mobile", "⚽"),
            ("fifa mobile", "⚽"), ("ea fc", "⚽"),
        ]

        def pick_icon(name: str) -> str:
            nl = name.lower()
            for key, ic in ICONS:
                if key in nl:
                    return ic
            return "🎮"

        def game_key(name: str) -> str:
            nl = name.lower()
            # Delta Force и прочие Garena — не Free Fire
            if "delta force" in nl or "deltaforce" in nl:
                return "delta_force"
            # Free Fire только по явным словам (не любое "Garena")
            if "free fire" in nl or "freefire" in nl or re.search(r"\bff\b", nl):
                if any(x in nl for x in ("indonesia", "indon", "(id)", " id ", " id)")):
                    return "ff_id"
                return "ff_cis"
            if "pubg" in nl:
                return "pubg"
            if "standoff" in nl:
                return "standoff"
            if "fc mobile" in nl or "fifa mobile" in nl or "ea fc" in nl:
                return "fc_mobile"
            if "capcut" in nl or "cap cut" in nl:
                return "capcut"
            if "afk" in nl:
                return "afk"
            if "mobile legends" in nl or "mlbb" in nl:
                return "mlbb"
            if "stars" in nl or "premium" in nl or "telegram" in nl:
                return "stars"
            return "game"

        result = []
        by_key = {}
        for cid, cat in catalog.items():
            cat_name = cat.get("name", str(cid))
            icon = pick_icon(cat_name)
            gkey = game_key(cat_name)
            prods = []
            for p in cat.get("products", []):
                prods.append({
                    "product_id": p.get("product_id"),
                    "title":      ptitle(p, "ru"),
                    "price_tjs":  round(float(p.get("price_tjs", 0)), 2),
                    "price_usd":  round(float(p.get("price_usd", 0)), 2),
                    "type":       p.get("kind", "topup"),
                })
            if prods:
                cat_name_l = str(cat_name or "").lower()
                is_ff_category = (
                    "free fire" in cat_name_l or "freefire" in cat_name_l
                    or re.search(r"\bff\b", cat_name_l) is not None
                )
                img = (
                    "/webapp/assets/free-fire-max.png" if is_ff_category else
                    (cat.get("image") or cat.get("icon_url") or cat.get("logo")
                     or get_game_icon_url(cat_name))
                )
                item = {
                    "id":       str(cid),
                    "name":     cat_name,
                    "icon":     icon,
                    "gkey":     gkey,
                    "image":    img,
                    "products": prods,
                }
                result.append(item)
                by_key.setdefault(gkey, item)

        # Stars и Premium — отдельными категориями, все пакеты
        star_prods = []
        if special.get("stars"):
            s = special["stars"]
            # Полный набор популярных пакетов Stars
            for qty in [50, 75, 100, 150, 250, 350, 500, 750, 1000, 1500, 2500, 5000]:
                if s.get("min", 0) <= qty <= s.get("max", 10**9):
                    star_prods.append({
                        "product_id": f"tg-stars-{qty}",
                        "title":      f"{qty} Stars",
                        "price_tjs":  round(qty * s["unit"] * usd_tjs * (1 + MARGIN), 2),
                        "price_usd":  round(qty * s["unit"], 2),
                        "type":       "stars",
                        "qty":        qty,
                    })
        prem_prods = []
        for pid, p in sorted((special.get("premium") or {}).items(), key=lambda x: x[0]):
            months = 1
            m = re.search(r"(\d+)", str(pid))
            if m:
                months = int(m.group(1))
            title = ptitle(p, "ru") or f"Premium {months} мес."
            prem_prods.append({
                "product_id": pid,
                "title":      title,
                "price_tjs":  round(float(p.get("price_usd", 0)) * usd_tjs * (1 + MARGIN), 2),
                "price_usd":  round(float(p.get("price_usd", 0)), 2),
                "type":       "premium",
                "months":     months,
            })
        if star_prods:
            stars_item = {
                "id": "stars", "name": "Telegram Stars ⭐", "icon": "⭐",
                "gkey": "stars",
                "image": GAME_ICONS.get("Telegram Stars ⭐", ""),
                "products": star_prods,
            }
            result.append(stars_item)
            by_key["stars"] = stars_item
        if prem_prods:
            prem_item = {
                "id": "premium", "name": "Telegram Premium 💜", "icon": "💜",
                "gkey": "premium",
                "image": GAME_ICONS.get("Telegram Premium 💜", ""),
                "products": prem_prods,
            }
            result.append(prem_item)
            by_key["premium"] = prem_item

        # Популярные: сначала ищем через match_game (точные регионы), потом by_key
        popular_order = ["ff_cis", "ff_id", "pubg", "standoff", "fc_mobile", "capcut"]
        labels = {
            "ff_cis": ("Free Fire СНГ", "🔥"),
            "ff_id": ("Free Fire Indonesia", "🇮🇩"),
            "pubg": ("PUBG Mobile", "🎯"),
            "standoff": ("Standoff 2", "🔫"),
            "fc_mobile": ("EA FC Mobile", "⚽"),
            "capcut": ("CapCut", "🎬"),
        }
        popular = []
        for k in popular_order:
            item = None
            # match_game знает регионы FF / PUBG лучше, чем простой gkey
            try:
                mid = match_game(k if k != "pubg" else "pubg")
                if mid is None and k == "pubg":
                    mid = match_game("pubg_us")
                if mid is not None:
                    item = next((x for x in result if x["id"] == str(mid)), None)
            except Exception:
                item = None
            if item is None:
                item = by_key.get(k)
            if item:
                popular.append({
                    "id": item["id"],
                    "name": item["name"],
                    "icon": item.get("icon") or labels[k][1],
                    "gkey": k,
                    "image": item.get("image") or get_game_icon_url(item.get("name", "")),
                    "count": len(item.get("products") or []),
                })
            else:
                name, ic = labels[k]
                popular.append({
                    "id": k, "name": name, "icon": ic, "gkey": k,
                    "image": get_game_icon_url(name),
                    "count": 0,
                })

        # Магазин: приоритетные игры сверху (FF → PUBG → Standoff → EA FC → CapCut → остальное)
        prio = {"ff_cis": 0, "ff_id": 1, "pubg": 2, "standoff": 3, "fc_mobile": 4, "capcut": 5, "stars": 6, "premium": 7}
        result.sort(key=lambda x: (prio.get(x.get("gkey"), 50), x.get("name", "").lower()))

        return web.json_response({"categories": result, "popular": popular})
    except Exception as e:
        log.error("h_webapp_catalog: %s", e)
        return web.json_response({"message": str(e)}, status=500)


async def h_webapp_nick(request: web.Request) -> web.Response:
    """
    GET /webapp/api/nick?product_id=...&player_id=...
    Response: { nick: string }
    """
    try:
        product_id = request.rel_url.query.get("product_id", "")
        player_id  = request.rel_url.query.get("player_id", "")
        if not product_id or not player_id:
            return web.json_response({"nick": ""})

        # Находим продукт в каталоге
        product = None
        for cat in catalog.values():
            for p in cat.get("products", []):
                if p.get("product_id") == product_id:
                    product = p
                    break
            if product:
                break

        nick = await lookup_player_nick(product or {"product_id": product_id}, player_id)
        return web.json_response({"nick": nick})
    except Exception as e:
        log.warning("h_webapp_nick: %s", e)
        return web.json_response({"nick": ""})


async def h_webapp_order(request: web.Request) -> web.Response:
    """
    POST /webapp/api/order
    Headers: X-TG-Init-Data
    Body: { product_id, player_id, price_tjs }
    Response: { ok, order_id, balance }
    """
    try:
        init_data = request.headers.get("X-TG-Init-Data", "")
        body = await request.json()

        # Аутентификация
        tg_user = verify_tg_initdata(init_data, BOT_TOKEN)
        if tg_user is None and not os.environ.get("DEV_MODE"):
            return web.json_response({"message": "Unauthorized"}, status=401)
        if tg_user is None:
            pairs = dict(parse_qsl(init_data, keep_blank_values=True))
            tg_user = json.loads(pairs.get("user", "{}"))

        uid_int = int(tg_user.get("id", 0))
        uid = str(uid_int)
        u = get_user(uid_int)

        # Находим продукт
        product_id = body.get("product_id", "")
        player_id  = str(body.get("player_id", ""))
        price_tjs  = float(body.get("price_tjs", 0))

        product = None
        for cat in catalog.values():
            for p in cat.get("products", []):
                if p.get("product_id") == product_id:
                    product = p
                    break
            if product:
                break

        if not product:
            # Поищем в special
            if product_id in special.get("premium", {}):
                product = special["premium"][product_id]
            elif product_id.startswith("tg-stars-"):
                qty = int(product_id.split("-")[-1])
                s = special.get("stars") or {}
                unit = float(s.get("unit") or 0.02)
                product = {
                    "product_id": product_id,
                    "title": f"{qty} Stars",
                    "price_usd": qty * unit,
                    "price_tjs": round(qty * unit * usd_tjs * (1 + MARGIN), 2),
                    "type": "stars",
                }

        if not product:
            return web.json_response({"message": "Товар не найден"}, status=404)

        # Проверяем баланс
        price = round(float(product.get("price_tjs", price_tjs)), 2)
        if u["balance"] < price:
            return web.json_response({"message": "insufficient_balance"}, status=402)

        # Блокировка двойного заказа
        async with user_locks[uid]:
            # Списываем баланс
            u["balance"] = round(u["balance"] - price, 2)
            add_transaction(uid_int, -price, "order", ptitle(product, "ru"))
            save_db()

            oid = str(uuid.uuid4())[:8].upper()
            ts = now_ts()

            # Размещаем заказ через Donatix API
            order_status = "processing"
            order_error  = ""
            try:
                # Stars: API product_id = "tg-stars", quantity = N
                # Premium: product_id = tg-premium-N, fields.username
                # Игры: product_id + fields.player_id
                api_pid = product_id
                api_qty = 1
                fields = {"player_id": player_id}
                if product_id.startswith("tg-stars-"):
                    api_pid = "tg-stars"
                    api_qty = int(product_id.split("-")[-1])
                    fields = {"username": player_id.lstrip("@")}
                elif (
                    product.get("kind") == "telegram_premium"
                    or product_id.startswith("tg_prem")
                    or product_id.startswith("tg-premium")
                    or product.get("type") == "premium"
                ):
                    fields = {"username": player_id.lstrip("@")}

                async with aiohttp.ClientSession() as sess:
                    async with sess.post(
                        f"{API}/orders",
                        json={"product_id": api_pid, "quantity": api_qty, "fields": fields},
                        headers={**HEADERS, "Content-Type": "application/json"},
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as r:
                        resp = await r.json(content_type=None)

                if resp.get("status") in ("success", "completed", "processing", "pending"):
                    order_status = "done" if resp.get("status") in ("success","completed") else "processing"
                else:
                    raise Exception(resp.get("message") or resp.get("error") or "API error")

            except asyncio.TimeoutError:
                order_status = "uncertain"
            except Exception as err:
                order_error = str(err)
                # Возвращаем деньги при ошибке
                u["balance"] = round(u["balance"] + price, 2)
                add_transaction(uid_int, +price, "refund", "Возврат: " + str(err)[:40])
                save_db()
                return web.json_response({"message": order_error}, status=500)

            # Сохраняем заказ
            order = {
                "oid":        oid,
                "uid":        uid,
                "product_id": product_id,
                "title":      ptitle(product, "ru"),
                "player_id":  player_id,
                "price":      price,
                "status":     order_status,
                "ts":         ts,
            }
            db["orders"].append(order)
            # Каждая подтверждённая успешная покупка даёт ровно один кредит настройки.
            # processing/uncertain не считаем выполненной покупкой.
            if order_status in ("done", "processing"):
                u["sensitivity_credits"] = int(u.get("sensitivity_credits", 0)) + 1
            save_db()

            # Уведомление админу
            await notify_admin(
                f"🌐 <b>Mini App заказ</b> #{oid}\n"
                f"👤 ID {uid} · {u.get('name','')} · @{u.get('username','')}\n"
                f"📦 {ptitle(product,'ru')}\n"
                f"🆔 {player_id}\n"
                f"💰 {price} TJS\n"
                f"📊 {order_status}"
            )

            return web.json_response({
                "ok":      True,
                "order_id": oid,
                "balance":  round(u["balance"], 2),
                "status":   order_status,
            })

    except Exception as e:
        log.error("h_webapp_order: %s", e)
        return web.json_response({"message": str(e)}, status=500)




async def h_webapp_sensitivity(request: web.Request) -> web.Response:
    """Внутренние настройки Free Fire: GET — баланс кредитов, POST — применить пресет."""
    try:
        init_data = request.headers.get("X-TG-Init-Data", "")
        tg_user = verify_tg_initdata(init_data, BOT_TOKEN)
        if tg_user is None and not os.environ.get("DEV_MODE"):
            return web.json_response({"message": "Unauthorized"}, status=401)
        if tg_user is None:
            pairs = dict(parse_qsl(init_data, keep_blank_values=True))
            tg_user = json.loads(pairs.get("user", "{}"))
        uid = int(tg_user.get("id", 0))
        u = get_user(uid, tg_user.get("first_name", ""), tg_user.get("username", ""))
        free_left = not bool(u.get("free_sensitivity_used"))
        credits = max(0, int(u.get("sensitivity_credits", 0)))
        if request.method == "GET":
            return web.json_response({"free_left": free_left, "credits": credits,
                                      "available": int(free_left) + credits})
        body = await request.json()
        device = str(body.get("device") or "").strip()[:80]
        if not device:
            return web.json_response({"message": "Выберите модель телефона"}, status=400)
        if not free_left and credits <= 0:
            return web.json_response({"message": "Нет доступных настроек. Совершите покупку."}, status=403)
        if free_left:
            u["free_sensitivity_used"] = True
        else:
            u["sensitivity_credits"] = credits - 1
        u["last_sensitivity_device"] = device
        save_db()
        return web.json_response({
            "ok": True, "device": device,
            "remaining": int(not u.get("free_sensitivity_used")) + int(u.get("sensitivity_credits", 0)),
            "values": [200, 190, 185, 180, 170, 160],
            "labels": ["Обзор", "Коллиматор", "2x Прицел", "4x Прицел", "Снайперский прицел", "Свободная камера"]
        })
    except Exception as e:
        log.error("h_webapp_sensitivity: %s", e)
        return web.json_response({"message": str(e)}, status=500)


async def h_webapp_top_donors(request: web.Request) -> web.Response:
    """Рейтинг по сумме подтверждённых заказов."""
    try:
        totals = {}
        for order in db.get("orders", []):
            if order.get("status") != "done":
                continue
            uid = str(order.get("uid", ""))
            if not uid:
                continue
            totals[uid] = totals.get(uid, 0.0) + float(order.get("price", 0) or 0)
        ranked = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:50]
        result = []
        for uid, amount in ranked:
            u = db.get("users", {}).get(uid, {})
            result.append({"name": u.get("name") or ("Покупатель " + uid[-4:]),
                           "username": u.get("username") or "", "amount": round(amount, 2)})
        return web.json_response({"items": result})
    except Exception as e:
        log.error("h_webapp_top_donors: %s", e)
        return web.json_response({"message": str(e)}, status=500)


async def h_webapp_orders(request: web.Request) -> web.Response:
    """
    GET /webapp/api/orders
    Headers: X-TG-Init-Data
    Response: { orders: [...] }
    """
    try:
        init_data = request.headers.get("X-TG-Init-Data", "")
        tg_user = verify_tg_initdata(init_data, BOT_TOKEN)
        if tg_user is None and not os.environ.get("DEV_MODE"):
            return web.json_response({"message": "Unauthorized"}, status=401)
        if tg_user is None:
            pairs = dict(parse_qsl(init_data, keep_blank_values=True))
            tg_user = json.loads(pairs.get("user", "{}"))

        uid = str(tg_user.get("id", ""))
        mine = [o for o in db["orders"] if str(o.get("uid")) == uid]
        mine = sorted(mine, key=lambda x: x.get("ts", 0), reverse=True)[:20]

        return web.json_response({"orders": [{
            "oid":    o.get("oid", "—"),
            "title":  o.get("title", "Заказ"),
            "status": o.get("status", "processing"),
            "ts":     o.get("ts", 0),
            "price":  round(float(o.get("price", 0)), 2),
        } for o in mine]})
    except Exception as e:
        log.error("h_webapp_orders: %s", e)
        return web.json_response({"message": str(e)}, status=500)


async def h_webapp_topup(request: web.Request) -> web.Response:
    """
    POST /webapp/api/topup
    Body: { method: 'dc'|'alif', amount: float }
    Отправляет инструкции пополнения в Telegram чат пользователя.
    """
    try:
        init_data = request.headers.get("X-TG-Init-Data", "")
        body = await request.json()

        tg_user = verify_tg_initdata(init_data, BOT_TOKEN)
        if tg_user is None and not os.environ.get("DEV_MODE"):
            return web.json_response({"message": "Unauthorized"}, status=401)
        if tg_user is None:
            pairs = dict(parse_qsl(init_data, keep_blank_values=True))
            tg_user = json.loads(pairs.get("user", "{}"))

        uid_int = int(tg_user.get("id", 0))
        method  = body.get("method", "dc")
        amount  = float(body.get("amount", 0))

        if amount < 2 or amount > 5000:
            return web.json_response({"message": "Недопустимая сумма"}, status=400)

        pm = PAY_METHODS.get(method)
        if not pm:
            return web.json_response({"message": "Способ оплаты недоступен"}, status=400)

        holder_line = f" ({pm['holder']})" if pm.get("holder") else ""
        instr = (
            f"💳 <b>{pm['title']}</b>\n\n"
            f"1️⃣ Переведите на: <code>{pm['number']}</code>{holder_line}\n"
            f"💵 Сумма: <b>{amount:.2f} TJS</b>\n\n"
            f"2️⃣ Отправьте фото чека здесь 📸\n"
            f"Администратор зачислит сумму на баланс.\n\n"
            f"<i>❗ Не отправляйте один чек дважды.</i>"
        )

        # Если запрос через DC Pay URL
        if method == "dc" and DC_PAY_URL:
            pay_link = payment_url("dc", amount)
            if pay_link:
                from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
                markup = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🏙 Оплатить через DC", url=pay_link)
                ]])
                try:
                    await bot.send_message(uid_int, instr, reply_markup=markup)
                except Exception:
                    await bot.send_message(uid_int, instr)
            else:
                await bot.send_message(uid_int, instr)
        else:
            await bot.send_message(uid_int, instr)

        # Переводим пользователя в состояние ожидания чека
        user_state[uid_int] = {
            "stage": "topup_receipt",
            "method": method,
            "amount": amount,
        }

        return web.json_response({"ok": True})

    except Exception as e:
        log.error("h_webapp_topup: %s", e)
        return web.json_response({"message": str(e)}, status=500)


async def h_webapp_support(request: web.Request) -> web.Response:
    """
    POST /webapp/api/support
    Body: { message: string }
    Отправляет обращение в поддержку из Mini App (без выхода в бот).
    """
    try:
        init_data = request.headers.get("X-TG-Init-Data", "")
        body = await request.json()
        msg_text = (body.get("message") or "").strip()
        if not msg_text or len(msg_text) < 3:
            return web.json_response({"message": "Слишком короткое сообщение"}, status=400)
        if len(msg_text) > 2000:
            return web.json_response({"message": "Слишком длинное сообщение"}, status=400)

        tg_user = verify_tg_initdata(init_data, BOT_TOKEN)
        if tg_user is None and not os.environ.get("DEV_MODE"):
            return web.json_response({"message": "Unauthorized"}, status=401)
        if tg_user is None:
            pairs = dict(parse_qsl(init_data, keep_blank_values=True))
            tg_user = json.loads(pairs.get("user", "{}"))

        uid_int = int(tg_user.get("id", 0))
        u = get_user(uid_int, tg_user.get("first_name", ""), tg_user.get("username", ""))
        u["support_last_ts"] = now_ts()
        save_db()

        admin_text = (
            f"🆘 <b>Поддержка из Mini App</b>\n"
            f"👤 {esc(u.get('name',''))} · @{esc(u.get('username') or '—')} · ID <code>{uid_int}</code>\n"
            f"💬 {esc(msg_text)}"
        )
        if ADMIN_ID:
            try:
                from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
                kb_admin = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="↩️ Ответить", callback_data=f"support_reply:{uid_int}")
                ]])
                await bot.send_message(ADMIN_ID, admin_text, reply_markup=kb_admin)
            except Exception as e:
                log.warning("support notify admin: %s", e)
                await notify_admin(admin_text)

        return web.json_response({"ok": True})
    except Exception as e:
        log.error("h_webapp_support: %s", e)
        return web.json_response({"message": str(e)}, status=500)


async def h_webapp_lang(request: web.Request) -> web.Response:
    """
    POST /webapp/api/lang
    Body: { lang: 'tg'|'ru'|'en' }
    """
    try:
        init_data = request.headers.get("X-TG-Init-Data", "")
        body = await request.json()
        lang = (body.get("lang") or "tg").lower()
        if lang not in ("tg", "ru", "en"):
            return web.json_response({"message": "Unsupported language"}, status=400)

        tg_user = verify_tg_initdata(init_data, BOT_TOKEN)
        if tg_user is None and not os.environ.get("DEV_MODE"):
            return web.json_response({"message": "Unauthorized"}, status=401)
        if tg_user is None:
            pairs = dict(parse_qsl(init_data, keep_blank_values=True))
            tg_user = json.loads(pairs.get("user", "{}"))

        uid_int = int(tg_user.get("id", 0))
        u = get_user(uid_int)
        u["lang"] = lang
        save_db()
        return web.json_response({"ok": True, "lang": lang})
    except Exception as e:
        log.error("h_webapp_lang: %s", e)
        return web.json_response({"message": str(e)}, status=500)


# ═══════════════════════════════════════════════════════════════════
#  КАК ДОБАВИТЬ МАРШРУТЫ В main()
# ═══════════════════════════════════════════════════════════════════
#
#  В функции async def main() найдите app.add_routes([...])
#  и добавьте эти строки:
#
#  app.add_routes([
#      web.get("/",                          h_health),
#      web.post("/webapp/api/web_login",     h_web_login),
#
#      # ──── Mini App маршруты ────
#      web.get("/webapp/",                   h_miniapp_html),   # ← HTML страница
#      web.get("/webapp",                    h_miniapp_html),
#      web.post("/webapp/api/init",          h_webapp_init),
#      web.get("/webapp/api/catalog",        h_webapp_catalog),
#      web.get("/webapp/api/nick",           h_webapp_nick),
#      web.post("/webapp/api/order",         h_webapp_order),
#      web.get("/webapp/api/orders",         h_webapp_orders),
#      web.post("/webapp/api/topup",         h_webapp_topup),
#  ])
#
# ═══════════════════════════════════════════════════════════════════
#  КАК ДОБАВИТЬ КНОПКУ MINI APP В БОТА
# ═══════════════════════════════════════════════════════════════════
#
#  В функции send_menu() добавьте кнопку WebApp в rows:
#
#  from aiogram.types import WebAppInfo
#  MINIAPP_URL = EXTERNAL_URL + "/webapp/"
#
#  rows.insert(0, [InlineKeyboardButton(
#      text="⚡ Открыть DONATEX Mini App",
#      web_app=WebAppInfo(url=MINIAPP_URL)
#  )])
#
# ═══════════════════════════════════════════════════════════════════
#  ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ (Render.com)
# ═══════════════════════════════════════════════════════════════════
#
#  DEV_MODE=1   — отключает проверку подписи (только для разработки!)
#
# ═══════════════════════════════════════════════════════════════════


# ================= DONATEX EXTENSIONS =================
VIP_LEVELS = [("Бронза", 0), ("Серебро", 500), ("Золото", 2000), ("Платина", 5000)]
def user_lifetime_spend(uid):
    return round(sum(float(o.get("price", 0)) for o in db["orders"] if str(o.get("uid")) == str(uid) and o.get("status") != "failed"), 2)
def user_vip(uid):
    spent=user_lifetime_spend(uid); cur=VIP_LEVELS[0]; nxt=None
    for i,x in enumerate(VIP_LEVELS):
        if spent >= x[1]: cur=x; nxt=VIP_LEVELS[i+1] if i+1<len(VIP_LEVELS) else None
    return {"name":cur[0],"spent":spent,"next":nxt[0] if nxt else None,"remaining":round(max(0,nxt[1]-spent),2) if nxt else 0}
def refresh_achievements(uid):
    u=get_user(uid); orders=[o for o in db["orders"] if str(o.get("uid"))==str(uid) and o.get("status") in ("done","processing","completed")]
    a=set(u.get("achievements",[]))
    if orders:a.add("first_order")
    if len(orders)>=10:a.add("ten_orders")
    ranked=sorted(((user_lifetime_spend(k),str(k)) for k in db["users"]), reverse=True)
    if orders and ranked and ranked[0][1]==str(uid):a.add("top_donor")
    u["achievements"]=sorted(a); save_db(); return u["achievements"]

@dp.message(Command("sensitivity"))
async def command_sensitivity(m):
    class C:
        def __init__(self): self.message=m; self.from_user=m.from_user
        async def answer(self,*a,**k): pass
    await cb_ff_sens(C())

@dp.message(Command("outfit"))
async def command_outfit(m, command: CommandObject):
    q=(command.args or "").lower()
    if "mlbb" in q: msg="👕 <b>MLBB:</b> Герои → выберите героя → Скины. Подбирайте скин по тематике события и сочетающимся цветам эффектов."
    elif "pubg" in q: msg="🔥 <b>PUBG Mobile:</b> Инвентарь → Одежда. Сочетайте костюм, шлем и рюкзак в одной палитре; сохраните комплект как пресет."
    else: msg="👕 Аутфиты:\n/outfit mlbb — Mobile Legends\n/outfit pubg — PUBG Mobile"
    await m.answer(msg)

@dp.message(Command("wish"))
async def command_wish(m, command: CommandObject):
    u=get_user(m.from_user.id); q=(command.args or "").strip()
    if not q or q.lower()=="list":
        await m.answer("💜 Вишлист:\n"+("\n".join("• "+esc(str(x)) for x in u.get("wishlist",[])) or "Пусто")+"\nДобавить: /wish PRODUCT_ID\nУдалить: /wish remove PRODUCT_ID"); return
    if q.lower().startswith("remove "):
        pid=q.split(maxsplit=1)[1]; u["wishlist"]=[x for x in u.get("wishlist",[]) if str(x)!=pid]; save_db(); await m.answer("✅ Удалено."); return
    pid=q.split()[0]; await load_catalog()
    prod=next((x for c in catalog.values() for x in c.get("products",[]) if str(x.get("product_id"))==pid),None)
    if not prod: await m.answer("❌ Товар не найден. Укажите product_id из каталога."); return
    if pid not in u.setdefault("wishlist",[]): u["wishlist"].append(pid)
    save_db(); await m.answer(f"💜 Добавлено: {esc(prod.get('title',pid))}. Бот будет отслеживать снижение цены при обновлении каталога.")

@dp.message(Command("news"))
async def command_news(m):
    ch=get_news_channel(m.from_user.id); await m.answer("📰 Новости игр: "+esc(ch) if ch else "📰 Новостной канал не настроен.")

@dp.message(Command("stats"))
async def command_stats(m):
    if is_admin(m.from_user.id): await m.answer(stats_text())

@dp.message(Command("export"))
async def command_export(m, command: CommandObject):
    if not is_admin(m.from_user.id): return
    try: days=max(1,min(3650,int((command.args or "30").strip())))
    except ValueError: days=30
    cutoff=time.time()-days*86400; buf=io.StringIO(); w=csv.writer(buf)
    w.writerow(["order_id","user_id","title","player_id","price_tjs","status","timestamp"])
    rows=[o for o in db["orders"] if float(o.get("ts",0))>=cutoff]
    for o in rows:w.writerow([o.get("oid"),o.get("uid"),o.get("title"),o.get("player_id"),o.get("price"),o.get("status"),o.get("ts")])
    await m.answer_document(BufferedInputFile(buf.getvalue().encode("utf-8-sig"),filename=f"donatex_orders_{days}d.csv"),caption=f"Экспорт за {days} дней: {len(rows)} заказов")

@dp.message(Command("give_voucher"))
async def command_give_voucher(m, command: CommandObject):
    if not is_admin(m.from_user.id): return
    a=(command.args or "").split()
    if len(a)<3: await m.answer("Формат: /give_voucher USER_ID CODE PERCENT"); return
    uid,code=a[0],a[1].upper()
    try:pct=int(a[2])
    except ValueError:pct=0
    if uid not in db["users"] or not re.fullmatch(r"[A-Z0-9_-]{3,20}",code) or not 1<=pct<=90: await m.answer("❌ Проверьте ID, код и скидку 1–90%."); return
    db["promos"][code]={"percent":pct,"max_uses":1,"used":0,"active":True,"users":[],"assigned_uid":uid}; get_user(uid)["promo"]=code; save_db()
    try: await bot.send_message(int(uid),f"🎟 Вам выдан ваучер <b>{code}</b>: скидка {pct}%!")
    except Exception: pass
    await m.answer(f"✅ Ваучер {code} (-{pct}%) назначен пользователю {uid}.")

@dp.message(Command("block_temp"))
async def command_block_temp(m, command: CommandObject):
    if not is_admin(m.from_user.id): return
    a=(command.args or "").split()
    if len(a)!=2: await m.answer("Формат: /block_temp USER_ID ЧАСЫ"); return
    try: hours=max(1,min(720,int(a[1])))
    except ValueError: hours=0
    if a[0] not in db["users"] or not hours: await m.answer("❌ Пользователь не найден или неверное число часов."); return
    get_user(a[0])["blocked_until"]=int(time.time()+hours*3600); save_db(); await m.answer(f"⏳ Временная блокировка {a[0]} на {hours} ч. записана.")

async def customer_low_balance_watcher():
    threshold = float(os.getenv("USER_LOW_BALANCE_TJS", "20"))
    while True:
        await asyncio.sleep(3600)
        now = int(time.time())
        for uid, u in db["users"].items():
            if u.get("blocked") or float(u.get("balance", 0)) >= threshold:
                continue
            if now - int(u.get("topup_reminded_at", 0)) < 86400:
                continue
            try:
                await bot.send_message(int(uid), f"💰 Ваш баланс ниже {threshold:.2f} TJS. Пополните его, чтобы быстро оформлять заказы.")
                u["topup_reminded_at"] = now
                save_db()
            except Exception:
                pass

async def wishlist_price_watcher():
    while True:
        await asyncio.sleep(900)
        try:
            await load_catalog(force=True)
            current={str(p.get("product_id")):float(p.get("price_tjs") or 0) for c in catalog.values() for p in c.get("products",[]) if p.get("product_id") and float(p.get("price_tjs") or 0)>0}
            previous=db.setdefault("price_snapshots",{})
            for uid,u in db["users"].items():
                for pid in set(u.get("wishlist",[]) + u.get("favorites",[])):
                    old,new=previous.get(str(pid)),current.get(str(pid))
                    if old and new and new<float(old)-.001:
                        try: await bot.send_message(int(uid),f"🔔 Цена снизилась для товара {pid}: {old:.2f} → {new:.2f} TJS")
                        except Exception: pass
            db["price_snapshots"]=current; save_db()
        except Exception as e: log.warning("wishlist watcher: %s",e)



# ===================== DONATEX: расширенные функции Mini App =====================
async def _web_user(request):
    init_data = request.headers.get('X-TG-Init-Data', '')
    tg = verify_tg_initdata(init_data, BOT_TOKEN)
    if tg is None and not os.environ.get('DEV_MODE'):
        raise web.HTTPUnauthorized(text='Unauthorized')
    if tg is None:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        tg = json.loads(pairs.get('user', '{}'))
    uid = str(tg.get('id') or '')
    if not uid.isdigit(): raise web.HTTPUnauthorized(text='Invalid user')
    u = get_user(int(uid), tg.get('first_name',''), tg.get('username',''))
    if u.get('blocked') and not is_admin(int(uid)):
        raise web.HTTPForbidden(text='Аккаунт временно заблокирован')
    return uid, u

def _push_notice(uid, title, body, kind='info', data=None):
    u=get_user(int(uid)); arr=u.setdefault('notifications',[])
    arr.insert(0, {'id':secrets.token_hex(6),'title':str(title)[:100],'body':str(body)[:500],
                   'kind':kind,'data':data or {},'ts':now_ts(),'read':False})
    u['notifications']=arr[:100]; save_db()

async def h_features(request):
    try:
        uid,u=await _web_user(request)
        orders=[o for o in db['orders'] if str(o.get('uid'))==uid]
        tx=u.get('transactions',[])
        spent=sum(float(o.get('price') or 0) for o in orders if o.get('status') not in ('failed','cancelled'))
        fav=u.setdefault('favorite_games',[])
        return web.json_response({'ok':True,'favorite_games':fav,'notifications':u.get('notifications',[])[:50],
          'topups':[x for x in tx if 'topup' in str(x.get('type','')).lower() or 'пополн' in str(x.get('desc','')).lower()][-100:][::-1],
          'spending':{'total':round(spent,2),'orders':len(orders),'by_month':_monthly_spend(orders)},
          'countdown':db.get('meta',{}).get('promo_countdown',{}),'favorites':u.get('favorites',[]),
          'saved_payment':u.get('saved_payment_method',''),'favorite_games_limit':5})
    except web.HTTPException: raise
    except Exception as e: return web.json_response({'message':str(e)},status=500)

def _monthly_spend(orders):
    out={}
    for o in orders:
        if o.get('status') in ('failed','cancelled'): continue
        try: key=datetime.fromtimestamp(int(o.get('ts') or 0),TZ).strftime('%Y-%m')
        except Exception: continue
        out[key]=round(out.get(key,0)+float(o.get('price') or 0),2)
    return [{'month':k,'amount':v} for k,v in sorted(out.items())[-12:]]

async def h_features_update(request):
    try:
        uid,u=await _web_user(request); d=await request.json(); action=d.get('action')
        if action=='favorites':
            vals=list(dict.fromkeys(str(x) for x in d.get('games',[]) if str(x) in {str(k) for k in catalog.keys()}))[:5]
            u['favorite_games']=vals
        elif action=='favorite_product':
            pid=str(d.get('product_id',''))[:100]; a=u.setdefault('favorites',[])
            if pid in a:a.remove(pid)
            elif pid:a.append(pid)
            u['favorites']=a[:100]
        elif action=='saved_payment':
            # Только предпочтение метода. PAN/CVV никогда не сохраняются.
            method=str(d.get('method',''))
            if method not in ('dc','alif','') : return web.json_response({'message':'Invalid method'},status=400)
            u['saved_payment_method']=method
        elif action=='read_notifications':
            ids=set(map(str,d.get('ids',[])))
            for n in u.get('notifications',[]):
                if not ids or n.get('id') in ids:n['read']=True
        elif action=='countdown':
            if not is_admin(int(uid)): return web.json_response({'message':'Forbidden'},status=403)
            end=int(d.get('end_ts') or 0); label=str(d.get('label') or 'Акция')[:80]
            db.setdefault('meta',{})['promo_countdown']={'end_ts':end,'label':label,'active':end>now_ts()}; save_db()
        elif action=='avatar':
            # Avatar is stored as a Telegram-provided photo URL; arbitrary binary uploads handled separately.
            url=str(d.get('url',''))
            if not url.startswith('https://') or len(url)>1000:return web.json_response({'message':'Invalid avatar URL'},status=400)
            u['custom_avatar_url']=url
        else:return web.json_response({'message':'Unknown action'},status=400)
        save_db(); return web.json_response({'ok':True})
    except web.HTTPException: raise
    except Exception as e:return web.json_response({'message':str(e)},status=500)

async def h_avatar_upload(request):
    try:
        uid,u=await _web_user(request); reader=await request.multipart(); field=await reader.next()
        if field is None or field.name!='avatar':return web.json_response({'message':'avatar required'},status=400)
        filename=Path(field.filename or 'avatar.jpg').name
        ext=Path(filename).suffix.lower()
        if ext not in ('.jpg','.jpeg','.png','.webp'):return web.json_response({'message':'Only JPG, PNG, WEBP'},status=400)
        data=await field.read(decode=False)
        if len(data)>2*1024*1024:return web.json_response({'message':'Max 2 MB'},status=413)
        if not data.startswith((b'\xff\xd8\xff',b'\x89PNG\r\n\x1a\n',b'RIFF')):return web.json_response({'message':'Invalid image'},status=400)
        folder=AVATAR_DIR;folder.mkdir(parents=True,exist_ok=True)
        name=f'{uid}_{secrets.token_hex(5)}{ext}';(folder/name).write_bytes(data)
        u['custom_avatar_url']=f'/webapp/uploads/avatars/{name}';save_db()
        return web.json_response({'ok':True,'url':u['custom_avatar_url']})
    except web.HTTPException:raise
    except Exception as e:return web.json_response({'message':str(e)},status=500)

async def h_avatar_file(request):
    name=Path(request.match_info.get('name','')).name
    f=AVATAR_DIR/name
    if not f.exists():return web.Response(status=404)
    return web.FileResponse(f,headers={'Cache-Control':'public,max-age=86400'})

async def h_receipt_pdf(request):
    try:
        uid,u=await _web_user(request); oid=str(request.match_info.get('oid',''))
        order=next((o for o in db['orders'] if str(o.get('uid'))==uid and str(o.get('oid'))==oid),None)
        if not order:return web.json_response({'message':'Заказ не найден'},status=404)
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            buf=io.BytesIO(); c=canvas.Canvas(buf,pagesize=A4)
            c.setTitle('DONATEX receipt'); c.setFont('Helvetica-Bold',18);c.drawString(55,790,'DONATEX — ORDER RECEIPT')
            c.setFont('Helvetica',11); lines=[f"Order: {oid}",f"Customer: {u.get('name','')}",f"Product: {order.get('title','')}",f"Amount: {float(order.get('price') or 0):.2f} TJS",f"Status: {order.get('status','processing')}",f"Date: {datetime.fromtimestamp(int(order.get('ts') or now_ts()),TZ).strftime('%Y-%m-%d %H:%M')} (Dushanbe)"]
            y=745
            for line in lines:c.drawString(55,y,line[:100]);y-=25
            c.drawString(55,590,'Thank you for choosing DONATEX!');c.save();buf.seek(0)
            return web.Response(body=buf.read(),content_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="DONATEX_{oid}.pdf"'})
        except ImportError:return web.json_response({'message':'PDF engine missing: add reportlab to requirements.txt'},status=501)
    except web.HTTPException:raise
    except Exception as e:return web.json_response({'message':str(e)},status=500)

async def h_order_track(request):
    try:
        uid,u=await _web_user(request);oid=str(request.match_info.get('oid',''))
        o=next((x for x in db['orders'] if str(x.get('uid'))==uid and str(x.get('oid'))==oid),None)
        if not o:return web.json_response({'message':'Заказ не найден'},status=404)
        return web.json_response({'ok':True,'order':{k:o.get(k) for k in ('oid','title','price','status','ts','result','message')}})
    except web.HTTPException:raise
    except Exception as e:return web.json_response({'message':str(e)},status=500)

async def h_share_order(request):
    try:
        uid,u=await _web_user(request);d=await request.json();oid=str(d.get('oid',''))
        o=next((x for x in db['orders'] if str(x.get('uid'))==uid and str(x.get('oid'))==oid),None)
        if not o:return web.json_response({'message':'Заказ не найден'},status=404)
        return web.json_response({'ok':True,'text':f"DONATEX • Заказ #{oid}\n{o.get('title','')}\nСумма: {float(o.get('price') or 0):.2f} TJS\nСтатус: {o.get('status','processing')}"})
    except web.HTTPException:raise
    except Exception as e:return web.json_response({'message':str(e)},status=500)

async def h_topup_history(request):
    try:
        uid,u=await _web_user(request)
        rows=[x for x in u.get('transactions',[]) if 'topup' in str(x.get('type','')).lower() or 'пополн' in str(x.get('desc','')).lower()]
        return web.json_response({'items':rows[-100:][::-1]})
    except web.HTTPException:raise
    except Exception as e:return web.json_response({'message':str(e)},status=500)

async def h_news_feed(request):
    # RSS-агрегация отключена; возвращаем только ссылку на официальный новостной канал.
    try:
        uid, u = await _web_user(request)
        ch = get_news_channel(int(uid)) or ''
        return web.json_response({
            'channel': ch,
            'items': [],
            'message': 'Откройте официальный новостной канал DONATEX для актуальных публикаций.'
        })
    except web.HTTPException:
        raise
    except Exception as e:
        return web.json_response({'message': str(e)}, status=500)


@dp.message(Command('promo_timer'))
async def command_promo_timer(m, command: CommandObject):
    if not is_admin(m.from_user.id): return
    args=(command.args or '').split(maxsplit=1)
    if not args or not args[0].isdigit():
        await m.answer('Формат: /promo_timer ЧАСЫ Название акции'); return
    hours=max(0,min(720,int(args[0]))); label=args[1] if len(args)>1 else 'Акция'
    db.setdefault('meta',{})['promo_countdown']={'end_ts':now_ts()+hours*3600,'label':label[:80],'active':hours>0};save_db()
    await m.answer(f'⏳ Таймер установлен на {hours} ч. ({esc(label)})')

@dp.message(Command('notify_game'))
async def command_notify_game(m, command: CommandObject):
    if not is_admin(m.from_user.id): return
    name=(command.args or '').strip()
    if not name: await m.answer('Формат: /notify_game Название игры или товара'); return
    sent=0
    for uid,u in db['users'].items():
        _push_notice(uid,'Новая игра / товар',f'В DONATEX добавлено: {name}','new_game')
        try: await bot.send_message(int(uid),f'🆕 В DONATEX добавлено: {esc(name)}');sent+=1
        except Exception: pass
    await m.answer(f'Уведомление отправлено: {sent}')

async def main():
    await init_db()
    app = web.Application(client_max_size=6 * 1024 * 1024)
    app.add_routes([
    web.get("/",                          h_health),
    web.post("/webapp/api/web_login",     h_web_login),
    web.get("/webapp/",                   h_miniapp_html),
    web.get("/webapp",                    h_miniapp_html),
    web.get("/webapp/assets/free-fire-max.png", h_free_fire_max_image),
    web.post("/webapp/api/init",          h_webapp_init),
    web.get("/webapp/api/catalog",        h_webapp_catalog),
    web.get("/webapp/api/nick",           h_webapp_nick),
    web.post("/webapp/api/order",         h_webapp_order),
    web.get("/webapp/api/sensitivity",    h_webapp_sensitivity),
    web.post("/webapp/api/sensitivity",   h_webapp_sensitivity),
    web.get("/webapp/api/top-donors",     h_webapp_top_donors),
    web.get("/webapp/api/orders",         h_webapp_orders),
    web.post("/webapp/api/topup",         h_webapp_topup),
    web.post("/webapp/api/support",       h_webapp_support),
    web.post("/webapp/api/lang",          h_webapp_lang),
    web.get("/webapp/api/features", h_features),
    web.post("/webapp/api/features", h_features_update),
    web.post("/webapp/api/avatar", h_avatar_upload),
    web.get("/webapp/uploads/avatars/{name}", h_avatar_file),
    web.get("/webapp/api/orders/{oid}/receipt.pdf", h_receipt_pdf),
    web.get("/webapp/api/orders/{oid}/track", h_order_track),
    web.post("/webapp/api/orders/share", h_share_order),
    web.get("/webapp/api/topups", h_topup_history),
    web.get("/webapp/api/news", h_news_feed),
])

    # ── CORS: разрешаем запросы с любого сайта ──────────────────────────
    try:
        import aiohttp_cors
        cors = aiohttp_cors.setup(app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods=["GET", "POST", "OPTIONS"],
            )
        })
        for route in list(app.router.routes()):
            try:
                cors.add(route)
            except Exception:
                pass
        log.info("CORS включён")
    except ImportError:
        log.warning("aiohttp-cors не установлен — CORS выключен. Добавьте в requirements.txt: aiohttp-cors>=0.7.0")
    # ────────────────────────────────────────────────────────────────────

    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    log.info("web on :%s", PORT)

    tasks = [asyncio.create_task(saver_loop()), asyncio.create_task(balance_watcher()),
             asyncio.create_task(keepalive()), asyncio.create_task(wishlist_price_watcher()), asyncio.create_task(customer_low_balance_watcher())]
    await load_catalog(force=True)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        # Регистрируем команды в меню бота
        from aiogram.types import BotCommand
        await bot.set_my_commands([
            BotCommand(command="start",   description="🏠 Главное меню"),
            BotCommand(command="balance", description="💰 Мой баланс"),
            BotCommand(command="help",    description="📖 Помощь"),
            BotCommand(command="sensitivity", description="🎯 Чувствительность"),
            BotCommand(command="outfit", description="👕 Аутфиты MLBB / PUBG"),
            BotCommand(command="wish", description="💜 Вишлист"),
            BotCommand(command="news", description="📰 Новости игр"),
            BotCommand(command="stats", description="📊 Статистика (админ)"),
            BotCommand(command="export", description="📁 Экспорт заказов (админ)"),
            BotCommand(command="give_voucher", description="🎟 Выдать ваучер (админ)"),
            BotCommand(command="block_temp", description="⏳ Временная блокировка (админ)"),
            BotCommand(command="promo_timer", description="⏳ Таймер акции (админ)"),
            BotCommand(command="notify_game", description="🆕 Уведомить о новой игре (админ)"),
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
