"""
seed_data.py - Mock data seed script
Usage: python seed_data.py

NOTE: Uses deterministic (uuid5) IDs so re-running never changes UUIDs.
      This means existing browser sessions stay valid after re-seed.
"""
import sys, io
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import uuid
from datetime import datetime, timedelta
from database import init_db, get_db

# ── 결정론적 UUID (재실행해도 항상 동일한 ID) ─────────────────────────────
# uuid5 uses SHA-1 hash of (namespace + name) → same name = same UUID every time
_NS = uuid.NAMESPACE_DNS
TRAINER_ID = str(uuid.uuid5(_NS, "timeplease.trainer.kim"))
MEMBER_ID  = str(uuid.uuid5(_NS, "timeplease.member.어푸어푸.010-1234-5678"))

# ── 기준 일시: 실행 당일을 기준으로 슬롯 생성 ─────────────────────────────
TODAY = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

# 오늘 포함 이번 주~다음 주 슬롯 (available 5개)
SLOT_OFFSETS = [
    (1, 10),   # 내일 10:00
    (1, 14),   # 내일 14:00
    (2, 10),   # 모레 10:00
    (5, 10),   # 5일 후 10:00
    (6, 16),   # 6일 후 16:00
]


def seed():
    init_db()
    db = get_db()

    # 기존 데이터 초기화
    db.executescript("""
        DELETE FROM reservations;
        DELETE FROM availabilities;
        DELETE FROM members;
        DELETE FROM trainers;
    """)
    db.commit()

    # 강사 Kim 등록
    db.execute(
        "INSERT INTO trainers (id, name, custom_slug) VALUES (?, ?, ?)",
        (TRAINER_ID, "Kim", "trainer_kim"),
    )

    # 회원 어푸어푸 등록
    db.execute(
        """INSERT INTO members
           (id, trainer_id, name, phone, total_sessions, used_sessions)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (MEMBER_ID, TRAINER_ID, "어푸어푸", "010-1234-5678", 10, 3),
    )

    # 예약 가능 슬롯 생성 (슬롯 ID도 결정론적)
    for day_offset, hour in SLOT_OFFSETS:
        slot_dt = TODAY + timedelta(days=day_offset)
        slot_dt = slot_dt.replace(hour=hour)
        slot_str = slot_dt.strftime("%Y-%m-%dT%H:%M:%S")
        slot_id  = str(uuid.uuid5(_NS, f"timeplease.slot.{slot_str}"))
        db.execute(
            "INSERT OR IGNORE INTO availabilities (id, trainer_id, slot_datetime, status) VALUES (?, ?, ?, ?)",
            (slot_id, TRAINER_ID, slot_str, "available"),
        )

    db.commit()
    db.close()

    print("[OK] Seed data inserted successfully!")
    print(f"     Trainer ID : {TRAINER_ID}")
    print(f"     Member  ID : {MEMBER_ID}")
    print(f"     Slots   : {len(SLOT_OFFSETS)} available slots (from {TODAY.strftime('%Y-%m-%d')})")
    print()
    print("Trainer ID is now STABLE — re-running this script keeps the same UUIDs.")
    print()
    print("Next step: run 'python app.py'")
    print("  Trainer dashboard : http://localhost:5000/")
    print("  Member booking    : http://localhost:5000/r/trainer_kim")


if __name__ == "__main__":
    seed()
