import json
import os
from bot.config import DATA_FILE, DEFAULT_FONT

user_settings = {}

def load_settings():
    global user_settings
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            user_settings = json.load(f)

def save_settings():
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(user_settings, f)

def get_user_settings(user_id: int):
    uid = str(user_id)
    
    # Миграция старых данных: если у юзера была сохранена просто строка, превращаем в словарь
    if uid in user_settings and isinstance(user_settings[uid], str):
        old_font = user_settings[uid]
        user_settings[uid] = {
            "font": old_font,
            "color": "black",
            "vertical": False,
            "extra_info": True
        }
        save_settings()

    # Если юзера еще нет в базе
    if uid not in user_settings:
        user_settings[uid] = {
            "font": DEFAULT_FONT,
            "color": "black",
            "vertical": False,
            "extra_info": True
        }
        save_settings()
        
    return user_settings[uid]

def update_user_setting(user_id: int, key: str, value):
    s = get_user_settings(user_id)
    s[key] = value
    save_settings()
