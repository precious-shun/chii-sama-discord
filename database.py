import sqlite3
from datetime import date

DB_PATH = "chiisama.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            coins INTEGER DEFAULT 0,
            last_daily TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS conversation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER,
            user_id INTEGER,
            user_name TEXT,
            role TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            user_id INTEGER PRIMARY KEY,
            character_id INTEGER NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS guild_campaigns (
            guild_id INTEGER PRIMARY KEY,
            campaign_name TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_message(channel_id: int, user_id: int, user_name: str, role: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO conversation_history (channel_id, user_id, user_name, role, content) VALUES (?, ?, ?, ?, ?)",
        (channel_id, user_id, user_name, role, content),
    )
    conn.commit()
    conn.close()


def get_history(channel_id: int, limit: int = 30) -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT user_name, role, content, timestamp FROM conversation_history WHERE channel_id = ? ORDER BY id DESC LIMIT ?",
        (channel_id, limit),
    )
    rows = c.fetchall()
    conn.close()
    return list(reversed(rows))


def ensure_user(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, coins) VALUES (?, 0)", (user_id,))
    conn.commit()
    conn.close()


def get_user(user_id: int) -> dict:
    ensure_user(user_id)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT coins, last_daily FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return {"coins": row[0], "last_daily": row[1]}


def add_coins(user_id: int, amount: int):
    ensure_user(user_id)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()


def claim_daily(user_id: int) -> bool:
    ensure_user(user_id)
    today = str(date.today())
    user = get_user(user_id)
    if user["last_daily"] == today:
        return False
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE users SET coins = coins + 100, last_daily = ? WHERE user_id = ?",
        (today, user_id),
    )
    conn.commit()
    conn.close()
    return True


def link_character(user_id: int, character_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO characters (user_id, character_id) VALUES (?, ?)",
        (user_id, character_id),
    )
    conn.commit()
    conn.close()


def get_all_characters() -> list[tuple[int, int]]:
    """Returns all (user_id, character_id) pairs."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, character_id FROM characters")
    rows = c.fetchall()
    conn.close()
    return rows


def get_character_id(user_id: int) -> int | None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT character_id FROM characters WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def set_campaign(guild_id: int, campaign_name: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO guild_campaigns (guild_id, campaign_name) VALUES (?, ?)",
        (guild_id, campaign_name),
    )
    conn.commit()
    conn.close()


def get_campaign(guild_id: int) -> str | None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT campaign_name FROM guild_campaigns WHERE guild_id = ?", (guild_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def get_leaderboard() -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, coins FROM users ORDER BY coins DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    return rows
