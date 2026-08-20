import sqlite3
import json

DB_NAME = "local_asyncpm.db"

STOP_WORDS = {"the", "a", "an", "for", "to", "of", "in", "on", "and", "or", "is", "are", "update", "fix", "add", "create", "new", "please", "our", "api"}

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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticket_memory (
            ticket_key TEXT PRIMARY KEY,
            summary TEXT,
            meeting_id TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_ticket_memory(ticket_key: str, summary: str, meeting_id: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO ticket_memory (ticket_key, summary, meeting_id, status)
        VALUES (?, ?, ?, 'Open')
    """, (ticket_key, summary, meeting_id))
    conn.commit()
    conn.close()

def search_past_tickets(query: str) -> list:
    """Searches persistent memory for existing tickets matching meaningful keywords (ignoring stop-words)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT ticket_key, summary, meeting_id FROM ticket_memory")
    rows = cursor.fetchall()
    conn.close()

    matches = []
    # Strip common stop-words
    query_words = set(query.lower().split()) - STOP_WORDS
    
    for ticket_key, summary, meeting_id in rows:
        summary_words = set(summary.lower().split()) - STOP_WORDS
        # Require at least 3 distinct meaningful keyword overlaps
        if len(query_words.intersection(summary_words)) >= 3:
            matches.append({"ticket_key": ticket_key, "summary": summary, "meeting_id": meeting_id})
    return matches

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