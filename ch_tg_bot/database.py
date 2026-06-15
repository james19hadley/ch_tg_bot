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

            CREATE TABLE IF NOT EXISTS user_progress (
                user_id           INTEGER PRIMARY KEY,
                streak            INTEGER DEFAULT 0,
                score             INTEGER DEFAULT 0,
                lessons_completed TEXT    DEFAULT '[]',
                accuracy          INTEGER DEFAULT 0,
                updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS users (
                user_id        INTEGER PRIMARY KEY,
                username       TEXT,
                first_name     TEXT,
                last_name      TEXT,
                share_progress INTEGER DEFAULT 0,
                updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS pairing (
                tracker_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                PRIMARY KEY (tracker_id, student_id),
                FOREIGN KEY (tracker_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES users(user_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS progress_push_configs (
                student_id        INTEGER PRIMARY KEY,
                chat_id           INTEGER NOT NULL,
                message_thread_id INTEGER,
                FOREIGN KEY (student_id) REFERENCES users(user_id) ON DELETE CASCADE
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

# ── User progress (synced from Web App) ────────────────────────────────────────

def update_user_progress(user_id: int, streak: int, score: int, lessons: list, accuracy: int) -> None:
    with db() as conn:
        conn.execute("""
            INSERT INTO user_progress (user_id, streak, score, lessons_completed, accuracy, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                streak = excluded.streak,
                score = excluded.score,
                lessons_completed = excluded.lessons_completed,
                accuracy = excluded.accuracy,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, streak, score, json.dumps(lessons), accuracy))

def get_all_user_progress() -> list[dict]:
    with db() as conn:
        rows = conn.execute("""
            SELECT user_id, streak, score, lessons_completed, accuracy, updated_at
            FROM user_progress
            ORDER BY updated_at DESC
        """).fetchall()
        return [dict(r) for r in rows]

# ── Users & Sharing / Pairing ──────────────────────────────────────────────────

def upsert_user(user_id: int, username: str | None, first_name: str | None, last_name: str | None) -> None:
    if username:
        username = username.lower()
    with db() as conn:
        conn.execute("""
            INSERT INTO users (user_id, username, first_name, last_name, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                username = COALESCE(excluded.username, users.username),
                first_name = COALESCE(excluded.first_name, users.first_name),
                last_name = COALESCE(excluded.last_name, users.last_name),
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, username, first_name, last_name))

def set_share_progress(user_id: int, share: bool) -> None:
    with db() as conn:
        conn.execute("""
            INSERT INTO users (user_id, share_progress, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                share_progress = excluded.share_progress,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, 1 if share else 0))

def get_user_by_username(username: str) -> dict | None:
    username = username.lower().lstrip('@')
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None

def get_user_by_id(user_id: int) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

def add_pairing(tracker_id: int, student_id: int) -> None:
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO pairing (tracker_id, student_id) VALUES (?, ?)", (tracker_id, student_id))

def remove_pairing(tracker_id: int, student_id: int) -> bool:
    with db() as conn:
        cur = conn.execute("DELETE FROM pairing WHERE tracker_id = ? AND student_id = ?", (tracker_id, student_id))
        return cur.rowcount > 0

def is_paired(tracker_id: int, student_id: int) -> bool:
    with db() as conn:
        row = conn.execute("SELECT 1 FROM pairing WHERE tracker_id = ? AND student_id = ?", (tracker_id, student_id)).fetchone()
        return row is not None

def get_paired_students(tracker_id: int) -> list[dict]:
    with db() as conn:
        rows = conn.execute("""
            SELECT u.user_id, u.username, u.first_name, u.last_name, u.share_progress,
                   p.streak, p.score, p.lessons_completed, p.accuracy, p.updated_at
            FROM pairing pr
            JOIN users u ON pr.student_id = u.user_id
            LEFT JOIN user_progress p ON pr.student_id = p.user_id
            WHERE pr.tracker_id = ?
        """, (tracker_id,)).fetchall()
        return [dict(r) for r in rows]

def get_student_progress(student_id: int) -> dict | None:
    with db() as conn:
        row = conn.execute("""
            SELECT u.user_id, u.username, u.first_name, u.last_name, u.share_progress,
                   p.streak, p.score, p.lessons_completed, p.accuracy, p.updated_at
            FROM users u
            LEFT JOIN user_progress p ON u.user_id = p.user_id
            WHERE u.user_id = ?
        """, (student_id,)).fetchone()
        return dict(row) if row else None

def upsert_progress_push_config(student_id: int, chat_id: int, message_thread_id: int | None) -> None:
    with db() as conn:
        conn.execute("""
            INSERT INTO progress_push_configs (student_id, chat_id, message_thread_id)
            VALUES (?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                chat_id = excluded.chat_id,
                message_thread_id = excluded.message_thread_id
        """, (student_id, chat_id, message_thread_id))

def remove_progress_push_config(student_id: int) -> bool:
    with db() as conn:
        cur = conn.execute("DELETE FROM progress_push_configs WHERE student_id = ?", (student_id,))
        return cur.rowcount > 0

def get_progress_push_config(student_id: int) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM progress_push_configs WHERE student_id = ?", (student_id,)).fetchone()
        return dict(row) if row else None
