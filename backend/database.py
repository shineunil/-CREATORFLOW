import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base
from dotenv import load_dotenv

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
    """모든 데이터베이스 테이블을 생성합니다."""
    Base.metadata.create_all(bind=engine)

def get_db():
    """요청(Request)마다 DB 세션을 생성하고 종료하는 제너레이터"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
