from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Enum
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()

class PlanType(enum.Enum):
    BASIC = "BASIC"
    PRO = "PRO"
    AGENCY = "AGENCY"

class TestStatus(enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    plan = Column(Enum(PlanType), default=PlanType.BASIC)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 1:N relationship with Channels
    channels = relationship("Channel", back_populates="user", cascade="all, delete-orphan")

class Channel(Base):
    __tablename__ = 'channels'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    youtube_channel_id = Column(String, unique=True, index=True, nullable=False)
    channel_title = Column(String)
    oauth_refresh_token = Column(String, nullable=True) # Essential for background jobs

    user = relationship("User", back_populates="channels")
    videos = relationship("Video", back_populates="channel", cascade="all, delete-orphan")

class Video(Base):
    __tablename__ = 'videos'

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey('channels.id'), nullable=False)
    youtube_video_id = Column(String, unique=True, index=True, nullable=False)
    
    channel = relationship("Channel", back_populates="videos")
    ab_tests = relationship("ABTest", back_populates="video", cascade="all, delete-orphan")

class ABTest(Base):
    __tablename__ = 'ab_tests'

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey('videos.id'), nullable=False)
    status = Column(Enum(TestStatus), default=TestStatus.PENDING)
    swap_interval_minutes = Column(Integer, default=120) # e.g., swap every 2 hours
    current_variation_id = Column(Integer, ForeignKey('variations.id'), nullable=True) # Optimization/Cache
    last_swapped_at = Column(DateTime, default=datetime.utcnow) # 마지막으로 썸네일을 교체한 시간
    last_views_snapshot = Column(Integer, default=0) # 마지막 교체 시점의 총 조회수 스냅샷
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    is_deleted = Column(Boolean, default=False) # 유저가 삭제 버튼을 누른 경우 (쿼터 계산용으로 보존)

    video = relationship("Video", back_populates="ab_tests")
    variations = relationship("Variation", back_populates="ab_test", foreign_keys="[Variation.ab_test_id]", cascade="all, delete-orphan")

class Variation(Base):
    __tablename__ = 'variations'

    id = Column(Integer, primary_key=True, index=True)
    ab_test_id = Column(Integer, ForeignKey('ab_tests.id', ondelete="CASCADE"), nullable=False)
    name = Column(String) # e.g., 'Variation A'
    thumbnail_image_url = Column(String)
    title_text = Column(String)
    is_control = Column(Boolean, default=False)
    is_winner = Column(Boolean, default=False)

    ab_test = relationship("ABTest", back_populates="variations", foreign_keys=[ab_test_id])
    metric_logs = relationship("MetricLog", back_populates="variation", cascade="all, delete-orphan")

class MetricLog(Base):
    __tablename__ = 'metrics_logs'

    id = Column(Integer, primary_key=True, index=True)
    variation_id = Column(Integer, ForeignKey('variations.id', ondelete="CASCADE"), nullable=False)
    measured_at = Column(DateTime, default=datetime.utcnow, index=True)
    views_gained = Column(Integer, default=0) # Delta views during this interval

    variation = relationship("Variation", back_populates="metric_logs")
