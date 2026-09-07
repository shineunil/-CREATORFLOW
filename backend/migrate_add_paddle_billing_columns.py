"""
Paddle 고객 포털(구독 취소/다운그레이드/결제 내역 조회) 연동을 위한 1회성 마이그레이션:
- users.paddle_customer_id      (Paddle 고객 ID, 최초 결제 웹훅 수신 시 채워짐)
- users.paddle_subscription_id  (Paddle 구독 ID, 최초 결제 웹훅 수신 시 채워짐)

로컬 SQLite는 Base.metadata.create_all()이 새 테이블만 만들고 기존 테이블에 컬럼을
추가하지 않으므로, 이 스크립트가 로컬/라이브 모두에서 안전하게(이미 있으면 건너뜀) 동작합니다.

실행 방법 (라이브 DB에 적용할 DATABASE_URL을 환경 변수로 넣고 실행):
    cd backend
    python migrate_add_paddle_billing_columns.py
"""
import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Windows 콘솔(cp949 등)에서 이모지 출력 시 UnicodeEncodeError로 죽는 것을 방지
# (print 실패가 트랜잭션 커밋 전에 발생하면 롤백될 수 있으므로 반드시 필요)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./youtube_ab_test.db")
engine = create_engine(DATABASE_URL)

COLUMNS = [
    ("users", "paddle_customer_id", "VARCHAR"),
    ("users", "paddle_subscription_id", "VARCHAR"),
]

with engine.begin() as conn:
    is_sqlite = DATABASE_URL.startswith("sqlite")
    for table, column, coltype in COLUMNS:
        if is_sqlite:
            existing_columns = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            has_column = any(row[1] == column for row in existing_columns)
            if has_column:
                print(f"이미 {table}.{column} 컬럼이 존재합니다. 건너뜁니다.")
            else:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}"))
                print(f"✅ SQLite: {table}.{column} 컬럼 추가 완료")
        else:
            # Postgres는 9.6+부터 IF NOT EXISTS를 지원하므로 멱등(idempotent)하게 실행 가능
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {coltype}"))
            print(f"✅ Postgres: {table}.{column} 컬럼 추가 완료 (이미 있었다면 변화 없음)")

print("마이그레이션 종료.")
