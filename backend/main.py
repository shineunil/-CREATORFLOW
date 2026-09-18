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
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import httpx
import urllib.parse
import certifi
from PIL import Image
import io

import jwt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import init_db, get_db, SessionLocal
from scheduler import AVSchedulerEngine
from models import User, Channel, Video, ABTest, Variation, TestStatus, MetricLog, PlanType, SiteAnnouncement, OAuthAuthCode, EmailVerificationCode
from schemas import ABTestCreate, ABTestResponse
from env_utils import is_dev_environment, allow_test_upgrade
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
JWT_EXPIRE_DAYS = int(os.getenv("JWT_EXPIRE_DAYS", "1"))
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

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="ThumbnailFlow API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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

@app.api_route("/", methods=["GET", "HEAD"])
def read_root():
    """
    UptimeRobot 등 업타임 모니터링 서비스가 Render 무료 플랜의 슬립을 막으려고 주기적으로
    핑을 보내는 엔드포인트. GET만 등록하면 HEAD 요청에 405를 반환해서(모니터링 서비스는
    보통 HEAD를 먼저 시도함) "다운"으로 오탐되므로 HEAD도 명시적으로 허용한다.
    """
    return {"message": "ThumbnailFlow API 서버 정상 동작 중 🚀"}

@app.get("/api/status")
def get_system_status():
    return {"status": "online"}

# --- Google OAuth 로직 ---
@app.get("/api/auth/login")
def login_via_google(state: str | None = None):
    """
    구글 로그인 페이지로 리다이렉트합니다.
    이미 로그인된 상태에서 "채널 추가"로 들어온 경우, 프론트가 현재 JWT를 state로 실어 보낸다.
    구글은 이 state 값을 그대로 콜백에 돌려주므로, 콜백에서 그걸로 "새로 로그인하는 구글
    계정과 무관하게 지금 로그인된 유저 소유로 채널을 붙여야 한다"는 걸 알 수 있다.
    """
    scope = "openid email profile https://www.googleapis.com/auth/youtube.force-ssl"
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
async def google_auth_callback(request: Request, code: str | None = None, error: str | None = None, state: str | None = None, db: Session = Depends(get_db)):
    if error or not code:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=cancelled")

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

    # 5. 프론트엔드로 리다이렉트 (C-1: JWT를 URL에 직접 싣지 않음)
    # JWT 전체를 URL에 노출하면 브라우저 히스토리·서버 로그·Referer에 그대로 남는다.
    # 대신 단기(5분) 일회용 auth_code를 생성해 URL에 실어 보내고,
    # 프론트엔드가 해당 코드를 /api/auth/exchange로 교환해 JWT를 받도록 한다.
    import secrets as _secrets
    token = create_access_token(channel.user_id, channel.id)
    auth_code = _secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    # 만료된 코드 정리 (최대 행 수 제어)
    db.query(OAuthAuthCode).filter(OAuthAuthCode.expires_at < now).delete()
    db.add(OAuthAuthCode(code=auth_code, token=token, expires_at=now + timedelta(minutes=5)))
    db.commit()
    channel_title_encoded = urllib.parse.quote(channel_title)
    return RedirectResponse(f"{FRONTEND_URL}/dashboard?auth_code={auth_code}&connected_channel={channel_title_encoded}")

@app.post("/api/auth/logout")
def logout_user():
    """유저 단순 세션 로그아웃 엔드포인트 (채널 연동 토큰은 유지되어 백그라운드 A/B 테스트가 계속 실행됩니다)"""
    return {"message": "성공적으로 로그아웃되었습니다."}

@app.get("/api/auth/exchange")
def exchange_auth_code(code: str, db: Session = Depends(get_db)):
    """OAuth 콜백 후 단기 auth_code를 실제 JWT로 교환합니다. 코드는 5분 내 1회만 유효합니다."""
    now = datetime.now(timezone.utc)
    entry = (
        db.query(OAuthAuthCode)
        .filter(OAuthAuthCode.code == code, OAuthAuthCode.used == False, OAuthAuthCode.expires_at > now)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=400, detail="유효하지 않거나 만료된 인증 코드입니다.")
    token = entry.token
    entry.used = True
    db.commit()
    return {"token": token}

@app.post("/api/channels/{target_channel_id}/disconnect")
def disconnect_channel(target_channel_id: int, db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """
    지정한 채널의 YouTube 연동을 해제합니다 (OAuth 리프레시 토큰만 삭제).
    switch_channel과 동일하게 같은 계정 소유 채널이면 지금 활성 채널이 아니어도 해제할 수 있다.
    채널 row/테스트 기록 자체는 지우지 않는다 - 재연동하면 다시 쓸 수 있어야 하고, cascade 삭제로
    과거 A/B 테스트 데이터까지 날아가면 안 되기 때문.
    """
    target = db.query(Channel).filter(Channel.id == target_channel_id).first()
    if not target or target.user_id != channel.user_id:
        raise HTTPException(status_code=404, detail="채널을 찾을 수 없거나 이 계정 소유가 아닙니다.")

    target.oauth_refresh_token = None
    target.needs_reconnect = False  # 완전히 연동 해제된 상태이므로 "재연동 필요" 배너와는 구분
    db.commit()
    return {"message": "YouTube 채널 연동이 해제되었습니다."}

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
                "is_connected": bool(c.oauth_refresh_token),
                "is_active": c.id == channel.id,
                "thumbnail_permission": c.thumbnail_permission or "unknown",
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

@app.post("/api/channels/{target_channel_id}/check-capabilities")
async def check_channel_capabilities_endpoint(
    target_channel_id: int,
    db: Session = Depends(get_db),
    channel: Channel = Depends(get_current_channel),
):
    """채널의 YouTube 기능 권한(맞춤 썸네일 등)을 실시간으로 체크하고 DB에 저장합니다."""
    from youtube_api import check_channel_capabilities, TokenRevokedError

    target = db.query(Channel).filter(Channel.id == target_channel_id).first()
    if not target or target.user_id != channel.user_id:
        raise HTTPException(status_code=404, detail="채널을 찾을 수 없습니다.")
    if not target.oauth_refresh_token:
        raise HTTPException(status_code=400, detail="연동이 해제된 채널입니다.")

    try:
        result = await check_channel_capabilities(target.oauth_refresh_token)
        perm = result.get("thumbnail_permission", "unknown")
        try:
            target.thumbnail_permission = perm
            db.commit()
        except Exception as db_err:
            db.rollback()
            logger.warning(f"[Capabilities] DB 저장 실패 (컬럼 없을 수 있음): {db_err}")
        return {"thumbnail_permission": perm}
    except TokenRevokedError:
        target.needs_reconnect = True
        db.commit()
        raise HTTPException(status_code=401, detail="YouTube 연동이 만료되었습니다. 재연동이 필요합니다.")
    except Exception as e:
        logger.error(f"[Capabilities] 예상치 못한 에러: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"권한 확인 중 오류가 발생했습니다: {type(e).__name__}")


@app.post("/api/settings/test-email")
@limiter.limit("3/hour")
def send_test_email(request: Request, db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """이메일 알림 테스트 전송 엔드포인트"""
    target_email = channel.user.email if channel and channel.user else os.getenv("ADMIN_EMAIL", "")
    
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
@limiter.limit("20/minute")
async def create_ab_test(request: Request, test_data: ABTestCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
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
                raise HTTPException(status_code=403, detail="BASIC plan allows only 1 active test at a time. Upgrade to PRO for unlimited concurrent tests.")
                
            # 2. 월간 누적 테스트 생성 횟수 제한 (4회)
            now = datetime.now(timezone.utc)
            first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            monthly_count = db.query(ABTest).join(Video).filter(
                Video.channel_id == channel.id,
                ABTest.start_time >= first_day_of_month,
            ).count()
            if monthly_count >= 4:
                raise HTTPException(status_code=403, detail="You've used all 4 free tests this month. Upgrade to PRO for unlimited tests.")
                
            # 3. 교체 주기 제한 (짧은 주기는 시간대 편향이 커지고 Analytics 데이터와도 안 맞으므로 PRO 전용)
            if test_data.swap_interval_minutes < BASIC_MIN_SWAP_INTERVAL_MINUTES:
                raise HTTPException(status_code=403, detail=f"BASIC plan requires a minimum {BASIC_MIN_SWAP_INTERVAL_MINUTES // 60}-hour swap interval. Shorter intervals are a PRO feature.")
                
            # 3. 썸네일 후보 개수 제한 (A, B, C 까지만 허용 = 최대 3개)
            if len(test_data.variations) > 3:
                raise HTTPException(status_code=403, detail="BASIC plan allows up to 3 thumbnail variants (A/B/C). Upgrade to PRO for up to 5 variants.")

    # 🔒 채널 범위로 조회해야 한다: Video.youtube_video_id는 DB 전역에서 unique라서, 채널 필터 없이
    # 조회하면 이미 다른 사용자가 등록해둔 영상 ID를 그대로 가져와 그 사람 채널에 테스트를 붙이게 된다
    # (그 뒤 스케줄러가 원래 소유자의 OAuth 토큰으로 실제 YouTube 썸네일/제목을 바꿔버리는 사고로 이어짐).
    video = db.query(Video).filter(Video.youtube_video_id == test_data.youtube_video_id, Video.channel_id == channel.id).first()
    if not video:
        # 이 youtube_video_id가 이미 "다른" 채널 소유로 등록되어 있다면(정상적으로는 발생하지 않아야 하지만,
        # 방어적으로) 그 영상을 가로채 테스트를 붙이지 못하도록 명확히 거부한다.
        existing_elsewhere = db.query(Video).filter(Video.youtube_video_id == test_data.youtube_video_id).first()
        if existing_elsewhere:
            raise HTTPException(status_code=403, detail="This video is already linked to another channel and cannot be used for a new test.")
        video = Video(channel_id=channel.id, youtube_video_id=test_data.youtube_video_id)
        db.add(video)
        db.commit()
        db.refresh(video)
        
    new_test = ABTest(
        video_id=video.id,
        swap_interval_minutes=test_data.swap_interval_minutes,
        status=TestStatus.RUNNING,
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc) + timedelta(hours=test_data.duration_hours)
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
    test.end_time = datetime.now(timezone.utc)
    
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
        channel = test.video.channel if test.video else None
        if channel and channel.user and channel.user.email and channel.user.plan == PlanType.PRO:
            from email_service import send_test_completion_email
            to_email = channel.user.notification_email if channel.user.notification_email and channel.user.notification_email_verified else channel.user.email
            await asyncio.to_thread(
                send_test_completion_email,
                user_email=to_email,
                video_title=winner_var.title_text or test.video.youtube_video_id,
                winner_name=winner_var.name,
                views_gained=winner_total_views
            )
        
    db.commit()
    return {"message": "테스트가 성공적으로 중단 및 종료되었습니다.", "winner": winner_var.name if winner_var else None}

@app.get("/api/tests/{test_id}/debug")
async def debug_test_state(test_id: int, db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """테스트 현재 상태 및 썸네일 URL 디버그 정보 반환."""
    from datetime import datetime, timezone
    test = db.query(ABTest).join(Video).filter(ABTest.id == test_id, Video.channel_id == channel.id).first()
    if not test:
        raise HTTPException(status_code=404, detail="테스트를 찾을 수 없거나 권한이 없습니다.")

    now = datetime.now(timezone.utc)
    last_swap = test.last_swapped_at
    if last_swap and last_swap.tzinfo is None:
        last_swap = last_swap.replace(tzinfo=timezone.utc)
    seconds_since_swap = (now - last_swap).total_seconds() if last_swap else None
    next_swap_in_seconds = max(0, test.swap_interval_minutes * 60 - (seconds_since_swap or 0))

    current_var = db.query(Variation).filter(Variation.id == test.current_variation_id).first() if test.current_variation_id else None
    all_vars = db.query(Variation).filter(Variation.ab_test_id == test.id).order_by(Variation.id).all()

    return {
        "test_id": test.id,
        "status": test.status.value if test.status else None,
        "swap_count": test.swap_count,
        "swap_failed": test.swap_failed,
        "swap_interval_minutes": test.swap_interval_minutes,
        "last_swapped_at": last_swap.isoformat() if last_swap else None,
        "seconds_since_last_swap": round(seconds_since_swap or 0),
        "next_swap_in_seconds": round(next_swap_in_seconds),
        "next_swap_in_minutes": round(next_swap_in_seconds / 60, 1),
        "current_variation": current_var.name if current_var else None,
        "variations": [
            {
                "name": v.name,
                "is_control": v.is_control,
                "thumbnail_url": v.thumbnail_image_url,
            }
            for v in all_vars
        ],
    }

@app.post("/api/tests/{test_id}/swap")
@limiter.limit("5/minute")
async def force_swap_ab_test(request: Request, test_id: int, db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """테스트 대기 시간을 기다리지 않고 즉시 다음 변인(썸네일/제목)으로 교체 테스트를 실행합니다."""
    test = db.query(ABTest).join(Video).filter(ABTest.id == test_id, Video.channel_id == channel.id).first()
    if not test:
        raise HTTPException(status_code=404, detail="테스트를 찾을 수 없거나 권한이 없습니다.")
    if test.status != TestStatus.RUNNING:
        raise HTTPException(status_code=400, detail="진행 중인 테스트만 교체 가능합니다.")
    if test.manual_swap_used:
        raise HTTPException(status_code=429, detail="수동 즉시 교체는 테스트당 1회만 사용할 수 있습니다.")

    await scheduler_engine._do_swap(test, db)
    test.manual_swap_used = True
    db.commit()

    if channel.needs_reconnect:
        raise HTTPException(status_code=409, detail="YouTube 연동이 만료되었습니다. 다시 로그인해 채널을 재연동해주세요.")
    if test.swap_failed:
        # 채널에 403 권한 오류가 기록됐으면 전용 메시지 반환
        perm_denied = getattr(channel, "thumbnail_permission_denied", False)
        if perm_denied:
            raise HTTPException(
                status_code=502,
                detail="YouTube 계정 인증이 필요합니다. youtube.com/features 에서 전화번호 인증을 완료해 주세요."
            )
        raise HTTPException(status_code=502, detail="YouTube 썸네일 교체에 실패했습니다. 잠시 후 스케줄러가 자동으로 재시도합니다.")

    current_var = db.query(Variation).filter(Variation.id == test.current_variation_id).first()
    return {"message": "즉시 썸네일/제목 교체가 수행되었습니다.", "current_variation": current_var.name if current_var else None}

@app.delete("/api/tests/{test_id}")
async def delete_ab_test(test_id: int, db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """테스트를 완전히 취소하고 삭제합니다. 유튜브 썸네일과 제목을 원본(Candidate A)으로 돌려놓습니다."""
    test = db.query(ABTest).filter(ABTest.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="테스트를 찾을 수 없습니다.")
        
    if not test.video or test.video.channel_id != channel.id:
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
            import re as _re
            _YT_NATIVE = ("https://i.ytimg.com/", "https://img.youtube.com/")
            _backend = os.getenv("BACKEND_URL", "")
            _allowed = ("https://res.cloudinary.com/", "https://cloudinary.com/") + _YT_NATIVE + ((_backend,) if _backend else ())
            restore_url = original_var.thumbnail_image_url
            if any(restore_url.startswith(p) for p in _YT_NATIVE):
                restore_url = _re.sub(r'/[^/]+\.jpg$', '/maxresdefault.jpg', restore_url)
            if restore_url.startswith("http"):
                if not any(restore_url.startswith(p) for p in _allowed):
                    logger.warning(f"원본 썸네일 URL 도메인 불허 — 복구 건너뜀: {restore_url[:80]}")
                else:
                    file_path = os.path.join("uploads", f"temp_original_{test.id}.jpg")
                    try:
                        import httpx
                        async with httpx.AsyncClient() as client:
                            resp = await client.get(restore_url)
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
@limiter.limit("10/minute")
async def upload_thumbnail(
    request: Request,
    file: UploadFile = File(...),
    channel: Channel = Depends(get_current_channel),
):
    """프론트엔드에서 업로드한 썸네일 이미지를 서버에 저장하고 URL을 반환합니다."""
    
    # 🔒 허용 확장자 화이트리스트 (실행 파일 업로드 차단)
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}
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

    # YouTube 규격에 맞게 자동 리사이즈 + 압축 (블로킹 I/O → 스레드 풀에서 실행)
    try:
        processed_path, img_width, img_height, file_size_bytes, was_processed = await asyncio.to_thread(
            _process_image_for_youtube, file_path
        )
        unique_filename = os.path.basename(processed_path)
    except Exception as e:
        logger.warning(f"[Upload] 이미지 자동 처리 실패 (원본 사용): {e}")
        img_width, img_height, file_size_bytes, was_processed = 0, 0, total_size, False
        processed_path = file_path

    public_url = await publish_local_image(processed_path, unique_filename)
    return {
        "url": public_url,
        "filename": unique_filename,
        "width": img_width,
        "height": img_height,
        "file_size_bytes": file_size_bytes,
        "was_processed": was_processed,
    }

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

def _process_image_for_youtube(file_path: str) -> tuple[str, int, int, int, bool]:
    """
    YouTube 썸네일 규격에 맞게 이미지를 자동 조정합니다.
    - 최소 해상도 미달(1280×720) → 업스케일
    - 파일 크기 초과(2MB) → JPEG 품질 낮춰 압축
    Returns: (final_path, width, height, size_bytes, was_processed)
    """
    YOUTUBE_MIN_W = 1280
    YOUTUBE_MIN_H = 720
    YOUTUBE_MAX_BYTES = 2 * 1024 * 1024  # 2MB

    img = Image.open(file_path)
    try:
        # RGBA/P 등 → RGB 변환 (JPEG 저장 필수)
        if img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            img.close()
            img = bg
        elif img.mode != "RGB":
            converted = img.convert("RGB")
            img.close()
            img = converted

        orig_w, orig_h = img.size
        current_size = os.path.getsize(file_path)

        # 최소 해상도 미달 → 업스케일
        if orig_w < YOUTUBE_MIN_W or orig_h < YOUTUBE_MIN_H:
            scale = max(YOUTUBE_MIN_W / orig_w, YOUTUBE_MIN_H / orig_h)
            resized = img.resize((int(orig_w * scale), int(orig_h * scale)), Image.LANCZOS)
            img.close()
            img = resized

        final_w, final_h = img.size
        needs_processing = (final_w != orig_w or final_h != orig_h or current_size > YOUTUBE_MAX_BYTES)

        if not needs_processing:
            return file_path, final_w, final_h, current_size, False

        # JPEG 압축 (quality 95→40까지 5씩 낮춰 2MB 이하 달성)
        new_path = os.path.splitext(file_path)[0] + ".jpg"
        quality = 95
        buf = io.BytesIO()
        while quality >= 40:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            if buf.tell() <= YOUTUBE_MAX_BYTES:
                break
            quality -= 5

        buf.seek(0)
        with open(new_path, "wb") as f:
            f.write(buf.read())

        if new_path != file_path:
            try:
                os.remove(file_path)
            except Exception:
                pass

        return new_path, final_w, final_h, os.path.getsize(new_path), True
    finally:
        try:
            img.close()
        except Exception:
            pass

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
@limiter.limit("30/minute")
async def get_channel_videos(request: Request, db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
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
            "youtube_video_id": var.ab_test.video.youtube_video_id if var.ab_test and var.ab_test.video else None,
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
                    "day": log.measured_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "views_gained": log.views_gained
                })

            # 로그가 아직 없는 경우 (첫 측정 전) 실제 시작 시각을 표시
            if not chart_data:
                start_label = test.start_time.strftime("%Y-%m-%dT%H:%M:%SZ") if test.start_time else None
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
            "manual_swap_used": test.manual_swap_used or False,
            "variations": vars_data,
        })

    return {"tests": result}

# --- 결제 시스템 (Stripe Integration) ---
import stripe as stripe_sdk
stripe_sdk.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")

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
        "is_admin": is_admin,
        "notification_email": user.notification_email,
        "notification_email_verified": user.notification_email_verified,
    }

@app.post("/api/checkout/create-session")
async def create_stripe_checkout_session(db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """Stripe Checkout Session 생성 - 호스팅된 결제 페이지 URL을 반환합니다."""
    user = channel.user
    if not STRIPE_PRICE_ID:
        raise HTTPException(status_code=503, detail="결제 시스템이 아직 설정되지 않았습니다.")

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    try:
        session = stripe_sdk.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
            mode="subscription",
            success_url=f"{frontend_url}/dashboard?upgraded=true",
            cancel_url=f"{frontend_url}/pricing",
            customer_email=user.email if user else None,
            metadata={"user_id": str(user.id) if user else ""},
        )
    except stripe_sdk.StripeError as e:
        logger.error(f"[Stripe Checkout] 세션 생성 실패: {e}")
        raise HTTPException(status_code=502, detail="결제 페이지를 여는 데 실패했습니다.")

    return {"checkout_url": session.url}

@app.post("/api/checkout/upgrade-test")
def upgrade_user_plan_test(db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """결제 테스트용: 현재 유저의 요금제를 즉시 PRO로 업그레이드합니다. 프로덕션에서는 비활성."""
    if not allow_test_upgrade():
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

@app.get("/api/billing/portal")
async def get_stripe_billing_portal(channel: Channel = Depends(get_current_channel)):
    """
    Stripe Customer Portal URL 발급. 구독 취소, 결제 수단 변경, 결제 내역 조회를
    Stripe가 호스팅하는 화면에서 처리한다. stripe_customer_id 없는 유저는 발급 불가.
    """
    user = channel.user
    if not user or not user.stripe_customer_id:
        raise HTTPException(status_code=404, detail="결제 내역이 없습니다. PRO 결제를 진행한 뒤 다시 시도해주세요.")

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    try:
        portal_session = stripe_sdk.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=f"{frontend_url}/settings",
        )
    except stripe_sdk.StripeError as e:
        logger.error(f"[Stripe Portal] 세션 생성 실패: {e}")
        raise HTTPException(status_code=502, detail="결제 관리 페이지를 여는 데 실패했습니다.")

    return {"url": portal_session.url}

# /api/webhooks/stripe 엔드포인트는 webhook.py 라우터에서 처리합니다 (서명 검증 포함)

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
                "has_stripe_customer": bool(u.stripe_customer_id),
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

@app.post("/api/user/notification-email/send-code")
@limiter.limit("5/minute")
def send_notification_email_code(
    request: Request,
    payload: dict,
    channel: Channel = Depends(get_current_channel),
    db: Session = Depends(get_db),
):
    """알림 이메일 인증 코드 발송 (C-2: DB 저장으로 멀티 워커 지원)."""
    import secrets
    import httpx as _httpx

    email = (payload.get("email") or "").strip()
    if not email or "@" not in email or "." not in email.split("@")[-1] or len(email) > 254:
        raise HTTPException(status_code=400, detail="Invalid email address.")

    now = datetime.now(timezone.utc)
    # 기존 미인증 코드 삭제 (유저당 1개 유지)
    db.query(EmailVerificationCode).filter(EmailVerificationCode.user_id == channel.user_id).delete()
    # 암호학적으로 안전한 6자리 코드 생성
    code = str(secrets.randbelow(900000) + 100000)
    db.add(EmailVerificationCode(
        user_id=channel.user_id,
        code=code,
        email=email,
        expires_at=now + timedelta(minutes=10),
    ))
    db.commit()

    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
    RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "ThumbnailFlow <onboarding@resend.dev>")
    html = f"""<div style="font-family:Arial,sans-serif;background:#09090b;color:#f4f4f5;padding:40px;border-radius:16px;">
<h2 style="color:#06b6d4;">ThumbnailFlow Email Verification</h2>
<p>Your verification code:</p>
<div style="font-size:36px;font-weight:900;letter-spacing:8px;color:#fff;background:#18181b;padding:20px 32px;border-radius:12px;display:inline-block;border:1px solid #06b6d4;">{code}</div>
<p style="color:#a1a1aa;margin-top:16px;">This code expires in 10 minutes.</p>
</div>"""

    simulated = False
    if RESEND_API_KEY:
        try:
            res = _httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={"from": RESEND_FROM_EMAIL, "to": [email], "subject": "[ThumbnailFlow] Email Verification Code", "html": html},
                timeout=10,
            )
            if res.status_code not in (200, 201):
                logger.error(f"Resend error ({res.status_code}): {res.text}")
                raise HTTPException(status_code=502, detail=f"이메일 발송에 실패했습니다. (Resend {res.status_code})")
            logger.info(f"[Resend] 인증 코드 발송 성공 → {email}")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Verification email send error: {e}")
            raise HTTPException(status_code=502, detail="이메일 발송 중 오류가 발생했습니다.")
    else:
        simulated = True
        logger.info(f"[SIMULATE] Verification code for {email}: {code}")

    return {"ok": True, "simulated": simulated}


@app.post("/api/user/notification-email/verify")
def verify_notification_email(
    payload: dict,
    channel: Channel = Depends(get_current_channel),
    db: Session = Depends(get_db),
):
    """인증 코드 확인 후 notification_email 저장 (C-2: DB 기반)."""
    import hmac as _hmac
    code = (payload.get("code") or "").strip()
    now = datetime.now(timezone.utc)
    entry = (
        db.query(EmailVerificationCode)
        .filter(EmailVerificationCode.user_id == channel.user_id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=400, detail="No verification request found. Please request a new code.")
    if now > entry.expires_at:
        db.delete(entry)
        db.commit()
        raise HTTPException(status_code=400, detail="Verification code expired. Please request a new one.")

    # 브루트포스 방지: 5회 초과 시 코드 무효화
    entry.attempts += 1
    if entry.attempts > 5:
        db.delete(entry)
        db.commit()
        raise HTTPException(status_code=429, detail="Too many attempts. Please request a new code.")

    db.commit()  # attempts 증가 저장

    if not _hmac.compare_digest(entry.code, code):
        remaining = 5 - entry.attempts
        raise HTTPException(status_code=400, detail=f"Incorrect verification code. {remaining} attempt(s) remaining.")

    user = db.query(User).filter(User.id == channel.user_id).first()
    if user:
        user.notification_email = entry.email
        user.notification_email_verified = True
    email_saved = entry.email
    db.delete(entry)
    db.commit()
    return {"ok": True, "notification_email": email_saved}


@app.delete("/api/user/notification-email")
def delete_notification_email(
    channel: Channel = Depends(get_current_channel),
    db: Session = Depends(get_db),
):
    """알림 이메일 삭제 (기본 로그인 이메일로 복귀)."""
    user = db.query(User).filter(User.id == channel.user_id).first()
    if user:
        user.notification_email = None
        user.notification_email_verified = False
        db.commit()
    return {"ok": True}


@app.get("/api/announcement")
def get_active_announcement(db: Session = Depends(get_db)):
    """현재 활성화된 공지사항 팝업 반환 (공개 엔드포인트, 인증 불필요)."""
    ann = db.query(SiteAnnouncement).filter(SiteAnnouncement.is_active == True).order_by(SiteAnnouncement.updated_at.desc()).first()
    if not ann:
        return {"announcement": None}
    return {
        "announcement": {
            "id": ann.id,
            "title": ann.title,
            "message": ann.message,
            "button_text": ann.button_text,
            "button_url": ann.button_url,
        }
    }

@app.post("/api/admin/announcement")
def upsert_announcement(
    payload: dict,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """공지사항 생성 또는 전체 교체 (하나만 활성 유지)."""
    title = (payload.get("title") or "").strip()[:200]
    message = (payload.get("message") or "").strip()[:2000]
    button_text = (payload.get("button_text") or "").strip()[:100] or None
    raw_url = (payload.get("button_url") or "").strip()

    if not title or not message:
        raise HTTPException(status_code=400, detail="Title and message are required.")

    # XSS 방지: button_url은 반드시 http/https만 허용
    button_url = None
    if raw_url:
        if not (raw_url.startswith("http://") or raw_url.startswith("https://")):
            raise HTTPException(status_code=400, detail="button_url must start with http:// or https://")
        button_url = raw_url[:500]

    db.query(SiteAnnouncement).update({"is_active": False})
    db.commit()
    ann = SiteAnnouncement(
        title=title,
        message=message,
        button_text=button_text,
        button_url=button_url,
        is_active=True,
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return {"id": ann.id, "title": ann.title, "message": ann.message}

@app.delete("/api/admin/announcement")
def delete_announcement(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    """모든 공지사항 비활성화."""
    db.query(SiteAnnouncement).update({"is_active": False})
    db.commit()
    return {"ok": True}

from webhook import router as stripe_router
app.include_router(stripe_router)
