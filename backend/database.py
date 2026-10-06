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

# 설치된 드라이버(psycopg2)를 주소에 명시한다. "postgresql://"만 쓰면 SQLAlchemy 버전에 따라
# 다른 드라이버(psycopg 3)를 찾다가 서버가 시작하지 못한다.
for _prefix in ("postgresql://", "postgres://"):
    if SQLALCHEMY_DATABASE_URL.startswith(_prefix):
        SQLALCHEMY_DATABASE_URL = "postgresql+psycopg2://" + SQLALCHEMY_DATABASE_URL[len(_prefix):]
        break

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


_UTC_TIMESTAMP_COLUMNS = [
    ("users", "created_at"),
    ("ab_tests", "last_swapped_at"),
    ("ab_tests", "start_time"),
    ("ab_tests", "end_time"),
    ("ab_tests", "exposure_start_at"),
    ("metrics_logs", "measured_at"),
]


def _migrate_timestamps_to_utc():
    """
    아직 TIMESTAMP WITHOUT TIME ZONE인 컬럼만 TIMESTAMPTZ로 바꾼다. (서버 시작 시 자동 실행, 멱등)
    예전엔 이미 TIMESTAMPTZ인 컬럼에도 매번 다시 실행했는데, 그 변환이 오류 없이 성공해 버려서
    DB 접속 시간대가 UTC가 아니면(로컬 PostgreSQL은 Asia/Seoul) 재시작할 때마다 시각이 9시간씩 밀렸고,
    운영에서도 재시작마다 테이블을 통째로 다시 썼다.
    """
    with engine.connect() as conn:
        pending = {
            (row.table_name, row.column_name)
            for row in conn.execute(text(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND data_type = 'timestamp without time zone'"
            ))
        }
        for table, column in _UTC_TIMESTAMP_COLUMNS:
            if (table, column) not in pending:
                continue
            try:
                conn.execute(text(
                    f"ALTER TABLE {table} ALTER COLUMN {column} TYPE TIMESTAMPTZ USING {column} AT TIME ZONE 'UTC'"
                ))
                conn.commit()
                logger.info(f"Migrated {table}.{column} to TIMESTAMPTZ")
            except Exception as e:
                conn.rollback()
                logger.warning(f"Timestamp migration failed for {table}.{column}: {e}")

def _migrate_add_columns():
    """신규 컬럼을 기존 테이블에 추가합니다. (서버 시작 시 자동 실행, 멱등)"""
    migrations = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS notification_email VARCHAR",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS notification_email_verified BOOLEAN DEFAULT FALSE",
        "ALTER TABLE site_announcements ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now()",
        "ALTER TABLE channels ADD COLUMN IF NOT EXISTS thumbnail_permission VARCHAR DEFAULT 'unknown'",
        # H-2: PostgreSQL은 FK에 자동 인덱스를 생성하지 않으므로 명시적으로 추가
        "CREATE INDEX IF NOT EXISTS idx_channels_user_id   ON channels(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_videos_channel_id  ON videos(channel_id)",
        "CREATE INDEX IF NOT EXISTS idx_abtests_video_id   ON ab_tests(video_id)",
        "CREATE INDEX IF NOT EXISTS idx_variations_test_id ON variations(ab_test_id)",
        "CREATE INDEX IF NOT EXISTS idx_metriclogs_var_id  ON metrics_logs(variation_id)",
        # M-6: 이메일 알림 opt-out 컬럼
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_alerts_enabled BOOLEAN NOT NULL DEFAULT TRUE",
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
