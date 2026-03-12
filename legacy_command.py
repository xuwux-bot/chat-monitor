# legacy_commands.py
from telegram import Update
from telegram.ext import ContextTypes
from data_utils import load_json, PLAYERS_FILE
from scripts.trade_blocker import start_blocker, stop_blocker, get_blocker_stats, blocker_is_running
from scripts.parser import run_parser, get_stats as get_parser_stats
from scripts.nuke import nuke_player
from scripts.equipment import apply_max_stats

OWNER_ID = 5150403377

def is_owner(user_id):
    return user_id == OWNER_ID

def is_admin_or_owner(user_id):
    players = load_json(PLAYERS_FILE, {})
    role = players.get(str(user_id), {}).get('role')
    return role in ('admin','owner') or user_id == OWNER_ID

async def monitor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    # здесь старый код /monitor
    await update.message.reply_text("Мониторинг запущен (заглушка)")

async def block_trade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    # старый код блокировки
    await update.message.reply_text("Блокировка трейдов (заглушка)")

async def parsing_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    await update.message.reply_text("Парсер (заглушка)")

async def nuke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    # старый nuke (с reply)
    await update.message.reply_text("NUKE (заглушка)")

async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("⛔ Недоступно")
        return
    await update.message.reply_text("Выдача характеристик (заглушка)")
