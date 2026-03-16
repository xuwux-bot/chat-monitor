#!/usr/bin/env python3
import asyncio
import json
import os
import time
import re
from typing import Dict, Set, Optional, Tuple, List
from datetime import datetime, timedelta, timezone

import requests
from telegram import Bot, Update
from telegram.ext import ContextTypes

# ================= НАСТРОЙКИ =================
API_BASE_URL = "https://api.efezgames.com/v1"
FIREBASE_URL = "https://api-project-7952672729.firebaseio.com"
CHECK_INTERVAL = 1  # секунд
LOG_FILE = "logs/TRADElogs.json"
CREATE_TOKEN = "Zluavtkju9WkqLYzGVKg"  # токен для создания трейдов
DEFAULT_SENDER_ID = "EfezAdmin1"       # аккаунт-отправитель для выводов
SKINS_DIR = "skins"
SKINS_LOG_FILE = os.path.join(SKINS_DIR, "skin.json")
SKINS_MAP_FILE = "айди скинов.txt"
WHITETRADE_FILE = "data/whitetrade.json"

# Чаты для уведомлений о выводах
WITHDRAW_NOTIFY_CHAT = -1003534308756
WITHDRAW_NOTIFY_THREAD = 10579
WITHDRAW_EXPIRE_HOURS = 48
# ==============================================

# Глобальные переменные модуля
_blocker_task: Optional[asyncio.Task] = None
_blocker_running = False
_blocked_count = 0
_notify_bot: Optional[Bot] = None
_notify_chat_id: Optional[int] = None
_notify_thread_id: Optional[int] = None

# Множество уже обработанных (заблокированных) ID трейдов (загружается из лога)
_seen_ids: Set[str] = set()
# Белый список трейдов (свои, не блокировать)
_whitelist: Dict[str, dict] = {}        # trade_id -> данные
_whitelist_messages: Dict[str, str] = {} # сообщение -> trade_id
# Словарь для связи message_id уведомления с trade_id (для разблокировки)
_trade_id_by_msg_id: Dict[int, str] = {}
# Словарь с полными данными трейда по его ID (для разблокировки)
_all_trades_data: Dict[str, dict] = {}

# Маппинг кодов скинов -> названия
_skin_map: Dict[str, str] = {}

def _load_skin_map() -> Dict[str, str]:
    """Загружает соответствие кодов скинов и названий из файла."""
    if not os.path.exists(SKINS_MAP_FILE):
        print(f"Предупреждение: файл {SKINS_MAP_FILE} не найден, названия скинов не будут загружены.")
        return {}
    skin_map = {}
    try:
        with open(SKINS_MAP_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or '|' not in line:
                    continue
                parts = line.split('|', 1)
                code = parts[0].strip()
                name = parts[1].strip() if len(parts) > 1 else code
                code = code[:2]  # обычно двухсимвольный
                skin_map[code] = name
    except Exception as e:
        print(f"Ошибка загрузки файла скинов: {e}")
    return skin_map

def _parse_skin_codes(skins_str: str) -> List[str]:
    if not skins_str:
        return []
    if ';' in skins_str:
        parts = skins_str.split(';')
    elif ',' in skins_str:
        parts = skins_str.split(',')
    else:
        parts = [skins_str]
    codes = []
    for p in parts:
        p = p.strip()
        if len(p) >= 2:
            codes.append(p[:2])
    return codes

def _get_skin_name(code: str) -> str:
    return _skin_map.get(code, code)

def _save_skins_to_log(trade_id: str, trade_data: dict):
    os.makedirs(SKINS_DIR, exist_ok=True)
    now_msk = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=3)))
    timestamp = now_msk.strftime("%Y-%m-%d %H:%M:%S")

    skins_offered = trade_data.get('skinsOffered', '')
    skins_requested = trade_data.get('skinsRequested', '')
    offered_codes = _parse_skin_codes(skins_offered)
    requested_codes = _parse_skin_codes(skins_requested)

    entry = {
        "trade_id": trade_id,
        "timestamp": timestamp,
        "skins_offered": [{"code": c, "name": _get_skin_name(c)} for c in offered_codes],
        "skins_requested": [{"code": c, "name": _get_skin_name(c)} for c in requested_codes]
    }

    if os.path.exists(SKINS_LOG_FILE):
        try:
            with open(SKINS_LOG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, list):
                    data = []
        except:
            data = []
    else:
        data = []
    data.append(entry)
    try:
        with open(SKINS_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Ошибка сохранения лога скинов: {e}")

def _load_blocked_ids() -> Set[str]:
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return set(data.keys())
        except:
            return set()
    return set()

def _save_trade_to_log(trade_id: str, trade_data: dict):
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = {}
    else:
        data = {}
    data[trade_id] = trade_data
    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Ошибка сохранения лога трейдов: {e}")

def load_whitelist():
    global _whitelist, _whitelist_messages
    if os.path.exists(WHITETRADE_FILE):
        try:
            with open(WHITETRADE_FILE, 'r', encoding='utf-8') as f:
                _whitelist = json.load(f)
                for tid, data in _whitelist.items():
                    msg = data.get('message')
                    if msg:
                        _whitelist_messages[msg] = tid
        except Exception as e:
            print(f"Ошибка загрузки whitelist: {e}")
            _whitelist = {}
            _whitelist_messages = {}
    else:
        _whitelist = {}
        _whitelist_messages = {}

def save_whitelist():
    try:
        with open(WHITETRADE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_whitelist, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Ошибка сохранения whitelist: {e}")

def add_to_whitelist(trade_id: str, message: str, receiver_game_id: str, skins_offered: str, notification_msg_id: int = None):
    _whitelist[trade_id] = {
        "message": message,
        "receiver_game_id": receiver_game_id,
        "skins_offered": skins_offered,
        "timestamp": datetime.now().isoformat(),
        "notification_msg_id": notification_msg_id,
        "completed": False
    }
    _whitelist_messages[message] = trade_id
    save_whitelist()

async def _notify_trade_accepted(trade_id: str, data: dict):
    if not _notify_bot:
        return
    msg_id = data.get('notification_msg_id')
    if not msg_id:
        return
    try:
        await _notify_bot.send_message(
            chat_id=WITHDRAW_NOTIFY_CHAT,
            text=(
                f"<tg-emoji emoji-id=\"5274099962655816924\">❗</tg-emoji> <b>Трейд был принят!</b>\n"
                f"- Время создания: {data['timestamp']}"
            ),
            message_thread_id=WITHDRAW_NOTIFY_THREAD,
            reply_to_message_id=msg_id,
            parse_mode='HTML'
        )
    except Exception as e:
        print(f"Ошибка уведомления о принятии трейда: {e}")

async def _recreate_trade(trade_id: str, data: dict):
    url = f"{API_BASE_URL}/trades/createOffer"
    params = {
        "token": CREATE_TOKEN,
        "playerID": data['receiver_game_id'],          # ID получателя (игрока)
        "receiverID": "",                               # не используется
        "senderNick": "EfezBot",                        # отправитель (бот)
        "senderFrame": "",
        "senderAvatar": "",
        "receiverNick": "",
        "receiverFrame": "",
        "receiverAvatar": "",
        "skinsOffered": data['skins_offered'],
        "skinsRequested": "",
        "message": data['message'],
        "pricesHash": "fbd9aec4384456124c0765581a4ba099",
        "receiverOneSignal": "",
        "senderOneSignal": "",
        "senderVersion": "2.40.0",
        "receiverVersion": "2.40.0"
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            resp_json = resp.json()
            new_trade_id = resp_json.get('offerID') or resp_json.get('_id')
            if new_trade_id:
                # Отправляем уведомление о пересоздании
                await _notify_bot.send_message(
                    chat_id=WITHDRAW_NOTIFY_CHAT,
                    text=f"🔄 Трейд пересоздан (не был принят за {WITHDRAW_EXPIRE_HOURS} часов). Новый ID: {new_trade_id}",
                    message_thread_id=WITHDRAW_NOTIFY_THREAD,
                    reply_to_message_id=data.get('notification_msg_id')
                )
                # Добавляем новый трейд в whitelist
                add_to_whitelist(new_trade_id, data['message'], data['receiver_game_id'], data['skins_offered'], data.get('notification_msg_id'))
    except Exception as e:
        print(f"Ошибка пересоздания трейда: {e}")

async def _check_whitelist():
    now = datetime.now()
    expire_threshold = timedelta(hours=WITHDRAW_EXPIRE_HOURS)
    to_delete = []
    for trade_id, data in list(_whitelist.items()):
        if data.get('completed'):
            continue
        created = datetime.fromisoformat(data['timestamp'])
        age = now - created
        # Проверяем наличие трейда в Firebase
        url = f"{FIREBASE_URL}/Trades/{trade_id}.json"
        try:
            resp = requests.get(url, timeout=5)
            trade_exists = (resp.status_code == 200 and resp.json() is not None)
        except:
            trade_exists = True  # при ошибке временно считаем существующим

        if not trade_exists:
            # Трейд принят
            await _notify_trade_accepted(trade_id, data)
            data['completed'] = True
            to_delete.append(trade_id)
        elif age > expire_threshold:
            # Трейд висит слишком долго – пересоздаём
            await _recreate_trade(trade_id, data)
            data['completed'] = True
            to_delete.append(trade_id)

    if to_delete:
        for tid in to_delete:
            msg = _whitelist[tid].get('message')
            if msg and msg in _whitelist_messages:
                del _whitelist_messages[msg]
            del _whitelist[tid]
        save_whitelist()

async def _send_notification(trade_id: str, trade_data: dict):
    if not _notify_bot or not _notify_chat_id:
        return

    ts = trade_data.get('ts', 0)
    if ts:
        time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts / 1000))
    else:
        time_str = 'неизвестно'
    message = trade_data.get('message', '')
    sender_nick = trade_data.get('senderNick', 'неизвестно')
    receiver_nick = trade_data.get('receiverNick', 'неизвестно')
    skins_offered = trade_data.get('skinsOffered', '')
    skins_requested = trade_data.get('skinsRequested', '')
    sender_id = trade_data.get('senderID', 'неизвестно')
    receiver_id = trade_data.get('receiverID', 'неизвестно')

    text = (
        f"✅ Трейд: {trade_id} - заблокирован\n"
        f"• Время отправки трейда: {time_str}\n"
        f"• Сообщение трейда: {message}\n"
        f"• Ник отправителя: {sender_nick}\n"
        f"• Ник получателя: {receiver_nick}\n"
        f"Скины\n"
        f"• Отправляемые скины: {skins_offered}\n"
        f"• Получаемые скины: {skins_requested}\n"
        f"Айди\n"
        f"• Айди отправителя: {sender_id}\n"
        f"• Айди получателя: {receiver_id}\n"
        f"---\n"
        f"| Информация\n"
        f"Чтобы разблокировать трейд ответьте на это или другое сообщение словом \"разблокировать\""
    )

    try:
        sent_msg = await _notify_bot.send_message(
            chat_id=_notify_chat_id,
            text=text,
            message_thread_id=_notify_thread_id
        )
        _trade_id_by_msg_id[sent_msg.message_id] = trade_id
        _all_trades_data[trade_id] = trade_data
    except Exception as e:
        print(f"Ошибка отправки уведомления о трейде: {e}")

async def _blocker_worker():
    global _blocked_count, _seen_ids
    check_counter = 0

    while _blocker_running:
        try:
            url = f"{FIREBASE_URL}/Trades.json?orderBy=\"ts\"&limitToLast=20"
            response = requests.get(url, timeout=5)
            trades = response.json()
            if not trades:
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            for trade_id, trade_data in trades.items():
                if trade_id in _seen_ids:
                    continue
                if trade_id in _whitelist:
                    # свой трейд, не блокируем
                    _seen_ids.add(trade_id)
                    continue

                # Проверяем сообщение на совпадение с белым списком
                msg_text = trade_data.get('message', '')
                if msg_text in _whitelist_messages and _whitelist_messages[msg_text] != trade_id:
                    # Кто-то отправил трейд с таким же сообщением - блокируем (обычная логика)
                    pass

                sender_id = trade_data.get('senderID')
                if sender_id:
                    accept_url = f"{API_BASE_URL}/trades/consumeOffer?token=besttoken&playerID={sender_id}&offerID={trade_id}"
                    try:
                        accept_resp = requests.get(accept_url, timeout=3)
                        if accept_resp.status_code == 200:
                            _blocked_count += 1
                            print(f"Трейд {trade_id} успешно принят")
                        else:
                            print(f"Ошибка принятия трейда {trade_id}: {accept_resp.status_code}")
                    except Exception as e:
                        print(f"Исключение при принятии трейда {trade_id}: {e}")

                    _seen_ids.add(trade_id)
                    _save_trade_to_log(trade_id, trade_data)
                    _save_skins_to_log(trade_id, trade_data)
                    await _send_notification(trade_id, trade_data)

            # Раз в минуту проверяем белый список
            check_counter += 1
            if check_counter >= 60:
                await _check_whitelist()
                check_counter = 0

            await asyncio.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"Ошибка в блокировщике трейдов: {e}")
            await asyncio.sleep(5)

def start_blocker(bot: Bot, chat_id: int, thread_id: Optional[int], active_tasks: dict):
    global _blocker_task, _blocker_running, _notify_bot, _notify_chat_id, _notify_thread_id, _seen_ids, _skin_map
    if _blocker_running:
        return
    _skin_map = _load_skin_map()
    load_whitelist()
    _notify_bot = bot
    _notify_chat_id = chat_id
    _notify_thread_id = thread_id
    _seen_ids = _load_blocked_ids()
    _blocked_count = len(_seen_ids)
    _blocker_running = True
    _blocker_task = asyncio.create_task(_blocker_worker())
    active_tasks["TradeBlocker"] = _blocker_task

def stop_blocker() -> bool:
    global _blocker_task, _blocker_running
    if not _blocker_running or not _blocker_task:
        return False
    _blocker_running = False
    _blocker_task.cancel()
    return True

def blocker_is_running() -> bool:
    return _blocker_running

def get_blocker_stats() -> Dict:
    return {
        "blocked": _blocked_count,
        "running": _blocker_running
    }

def _send_create_offer(trade_data: dict) -> Tuple[bool, str, Optional[str]]:
    url = f"{API_BASE_URL}/trades/createOffer"
    params = {
        "token": CREATE_TOKEN,
        "playerID": trade_data.get('receiverID', ''),  # ID получателя (оригинальный)
        "receiverID": "",                               # не используется
        "senderNick": "EfezBot",                        # отправитель (бот)
        "senderFrame": trade_data.get('senderFrame', ''),
        "senderAvatar": trade_data.get('senderAvatar', ''),
        "receiverNick": trade_data.get('receiverNick', ''),
        "receiverFrame": trade_data.get('receiverFrame', ''),
        "receiverAvatar": trade_data.get('receiverAvatar', ''),
        "skinsOffered": trade_data.get('skinsOffered', ''),
        "skinsRequested": trade_data.get('skinsRequested', ''),
        "message": trade_data.get('message', ''),
        "pricesHash": trade_data.get('pricesHash', 'fbd9aec4384456124c0765581a4ba099'),
        "receiverOneSignal": trade_data.get('receiverOneSignal', ''),
        "senderOneSignal": trade_data.get('senderOneSignal', ''),
        "senderVersion": trade_data.get('senderVersion', '2.37.0'),
        "receiverVersion": trade_data.get('receiverVersion', '2.37.0')
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            resp_json = response.json()
            new_trade_id = resp_json.get('offerID') or resp_json.get('_id') or resp_json.get('id')
            if not new_trade_id:
                new_trade_id = None
            return True, response.text, new_trade_id
        else:
            return False, f"HTTP {response.status_code}\n{response.text}", None
    except Exception as e:
        return False, str(e), None

async def handle_unblock_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.message.reply_to_message:
        return False
    if update.message.reply_to_message.from_user.id != context.bot.id:
        return False

    replied_msg = update.message.reply_to_message
    msg_id = replied_msg.message_id

    if msg_id not in _trade_id_by_msg_id:
        return False

    text = update.message.text.strip().lower()
    if "разблокировать" not in text:
        return False

    trade_id = _trade_id_by_msg_id[msg_id]
    trade_data = _all_trades_data.get(trade_id)
    if not trade_data:
        await update.message.reply_text("❌ Данные трейда не найдены.")
        return True

    success, result_msg, new_trade_id = _send_create_offer(trade_data)
    if success:
        reply = f"✅ Трейд {trade_id} разблокирован (отправлен повторно)."
        if new_trade_id:
            reply += f"\nНовый ID трейда: {new_trade_id}"
            # добавляем новый трейд в белый список
            add_to_whitelist(new_trade_id, trade_data.get('message', ''), trade_data.get('receiverID', ''), trade_data.get('skinsOffered', ''))
        await update.message.reply_text(reply)
    else:
        await update.message.reply_text(f"❌ Ошибка при отправке трейда:\n{result_msg}")
    return True

__all__ = [
    'start_blocker',
    'stop_blocker',
    'get_blocker_stats',
    'blocker_is_running',
    'handle_unblock_reply',
    'add_to_whitelist'
  ]
