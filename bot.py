#!/usr/bin/env python3
import asyncio
import json
import os
import re
import time
import threading
import random
import string
from datetime import datetime, timedelta
from typing import Dict, Set, Optional, Tuple, Any, List

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.error import RetryAfter

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8645051590:AAHic0cgu1E12kwEC2g81R0VM9iqf-Sq1PQ"
GAME_API_TOKEN = "Zluavtkju9WkqLYzGVKg"
DEFAULT_SENDER_ID = "EfezAdmin1"
OWNER_ID = 5150403377
FIREBASE_URL = "https://api-project-7952672729.firebaseio.com"
API_BASE_URL = "https://api.efezgames.com/v1"
REFERRAL_BONUS = 1500  # монет за приглашенного друга

# Файлы данных
PLAYERS_FILE = "data/players.json"
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
    "API_BASE_URL": API_BASE_URL,
    "FIREBASE_URL": FIREBASE_URL,
    "REQUEST_TIMEOUT": 10,
    "RETRY_ATTEMPTS": 3,
    "RETRY_DELAY": 2
}
# ==============================================

# Импортируем старые модули (должны лежать в папке scripts)
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

# ============= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============
def load_json(filename: str, default=None):
    if default is None:
        default = {} if 'players' in filename else []
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(filename: str, data):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

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

# ============= ФУНКЦИИ ДЛЯ РАБОТЫ С МОНЕТАМИ =============
def format_coins(amount: int) -> str:
    return f"{amount:,}".replace(",", ".")

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
        except:
            pass

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
    coins_str = format_coins(coins)

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

    text = (
        f"🍓 **Административный профиль**\n\n"
        f"**Статистика** ⤵︎\n"
        f"• Зарегистрированный аккаунт: {pdata.get('game_nick', 'неизвестно')}\n"
        f"🕓 Дата регистрации: {pdata.get('registered_at', 'неизвестно')}\n"
        f"👛 Баланс: {coins_str}\n\n"
        f"**Информация** ⤵︎\n"
        f"🌹 Время до конца администратора: {time_left}"
    )
    await update.message.reply_text(text, parse_mode='Markdown')
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

    text = (
        f"⚡ **Реферальная система** ⤵︎\n"
        f"| Ваша ссылка: `{ref_link}`\n"
        f"| Вы хотите, чтобы после перехода по вашей ссылке\n"
        f"| вам автоматически приходил запрос в друзья?\n\n"
        f"**Текущий статус:** {'✅ Да' if auto_friend else '❌ Нет'}\n"
        f"**Количество рефералов:** {pdata.get('referral_count', 0)}\n"
        f"**Заработано монет:** {format_coins(pdata.get('referral_count', 0) * REFERRAL_BONUS)}"
    )

    # Одна кнопка, текст которой меняется в зависимости от состояния
    button_text = "✅ Да" if auto_friend else "❌ Нет"
    keyboard = [[InlineKeyboardButton(button_text, callback_data="toggle_auto_friend")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
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

    text = (
        f"⚡ **Реферальная система** ⤵︎\n"
        f"| Ваша ссылка: `{ref_link}`\n"
        f"| Вы хотите, чтобы после перехода по вашей ссылке\n"
        f"| вам автоматически приходил запрос в друзья?\n\n"
        f"**Текущий статус:** {'✅ Да' if auto_friend else '❌ Нет'}\n"
        f"**Количество рефералов:** {players[str(user_id)].get('referral_count', 0)}\n"
        f"**Заработано монет:** {format_coins(players[str(user_id)].get('referral_count', 0) * REFERRAL_BONUS)}"
    )
    button_text = "✅ Да" if auto_friend else "❌ Нет"
    keyboard = [[InlineKeyboardButton(button_text, callback_data="toggle_auto_friend")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

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
        print(f"Не удалось отправить уведомление пользователю {target_id}: {e}")

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
    except:
        pass

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
    user_id = update.effective_user.id
    players = load_json(PLAYERS_FILE, {})
    current_user = players.get(str(user_id))
    if not current_user:
        await update.message.reply_text("❌ Сначала зарегистрируйтесь")
        return

    friends = current_user.get('friends', [])
    if not friends:
        await update.message.reply_text("У вас пока нет друзей")
        return

    text = "🧟‍♂️ **Ваши друзья** ⤵︎\n"
    keyboard = []
    for friend_nick in friends:
        text += f"- {friend_nick}\n"
        row = [
            InlineKeyboardButton("👤 Профиль", callback_data=f"friend_profile|{friend_nick}"),
            InlineKeyboardButton("🗑 Удалить", callback_data=f"friend_delete|{friend_nick}")
        ]
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def friend_profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    _, friend_nick = data.split('|', 1)
    user_id = str(query.from_user.id)

    players = load_json(PLAYERS_FILE, {})
    current_user = players.get(user_id)
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

    friend_data = players[friend_id]
    coins = friend_data.get('coins', 0)
    coins_str = format_coins(coins)

    text = (
        f"👤 **Профиль друга**\n"
        f"🗨️ Никнейм в игре: {friend_data.get('game_nick', 'неизвестно')}\n"
        f"🕓 Время регистрации: {friend_data.get('registered_at', 'неизвестно')}\n"
        f"👛 Баланс: {coins_str} монет"
    )
    await query.edit_message_text(text, parse_mode='Markdown')

async def friend_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    _, friend_nick = data.split('|', 1)
    user_id = str(query.from_user.id)

    players = load_json(PLAYERS_FILE, {})
    current_user = players.get(user_id)
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

    current_user['friends'].remove(friend_nick)
    if 'friends' in players[friend_id] and current_user['game_nick'] in players[friend_id]['friends']:
        players[friend_id]['friends'].remove(current_user['game_nick'])

    save_json(PLAYERS_FILE, players)

    await query.edit_message_text(
        f"✅ Вы удалили {friend_nick} из друзей.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Обновить список", callback_data="friend_refresh")]
        ])
    )

async def friend_refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    players = load_json(PLAYERS_FILE, {})
    current_user = players.get(str(user_id))
    if not current_user:
        await query.edit_message_text("❌ Ошибка")
        return

    friends = current_user.get('friends', [])
    if not friends:
        await query.edit_message_text("У вас пока нет друзей")
        return

    text = "🧟‍♂️ **Ваши друзья** ⤵︎\n"
    keyboard = []
    for friend_nick in friends:
        text += f"- {friend_nick}\n"
        row = [
            InlineKeyboardButton("👤 Профиль", callback_data=f"friend_profile|{friend_nick}"),
            InlineKeyboardButton("🗑 Удалить", callback_data=f"friend_delete|{friend_nick}")
        ]
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

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
        text += f"- {req_nick} ⤵︎\n"
        keyboard.append([
            InlineKeyboardButton("✅ Принять", callback_data=f"friend_accept|{req_nick}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"friend_decline|{req_nick}")
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

@require_registration
@check_ban
async def profile_friend_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2 or args[0].lower() != "friend":
        await update.message.reply_text("Использование: /profile friend <ник>")
        return
    friend_nick = args[1]

    players = load_json(PLAYERS_FILE, {})
    current_user = players.get(str(update.effective_user.id))
    if not current_user:
        return

    if friend_nick not in current_user.get('friends', []):
        await update.message.reply_text("❌ Этот пользователь не в вашем списке друзей")
        return

    friend_id = get_player_by_nick(friend_nick, players)
    if not friend_id:
        await update.message.reply_text("❌ Друг не найден в базе")
        return

    friend_data = players[friend_id]
    coins = friend_data.get('coins', 0)
    coins_str = format_coins(coins)

    text = (
        f"👤 **Профиль друга**\n"
        f"🗨️ Никнейм в игре: {friend_data.get('game_nick', 'неизвестно')}\n"
        f"🕓 Время регистрации: {friend_data.get('registered_at', 'неизвестно')}\n"
        f"👛 Баланс: {coins_str} монет"
    )
    await update.message.reply_text(text, parse_mode='Markdown')
    update_player_stats(update.effective_user.id)

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
    except Exception:
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    players = load_json(PLAYERS_FILE, {})

    if context.args and len(context.args) > 0:
        ref_code = context.args[0]
        context.user_data['referral_code'] = ref_code

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
            except:
                pass

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
                    except:
                        pass

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

# ============= ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ (С ВЫРОВНЕННЫМИ ЛИНИЯМИ) =============
@require_registration
@check_ban
async def show_user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    players = load_json(PLAYERS_FILE, {})
    pdata = players.get(user_id, {})
    coins = pdata.get('coins', 0)
    coins_str = format_coins(coins)
    friends_count = len(pdata.get('friends', []))
    referral_count = pdata.get('referral_count', 0)
    role = pdata.get('role', 'user')
    role_display = "Игрок" if role == "user" else ("Администратор" if role == "admin" else "Владелец")
    reg_time = pdata.get('registered_at', 'неизвестно')

    line = "=" * 45

    text = (
        f"👤 **Ваш профиль** ⤵︎\n"
        f"{line}\n"
        f"- 🗨️ Никнейм в игре: {pdata.get('game_nick', 'неизвестно')}\n"
        f"- 👑 Роль: {role_display}\n"
        f"- 🕓 Время регистрации: {reg_time}\n"
        f"- 💰 Баланс: {coins_str}\n"
        f"- 🧟‍♂️ Друзей: {friends_count}\n"
        f"- ⚡ Рефералов: {referral_count}\n"
        f"{line}\n"
        f"Информация ⤵︎\n"
        f"- Введите /help для списка команд.\n"
        f"-"
    )

    keyboard = [
        [KeyboardButton("🧟‍♂️ Добавить друга")],
        [KeyboardButton("👤 Список друзей")],
        [KeyboardButton("🕓 Активные запросы в друзья")],
        [KeyboardButton("⚡ Реферальная система")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    update_player_stats(int(user_id))

async def handle_reply_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if text == "👤 Меню игрока":
        await show_user_profile(update, context)
    elif text == "⚙️ Админ-меню":
        if not is_admin_or_owner(user_id):
            await update.message.reply_text("⛔ Доступ запрещён")
            return
        await show_admin_menu(update, context)
    elif text == "🧟‍♂️ Добавить друга":
        await friend_add_start(update, context)
    elif text == "👤 Список друзей":
        await friend_list(update, context)
    elif text == "🕓 Активные запросы в друзья":
        await friend_requests_list(update, context)
    elif text == "⚡ Реферальная система":
        await referral_system(update, context)
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
        pass

async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("👤 Мой профиль (админ)")],
        [KeyboardButton("🔍 Найти игрока")],
        [KeyboardButton("◀️ Назад")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

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

@check_ban
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

@check_ban
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

# ============= ФУНКЦИИ ДЛЯ ЛОГИРОВАНИЯ =============
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

# ============= ФУНКЦИИ МОНИТОРИНГА =============
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
    except:
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
    url = f"{API_BASE_URL}/social/findUser?ID={player_id}"
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

# ============= ФУНКЦИЯ ОТПРАВКИ ОТВЕТА ИГРОКУ =============
@require_registration
@check_ban
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

# ============= АДМИН-КОМАНДЫ =============
@check_ban
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

@check_ban
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

@check_ban
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

@check_ban
async def nuke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Ответьте на сообщение игрока")
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

@check_ban
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

@check_ban
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

@check_ban
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

@check_ban
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    if monitor_running:
        await update.message.reply_text("📡 Мониторинг активен.")
    else:
        await update.message.reply_text("⏸ Мониторинг не запущен.")
    update_player_stats(update.effective_user.id)

@check_ban
async def channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    text = "🔗 Текущие привязки каналов:\n"
    for game, link in channel_config.items():
        text += f"• {game}: {link}\n"
    await update.message.reply_text(text)
    update_player_stats(update.effective_user.id)

@check_ban
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

@check_ban
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

@check_ban
async def showid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    current = sender_ids.get(update.effective_chat.id, DEFAULT_SENDER_ID)
    await update.message.reply_text(f"🆔 Текущий ID отправителя: {current}")
    update_player_stats(update.effective_user.id)

@check_ban
async def skin_download_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    skin_file = "skins/skin.json"
    if not os.path.exists(skin_file):
        await update.message.reply_text("❌ Файл с информацией о скинах ещё не создан.")
        return
    with open(skin_file, "rb") as doc:
        await context.bot.send_document(chat_id=update.effective_chat.id, document=doc, filename="skin.json")
    update_player_stats(update.effective_user.id)

@require_registration
@check_ban
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    role = get_player_role(user_id)
    if role == "user":
        text = (
            "📋 **Доступные команды (игрок):**\n\n"
            "/start - главное меню / регистрация\n"
            "/profile - показать профиль\n"
            "/money - показать баланс\n"
            "/profile friend <ник> - просмотр профиля друга\n"
            "/help - это сообщение\n\n"
            "Для доступа к админ-командам нужна роль администратора."
        )
    else:
        text = (
            "📋 **Доступные команды (администратор):**\n\n"
            "**Мониторинг:**\n"
            "/monitor - запустить мониторинг чатов\n"
            "/status - статус мониторинга\n"
            "/download <канал> [количество] - загрузить последние сообщения из канала\n"
            "/channels - показать текущие привязки каналов\n"
            "/setlink <канал> <ссылка> - изменить ссылку для канала\n"
            "/setid <новый ID> - сменить ID отправителя в игре\n"
            "/showid - показать текущий ID отправителя\n\n"
            "**Монеты:**\n"
            "/money - показать свой баланс\n"
            "/money give <ник> <количество> - выдать монеты игроку\n"
            "/money set <ник> <количество> - установить баланс игрока\n"
            "/money take <ник> <количество> - забрать монеты у игрока\n\n"
            "**Трейды:**\n"
            "/block trade - запустить блокировку трейдов\n"
            "/block trade stop - остановить блокировку\n"
            "/block trade status - статистика заблокированных трейдов\n"
            "/skin download - скачать JSON с информацией о заблокированных скинах\n\n"
            "**Парсер аккаунтов:**\n"
            "/parsing start - запустить парсер\n"
            "/parsing stop - остановить парсер\n"
            "/parsing status - статус парсера\n\n"
            "**NUKE и выдача характеристик:**\n"
            "/nuke - сбросить данные игрока (ответом на сообщение)\n"
            "/send all <id> - выдать максимальные характеристики игроку\n\n"
            "**Управление админами:**\n"
            "/addadmin <telegram_id> [срок] - добавить админа\n"
            "/deladmin <telegram_id> - удалить админа\n"
            "/ban <ник> - забанить игрока в боте\n"
            "/unban <ник> - разбанить игрока\n\n"
            "**Остановка задач:**\n"
            "/stop <имя задачи> - остановить задачу (Мониторинг, TradeBlocker)\n\n"
            "**Общие:**\n"
            "/start - главное меню\n"
            "/profile - профиль\n"
            "/help - это сообщение"
        )
    await update.message.reply_text(text, parse_mode='Markdown')
    update_player_stats(update.effective_user.id)

@require_registration
@check_ban
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_user_profile(update, context)
    update_player_stats(update.effective_user.id)

# ============= ГЛАВНЫЙ ОБРАБОТЧИК СООБЩЕНИЙ =============
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if is_banned(user_id):
        await update.message.reply_text("❌ Вы были заблокированы")
        return

    if user_id in awaiting_friend_add:
        await handle_friend_add(update, context)
        return
    if user_id in awaiting_search:
        await handle_find_player(update, context)
        return

    if text in ["👤 Меню игрока", "⚙️ Админ-меню", "🧟‍♂️ Добавить друга", "👤 Список друзей", "🕓 Активные запросы в друзья", "⚡ Реферальная система", "👤 Мой профиль (админ)", "🔍 Найти игрока", "◀️ Назад"]:
        if not is_registered(user_id):
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

    app = Application.builder().token(BOT_TOKEN).build()

    # Регистрация
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(chat_selected, pattern='^reg_chat_'))
    app.add_handler(CommandHandler("confirm", confirm))

    # Профиль и помощь
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("help", help_command))

    # Монеты
    app.add_handler(CommandHandler("money", money_command))
    app.add_handler(CommandHandler("money_give", money_give_command))
    app.add_handler(CommandHandler("money_set", money_set_command))
    app.add_handler(CommandHandler("money_take", money_take_command))

    # Бан/разбан
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))

    # Управление админами
    app.add_handler(CommandHandler("addadmin", addadmin_command))
    app.add_handler(CommandHandler("deladmin", deladmin_command))

    # Команды мониторинга и старые команды
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

    # Друзья
    app.add_handler(CommandHandler("profile_friend", profile_friend_command))
    app.add_handler(CallbackQueryHandler(friend_accept_callback, pattern='^friend_accept\|'))
    app.add_handler(CallbackQueryHandler(friend_decline_callback, pattern='^friend_decline\|'))
    app.add_handler(CallbackQueryHandler(friend_profile_callback, pattern='^friend_profile\|'))
    app.add_handler(CallbackQueryHandler(friend_delete_callback, pattern='^friend_delete\|'))
    app.add_handler(CallbackQueryHandler(friend_refresh_callback, pattern='^friend_refresh$'))

    # Реферальная система
    app.add_handler(CallbackQueryHandler(toggle_auto_friend_callback, pattern='^toggle_auto_friend$'))

    # Обработчик текстовых сообщений
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 Бот с регистрацией, ролями, монетами, друзьями и реферальной системой запущен.")
    print("👤 Владелец ID:", OWNER_ID)
    print("📁 Данные сохраняются в папке data/")
    app.run_polling()

if __name__ == "__main__":
    main()
