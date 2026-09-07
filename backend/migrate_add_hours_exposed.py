"""
VPH 정규화를 위한 1회성 마이그레이션: metrics_logs 테이블에 hours_exposed 컬럼을 추가합니다.

로컬 SQLite는 Base.metadata.create_all()이 새 테이블만 만들고 기존 테이블에 컬럼을
추가하지 않으므로, 이 스크립트가 로컬/라이브 모두에서 안전하게(이미 있으면 건너뜀) 동작합니다.

실행 방법 (라이브 DB에 적용할 DATABASE_URL을 환경 변수로 넣고 실행):
    cd backend
    python migrate_add_hours_exposed.py
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

with engine.begin() as conn:
    if DATABASE_URL.startswith("sqlite"):
        existing_columns = conn.execute(text("PRAGMA table_info(metrics_logs)")).fetchall()
        has_column = any(row[1] == "hours_exposed" for row in existing_columns)
        if has_column:
            print("이미 hours_exposed 컬럼이 존재합니다. 건너뜁니다.")
        else:
            conn.execute(text("ALTER TABLE metrics_logs ADD COLUMN hours_exposed FLOAT DEFAULT 0"))
            print("✅ SQLite: metrics_logs.hours_exposed 컬럼 추가 완료")
    else:
        # Postgres는 9.6+부터 IF NOT EXISTS를 지원하므로 멱등(idempotent)하게 실행 가능
        conn.execute(text("ALTER TABLE metrics_logs ADD COLUMN IF NOT EXISTS hours_exposed FLOAT DEFAULT 0"))
        print("✅ Postgres: metrics_logs.hours_exposed 컬럼 추가 완료 (이미 있었다면 변화 없음)")

print("마이그레이션 종료. 이 컬럼이 없던 기존 MetricLog 행은 hours_exposed=0으로 남으며,")
print("VPH 계산 시 폴백(raw 합계)으로만 처리됩니다 — 과거 데이터를 소급 보정하지는 않습니다.")
