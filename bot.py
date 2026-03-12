#!/usr/bin/env python3
import asyncio
import json
import os
import re
import time
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, Set, Optional, Tuple

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.error import RetryAfter

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8645051590:AAHic0cgu1E12kwEC2g81R0VM9iqf-Sq1PQ"
GAME_API_TOKEN = "Zluavtkju9WkqLYzGVKg"
DEFAULT_SENDER_ID = "EfezAdmin1"
PASSWORD = "201188messo"
OWNER_ID = 5150403377

CONFIG_FILE = "monitor_config.json"
LOG_DIR = "logs"
DOWNLOAD_LIMIT = 100

# Чат для уведомлений о трейдах
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
    "API_BASE_URL": "https://api.efezgames.com/v1",
    "FIREBASE_URL": "https://api-project-7952672729.firebaseio.com",
    "REQUEST_TIMEOUT": 10,
    "RETRY_ATTEMPTS": 3,
    "RETRY_DELAY": 2
}
# ==============================================

# Глобальные переменные
authorised_users: Set[int] = set()
monitor_running = False
monitor_task: Optional[asyncio.Task] = None
sender_ids: Dict[int, str] = {}
nick_cache: Dict[str, str] = {}
active_tasks: Dict[str, asyncio.Task] = {}

flood_until: Dict[Tuple[int, int], float] = {}

# Импортируем модули
from scripts.trade_blocker import (
    start_blocker,
    stop_blocker,
    get_blocker_stats,
    blocker_is_running,
    handle_unblock_reply
)
from scripts.parser import (
    run_parser,
    get_stats as get_parser_stats,
    is_running as parser_is_running
)
from scripts.nuke import nuke_player
from scripts.equipment import apply_max_stats  # новый модуль

# Поток для парсера
parser_thread: Optional[threading.Thread] = None
parser_stop_event: Optional[threading.Event] = None

def get_log_path(channel: str) -> str:
    return os.path.join(LOG_DIR, f"{channel}logs.json")

def load_log_ids(channel: str) -> Set[str]:
    log_path = get_log_path(channel)
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return set(data.keys())
        except:
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
        print(f"Ошибка сохранения лога для {channel}: {e}")

def load_config() -> Dict[str, str]:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return DEFAULT_LINKS.copy()
    else:
        return DEFAULT_LINKS.copy()

def save_config(config: Dict[str, str]):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

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

reply_map: Dict[int, Tuple[str, str]] = {}
awaiting_lang: Dict[int, Dict] = {}

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
    url = f"{MONITOR_CONFIG['API_BASE_URL']}/social/findUser?{query}"
    try:
        r = requests.get(url, timeout=MONITOR_CONFIG["REQUEST_TIMEOUT"])
        r.raise_for_status()
        return str(r.json()["_id"])
    except:
        return "error: user not found or API error"

def _get_id_from_chat(keyword: str, chat_region: str) -> str:
    url = f"{MONITOR_CONFIG['FIREBASE_URL']}/Chat/Messages/{chat_region}.json?orderBy=\"ts\"&limitToLast=20"
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
        except:
            return "error: invalid hash format"

    if _has_cyrillic(nickname):
        try:
            import base64
            enc = base64.b64encode(nickname.encode()).decode()
            return _fetch_user_id(f"nick=@{enc}")
        except:
            return "error: encoding failed"

    return _fetch_user_id(f"nick={nickname}")

def get_player_nick(player_id: str) -> Optional[str]:
    if player_id in nick_cache:
        return nick_cache[player_id]
    url = f"{MONITOR_CONFIG['API_BASE_URL']}/social/findUser?ID={player_id}"
    try:
        r = requests.get(url, timeout=MONITOR_CONFIG["REQUEST_TIMEOUT"])
        if r.status_code == 200:
            data = r.json()
            nick = data.get('nick')
            if nick:
                nick_cache[player_id] = nick
                return nick
    except:
        pass
    return None

def send_chat_message(sender_id: str, message: str, channel: str) -> bool:
    url = f"{MONITOR_CONFIG['API_BASE_URL']}/social/sendChat"
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
            print(f"Ошибка отправки в игру: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        print(f"Исключение при отправке: {e}")
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
        print(f"Flood control для чата {chat_id}, тема {thread_id}, ждём {e.retry_after} сек")
        return False
    except Exception as e:
        print(f"Ошибка отправки в Telegram-чат {chat_id} (тема {thread_id}): {e}")
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
            
            url = f"{MONITOR_CONFIG['FIREBASE_URL']}/Chat/Messages/{game_channel}.json?orderBy=\"ts\"&limitToLast={MONITOR_CONFIG['MAX_MESSAGES']}"
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

# ============= КОМАНДА РУЧНОЙ ЗАГРУЗКИ =============
async def download_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Сначала авторизуйся.")
        return

    if not monitor_running:
        await update.message.reply_text("⚠️ Мониторинг не запущен. Сначала запусти мониторинг командой /monitor.")
        return

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

    url = f"{MONITOR_CONFIG['FIREBASE_URL']}/Chat/Messages/{channel}.json?orderBy=\"ts\"&limitToLast={limit}"
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
                await update.message.reply_text(f"❌ Ошибка загрузки из Firebase: {e}")
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

# ============= ОТПРАВКА ОТВЕТА ИГРОКУ (reply) =============
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
        else:  # US, PL, DE, DEV
            prefix = "reply to player:"
    
    reply_text = f"{prefix} {nick} - {user_text}"
    success = send_chat_message(sender_id, reply_text, channel)
    
    if success:
        await update.message.reply_text(f"✅ Ответ отправлен игроку {nick} в канал {channel}")
    else:
        await update.message.reply_text("❌ Не удалось отправить ответ в игру.")

# ============= АВТОРИЗАЦИЯ =============
def is_authorized(user_id: int) -> bool:
    return user_id in authorised_users or user_id == OWNER_ID

# ============= ОБРАБОТЧИКИ КОМАНД =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_authorized(user_id):
        await update.message.reply_text("👋 Ты уже авторизован. Используй /help для списка команд.")
    else:
        await update.message.reply_text(
            "🔐 Для доступа к боту введи пароль.\n"
            "Используй /login <пароль> или просто отправь пароль в чат."
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Сначала авторизуйся.")
        return
    text = (
        "📋 Доступные команды:\n\n"
        "/login <пароль> – авторизация\n"
        "/channels – показать текущие привязки каналов\n"
        "/setlink <игровой_канал> <ссылка> – изменить ссылку для канала\n"
        "   Пример: /setlink RU https://t.me/c/3534308756/3\n"
        "/setid <новый ID> – сменить ID отправителя в игре\n"
        "/showid – показать текущий ID отправителя\n"
        "/monitor – запустить мониторинг\n"
        "/stop – остановить задачу (например /stop Мониторинг RU или /stop TradeBlocker)\n"
        "/status – статус мониторинга\n"
        "/download КАНАЛ [количество] – принудительно загрузить последние сообщения из канала (только при активном мониторинге)\n"
        "   Пример: /download DEV 40\n"
        "/block trade – запустить блокировку трейдов (автопринятие)\n"
        "/block trade stop – остановить блокировку\n"
        "/block trade status – показать статистику заблокированных трейдов\n"
        "/skin download – скачать JSON-файл с информацией о заблокированных скинах\n"
        "/send all <айди> – выдать игроку максимальные монеты, опыт и кейсы (требует подтверждения)\n"
        "/parsing start – запустить парсер аккаунтов\n"
        "/parsing stop – остановить парсер\n"
        "/parsing status – показать статистику парсера\n"
        "/nuke – сбросить данные игрока (использовать как ответ на сообщение в чате мониторинга)\n"
        "/setpass <новый пароль> – сменить пароль (только для владельца)\n"
        "/help – это сообщение\n\n"
        "📝 **Как использовать мониторинг:**\n"
        "• Просто напиши сообщение в любой из отслеживаемых веток – оно отправится в игру.\n"
        "• Ответь (reply) на любое сообщение, чтобы ответить игроку.\n"
        "• Для PREMIUM-канала при ответе бот спросит язык.\n"
        "• Для NUKE: ответь на сообщение игрока в чате и отправь /nuke – данные игрока будут сброшены.\n"
        "• Для разблокировки трейда: ответь на сообщение о заблокированном трейде словом \"разблокировать\".\n\n"
        "Доступные игровые каналы: RU, UA, US, PL, DE, PREMIUM, DEV"
    )
    await update.message.reply_text(text)

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_authorized(user_id):
        await update.message.reply_text("✅ Ты уже авторизован.")
        return
    if not context.args:
        await update.message.reply_text("Укажи пароль: /login <пароль>")
        return
    entered = ' '.join(context.args)
    if entered == PASSWORD:
        authorised_users.add(user_id)
        await update.message.reply_text("✅ Пароль верный! Доступ получен.")
    else:
        await update.message.reply_text("❌ Неверный пароль.")

async def setpass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("⛔ Только владелец может менять пароль.")
        return
    if not context.args:
        await update.message.reply_text("Укажи новый пароль: /setpass <пароль>")
        return
    global PASSWORD
    PASSWORD = ' '.join(context.args)
    await update.message.reply_text("✅ Пароль изменён.")

async def channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Сначала авторизуйся.")
        return
    text = "🔗 Текущие привязки каналов:\n"
    for game, link in channel_config.items():
        text += f"• {game}: {link}\n"
    await update.message.reply_text(text)

async def setlink_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Сначала авторизуйся.")
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Использование: /setlink <игровой_канал> <ссылка>\nПример: /setlink RU https://t.me/c/3534308756/3")
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

async def setid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Сначала авторизуйся.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Укажи новый ID: /setid EfezAdmin1")
        return
    new_id = args[0]
    sender_ids[chat_id] = new_id
    await update.message.reply_text(f"✅ ID отправителя для этого чата изменён на: {new_id}")

async def showid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Сначала авторизуйся.")
        return
    current = sender_ids.get(chat_id, DEFAULT_SENDER_ID)
    await update.message.reply_text(f"🆔 Текущий ID отправителя: {current}")

async def monitor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Сначала авторизуйся.")
        return
    global monitor_running, monitor_task
    if monitor_running:
        await update.message.reply_text("⚠️ Мониторинг уже запущен.")
        return
    monitor_running = True
    monitor_task = asyncio.create_task(monitor_worker(context.bot))
    active_tasks["Мониторинг"] = monitor_task
    await update.message.reply_text("✅ Мониторинг запущен. Сообщения будут пересылаться в указанные Telegram-чаты.")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Сначала авторизуйся.")
        return

    global monitor_running, monitor_task

    if not context.args:
        await update.message.reply_text("Укажи имя задачи: /stop <имя> (например /stop Мониторинг RU или /stop TradeBlocker)")
        return

    task_name = ' '.join(context.args)

    if task_name.lower() == "tradeblocker":
        if stop_blocker():
            await update.message.reply_text("✅ Блокировка трейдов остановлена.")
        else:
            await update.message.reply_text("❌ Блокировка трейдов не была запущена.")
        return

    # Проверяем задачи мониторинга
    if task_name not in active_tasks:
        await update.message.reply_text(f"❌ Задача '{task_name}' не найдена.")
        return

    task = active_tasks[task_name]
    if not task.done():
        task.cancel()
        await update.message.reply_text(f"✅ Задача '{task_name}' остановлена.")
    else:
        await update.message.reply_text(f"⚠️ Задача '{task_name}' уже завершена.")
    if task_name in active_tasks:
        del active_tasks[task_name]

async def block_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Сначала авторизуйся.")
        return

    args = context.args
    if not args:
        await update.message.reply_text("Использование: /block trade | /block trade stop | /block trade status")
        return

    subcmd = args[0].lower()
    if subcmd == "trade":
        if len(args) == 1:
            if blocker_is_running():
                await update.message.reply_text("⚠️ Блокировка трейдов уже запущена.")
                return
            start_blocker(context.bot, TRADE_NOTIFY_CHAT, TRADE_NOTIFY_THREAD, active_tasks)
            await update.message.reply_text("✅ Блокировка трейдов запущена. Новые обмены будут приниматься.")
        elif len(args) >= 2:
            if args[1].lower() == "stop":
                if stop_blocker():
                    await update.message.reply_text("✅ Блокировка трейдов остановлена.")
                else:
                    await update.message.reply_text("❌ Блокировка трейдов не была запущена.")
            elif args[1].lower() == "status":
                stats = get_blocker_stats()
                if stats:
                    text = f"📊 **Статистика блокировки трейдов**\n• Всего заблокировано: {stats['blocked']}"
                    if stats['running']:
                        text += "\n• Статус: 🔴 работает"
                    else:
                        text += "\n• Статус: ⏸ остановлен"
                    await update.message.reply_text(text)
                else:
                    await update.message.reply_text("Блокировка трейдов не запускалась.")
            else:
                await update.message.reply_text("Неизвестная подкоманда. Используй /block trade [stop|status]")
        else:
            await update.message.reply_text("Неверный формат. Используй /block trade | /block trade stop | /block trade status")
    else:
        await update.message.reply_text("Неизвестная команда. Используй /block trade")

async def parsing_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Сначала авторизуйся.")
        return

    args = context.args
    if not args:
        await update.message.reply_text("Использование:\n/parsing start – запустить парсер\n/parsing stop – остановить\n/parsing status – статус")
        return

    subcmd = args[0].lower()
    global parser_thread, parser_stop_event

    if subcmd == "start":
        if parser_thread and parser_thread.is_alive():
            await update.message.reply_text("⚠️ Парсер уже запущен.")
            return
        parser_stop_event = threading.Event()
        parser_thread = threading.Thread(target=run_parser, args=("parsing", parser_stop_event), daemon=True)
        parser_thread.start()
        await update.message.reply_text("✅ Парсер запущен. Файлы сохраняются в папку parsing/")
    elif subcmd == "stop":
        if not parser_thread or not parser_thread.is_alive():
            await update.message.reply_text("❌ Парсер не запущен.")
            return
        parser_stop_event.set()
        await update.message.reply_text("🛑 Сигнал остановки отправлен. Парсер завершится через несколько секунд.")
    elif subcmd == "status":
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

async def nuke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Сначала авторизуйся.")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Команда /nuke должна быть ответом (reply) на сообщение в чате мониторинга.")
        return

    replied_msg = update.message.reply_to_message
    if replied_msg.from_user.id != context.bot.id:
        await update.message.reply_text("❌ Можно отвечать только на сообщения, отправленные ботом (из мониторинга).")
        return

    nick = extract_nick_from_text(replied_msg.text)
    if not nick:
        await update.message.reply_text("❌ Не удалось извлечь ник игрока из сообщения.")
        return

    thread_id = replied_msg.message_thread_id
    game_channel = thread_to_channel.get(thread_id) if thread_id else "RU"

    await update.message.reply_text(f"🔍 Ищу ID игрока {nick} в канале {game_channel}...")
    
    player_id = get_user_id(nick, game_channel)
    if player_id.startswith("error"):
        await update.message.reply_text(f"❌ Не удалось найти ID для ника {nick}: {player_id}")
        return

    await update.message.reply_text(f"⚠️ Найден ID: {player_id}. Выполняю NUKE...")
    success, message = nuke_player(player_id)
    if success:
        await update.message.reply_text(f"✅ NUKE выполнен успешно!\n{message}")
    else:
        await update.message.reply_text(f"❌ Ошибка при выполнении NUKE:\n{message}")

async def skin_download_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Сначала авторизуйся.")
        return

    skin_file = "skins/skin.json"
    if not os.path.exists(skin_file):
        await update.message.reply_text("❌ Файл с информацией о скинах ещё не создан.")
        return

    try:
        with open(skin_file, "rb") as doc:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=doc,
                filename="skin.json"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при отправке файла: {e}")

# ============= НОВАЯ КОМАНДА ДЛЯ ВЫДАЧИ МАКСИМАЛЬНЫХ ХАРАКТЕРИСТИК =============
async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Сначала авторизуйся.")
        return

    args = context.args
    if len(args) < 2 or args[0].lower() != "all":
        await update.message.reply_text("Использование: /send all <айди игрока>")
        return

    target_id = args[1]
    # Сохраняем в user_data информацию для подтверждения
    context.user_data['pending_send'] = target_id

    keyboard = [
        [
            InlineKeyboardButton("✅ Да", callback_data="confirm_send"),
            InlineKeyboardButton("❌ Нет", callback_data="cancel_send")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Вы уверены, что хотите применить максимальные характеристики к игроку {target_id}? (Это может работать только после переустановки игры)",
        reply_markup=reply_markup
    )

async def send_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_authorized(user_id):
        await query.edit_message_text("⛔ Сначала авторизуйся.")
        return

    if query.data == "confirm_send":
        target_id = context.user_data.get('pending_send')
        if not target_id:
            await query.edit_message_text("❌ Данные не найдены. Попробуйте снова.")
            return
        await query.edit_message_text(f"⏳ Применяю максимальные характеристики к игроку {target_id}...")
        success, message = apply_max_stats(target_id)
        if success:
            await query.edit_message_text(f"✅ Успешно!\n{message}")
        else:
            await query.edit_message_text(f"❌ Ошибка:\n{message}")
        context.user_data.pop('pending_send', None)
    elif query.data == "cancel_send":
        await query.edit_message_text("❌ Действие отменено.")
        context.user_data.pop('pending_send', None)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Сначала авторизуйся.")
        return
    if monitor_running:
        await update.message.reply_text("📡 Мониторинг активен.")
    else:
        await update.message.reply_text("⏸ Мониторинг не запущен.")

# ============= ГЛАВНЫЙ ОБРАБОТЧИК СООБЩЕНИЙ =============
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    # Сначала проверяем, не является ли сообщение ответом для разблокировки трейда
    if await handle_unblock_reply(update, context):
        return

    # Проверяем авторизацию
    if not is_authorized(user_id):
        if text == PASSWORD:
            authorised_users.add(user_id)
            await update.message.reply_text("✅ Пароль верный! Доступ получен.")
        else:
            await update.message.reply_text("❌ Неверный пароль. Попробуй ещё раз или используй /login.")
        return

    # Авторизован: обрабатываем диалоги и прочее
    chat_id = update.effective_chat.id

    if chat_id in awaiting_lang:
        data = awaiting_lang[chat_id]
        choice = text.strip().upper()
        if choice in ("RU", "US"):
            await send_reply(update, context, data['nick'], data['channel'], data['text'], lang=choice)
            del awaiting_lang[chat_id]
        else:
            await update.message.reply_text("Пожалуйста, выберите RU или US.")
        return

    if update.message.reply_to_message:
        replied_msg = update.message.reply_to_message
        if replied_msg.from_user.id == context.bot.id:
            nick = extract_nick_from_text(replied_msg.text)
            thread_id = replied_msg.message_thread_id
            game_channel = thread_to_channel.get(thread_id) if thread_id else None
            if nick and game_channel:
                if game_channel == "PREMIUM":
                    awaiting_lang[chat_id] = {
                        'nick': nick,
                        'channel': game_channel,
                        'text': text,
                        'original_msg_id': replied_msg.message_id
                    }
                    await update.message.reply_text("Выберите язык ответа: RU или US")
                else:
                    await send_reply(update, context, nick, game_channel, text)
            else:
                await update.message.reply_text("Не удалось извлечь ник или канал.")
            return

    if update.message.message_thread_id and update.message.message_thread_id in thread_to_channel:
        game_channel = thread_to_channel[update.message.message_thread_id]
        sender_id = sender_ids.get(chat_id, DEFAULT_SENDER_ID)
        success = send_chat_message(sender_id, text, game_channel)
        if success:
            await update.message.reply_text(f"✅ Сообщение отправлено в канал {game_channel}")
        else:
            await update.message.reply_text("❌ Не удалось отправить сообщение в игру.")
        return

    await update.message.reply_text("Используй /help для списка команд.")

def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs("skins", exist_ok=True)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("setpass", setpass))
    app.add_handler(CommandHandler("channels", channels_command))
    app.add_handler(CommandHandler("setlink", setlink_command))
    app.add_handler(CommandHandler("setid", setid_command))
    app.add_handler(CommandHandler("showid", showid_command))
    app.add_handler(CommandHandler("monitor", monitor_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("download", download_command))
    app.add_handler(CommandHandler("block", block_command))
    app.add_handler(CommandHandler("parsing", parsing_command))
    app.add_handler(CommandHandler("nuke", nuke_command))
    app.add_handler(CommandHandler("skin", skin_download_command))
    app.add_handler(CommandHandler("send", send_command))  # новая команда
    app.add_handler(CallbackQueryHandler(send_callback, pattern="^(confirm_send|cancel_send)$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 Монитор-бот с блокировкой трейдов, парсером, NUKE и выдачей характеристик запущен. Нажми Ctrl+C для остановки.")
    app.run_polling()

if __name__ == "__main__":
    main()
