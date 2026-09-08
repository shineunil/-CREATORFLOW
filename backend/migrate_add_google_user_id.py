"""
유저 식별을 email 대신 구글 계정 고유 ID(google_user_id)로 하기 위한 1회성 마이그레이션:
- users.google_user_id  (구글 OAuth userinfo의 "id"/OIDC sub. 계정당 고유·불변)

email만으로 유저를 식별하면, 유튜브 브랜드 계정(채널) 컨텍스트로 로그인했을 때 구글이 실제
이메일 대신 그 채널 전용 가짜 이메일("...@pages.plusgoogle.com")을 돌려주는 경우가 있어서
같은 사람인데도 채널 연동할 때마다 별개 계정이 새로 생기는 문제가 있었다.

로컬 SQLite는 Base.metadata.create_all()이 새 테이블만 만들고 기존 테이블에 컬럼을
추가하지 않으므로, 이 스크립트가 로컬/라이브 모두에서 안전하게(이미 있으면 건너뜀) 동작합니다.

실행 방법 (라이브 DB에 적용할 DATABASE_URL을 환경 변수로 넣고 실행):
    cd backend
    python migrate_add_google_user_id.py
"""
import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Windows 콘솔(cp949 등)에서 이모지 출력 시 UnicodeEncodeError로 죽는 것을 방지
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./youtube_ab_test.db")
engine = create_engine(DATABASE_URL)

COLUMNS = [
    ("users", "google_user_id", "VARCHAR"),
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
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {coltype}"))
            print(f"✅ Postgres: {table}.{column} 컬럼 추가 완료 (이미 있었다면 변화 없음)")

    # 유니크 인덱스도 함께 생성 (모델의 unique=True와 일치시킴)
    if is_sqlite:
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_user_id ON users (google_user_id)"))
    else:
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_user_id ON users (google_user_id)"))
    print("✅ users.google_user_id 유니크 인덱스 확인/생성 완료")

print("마이그레이션 종료.")
