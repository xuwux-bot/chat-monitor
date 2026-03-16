#!/usr/bin/env python3
import requests
from typing import Tuple

API_BASE_URL = "https://api.efezgames.com/v1"

def apply_max_stats(player_id: str) -> Tuple[bool, str]:
    """
    Отправляет POST-запрос для применения максимальных характеристик (монеты, опыт, кейсы).
    Возвращает (успех, сообщение).
    """
    url = f"{API_BASE_URL}/equipment/sendEQ"
    # Параметры скопированы из предоставленного скрипта
    params = {
        "playerID": player_id,
        "description": "",
        "data": "999991;2999992;39999;499999;99995;699999;999997;9999998;99999;999999",
        "stats": "1:1,2:1,3:1,4:07,5:66,6:281.21,7:346.50,8:0,9:1342,11:518,13:1074,15:247.60,16:320.70,17:2.00,18:1100,19:1,20:1,23:0,24:52,25:2457598,26:314,27:22,28:92,29:1.164,30:108,31:7348748,32:1,33:18,34:54,35:8,36:0,37:0,38:0,39:0,40:0,41:0,42:0"
    }
    try:
        response = requests.post(url, data=params, timeout=15)
        if response.status_code == 200:
            return True, f"Статус: {response.status_code}\nОтвет: {response.text}"
        else:
            return False, f"Ошибка HTTP {response.status_code}\n{response.text}"
    except Exception as e:
        return False, str(e)
