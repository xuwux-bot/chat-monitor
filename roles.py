# roles.py
from datetime import datetime, timedelta
from typing import Optional
from data_utils import load_json, save_json, PLAYERS_FILE

def parse_time(expiry_str: str) -> Optional[datetime]:
    """Парсит строку вида 4мес, 4д, 4ч, 4м"""
    if not expiry_str:
        return None
    num = int(expiry_str[:-1])
    unit = expiry_str[-1]
    if unit == 'м':
        if expiry_str.endswith('мес'):
            return datetime.now() + timedelta(days=30*num)
        else:
            return datetime.now() + timedelta(minutes=num)
    elif unit == 'д':
        return datetime.now() + timedelta(days=num)
    elif unit == 'ч':
        return datetime.now() + timedelta(hours=num)
    return None

def add_admin(tg_id: str, expiry_str: Optional[str] = None):
    players = load_json(PLAYERS_FILE, {})
    if tg_id not in players:
        return False
    expiry = parse_time(expiry_str) if expiry_str else None
    players[tg_id]["role"] = "admin"
    players[tg_id]["admin_expires"] = expiry.isoformat() if expiry else None
    save_json(PLAYERS_FILE, players)
    return True

def remove_admin(tg_id: str):
    players = load_json(PLAYERS_FILE, {})
    if tg_id not in players:
        return False
    players[tg_id]["role"] = "user"
    players[tg_id]["admin_expires"] = None
    save_json(PLAYERS_FILE, players)
    return True

def check_admin_expiry():
    """Проверяет всех админов и снимает роль при истечении срока. Вызывать при старте и периодически."""
    players = load_json(PLAYERS_FILE, {})
    changed = False
    now = datetime.now()
    for tid, pdata in players.items():
        if pdata.get("role") == "admin" and pdata.get("admin_expires"):
            try:
                expiry = datetime.fromisoformat(pdata["admin_expires"])
                if now > expiry:
                    pdata["role"] = "user"
                    pdata["admin_expires"] = None
                    changed = True
            except:
                pass
    if changed:
        save_json(PLAYERS_FILE, players)
