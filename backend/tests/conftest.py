import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base


@pytest.fixture()
def db_session():
    """
    실제 DATABASE_URL(라이브 DB일 수 있음)에는 절대 손대지 않는, 순수 인메모리 SQLite 세션.
    database.py의 실제 프로덕션 세션 설정(autoflush=False)과 반드시 일치시킨다 - 그렇지 않으면
    autoflush 차이 때문에 테스트가 통과해도 실제로는 세션 관련 버그(예: 한 요청 안에서 같은 행을
    여러 번 add()하다 UNIQUE 위반)를 못 잡는다 (실제로 한 번 이렇게 놓친 적이 있었음).
    """
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
