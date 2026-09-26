import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import timezone

import pytest
from sqlalchemy import DateTime, create_engine, event, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import set_committed_value

from models import Base


def _restore_utc(target, *_):
    """
    SQLite는 저장할 때 시간대 정보를 버려서, DateTime(timezone=True) 칸을 다시 읽으면 시간대 없는 시각이 된다.
    실제 DB(Postgres timestamptz)처럼 UTC 시간대를 붙여 돌려준다 - 그래야 코드의 datetime.now(timezone.utc)와 계산할 수 있다.
    """
    for attr in inspect(target).mapper.column_attrs:
        column = attr.columns[0]
        if not (isinstance(column.type, DateTime) and column.type.timezone):
            continue
        value = target.__dict__.get(attr.key)
        if value is not None and value.tzinfo is None:
            set_committed_value(target, attr.key, value.replace(tzinfo=timezone.utc))


event.listen(Base, "load", _restore_utc, propagate=True)
event.listen(Base, "refresh", _restore_utc, propagate=True)


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
