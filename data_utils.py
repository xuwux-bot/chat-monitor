# data_utils.py
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any

def load_json(filename: str, default=None):
    if default is None:
        default = {} if filename.endswith('players.json') else []
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(filename: str, data):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_player_by_nick(nick: str, players: dict) -> Optional[str]:
    """Возвращает telegram_id по игровому нику"""
    for tid, pdata in players.items():
        if pdata.get('game_nick') == nick:
            return tid
    return None
