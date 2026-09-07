"""
최소 사이클 / 최소 표본 / 워밍업 구간 제외를 위한 1회성 마이그레이션.
ab_tests 테이블에 아래 컬럼을 추가합니다:
- swap_count       (성공적으로 반영된 스왑 횟수 - 최소 사이클 판정용)
- extension_count  (사이클/표본 부족으로 자동 연장된 횟수)
- warmup_captured  (스왑 직후 워밍업이 지나 기준선을 재캡처했는지 여부)
- exposure_start_at (워밍업 이후 "진짜" 측정 시작 시각)

로컬 SQLite는 Base.metadata.create_all()이 새 테이블만 만들고 기존 테이블에 컬럼을
추가하지 않으므로, 이 스크립트가 로컬/라이브 모두에서 안전하게(이미 있으면 건너뜀) 동작합니다.

실행 방법 (라이브 DB에 적용할 DATABASE_URL을 환경 변수로 넣고 실행):
    cd backend
    python migrate_add_test_policy_columns.py
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
    ("ab_tests", "swap_count", "INTEGER DEFAULT 0"),
    ("ab_tests", "extension_count", "INTEGER DEFAULT 0"),
    ("ab_tests", "warmup_captured", "BOOLEAN DEFAULT TRUE"),
    ("ab_tests", "exposure_start_at", "TIMESTAMP"),
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
                sqlite_coltype = coltype.replace("TIMESTAMP", "DATETIME")
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sqlite_coltype}"))
                print(f"✅ SQLite: {table}.{column} 컬럼 추가 완료")
        else:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {coltype}"))
            print(f"✅ Postgres: {table}.{column} 컬럼 추가 완료 (이미 있었다면 변화 없음)")

print("마이그레이션 종료. 기존 진행 중인 테스트는 swap_count=0으로 시작하므로,")
print("남은 기간 동안의 스왑만으로 최소 사이클 판정이 이뤄집니다 (과거 스왑은 소급 집계되지 않음).")
