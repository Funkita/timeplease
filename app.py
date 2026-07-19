"""
app.py — 수업콕 Flask Application
강사 로그인/회원가입 + 대시보드 + 회원 예약 API
"""

import os
from datetime import datetime, timedelta
import re
import uuid
from functools import wraps

MASTER_PASSWORD = os.environ.get("MASTER_PASSWORD", "@3010@")

from flask import (
    Flask, jsonify, render_template, request,
    abort, redirect, url_for, session
)
from werkzeug.security import generate_password_hash, check_password_hash

from database import init_db, get_db

app = Flask(__name__)
# SECRET_KEY: 환경변수로 설정 권장. 없으면 랜덤 (재시작 시 세션 초기화)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(32))


# ── DB 초기화 ─────────────────────────────────────────────────────────
_db_initialized = False

# 매 요청마다 DB 초기화(init_db)를 실행하면 엄청 느려지므로 최초 1회만 실행하도록 수정
@app.before_request
def setup():
    global _db_initialized
    if not _db_initialized:
        init_db()
        _db_initialized = True


# ══════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════

def login_required(f):
    """강사 로그인 필요 데코레이터"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "trainer_id" not in session:
            return redirect(url_for("trainer_login"))
        return f(*args, **kwargs)
    return decorated


def _check_trainer_session(trainer_id):
    """세션 강사 ID 불일치 시 403 반환"""
    if session.get("trainer_id") != trainer_id:
        return jsonify({"error": "인증이 필요합니다."}), 403
    return None


def _slot_belongs_to_session(slot_id):
    """슬롯 소유자가 세션 강사가 아니면 403 반환"""
    db = get_db()
    slot = db.execute(
        "SELECT trainer_id FROM availabilities WHERE id=?", (slot_id,)
    ).fetchone()
    db.close()
    if not slot:
        return jsonify({"error": "슬롯을 찾을 수 없습니다."}), 404
    if slot["trainer_id"] != session.get("trainer_id"):
        return jsonify({"error": "권한이 없습니다."}), 403
    return None


def _member_belongs_to_session(member_id):
    """회원 소유자가 세션 강사가 아니면 403 반환"""
    db = get_db()
    member = db.execute(
        "SELECT trainer_id FROM members WHERE id=?", (member_id,)
    ).fetchone()
    db.close()
    if not member:
        return jsonify({"error": "회원을 찾을 수 없습니다."}), 404
    if member["trainer_id"] != session.get("trainer_id"):
        return jsonify({"error": "권한이 없습니다."}), 403
    return None


# ══════════════════════════════════════════════════════════════════════
# PAGE ROUTES — TRAINER AUTH
# ══════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    if "trainer_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("trainer_login"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    trainer = db.execute(
        "SELECT * FROM trainers WHERE id=?", (session["trainer_id"],)
    ).fetchone()
    db.close()
    if not trainer:
        session.clear()
        return redirect(url_for("trainer_login"))
    return render_template("trainer/dashboard.html", trainer=dict(trainer))


@app.route("/trainer/login", methods=["GET", "POST"])
def trainer_login():
    if "trainer_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        data     = request.get_json()
        slug     = (data.get("slug") or "").strip()
        password = data.get("password") or ""
        if not slug or not password:
            return jsonify({"error": "주소와 비밀번호를 입력해주세요."}), 400
        db = get_db()
        trainer = db.execute(
            "SELECT * FROM trainers WHERE custom_slug=?", (slug,)
        ).fetchone()
        db.close()
        if not trainer or not trainer["password_hash"]:
            return jsonify({"error": "주소 또는 비밀번호가 올바르지 않습니다."}), 401
        if not check_password_hash(trainer["password_hash"], password):
            return jsonify({"error": "주소 또는 비밀번호가 올바르지 않습니다."}), 401
        session["trainer_id"]   = trainer["id"]
        session["trainer_name"] = trainer["name"]
        return jsonify({"redirect": url_for("dashboard")})
    return render_template("trainer/login.html")


@app.route("/trainer/register", methods=["GET", "POST"])
def trainer_register():
    if "trainer_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        data     = request.get_json()
        name     = (data.get("name") or "").strip()
        slug     = (data.get("slug") or "").strip()
        password = data.get("password") or ""
        confirm  = data.get("confirm") or ""
        if not name or not slug or not password:
            return jsonify({"error": "모든 항목을 입력해주세요."}), 400
        if not re.match(r"^[a-z0-9_-]+$", slug):
            return jsonify({"error": "예약 주소는 영문 소문자/숫자/-/_만 사용 가능합니다."}), 400
        if len(password) < 6:
            return jsonify({"error": "비밀번호는 6자 이상이어야 합니다."}), 400
        if password != confirm:
            return jsonify({"error": "비밀번호가 일치하지 않습니다."}), 400
        db = get_db()
        existing = db.execute(
            "SELECT id FROM trainers WHERE custom_slug=?", (slug,)
        ).fetchone()
        if existing:
            db.close()
            return jsonify({"error": "이미 사용 중인 주소입니다. 다른 주소를 선택해주세요."}), 409
        new_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO trainers (id, name, custom_slug, password_hash) VALUES (?, ?, ?, ?)",
            (new_id, name, slug, generate_password_hash(password)),
        )
        db.commit()
        db.close()
        session["trainer_id"]   = new_id
        session["trainer_name"] = name
        return jsonify({"redirect": url_for("dashboard")}), 201
    return render_template("trainer/register.html")


@app.route("/trainer/logout")
def trainer_logout():
    session.clear()
    return redirect(url_for("trainer_login"))


@app.route("/r/<slug>")
def member_booking(slug):
    """회원 예약 페이지 (공개)"""
    db = get_db()
    trainer = db.execute(
        "SELECT * FROM trainers WHERE custom_slug = ?", (slug,)
    ).fetchone()
    db.close()
    if not trainer:
        abort(404)
    return render_template("member/booking.html", trainer=dict(trainer))



# ══════════════════════════════════════════════════════════════════════
# API — SLOTS (availabilities)
# ══════════════════════════════════════════════════════════════════════

@app.route("/api/slots/<trainer_id>")
def get_slots(trainer_id):
    """강사의 모든 슬롯 조회 (available / reserved 포함)"""
    db = get_db()
    rows = db.execute(
        "SELECT * FROM availabilities WHERE trainer_id = ? ORDER BY slot_datetime",
        (trainer_id,),
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/slots/toggle", methods=["POST"])
def toggle_slot():
    data          = request.get_json()
    trainer_id    = data.get("trainer_id")
    slot_datetime = data.get("slot_datetime")
    err = _check_trainer_session(trainer_id)
    if err: return err
    if not slot_datetime:
        return jsonify({"error": "slot_datetime 필요"}), 400

    db = get_db()
    existing = db.execute(
        "SELECT * FROM availabilities WHERE trainer_id = ? AND slot_datetime = ?",
        (trainer_id, slot_datetime),
    ).fetchone()

    if existing:
        # reserved 슬롯은 토글 불가
        if existing["status"] == "reserved":
            db.close()
            return jsonify({"error": "예약된 슬롯은 비활성화할 수 없습니다."}), 400
        db.execute(
            "DELETE FROM availabilities WHERE id = ?", (existing["id"],)
        )
        db.commit()
        db.close()
        return jsonify({"action": "removed", "slot_datetime": slot_datetime})
    else:
        new_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO availabilities (id, trainer_id, slot_datetime, status) VALUES (?, ?, ?, ?)",
            (new_id, trainer_id, slot_datetime, "available"),
        )
        db.commit()
        db.close()
        return jsonify({"action": "added", "id": new_id, "slot_datetime": slot_datetime, "status": "available"})


@app.route("/api/slots/add", methods=["POST"])
def add_slot():
    """슬롯 개별 추가 (강사용)"""
    data             = request.get_json()
    trainer_id       = data.get("trainer_id")
    slot_datetime    = data.get("slot_datetime")
    duration_minutes = int(data.get("duration_minutes", 60))
    err = _check_trainer_session(trainer_id)
    if err: return err
    if not slot_datetime:
        return jsonify({"error": "slot_datetime 필요"}), 400

    db = get_db()
    existing = db.execute(
        "SELECT id FROM availabilities WHERE trainer_id=? AND slot_datetime=?",
        (trainer_id, slot_datetime),
    ).fetchone()
    if existing:
        db.close()
        return jsonify({"error": "이미 동일한 시간대 슬롯이 존재합니다."}), 409

    new_id = str(uuid.uuid4())
    db.execute(
        """INSERT INTO availabilities (id, trainer_id, slot_datetime, status, duration_minutes)
           VALUES (?, ?, ?, 'available', ?)""",
        (new_id, trainer_id, slot_datetime, duration_minutes),
    )
    db.commit()
    row = db.execute("SELECT * FROM availabilities WHERE id=?", (new_id,)).fetchone()
    db.close()
    return jsonify(dict(row)), 201


@app.route("/api/slots/delete/<slot_id>", methods=["DELETE"])
def delete_slot(slot_id):
    """슬롯 개별 삭제 (예약된 슬롯은 삭제 불가)"""
    err = _slot_belongs_to_session(slot_id)
    if err: return err
    db = get_db()
    slot = db.execute("SELECT * FROM availabilities WHERE id=?", (slot_id,)).fetchone()
    if not slot:
        db.close()
        return jsonify({"error": "슬롯을 찾을 수 없습니다."}), 404
    if slot["status"] == "reserved":
        db.close()
        return jsonify({"error": "예약이 확정된 슬롯은 삭제할 수 없습니다. 예약 취소를 먼저 진행하세요."}), 400
    
    # 취소 후 다시 열린(available) 슬롯을 삭제할 때, 
    # 과거 취소된 예약 기록이 이 슬롯을 참조하고 있으면 FK 제약 조건 에러가 발생함.
    # 따라서 삭제 전 참조를 NULL로 변경해 줌.
    db.execute("UPDATE reservations SET availability_id = NULL WHERE availability_id = ?", (slot_id,))
    
    db.execute("DELETE FROM availabilities WHERE id=?", (slot_id,))
    db.commit()
    db.close()
    return jsonify({"message": "슬롯이 삭제되었습니다."})


# ══════════════════════════════════════════════════════════════════════
# API — MEMBERS
# ══════════════════════════════════════════════════════════════════════

@app.route("/api/members/<trainer_id>")
def get_members(trainer_id):
    err = _check_trainer_session(trainer_id)
    if err: return err
    db = get_db()
    rows = db.execute(
        "SELECT * FROM members WHERE trainer_id = ? ORDER BY name",
        (trainer_id,),
    ).fetchall()
    db.close()
    # 전화번호 마스킹
    result = []
    for r in rows:
        m = dict(r)
        p = m.get("phone", "")
        m["phone_masked"] = p[:3] + "-****-" + p[-4:] if p and len(p) >= 7 else p
        result.append(m)
    return jsonify(result)


@app.route("/api/members", methods=["POST"])
def create_member():
    data = request.get_json()
    required = ["trainer_id", "name", "phone", "total_sessions"]
    if not all(k in data for k in required):
        return jsonify({"error": "필수 필드 누락"}), 400
    err = _check_trainer_session(data["trainer_id"])
    if err: return err

    new_id = str(uuid.uuid4())
    db = get_db()
    try:
        db.execute(
            """INSERT INTO members (id, trainer_id, name, phone, total_sessions, used_sessions)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (new_id, data["trainer_id"], data["name"], data["phone"],
             int(data["total_sessions"]), int(data.get("used_sessions", 0))),
        )
        db.commit()
    except Exception as e:
        db.close()
        msg = str(e)
        if "FOREIGN KEY" in msg:
            msg = "강사 정보가 유효하지 않습니다. 페이지를 새로고침 후 다시 시도해주세요."
        elif "UNIQUE" in msg:
            msg = "이미 동일한 전화번호로 등록된 회원이 있습니다."
        return jsonify({"error": msg}), 500

    db.close()
    return jsonify({"id": new_id, "message": "회원이 등록되었습니다."}), 201


@app.route("/api/members/<member_id>", methods=["PUT"])
def update_member(member_id):
    err = _member_belongs_to_session(member_id)
    if err: return err
    data = request.get_json()
    db = get_db()
    member = db.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    if not member:
        db.close()
        return jsonify({"error": "회원을 찾을 수 없습니다."}), 404

    name           = data.get("name",           member["name"])
    phone          = data.get("phone",          member["phone"])
    total_sessions = data.get("total_sessions", member["total_sessions"])
    used_sessions  = data.get("used_sessions",  member["used_sessions"])

    # used_sessions는 total_sessions를 초과할 수 없음
    used_sessions = max(0, min(int(used_sessions), int(total_sessions)))

    db.execute(
        """UPDATE members SET name=?, phone=?, total_sessions=?, used_sessions=?
           WHERE id=?""",
        (name, phone, int(total_sessions), used_sessions, member_id),
    )
    db.commit()
    row = db.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    db.close()
    return jsonify(dict(row))


@app.route("/api/members/<member_id>", methods=["DELETE"])
def delete_member(member_id):
    err = _member_belongs_to_session(member_id)
    if err: return err
    db = get_db()
    db.execute("DELETE FROM reservations WHERE member_id = ?", (member_id,))
    db.execute("DELETE FROM session_adjustments WHERE member_id = ?", (member_id,))
    db.execute("DELETE FROM members WHERE id = ?", (member_id,))
    db.commit()
    db.close()
    return jsonify({"message": "삭제되었습니다."})


@app.route("/api/members/<member_id>/adjust", methods=["POST"])
def adjust_session(member_id):
    """세션 횟수 수동 조정 (강사용)"""
    err = _member_belongs_to_session(member_id)
    if err: return err
    data   = request.get_json()
    delta  = int(data.get("delta", 0))
    reason = (data.get("reason") or "").strip() or None
    trainer_id = session["trainer_id"]

    if delta not in (1, -1):
        return jsonify({"error": "delta는 +1 또는 -1만 가능합니다."}), 400

    db = get_db()
    member = db.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    if not member:
        db.close()
        return jsonify({"error": "회원을 찾을 수 없습니다."}), 404

    new_used = max(0, min(member["total_sessions"], member["used_sessions"] + delta))
    db.execute(
        "UPDATE members SET used_sessions = ? WHERE id = ?",
        (new_used, member_id),
    )
    # 조정 내역 기록
    db.execute(
        """INSERT INTO session_adjustments (id, member_id, trainer_id, delta, reason)
           VALUES (?, ?, ?, ?, ?)""",
        (str(uuid.uuid4()), member_id, trainer_id or member["trainer_id"], delta, reason),
    )
    db.commit()
    updated = db.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    db.close()
    return jsonify(dict(updated))


@app.route("/api/members/<member_id>/adjustments")
def get_adjustments(member_id):
    """세션 조정 내역 조회 (최근 10건)"""
    err = _member_belongs_to_session(member_id)
    if err: return err
    db = get_db()
    rows = db.execute(
        """SELECT * FROM session_adjustments
           WHERE member_id = ?
           ORDER BY created_at DESC LIMIT 10""",
        (member_id,),
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


# ══════════════════════════════════════════════════════════════════════
# API — AUTH (회원 전화번호 인증)
# ══════════════════════════════════════════════════════════════════════

@app.route("/api/auth/verify", methods=["POST"])
def verify_member():
    """
    이름 + 전화번호로 회원 조회 (PIN 없는 간편 인증)
    성공 시 회원 정보 반환 → 프론트가 localStorage에 저장
    """
    data       = request.get_json()
    trainer_id = data.get("trainer_id")
    name       = data.get("name", "").strip()
    phone      = data.get("phone", "").strip()

    if not all([trainer_id, name, phone]):
        return jsonify({"error": "이름과 전화번호를 모두 입력해주세요."}), 400

    db = get_db()
    member = db.execute(
        "SELECT * FROM members WHERE trainer_id=? AND name=? AND phone=?",
        (trainer_id, name, phone),
    ).fetchone()
    db.close()

    if not member:
        return jsonify({"error": "일치하는 회원 정보를 찾을 수 없습니다.\n강사에게 문의해주세요."}), 404
    # 전화번호는 클라이언트로 보내지 않음
    m = dict(member)
    m.pop("phone", None)
    return jsonify(m)


# ══════════════════════════════════════════════════════════════════════
# API — RESERVATIONS
# ══════════════════════════════════════════════════════════════════════

@app.route("/api/reservations/<trainer_id>")
def get_reservations(trainer_id):
    err = _check_trainer_session(trainer_id)
    if err: return err
    db = get_db()
    rows = db.execute(
        """SELECT r.*, m.name as member_name
           FROM reservations r
           JOIN members m ON r.member_id = m.id
           WHERE r.trainer_id = ?
           ORDER BY r.slot_datetime""",
        (trainer_id,),
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/reservations/member/<member_id>")
def get_member_reservations(member_id):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM reservations WHERE member_id = ? ORDER BY slot_datetime",
        (member_id,),
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/reservations", methods=["POST"])
def create_reservation():
    """
    슬롯 예약:
      1. availability 상태를 'reserved'로 변경
      2. reservation 레코드 생성
      3. 회원 used_sessions += 1
    """
    data             = request.get_json()
    trainer_id       = data.get("trainer_id")
    member_id        = data.get("member_id")
    availability_id  = data.get("availability_id")

    if not all([trainer_id, member_id, availability_id]):
        return jsonify({"error": "필수 필드 누락"}), 400

    db = get_db()

    # 슬롯 확인
    slot = db.execute(
        "SELECT * FROM availabilities WHERE id = ? AND trainer_id = ?",
        (availability_id, trainer_id),
    ).fetchone()
    if not slot:
        db.close()
        return jsonify({"error": "슬롯을 찾을 수 없습니다."}), 404
    if slot["status"] != "available":
        db.close()
        return jsonify({"error": "이미 예약된 슬롯입니다."}), 409

    # 회원 확인 & 잔여 횟수 체크
    member = db.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    if not member:
        db.close()
        return jsonify({"error": "회원 정보를 찾을 수 없습니다."}), 404
    remaining = member["total_sessions"] - member["used_sessions"]
    if remaining <= 0:
        db.close()
        return jsonify({"error": "잔여 세션이 없습니다. 강사에게 문의하세요."}), 400

    # 중복 예약 확인
    dup = db.execute(
        "SELECT id FROM reservations WHERE member_id=? AND slot_datetime=? AND status='active'",
        (member_id, slot["slot_datetime"]),
    ).fetchone()
    if dup:
        db.close()
        return jsonify({"error": "이미 해당 시간에 예약이 있습니다."}), 409

    # 트랜잭션
    new_id = str(uuid.uuid4())
    db.execute(
        "UPDATE availabilities SET status='reserved' WHERE id=?",
        (availability_id,),
    )
    db.execute(
        """INSERT INTO reservations
           (id, trainer_id, member_id, availability_id, slot_datetime, status)
           VALUES (?, ?, ?, ?, ?, 'active')""",
        (new_id, trainer_id, member_id, availability_id, slot["slot_datetime"]),
    )
    db.execute(
        "UPDATE members SET used_sessions = used_sessions + 1 WHERE id = ?",
        (member_id,),
    )
    db.commit()

    # 최신 회원 정보 반환
    updated_member = db.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    db.close()

    return jsonify({
        "reservation_id": new_id,
        "slot_datetime":  slot["slot_datetime"],
        "member":         dict(updated_member),
        "message":        "예약이 완료되었습니다!",
    }), 201


@app.route("/api/reservations/<reservation_id>", methods=["DELETE"])
def cancel_reservation(reservation_id):
    """
    예약 취소:
      1. reservation status → 'cancelled'
      2. cancelled_by ('trainer'|'member') + cancel_reason 저장
      3. availability 처리 (reopen 여부)
      4. member used_sessions -= 1
    Query param : reopen=true|false (default: true)
    JSON body   : { cancelled_by, cancel_reason }
    """
    reopen = request.args.get('reopen', 'true').lower() != 'false'
    body   = request.get_json(silent=True) or {}
    cancelled_by  = body.get('cancelled_by', 'member')   # 'trainer' | 'member'
    cancel_reason = (body.get('cancel_reason') or '').strip() or None

    db = get_db()
    res = db.execute(
        "SELECT * FROM reservations WHERE id = ?", (reservation_id,)
    ).fetchone()
    if not res:
        db.close()
        return jsonify({"error": "예약을 찾을 수 없습니다."}), 404
    if res["status"] == "cancelled":
        db.close()
        return jsonify({"error": "이미 취소된 예약입니다."}), 400
    # 강사 취소인 경우 세션 확인
    if cancelled_by == "trainer":
        err = _check_trainer_session(res["trainer_id"])
        if err:
            db.close()
            return err

    db.execute(
        """UPDATE reservations
           SET status='cancelled', cancelled_by=?, cancel_reason=?
           WHERE id=?""",
        (cancelled_by, cancel_reason, reservation_id),
    )
    if res["availability_id"]:
        if reopen:
            db.execute(
                "UPDATE availabilities SET status='available' WHERE id=?",
                (res["availability_id"],),
            )
        else:
            # 슬롯 완전히 닫음 — 삭제해 비활성 처리
            db.execute(
                "DELETE FROM availabilities WHERE id=?",
                (res["availability_id"],),
            )
    db.execute(
        "UPDATE members SET used_sessions = MAX(0, used_sessions - 1) WHERE id=?",
        (res["member_id"],),
    )
    db.commit()

    updated_member = db.execute(
        "SELECT * FROM members WHERE id = ?", (res["member_id"],)
    ).fetchone()
    db.close()

    return jsonify({
        "message":      "예약이 취소되었습니다.",
        "member":       dict(updated_member),
        "reopened":     reopen,
        "cancelled_by": cancelled_by,
        "cancel_reason": cancel_reason,
    })




# ══════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════
# MASTER (ADMIN) ROUTES
# ══════════════════════════════════════════════════════════════════════

def master_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_master"):
            return redirect(url_for("master_login"))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/master")
def master_index():
    if session.get("is_master"):
        return redirect(url_for("master_dashboard"))
    return redirect(url_for("master_login"))

@app.route("/master/login", methods=["GET", "POST"])
def master_login():
    if request.method == "GET":
        return render_template("admin/login.html")
    
    data = request.get_json(silent=True) or {}
    password = data.get("password")
    
    if password == MASTER_PASSWORD:
        session.clear()
        session["is_master"] = True
        return jsonify({"redirect": url_for("master_dashboard")})
    
    return jsonify({"error": "비밀번호가 일치하지 않습니다."}), 401

@app.route("/master/logout")
def master_logout():
    session.clear()
    return redirect(url_for("master_login"))

@app.route("/master/dashboard")
@master_required
def master_dashboard():
    db = get_db()
    # 통계
    total_trainers = db.execute("SELECT COUNT(*) as c FROM trainers").fetchone()["c"]
    total_members = db.execute("SELECT COUNT(*) as c FROM members").fetchone()["c"]
    total_reservations = db.execute("SELECT COUNT(*) as c FROM reservations").fetchone()["c"]
    
    # 강사 리스트 (회원수, 예약수 포함)
    trainers = db.execute("""
        SELECT t.*, 
               (SELECT COUNT(*) FROM members m WHERE m.trainer_id = t.id) as member_count,
               (SELECT COUNT(*) FROM reservations r WHERE r.trainer_id = t.id) as reservation_count
        FROM trainers t
        ORDER BY t.name ASC
    """).fetchall()
    
    db.close()
    
    stats = {
        "total_trainers": total_trainers,
        "total_members": total_members,
        "total_reservations": total_reservations
    }
    
    return render_template("admin/dashboard.html", stats=stats, trainers=[dict(t) for t in trainers])

@app.route("/api/master/trainers/<trainer_id>", methods=["DELETE"])
@master_required
def master_delete_trainer(trainer_id):
    db = get_db()
    
    # 해당 강사의 회원 ID들
    members = db.execute("SELECT id FROM members WHERE trainer_id = ?", (trainer_id,)).fetchall()
    member_ids = [m["id"] for m in members]
    
    if member_ids:
        placeholders = ",".join(["?"] * len(member_ids))
        if len(member_ids) == 1:
            db.execute("DELETE FROM session_adjustments WHERE member_id = ?", (member_ids[0],))
        else:
            db.execute(f"DELETE FROM session_adjustments WHERE member_id IN ({placeholders})", member_ids)
        
    db.execute("DELETE FROM reservations WHERE trainer_id = ?", (trainer_id,))
    db.execute("DELETE FROM availabilities WHERE trainer_id = ?", (trainer_id,))
    db.execute("DELETE FROM members WHERE trainer_id = ?", (trainer_id,))
    db.execute("DELETE FROM trainers WHERE id = ?", (trainer_id,))
    
    db.commit()
    db.close()
    
    return jsonify({"message": "강사 및 관련 데이터가 모두 삭제되었습니다."})


if __name__ == "__main__":
    import sys, io
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    init_db()
    print("=" * 50)
    print("  TimePlease Server Started")
    print("=" * 50)

@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    return f"<pre>{traceback.format_exc()}</pre>", 500
    print("  Trainer Dashboard : http://localhost:5000/")
    print("  Member Booking    : http://localhost:5000/r/trainer_kim")
    print("=" * 50)
    app.run(debug=True, port=5000)
