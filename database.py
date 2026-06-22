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
    c.execute("""
        CREATE TABLE IF NOT EXISTS qj_campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS qj_main_quests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            sort_order INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS qj_objectives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            main_quest_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            state TEXT DEFAULT 'ongoing',
            sort_order INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS qj_side_quests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            state TEXT DEFAULT 'ongoing',
            sort_order INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS qj_footnotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            main_quest_id INTEGER NOT NULL,
            character_name TEXT NOT NULL,
            text TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0
        )
    """)
    #for session recording
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            channel_id INTEGER PRIMARY KEY,
            started_at TEXT NOT NULL,
            started_by INTEGER
        )
    """)
    conn.commit()
    try:
        c.execute("ALTER TABLE qj_main_quests ADD COLUMN channel_message_id INTEGER")
        conn.commit()
    except Exception:
        pass
    _seed_quest_data(conn)
    conn.close()

#for session recording
def start_session(channel_id: int, started_at: str, started_by: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT OR REPLACE INTO sessions
        (channel_id, started_at, started_by)
        VALUES (?, ?, ?)
        """,
        (channel_id, started_at, started_by),
    )
    conn.commit()
    conn.close()


def get_session(channel_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT started_at, started_by FROM sessions WHERE channel_id = ?",
        (channel_id,),
    )
    row = c.fetchone()
    conn.close()
    return row


def end_session(channel_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "DELETE FROM sessions WHERE channel_id = ?",
        (channel_id,),
    )
    conn.commit()
    conn.close()
def _seed_quest_data(conn):
    c = conn.cursor()
    GUILD_ID = 184915565511442432
    c.execute("SELECT id FROM qj_campaigns WHERE guild_id = ?", (GUILD_ID,))
    if c.fetchone():
        return

    c.execute("INSERT INTO qj_campaigns (guild_id, name) VALUES (?, ?)",
              (GUILD_ID, "~ Both God and Mammon ~"))
    campaign_id = c.lastrowid

    c.execute("INSERT INTO qj_main_quests (campaign_id, name, sort_order) VALUES (?, ?, ?)",
              (campaign_id, "~ Flawful Diamond ~", 0))
    mq1 = c.lastrowid
    c.execute("INSERT INTO qj_objectives (main_quest_id, text, state, sort_order) VALUES (?, ?, ?, ?)",
              (mq1, "Go to Luna to find where the saintess is.", "ongoing", 0))

    c.execute("INSERT INTO qj_main_quests (campaign_id, name, sort_order) VALUES (?, ?, ?)",
              (campaign_id, "~ Astral Eye of the Sky-shouldering Bull ~", 1))
    mq2 = c.lastrowid
    for i, (text, state) in enumerate([
        ("Find Enritzo Tonnuy.", "completed"),
        ("Wait for Enritzo's letter.", "ongoing"),
        ("Meet Enritzo in Nurnthrad.", "ongoing"),
    ]):
        c.execute("INSERT INTO qj_objectives (main_quest_id, text, state, sort_order) VALUES (?, ?, ?, ?)",
                  (mq2, text, state, i))

    side_quests = [
        ("There have been troubles with the company and that they need some of our aid.", "ongoing"),
        ("Some of our local supporters are being harassed by certain individuals of unknown origin.", "completed"),
        ("We got invited by a noble to a fine dining.", "completed"),
        ("We need to keep up the pressure, we are not lacking in money, but our presence need to spread outside of Lollyga.", "completed"),
        ("There is a matter regarding Obelisk, apparently they are being held by press coverage, we can help them take care of it.", "ongoing"),
        ("Recruit an accountant.", "ongoing"),
    ]
    for i, (text, state) in enumerate(side_quests):
        c.execute("INSERT INTO qj_side_quests (campaign_id, text, state, sort_order) VALUES (?, ?, ?, ?)",
                  (campaign_id, text, state, i))

    conn.commit()


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


def get_quest_journal(guild_id: int) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT id, name FROM qj_campaigns WHERE guild_id = ? ORDER BY id DESC LIMIT 1", (guild_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return None
    campaign_id, campaign_name = row

    c.execute("SELECT id, name, description FROM qj_main_quests WHERE campaign_id = ? ORDER BY sort_order", (campaign_id,))
    main_quests_raw = c.fetchall()

    main_quests = []
    for mq_id, mq_name, mq_desc in main_quests_raw:
        c.execute("SELECT text, state FROM qj_objectives WHERE main_quest_id = ? ORDER BY sort_order", (mq_id,))
        objectives = c.fetchall()
        c.execute("SELECT character_name, text FROM qj_footnotes WHERE main_quest_id = ? ORDER BY sort_order", (mq_id,))
        footnotes = c.fetchall()
        main_quests.append({
            "name": mq_name,
            "description": mq_desc,
            "objectives": objectives,
            "footnotes": footnotes,
        })

    c.execute("SELECT text, state FROM qj_side_quests WHERE campaign_id = ? ORDER BY sort_order", (campaign_id,))
    side_quests = c.fetchall()

    conn.close()
    return {
        "campaign": campaign_name,
        "main_quests": main_quests,
        "side_quests": side_quests,
    }


def set_main_quest_message_id(quest_id: int, message_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE qj_main_quests SET channel_message_id = ? WHERE id = ?", (message_id, quest_id))
    conn.commit()
    conn.close()


def get_main_quest_names(guild_id: int) -> list[tuple[int, str]]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT mq.id, mq.name FROM qj_main_quests mq
        JOIN qj_campaigns qc ON mq.campaign_id = qc.id
        WHERE qc.guild_id = ? ORDER BY mq.sort_order
    """, (guild_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def get_side_quest_list(guild_id: int) -> list[tuple[int, str]]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT sq.id, sq.text FROM qj_side_quests sq
        JOIN qj_campaigns qc ON sq.campaign_id = qc.id
        WHERE qc.guild_id = ? ORDER BY sq.sort_order
    """, (guild_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def delete_main_quest(quest_id: int) -> int | None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT channel_message_id FROM qj_main_quests WHERE id = ?", (quest_id,))
    row = c.fetchone()
    message_id = row[0] if row else None
    c.execute("DELETE FROM qj_objectives WHERE main_quest_id = ?", (quest_id,))
    c.execute("DELETE FROM qj_footnotes WHERE main_quest_id = ?", (quest_id,))
    c.execute("DELETE FROM qj_main_quests WHERE id = ?", (quest_id,))
    conn.commit()
    conn.close()
    return message_id


def delete_side_quest(quest_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM qj_side_quests WHERE id = ?", (quest_id,))
    conn.commit()
    conn.close()


def add_main_quest(guild_id: int, name: str, objectives: list[str], description: str | None = None) -> int | None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM qj_campaigns WHERE guild_id = ? ORDER BY id DESC LIMIT 1", (guild_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return None
    campaign_id = row[0]
    c.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM qj_main_quests WHERE campaign_id = ?", (campaign_id,))
    sort_order = c.fetchone()[0]
    c.execute("INSERT INTO qj_main_quests (campaign_id, name, description, sort_order) VALUES (?, ?, ?, ?)",
              (campaign_id, name, description, sort_order))
    mq_id = c.lastrowid
    for i, obj in enumerate(objectives):
        c.execute("INSERT INTO qj_objectives (main_quest_id, text, state, sort_order) VALUES (?, ?, 'ongoing', ?)",
                  (mq_id, obj, i))
    conn.commit()
    conn.close()
    return mq_id


def save_footnote(main_quest_id: int, character_name: str, text: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM qj_footnotes WHERE main_quest_id = ?", (main_quest_id,))
    sort_order = c.fetchone()[0]
    c.execute("INSERT INTO qj_footnotes (main_quest_id, character_name, text, sort_order) VALUES (?, ?, ?, ?)",
              (main_quest_id, character_name, text, sort_order))
    conn.commit()
    conn.close()


def add_side_quest(guild_id: int, text: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM qj_campaigns WHERE guild_id = ? ORDER BY id DESC LIMIT 1", (guild_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    campaign_id = row[0]
    c.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM qj_side_quests WHERE campaign_id = ?", (campaign_id,))
    sort_order = c.fetchone()[0]
    c.execute("INSERT INTO qj_side_quests (campaign_id, text, state, sort_order) VALUES (?, ?, 'ongoing', ?)",
              (campaign_id, text, sort_order))
    conn.commit()
    conn.close()
    return True


def get_main_quest_detail(quest_id: int) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, description, channel_message_id FROM qj_main_quests WHERE id = ?", (quest_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {"name": row[0], "description": row[1], "channel_message_id": row[2]}


def update_quest_description(quest_id: int, description: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE qj_main_quests SET description = ? WHERE id = ?", (description, quest_id))
    conn.commit()
    conn.close()


def get_objectives_for_quest(main_quest_id: int) -> list[tuple[int, str, str]]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, text, state FROM qj_objectives WHERE main_quest_id = ? ORDER BY sort_order", (main_quest_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def update_objective_state(objective_id: int, state: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE qj_objectives SET state = ? WHERE id = ?", (state, objective_id))
    conn.commit()
    conn.close()


def update_all_ongoing_objectives(main_quest_id: int, state: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE qj_objectives SET state = ? WHERE main_quest_id = ? AND state = 'ongoing'", (state, main_quest_id))
    conn.commit()
    conn.close()


def get_footnotes_for_quest(main_quest_id: int) -> list[tuple[str, str]]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT character_name, text FROM qj_footnotes WHERE main_quest_id = ? ORDER BY sort_order", (main_quest_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def update_side_quest_state(quest_id: int, state: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE qj_side_quests SET state = ? WHERE id = ?", (state, quest_id))
    conn.commit()
    conn.close()


def get_leaderboard() -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, coins FROM users ORDER BY coins DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    return rows
