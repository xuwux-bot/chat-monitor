# skins.py
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from data_utils import load_json, save_json, INVENTORY_FILE, PLAYERS_FILE, get_player_by_nick
from config import MODIFIERS_MAP, SKINS_MAP_FILE

# Загружаем словарь скинов: код -> название
def load_skins_map():
    skin_map = {}
    if not os.path.exists(SKINS_MAP_FILE):
        return skin_map
    with open(SKINS_MAP_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or '|' not in line:
                continue
            parts = line.split('|', 1)
            code = parts[0].strip()[:2]  # берём первые два символа
            name = parts[1].strip()
            skin_map[code] = name
    return skin_map

# Обратный поиск по названию
def find_skins_by_name(query: str, skin_map: dict):
    results = []
    query = query.lower()
    for code, name in skin_map.items():
        if query in name.lower():
            results.append((code, name))
    return results

async def start_give_skin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text("Введите команду: /skin give <ник> <название скина>")

async def skin_give_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    players = load_json(PLAYERS_FILE, {})
    if players.get(user_id, {}).get('role') not in ('admin','owner'):
        await update.message.reply_text("Недостаточно прав")
        return
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("Использование: /skin give <ник> <название скина>")
        return
    target_nick = args[1]
    skin_query = ' '.join(args[2:]).lower()

    target_id = get_player_by_nick(target_nick, players)
    if not target_id:
        await update.message.reply_text("Игрок не найден")
        return
    context.user_data['give_skin_target'] = target_id

    skin_map = load_skins_map()
    matches = find_skins_by_name(skin_query, skin_map)
    if not matches:
        await update.message.reply_text("Скин не найден")
        return
    # Показываем первые 10 совпадений
    keyboard = []
    for code, name in matches[:10]:
        keyboard.append([InlineKeyboardButton(name[:50], callback_data=f'skin_select_{code}')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Найдены скины. Выберите:", reply_markup=reply_markup)

async def skin_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    code = query.data.split('_')[2]
    skin_map = load_skins_map()
    name = skin_map.get(code, "Неизвестный скин")
    context.user_data['selected_skin_code'] = code
    context.user_data['selected_skin_name'] = name

    keyboard = [
        [InlineKeyboardButton("❌ Назад", callback_data='skin_back_to_list')],
        [InlineKeyboardButton("✅ Вперёд", callback_data='skin_choose_quality')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"Вы выбрали скин:\nКод: {code}\nНазвание: {name}",
        reply_markup=reply_markup
    )

async def skin_choose_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Поношенное", callback_data='skin_qual_10')],
        [InlineKeyboardButton("После полевых испытаний", callback_data='skin_qual_20')],
        [InlineKeyboardButton("Немного поношенное", callback_data='skin_qual_30')],
        [InlineKeyboardButton("Прямо с завода", callback_data='skin_qual_40')],
        [InlineKeyboardButton("❌ Назад", callback_data='skin_back_to_select')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Выберите качество скина:", reply_markup=reply_markup)

async def skin_quality_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    base = int(query.data.split('_')[2])  # 10,20,30,40
    context.user_data['base_modifier'] = base
    # Теперь выбор StatTrak и Souvenir
    keyboard = [
        [InlineKeyboardButton("StatTrak: ❌", callback_data='skin_toggle_st')],
        [InlineKeyboardButton("Сувенирное: ❌", callback_data='skin_toggle_sv')],
        [InlineKeyboardButton("✅ Готово", callback_data='skin_modifier_done')],
        [InlineKeyboardButton("❌ Назад", callback_data='skin_choose_quality')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "Настройте модификаторы (нажимайте для переключения):",
        reply_markup=reply_markup
    )
    context.user_data['st'] = False
    context.user_data['sv'] = False

async def skin_toggle_st(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['st'] = not context.user_data.get('st', False)
    await update_skin_modifier_message(update, context)

async def skin_toggle_sv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['sv'] = not context.user_data.get('sv', False)
    await update_skin_modifier_message(update, context)

async def update_skin_modifier_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st = context.user_data.get('st', False)
    sv = context.user_data.get('sv', False)
    st_text = "✅" if st else "❌"
    sv_text = "✅" if sv else "❌"
    keyboard = [
        [InlineKeyboardButton(f"StatTrak: {st_text}", callback_data='skin_toggle_st')],
        [InlineKeyboardButton(f"Сувенирное: {sv_text}", callback_data='skin_toggle_sv')],
        [InlineKeyboardButton("✅ Готово", callback_data='skin_modifier_done')],
        [InlineKeyboardButton("❌ Назад", callback_data='skin_choose_quality')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_reply_markup(reply_markup)

async def skin_modifier_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    base = context.user_data['base_modifier']
    st = 4 if context.user_data.get('st') else 0
    sv = 2 if context.user_data.get('sv') else 0
    modifier = base + st + sv
    context.user_data['final_modifier'] = modifier
    # Запрашиваем количество
    keyboard = [
        [InlineKeyboardButton("1", callback_data='skin_qty_1'),
         InlineKeyboardButton("2", callback_data='skin_qty_2'),
         InlineKeyboardButton("3", callback_data='skin_qty_3')],
        [InlineKeyboardButton("5", callback_data='skin_qty_5'),
         InlineKeyboardButton("10", callback_data='skin_qty_10')],
        [InlineKeyboardButton("✅ Выдать", callback_data='skin_execute')],
        [InlineKeyboardButton("❌ Назад", callback_data='skin_choose_quality')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"Выбран модификатор: {MODIFIERS_MAP[modifier]}\nВведите количество (или нажмите кнопку):",
        reply_markup=reply_markup
    )
    context.user_data['skin_qty'] = 1  # по умолчанию

async def skin_qty_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split('_')[2])
    context.user_data['skin_qty'] = qty
    # Обновляем сообщение
    keyboard = [
        [InlineKeyboardButton("1", callback_data='skin_qty_1'),
         InlineKeyboardButton("2", callback_data='skin_qty_2'),
         InlineKeyboardButton("3", callback_data='skin_qty_3')],
        [InlineKeyboardButton("5", callback_data='skin_qty_5'),
         InlineKeyboardButton("10", callback_data='skin_qty_10')],
        [InlineKeyboardButton(f"✅ Выдать ({qty} шт.)", callback_data='skin_execute')],
        [InlineKeyboardButton("❌ Назад", callback_data='skin_choose_quality')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_reply_markup(reply_markup)

async def skin_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target_id = context.user_data['give_skin_target']
    code = context.user_data['selected_skin_code']
    modifier = context.user_data['final_modifier']
    qty = context.user_data.get('skin_qty', 1)
    skin_name = context.user_data['selected_skin_name']
    inv = load_json(INVENTORY_FILE, {})
    if target_id not in inv:
        inv[target_id] = {"skins": []}
    for _ in range(qty):
        inv[target_id]["skins"].append({
            "code": code,
            "modifier": modifier,
            "name": skin_name
        })
    save_json(INVENTORY_FILE, inv)
    await query.edit_message_text(f"✅ Выдано {qty} x {skin_name} (мод: {MODIFIERS_MAP[modifier]}) игроку {target_id}")
    # Очищаем user_data
    keys = ['give_skin_target','selected_skin_code','selected_skin_name','base_modifier','st','sv','final_modifier','skin_qty']
    for k in keys:
        context.user_data.pop(k, None)
