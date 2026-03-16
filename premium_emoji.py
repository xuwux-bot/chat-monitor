import html
import inspect
from telegram import Bot, Message, CallbackQuery, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton

EMOJI_MAP = {
    "💰": "5375296873982604963","📦": "5854908544712707500","⚠️": "5420323339723881652","⚠": "5420323339723881652",
    "❌": "5210952531676504517","✅": "5206607081334906820","🔄": "5386367538735104399","👤": "5190533149049757592",
    "🛒": "5451882707875276247","🎁": "5199749070830197566","🧾": "5334882760735598374","⛔": "5260293700088511294",
    "👥": "5372926953978341366","💎": "5427168083074628963","🕓": "5382194935057372936","🍪": "5370783443175086955",
    "⚡": "5456140674028019486","❗": "5274099962655816924","🧟": "5190533149049757592","🧟‍♀️": "5190533149049757592",
    "✉️": "5253742260054409879","✉": "5253742260054409879","♻": "5361741454685256344","📁": "5282843764451195532",
    "📤": "5433614747381538714","🔍": "5188217332748527444","🪙": "5379600444098093058","📊": "5231200819986047254",
    "🔫": "5454177848203951217","⚙": "5341715473882955310","⚙️": "5341715473882955310","➡": "5416117059207572332",
    "➕": "5226945370684140473","➖": "5229113891081956317","👑": "5217822164362739968","🔔": "5458603043203327669",
    "🔴": "5411225014148014586","🔸": "5411225014148014586","🔹": "5411225014148014586","🚀": "5445284980978621387",
    "🌐": "5447410659077661506","🎉": "5436040291507247633","💡": "5422439311196834318","📅": "5413879192267805083",
    "📜": "5282843764451195532","📝": "5258500400918587241","📡": "5372846474881146350","🔗": "5305265301917549162",
    "🛑": "5240241223632954241","🌹": "5440911110838425969","🍓": "5469963154391833732","💤": "5451959871257713464",
    "♥": "5449505950283078474","🗨": "5443038326535759644","📥": "5433811242135331842","🔢": "5472404950673791399",
    "📋": "5433982607035474385","🎫": "5418010521309815154",
}
EMOJIS_SORTED = sorted(EMOJI_MAP.keys(), key=len, reverse=True)

def replace_text_with_premium(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text
    escaped = html.escape(text)
    for emoji in EMOJIS_SORTED:
        escaped = escaped.replace(emoji, f'<tg-emoji emoji-id="{EMOJI_MAP[emoji]}">{emoji}</tg-emoji>')
    return escaped

def _split_button_text(text: str):
    if not isinstance(text, str):
        return None, text
    stripped = text.lstrip()
    leading_spaces = text[:len(text)-len(stripped)]
    for emoji in EMOJIS_SORTED:
        if stripped.startswith(emoji):
            rest = stripped[len(emoji):].lstrip()
            return EMOJI_MAP[emoji], leading_spaces + rest
    return None, text

def _clone_button(btn, new_text, icon_id):
    cls = btn.__class__
    sig = inspect.signature(cls.__init__)
    kwargs = {}
    for name in sig.parameters:
        if name == "self":
            continue
        if name == "text":
            kwargs[name] = new_text
        elif name == "icon_custom_emoji_id" and icon_id:
            kwargs[name] = icon_id
        elif hasattr(btn, name):
            val = getattr(btn, name)
            if val is not None:
                kwargs[name] = val
    return cls(**kwargs)

def transform_reply_markup(reply_markup):
    if reply_markup is None:
        return None
    if isinstance(reply_markup, InlineKeyboardMarkup):
        rows = []
        for row in reply_markup.inline_keyboard:
            new_row = []
            for btn in row:
                icon_id, new_text = _split_button_text(btn.text)
                new_row.append(_clone_button(btn, new_text, icon_id))
            rows.append(new_row)
        return InlineKeyboardMarkup(rows)
    if isinstance(reply_markup, ReplyKeyboardMarkup):
        rows = []
        for row in reply_markup.keyboard:
            new_row = []
            for btn in row:
                if isinstance(btn, str):
                    icon_id, new_text = _split_button_text(btn)
                    if icon_id:
                        new_row.append(KeyboardButton(text=new_text, icon_custom_emoji_id=icon_id))
                    else:
                        new_row.append(btn)
                else:
                    icon_id, new_text = _split_button_text(btn.text)
                    new_row.append(_clone_button(btn, new_text, icon_id))
            rows.append(new_row)
        return ReplyKeyboardMarkup(
            keyboard=rows,
            resize_keyboard=reply_markup.resize_keyboard,
            one_time_keyboard=reply_markup.one_time_keyboard,
            selective=reply_markup.selective,
            input_field_placeholder=reply_markup.input_field_placeholder,
            is_persistent=reply_markup.is_persistent,
        )
    return reply_markup

def install_premium_emoji_patches(app=None):
    if getattr(Bot, "_premium_emoji_patch_installed", False):
        return

    orig_reply_text = Message.reply_text
    async def patched_reply_text(self, text, *args, **kwargs):
        if isinstance(text, str):
            kwargs.setdefault("parse_mode", "HTML")
            text = replace_text_with_premium(text)
        if "reply_markup" in kwargs:
            kwargs["reply_markup"] = transform_reply_markup(kwargs.get("reply_markup"))
        return await orig_reply_text(self, text, *args, **kwargs)

    orig_send_message = Bot.send_message
    async def patched_send_message(self, chat_id, text, *args, **kwargs):
        if isinstance(text, str):
            kwargs.setdefault("parse_mode", "HTML")
            text = replace_text_with_premium(text)
        if "reply_markup" in kwargs:
            kwargs["reply_markup"] = transform_reply_markup(kwargs.get("reply_markup"))
        return await orig_send_message(self, chat_id, text, *args, **kwargs)

    orig_edit_message_text = Bot.edit_message_text
    async def patched_edit_message_text(self, text, *args, **kwargs):
        if isinstance(text, str):
            kwargs.setdefault("parse_mode", "HTML")
            text = replace_text_with_premium(text)
        if "reply_markup" in kwargs:
            kwargs["reply_markup"] = transform_reply_markup(kwargs.get("reply_markup"))
        return await orig_edit_message_text(self, text, *args, **kwargs)

    orig_cq_edit_message_text = CallbackQuery.edit_message_text
    async def patched_cq_edit_message_text(self, text, *args, **kwargs):
        if isinstance(text, str):
            kwargs.setdefault("parse_mode", "HTML")
            text = replace_text_with_premium(text)
        if "reply_markup" in kwargs:
            kwargs["reply_markup"] = transform_reply_markup(kwargs.get("reply_markup"))
        return await orig_cq_edit_message_text(self, text, *args, **kwargs)

    Message.reply_text = patched_reply_text
    Bot.send_message = patched_send_message
    Bot.edit_message_text = patched_edit_message_text
    CallbackQuery.edit_message_text = patched_cq_edit_message_text
    Bot._premium_emoji_patch_installed = True
