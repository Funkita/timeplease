import sqlite3

DATABASE = "timeplease.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.executescript(
        """
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
            created_at      TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (trainer_id)   REFERENCES trainers(id),
            FOREIGN KEY (member_id)    REFERENCES members(id),
            FOREIGN KEY (availability_id) REFERENCES availabilities(id)
        );
    """
    )
    conn.commit()

    # ── 컬럼 마이그레이션 (이미 존재하면 무시) ──────────────────────────
    for col, typedef in [
        ("cancelled_by",  "TEXT"),          # 'trainer' | 'member'
        ("cancel_reason", "TEXT"),           # 취소 사유 (자유 입력)
    ]:
        try:
            conn.execute(f"ALTER TABLE reservations ADD COLUMN {col} {typedef}")
            conn.commit()
        except Exception:
            pass  # 이미 존재하는 컬럼 — 무시

    # ── trainers 기본 컬럼 ────────────────────────────────────────────
    for col in [("custom_slug", "TEXT UNIQUE"), ("password_hash", "TEXT")]:
        try:
            conn.execute(f"ALTER TABLE trainers ADD COLUMN {col[0]} {col[1]}")
            conn.commit()
        except Exception:
            pass  # 이미 존재하는 컬럼 — 무시

    # ── availabilities 수업 시간 컬럼 ─────────────────────────────────
    try:
        conn.execute("ALTER TABLE availabilities ADD COLUMN duration_minutes INTEGER DEFAULT 60")
        conn.commit()
    except Exception:
        pass

    # ── 세션 조정 내역 테이블 ───────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_adjustments (
            id         TEXT PRIMARY KEY,
            member_id  TEXT NOT NULL,
            trainer_id TEXT NOT NULL,
            delta      INTEGER NOT NULL,   -- +1 or -1
            reason     TEXT,               -- 사유 (선택)
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (member_id)  REFERENCES members(id),
            FOREIGN KEY (trainer_id) REFERENCES trainers(id)
        )
    """)
    conn.commit()

    conn.close()


