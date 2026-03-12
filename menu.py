# menu.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from data_utils import load_json, PLAYERS_FILE

async def show_user_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню игрока (inline кнопки)"""
    keyboard = [
        [InlineKeyboardButton("👤 Профиль", callback_data='menu_profile')],
        [InlineKeyboardButton("💰 Монеты", callback_data='menu_money')],
        [InlineKeyboardButton("🎒 Инвентарь", callback_data='menu_inventory')],
        [InlineKeyboardButton("❓ Помощь", callback_data='menu_help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Меню игрока:", reply_markup=reply_markup)

async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню администратора"""
    keyboard = [
        [InlineKeyboardButton("👤 Профиль", callback_data='menu_profile')],
        [InlineKeyboardButton("💰 Монеты", callback_data='menu_money')],
        [InlineKeyboardButton("🎒 Инвентарь", callback_data='menu_inventory')],
        [InlineKeyboardButton("🎁 Выдать скин", callback_data='menu_give_skin')],
        [InlineKeyboardButton("🪙 Управление монетами", callback_data='menu_manage_money')],
        [InlineKeyboardButton("❓ Помощь", callback_data='menu_help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Админ-меню:", reply_markup=reply_markup)

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = str(query.from_user.id)
    players = load_json(PLAYERS_FILE, {})
    role = players.get(user_id, {}).get("role", "user")

    if data == 'menu_profile':
        await profile_command(update, context)
    elif data == 'menu_money':
        await money_command(update, context)
    elif data == 'menu_inventory':
        await inventory_command(update, context)
    elif data == 'menu_help':
        await help_command(update, context)
    elif data == 'menu_give_skin' and role in ('admin','owner'):
        await start_give_skin(update, context)
    elif data == 'menu_manage_money' and role in ('admin','owner'):
        await manage_money_menu(update, context)
    else:
        await query.edit_message_text("Доступ запрещён.")
