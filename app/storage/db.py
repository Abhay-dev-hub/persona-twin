"""
Local SQLite storage for personas, chat sessions, and messages.
Lives alongside the project (db.sqlite3) — no external DB service
needed for this part, unlike Neo4j/Qdrant which store the actual
persona knowledge.
"""

import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "db.sqlite3"
DATABASE_URL = os.environ.get("DATABASE_URL")

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

@contextmanager
def _connect():
    if DATABASE_URL:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        conn.autocommit = True
        
        class PostgresCursorWrapper:
            def __init__(self, conn):
                self.conn = conn
            def execute(self, query, params=()):
                query = query.replace("?", "%s")
                query = query.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
                cur = self.conn.cursor()
                cur.execute(query, params)
                return cur
            def commit(self):
                pass
            def close(self):
                self.conn.close()

        wrapper = PostgresCursorWrapper(conn)
        try:
            yield wrapper
        finally:
            wrapper.close()
    else:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS personas (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                collection_name TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'pending',
                error_message TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                persona_id TEXT NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
                title TEXT NOT NULL DEFAULT 'New chat',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


# ---------- personas ----------

def create_persona(name: str, collection_name: str) -> dict:
    persona_id = str(uuid.uuid4())
    with _connect() as conn:
        conn.execute(
            "INSERT INTO personas (id, name, collection_name, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
            (persona_id, name, collection_name, _now()),
        )
    return get_persona(persona_id)


def get_persona(persona_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM personas WHERE id = ?", (persona_id,)).fetchone()
        return dict(row) if row else None


def list_personas() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM personas ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def update_persona_status(persona_id: str, status: str, error_message: str | None = None) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE personas SET status = ?, error_message = ? WHERE id = ?",
            (status, error_message, persona_id),
        )


def delete_persona(persona_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM personas WHERE id = ?", (persona_id,))


# ---------- chats ----------

def create_chat(persona_id: str, title: str = "New chat") -> dict:
    chat_id = str(uuid.uuid4())
    with _connect() as conn:
        conn.execute(
            "INSERT INTO chats (id, persona_id, title, created_at) VALUES (?, ?, ?, ?)",
            (chat_id, persona_id, title, _now()),
        )
    return get_chat(chat_id)


def get_chat(chat_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
        return dict(row) if row else None


def list_chats(persona_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM chats WHERE persona_id = ? ORDER BY created_at DESC", (persona_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def delete_chat(chat_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))


def rename_chat(chat_id: str, title: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE chats SET title = ? WHERE id = ?", (title, chat_id))


# ---------- messages ----------

def add_message(chat_id: str, role: str, content: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO messages (chat_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (chat_id, role, content, _now()),
        )
def delete_last_assistant_message(chat_id: str) -> None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, role FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT 1", (chat_id,)
        ).fetchone()
        if row and row["role"] == "assistant":
            conn.execute("DELETE FROM messages WHERE id = ?", (row["id"],))

def list_messages(chat_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM messages WHERE chat_id = ? ORDER BY id ASC", (chat_id,)
        ).fetchall()
        return [dict(r) for r in rows]
