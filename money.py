# money.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from data_utils import load_json, save_json, PLAYERS_FILE, INVENTORY_FILE, get_player_by_nick

async def money_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    players = load_json(PLAYERS_FILE, {})
    if user_id not in players:
        await update.message.reply_text("Сначала зарегистрируйтесь")
        return
    coins = players[user_id].get('coins', 0)
    await update.message.reply_text(f"💰 Ваш баланс: {coins} монет")

async def manage_money_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text(
        "Управление монетами:\n"
        "/give money <ник> <количество>\n"
        "/money set <ник> <количество>\n"
        "/money take <ник> <количество>"
    )

async def give_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    players = load_json(PLAYERS_FILE, {})
    if players.get(user_id, {}).get('role') not in ('admin','owner'):
        await update.message.reply_text("Недостаточно прав")
        return
    args = context.args
    if len(args) < 3 or args[0].lower() != 'money':
        await update.message.reply_text("Использование: /give money <ник> <количество>")
        return
    target_nick = args[1]
    try:
        amount = int(args[2])
    except:
        await update.message.reply_text("Количество должно быть числом")
        return
    target_id = get_player_by_nick(target_nick, players)
    if not target_id:
        await update.message.reply_text("Игрок не найден")
        return
    players[target_id]['coins'] = players[target_id].get('coins', 0) + amount
    save_json(PLAYERS_FILE, players)
    await update.message.reply_text(f"✅ Игроку {target_nick} выдано {amount} монет")

async def money_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # аналогично, с проверкой прав
    pass

async def money_take(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # аналогично
    pass
