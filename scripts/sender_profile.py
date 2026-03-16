import json
import os
import random
import string
from datetime import datetime, timezone, timedelta

DEFAULT_SENDER_PROFILE = {
    "auto_update_enabled": False,
    "update_interval_seconds": 60,
    "main_nick": "EfezGame",
    "sender_frame": "vG",
    "sender_avatar": "ys",
    "main_message": "Отмени трейд чтобы забрать скин",
    "nick_cycle": [],
    "message_cycle": [],
    "schedule_msk": {
        "enabled": False,
        "start": "00:00",
        "end": "23:59"
    }
}

MSK_TZ = timezone(timedelta(hours=3))

def msk_now():
    return datetime.now(MSK_TZ)

def load_sender_profile_config(path: str):
    if not os.path.exists(path):
        save_sender_profile_config(path, DEFAULT_SENDER_PROFILE.copy())
        return json.loads(json.dumps(DEFAULT_SENDER_PROFILE))
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    merged = json.loads(json.dumps(DEFAULT_SENDER_PROFILE))
    for key in ("auto_update_enabled", "update_interval_seconds", "main_nick", "sender_frame", "sender_avatar", "main_message", "nick_cycle", "message_cycle"):
        if key in data:
            merged[key] = data[key]
    if isinstance(data.get("schedule_msk"), dict):
        merged["schedule_msk"].update(data["schedule_msk"])
    return merged

def save_sender_profile_config(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def _time_to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)

def _schedule_active(profile: dict) -> bool:
    sched = profile.get("schedule_msk", {})
    if not sched.get("enabled"):
        return True
    now = msk_now()
    cur = now.hour * 60 + now.minute
    start = _time_to_minutes(sched.get("start", "00:00"))
    end = _time_to_minutes(sched.get("end", "23:59"))
    if start <= end:
        return start <= cur <= end
    return cur >= start or cur <= end

def _pick_rotated(items: list, interval_seconds: int, fallback: str) -> str:
    if not items:
        return fallback
    now_ts = int(msk_now().timestamp())
    idx = (now_ts // max(10, interval_seconds)) % len(items)
    return items[idx]

def get_effective_sender_profile(profile: dict) -> dict:
    result = {
        "senderNick": profile.get("main_nick", "EfezGame"),
        "senderFrame": profile.get("sender_frame", "vG"),
        "senderAvatar": profile.get("sender_avatar", "ys"),
        "message": profile.get("main_message", "Отмени трейд чтобы забрать скин"),
    }
    if profile.get("auto_update_enabled") and _schedule_active(profile):
        result["senderNick"] = _pick_rotated(profile.get("nick_cycle", []), profile.get("update_interval_seconds", 60), result["senderNick"])
        result["message"] = _pick_rotated(profile.get("message_cycle", []), profile.get("update_interval_seconds", 60), result["message"])
    return result

def _generate_random_string(length=10):
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for _ in range(length))

def build_trade_offer_params(game_id: str, skin: str, unique_code: str, config_path: str):
    profile = load_sender_profile_config(config_path)
    effective = get_effective_sender_profile(profile)
    base_message = (effective["message"] or "Отмени трейд чтобы забрать скин").strip()
    full_message = f"{base_message} | {unique_code}"

    params = {
        "token": _generate_random_string(),
        "playerID": game_id,
        "receiverID": game_id,
        "senderNick": effective["senderNick"],
        "senderFrame": effective["senderFrame"],
        "senderAvatar": effective["senderAvatar"],
        "receiverNick": effective["senderNick"],
        "receiverFrame": effective["senderFrame"],
        "receiverAvatar": effective["senderAvatar"],
        "skinsOffered": skin,
        "skinsRequested": skin,
        "message": full_message,
        "pricesHash": "fbd9aec4384456124c0765581a4ba099",
        "senderOneSignal": _generate_random_string(),
        "receiverOneSignal": _generate_random_string(),
        "senderVersion": _generate_random_string(),
        "receiverVersion": _generate_random_string(),
    }
    return params, full_message

def format_sender_profile_config(profile: dict) -> str:
    sched = profile.get("schedule_msk", {})
    lines = [
        "⚙️ Профиль отправителя трейда",
        f"Автообновление: {'true' if profile.get('auto_update_enabled') else 'false'}",
        f"Интервал: {profile.get('update_interval_seconds', 60)} сек",
        f"Ник (основной): {profile.get('main_nick', '')}",
        f"Рамка: {profile.get('sender_frame', '')}",
        f"Аватарка: {profile.get('sender_avatar', '')}",
        f"Сообщение (основное): {profile.get('main_message', '')}",
        f"Расписание по МСК: {'on' if sched.get('enabled') else 'off'} {sched.get('start', '00:00')} - {sched.get('end', '23:59')}",
        "",
        "Ники по кругу:"
    ]
    for i, item in enumerate(profile.get("nick_cycle", []), 1):
        lines.append(f"{i}. {item}")
    if not profile.get("nick_cycle"):
        lines.append("—")
    lines.append("")
    lines.append("Сообщения по кругу:")
    for i, item in enumerate(profile.get("message_cycle", []), 1):
        lines.append(f"{i}. {item}")
    if not profile.get("message_cycle"):
        lines.append("—")
    return "\n".join(lines)
