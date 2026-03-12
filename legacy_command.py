# legacy_commands.py
from telegram import Update
from telegram.ext import ContextTypes
from data_utils import load_json, PLAYERS_FILE
import asyncio

# ID владельца (захардкожен, но можно импортировать из config)
OWNER_ID = 5150403377

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

def is_admin_or_owner(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    players = load_json(PLAYERS_FILE, {})
    role = players.get(str(user_id), {}).get('role')
    return role == 'admin'

# ============= ЗАГЛУШКИ ДЛЯ КОМАНД =============
# Позже ты заменишь их на реальный код из старых скриптов

async def monitor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /monitor - запуск мониторинга чата (только для владельца)"""
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    await update.message.reply_text("📡 Мониторинг чата (заглушка)")

async def block_trade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /block trade - блокировка трейдов (только для владельца)"""
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    await update.message.reply_text("🔒 Блокировка трейдов (заглушка)")

async def parsing_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /parsing - парсер аккаунтов (только для владельца)"""
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    await update.message.reply_text("🔄 Парсер аккаунтов (заглушка)")

async def nuke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /nuke - сброс данных игрока (для админов и владельца)"""
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    await update.message.reply_text("💥 NUKE (заглушка)")

async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /send all <id> - выдача характеристик (для админов и владельца)"""
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    await update.message.reply_text("📦 Выдача характеристик (заглушка)")

# Экспортируем всё, что нужно для bot.py
__all__ = [
    'monitor_command',
    'block_trade_command',
    'parsing_command',
    'nuke_command',
    'send_command'
]
