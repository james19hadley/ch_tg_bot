import sqlite3
from ch_tg_bot.database import db

def add_word(user_id: int, text: str, pinyin: str = None,
             trans_ru: str = None, trans_en: str = None) -> bool:
    """
    Add a word to user's vocabulary.
    Returns True if added, False if already existed.
    """
    with db() as conn:
        try:
            conn.execute("""
                INSERT INTO vocabulary (user_id, text, pinyin, trans_ru, trans_en)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, text.strip(), pinyin, trans_ru, trans_en))
            return True
        except sqlite3.IntegrityError:
            return False  # Already exists

def get_words(user_id: int, limit: int = 20, offset: int = 0) -> list[dict]:
    """Get user's vocabulary, newest first."""
    with db() as conn:
        rows = conn.execute("""
            SELECT id, text, pinyin, trans_ru, trans_en, added_at
            FROM vocabulary
            WHERE user_id = ?
            ORDER BY added_at DESC
            LIMIT ? OFFSET ?
        """, (user_id, limit, offset)).fetchall()
        return [dict(r) for r in rows]

def count_words(user_id: int) -> int:
    with db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as n FROM vocabulary WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["n"]

def delete_word(user_id: int, word_id: int) -> bool:
    """Delete a word by its DB id (only if it belongs to this user)."""
    with db() as conn:
        cur = conn.execute(
            "DELETE FROM vocabulary WHERE id = ? AND user_id = ?", (word_id, user_id)
        )
        return cur.rowcount > 0

def get_random_word(user_id: int) -> dict | None:
    """Pick a random word from user's vocabulary."""
    with db() as conn:
        row = conn.execute("""
            SELECT id, text, pinyin, trans_ru, trans_en
            FROM vocabulary
            WHERE user_id = ?
            ORDER BY RANDOM()
            LIMIT 1
        """, (user_id,)).fetchone()
        return dict(row) if row else None

def word_exists(user_id: int, text: str) -> bool:
    with db() as conn:
        row = conn.execute(
            "SELECT 1 FROM vocabulary WHERE user_id = ? AND text = ?",
            (user_id, text.strip())
        ).fetchone()
        return row is not None
