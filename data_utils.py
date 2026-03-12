# data_utils.py
import json
import os
from typing import Optional, Dict, Any

# Импортируем пути к файлам из конфигурации
from config import PLAYERS_FILE, INVENTORY_FILE

def load_json(filename: str, default=None):
    """
    Загружает JSON из файла. Если файл не существует или повреждён,
    возвращает default (по умолчанию пустой словарь или список).
    """
    if default is None:
        # Если имя файла содержит 'players', по умолчанию словарь, иначе список
        if 'players' in filename:
            default = {}
        else:
            default = []
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return default
    return default

def save_json(filename: str, data):
    """Сохраняет данные в JSON-файл, создавая папки при необходимости."""
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_player_by_nick(nick: str, players: dict) -> Optional[str]:
    """
    Ищет Telegram ID игрока по его игровому нику (game_nick).
    Возвращает строковый ID или None.
    """
    for tid, pdata in players.items():
        if pdata.get('game_nick') == nick:
            return tid
    return None

def get_player_by_telegram_id(tg_id: str, players: dict) -> Optional[dict]:
    """Возвращает данные игрока по Telegram ID или None."""
    return players.get(tg_id)

def update_player_stats(tg_id: str, **kwargs):
    """
    Обновляет указанные поля в данных игрока и сохраняет файл.
    Пример: update_player_stats('12345', coins=100, commands_count=5)
    """
    players = load_json(PLAYERS_FILE, {})
    if tg_id in players:
        players[tg_id].update(kwargs)
        save_json(PLAYERS_FILE, players)

def add_skin_to_inventory(tg_id: str, skin_data: dict):
    """Добавляет скин в инвентарь игрока."""
    inv = load_json(INVENTORY_FILE, {})
    if tg_id not in inv:
        inv[tg_id] = {"skins": [], "cases": []}
    inv[tg_id]["skins"].append(skin_data)
    save_json(INVENTORY_FILE, inv)

def get_inventory(tg_id: str) -> dict:
    """Возвращает инвентарь игрока (пустой, если нет)."""
    inv = load_json(INVENTORY_FILE, {})
    return inv.get(tg_id, {"skins": [], "cases": []})
