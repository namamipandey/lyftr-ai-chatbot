import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote


def db_path(url: str) -> str:
    if not url.startswith('sqlite:///'):
        raise ValueError('DATABASE_URL must be a sqlite:/// URL')
    return unquote(url[len('sqlite:///'):])


class Store:
    def __init__(self, url: str):
        self.path = db_path(url)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL
            )''')
            db.execute('CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id)')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.execute('PRAGMA busy_timeout=20000')
        return db

    def ping(self):
        with self.connect() as db:
            db.execute('SELECT 1').fetchone()

    def history(self, session_id: str):
        with self.connect() as db:
            rows = db.execute('SELECT role,content,metadata FROM messages WHERE session_id=? ORDER BY id', (session_id,)).fetchall()
        return [{'role': r, 'content': c, **({'metadata': json.loads(m)} if m else {})} for r,c,m in rows]

    def append_exchange(self, session_id, user_text, reply, metadata):
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute('INSERT INTO messages(session_id,role,content,metadata,created_at) VALUES (?,?,?,?,?)', (session_id, 'user', user_text, None, now))
            db.execute('INSERT INTO messages(session_id,role,content,metadata,created_at) VALUES (?,?,?,?,?)', (session_id, 'assistant', reply, json.dumps(metadata), now))
