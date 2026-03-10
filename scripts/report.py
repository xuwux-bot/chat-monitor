#!/usr/bin/env python3
import asyncio
import time
from typing import Dict, Optional, List
import requests
from telegram import Update
from telegram.ext import ContextTypes

# ================= НАСТРОЙКИ =================
API_BASE_URL = "https://api.efezgames.com/v1"
MAX_WORKERS = 50
UPDATE_INTERVAL = 2  # сек для обновления статуса
# ==============================================

# Глобальные словари для отслеживания активных задач жалоб
report_tasks: Dict[str, asyncio.Task] = {}          # target_id -> asyncio.Task
report_stats: Dict[str, Dict] = {}                  # target_id -> {"total": int, "sent": int, "last_update": float}
report_status_messages: Dict[str, int] = {}          # target_id -> message_id для обновления (уже не используется, но оставим)
# Для хранения последнего статусного сообщения по чату
last_status_message: Dict[int, int] = {}             # chat_id -> message_id

def get_report_task_name(target_id: str) -> str:
    return f"Report {target_id}"

async def report_worker(target_id: str, reason: str, count: int, chat_id: int, bot, status_message_id: int):
    """Фоновая задача отправки жалоб."""
    try:
        url = f"{API_BASE_URL}/users/reportUser?reportedUser={target_id}&submitter={target_id}&reason={reason}"
        headers = {
            "User-Agent": "UnityPlayer/2021.3.45f1",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            "X-Unity-Version": "2021.3.45f1"
        }

        report_stats[target_id] = {"total": count, "sent": 0, "last_update": time.time()}
        sent = 0
        i = 0
        infinite = (count == 0)

        while infinite or i < count:
            try:
                response = requests.get(url, headers=headers, timeout=5)
                if response.status_code == 200:
                    sent += 1
                    report_stats[target_id]["sent"] = sent
                    report_stats[target_id]["last_update"] = time.time()
                # Небольшая задержка, чтобы не зафлудить
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"Ошибка отправки жалобы: {e}")
            i += 1
            # Каждые 2 секунды обновляем сообщение статуса (если нужно)
            if i % 20 == 0:
                try:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=status_message_id,
                        text=format_report_status(target_id)
                    )
                except:
                    pass

        # Завершение
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_message_id,
                text=format_report_status(target_id, finished=True)
            )
        except:
            pass

    except asyncio.CancelledError:
        # Задача отменена
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_message_id,
                text=f"🛑 Жалобы на игрока {target_id} остановлены.\nОтправлено: {report_stats.get(target_id, {}).get('sent', 0)}"
            )
        except:
            pass
        raise
    finally:
        if target_id in report_tasks:
            del report_tasks[target_id]
        if target_id in report_stats:
            del report_stats[target_id]

def format_report_status(target_id: str, finished: bool = False) -> str:
    stats = report_stats.get(target_id, {"sent": 0, "total": 0})
    if finished:
        return f"✅ Жалобы на игрока {target_id} завершены.\nОтправлено: {stats['sent']}"
    else:
        total_str = f"/{stats['total']}" if stats['total'] > 0 else ""
        return f"📊 **Жалобы на игрока {target_id}**\n• Отправлено: {stats['sent']}{total_str}"

async def handle_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE, active_tasks: dict):
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "Использование: /report <айди игрока> <причина> <количество>\n"
            "Причины: 0 – неуместный ник, 1 – неуместное сообщение, 2 – спам\n"
            "Количество: 0 – бесконечно (остановить через /stop Report <айди>)"
        )
        return

    target_id = args[0]
    reason = args[1]
    if reason not in ("0", "1", "2"):
        await update.message.reply_text("Неверная причина. Допустимо: 0, 1, 2")
        return

    try:
        count = int(args[2])
        if count < 0:
            raise ValueError
    except:
        await update.message.reply_text("Количество должно быть целым неотрицательным числом.")
        return

    task_name = get_report_task_name(target_id)
    if task_name in active_tasks and not active_tasks[task_name].done():
        await update.message.reply_text(f"⚠️ Жалобы на игрока {target_id} уже запущены.")
        return

    # Отправляем стартовое сообщение
    status_msg = await update.message.reply_text(f"🚀 Запуск жалоб на игрока {target_id}...")
    # Сохраняем ID сообщения для последующего обновления
    report_status_messages[target_id] = status_msg.message_id

    # Создаём задачу
    task = asyncio.create_task(
        report_worker(target_id, reason, count, update.effective_chat.id, context.bot, status_msg.message_id)
    )
    active_tasks[task_name] = task
    report_tasks[target_id] = task

async def handle_report_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not report_stats:
        # Если нет активных жалоб, просто сообщаем
        await update.message.reply_text("Нет активных жалоб.")
        return

    text = "📊 **Статистика активных жалоб:**\n"
    for target_id, stats in report_stats.items():
        total_str = f"/{stats['total']}" if stats['total'] > 0 else ""
        text += f"• {target_id}: {stats['sent']}{total_str}\n"

    # Проверяем, есть ли уже отправленное статусное сообщение в этом чате
    if chat_id in last_status_message:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=last_status_message[chat_id],
                text=text
            )
            return
        except:
            # Если не удалось отредактировать (например, сообщение удалено), удаляем запись и отправляем новое
            del last_status_message[chat_id]

    # Отправляем новое сообщение и запоминаем его ID
    msg = await update.message.reply_text(text)
    last_status_message[chat_id] = msg.message_id

def stop_report_task(target_id: str) -> bool:
    if target_id in report_tasks and not report_tasks[target_id].done():
        report_tasks[target_id].cancel()
        return True
    return False

def stop_all_reports() -> int:
    """Останавливает все активные жалобы, возвращает количество остановленных."""
    count = 0
    for target_id, task in list(report_tasks.items()):
        if not task.done():
            task.cancel()
            count += 1
    report_tasks.clear()
    report_stats.clear()
    return count

def get_report_stats() -> Dict:
    return report_stats
