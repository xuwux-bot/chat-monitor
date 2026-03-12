#!/usr/bin/env python3
import asyncio
import json
import os
import time
from typing import Dict, Set, Optional

import requests
from telegram import Bot
from telegram.error import RetryAfter

# ================= НАСТРОЙКИ =================
API_BASE_URL = "https://api.efezgames.com/v1"
FIREBASE_URL = "https://api-project-7952672729.firebaseio.com"
MAX_WORKERS = 50
CHECK_INTERVAL = 1  # секунд
LOG_FILE = "logs/TRADElogs.json"
# ==============================================

# Глобальные переменные модуля
_blocker_task: Optional[asyncio.Task] = None
_blocker_running = False
_blocked_trades: Set[str] = set()
_blocked_count = 0
_notify_bot: Optional[Bot] = None
_notify_chat_id: Optional[int] = None
_notify_thread_id: Optional[int] = None

def _load_blocked_ids() -> Set[str]:
    """Загружает уже заблокированные ID из лога."""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return set(data.keys())
        except:
            return set()
    return set()

def _save_trade_to_log(trade_id: str, trade_data: dict):
    """Сохраняет трейд в лог-файл."""
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

async def _send_notification(text: str):
    """Отправляет уведомление в Telegram-чат."""
    global _notify_bot, _notify_chat_id, _notify_thread_id
    if not _notify_bot or not _notify_chat_id:
        return
    try:
        await _notify_bot.send_message(
            chat_id=_notify_chat_id,
            text=text,
            message_thread_id=_notify_thread_id
        )
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
                                await _send_notification(f"✅ Трейд заблокирован: {trade_id}")
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
