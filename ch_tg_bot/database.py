import sqlite3
import json
import os
import logging
from contextlib import contextmanager
from ch_tg_bot.config import DB_FILE, DEFAULT_FONT

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

@contextmanager
def db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    with db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id  INTEGER PRIMARY KEY,
                font     TEXT    DEFAULT 'sans_regular',
                color    TEXT    DEFAULT 'black',
                vertical INTEGER DEFAULT 0,
                pinyin   INTEGER DEFAULT 1,
                audio    INTEGER DEFAULT 1,
                ru_trans INTEGER DEFAULT 1,
                en_trans INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS vocabulary (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id  INTEGER NOT NULL,
                text     TEXT    NOT NULL,
                pinyin   TEXT,
                trans_ru TEXT,
                trans_en TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, text)
            );

            CREATE TABLE IF NOT EXISTS push_schedule (
                user_id        INTEGER PRIMARY KEY,
                chat_id        INTEGER NOT NULL,
                enabled        INTEGER DEFAULT 0,
                pushes_per_day INTEGER DEFAULT 2,
                last_push_at   TIMESTAMP
            );
        """)

def _migrate_from_json(json_path: str):
    """One-time migration from old JSON settings file."""
    if not os.path.exists(json_path):
        return
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            old_data = json.load(f)
    except Exception as e:
        logging.warning(f"Could not read old JSON settings: {e}")
        return

    migrated = 0
    with db() as conn:
        for uid_str, s in old_data.items():
            try:
                uid = int(uid_str)
            except ValueError:
                continue

            if isinstance(s, str):
                s = {"font": s}

            if "extra_info" in s:
                val = s.pop("extra_info")
                s.update({"pinyin": val, "audio": val, "ru": val, "en": val})

            conn.execute("""
                INSERT OR IGNORE INTO user_settings
                    (user_id, font, color, vertical, pinyin, audio, ru_trans, en_trans)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                uid,
                s.get("font", DEFAULT_FONT),
                s.get("color", "black"),
                1 if s.get("vertical", False) else 0,
                1 if s.get("pinyin", True) else 0,
                1 if s.get("audio", True) else 0,
                1 if s.get("ru", True) else 0,
                1 if s.get("en", True) else 0,
            ))
            migrated += 1

    if migrated:
        backup = json_path + ".migrated"
        os.rename(json_path, backup)
        logging.info(f"Migrated {migrated} users from JSON -> SQLite. Old file renamed to {backup}")

def load_settings():
    """Initialize DB and migrate old data if needed."""
    init_db()
    _migrate_from_json("data/settings.json")

# ── User settings ──────────────────────────────────────────────────────────────

_DEFAULTS = {
    "font": DEFAULT_FONT,
    "color": "black",
    "vertical": False,
    "pinyin": True,
    "audio": True,
    "ru": True,
    "en": True,
}

def get_user_settings(user_id: int) -> dict:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM user_settings WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            conn.execute("INSERT INTO user_settings (user_id) VALUES (?)", (user_id,))
            return dict(_DEFAULTS)
        return {
            "font":     row["font"],
            "color":    row["color"],
            "vertical": bool(row["vertical"]),
            "pinyin":   bool(row["pinyin"]),
            "audio":    bool(row["audio"]),
            "ru":       bool(row["ru_trans"]),
            "en":       bool(row["en_trans"]),
        }

def update_user_setting(user_id: int, key: str, value) -> None:
    col_map = {"ru": "ru_trans", "en": "en_trans"}
    col = col_map.get(key, key)
    db_value = 1 if value is True else (0 if value is False else value)
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)", (user_id,))
        conn.execute(f"UPDATE user_settings SET {col} = ? WHERE user_id = ?", (db_value, user_id))

# ── Push schedule ──────────────────────────────────────────────────────────────

def get_push_settings(user_id: int) -> dict | None:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM push_schedule WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return None
        return {
            "chat_id":        row["chat_id"],
            "enabled":        bool(row["enabled"]),
            "pushes_per_day": row["pushes_per_day"],
            "last_push_at":   row["last_push_at"],
        }

def upsert_push_settings(user_id: int, chat_id: int, enabled: bool, pushes_per_day: int) -> None:
    with db() as conn:
        conn.execute("""
            INSERT INTO push_schedule (user_id, chat_id, enabled, pushes_per_day)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                chat_id = excluded.chat_id,
                enabled = excluded.enabled,
                pushes_per_day = excluded.pushes_per_day
        """, (user_id, chat_id, 1 if enabled else 0, pushes_per_day))

def update_last_push(user_id: int) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE push_schedule SET last_push_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,)
        )

def get_all_push_targets() -> list[dict]:
    with db() as conn:
        rows = conn.execute("""
            SELECT user_id, chat_id, pushes_per_day, last_push_at
            FROM push_schedule
            WHERE enabled = 1 AND pushes_per_day > 0
        """).fetchall()
        return [dict(r) for r in rows]
