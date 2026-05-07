"""
This initializes the SQLite database for storing user survey responses and chat messages.
It creates two tables: 'responses' for survey data and 'messages' for chat logs,
along with appropriate indexes for efficient querying.
"""

from pathlib import Path
import sqlite3

def init_db(db_path: Path):
    """
    Initialize the SQLite database.
    """
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS responses (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id            TEXT    NOT NULL,
                timestamp             TEXT    NOT NULL,
                latin_level           TEXT,
                ai_familiarity        TEXT,
                easy_to_use           INTEGER,
                understood_questions  INTEGER,
                answers_accurate      INTEGER,
                answers_helpful       INTEGER,
                enjoyed_using         INTEGER,
                increased_interest    INTEGER,
                would_recommend       INTEGER,
                liked_most            TEXT,
                improvements          TEXT,
                other                 TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id   TEXT    NOT NULL,
                chat_id      TEXT    NOT NULL,
                timestamp    TEXT    NOT NULL,
                role         TEXT    NOT NULL,   -- 'user' or 'bot'
                content      TEXT    NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_session ON responses(session_id)")

