"""
화면·이메일 언어 저장을 위한 마이그레이션:
- users.locale  ("en" | "ko", null이면 영어로 취급)
"""
import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./youtube_ab_test.db")
engine = create_engine(DATABASE_URL)

COLUMNS = [
    ("users", "locale", "VARCHAR"),
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
                print(f"SQLite: {table}.{column} 컬럼 추가 완료")
        else:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {coltype}"))
            print(f"Postgres: {table}.{column} 컬럼 추가 완료 (이미 있었다면 변화 없음)")

print("마이그레이션 종료.")
