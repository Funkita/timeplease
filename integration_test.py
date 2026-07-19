"""
integration_test.py — TimePlease API Integration Tests
Run: python integration_test.py
"""
import sys, io
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import urllib.request
import json
import sqlite3

BASE = "http://localhost:5000"


def get_page(path):
    r = urllib.request.urlopen(BASE + path)
    return r.status


def post(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        BASE + path, data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        r = urllib.request.urlopen(req)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def delete(path):
    req = urllib.request.Request(BASE + path, method="DELETE")
    try:
        r = urllib.request.urlopen(req)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def ok(label):
    print(f"  [PASS] {label}")


def fail(label, detail=""):
    print(f"  [FAIL] {label}")
    if detail:
        print(f"         {detail}")
    raise AssertionError(label)


# ── 1: Page loads ─────────────────────────────────────────────
print("--- TEST 1: Page loads ---")
assert get_page("/") == 200, "Dashboard page failed"
ok("Trainer dashboard loads (HTTP 200)")
assert get_page("/r/trainer_kim") == 200, "Booking page failed"
ok("Member booking page loads (HTTP 200)")

# ── Read seed data ─────────────────────────────────────────────
db = sqlite3.connect("timeplease.db")
db.row_factory = sqlite3.Row
trainer = db.execute(
    "SELECT * FROM trainers WHERE custom_slug='trainer_kim'"
).fetchone()
member = db.execute(
    "SELECT * FROM members WHERE name=?", ("\uc5b4\ud478\uc5b4\ud478",)
).fetchone()
slots = db.execute(
    "SELECT * FROM availabilities WHERE trainer_id=? AND status='available'",
    (trainer["id"],)
).fetchall()
db.close()

TRAINER_ID = trainer["id"]
MEMBER_ID = member["id"]
SLOT_ID = slots[0]["id"]
print(f"  Trainer ID     : {TRAINER_ID[:8]}...")
print(f"  Member         : {member['name']} (used={member['used_sessions']}/{member['total_sessions']})")
print(f"  Available slots: {len(slots)}")

# ── 2: Auth — correct ─────────────────────────────────────────
print("\n--- TEST 2: Auth verify (correct) ---")
code, data = post("/api/auth/verify", {
    "trainer_id": TRAINER_ID,
    "name": "\uc5b4\ud478\uc5b4\ud478",
    "phone": "010-1234-5678"
})
if code != 200:
    fail("Auth correct credentials", f"HTTP {code} {data}")
if data["used_sessions"] != 3:
    fail("used_sessions should be 3", str(data))
ok(f"Auth OK — used_sessions={data['used_sessions']}/{data['total_sessions']}")

# ── 3: Auth — wrong credentials ───────────────────────────────
print("\n--- TEST 3: Auth verify (wrong credentials) ---")
code, data = post("/api/auth/verify", {
    "trainer_id": TRAINER_ID,
    "name": "\ud64d\uae38\ub3d9",
    "phone": "010-9999-9999"
})
if code != 404:
    fail("Wrong credentials should return 404", f"Got {code}")
ok("Wrong credentials rejected (HTTP 404)")

# ── 4: Create reservation ─────────────────────────────────────
print("\n--- TEST 4: Create reservation ---")
code, data = post("/api/reservations", {
    "trainer_id": TRAINER_ID,
    "member_id": MEMBER_ID,
    "availability_id": SLOT_ID
})
if code != 201:
    fail("Reservation creation failed", f"HTTP {code} {data}")
RESERVATION_ID = data["reservation_id"]
if data["member"]["used_sessions"] != 4:
    fail("used_sessions should be 4", str(data["member"]))
ok(f"Reservation created — used_sessions now {data['member']['used_sessions']}")
ok(f"Slot datetime: {data['slot_datetime']}")

# ── 5: Slot marked reserved ───────────────────────────────────
print("\n--- TEST 5: Slot status = reserved ---")
db = sqlite3.connect("timeplease.db")
db.row_factory = sqlite3.Row
slot = db.execute("SELECT status FROM availabilities WHERE id=?", (SLOT_ID,)).fetchone()
db.close()
if slot["status"] != "reserved":
    fail("Slot should be reserved", slot["status"])
ok("Slot status = reserved")

# ── 6: Double-booking rejected ────────────────────────────────
print("\n--- TEST 6: Double-booking rejected ---")
code, data = post("/api/reservations", {
    "trainer_id": TRAINER_ID,
    "member_id": MEMBER_ID,
    "availability_id": SLOT_ID
})
if code != 409:
    fail("Double-booking should return 409", f"Got {code}")
ok("Double-booking rejected (HTTP 409)")

# ── 7: Cancel reservation ─────────────────────────────────────
print("\n--- TEST 7: Cancel reservation ---")
code, data = delete(f"/api/reservations/{RESERVATION_ID}")
if code != 200:
    fail("Cancellation failed", f"HTTP {code} {data}")
if data["member"]["used_sessions"] != 3:
    fail("used_sessions should be restored to 3", str(data["member"]))
ok(f"Reservation cancelled — used_sessions restored to {data['member']['used_sessions']}")

# ── 8: Slot restored to available ─────────────────────────────
print("\n--- TEST 8: Slot restored to available ---")
db = sqlite3.connect("timeplease.db")
db.row_factory = sqlite3.Row
slot = db.execute("SELECT status FROM availabilities WHERE id=?", (SLOT_ID,)).fetchone()
db.close()
if slot["status"] != "available":
    fail("Slot should be restored to available", slot["status"])
ok("Slot status restored = available")

# ── 9: Slot toggle (activate / deactivate) ────────────────────
print("\n--- TEST 9: Slot toggle ---")
code, res = post("/api/slots/toggle", {
    "trainer_id": TRAINER_ID,
    "slot_datetime": "2026-07-25T08:00:00"
})
if code != 200 or res.get("action") != "added":
    fail("Slot toggle activate failed", str(res))
ok("New slot activated")

code, res = post("/api/slots/toggle", {
    "trainer_id": TRAINER_ID,
    "slot_datetime": "2026-07-25T08:00:00"
})
if code != 200 or res.get("action") != "removed":
    fail("Slot toggle deactivate failed", str(res))
ok("Same slot deactivated (toggle)")

# ── DONE ──────────────────────────────────────────────────────
print()
print("=" * 50)
print("  ALL 9 INTEGRATION TESTS PASSED!")
print("=" * 50)
