import os
import logging
import uuid
import shutil
import asyncio
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import httpx
import urllib.parse
import certifi
from PIL import Image

import jwt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import init_db, get_db, SessionLocal
from scheduler import AVSchedulerEngine
from models import User, Channel, Video, ABTest, Variation, TestStatus, MetricLog, PlanType
from schemas import ABTestCreate, ABTestResponse
from env_utils import is_dev_environment
from metrics_utils import compute_variation_vph
from storage import is_cloud_storage_configured, upload_thumbnail_to_cloud
from test_policy import BASIC_MIN_SWAP_INTERVAL_MINUTES, MAX_CONCURRENT_TESTS_PER_CHANNEL

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 에러 모니터링(Sentry): SENTRY_DSN이 설정된 경우에만 활성화된다. 미설정 시(로컬 개발 등)에는
# 조용히 건너뛰므로 별도 계정 없이도 앱이 정상 동작한다. 배포 환경에서 예외가 발생하면
# 이 세션에서처럼 로그를 직접 뒤지지 않아도 Sentry 대시보드/알림으로 바로 확인할 수 있다.
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.getenv("SENTRY_ENVIRONMENT", "development" if is_dev_environment() else "production"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        send_default_pii=False,
    )
    logger.info("✅ Sentry 에러 모니터링 활성화됨")
else:
    logger.info("ℹ️ SENTRY_DSN 미설정 - 에러 모니터링 비활성화 (로컬 개발에서는 정상)")

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("🚨 JWT_SECRET 환경 변수가 설정되지 않았습니다. .env 파일을 확인하세요.")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = int(os.getenv("JWT_EXPIRE_DAYS", "7"))
security = HTTPBearer()

def create_access_token(user_id: int, channel_id: int) -> str:
    """
    한 계정(User)이 여러 YouTube 채널을 연동할 수 있으므로, 토큰에는 유저 신원(sub)과
    "지금 보고 있는 채널"(channel_id)을 함께 담는다. 채널 전환은 /api/channels/{id}/switch로
    channel_id만 다른 새 토큰을 재발급받는 방식으로 처리한다 (기존 엔드포인트들은 변경 없이
    Depends(get_current_channel)만으로 계속 동작함).
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "channel_id": channel_id,
        "iat": now,
        "exp": now + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def _decode_token(request: Request) -> dict:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth.split(" ")[1]
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    payload = _decode_token(request)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def get_current_channel(request: Request, db: Session = Depends(get_db)) -> Channel:
    payload = _decode_token(request)
    user_id = payload.get("sub")
    channel_id = payload.get("channel_id")
    if not user_id or not channel_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    channel = db.query(Channel).filter(Channel.id == int(channel_id)).first()
    if not channel:
        raise HTTPException(status_code=401, detail="Channel not found")
    # 토큰의 유저와 채널 소유자가 일치하는지 재확인 (다른 유저의 채널을 흉내내지 못하도록)
    if channel.user_id != int(user_id):
        raise HTTPException(status_code=401, detail="Channel does not belong to this account")
    return channel

def get_current_admin(request: Request, db: Session = Depends(get_db)) -> User:
    """
    운영자 전용 엔드포인트 인증. 별도 role 컬럼/가입 절차 없이, 환경 변수 ADMIN_EMAILS(쉼표 구분)에
    등록된 이메일의 계정만 관리자로 취급한다. 미설정 시(빈 값) 어떤 계정도 관리자가 될 수 없다 -
    운영자 화면을 배포할 계획이 없다면 그냥 비워두면 안전하게 전부 차단된다.
    """
    payload = _decode_token(request)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    admin_emails = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
    if not user.email or user.email.lower() not in admin_emails:
        raise HTTPException(status_code=403, detail="관리자 권한이 없습니다.")
    return user


GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
REDIRECT_URI = f"{BACKEND_URL}/api/auth/callback"

# CORS 허용 도메인 목록 (환경 변수로 관리 - 배포 시 실제 도메인으로 변경)
ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")]

scheduler_engine = AVSchedulerEngine(db_session_maker=SessionLocal)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("📦 데이터베이스 테이블 초기화 중...")
    init_db()
    logger.info("⏰ 자동화 스케줄러 엔진 시작...")
    scheduler_engine.start()
    yield
    logger.info("🛑 서버 및 스케줄러 종료...")

app = FastAPI(title="CreatorFlow API", lifespan=lifespan)

# 💥 Render 배포 시 uploads 폴더가 없으면 에러가 나므로, 마운트하기 전에 미리 폴더를 강제로 생성해 줍니다.
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "CreatorFlow API 서버 정상 동작 중 🚀"}

@app.get("/api/status")
def get_system_status(db: Session = Depends(get_db)):
    user_count = db.query(User).count()
    channel_count = db.query(Channel).count()
    return {"status": "online", "users": user_count, "channels": channel_count}

# --- Google OAuth 로직 ---
@app.get("/api/auth/login")
def login_via_google(state: str | None = None):
    """
    구글 로그인 페이지로 리다이렉트합니다.
    이미 로그인된 상태에서 "채널 추가"로 들어온 경우, 프론트가 현재 JWT를 state로 실어 보낸다.
    구글은 이 state 값을 그대로 콜백에 돌려주므로, 콜백에서 그걸로 "새로 로그인하는 구글
    계정과 무관하게 지금 로그인된 유저 소유로 채널을 붙여야 한다"는 걸 알 수 있다.
    """
    scope = "openid email profile https://www.googleapis.com/auth/youtube.force-ssl https://www.googleapis.com/auth/yt-analytics.readonly"
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"response_type=code&"
        f"scope={scope}&"
        f"access_type=offline&"
        f"prompt=consent"
    )
    if state:
        auth_url += f"&state={urllib.parse.quote(state)}"
    return RedirectResponse(auth_url)

@app.get("/api/auth/callback")
async def google_auth_callback(code: str, state: str | None = None, db: Session = Depends(get_db)):
    """구글 로그인 성공 시 되돌아오는 콜백 엔드포인트"""

    # "채널 추가" 흐름이면 state에 기존 로그인 유저의 JWT가 실려있다. 유효하면 이 흐름 전체에서
    # 그 유저를 채널 소유자로 쓴다 (아래 4번 DB 저장 로직에서 google_user_id 기준 조회/생성을 건너뜀).
    linking_user_id: int | None = None
    if state:
        try:
            state_payload = jwt.decode(state, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            linking_user_id = int(state_payload["sub"])
        except (jwt.PyJWTError, KeyError, ValueError):
            logger.warning("채널 추가 시 전달된 state 토큰이 유효하지 않습니다. 신규 로그인으로 처리합니다.")
    
    # 1. code를 이용해 access_token과 refresh_token 발급
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    
    # 로컬 환경(localhost)에서는 SSL 검증을 끄고, 실제 라이브 배포 환경에서는 보안을 위해 검증을 켭니다.
    is_local = "localhost" in BACKEND_URL or "127.0.0.1" in BACKEND_URL
    ssl_verify = False if is_local else True
    
    async with httpx.AsyncClient(verify=ssl_verify) as client:
        token_res = await client.post(token_url, data=token_data)
        if token_res.status_code != 200:
            logger.error(f"Token error: {token_res.text}")
            raise HTTPException(status_code=400, detail="토큰 발급 실패")
            
        token_json = token_res.json()
        access_token = token_json.get("access_token")
        refresh_token = token_json.get("refresh_token") # 최초 로그인 시에만 발급됨
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # 2. 사용자 정보 가져오기
        userinfo_res = await client.get("https://www.googleapis.com/oauth2/v2/userinfo", headers=headers)
        if userinfo_res.status_code != 200:
            logger.error(f"Userinfo error: {userinfo_res.text}")
            raise HTTPException(status_code=400, detail="구글 사용자 정보 조회 실패")
        userinfo_json = userinfo_res.json()
        # 🔒 유저 식별은 반드시 이 "id"(OIDC sub와 동일, 계정당 고유·불변) 기준으로 해야 한다.
        # email은 브랜드 계정(유튜브 채널) 컨텍스트로 로그인하면 실제 이메일 대신
        # "...@pages.plusgoogle.com" 같은 그 채널 전용 가짜 이메일을 돌려주는 경우가 있어서,
        # email로 유저를 찾으면 같은 사람인데도 채널 연동할 때마다 별개 계정이 새로 생겨버린다.
        google_user_id = userinfo_json.get("id")
        email = userinfo_json.get("email")
        if not google_user_id:
            logger.error("구글 userinfo 응답에 id(sub)가 없습니다.")
            raise HTTPException(status_code=400, detail="구글 계정 정보를 가져오지 못했습니다.")
        if not email:
            # User.email은 nullable=False라서, None인 채로 User를 만들면 여기서 잡지 않으면
            # DB commit 시점에 처리되지 않은 IntegrityError로 500이 난다.
            logger.error("구글 userinfo 응답에 email이 없습니다.")
            raise HTTPException(status_code=400, detail="구글 계정에서 이메일 정보를 가져오지 못했습니다.")

        # 3. 유튜브 채널 정보 가져오기
        yt_res = await client.get("https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true", headers=headers)
        if yt_res.status_code == 403:
            # 스코프 동의 화면에서 YouTube 권한이 빠지면(브랜드 계정 로그인 시 간소화된 동의 화면이
            # 뜨는 경우 등) 여기서 403이 난다. "채널이 없다"는 것과는 다른 원인이라 별도 에러로 구분한다.
            logger.error(f"YouTube API 403: {yt_res.text}")
            return RedirectResponse(f"{FRONTEND_URL}/login?error=youtube_permission_denied")
        yt_data = yt_res.json()

        if not yt_data.get("items"):
            return RedirectResponse(f"{FRONTEND_URL}/?error=no_youtube_channel")

        channel_id = yt_data["items"][0]["id"]
        channel_title = yt_data["items"][0]["snippet"]["title"]

    # 4. DB 저장 로직 (유저 및 채널)
    user = db.query(User).filter(User.id == linking_user_id).first() if linking_user_id else None
    if not user:
        # "채널 추가"로 들어온 게 아니거나 state가 무효했던 경우의 일반 로그인 흐름.
        user = db.query(User).filter(User.google_user_id == google_user_id).first()
        if not user:
            # 레거시 브릿지: google_user_id 도입 이전에 이메일만으로 저장된 유저가 있으면 그쪽에
            # 채워 넣는다 (단, 이번 로그인의 email이 진짜 자기 이메일일 때만 유효한 매칭이므로 그대로 사용).
            user = db.query(User).filter(User.email == email).first()
            if user and not user.google_user_id:
                user.google_user_id = google_user_id
        if not user:
            user = User(google_user_id=google_user_id, email=email)
            db.add(user)
            db.commit()
            db.refresh(user)

    channel = db.query(Channel).filter(Channel.youtube_channel_id == channel_id).first()
    if not channel:
        # 신규 채널 연동 - 요금제별 채널 개수 상한 확인 (멀티채널 관리는 PRO/AGENCY 차별화 포인트)
        from test_policy import max_channels_for_plan
        plan_value = user.plan.value if hasattr(user.plan, "value") else str(user.plan)
        existing_count = db.query(Channel).filter(Channel.user_id == user.id).count()
        if existing_count >= max_channels_for_plan(plan_value):
            logger.info(f"채널 연동 한도 초과: {email} (plan={plan_value}, 기존 {existing_count}개)")
            return RedirectResponse(f"{FRONTEND_URL}/dashboard?error=channel_limit_reached")
        channel = Channel(user_id=user.id, youtube_channel_id=channel_id, channel_title=channel_title)

    if refresh_token:
        channel.oauth_refresh_token = refresh_token
        channel.needs_reconnect = False  # 재동의로 새 refresh_token을 받았으므로 재연동 필요 상태 해제

    channel.channel_title = channel_title
    db.add(channel)
    db.commit()
    db.refresh(channel)

    logger.info(f"유튜브 채널 연동 성공: {channel_title} ({email})")

    # 5. 프론트엔드로 리다이렉트 (JWT 발급 포함)
    # 채널의 실제 소유 유저(channel.user_id) 기준으로 토큰을 발급한다. 이미 다른 계정이
    # 먼저 연동해둔 채널이라면(예: 같은 브랜드 계정을 여러 사람이 관리하는 경우) 방금
    # 로그인한 이메일이 아니라 원래 소유자 명의로 세션이 유지되어야 계정 탈취를 방지할 수 있다.
    token = create_access_token(channel.user_id, channel.id)
    channel_title_encoded = urllib.parse.quote(channel_title)
    return RedirectResponse(f"{FRONTEND_URL}/dashboard?token={token}&connected_channel={channel_title_encoded}")

@app.post("/api/auth/logout")
def logout_user():
    """유저 단순 세션 로그아웃 엔드포인트 (채널 연동 토큰은 유지되어 백그라운드 A/B 테스트가 계속 실행됩니다)"""
    return {"message": "성공적으로 로그아웃되었습니다."}

@app.post("/api/auth/disconnect-channel")
def disconnect_channel(db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """YouTube 채널 연동 해제 엔드포인트 (현재 활성화된 채널의 OAuth 리프레시 토큰만 삭제)"""
    channel.oauth_refresh_token = None
    channel.needs_reconnect = False  # 완전히 연동 해제된 상태이므로 "재연동 필요" 배너와는 구분
    db.commit()
    return {"message": "YouTube 채널 연동이 완벽하게 해제되었습니다."}

@app.get("/api/channels")
def list_channels(db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """현재 계정에 연동된 모든 YouTube 채널 목록 (멀티채널 전환 UI용). '활성' 채널은 지금 토큰이 가리키는 채널."""
    from test_policy import max_channels_for_plan

    channels = db.query(Channel).filter(Channel.user_id == channel.user_id).order_by(Channel.id).all()
    user = channel.user
    plan_value = user.plan.value if user and hasattr(user.plan, "value") else "BASIC"

    return {
        "channels": [
            {
                "id": c.id,
                "channel_title": c.channel_title,
                "youtube_channel_id": c.youtube_channel_id,
                "needs_reconnect": c.needs_reconnect,
                "is_active": c.id == channel.id,
            }
            for c in channels
        ],
        "max_channels": max_channels_for_plan(plan_value),
    }

@app.post("/api/channels/{target_channel_id}/switch")
def switch_channel(target_channel_id: int, db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """대시보드에서 다른 연동 채널로 전환 - 같은 계정 소유 채널일 때만 새 토큰을 발급한다."""
    target = db.query(Channel).filter(Channel.id == target_channel_id).first()
    if not target or target.user_id != channel.user_id:
        raise HTTPException(status_code=404, detail="채널을 찾을 수 없거나 이 계정 소유가 아닙니다.")

    token = create_access_token(target.user_id, target.id)
    return {"token": token, "channel_title": target.channel_title}

@app.post("/api/settings/test-email")
def send_test_email(db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """이메일 알림 테스트 전송 엔드포인트"""
    target_email = channel.user.email if channel and channel.user else "godlove3854@gmail.com"
    
    from email_service import send_test_completion_email
    result = send_test_completion_email(
        user_email=target_email,
        video_title="사진 속 우리 (비하인드 스페셜)",
        winner_name="Variation B (네온 자막 강조 썸네일)",
        views_gained=458
    )
    if result["simulated"]:
        message = f"SMTP가 설정되어 있지 않아 시뮬레이션 모드로 처리했습니다. '{target_email}'로 실제 이메일은 발송되지 않았습니다."
    elif result["sent"]:
        message = f"'{target_email}' 주소로 A/B 테스트 승자 확정 이메일 알림이 실제로 발송되었습니다!"
    else:
        message = "이메일 발송에 실패했습니다."

    return {
        "status": "ok" if result["sent"] else "error",
        "simulated": result["simulated"],
        "target_email": target_email,
        "message": message
    }

async def _apply_first_variant_in_background(test_id: int):
    """
    테스트 생성 직후 첫 후보를 YouTube에 적용하는 작업을 백그라운드에서 수행한다.
    실제 YouTube API 호출(조회수 조회, 썸네일/제목 교체)은 몇 초씩 걸릴 수 있어서,
    요청-응답 안에서 기다리게 하면 프론트엔드 버튼이 응답 없이 멈춘 것처럼 보인다.
    응답은 테스트/변인 생성 즉시 반환하고, 실제 유튜브 적용은 뒤에서 이어서 처리한다.
    (요청 스코프의 DB 세션은 응답 전송 직후 닫히므로, 별도의 새 세션을 새로 연다.)
    """
    session = SessionLocal()
    try:
        test = session.query(ABTest).filter(ABTest.id == test_id).first()
        if not test:
            return
        await scheduler_engine._do_swap(test, session)
        session.commit()
    except Exception as e:
        logger.error(f"최초 변인 적용 실패 (백그라운드, 테스트 ID {test_id}): {e}")
        session.rollback()
    finally:
        session.close()

# --- A/B Test 로직 ---
@app.post("/api/tests", response_model=ABTestResponse)
async def create_ab_test(test_data: ABTestCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """프론트엔드에서 보낸 설정값으로 새로운 A/B 테스트를 DB에 생성합니다."""

    # 🔒 같은 채널이 동시에 두 번 테스트 생성을 요청하면(더블클릭, 두 탭 등) 아래 개수 제한 체크가
    # 둘 다 통과한 뒤 동시에 커밋되어 제한을 우회할 수 있다(TOCTOU). 채널 행에 락을 걸어 같은 채널의
    # 요청은 이 트랜잭션이 끝날 때까지 직렬화되도록 한다 (Postgres에서만 유효; SQLite는 no-op).
    db.query(Channel).filter(Channel.id == channel.id).with_for_update().first()

    # 요금제 무관 시스템 보호용 상한 (YouTube API 쿼터는 프로젝트 전체 공유 자원이므로,
    # PRO/AGENCY라도 한 채널이 무제한으로 테스트를 돌리지 못하도록 절대 상한을 둔다)
    concurrent_count = db.query(ABTest).join(Video).filter(
        Video.channel_id == channel.id,
        ABTest.status == TestStatus.RUNNING,
        ABTest.is_deleted == False
    ).count()
    if concurrent_count >= MAX_CONCURRENT_TESTS_PER_CHANNEL:
        raise HTTPException(status_code=403, detail=f"채널당 동시 진행 가능한 테스트는 최대 {MAX_CONCURRENT_TESTS_PER_CHANNEL}개입니다.")

    # [요금제 제한 로직 추가]
    user = channel.user
    if user:
        if user.plan == PlanType.BASIC:
            # 1. 동시 테스트 개수 제한
            active_count = db.query(ABTest).join(Video).filter(
                Video.channel_id == channel.id, 
                ABTest.status == TestStatus.RUNNING,
                ABTest.is_deleted == False
            ).count()
            if active_count >= 1:
                raise HTTPException(status_code=403, detail="BASIC 요금제는 동시에 1개의 테스트만 진행할 수 있습니다. PRO 요금제로 업그레이드해주세요.")
                
            # 2. 월간 누적 테스트 생성 횟수 제한 (4회)
            now = datetime.utcnow()
            first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            monthly_count = db.query(ABTest).join(Video).filter(
                Video.channel_id == channel.id,
                ABTest.start_time >= first_day_of_month
            ).count()
            if monthly_count >= 4:
                raise HTTPException(status_code=403, detail="이번 달 무료 테스트 제공량(4회)을 모두 소진하셨습니다. 계속해서 테스트를 진행하시려면 PRO 요금제로 업그레이드해주세요.")
                
            # 3. 교체 주기 제한 (짧은 주기는 시간대 편향이 커지고 Analytics 데이터와도 안 맞으므로 PRO 전용)
            if test_data.swap_interval_minutes < BASIC_MIN_SWAP_INTERVAL_MINUTES:
                raise HTTPException(status_code=403, detail=f"BASIC 요금제는 최소 {BASIC_MIN_SWAP_INTERVAL_MINUTES // 60}시간 주기로만 테스트할 수 있습니다. 더 짧은 교체 주기는 PRO 요금제 전용입니다.")
                
            # 3. 썸네일 후보 개수 제한 (A, B, C 까지만 허용 = 최대 3개)
            if len(test_data.variations) > 3:
                raise HTTPException(status_code=403, detail="BASIC 요금제는 원본 포함 최대 3개의 후보까지만 테스트할 수 있습니다. 무제한 추가를 원하시면 PRO로 업그레이드해주세요.")

    # 🔒 채널 범위로 조회해야 한다: Video.youtube_video_id는 DB 전역에서 unique라서, 채널 필터 없이
    # 조회하면 이미 다른 사용자가 등록해둔 영상 ID를 그대로 가져와 그 사람 채널에 테스트를 붙이게 된다
    # (그 뒤 스케줄러가 원래 소유자의 OAuth 토큰으로 실제 YouTube 썸네일/제목을 바꿔버리는 사고로 이어짐).
    video = db.query(Video).filter(Video.youtube_video_id == test_data.youtube_video_id, Video.channel_id == channel.id).first()
    if not video:
        # 이 youtube_video_id가 이미 "다른" 채널 소유로 등록되어 있다면(정상적으로는 발생하지 않아야 하지만,
        # 방어적으로) 그 영상을 가로채 테스트를 붙이지 못하도록 명확히 거부한다.
        existing_elsewhere = db.query(Video).filter(Video.youtube_video_id == test_data.youtube_video_id).first()
        if existing_elsewhere:
            raise HTTPException(status_code=403, detail="이 영상은 다른 채널에 이미 연동되어 있어 테스트를 생성할 수 없습니다.")
        video = Video(channel_id=channel.id, youtube_video_id=test_data.youtube_video_id)
        db.add(video)
        db.commit()
        db.refresh(video)
        
    new_test = ABTest(
        video_id=video.id,
        swap_interval_minutes=test_data.swap_interval_minutes,
        status=TestStatus.RUNNING,
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow() + timedelta(hours=test_data.duration_hours)
    )
    db.add(new_test)
    db.commit()
    db.refresh(new_test)
    
    for var_data in test_data.variations:
        new_var = Variation(
            ab_test_id=new_test.id,
            name=var_data.name,
            title_text=var_data.title_text,
            is_control=var_data.is_control,
            thumbnail_image_url=var_data.thumbnail_image_url
        )
        db.add(new_var)
    db.commit()

    # 생성 직후 첫 후보를 바로 YouTube에 적용 (교체 주기만큼 기다리지 않음).
    # 응답을 막지 않도록 백그라운드로 돌린다 - 프론트 버튼이 몇 초씩 멈춰 보이는 것 방지.
    background_tasks.add_task(_apply_first_variant_in_background, new_test.id)

    return ABTestResponse(id=new_test.id, status=new_test.status.name, message="A/B 테스트가 성공적으로 시작되었습니다!")

@app.post("/api/tests/{test_id}/stop")
async def stop_ab_test(test_id: int, db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """진행 중인 A/B 테스트를 수동으로 중단하고 승자를 확정합니다."""
    test = db.query(ABTest).join(Video).filter(ABTest.id == test_id, Video.channel_id == channel.id).first()
    if not test:
        raise HTTPException(status_code=404, detail="테스트를 찾을 수 없거나 권한이 없습니다.")
    if test.is_deleted or test.status != TestStatus.RUNNING:
        raise HTTPException(status_code=400, detail="진행 중인 테스트만 중단할 수 있습니다.")

    test.status = TestStatus.COMPLETED
    test.end_time = datetime.utcnow()
    
    # 승자 확정 (노출 시간당 조회수 = VPH가 가장 높은 변인. 오래 노출된 변인이 유리해지는 것을 방지)
    all_vars = db.query(Variation).filter(Variation.ab_test_id == test.id).all()
    winner_var = None
    max_vph = -1.0
    for var in all_vars:
        vph = compute_variation_vph(var)
        if vph > max_vph:
            max_vph = vph
            winner_var = var

    if winner_var:
        winner_var.is_winner = True
        winner_total_views = sum(l.views_gained for l in winner_var.metric_logs)
        channel = test.video.channel
        if channel and channel.user and channel.user.email:
            from email_service import send_test_completion_email
            # 🔒 smtplib는 동기(blocking) 호출이라, async 핸들러 안에서 그대로 부르면 SMTP 서버가
            # 응답 없을 때 이벤트 루프 전체(다른 요청 포함)가 멈춘다. 별도 스레드로 실행한다.
            await asyncio.to_thread(
                send_test_completion_email,
                user_email=channel.user.email,
                video_title=winner_var.title_text or test.video.youtube_video_id,
                winner_name=winner_var.name,
                views_gained=winner_total_views
            )
        
    db.commit()
    return {"message": "테스트가 성공적으로 중단 및 종료되었습니다.", "winner": winner_var.name if winner_var else None}

@app.post("/api/tests/{test_id}/swap")
async def force_swap_ab_test(test_id: int, db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """테스트 대기 시간을 기다리지 않고 즉시 다음 변인(썸네일/제목)으로 교체 테스트를 실행합니다."""
    test = db.query(ABTest).join(Video).filter(ABTest.id == test_id, Video.channel_id == channel.id).first()
    if not test:
        raise HTTPException(status_code=404, detail="테스트를 찾을 수 없거나 권한이 없습니다.")
    if test.status != TestStatus.RUNNING:
        raise HTTPException(status_code=400, detail="진행 중인 테스트만 교체 가능합니다.")
        
    await scheduler_engine._do_swap(test, db)
    db.commit()

    if channel.needs_reconnect:
        raise HTTPException(status_code=409, detail="YouTube 연동이 만료되었습니다. 다시 로그인해 채널을 재연동해주세요.")
    if test.swap_failed:
        raise HTTPException(status_code=502, detail="YouTube에 썸네일/제목 반영에 실패했습니다. 잠시 후 스케줄러가 자동으로 재시도합니다.")

    current_var = db.query(Variation).filter(Variation.id == test.current_variation_id).first()
    return {"message": "즉시 썸네일/제목 교체가 수행되었습니다.", "current_variation": current_var.name if current_var else None}

@app.delete("/api/tests/{test_id}")
async def delete_ab_test(test_id: int, db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """테스트를 완전히 취소하고 삭제합니다. 유튜브 썸네일과 제목을 원본(Candidate A)으로 돌려놓습니다."""
    test = db.query(ABTest).filter(ABTest.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="테스트를 찾을 수 없습니다.")
        
    if test.video.channel_id != channel.id:
        raise HTTPException(status_code=403, detail="권한이 없습니다.")

    # 재시도/더블클릭으로 같은 삭제 요청이 두 번 오면, 이미 삭제된 테스트에 대해 원본 복구
    # YouTube 요청(썸네일 다운로드+업로드, 제목 변경)을 매번 다시 실행하는 걸 막는다.
    if test.is_deleted:
        return {"message": "테스트가 취소되고 원본으로 복구되었습니다."}

    # 원본(Candidate A) 찾기
    original_var = db.query(Variation).filter(Variation.ab_test_id == test.id, Variation.is_control == True).first()
    
    if original_var:
        from youtube_api import update_youtube_thumbnail, update_youtube_title
        
        # 원본 썸네일 복구
        if original_var.thumbnail_image_url:
            if original_var.thumbnail_image_url.startswith("http"):
                file_path = os.path.join("uploads", f"temp_original_{test.id}.jpg")
                try:
                    import httpx
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(original_var.thumbnail_image_url)
                        if resp.status_code == 200:
                            with open(file_path, "wb") as f:
                                f.write(resp.content)
                            await update_youtube_thumbnail(test.video.youtube_video_id, file_path, channel.oauth_refresh_token)
                        else:
                            logger.error(f"원본 썸네일 복구 실패 (상태 코드: {resp.status_code})")
                except Exception as e:
                    logger.error(f"원본 썸네일 복구 다운로드 에러: {e}")
            else:
                try:
                    file_name = original_var.thumbnail_image_url.split('/')[-1]
                    file_path = os.path.join("uploads", file_name)
                    if os.path.exists(file_path):
                        await update_youtube_thumbnail(test.video.youtube_video_id, file_path, channel.oauth_refresh_token)
                except Exception as e:
                    logger.error(f"원본 썸네일 로컬 복구 실패: {e}")
                    
        # 제목 복구
        if original_var.title_text:
            try:
                await update_youtube_title(test.video.youtube_video_id, original_var.title_text, channel.oauth_refresh_token)
            except Exception as e:
                logger.error(f"원본 제목 복구 실패: {e}")

    # 논리적 삭제 (Soft Delete) - 쿼터 유지를 위해 DB에 남김
    test.is_deleted = True
    test.status = TestStatus.STOPPED
    db.commit()
    return {"message": "테스트가 취소되고 원본으로 복구되었습니다."}

@app.post("/api/upload")
async def upload_thumbnail(
    file: UploadFile = File(...),
    channel: Channel = Depends(get_current_channel)  # 🔒 로그인 필수
):
    """프론트엔드에서 업로드한 썸네일 이미지를 서버에 저장하고 URL을 반환합니다."""
    
    # 🔒 허용 확장자 화이트리스트 (실행 파일 업로드 차단)
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB 제한
    
    file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"허용되지 않는 파일 형식입니다. 허용: {', '.join(ALLOWED_EXTENSIONS)}")
    
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="허용되지 않는 Content-Type입니다. 이미지 파일만 업로드 가능합니다.")

    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    # 파일 크기 검증 및 저장
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(upload_dir, unique_filename)
    
    total_size = 0
    with open(file_path, "wb+") as file_object:
        while chunk := await file.read(1024 * 64):  # 64KB 청크 단위로 읽기
            total_size += len(chunk)
            if total_size > MAX_FILE_SIZE:
                file_object.close()
                os.remove(file_path)
                raise HTTPException(status_code=400, detail="파일 크기가 10MB를 초과합니다.")
            file_object.write(chunk)

    # 🔒 확장자/Content-Type은 클라이언트가 조작 가능하므로, 실제 파일 바이트(매직 시그니처)로
    # 진짜 이미지가 맞는지 재검증한다 (예: .jpg로 위장한 실행 파일 차단)
    ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
    try:
        with Image.open(file_path) as img:
            img.verify()
            detected_format = img.format
    except Exception:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail="파일 내용이 올바른 이미지 형식이 아닙니다.")

    if detected_format not in ALLOWED_IMAGE_FORMATS:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"허용되지 않는 이미지 형식입니다 (감지된 형식: {detected_format}).")

    public_url = await publish_local_image(file_path, unique_filename)
    return {"url": public_url, "filename": unique_filename}

@app.post("/api/generate-thumbnail")
async def generate_thumbnail_endpoint(
    file: UploadFile = File(...),
    headline: str = Form(...),
    channel: Channel = Depends(get_current_channel)
):
    """
    베이스 이미지 + 헤드라인 문구로 유튜브 규격(16:9) 썸네일을 자동 생성합니다.
    외부 AI 이미지 생성 API를 쓰지 않고, PIL로 크롭/보정하고 텍스트를 얹는 방식이라
    호출당 비용이 발생하지 않습니다. ml_scorer의 명도/대비/채도 이상값에 맞춰 자동 보정합니다.
    """
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
    MAX_FILE_SIZE = 10 * 1024 * 1024

    file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"허용되지 않는 파일 형식입니다. 허용: {', '.join(ALLOWED_EXTENSIONS)}")

    headline = headline.strip()
    if not headline:
        raise HTTPException(status_code=400, detail="문구를 입력해주세요.")
    if len(headline) > 60:
        raise HTTPException(status_code=400, detail="문구는 60자 이내로 입력해주세요.")

    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)

    temp_input_path = os.path.join(upload_dir, f"temp_{uuid.uuid4()}{file_ext}")
    total_size = 0
    with open(temp_input_path, "wb") as f:
        while chunk := await file.read(1024 * 64):
            total_size += len(chunk)
            if total_size > MAX_FILE_SIZE:
                f.close()
                os.remove(temp_input_path)
                raise HTTPException(status_code=400, detail="파일 크기가 10MB를 초과합니다.")
            f.write(chunk)

    try:
        with Image.open(temp_input_path) as img:
            img.verify()
    except Exception:
        os.remove(temp_input_path)
        raise HTTPException(status_code=400, detail="파일 내용이 올바른 이미지 형식이 아닙니다.")

    output_filename = f"{uuid.uuid4()}.jpg"
    output_path = os.path.join(upload_dir, output_filename)

    try:
        from thumbnail_generator import generate_thumbnail
        generate_thumbnail(temp_input_path, headline, output_path)
    except Exception as e:
        logger.error(f"썸네일 자동 생성 실패: {e}")
        raise HTTPException(status_code=500, detail="썸네일 생성 중 오류가 발생했습니다.")
    finally:
        if os.path.exists(temp_input_path):
            os.remove(temp_input_path)

    analysis = analyze_thumbnail(output_path)
    public_url = await publish_local_image(output_path, output_filename)

    return {"url": public_url, "filename": output_filename, "analysis": analysis}

from ml_scorer import analyze_thumbnail

async def publish_local_image(file_path: str, filename: str) -> str:
    """
    🌩️ 클라우드 스토리지(Cloudinary)가 설정되어 있으면 영구 URL로 업로드합니다.
    (로컬 디스크는 Render 재배포 시 초기화되므로, 프로덕션에서는 클라우드 URL을 DB에 저장해야 합니다.
     로컬 사본은 /api/analyze-thumbnail의 즉시 분석과 스케줄러의 로컬 캐시 용도로 그대로 유지합니다.)
    """
    if not is_cloud_storage_configured():
        return f"{BACKEND_URL}/uploads/{filename}"

    with open(file_path, "rb") as f:
        file_bytes = f.read()
    cloud_url = await upload_thumbnail_to_cloud(file_bytes, filename)
    if cloud_url:
        return cloud_url

    logger.error("Cloudinary 업로드 실패 - 로컬 URL로 폴백합니다 (재배포 시 유실될 수 있음)")
    return f"{BACKEND_URL}/uploads/{filename}"

@app.post("/api/analyze-thumbnail")
async def api_analyze_thumbnail(request: Request, channel: Channel = Depends(get_current_channel)):
    """업로드된 썸네일 이미지의 파일명을 받아 머신러닝(휴리스틱) 예측 점수를 반환합니다."""
    data = await request.json()
    filename = data.get("filename")
    if not filename:
        raise HTTPException(status_code=400, detail="파일명이 제공되지 않았습니다.")

    # 🔒 filename은 클라이언트가 보내는 값이므로, os.path.basename으로 경로 조작(../ 등)을 제거하고
    # uploads/ 디렉터리 밖의 임의 파일을 열람하지 못하도록 막는다.
    safe_filename = os.path.basename(filename)
    if not safe_filename or safe_filename != filename:
        raise HTTPException(status_code=400, detail="올바르지 않은 파일명입니다.")

    file_path = os.path.join("uploads", safe_filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    result = analyze_thumbnail(file_path)
    return result

from youtube_api import get_recent_videos, TokenRevokedError

@app.get("/api/videos")
async def get_channel_videos(db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """현재 연동된 채널의 최근 유튜브 영상 목록을 가져옵니다."""
    if not channel or not channel.oauth_refresh_token:
        raise HTTPException(status_code=400, detail="연동된 채널이나 인증 토큰이 없습니다.")

    try:
        videos = await get_recent_videos(channel.oauth_refresh_token)
    except TokenRevokedError:
        channel.needs_reconnect = True
        db.commit()
        raise HTTPException(status_code=409, detail="YouTube 연동이 만료되었습니다. 다시 로그인해 채널을 재연동해주세요.")

    return {"videos": videos}

from sqlalchemy import func

@app.get("/api/analytics")
def get_analytics(db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """채널의 전체 통계 데이터를 반환합니다."""
    if not channel:
        return {"total_tests": 0, "total_views_gained": 0, "active_tests": 0, "trend": [], "best_variation": None}
        
    tests = db.query(ABTest).join(Video).filter(Video.channel_id == channel.id).all()
    total_tests = len(tests)
    active_tests = sum(1 for t in tests if t.status == TestStatus.RUNNING)
    
    # 누적 추가 획득 조회수 (모든 MetricLog의 views_gained 합계)
    total_views_query = (
        db.query(func.sum(MetricLog.views_gained))
        .join(Variation)
        .join(ABTest, Variation.ab_test_id == ABTest.id)
        .join(Video, ABTest.video_id == Video.id)
        .filter(Video.channel_id == channel.id)
        .scalar()
    )
    total_views_gained = total_views_query or 0

    # 일별 누적 추가 조회수 추이 (Analytics 페이지 트렌드 차트용). SQLite/Postgres 양쪽에서
    # 동일하게 동작하도록 DB 윈도우 함수 대신 Python에서 날짜별로 합산 후 누적합을 계산한다.
    logs = (
        db.query(MetricLog.measured_at, MetricLog.views_gained)
        .join(Variation)
        .join(ABTest, Variation.ab_test_id == ABTest.id)
        .join(Video, ABTest.video_id == Video.id)
        .filter(Video.channel_id == channel.id)
        .all()
    )
    daily_totals: dict = {}
    for measured_at, views_gained in logs:
        day = measured_at.date()
        daily_totals[day] = daily_totals.get(day, 0) + (views_gained or 0)

    trend = []
    cumulative = 0
    for day in sorted(daily_totals.keys()):
        cumulative += daily_totals[day]
        trend.append({"day": day.strftime("%m-%d"), "views_gained": cumulative})

    # 지금까지 가장 성과 좋았던 썸네일 후보 (전체 채널 기준, variation 단위 누적 조회수 최고)
    best = (
        db.query(Variation, func.sum(MetricLog.views_gained).label("total_views"))
        .join(MetricLog, MetricLog.variation_id == Variation.id)
        .join(ABTest, Variation.ab_test_id == ABTest.id)
        .join(Video, ABTest.video_id == Video.id)
        .filter(Video.channel_id == channel.id)
        .group_by(Variation.id)
        .order_by(func.sum(MetricLog.views_gained).desc())
        .first()
    )
    best_variation = None
    if best:
        var, total_views = best
        best_variation = {
            "name": var.name,
            "title_text": var.title_text,
            "thumbnail_image_url": var.thumbnail_image_url,
            "total_views_gained": int(total_views or 0),
            "youtube_video_id": var.ab_test.video.youtube_video_id,
        }

    return {
        "total_tests": total_tests,
        "active_tests": active_tests,
        "total_views_gained": total_views_gained,
        "trend": trend,
        "best_variation": best_variation,
    }

@app.get("/api/history")
def get_history(db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """채널의 완료된 테스트 기록을 반환합니다."""
    if not channel:
        return {"tests": []}
        
    tests = db.query(ABTest).join(Video).filter(Video.channel_id == channel.id, ABTest.status == TestStatus.COMPLETED, ABTest.is_deleted == False).order_by(ABTest.id.desc()).all()
    
    result = []
    for test in tests:
        vars_data = []
        for var in test.variations:
            vars_data.append({
                "id": var.id,
                "name": var.name,
                "title_text": var.title_text,
                "thumbnail_image_url": var.thumbnail_image_url,
                "is_winner": var.is_winner,
                "total_views_gained": sum(log.views_gained for log in var.metric_logs),
                "vph": round(compute_variation_vph(var), 2)
            })

        result.append({
            "test_id": test.id,
            "video_id": test.video.youtube_video_id,
            "status": test.status.name,
            "swap_interval": test.swap_interval_minutes,
            "end_time": test.end_time.isoformat() if test.end_time else None,
            "variations": vars_data,
            # 참고용 실측 CTR (YouTube Analytics, 영상 전체 단위, 최대 하루 지연). 승자 판정에는 쓰이지 않음.
            "daily_analytics": sorted(
                [{"date": d.date, "impressions": d.impressions, "impressions_ctr": d.impressions_ctr} for d in test.video.daily_analytics],
                key=lambda d: d["date"]
            )
        })

    return {"tests": result}

@app.get("/api/tests")
def get_ab_tests(db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """프론트엔드 대시보드에 표시할 테스트 진행 상황과 차트 데이터를 반환합니다."""
    tests = db.query(ABTest).join(Video).filter(Video.channel_id == channel.id, ABTest.is_deleted == False).order_by(ABTest.id.desc()).all()
    
    result = []
    for test in tests:
        vars_data = []
        for var in test.variations:
            chart_data = []
            # 측정된 로그들로 차트 데이터 구성
            for log in var.metric_logs:
                chart_data.append({
                    "day": log.measured_at.strftime("%m-%d %H:%M"),
                    "views_gained": log.views_gained
                })

            # 로그가 아직 없는 경우 (첫 측정 전) 실제 시작 시각을 표시
            if not chart_data:
                start_label = test.start_time.strftime("%m-%d %H:%M") if test.start_time else "방금 전"
                chart_data = [
                    {"day": start_label, "views_gained": 0}
                ]
                
            vars_data.append({
                "id": var.id,
                "name": var.name,
                "title_text": var.title_text,
                "thumbnail_image_url": var.thumbnail_image_url,
                "is_winner": var.is_winner,
                "chart_data": chart_data,
                "total_views_gained": sum(log.views_gained for log in var.metric_logs),
                "vph": round(compute_variation_vph(var), 2)
            })
            
        result.append({
            "test_id": test.id,
            "video_id": test.video.youtube_video_id,
            "status": test.status.name,
            "swap_interval": test.swap_interval_minutes,
            "start_time": test.start_time.isoformat() if test.start_time else None,
            "end_time": test.end_time.isoformat() if test.end_time else None,
            "variations": vars_data,
            # 참고용 실측 CTR (YouTube Analytics, 영상 전체 단위, 최대 하루 지연). 승자 판정에는 쓰이지 않음.
            "daily_analytics": sorted(
                [{"date": d.date, "impressions": d.impressions, "impressions_ctr": d.impressions_ctr} for d in test.video.daily_analytics],
                key=lambda d: d["date"]
            )
        })

    return {"tests": result}

# --- 결제 시스템 (Lemon Squeezy Integration) ---
import hmac
import hashlib

@app.get("/api/user/me")
def get_current_user_profile(channel: Channel = Depends(get_current_channel)):
    """현재 연동된 채널 소유 유저 정보 및 구독 요금제를 반환합니다."""
    user = channel.user
    if not user:
        return {"email": None, "plan": "BASIC", "is_pro": False, "channel_title": None, "needs_reconnect": channel.needs_reconnect, "is_admin": False}

    admin_emails = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
    is_admin = bool(user.email) and user.email.lower() in admin_emails

    return {
        "email": user.email,
        "plan": user.plan.value if hasattr(user.plan, "value") else str(user.plan),
        "is_pro": user.plan == PlanType.PRO or user.plan == PlanType.AGENCY,
        "channel_title": channel.channel_title,
        "needs_reconnect": channel.needs_reconnect,
        "is_admin": is_admin
    }

@app.post("/api/checkout/create-session")
def create_checkout_session(plan: str = "PRO", db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """Lemon Squeezy 결제 체크아웃 URL 생성 엔드포인트"""
    user_email = channel.user.email if channel and channel.user else "creator@example.com"
    
    checkout_base_url = os.getenv("LEMON_SQUEEZY_CHECKOUT_URL")
    if checkout_base_url:
        checkout_url = f"{checkout_base_url}?checkout[custom][user_email]={user_email}"
    else:
        checkout_url = f"https://lemonsqueezy.com/checkout/mock?plan={plan}&user_email={user_email}"
        
    return {
        "checkout_url": checkout_url,
        "user_email": user_email,
        "plan": plan
    }

@app.post("/api/checkout/upgrade-test")
def upgrade_user_plan_test(db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """결제 테스트용: 현재 유저의 요금제를 즉시 PRO로 업그레이드합니다. 프로덕션에서는 비활성."""
    if not is_dev_environment():
        raise HTTPException(status_code=403, detail="Test upgrade is disabled in production.")
    user = channel.user
    if not user:
            user = User(email="test@creatorflow.io", plan=PlanType.BASIC)
            db.add(user)
            db.commit()
            db.refresh(user)
    else:
        user = channel.user
        
    user.plan = PlanType.PRO
    db.commit()
    return {"status": "success", "message": "PRO 요금제로 성공적으로 업그레이드되었습니다!", "plan": user.plan.value}

@app.post("/api/webhooks/lemonsqueezy")
async def lemonsqueezy_webhook(request: Request, db: Session = Depends(get_db)):
    """Lemon Squeezy 결제 성공/구독 변경 시 호출되는 웹훅"""
    secret = os.getenv("LEMON_SQUEEZY_WEBHOOK_SECRET", "")
    if not secret and not is_dev_environment():
        logger.error("[Lemon Squeezy Webhook] 🚨 LEMON_SQUEEZY_WEBHOOK_SECRET 미설정 - 프로덕션에서 웹훅 거부")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    signature = request.headers.get("x-signature")
    payload = await request.body()
    if secret:
        if not signature:
            raise HTTPException(status_code=401, detail="Missing signature")
        computed_signature = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, computed_signature):
            logger.warning("Invalid Lemon Squeezy webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

    data = await request.json()
    event_name = data.get("meta", {}).get("event_name")
    
    custom_data = data.get("meta", {}).get("custom_data", {})
    user_email = custom_data.get("user_email")

    if not user_email:
        user_email = data.get("data", {}).get("attributes", {}).get("user_email")

    if event_name in ["subscription_created", "order_created", "subscription_updated"]:
        if user_email:
            user = db.query(User).filter(User.email == user_email).first()
            if user:
                user.plan = PlanType.PRO
                db.commit()
                logger.info(f"🎉 웹훅 수신: 유저 {user_email}의 요금제가 PRO로 성공적으로 업그레이드 되었습니다.")

    # 구독 취소/만료/결제 실패 시 다운그레이드 처리가 없으면, 유저가 결제를 끊어도 PRO가 영구히
    # 유지되는 매출 손실 버그가 된다 (webhook.py의 Paddle 핸들러와 동일한 패턴으로 맞춘다).
    elif event_name in ["subscription_cancelled", "subscription_expired", "subscription_paused"]:
        if user_email:
            user = db.query(User).filter(User.email == user_email).first()
            if user:
                user.plan = PlanType.BASIC
                db.commit()
                logger.info(f"⬇️ 웹훅 수신: 유저 {user_email}의 요금제가 BASIC으로 다운그레이드 되었습니다. (사유: {event_name})")

    return {"status": "ok"}

# --- Paddle 결제 연동 ---
PADDLE_PRICE_ID = os.getenv("PADDLE_PRICE_ID", "pri_01m1psq971t3sy5h2xq0venhsg")

@app.get("/api/checkout/paddle-config")
def get_paddle_checkout_config(db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """Paddle 결제 체크아웃용 Price ID 및 유저 이메일 반환"""
    user_email = channel.user.email if channel and channel.user else "creator@example.com"

    return {
        "price_id": PADDLE_PRICE_ID,
        "user_email": user_email,
        "environment": os.getenv("PADDLE_ENVIRONMENT", "sandbox")
    }

@app.get("/api/billing/portal")
async def get_paddle_billing_portal(channel: Channel = Depends(get_current_channel)):
    """
    Paddle 고객 포털(Customer Portal) 딥링크를 발급합니다. 구독 취소, 결제수단 변경,
    결제 내역/영수증 조회를 전부 Paddle이 호스팅하는 화면에서 처리하므로 직접 구현하지 않는다.
    구독을 시작한 적 없는 유저(paddle_customer_id 없음)는 발급할 포털이 없다.
    """
    user = channel.user
    if not user or not user.paddle_customer_id:
        raise HTTPException(status_code=404, detail="결제 내역이 없습니다. PRO 결제를 진행한 뒤 다시 시도해주세요.")

    api_key = os.getenv("PADDLE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="결제 시스템이 설정되지 않았습니다.")

    is_sandbox = os.getenv("PADDLE_ENVIRONMENT", "sandbox") == "sandbox"
    base_url = "https://sandbox-api.paddle.com" if is_sandbox else "https://api.paddle.com"

    body = {}
    if user.paddle_subscription_id:
        body["subscription_ids"] = [user.paddle_subscription_id]

    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{base_url}/customers/{user.paddle_customer_id}/portal-sessions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=body,
        )

    if res.status_code != 201:
        logger.error(f"[Paddle Portal] 세션 생성 실패 ({res.status_code}): {res.text}")
        raise HTTPException(status_code=502, detail="결제 관리 페이지를 여는 데 실패했습니다. 잠시 후 다시 시도해주세요.")

    urls = res.json().get("data", {}).get("urls", {})
    portal_url = urls.get("general", {}).get("overview")
    if not portal_url:
        raise HTTPException(status_code=502, detail="결제 관리 페이지 링크를 가져오지 못했습니다.")

    return {"url": portal_url}

# /api/webhooks/paddle 엔드포인트는 webhook.py 라우터에서 처리합니다 (서명 검증 포함)

# --- 관리자 대시보드 (ADMIN_EMAILS 환경 변수에 등록된 계정만 접근 가능) ---

@app.get("/api/admin/stats")
def get_admin_stats(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    """가입자/채널/테스트 현황과 오늘의 YouTube API 쿼터 사용량을 한눈에 보여준다."""
    from quota_guard import get_today_usage, DAILY_QUOTA_LIMIT

    total_users = db.query(User).count()
    pro_users = db.query(User).filter(User.plan == PlanType.PRO).count()
    basic_users = db.query(User).filter(User.plan == PlanType.BASIC).count()

    total_channels = db.query(Channel).count()
    channels_needing_reconnect = db.query(Channel).filter(Channel.needs_reconnect == True).count()

    active_tests = db.query(ABTest).filter(ABTest.status == TestStatus.RUNNING, ABTest.is_deleted == False).count()
    completed_tests = db.query(ABTest).filter(ABTest.status == TestStatus.COMPLETED).count()
    total_tests = db.query(ABTest).count()

    return {
        "users": {"total": total_users, "pro": pro_users, "basic": basic_users},
        "channels": {"total": total_channels, "needs_reconnect": channels_needing_reconnect},
        "tests": {"active": active_tests, "completed": completed_tests, "total": total_tests},
        "quota_today": {"used": get_today_usage(db), "limit": DAILY_QUOTA_LIMIT},
    }

@app.get("/api/admin/users")
def get_admin_users(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    """가입자 목록 (이메일, 플랜, 가입일, 연동 채널 수)."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "plan": u.plan.name,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "channel_count": len(u.channels),
                "has_paddle_customer": bool(u.paddle_customer_id),
            }
            for u in users
        ]
    }

@app.get("/api/admin/tests")
def get_admin_tests(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    """현재 진행 중(RUNNING)인 모든 테스트 목록 - 재연동 필요/스왑 실패 등 이상 유무를 한눈에 확인용."""
    tests = (
        db.query(ABTest)
        .join(Video)
        .filter(ABTest.status == TestStatus.RUNNING, ABTest.is_deleted == False)
        .order_by(ABTest.start_time.desc())
        .all()
    )
    return {
        "tests": [
            {
                "test_id": t.id,
                "youtube_video_id": t.video.youtube_video_id,
                "channel_title": t.video.channel.channel_title,
                "user_email": t.video.channel.user.email if t.video.channel.user else None,
                "needs_reconnect": t.video.channel.needs_reconnect,
                "swap_count": t.swap_count,
                "swap_failed": t.swap_failed,
                "start_time": t.start_time.isoformat() if t.start_time else None,
            }
            for t in tests
        ]
    }

from webhook import router as webhook_router
app.include_router(webhook_router)
