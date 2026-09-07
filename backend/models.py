from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Enum, Float
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()

class PlanType(enum.Enum):
    BASIC = "BASIC"
    PRO = "PRO"
    # 예약된 상태: 채널 개수 제한(test_policy.py) 등 내부 로직은 이미 준비되어 있지만,
    # 실제로 구매할 수 있는 경로(Paddle price ID, pricing 페이지 카드)가 아직 없다.
    # 가격/차별화 요소가 정해지기 전까지는 어떤 화면에서도 노출/판매하지 않는다.
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
    # Paddle 고객 포털(구독 취소/다운그레이드/결제 내역 조회)에 필요한 식별자.
    # 최초 결제(구독 생성) 웹훅을 받을 때 채워지며, 결제 이력이 없는 유저는 계속 null.
    paddle_customer_id = Column(String, nullable=True)
    paddle_subscription_id = Column(String, nullable=True)

    # 1:N relationship with Channels
    channels = relationship("Channel", back_populates="user", cascade="all, delete-orphan")

class Channel(Base):
    __tablename__ = 'channels'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    youtube_channel_id = Column(String, unique=True, index=True, nullable=False)
    channel_title = Column(String)
    oauth_refresh_token = Column(String, nullable=True) # Essential for background jobs
    needs_reconnect = Column(Boolean, default=False) # refresh_token이 만료/철회되어 유저의 재동의(재로그인)가 필요한 상태

    user = relationship("User", back_populates="channels")
    videos = relationship("Video", back_populates="channel", cascade="all, delete-orphan")

class Video(Base):
    __tablename__ = 'videos'

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey('channels.id'), nullable=False)
    youtube_video_id = Column(String, unique=True, index=True, nullable=False)
    
    channel = relationship("Channel", back_populates="videos")
    ab_tests = relationship("ABTest", back_populates="video", cascade="all, delete-orphan")
    daily_analytics = relationship("DailyAnalytics", back_populates="video", cascade="all, delete-orphan")

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
    swap_failed = Column(Boolean, default=False) # 직전 스왑(썸네일/제목 교체) 시도가 실패해 재시도 대상인지 여부
    swap_count = Column(Integer, default=0) # 지금까지 성공적으로 반영된 스왑 횟수 (최소 사이클 판정용)
    extension_count = Column(Integer, default=0) # 사이클/표본 부족으로 자동 연장된 횟수 (무한 연장 방지)
    warmup_captured = Column(Boolean, default=True) # 스왑 직후 워밍업 구간이 지나 조회수 기준선을 다시 캡처했는지 여부
    exposure_start_at = Column(DateTime, nullable=True) # 워밍업 이후 "진짜" 측정이 시작된 시각 (없으면 last_swapped_at 사용)

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
    hours_exposed = Column(Float, default=0) # 이 구간 동안 실제 노출된 시간(시간 단위) - VPH 계산용

    variation = relationship("Variation", back_populates="metric_logs")

class DailyAnalytics(Base):
    """
    YouTube Analytics API(yt-analytics.readonly)로 수집한 영상 단위 일별 실측 CTR.
    Data API의 viewCount 델타(VPH)와 달리 실제 노출(impressions) 대비 클릭률이지만,
    최대 하루 정도 지연되어 채워지고 변인(Variation) 단위가 아닌 영상 전체 단위로만 제공된다.
    승자 판정에는 쓰지 않고(VPH가 즉시 확정), 대시보드에 참고 지표로만 노출한다.
    """
    __tablename__ = 'daily_analytics'

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey('videos.id', ondelete="CASCADE"), nullable=False)
    date = Column(String, nullable=False, index=True)  # "YYYY-MM-DD" (YouTube Analytics의 day 차원 그대로 저장)
    impressions = Column(Integer, default=0)
    impressions_ctr = Column(Float, default=0)  # percentage (0~100)
    collected_at = Column(DateTime, default=datetime.utcnow)

    video = relationship("Video", back_populates="daily_analytics")

class ApiQuotaUsage(Base):
    """
    YouTube Data API v3 프로젝트 전체(모든 채널 공통)의 일일 쿼터 사용량 추적.
    쿼터는 프로젝트 단위로 공유되므로(채널별이 아님), 한 유저가 과도하게 많은 테스트를
    돌리면 전체 서비스의 API 접근이 막힐 수 있어 이를 방지하기 위한 안전장치.
    """
    __tablename__ = 'api_quota_usage'

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, unique=True, index=True, nullable=False)  # "YYYY-MM-DD" (태평양 시간 기준)
    units_used = Column(Integer, default=0)
