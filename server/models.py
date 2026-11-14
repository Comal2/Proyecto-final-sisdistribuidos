import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "/app/data/chat.db")

@contextmanager
def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id       TEXT PRIMARY KEY,
                from_user TEXT NOT NULL,
                origin   TEXT NOT NULL,
                lamport  INTEGER NOT NULL,
                sent_at  TEXT NOT NULL,
                body     TEXT NOT NULL
            );
        """)

# --- Usuarios ---

def create_user(username: str, created_at: str) -> bool:
    """Crea un usuario. Retorna False si ya existe."""
    with get_db() as conn:
        try:
            conn.execute(
                "INSERT INTO users (username, created_at) VALUES (?, ?)",
                (username, created_at)
            )
            return True
        except sqlite3.IntegrityError:
            return False

def user_exists(username: str) -> bool:
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM users WHERE username = ?", (username,)
        ).fetchone()
        return row is not None

# --- Mensajes ---

def save_message(id: str, from_user: str, origin: str, lamport: int, sent_at: str, body: str) -> bool:
    """Guarda un mensaje. Retorna False si el id ya existe (duplicado)."""
    with get_db() as conn:
        try:
            conn.execute(
                "INSERT INTO messages (id, from_user, origin, lamport, sent_at, body) VALUES (?, ?, ?, ?, ?, ?)",
                (id, from_user, origin, lamport, sent_at, body)
            )
            return True
        except sqlite3.IntegrityError:
            return False

def get_history(since_lamport: int = 0) -> list[dict]:
    """Retorna mensajes con lamport > since_lamport, ordenados por (lamport, origin)."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE lamport > ? ORDER BY lamport ASC, origin ASC",
            (since_lamport,)
        ).fetchall()
        return [dict(row) for row in rows]
