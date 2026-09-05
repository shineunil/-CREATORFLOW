from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import User, Channel, PlanType, ABTest, Video, TestStatus

engine = create_engine("sqlite:///./youtube_ab_test.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

channel_id = 4 # The last created one

count = db.query(ABTest).join(Video).filter(Video.channel_id == channel_id, ABTest.status == TestStatus.RUNNING).count()
print("Count:", count)

tests = db.query(ABTest).join(Video).filter(Video.channel_id == channel_id).all()
for t in tests:
    print(t.id, t.status, type(t.status))

