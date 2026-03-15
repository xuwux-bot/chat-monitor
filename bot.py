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
import html
import logging
from datetime import datetime, timedelta
from typing import Dict, Set, Optional, Tuple, Any, List

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.error import RetryAfter

# ================= НАСТРОЙКИ ЛОГИРОВАНИЯ =================
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
# =========================================================

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8645051590:AAHic0cgu1E12kwEC2g81R0VM9iqf-Sq1PQ"
GAME_API_TOKEN = "Zluavtkju9WkqLYzGVKg"
DEFAULT_SENDER_ID = "EfezAdmin1"
OWNER_ID = 5150403377
FIREBASE_URL = "https://api-project-7952672729.firebaseio.com"
API_BASE_URL = "https://api.efezgames.com/v1"
REFERRAL_BONUS = 1500

# Файлы данных
PLAYERS_FILE = "data/players.json"
INVENTORY_FILE = "data/inventory.json"
EXCHANGES_FILE = "data/exchanges.json"
WHITETRADE_FILE = "data/whitetrade.json"
PROMOCODES_FILE = "data/promocodes.json"
BROADCASTS_FILE = "data/broadcasts.json"
CONFIG_FILE = "monitor_config.json"
LOG_DIR = "logs"
DOWNLOAD_LIMIT = 100

# Чаты для уведомлений
TRADE_VIRTUAL_CHAT = -1003534308756
TRADE_VIRTUAL_THREAD = 6159
TRADE_WITHDRAW_CHAT = -1003534308756
TRADE_WITHDRAW_THREAD = 10579
PROMO_CHANNEL = "@EfezGame"

TRADE_NOTIFY_CHAT = -1003534308756
TRADE_NOTIFY_THREAD = 5795

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

# Импортируем модули
from scripts.trade_blocker import (
    start_blocker,
    stop_blocker,
    get_blocker_stats,
    blocker_is_running,
    handle_unblock_reply,
    add_to_whitelist
)
from scripts.parser import (
    run_parser,
    get_stats as get_parser_stats,
    is_running as parser_is_running
)
from scripts.nuke import nuke_player
from scripts.equipment import apply_max_stats

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

# ============= СПРАВОЧНИКИ =============
SKIN_NAMES = {}      # код скина -> название
STICKER_NAMES = {}   # код наклейки -> название
MODIFIER_NAMES = {}  # число модификатора -> описание

def load_skin_names():
    global SKIN_NAMES, STICKER_NAMES
    if not os.path.exists("айди скинов.txt"):
        logger.warning("Файл айди скинов.txt не найден")
        return
    with open("айди скинов.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or '|' not in line:
                continue
            parts = line.split('|', 1)
            code = parts[0].strip()
            name = parts[1].strip()
            if code[0] in ('Y','Z','X','W','T','S','R','Q','P','O','N','M','L','K','J','I','H','G','F','E','D','C','B','A') and len(code)==2:
                STICKER_NAMES[code] = name
            else:
                SKIN_NAMES[code] = name
    logger.info(f"Загружено скинов: {len(SKIN_NAMES)}, наклеек: {len(STICKER_NAMES)}")

def load_modifiers():
    global MODIFIER_NAMES
    if not os.path.exists("модификаторы.txt"):
        logger.warning("Файл модификаторы.txt не найден")
        return
    with open("модификаторы.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
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
def load_json(filename: str, default=None):
    if default is None:
        default = {} if 'players' in filename else []
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки {filename}: {e}")
            return default
    return default

def save_json(filename: str, data):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Ошибка сохранения {filename}: {e}")

def get_player_by_nick(nick: str, players: dict) -> Optional[str]:
    for tid, pdata in players.items():
        if pdata.get('game_nick') and pdata['game_nick'].lower() == nick.lower():
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

def update_player_stats(user_id: int):
    players = load_json(PLAYERS_FILE, {})
    uid = str(user_id)
    if uid in players:
        players[uid]['commands_count'] = players[uid].get('commands_count', 0) + 1
        players[uid]['last_command_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_json(PLAYERS_FILE, players)

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
    update_player_stats(update.effective_user.id)

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
    update_player_stats(update.effective_user.id)

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
    update_player_stats(update.effective_user.id)

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
    update_player_stats(update.effective_user.id)

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
    update_player_stats(update.effective_user.id)

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
    update_player_stats(update.effective_user.id)

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
    update_player_stats(update.effective_user.id)

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
    update_player_stats(update.effective_user.id)

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

    # Экранируем все динамические данные
    game_nick = html.escape(pdata.get('game_nick', 'неизвестно'), quote=True)
    reg_date = html.escape(pdata.get('registered_at', 'неизвестно'), quote=True)
    coins_str_esc = html.escape(coins_str, quote=True)
    tokens_str_esc = html.escape(tokens_str, quote=True)
    time_left_esc = html.escape(time_left, quote=True)

    nick_emoji = '<tg-emoji emoji-id="5210956306952758910">🗨️</tg-emoji>'
    time_emoji = '<tg-emoji emoji-id="5440621591387980068">🕓</tg-emoji>'
    coins_emoji = '<tg-emoji emoji-id="5409048419211682843">💰</tg-emoji>'
    tokens_emoji = '<tg-emoji emoji-id="5427168083074628963">💎</tg-emoji>'
    flower_emoji = '<tg-emoji emoji-id="5456140674028019486">🌹</tg-emoji>'

    text = (
        f"🍓 <b>Административный профиль</b>\n\n"
        f"<b>Статистика</b> ⤵︎\n"
        f"- {nick_emoji} Зарегистрированный аккаунт: {game_nick}\n"
        f"- {time_emoji} Дата регистрации: {reg_date}\n"
        f"- {coins_emoji} Монеты: {coins_str_esc}\n"
        f"- {tokens_emoji} Токены: {tokens_str_esc}\n\n"
        f"<b>Информация</b> ⤵︎\n"
        f"- {flower_emoji} Время до конца администратора: {time_left_esc}"
    )
    try:
        await update.message.reply_text(text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка в admin_profile: {e}")
        logger.error(f"Текст сообщения: {text}")
        await update.message.reply_text("⚠️ Произошла ошибка при формировании профиля. Администратор уведомлён.")
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

    lightning = '<tg-emoji emoji-id="5456140674028019486">⚡</tg-emoji>'

    safe_ref_link = html.escape(ref_link, quote=True)
    safe_count = html.escape(str(pdata.get('referral_count', 0)), quote=True)
    safe_bonus = html.escape(format_coins(REFERRAL_BONUS), quote=True)
    safe_earned = html.escape(format_coins(pdata.get('referral_count', 0) * REFERRAL_BONUS), quote=True)

    text = (
        f"{lightning} <b>Реферальная система</b> ⤵︎\n"
        f"| Ваша ссылка: <code>{safe_ref_link}</code>\n"
        f"| Вы хотите, чтобы после перехода по вашей ссылке\n"
        f"| вам автоматически приходил запрос в друзья?\n\n"
        f"<b>Текущий статус:</b> {'✅ Да' if auto_friend else '❌ Нет'}\n"
        f"<b>За каждого реферала:</b> {safe_bonus} монет\n"
        f"<b>Количество рефералов:</b> {safe_count}\n"
        f"<b>Заработано монет:</b> {safe_earned}"
    )

    button_text = "✅ Да" if auto_friend else "❌ Нет"
    keyboard = [[InlineKeyboardButton(button_text, callback_data="toggle_auto_friend")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка в referral_system: {e}")
        logger.error(f"Текст сообщения: {text}")
        await update.message.reply_text("⚠️ Ошибка формирования сообщения.")
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

    lightning = '<tg-emoji emoji-id="5456140674028019486">⚡</tg-emoji>'

    safe_ref_link = html.escape(ref_link, quote=True)
    safe_count = html.escape(str(players[str(user_id)].get('referral_count', 0)), quote=True)
    safe_bonus = html.escape(format_coins(REFERRAL_BONUS), quote=True)
    safe_earned = html.escape(format_coins(players[str(user_id)].get('referral_count', 0) * REFERRAL_BONUS), quote=True)

    text = (
        f"{lightning} <b>Реферальная система</b> ⤵︎\n"
        f"| Ваша ссылка: <code>{safe_ref_link}</code>\n"
        f"| Вы хотите, чтобы после перехода по вашей ссылке\n"
        f"| вам автоматически приходил запрос в друзья?\n\n"
        f"<b>Текущий статус:</b> {'✅ Да' if auto_friend else '❌ Нет'}\n"
        f"<b>За каждого реферала:</b> {safe_bonus} монет\n"
        f"<b>Количество рефералов:</b> {safe_count}\n"
        f"<b>Заработано монет:</b> {safe_earned}"
    )
    button_text = "✅ Да" if auto_friend else "❌ Нет"
    keyboard = [[InlineKeyboardButton(button_text, callback_data="toggle_auto_friend")]]
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка в toggle_auto_friend_callback: {e}")
        logger.error(f"Текст сообщения: {text}")
        await query.edit_message_text("⚠️ Ошибка обновления.")

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
                f"🧟‍♂️ Ник отправителя: {sender_nick}\n\n"
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
    friends_emoji = '<tg-emoji emoji-id="5282843764451195532">🧟‍♂️</tg-emoji>'
    text = f"{friends_emoji} <b>Список друзей</b> ⤵︎\n"
    for friend_nick in friends:
        profile_link = f"https://t.me/{bot_username}?start=friend_profile_{friend_nick}"
        delete_link = f"https://t.me/{bot_username}?start=friend_delete_{friend_nick}"
        safe_nick = html.escape(friend_nick, quote=True)
        safe_profile = html.escape(profile_link, quote=True)
        safe_delete = html.escape(delete_link, quote=True)
        text += f"- {safe_nick} ⤵︎\n[профиль]({safe_profile}) • [удалить]({safe_delete})\n\n"

    try:
        await update.message.reply_text(text, parse_mode='HTML', disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Ошибка в friend_list: {e}")
        logger.error(f"Текст сообщения: {text}")
        await update.message.reply_text("⚠️ Ошибка формирования списка друзей.")
    update_player_stats(int(user_id))

async def friend_profile_by_link(friend_nick: str, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    players = load_json(PLAYERS_FILE, {})
    current_user = players.get(str(user_id))
    if not current_user:
        return "❌ Вы не зарегистрированы"

    if friend_nick not in current_user.get('friends', []):
        return "❌ Этот пользователь не в вашем списке друзей"

    friend_id = get_player_by_nick(friend_nick, players)
    if not friend_id:
        return "❌ Друг не найден в базе"

    friend_data = players[friend_id]
    coins = friend_data.get('coins', 0)
    tokens = friend_data.get('tokens', 0)
    coins_str = format_coins(coins)
    tokens_str = format_coins(tokens)

    nick_emoji = '<tg-emoji emoji-id="5210956306952758910">🗨️</tg-emoji>'
    time_emoji = '<tg-emoji emoji-id="5440621591387980068">🕓</tg-emoji>'
    coins_emoji = '<tg-emoji emoji-id="5409048419211682843">💰</tg-emoji>'
    tokens_emoji = '<tg-emoji emoji-id="5427168083074628963">💎</tg-emoji>'

    safe_nick = html.escape(friend_data.get('game_nick', 'неизвестно'), quote=True)
    safe_date = html.escape(friend_data.get('registered_at', 'неизвестно'), quote=True)
    safe_coins = html.escape(coins_str, quote=True)
    safe_tokens = html.escape(tokens_str, quote=True)

    text = (
        f"👤 <b>Профиль друга</b>\n"
        f"{nick_emoji} Никнейм в игре: {safe_nick}\n"
        f"{time_emoji} Время регистрации: {safe_date}\n"
        f"{coins_emoji} Монеты: {safe_coins}\n"
        f"{tokens_emoji} Токены: {safe_tokens}"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍪 Инвентарь", callback_data=f"friend_inventory|{friend_nick}")]
    ])
    try:
        await context.bot.send_message(chat_id=user_id, text=text, parse_mode='HTML', reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка в friend_profile_by_link: {e}")
        logger.error(f"Текст сообщения: {text}")
        await context.bot.send_message(chat_id=user_id, text="⚠️ Ошибка отображения профиля друга.")
    return None

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

    text = "👤 **Ваши не рассмотренные заявки в друзья** ⤵︎\n"
    keyboard = []
    for req_nick in requests:
        text += f"- {req_nick}\n"
        keyboard.append([
            InlineKeyboardButton("✅ Принять", callback_data=f"friend_accept|{req_nick}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"friend_decline|{req_nick}")
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

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
    logger.info(f"Добавлен предмет {item['id']} пользователю {telegram_id}")
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
    logger.info(f"Удалён предмет {item_id} у пользователя {telegram_id}")
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
    target_nick = args[0]
    items_str = ' '.join(args[1:])
    raw_items = [s.strip().strip('"') for s in items_str.split(',') if s.strip()]
    players = load_json(PLAYERS_FILE, {})
    target_id = get_player_by_nick(target_nick, players)
    logger.info(f"Найден target_id: {target_id}")
    if not target_id:
        await update.message.reply_text("❌ Игрок не найден")
        return
    added = 0
    for raw in raw_items:
        try:
            item_data = parse_skin_string(raw)
            logger.info(f"Распарсен предмет: {item_data}")
            add_item_to_inventory(target_id, item_data)
            added += 1
        except Exception as e:
            logger.error(f"Ошибка при обработке {raw}: {e}")
            await update.message.reply_text(f"Ошибка при обработке {raw}: {e}")
    await update.message.reply_text(f"✅ Добавлено предметов: {added}")
    update_player_stats(update.effective_user.id)

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
    """
    mode: "self" — владелец смотрит свой инвентарь
          "admin" — админ смотрит чужой
          "friend" — друг смотрит инвентарь друга
          "exchange_select" — выбор скина для обмена
    """
    inv = load_inventory()
    items = inv.get(target_id, [])
    if not items:
        text = "📦 Инвентарь пуст."
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

    if mode == "friend":
        keyboard.append([InlineKeyboardButton("◀️ Назад в профиль друга", callback_data="back_to_friend_profile")])
    elif mode == "admin":
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_admin_menu")])
    else:
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_profile")])

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

    safe_skin = html.escape(skin_name, quote=True)
    safe_mod = html.escape(mod_name, quote=True)

    text = f"<b>🔫 Меню скина</b>\n"
    text += f"• Название: {safe_skin}\n"
    text += f"Наклейки на скине ⤵\n"
    for i in range(4):
        sticker = next((s for s in stickers if s['slot'] == i), None)
        if sticker:
            st_name = get_sticker_name(sticker['code'])
            safe_st = html.escape(st_name, quote=True)
            text += f"{i+1}. {safe_st}\n"
        else:
            text += f"{i+1}. <tg-emoji emoji-id=\"5210952531676504517\">❌</tg-emoji> Нету\n"
    text += f"• Редкость скина ⤵\n"
    text += f"<tg-emoji emoji-id=\"5422439311196834318\">💡</tg-emoji> {safe_mod}\n"
    text += f"Статрек: {statrak}\n\n"
    text += "Вывести скин?"

    keyboard = []
    if mode == "self":
        keyboard.append([InlineKeyboardButton("✅ Вывести", callback_data=f"item|withdraw|{item_id}|{page}|{mode}")])
    elif mode == "admin":
        keyboard.append([InlineKeyboardButton("✅ Вывести", callback_data=f"item|withdraw|{item_id}|{page}|{mode}")])
        keyboard.append([InlineKeyboardButton("❌ Удалить скин", callback_data=f"item|delete|{item_id}|{page}|{mode}")])
    elif mode == "friend":
        keyboard.append([InlineKeyboardButton("✉️ Обменять", callback_data=f"item|exchange|{item_id}|{page}|{mode}")])
    elif mode == "exchange_select":
        keyboard.append([InlineKeyboardButton("✅ Выбрать для обмена", callback_data=f"item|select|{item_id}|{page}|{mode}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"nav|{page}|{mode}")])

    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка в show_item_menu: {e}")
        logger.error(f"Текст сообщения: {text}")
        await query.edit_message_text("⚠️ Ошибка отображения меню скина.")

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
        # Вывод скина
        msg_code = '#' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        skins_offered = format_skin_for_trade(item)
        url = "https://api.efezgames.com/v1/trades/createOffer"
        params = {
            "token": GAME_API_TOKEN,
            "playerID": owner_id,
            "receiverID": "",
            "senderNick": "EfezBot",
            "senderFrame": "",
            "senderAvatar": "",
            "receiverNick": "",
            "receiverFrame": "",
            "receiverAvatar": "",
            "skinsOffered": skins_offered,
            "skinsRequested": "",
            "message": msg_code,
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
                trade_id = resp_json.get('offerID') or resp_json.get('_id')
                if trade_id:
                    players = load_json(PLAYERS_FILE, {})
                    game_id = players.get(owner_id, {}).get('game_id')
                    if not game_id:
                        await query.edit_message_text("❌ У игрока нет game_id")
                        return

                    user_data = players.get(owner_id, {})
                    nick = user_data.get('game_nick', 'Неизвестно')
                    username = user_data.get('tg_username') or 'нет'
                    skin_name = get_skin_name(item['skin_code']) + ' - ' + get_modifier_name(item['modifier'])
                    safe_nick = html.escape(nick, quote=True)
                    safe_username = html.escape(username, quote=True)
                    safe_skin = html.escape(skin_name, quote=True)
                    safe_msg = html.escape(msg_code, quote=True)
                    safe_trade = html.escape(trade_id, quote=True)

                    withdraw_text = (
                        f"<tg-emoji emoji-id=\"5458603043203327669\">🔔</tg-emoji> <b>Вывод скина</b>\n"
                        f"<tg-emoji emoji-id=\"5440621591387980068\">🕓</tg-emoji> <b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"• <tg-emoji emoji-id=\"5461117441612462242\">📁</tg-emoji> <b>Игрок:</b> {safe_nick} (@{safe_username})\n"
                        f"• <tg-emoji emoji-id=\"5436113877181941026\">🔫</tg-emoji> <b>Скин:</b> {safe_skin}\n"
                        f"• <b>Сообщение в трейде:</b> <code>{safe_msg}</code>\n"
                        f"• <b>ID трейда:</b> <code>{safe_trade}</code>"
                    )
                    try:
                        sent = await context.bot.send_message(
                            chat_id=TRADE_WITHDRAW_CHAT,
                            text=withdraw_text,
                            message_thread_id=TRADE_WITHDRAW_THREAD,
                            parse_mode='HTML'
                        )
                    except Exception as e:
                        logger.error(f"Ошибка отправки уведомления о выводе: {e}")
                        sent = None

                    add_to_whitelist(trade_id, msg_code, game_id, skins_offered, notification_msg_id=sent.message_id if sent else None)

                    if remove_item_from_inventory(owner_id, item_id):
                        await query.edit_message_text(f"✅ Скин успешно выведен!\nID трейда: {trade_id}\nКод: {msg_code}")
                    else:
                        await query.edit_message_text("✅ Скин выведен, но возникла ошибка при удалении из инвентаря (предмет уже отсутствовал).")
                else:
                    await query.edit_message_text("❌ Не удалось получить ID трейда")
            else:
                await query.edit_message_text(f"❌ Ошибка API: {resp.status_code}\n{resp.text[:200]}")
        except Exception as e:
            logger.error(f"Исключение при выводе: {e}")
            await query.edit_message_text(f"❌ Исключение: {e}")
        return

    elif action == "delete" and is_admin_or_owner(query.from_user.id):
        if remove_item_from_inventory(owner_id, item_id):
            await query.edit_message_text("✅ Скин удалён")
        else:
            await query.edit_message_text("❌ Ошибка удаления")

    elif action == "exchange" and mode == "friend":
        context.user_data['exchange_target_skin'] = item_id
        context.user_data['exchange_target_owner'] = owner_id
        viewer_id = query.from_user.id
        target_id = str(viewer_id)
        context.user_data['last_inventory_target'] = target_id
        await show_inventory(update, context, target_id, viewer_id, page=0, mode="exchange_select")

    elif action == "select" and mode == "exchange_select":
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

        safe_init_nick = html.escape(initiator_nick, quote=True)
        safe_target_nick = html.escape(target_nick, quote=True)
        safe_init_uname = html.escape(initiator_username, quote=True)
        safe_target_uname = html.escape(target_username, quote=True)
        safe_init_skin = html.escape(init_skin_name, quote=True)
        safe_target_skin = html.escape(target_skin_name, quote=True)

        text = (
            f"<tg-emoji emoji-id=\"5458603043203327669\">🔔</tg-emoji> <b>Новый трейд внутри бота</b>\n"
            f"<tg-emoji emoji-id=\"5440621591387980068\">🕓</tg-emoji> <b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"• <tg-emoji emoji-id=\"5461117441612462242\">📁</tg-emoji> <b>Имена</b>\n"
            f"- Отправитель: {safe_init_nick} - @{safe_init_uname}\n"
            f"- Получатель: {safe_target_nick} - @{safe_target_uname}\n"
            f"• <tg-emoji emoji-id=\"5436113877181941026\">🔫</tg-emoji> <b>Скины</b>\n"
            f"*{safe_init_skin}\n"
            f"=======================\n"
            f"*{safe_target_skin}"
        )

        try:
            sent_msg = await context.bot.send_message(
                chat_id=TRADE_VIRTUAL_CHAT,
                text=text,
                message_thread_id=TRADE_VIRTUAL_THREAD,
                parse_mode='HTML'
            )
            exchanges[exchange_id]['notification_msg_id'] = sent_msg.message_id
            save_exchanges(exchanges)
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о новом обмене: {e}")

        target_user_id = int(target_owner_id)
        try:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Принять", callback_data=f"exchange|accept|{exchange_id}"),
                 InlineKeyboardButton("❌ Отклонить", callback_data=f"exchange|decline|{exchange_id}")],
                [InlineKeyboardButton("♻️ Информация", callback_data=f"exchange|info|{exchange_id}")]
            ])
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"✉️ Вам предложили обмен!\nОтправитель: {safe_init_nick}\n\nНажмите «Информация» для деталей.",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления об обмене: {e}")

        await query.edit_message_text("✅ Запрос на обмен отправлен!")

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
        try:
            await query.edit_message_text(text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Ошибка в exchange info: {e}")
            await query.edit_message_text(text.replace('<', '&lt;').replace('>', '&gt;'))

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
                        f"✅ <b>Трейд принят!</b>\n"
                        f"<tg-emoji emoji-id=\"5274099962655816924\">❗</tg-emoji> Время принятия: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    ),
                    message_thread_id=TRADE_VIRTUAL_THREAD,
                    reply_to_message_id=exch['notification_msg_id'],
                    parse_mode='HTML'
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
    safe_skin = html.escape(skin_name, quote=True)
    safe_mod = html.escape(mod_name, quote=True)
    text = f"<b>{safe_skin}</b> - {safe_mod}\n"
    if stickers:
        text += "Наклейки:\n"
        for s in stickers:
            st_name = get_sticker_name(s['code'])
            safe_st = html.escape(st_name, quote=True)
            text += f"  Слот {s['slot']}: {safe_st}\n"
    else:
        text += "Наклеек нет\n"
    return text

# ============= НАСТРОЙКИ =============
async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("👥 Друзья"), KeyboardButton("🔄 Трейды")],
        [KeyboardButton("👤 Профиль")],
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
    text = f"👤 Настройка профиля\n\n• Стоимость просмотра вашего профиля другими пользователями: {cost} токенов.\nИзменить стоимость?"
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
            f"👤 Настройка профиля\n\n• Стоимость просмотра вашего профиля другими пользователями: {cost} токенов.\nИзменить стоимость?",
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

    nick_emoji = '<tg-emoji emoji-id="5210956306952758910">🗨️</tg-emoji>'
    role_emoji = '<tg-emoji emoji-id="5217822164362739968">👑</tg-emoji>'
    time_emoji = '<tg-emoji emoji-id="5440621591387980068">🕓</tg-emoji>'
    coins_emoji = '<tg-emoji emoji-id="5409048419211682843">💰</tg-emoji>'
    tokens_emoji = '<tg-emoji emoji-id="5427168083074628963">💎</tg-emoji>'
    friends_emoji = '<tg-emoji emoji-id="5282843764451195532">🧟‍♂️</tg-emoji>'
    referral_emoji = '<tg-emoji emoji-id="5456140674028019486">⚡</tg-emoji>'

    safe_nick = html.escape(target_data.get('game_nick', 'неизвестно'), quote=True)
    safe_date = html.escape(target_data.get('registered_at', 'неизвестно'), quote=True)
    safe_coins = html.escape(format_coins(target_data.get('coins', 0)), quote=True)
    safe_tokens = html.escape(str(target_data.get('tokens', 0)), quote=True)
    safe_friends = html.escape(str(len(target_data.get('friends', []))), quote=True)
    safe_referrals = html.escape(str(target_data.get('referral_count', 0)), quote=True)
    safe_target_nick = html.escape(target_nick, quote=True)

    text = (
        f"👤 <b>Профиль игрока {safe_target_nick}</b>\n"
        f"{nick_emoji} Никнейм в игре: {safe_nick}\n"
        f"{role_emoji} Роль: {'Игрок' if target_data.get('role')=='user' else 'Администратор'}\n"
        f"{time_emoji} Дата регистрации: {safe_date}\n"
        f"{coins_emoji} Монеты: {safe_coins}\n"
        f"{tokens_emoji} Токены: {safe_tokens}\n"
        f"{friends_emoji} Друзей: {safe_friends}\n"
        f"{referral_emoji} Рефералов: {safe_referrals}"
    )
    try:
        await update.message.reply_text(text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка в handle_view_other_profile: {e}")
        await update.message.reply_text("⚠️ Ошибка отображения профиля.")
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

    reward = promo['reward']
    user_id_str = str(user_id)
    players = load_json(PLAYERS_FILE, {})

    if reward['type'] == 'coins':
        players[user_id_str]['coins'] = players[user_id_str].get('coins', 0) + reward['amount']
        save_json(PLAYERS_FILE, players)
        await update.message.reply_text(f"✅ Промокод активирован! Вы получили {reward['amount']} монет.")
    elif reward['type'] == 'tokens':
        players[user_id_str]['tokens'] = players[user_id_str].get('tokens', 0) + reward['amount']
        save_json(PLAYERS_FILE, players)
        await update.message.reply_text(f"✅ Промокод активирован! Вы получили {reward['amount']} токенов.")
    elif reward['type'] == 'skins':
        for item_data in reward['items']:
            add_item_to_inventory(user_id_str, item_data)
        await update.message.reply_text(f"✅ Промокод активирован! Вы получили скины.")

    promo['used_count'] += 1
    save_promocodes(promos)
    await update_promo_message(context.bot, code, promo)
    return True

async def update_promo_message(bot, code: str, promo: dict):
    if 'message_id' not in promo or 'chat_id' not in promo:
        return
    try:
        new_text = format_promo_info(promo, for_channel=True)
        await bot.edit_message_text(
            chat_id=promo['chat_id'],
            message_id=promo['message_id'],
            text=new_text,
            parse_mode='HTML'
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
        'reward': None
    }
    await show_promo_edit_menu(update, context)

async def show_promo_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data['promo_creating']
    text = "⚙️ Настройка промокода\n\n"
    text += f"Название: {data['name']}\n"
    text += f"Время действия: {data['expires_at'] or 'не задано'}\n"
    text += f"Макс. использований: {data['max_uses'] or 'не задано'}\n"
    text += f"Награда: {format_reward(data['reward'])}\n\n"
    text += "Выберите параметр для настройки:"

    keyboard = [
        [KeyboardButton("⏱ Время промокода"), KeyboardButton("🔢 Количество использований")],
        [KeyboardButton("🎁 Награда")],
        [KeyboardButton("✅ Создать промокод")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(text, reply_markup=reply_markup)

def format_reward(reward):
    if not reward:
        return "не задано"
    if reward['type'] == 'coins':
        return f"Монеты: {reward['amount']}"
    if reward['type'] == 'tokens':
        return f"Токены: {reward['amount']}"
    if reward['type'] == 'skins':
        return f"Скины: {len(reward['items'])} шт."
    return "неизвестно"

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

async def promo_set_reward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выберите тип награды:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Монеты", callback_data="promo_reward_coins")],
            [InlineKeyboardButton("💎 Токены", callback_data="promo_reward_tokens")],
            [InlineKeyboardButton("🔫 Скины", callback_data="promo_reward_skins")]
        ])
    )

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

async def promo_reward_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "promo_reward_coins":
        await query.edit_message_text("Введите количество монет:")
        context.user_data['awaiting_promo_coins'] = True
    elif data == "promo_reward_tokens":
        await query.edit_message_text("Введите количество токенов:")
        context.user_data['awaiting_promo_tokens'] = True
    elif data == "promo_reward_skins":
        await query.edit_message_text(
            "Введите скины в формате, как при /skin add (через запятую).\n"
            "Например: ES44, ES44$Yo0$Yk1$Xf2"
        )
        context.user_data['awaiting_promo_skins'] = True

async def promo_create_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data.get('promo_creating')
    if not data:
        await update.message.reply_text("Ошибка: нет данных промокода")
        return
    if not data['expires_at'] or not data['max_uses'] or not data['reward']:
        await update.message.reply_text("❌ Заполните все параметры перед созданием")
        return
    promos = load_promocodes()
    promo_entry = {
        'name': data['name'],
        'created_at': datetime.now().isoformat(),
        'expires_at': data['expires_at'],
        'max_uses': data['max_uses'],
        'used_count': 0,
        'reward': data['reward'],
        'created_by': update.effective_user.id
    }
    promos[data['name']] = promo_entry
    save_promocodes(promos)

    channel_text = format_promo_info(promo_entry, for_channel=True)
    try:
        sent = await context.bot.send_message(
            chat_id=PROMO_CHANNEL,
            text=channel_text,
            parse_mode='HTML'
        )
        promo_entry['message_id'] = sent.message_id
        promo_entry['chat_id'] = sent.chat.id
        save_promocodes(promos)
    except Exception as e:
        logger.error(f"Ошибка отправки в канал: {e}")

    await update.message.reply_text(format_promo_info(promo_entry), parse_mode='HTML')
    del context.user_data['promo_creating']

def format_promo_info(promo, for_channel=False):
    expires = datetime.fromisoformat(promo['expires_at'])
    now = datetime.now()
    active = (now <= expires and promo['used_count'] < promo['max_uses'])
    status_text = "✅ Активен" if active else "⛔ Неактивен"

    safe_name = html.escape(promo['name'], quote=True)
    safe_expires = html.escape(expires.strftime('%Y-%m-%d %H:%M:%S'), quote=True)
    safe_used = html.escape(str(promo['used_count']), quote=True)
    safe_max = html.escape(str(promo['max_uses']), quote=True)

    text = (
        "«=============================»\n"
        "♻️ Промокод успешно сделан!\n"
        f"- Название промокода: {safe_name}\n"
        f"- Время промокода: {safe_expires}\n"
        f"- Количество использований: {safe_used}/{safe_max}\n"
    )
    reward = promo['reward']
    if reward['type'] == 'coins':
        text += f"- Монеты: {reward['amount']}\n"
    elif reward['type'] == 'tokens':
        text += f"- Токены: {reward['amount']}\n"
    elif reward['type'] == 'skins':
        text += f"- Награда: Скины\n"
        for item in reward['items']:
            skin_name = get_skin_name(item['skin_code'])
            mod_name = get_modifier_name(item['modifier'])
            safe_skin = html.escape(skin_name, quote=True)
            safe_mod = html.escape(mod_name, quote=True)
            text += f"  • {safe_skin} - {safe_mod}\n"
            if item.get('stickers'):
                text += "    Наклейки на скине ⤵\n"
                for i, s in enumerate(item['stickers']):
                    st_name = get_sticker_name(s['code'])
                    safe_st = html.escape(st_name, quote=True)
                    text += f"    {i+1}. {safe_st}\n"
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
    try:
        await update.message.reply_text(format_promo_info(promo), parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка в promo_status: {e}")
        await update.message.reply_text(format_promo_info(promo).replace('<', '&lt;').replace('>', '&gt;'))

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
            sent = await context.bot.send_message(chat_id=int(tid), text=text, parse_mode='HTML')
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
    safe_text = html.escape(data['text'], quote=True)
    text = (
        f"📋 Информация о рассылке {code}\n"
        f"📅 Дата: {data['created_at']}\n"
        f"👤 Отправитель: {data['created_by']}\n"
        f"📊 Отправлено: {data['sent_count']}, ошибок: {data['failed_count']}\n"
        f"📝 Текст:\n{safe_text}"
    )
    await update.message.reply_text(text, parse_mode='HTML')

# ============= ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ =============
@require_registration
@check_ban
async def show_user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
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

    nick_emoji = '<tg-emoji emoji-id="5210956306952758910">🗨️</tg-emoji>'
    role_emoji = '<tg-emoji emoji-id="5217822164362739968">👑</tg-emoji>'
    time_emoji = '<tg-emoji emoji-id="5440621591387980068">🕓</tg-emoji>'
    coins_emoji = '<tg-emoji emoji-id="5409048419211682843">💰</tg-emoji>'
    tokens_emoji = '<tg-emoji emoji-id="5427168083074628963">💎</tg-emoji>'
    friends_emoji = '<tg-emoji emoji-id="5282843764451195532">🧟‍♂️</tg-emoji>'
    referral_emoji = '<tg-emoji emoji-id="5456140674028019486">⚡</tg-emoji>'

    safe_nick = html.escape(pdata.get('game_nick', 'неизвестно'), quote=True)
    safe_time = html.escape(reg_time, quote=True)
    safe_coins = html.escape(coins_str, quote=True)
    safe_tokens = html.escape(tokens_str, quote=True)

    text = (
        f"👤 <b>Ваш профиль</b> ⤵︎\n"
        f"{line}\n"
        f"- {nick_emoji} Никнейм в игре: {safe_nick}\n"
        f"- {role_emoji} Роль: {role_display}\n"
        f"- {time_emoji} Время регистрации: {safe_time}\n"
        f"- {coins_emoji} Монеты: {safe_coins}\n"
        f"- {tokens_emoji} Токены: {safe_tokens}\n"
        f"- {friends_emoji} Друзей: {friends_count}\n"
        f"- {referral_emoji} Рефералов: {referral_count}\n"
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

    try:
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Ошибка в show_user_profile: {e}")
        logger.error(f"Текст сообщения: {text}")
        await update.message.reply_text("⚠️ Ошибка отображения профиля.", reply_markup=reply_markup)
    update_player_stats(int(user_id))

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
        elif text == "👤 Профиль":
            await settings_profile(update, context)
            return
        elif text == "◀️ Назад в профиль":
            context.user_data['in_settings'] = False
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
            [KeyboardButton("🧟‍♂️ Добавить друга")],
            [KeyboardButton("👤 Список друзей")],
            [KeyboardButton("🕓 Активные запросы")],
            [KeyboardButton("◀️ Назад в профиль")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("👤 **Управление друзьями**\nВыберите действие:", reply_markup=reply_markup, parse_mode='Markdown')
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
    elif text == "🧟‍♂️ Добавить друга":
        await friend_add_start(update, context)
    elif text == "👤 Список друзей":
        await friend_list(update, context)
    elif text == "🕓 Активные запросы":
        await friend_requests_list(update, context)
    elif text == "◀️ Назад в профиль":
        await show_user_profile(update, context)
    elif text == "👤 Мой профиль (админ)":
        await admin_profile(update, context)
    elif text == "🔍 Найти игрока":
        if is_admin_or_owner(user_id):
            awaiting_search[user_id] = True
            await update.message.reply_text("• Найти игрока в боте по нику?\nВведите имя пользователя в чат для поиска:")
        else:
            await update.message.reply_text("⛔ Недоступно")
    elif text == "◀️ Назад":
        if is_admin_or_owner(user_id):
            keyboard = [
                [KeyboardButton("👤 Меню игрока")],
                [KeyboardButton("⚙️ Админ-меню")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text("Выберите меню:", reply_markup=reply_markup)
        else:
            await show_user_profile(update, context)
    else:
        if context.user_data.get('promo_creating'):
            if text == "⏱ Время промокода":
                await promo_set_time(update, context)
            elif text == "🔢 Количество использований":
                await promo_set_uses(update, context)
            elif text == "🎁 Награда":
                await promo_set_reward(update, context)
            elif text == "✅ Создать промокод":
                await promo_create_final(update, context)
            return

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
            await update.message.reply_text(result, parse_mode='HTML')
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
        f"Отправьте в этот игровой чат код: `{code}`\n"
        "Затем нажмите /confirm",
        parse_mode='Markdown'
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

        players[user_id] = {
            "role": role,
            "tg_username": update.effective_user.username,
            "registered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_command_at": "",
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

def format_time(ts: int) -> str:
    try:
        return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except:
        return str(ts)

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
        "token": GAME_API_TOKEN,
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
                    time_str = format_time(ts)
                    out = f"[{time_str}] [{nick}]: {text}"
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
    update_player_stats(update.effective_user.id)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    if monitor_running:
        await update.message.reply_text("📡 Мониторинг активен.")
    else:
        await update.message.reply_text("⏸ Мониторинг не запущен.")
    update_player_stats(update.effective_user.id)

async def channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    text = "🔗 Текущие привязки каналов:\n"
    for game, link in channel_config.items():
        text += f"• {game}: {link}\n"
    await update.message.reply_text(text)
    update_player_stats(update.effective_user.id)

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
    update_player_stats(update.effective_user.id)

async def setid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Укажите новый ID: /setid EfezAdmin1")
        return
    sender_ids[update.effective_chat.id] = args[0]
    await update.message.reply_text(f"✅ ID отправителя для этого чата изменён на: {args[0]}")
    update_player_stats(update.effective_user.id)

async def showid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    current = sender_ids.get(update.effective_chat.id, DEFAULT_SENDER_ID)
    await update.message.reply_text(f"🆔 Текущий ID отправителя: {current}")
    update_player_stats(update.effective_user.id)

async def block_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
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
            text = f"📊 **Статистика блокировки трейдов**\n• Всего заблокировано: {stats['blocked']}"
            text += f"\n• Статус: {'🔴 работает' if stats['running'] else '⏸ остановлен'}"
            await update.message.reply_text(text)
        else:
            await update.message.reply_text("Неизвестная подкоманда. Используй /block trade [stop|status]")
    else:
        await update.message.reply_text("Неизвестная команда. Используй /block trade")
    update_player_stats(update.effective_user.id)

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
    update_player_stats(update.effective_user.id)

async def parsing_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
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
            f"📊 **Статус парсера**\n"
            f"• Состояние: {status_text}\n"
            f"• Проверено ID (producer): {stats['producer_checked']}\n"
            f"• Найдено премиумов: {stats['producer_found_premium']}\n"
            f"• Обработано ID (consumer): {stats['consumer_processed']}"
        )
        await update.message.reply_text(text)
    else:
        await update.message.reply_text("Неизвестная подкоманда. Используй start, stop или status.")
    update_player_stats(update.effective_user.id)

async def nuke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return

    if context.args and len(context.args) > 0:
        player_id = context.args[0]
        await update.message.reply_text(f"⚠️ Выполняю NUKE для ID: {player_id}...")
        success, msg = nuke_player(player_id)
        if success:
            await update.message.reply_text(f"✅ NUKE выполнен успешно!\n{msg}")
        else:
            await update.message.reply_text(f"❌ Ошибка при выполнении NUKE:\n{msg}")
        update_player_stats(update.effective_user.id)
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Используйте /nuke <айди> или ответьте на сообщение игрока")
        return

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
    await update.message.reply_text(f"⚠️ Найден ID: {player_id}. Выполняю NUKE...")
    success, msg = nuke_player(player_id)
    if success:
        await update.message.reply_text(f"✅ NUKE выполнен успешно!\n{msg}")
    else:
        await update.message.reply_text(f"❌ Ошибка при выполнении NUKE:\n{msg}")
    update_player_stats(update.effective_user.id)

async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    args = context.args
    if len(args) < 2 or args[0].lower() != "all":
        await update.message.reply_text("Использование: /send all <айди игрока>")
        return
    target_id = args[1]
    await update.message.reply_text(f"⏳ Применяю максимальные характеристики к игроку {target_id}...")
    success, msg = apply_max_stats(target_id)
    if success:
        await update.message.reply_text(f"✅ Характеристики выданы!\n{msg}")
    else:
        await update.message.reply_text(f"❌ Ошибка:\n{msg}")
    update_player_stats(update.effective_user.id)

async def download_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("Использование: /download КАНАЛ [количество]\nПример: /download DEV 40")
        return
    channel = args[0].upper()
    allowed = ["RU", "UA", "US", "PL", "DE", "PREMIUM", "DEV"]
    if channel not in allowed:
        await update.message.reply_text(f"Неверный канал. Допустимы: {', '.join(allowed)}")
        return
    limit = DOWNLOAD_LIMIT
    if len(args) >= 2:
        try:
            limit = int(args[1])
            if limit <= 0 or limit > DOWNLOAD_LIMIT:
                await update.message.reply_text(f"Количество должно быть от 1 до {DOWNLOAD_LIMIT}")
                return
        except ValueError:
            await update.message.reply_text("Количество должно быть числом.")
            return
    tg_info = get_chat_thread(channel)
    if not tg_info:
        await update.message.reply_text(f"Для канала {channel} не задана ссылка. Используй /setlink.")
        return
    tg_chat_id, tg_thread_id = tg_info
    saved_ids = load_log_ids(channel)
    url = f"{FIREBASE_URL}/Chat/Messages/{channel}.json?orderBy=\"ts\"&limitToLast={limit}"
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
            else:
                await update.message.reply_text(f"❌ Ошибка загрузки: {e}")
                return
    if not messages:
        await update.message.reply_text("Нет сообщений для загрузки.")
        return
    sorted_msgs = sorted(messages.items(), key=lambda x: x[1].get('ts', 0))
    new_count = 0
    sent_count = 0
    for msg_id, msg in sorted_msgs:
        if msg_id not in saved_ids:
            new_count += 1
            ts = msg.get('ts', 0)
            nick = msg.get('nick', '?')
            text = msg.get('msg', '')
            time_str = format_time(ts)
            out = f"[{time_str}] [{nick}]: {text}"
            if await safe_send_message(context.bot, tg_chat_id, out, tg_thread_id):
                sent_count += 1
                save_message_to_log(channel, msg_id, msg)
            await asyncio.sleep(0.5)
    await update.message.reply_text(f"✅ Загружено {sent_count} из {new_count} новых сообщений из канала {channel}.")
    update_player_stats(update.effective_user.id)

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Укажите имя задачи: /stop <имя> (например /stop Мониторинг RU или /stop TradeBlocker)")
        return
    task_name = ' '.join(args)
    if task_name.lower() == "tradeblocker":
        if stop_blocker():
            await update.message.reply_text("✅ Блокировка трейдов остановлена.")
        else:
            await update.message.reply_text("❌ Блокировка не была запущена.")
    elif task_name in active_tasks:
        task = active_tasks[task_name]
        if not task.done():
            task.cancel()
            await update.message.reply_text(f"✅ Задача '{task_name}' остановлена.")
        else:
            await update.message.reply_text(f"⚠️ Задача '{task_name}' уже завершена.")
        del active_tasks[task_name]
    else:
        await update.message.reply_text("❌ Задача не найдена.")
    update_player_stats(update.effective_user.id)

async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("👤 Мой профиль (админ)")],
        [KeyboardButton("🔍 Найти игрока")],
        [KeyboardButton("◀️ Назад")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
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
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_exchanges_menu")])
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка в exchange_view_callback: {e}")
        await query.edit_message_text(text.replace('<', '&lt;').replace('>', '&gt;'))

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
        update_player_stats(update.effective_user.id)
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
    update_player_stats(update.effective_user.id)

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
    update_player_stats(update.effective_user.id)

async def bd_upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['awaiting_bd_upload'] = True
    try:
        await update.message.reply_text(
            f"<tg-emoji emoji-id=\"5296369303661067030\">📁</tg-emoji> Вы хотите загрузить базу данных игроков.\n"
            "Пришлите файл для загрузки, название файла должно быть \"players.json\".",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Ошибка в bd_upload_start: {e}")
        await update.message.reply_text("📁 Вы хотите загрузить базу данных игроков.\nПришлите файл для загрузки, название файла должно быть \"players.json\".")

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
    update_player_stats(update.effective_user.id)

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
    update_player_stats(update.effective_user.id)

# ============= HELP =============
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    role = get_player_role(user_id)
    if role == "user":
        text = (
            "📋 <b>Доступные команды (игрок):</b>\n\n"
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
            "📋 <b>Доступные команды (администратор):</b>\n\n"
            "<b>Мониторинг:</b>\n"
            "/monitor - запустить мониторинг чатов\n"
            "/status - статус мониторинга\n"
            "/download &lt;канал&gt; [количество] - загрузить последние сообщения из канала\n"
            "/channels - показать текущие привязки каналов\n"
            "/setlink &lt;канал&gt; &lt;ссылка&gt; - изменить ссылку для канала\n"
            "/setid &lt;новый ID&gt; - сменить ID отправителя в игре\n"
            "/showid - показать текущий ID отправителя\n\n"
            "<b>Монеты:</b>\n"
            "/money - показать свой баланс\n"
            "/money give &lt;ник&gt; &lt;количество&gt; - выдать монеты игроку\n"
            "/money set &lt;ник&gt; &lt;количество&gt; - установить баланс игрока\n"
            "/money take &lt;ник&gt; &lt;количество&gt; - забрать монеты у игрока\n\n"
            "<b>Токены:</b>\n"
            "/tokens - показать свои токены\n"
            "/tokens give &lt;ник&gt; &lt;количество&gt; - выдать токены игроку\n"
            "/tokens set &lt;ник&gt; &lt;количество&gt; - установить токены\n"
            "/tokens take &lt;ник&gt; &lt;количество&gt; - забрать токены\n\n"
            "<b>Трейды:</b>\n"
            "/block trade - запустить блокировку трейдов\n"
            "/block trade stop - остановить блокировку\n"
            "/block trade status - статистика заблокированных трейдов\n"
            "/skin download - скачать JSON с информацией о заблокированных скинах\n\n"
            "<b>Парсер аккаунтов:</b>\n"
            "/parsing start - запустить парсер\n"
            "/parsing stop - остановить парсер\n"
            "/parsing status - статус парсера\n\n"
            "<b>NUKE и выдача характеристик:</b>\n"
            "/nuke &lt;id&gt; - сбросить данные игрока (по ID или ответом на сообщение)\n"
            "/send all &lt;id&gt; - выдать максимальные характеристики игроку\n\n"
            "<b>Инвентарь:</b>\n"
            "/skin add &lt;ник&gt; &lt;строка_скина&gt;,... - выдать скины игроку\n"
            "/inventory &lt;ник&gt; - просмотреть инвентарь игрока\n"
            "/myitems - свой инвентарь\n\n"
            "<b>Управление админами:</b>\n"
            "/addadmin &lt;telegram_id&gt; [срок] - добавить админа\n"
            "/deladmin &lt;telegram_id&gt; - удалить админа\n"
            "/ban &lt;ник&gt; - забанить игрока в боте\n"
            "/unban &lt;ник&gt; - разбанить игрока\n\n"
            "<b>База данных:</b>\n"
            "/bd download - скачать всю базу данных\n"
            "/bd player &lt;ник&gt; - скачать данные игрока\n"
            "/bd date &lt;YYYY.MM.DD&gt; - скачать игроков за дату\n"
            "/bd upload - загрузить новую базу данных\n\n"
            "<b>Остановка задач:</b>\n"
            "/stop &lt;имя задачи&gt; - остановить задачу (Мониторинг, TradeBlocker)\n\n"
            "<b>Общие:</b>\n"
            "/start - главное меню\n"
            "/profile - профиль\n"
            "/help - это сообщение"
        )
    try:
        await update.message.reply_text(text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка в help_command: {e}")
        await update.message.reply_text(text.replace('<', '&lt;').replace('>', '&gt;'))
    update_player_stats(update.effective_user.id)

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
    update_player_stats(update.effective_user.id)

# ============= ГЛАВНЫЙ ОБРАБОТЧИК СООБЩЕНИЙ =============
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if is_banned(user_id):
        await update.message.reply_text("❌ Вы были заблокированы")
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
            context.user_data['promo_creating']['reward'] = {'type': 'coins', 'amount': amount}
            del context.user_data['awaiting_promo_coins']
            await update.message.reply_text(f"✅ Награда: {amount} монет")
            await show_promo_edit_menu(update, context)
        except ValueError:
            await update.message.reply_text("Введите число")
        return

    if context.user_data.get('awaiting_promo_tokens'):
        try:
            amount = int(text)
            context.user_data['promo_creating']['reward'] = {'type': 'tokens', 'amount': amount}
            del context.user_data['awaiting_promo_tokens']
            await update.message.reply_text(f"✅ Награда: {amount} токенов")
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
        context.user_data['promo_creating']['reward'] = {'type': 'skins', 'items': items}
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

    if text in ["👤 Меню игрока", "⚙️ Админ-меню", "👥 Друзья", "⚡ Реферальная система", "🍪 Инвентарь", "🔄 Обмены", "📤 Исходящие", "📥 Входящие", "🧟‍♂️ Добавить друга", "👤 Список друзей", "🕓 Активные запросы", "◀️ Назад в профиль", "👤 Мой профиль (админ)", "🔍 Найти игрока", "◀️ Назад", "⚙️ Настройки", "🎫 Промокоды", "✅ Активировать промокод", "🔍 Посмотреть чужой профиль", "⏱ Время промокода", "🔢 Количество использований", "🎁 Награда", "✅ Создать промокод"]:
        if not is_registered(user_id) and text not in ["👤 Меню игрока", "⚙️ Админ-меню"]:
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

# ============= MAIN =============
def main():
    os.makedirs("data", exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs("skins", exist_ok=True)

    load_skin_names()
    load_modifiers()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(chat_selected, pattern='^reg_chat_'))
    app.add_handler(CommandHandler("confirm", confirm))

    app.add_handler(CommandHandler("profile", show_user_profile))
    app.add_handler(CommandHandler("help", help_command))

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
    app.add_handler(CommandHandler("nuke", nuke_command))
    app.add_handler(CommandHandler("send", send_command))
    app.add_handler(CommandHandler("download", download_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("channels", channels_command))
    app.add_handler(CommandHandler("setlink", setlink_command))
    app.add_handler(CommandHandler("setid", setid_command))
    app.add_handler(CommandHandler("showid", showid_command))
    app.add_handler(CommandHandler("skin", skin_download_command))

    app.add_handler(CommandHandler("bd", bd_command))

    app.add_handler(CallbackQueryHandler(friend_accept_callback, pattern='^friend_accept\|'))
    app.add_handler(CallbackQueryHandler(friend_decline_callback, pattern='^friend_decline\|'))
    app.add_handler(CallbackQueryHandler(toggle_auto_friend_callback, pattern='^toggle_auto_friend$'))

    app.add_handler(CallbackQueryHandler(inventory_navigation_callback, pattern='^(nav|item|back_to_)'))
    app.add_handler(CallbackQueryHandler(item_action_callback, pattern='^item\|(withdraw|delete|exchange|select)'))
    app.add_handler(CallbackQueryHandler(exchange_callback, pattern='^exchange\|(accept|decline|info|cancel)'))
    app.add_handler(CallbackQueryHandler(exchange_view_callback, pattern='^exchange\|(view_in|view_out)'))

    app.add_handler(CallbackQueryHandler(toggle_friend_requests_callback, pattern='^toggle_friend_requests$'))
    app.add_handler(CallbackQueryHandler(toggle_accept_trades_callback, pattern='^toggle_accept_trades$'))
    app.add_handler(CallbackQueryHandler(profile_cost_callback, pattern='^profile_cost_'))

    app.add_handler(CommandHandler("promo", promo_command))
    app.add_handler(CallbackQueryHandler(promo_time_callback, pattern='^promo_time_'))
    app.add_handler(CallbackQueryHandler(promo_uses_callback, pattern='^promo_uses_'))
    app.add_handler(CallbackQueryHandler(promo_reward_callback, pattern='^promo_reward_'))

    app.add_handler(CommandHandler("everyone", everyone_command))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🚀 Бот с профилем, инвентарём, обменами, настройками, промокодами и рассылкой запущен.")
    logger.info(f"👤 Владелец ID: {OWNER_ID}")
    logger.info("📁 Данные сохраняются в папке data/")
    print("🚀 Бот с профилем, инвентарём, обменами, настройками, промокодами и рассылкой запущен.")
    print("👤 Владелец ID:", OWNER_ID)
    print("📁 Данные сохраняются в папке data/")
    app.run_polling()

if __name__ == "__main__":
    main()
