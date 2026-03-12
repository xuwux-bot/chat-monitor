# main bot.py (сборка)
import asyncio
import os
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Импорты конфигурации
from config import BOT_TOKEN, OWNER_ID

# Импорты утилит
from data_utils import load_json, save_json, PLAYERS_FILE, INVENTORY_FILE
from roles import check_admin_expiry

# Импорты регистрации
from registration import start_registration, chat_selected, confirm_registration

# Импорты меню
from menu import show_user_menu, show_admin_menu, menu_callback

# Импорты профиля
from profile import profile_command

# Импорты денег
from money import money_command, give_money, money_set, money_take, manage_money_menu

# Импорты скинов
from skins import skin_give_command, skin_select_callback, skin_choose_quality, skin_quality_selected, skin_toggle_st, skin_toggle_sv, skin_modifier_done, skin_qty_selected, skin_execute

# Импорты инвентаря
from inventory_display import inventory_command, skin_info_callback

# Импорты старых команд
from legacy_commands import monitor_command, block_trade_command, parsing_command, nuke_command, send_command

# ============= Хэлперы =============
def update_command_stats(user_id):
    players = load_json(PLAYERS_FILE, {})
    if str(user_id) in players:
        players[str(user_id)]['commands_count'] = players[str(user_id)].get('commands_count',0) + 1
        players[str(user_id)]['last_command_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_json(PLAYERS_FILE, players)

# ============= Команды =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    players = load_json(PLAYERS_FILE, {})
    if str(user_id) in players:
        # уже зарегистрирован
        role = players[str(user_id)].get('role')
        if role == 'user':
            await show_user_menu(update, context)
        else:
            # админ или овнер — показываем выбор меню
            keyboard = [
                [InlineKeyboardButton("👤 Меню игрока", callback_data='menu_user')],
                [InlineKeyboardButton("⚙️ Админ-меню", callback_data='menu_admin')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Выберите меню:", reply_markup=reply_markup)
    else:
        await start_registration(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    players = load_json(PLAYERS_FILE, {})
    if str(user_id) not in players:
        await update.message.reply_text("Сначала зарегистрируйтесь через /start")
        return
    role = players[str(user_id)].get('role')
    if role == 'user':
        text = (
            "📋 Доступные команды:\n"
            "/profile - профиль\n"
            "/money - баланс\n"
            "/inventory - инвентарь\n"
            "/help - это сообщение"
        )
    else:
        text = (
            "📋 Команды администратора:\n"
            "/profile [ник] - профиль (с ником для владельца)\n"
            "/give money <ник> <кол> - выдать монеты\n"
            "/money set <ник> <кол> - установить монеты\n"
            "/money take <ник> <кол> - забрать монеты\n"
            "/skin give <ник> <скин> - выдать скин\n"
            "/monitor - мониторинг чата (только владелец)\n"
            "/block trade - блокировка трейдов (только владелец)\n"
            "/parsing - парсер (только владелец)\n"
            "/nuke - сброс игрока (ответом на сообщение)\n"
            "/send all <id> - выдать характеристики\n"
            "/addadmin <id> [срок] - добавить админа\n"
            "/deladmin <id> - удалить админа\n"
            "/help - это сообщение"
        )
    await update.message.reply_text(text)

async def addadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔ Недоступно")
        return
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("Использование: /addadmin <telegram_id> [срок]")
        return
    target_id = args[0]
    expiry = args[1] if len(args) > 1 else None
    from roles import add_admin
    if add_admin(target_id, expiry):
        await update.message.reply_text(f"✅ Админ {target_id} добавлен")
    else:
        await update.message.reply_text("❌ Пользователь не найден")

async def deladmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔ Недоступно")
        return
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("Использование: /deladmin <telegram_id>")
        return
    target_id = args[0]
    from roles import remove_admin
    if remove_admin(target_id):
        await update.message.reply_text(f"✅ Админ {target_id} удалён")
    else:
        await update.message.reply_text("❌ Пользователь не найден")

# ============= Обработчик всех сообщений (для счётчика команд) =============
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # если это команда, она уже обработана, но мы можем добавить счётчик в её обработчиках.
    # В этом обработчике только не-команды.
    pass

# ============= Main =============
def main():
    # Создаём папки
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    # Проверка истечения админок
    check_admin_expiry()

    app = Application.builder().token(BOT_TOKEN).build()

    # Регистрация
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(chat_selected, pattern='^reg_chat_'))
    app.add_handler(CommandHandler("confirm", confirm_registration))

    # Меню
    app.add_handler(CallbackQueryHandler(menu_callback, pattern='^menu_'))

    # Профиль
    app.add_handler(CommandHandler("profile", profile_command))

    # Деньги
    app.add_handler(CommandHandler("money", money_command))
    app.add_handler(CommandHandler("give", give_money))
    app.add_handler(CommandHandler("money_set", money_set))
    app.add_handler(CommandHandler("money_take", money_take))

    # Скины
    app.add_handler(CommandHandler("skin", skin_give_command))
    app.add_handler(CallbackQueryHandler(skin_select_callback, pattern='^skin_select_'))
    app.add_handler(CallbackQueryHandler(skin_choose_quality, pattern='^skin_choose_quality$'))
    app.add_handler(CallbackQueryHandler(skin_quality_selected, pattern='^skin_qual_'))
    app.add_handler(CallbackQueryHandler(skin_toggle_st, pattern='^skin_toggle_st$'))
    app.add_handler(CallbackQueryHandler(skin_toggle_sv, pattern='^skin_toggle_sv$'))
    app.add_handler(CallbackQueryHandler(skin_modifier_done, pattern='^skin_modifier_done$'))
    app.add_handler(CallbackQueryHandler(skin_qty_selected, pattern='^skin_qty_'))
    app.add_handler(CallbackQueryHandler(skin_execute, pattern='^skin_execute$'))

    # Инвентарь
    app.add_handler(CommandHandler("inventory", inventory_command))
    app.add_handler(CallbackQueryHandler(skin_info_callback, pattern='^skin_info_'))

    # Админка
    app.add_handler(CommandHandler("addadmin", addadmin_command))
    app.add_handler(CommandHandler("deladmin", deladmin_command))

    # Легаси команды (только для владельца/админов)
    app.add_handler(CommandHandler("monitor", monitor_command))
    app.add_handler(CommandHandler("block", block_trade_command))
    app.add_handler(CommandHandler("parsing", parsing_command))
    app.add_handler(CommandHandler("nuke", nuke_command))
    app.add_handler(CommandHandler("send", send_command))

    # Help
    app.add_handler(CommandHandler("help", help_command))

    # Обработчик остальных сообщений (не команд)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
