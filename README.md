# 수업콕 🗓️
**1인 강사/프리랜서 전용 초경량 예약 관리 시스템**

> 강사는 슬롯을 열고, 회원은 링크 하나로 콕콕 예약. 앱 설치·회원가입 완전 Zero.

---

## 디렉토리 구조

```
timeplease/
├── app.py              # Flask 앱 진입점 + 모든 API 라우트
├── database.py         # SQLite 초기화 & 연결 헬퍼
├── seed_data.py        # 목 데이터 삽입 스크립트
├── requirements.txt    # 의존성 (Flask만)
├── README.md
└── templates/
    ├── trainer/
    │   └── dashboard.html   # 강사 대시보드
    └── member/
        └── booking.html     # 회원 예약 페이지
```

---

## 빠른 시작

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 목 데이터 삽입

```bash
python seed_data.py
```

삽입 내용:
| 항목 | 값 |
|------|-----|
| 강사 | Kim |
| 예약 슬러그 | `trainer_kim` |
| 회원 | 어푸어푸 |
| 전화번호 | `010-1234-5678` |
| 전체 회차 | 10회 |
| 사용 회차 | 3회 |
| 예약 가능 슬롯 | 5개 |

### 3. 서버 실행

```bash
python app.py
```

### 4. 브라우저에서 확인

| 역할 | URL |
|------|-----|
| 강사 대시보드 | http://localhost:5000/ |
| 회원 예약 페이지 | http://localhost:5000/r/trainer_kim |

---

## 주요 API 목록

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| GET | `/api/slots/<trainer_id>` | 슬롯 목록 조회 |
| POST | `/api/slots/toggle` | 슬롯 활성/비활성 토글 |
| GET | `/api/members/<trainer_id>` | 회원 목록 조회 |
| POST | `/api/members` | 회원 등록 |
| PUT | `/api/members/<id>` | 회원 정보/횟수 수정 |
| DELETE | `/api/members/<id>` | 회원 삭제 |
| POST | `/api/auth/verify` | 전화번호 간편 인증 |
| POST | `/api/reservations` | 예약 생성 |
| DELETE | `/api/reservations/<id>` | 예약 취소 |
| GET | `/api/reservations/<trainer_id>` | 강사 예약 현황 |
| GET | `/api/reservations/member/<member_id>` | 회원별 예약 내역 |

---

## 회원 예약 플로우

```
1. 강사가 링크 공유  →  /r/trainer_kim
2. 회원: 이름 + 전화번호 입력
3. 서버에서 일치하는 회원 확인
4. 성공 → 세션 잔여 횟수 카드 표시
5. 원하는 슬롯 클릭 → 즉시 예약
6. used_sessions++ / 슬롯 status → 'reserved'
```

---

## 목 데이터 초기화 (재시드)

```bash
python seed_data.py   # 기존 데이터 삭제 후 재삽입
```

---

## 기술 스택

- **Backend**: Python 3.10+ / Flask 3.x / SQLite3
- **Frontend**: HTML5 / Tailwind CSS (CDN) / Vanilla JavaScript
- **DB**: SQLite (단일 파일 `timeplease.db`)
