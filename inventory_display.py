# inventory_display.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from data_utils import load_json, INVENTORY_FILE
from config import MODIFIERS_MAP

async def inventory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    inv = load_json(INVENTORY_FILE, {})
    user_inv = inv.get(user_id, {})
    skins = user_inv.get("skins", [])
    if not skins:
        await update.message.reply_text("Инвентарь пуст")
        return
    # Показываем список inline-кнопками
    keyboard = []
    for i, skin in enumerate(skins):
        # Текст кнопки: название (обрезанное)
        btn_text = f"{skin['name'][:30]} ({MODIFIERS_MAP[skin['modifier']]})"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f'skin_info_{i}')])
    # Добавляем кнопку "Назад", если нужно
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Ваши скины:", reply_markup=reply_markup)
    context.user_data['inv_skins'] = skins

async def skin_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split('_')[2])
    skins = context.user_data.get('inv_skins', [])
    if idx >= len(skins):
        await query.edit_message_text("Ошибка")
        return
    skin = skins[idx]
    await query.edit_message_text(
        f"🎨 {skin['name']}\n"
        f"Качество: {MODIFIERS_MAP[skin['modifier']]}\n"
        f"Код: {skin['code']}{skin['modifier']}"
    )
