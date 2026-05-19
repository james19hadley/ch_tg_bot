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
    
    if uid in user_settings:
        s = user_settings[uid]
        if isinstance(s, str):
            # Very old format
            user_settings[uid] = {"font": s}
            
        # Migrate from "extra_info" to separated toggles
        if "extra_info" in user_settings[uid]:
            val = user_settings[uid]["extra_info"]
            user_settings[uid].update({
                "pinyin": val, "audio": val, "ru": val, "en": val
            })
            del user_settings[uid]["extra_info"]
            save_settings()

    if uid not in user_settings:
        user_settings[uid] = {
            "font": DEFAULT_FONT,
            "color": "black",
            "vertical": False,
            "pinyin": True,
            "audio": True,
            "ru": True,
            "en": True
        }
        save_settings()
        
    return user_settings[uid]

def update_user_setting(user_id: int, key: str, value):
    s = get_user_settings(user_id)
    s[key] = value
    save_settings()
