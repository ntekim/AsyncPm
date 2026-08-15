import sqlite3
import json

DB_NAME = "local_asyncpm.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meeting_logs (
            meeting_id TEXT PRIMARY KEY,
            meeting_title TEXT,
            summary TEXT,
            created_tickets TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_meeting_log(meeting_id: str, title: str, summary: str, tickets: list):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO meeting_logs (meeting_id, meeting_title, summary, created_tickets)
        VALUES (?, ?, ?, ?)
    """, (meeting_id, title, summary, json.dumps(tickets)))
    conn.commit()
    conn.close()

def get_meeting_log(meeting_id: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM meeting_logs WHERE meeting_id = ?", (meeting_id,))
    row = cursor.fetchone()
    conn.close()
    return row