import os
import sqlite3

DATABASE = "timeplease.db"
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    import urllib.parse
    creds, host_part = DATABASE_URL.rsplit("@", 1)
    prefix = "postgresql://"
    if creds.startswith(prefix):
        user_pass = creds[len(prefix):]
        if ":" in user_pass:
            user, pwd = user_pass.split(":", 1)
            pwd = urllib.parse.quote(pwd, safe="")
            DATABASE_URL = f"{prefix}{user}:{pwd}@{host_part}"

class DBWrapper:
    def __init__(self):
        self.is_postgres = bool(DATABASE_URL)
        if self.is_postgres:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            self.conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
            self.conn.autocommit = False
        else:
            self.conn = sqlite3.connect(DATABASE)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=ON")

    def execute(self, query, params=()):
        if self.is_postgres:
            # Convert SQLite ? to PostgreSQL %s
            query = query.replace("?", "%s")
            # SQLite datetime('now') -> CURRENT_TIMESTAMP
            query = query.replace("datetime('now')", "CURRENT_TIMESTAMP")
            query = query.replace("datetime('now', 'localtime')", "CURRENT_TIMESTAMP")
            cursor = self.conn.cursor()
            cursor.execute(query, params)
            return cursor
        else:
            return self.conn.execute(query, params)

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

    def cursor(self):
        return self.conn.cursor()

def get_db():
    return DBWrapper()

def init_db():
    db = get_db()
    
    schema = """
        CREATE TABLE IF NOT EXISTS trainers (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            custom_slug TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS members (
            id             TEXT PRIMARY KEY,
            trainer_id     TEXT NOT NULL,
            name           TEXT NOT NULL,
            phone          TEXT NOT NULL,
            total_sessions INTEGER NOT NULL DEFAULT 0,
            used_sessions  INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (trainer_id) REFERENCES trainers(id)
        );

        CREATE TABLE IF NOT EXISTS availabilities (
            id            TEXT PRIMARY KEY,
            trainer_id    TEXT NOT NULL,
            slot_datetime TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'available',
            FOREIGN KEY (trainer_id) REFERENCES trainers(id)
        );

        CREATE TABLE IF NOT EXISTS reservations (
            id              TEXT PRIMARY KEY,
            trainer_id      TEXT NOT NULL,
            member_id       TEXT NOT NULL,
            availability_id TEXT,
            slot_datetime   TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'active',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (trainer_id)   REFERENCES trainers(id),
            FOREIGN KEY (member_id)    REFERENCES members(id),
            FOREIGN KEY (availability_id) REFERENCES availabilities(id)
        );
        
        CREATE TABLE IF NOT EXISTS session_adjustments (
            id         TEXT PRIMARY KEY,
            member_id  TEXT NOT NULL,
            trainer_id TEXT NOT NULL,
            delta      INTEGER NOT NULL,
            reason     TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (member_id)  REFERENCES members(id),
            FOREIGN KEY (trainer_id) REFERENCES trainers(id)
        );
    """
    
    if db.is_postgres:
        db.execute(schema)
    else:
        db.cursor().executescript(schema)
    db.commit()

    # 컬럼 마이그레이션
    for col, typedef in [
        ("cancelled_by",  "TEXT"),
        ("cancel_reason", "TEXT"),
    ]:
        try:
            db.execute(f"ALTER TABLE reservations ADD COLUMN {col} {typedef}")
            db.commit()
        except Exception:
            if db.is_postgres: db.conn.rollback()
            pass

    # trainers 기본 컬럼
    for col in [("custom_slug", "TEXT UNIQUE"), ("password_hash", "TEXT")]:
        try:
            db.execute(f"ALTER TABLE trainers ADD COLUMN {col[0]} {col[1]}")
            db.commit()
        except Exception:
            if db.is_postgres: db.conn.rollback()
            pass

    # availabilities 수업 시간 컬럼
    try:
        db.execute("ALTER TABLE availabilities ADD COLUMN duration_minutes INTEGER DEFAULT 60")
        db.commit()
    except Exception:
        if db.is_postgres: db.conn.rollback()
        pass

    db.close()
