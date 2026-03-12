#!/usr/bin/env python3
import asyncio
import json
import os
import time
from typing import Dict, Set, Optional, Tuple

import requests
from telegram import Bot, Update
from telegram.ext import ContextTypes

# ================= НАСТРОЙКИ =================
API_BASE_URL = "https://api.efezgames.com/v1"
FIREBASE_URL = "https://api-project-7952672729.firebaseio.com"
CHECK_INTERVAL = 1  # секунд
LOG_FILE = "logs/TRADElogs.json"
CREATE_TOKEN = "Zluavtkju9WkqLYzGVKg"  # токен для создания трейдов
# ==============================================

# Глобальные переменные модуля
_blocker_task: Optional[asyncio.Task] = None
_blocker_running = False
_blocked_trades: Set[str] = set()
_blocked_count = 0
_notify_bot: Optional[Bot] = None
_notify_chat_id: Optional[int] = None
_notify_thread_id: Optional[int] = None

# Хранилище данных трейдов для разблокировки
_trade_data_by_msg_id: Dict[int, str] = {}   # message_id -> trade_id
_all_trades_data: Dict[str, dict] = {}       # trade_id -> полные данные трейда

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

async def _send_notification(trade_id: str, trade_data: dict):
    """Отправляет уведомление о новом трейде в Telegram-чат."""
    if not _notify_bot or not _notify_chat_id:
        return

    # Формируем сообщение по шаблону
    ts = trade_data.get('ts', 0)
    time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts / 1000)) if ts else 'неизвестно'
    message = trade_data.get('message', '')
    sender_nick = trade_data.get('senderNick', 'неизвестно')
    receiver_nick = trade_data.get('receiverNick', 'неизвестно')
    skins_offered = trade_data.get('skinsOffered', '')
    skins_requested = trade_data.get('skinsRequested', '')
    sender_id = trade_data.get('senderID', 'неизвестно')
    receiver_id = trade_data.get('receiverID', 'неизвестно')

    text = (
        f"✅ Трейд: {trade_id} - заблокирован\n"
        f"•Время отправки трейда: {time_str}\n"
        f"•Сообщение трейда: {message}\n"
        f"•Ник отправителя: {sender_nick}\n"
        f"•Ник получателя: {receiver_nick}\n"
        f"Скины\n"
        f"•Отправляемые скины: {skins_offered}\n"
        f"•Получаемые скины: {skins_requested}\n"
        f"Айди\n"
        f"•Айди отправителя: {sender_id}\n"
        f"•Айди получателя: {receiver_id}\n"
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
        # Сохраняем связь message_id -> trade_id для последующей разблокировки
        _trade_data_by_msg_id[sent_msg.message_id] = trade_id
        _all_trades_data[trade_id] = trade_data
    except Exception as e:
        print(f"Ошибка отправки уведомления о трейде: {e}")

async def _blocker_worker():
    """Основная задача: мониторит новые трейды и принимает их."""
    global _blocked_trades, _blocked_count, _blocker_running
    seen_ids = _load_blocked_ids()
    _blocked_trades = seen_ids.copy()
    _blocked_count = len(seen_ids)

    while _blocker_running:
        try:
            url = f"{FIREBASE_URL}/Trades.json?orderBy=\"ts\"&limitToLast=20"
            response = requests.get(url, timeout=5)
            trades = response.json()
            if not trades:
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            for trade_id, trade_data in trades.items():
                if trade_id not in seen_ids:
                    sender_id = trade_data.get('senderID')
                    if sender_id:
                        # Принимаем обмен
                        accept_url = f"{API_BASE_URL}/trades/consumeOffer?token=besttoken&playerID={sender_id}&offerID={trade_id}"
                        try:
                            accept_resp = requests.get(accept_url, timeout=3)
                            if accept_resp.status_code == 200:
                                _blocked_count += 1
                                seen_ids.add(trade_id)
                                _blocked_trades.add(trade_id)
                                _save_trade_to_log(trade_id, trade_data)
                                # Отправляем уведомление
                                await _send_notification(trade_id, trade_data)
                            else:
                                print(f"Ошибка принятия трейда {trade_id}: {accept_resp.status_code}")
                        except Exception as e:
                            print(f"Исключение при принятии трейда {trade_id}: {e}")

            await asyncio.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"Ошибка в блокировщике трейдов: {e}")
            await asyncio.sleep(5)

def start_blocker(bot: Bot, chat_id: int, thread_id: Optional[int], active_tasks: dict):
    """Запускает фоновую задачу блокировки трейдов."""
    global _blocker_task, _blocker_running, _notify_bot, _notify_chat_id, _notify_thread_id
    if _blocker_running:
        return
    _notify_bot = bot
    _notify_chat_id = chat_id
    _notify_thread_id = thread_id
    _blocker_running = True
    _blocker_task = asyncio.create_task(_blocker_worker())
    active_tasks["TradeBlocker"] = _blocker_task

def stop_blocker() -> bool:
    """Останавливает блокировку трейдов."""
    global _blocker_task, _blocker_running
    if not _blocker_running or not _blocker_task:
        return False
    _blocker_running = False
    _blocker_task.cancel()
    return True

def blocker_is_running() -> bool:
    return _blocker_running

def get_blocker_stats() -> Dict:
    """Возвращает статистику: количество заблокированных, статус."""
    return {
        "blocked": _blocked_count,
        "running": _blocker_running
    }

# ============= ФУНКЦИЯ ДЛЯ РАЗБЛОКИРОВКИ ТРЕЙДА =============
async def handle_unblock_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Обрабатывает ответы на сообщения о трейдах.
    Если ответ содержит слово "разблокировать", отправляет такой же трейд.
    Возвращает True, если обработано.
    """
    if not update.message.reply_to_message:
        return False
    if update.message.reply_to_message.from_user.id != context.bot.id:
        return False

    replied_msg = update.message.reply_to_message
    msg_id = replied_msg.message_id

    # Проверяем, есть ли этот message_id в нашем хранилище
    if msg_id not in _trade_data_by_msg_id:
        return False

    # Проверяем текст ответа (можно просто наличие слова "разблокировать")
    text = update.message.text.strip().lower()
    if "разблокировать" not in text:
        return False

    trade_id = _trade_data_by_msg_id[msg_id]
    trade_data = _all_trades_data.get(trade_id)
    if not trade_data:
        await update.message.reply_text("❌ Данные трейда не найдены.")
        return True

    # Отправляем такой же трейд
    success, message = _send_create_offer(trade_data)
    if success:
        await update.message.reply_text(f"✅ Трейд {trade_id} разблокирован (отправлен повторно).")
    else:
        await update.message.reply_text(f"❌ Ошибка при отправке трейда:\n{message}")
    return True

def _send_create_offer(trade_data: dict) -> Tuple[bool, str]:
    """Отправляет запрос на создание трейда на основе данных исходного."""
    url = f"{API_BASE_URL}/trades/createOffer"

    # Извлекаем нужные поля с дефолтными значениями
    params = {
        "token": CREATE_TOKEN,
        "playerID": trade_data.get('senderID', ''),
        "receiverID": trade_data.get('receiverID', ''),
        "senderNick": trade_data.get('senderNick', ''),
        "senderFrame": trade_data.get('senderFrame', ''),
        "senderAvatar": trade_data.get('senderAvatar', ''),
        "receiverNick": trade_data.get('receiverNick', ''),
        "receiverFrame": trade_data.get('receiverFrame', ''),
        "receiverAvatar": trade_data.get('receiverAvatar', ''),
        "skinsOffered": trade_data.get('skinsOffered', ''),
        "skinsRequested": trade_data.get('skinsRequested', ''),
        "message": trade_data.get('message', ''),
        "pricesHash": trade_data.get('pricesHash', 'fbd9aec4384456124c0765581a4ba099'),  # запасной
        "receiverOneSignal": trade_data.get('receiverOneSignal', ''),
        "senderOneSignal": trade_data.get('senderOneSignal', ''),
        "senderVersion": trade_data.get('senderVersion', '2.40.0'),
        "receiverVersion": trade_data.get('receiverVersion', '2.40.0')
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return True, response.text
        else:
            return False, f"HTTP {response.status_code}\n{response.text}"
    except Exception as e:
        return False, str(e)

# Экспортируем для использования в bot.py
__all__ = [
    'start_blocker',
    'stop_blocker',
    'get_blocker_stats',
    'blocker_is_running',
    'handle_unblock_reply'
]
