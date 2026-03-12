# registration.py
import random
import string
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import FIREBASE_URL
from data_utils import save_json, load_json, PLAYERS_FILE

def generate_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Первый шаг: выбор чата"""
    keyboard = [
        [InlineKeyboardButton("🇷🇺 RU", callback_data='reg_chat_RU')],
        [InlineKeyboardButton("🇺🇸 US", callback_data='reg_chat_US')],
        [InlineKeyboardButton("🇩🇪 DE", callback_data='reg_chat_DE')],
        [InlineKeyboardButton("🇵🇱 PL", callback_data='reg_chat_PL')],
        [InlineKeyboardButton("🇺🇦 UA", callback_data='reg_chat_UA')],
        [InlineKeyboardButton("💎 PREMIUM", callback_data='reg_chat_PREMIUM')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите игровой чат для подтверждения:", reply_markup=reply_markup)

async def chat_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat = query.data.split('_')[2]  # например 'RU'
    context.user_data['reg_chat'] = chat
    code = generate_code()
    context.user_data['reg_code'] = code
    await query.edit_message_text(
        f"Выбран чат: {chat}\n"
        f"Отправьте в этот игровой чат код: `{code}`\n"
        "Затем нажмите /confirm",
        parse_mode='Markdown'
    )

async def confirm_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if 'reg_chat' not in context.user_data or 'reg_code' not in context.user_data:
        await update.message.reply_text("Сначала выполните /start")
        return

    chat = context.user_data['reg_chat']
    code = context.user_data['reg_code']

    # Проверяем наличие сообщения в Firebase
    try:
        url = f"{FIREBASE_URL}/Chat/Messages/{chat}.json?orderBy=\"ts\"&limitToLast=5000"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            messages = resp.json()
            if messages:
                for msg_id, msg in messages.items():
                    if msg.get('msg') == code:
                        game_id = msg.get('playerID')
                        game_nick = msg.get('nick')
                        # Регистрация успешна
                        players = load_json(PLAYERS_FILE, {})
                        players[user_id] = {
                            "role": "user",
                            "tg_username": update.effective_user.username,
                            "registered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "commands_count": 0,
                            "last_command_at": "",
                            "game_chat": chat,
                            "game_id": game_id,
                            "game_nick": game_nick,
                            "coins": 0,
                            "banned": False,
                            "admin_expires": None
                        }
                        save_json(PLAYERS_FILE, players)
                        # Инвентарь создаётся отдельно
                        inv = load_json(INVENTORY_FILE, {})
                        if user_id not in inv:
                            inv[user_id] = {"skins": [], "cases": []}
                            save_json(INVENTORY_FILE, inv)

                        await update.message.reply_text(
                            f"✅ Регистрация успешна!\n"
                            f"Игровой ник: {game_nick}\n"
                            f"ID: {game_id}"
                        )
                        # Очищаем временные данные
                        del context.user_data['reg_chat']
                        del context.user_data['reg_code']
                        # Показываем меню
                        await show_user_menu(update, context)
                        return
        await update.message.reply_text("❌ Код не найден. Попробуйте снова /start")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
