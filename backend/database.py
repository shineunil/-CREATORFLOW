import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models import Base
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

# 환경 변수에서 DATABASE_URL을 가져오거나, 없으면 기본 SQLite 사용 (Supabase 연동 준비)
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./youtube_ab_test.db")

# PostgreSQL일 경우 check_same_thread 옵션 제거
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Neon 등 서버리스 Postgres는 유휴 커넥션을 서버 쪽에서 먼저 끊는 경우가 있어,
    # pool_pre_ping으로 사용 전 헬스체크 후 죽은 커넥션이면 투명하게 재연결한다.
    engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True, pool_recycle=300)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """모든 데이터베이스 테이블을 생성하고, datetime 컬럼을 TIMESTAMPTZ로 마이그레이션합니다."""
    Base.metadata.create_all(bind=engine)
    if not SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
        _migrate_timestamps_to_utc()
        _migrate_add_columns()


def _migrate_timestamps_to_utc():
    """TIMESTAMP WITHOUT TIME ZONE 컬럼을 TIMESTAMPTZ로 일괄 변환합니다. (서버 시작 시 자동 실행, 멱등)"""
    migrations = [
        "ALTER TABLE users ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'",
        "ALTER TABLE ab_tests ALTER COLUMN last_swapped_at TYPE TIMESTAMPTZ USING last_swapped_at AT TIME ZONE 'UTC'",
        "ALTER TABLE ab_tests ALTER COLUMN start_time TYPE TIMESTAMPTZ USING start_time AT TIME ZONE 'UTC'",
        "ALTER TABLE ab_tests ALTER COLUMN end_time TYPE TIMESTAMPTZ USING end_time AT TIME ZONE 'UTC'",
        "ALTER TABLE ab_tests ALTER COLUMN exposure_start_at TYPE TIMESTAMPTZ USING exposure_start_at AT TIME ZONE 'UTC'",
        "ALTER TABLE metrics_logs ALTER COLUMN measured_at TYPE TIMESTAMPTZ USING measured_at AT TIME ZONE 'UTC'",
    ]
    with engine.connect() as conn:
        for stmt in migrations:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception as e:
                conn.rollback()  # 이미 TIMESTAMPTZ면 무시하고 계속 진행
                logger.debug(f"Migration skip (probably already applied): {e}")

def _migrate_add_columns():
    """신규 컬럼을 기존 테이블에 추가합니다. (서버 시작 시 자동 실행, 멱등)"""
    migrations = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS notification_email VARCHAR",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS notification_email_verified BOOLEAN DEFAULT FALSE",
        "ALTER TABLE site_announcements ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now()",
    ]
    with engine.connect() as conn:
        for stmt in migrations:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.debug(f"Column migration skip: {e}")

def get_db():
    """요청(Request)마다 DB 세션을 생성하고 종료하는 제너레이터"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
