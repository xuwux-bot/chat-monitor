#!/usr/bin/env python3
import requests
import csv
import os
import time
import threading
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any

# ========== НАСТРОЙКИ ==========
URL_FIND = "https://api.efezgames.com/v1/social/findUser"
URL_CHECK = "https://api.efezgames.com/v1/equipment/getEQ"

# Диапазон генерации
ID_RANGE_START = 1
ID_RANGE_END = 6000000

# Потоки для producer (поиск ID)
PRODUCER_THREADS = 10

# Потоки для consumer (обработка стран)
CONSUMER_THREADS = 50
ALLOWED_COUNTRIES = {"RU", "DE", "PL", "US", "UA"}

# Глобальные переменные модуля (инициализируются при запуске)
_output_dir = "parsing"
_producer_running = False
_consumer_running = False
_producer_checked = 0
_producer_found_premium = 0
_consumer_processed = 0
_stats_lock = threading.Lock()
_stop_event = None

def _get_path(filename: str) -> str:
    """Возвращает полный путь к файлу в папке output_dir."""
    return os.path.join(_output_dir, filename)

def _load_processed_ids():
    """Загружает множество уже обработанных ID из processed.txt"""
    path = _get_path('processed.txt')
    if not os.path.exists(path):
        return set()
    with open(path, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())

def _shorten_id(player_id):
    if len(player_id) > 7:
        return f"{player_id[:7]}..."
    return player_id

def _producer_worker(stop_event):
    global _producer_checked, _producer_found_premium
    session = requests.Session()
    unique_ids = set()

    while not stop_event.is_set():
        random_num = random.randint(ID_RANGE_START, ID_RANGE_END)
        req_start = time.time()

        try:
            # ШАГ 1: поиск пользователя
            resp_find = session.get(URL_FIND, params={"ID": str(random_num)}, timeout=10)

            if resp_find.status_code == 200:
                data_find = resp_find.json()
                player_id = data_find.get("_id")

                if not player_id:
                    continue

                if player_id in unique_ids:
                    continue
                unique_ids.add(player_id)

                # Запись ВСЕХ найденных ID в общий файл
                with open(_get_path('user_id.txt'), "a", encoding="utf-8") as f:
                    f.write(player_id + "\n")

                # ШАГ 2: проверка премиум-статуса
                resp_check = session.get(URL_CHECK, params={"playerID": player_id}, timeout=10)
                duration = round(time.time() - req_start, 3)

                if resp_check.status_code == 200:
                    data_check = resp_check.json()
                    is_premium = data_check.get('premium') is True

                    if is_premium:
                        with open(_get_path('premiumaccount.csv'), 'a', encoding='utf-8', newline='') as f:
                            csv.writer(f).writerow([player_id])
                        with _stats_lock:
                            _producer_found_premium += 1
                        print('\a', end='')
                    else:
                        with open(_get_path('no_prem_account.csv'), 'a', encoding='utf-8', newline='') as f:
                            csv.writer(f).writerow([player_id])

                    with _stats_lock:
                        _producer_checked += 1
                        current_time = datetime.now().strftime("%H:%M:%S")
                        status = "PREMIUM ✅" if is_premium else "Обычный ❌"
                        print(f"[PRODUCER][{current_time}] #{_producer_checked} {_shorten_id(player_id)} -> {status} ({duration}s)")

            else:
                time.sleep(1)

        except Exception:
            time.sleep(0.5)

def _consumer_check_id(p_id, stop_event):
    """Проверяет один ID: запрос getEQ и сохранение по стране"""
    req_start = time.time()
    try:
        response = requests.get(URL_CHECK, params={"playerID": p_id}, timeout=15)
        duration = time.time() - req_start
        if response.status_code == 200:
            data = response.json()
            country = data.get("country")
            if country in ALLOWED_COUNTRIES:
                filename = f"{country}account.csv"
                with open(_get_path(filename), 'a', newline='', encoding='utf-8') as f:
                    csv.writer(f).writerow([p_id])
            with open(_get_path('processed.txt'), 'a', encoding='utf-8') as f:
                f.write(f"{p_id}\n")
            with _stats_lock:
                _consumer_processed += 1
            status_icon = "✅"
            label = country if country else "???"
        else:
            status_icon = "❌"
            label = f"HTTP:{response.status_code}"
            duration = time.time() - req_start
    except Exception:
        status_icon = "❌"
        label = "???"
        duration = time.time() - req_start

    with _stats_lock:
        current_time = datetime.now().strftime("%H:%M:%S")
        print(f"[CONSUMER][{current_time}] {_shorten_id(p_id)} -> [{label}] {status_icon} ({duration:.2f}s)")

def _consumer_worker(stop_event):
    """Поток consumer: читает новые строки из user_id.txt и отправляет их в пул на обработку"""
    file_position = 0
    processed = _load_processed_ids()

    while not os.path.exists(_get_path('user_id.txt')) and not stop_event.is_set():
        time.sleep(2)
    if stop_event.is_set():
        return

    with open(_get_path('user_id.txt'), 'r', encoding='utf-8') as f:
        f.seek(0, os.SEEK_END)
        file_position = f.tell()

    with ThreadPoolExecutor(max_workers=CONSUMER_THREADS) as executor:
        while not stop_event.is_set():
            try:
                with open(_get_path('user_id.txt'), 'r', encoding='utf-8') as f:
                    f.seek(file_position)
                    new_lines = f.readlines()
                    if new_lines:
                        file_position = f.tell()
                        futures = []
                        for line in new_lines:
                            p_id = line.strip()
                            if not p_id or p_id in processed:
                                continue
                            futures.append(executor.submit(_consumer_check_id, p_id, stop_event))
                    else:
                        time.sleep(1)
            except Exception as e:
                print(f"[CONSUMER] Ошибка: {e}")
                time.sleep(2)

def run_parser(output_dir: str, stop_event: threading.Event):
    """Основная функция парсера, запускается в отдельном потоке."""
    global _output_dir, _producer_running, _consumer_running, _stop_event
    _output_dir = output_dir
    os.makedirs(_output_dir, exist_ok=True)
    _stop_event = stop_event

    _producer_running = True
    _consumer_running = True

    producer_threads = []
    for _ in range(PRODUCER_THREADS):
        t = threading.Thread(target=_producer_worker, args=(stop_event,), daemon=True)
        t.start()
        producer_threads.append(t)

    consumer_thread = threading.Thread(target=_consumer_worker, args=(stop_event,), daemon=True)
    consumer_thread.start()

    stop_event.wait()

    _producer_running = False
    _consumer_running = False
    time.sleep(2)

def get_stats() -> Dict[str, Any]:
    """Возвращает текущую статистику парсера."""
    with _stats_lock:
        return {
            "producer_checked": _producer_checked,
            "producer_found_premium": _producer_found_premium,
            "consumer_processed": _consumer_processed,
            "running": _producer_running or _consumer_running
        }

def is_running() -> bool:
    return _producer_running or _consumer_running
