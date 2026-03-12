# profile.py
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from data_utils import load_json, PLAYERS_FILE, get_player_by_nick

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    players = load_json(PLAYERS_FILE, {})
    owner_id = 5150403377

    # Проверка на бан
    if players.get(user_id, {}).get('banned'):
        await update.message.reply_text("Вы забанены")
        return

    # Если указан ник другого игрока (только для owner)
    args = context.args
    if args and user_id == str(owner_id):
        target_nick = args[0]
        target_id = get_player_by_nick(target_nick, players)
        if not target_id:
            await update.message.reply_text("Игрок не найден")
            return
        pdata = players[target_id]
        await update.message.reply_text(
            f"👤 Профиль {target_nick}\n"
            f"Роль: {pdata.get('role')}\n"
            f"Монеты: {pdata.get('coins', 0)}\n"
            f"Дата регистрации: {pdata.get('registered_at', 'неизвестно')}"
        )
        return

    # Свой профиль
    if user_id not in players:
        await update.message.reply_text("Сначала зарегистрируйтесь через /start")
        return
    pdata = players[user_id]
    await update.message.reply_text(
        f"👤 Профиль\n"
        f"Ник в игре: {pdata.get('game_nick')}\n"
        f"Роль: {pdata.get('role')}\n"
        f"Монеты: {pdata.get('coins', 0)}\n"
        f"Дата регистрации: {pdata.get('registered_at', 'неизвестно')}"
    )
