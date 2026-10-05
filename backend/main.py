import os
import logging
import time
import uuid
import shutil
import asyncio
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import RedirectResponse, JSONResponse
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
import hmac as _hmac_lib
import hashlib as _hashlib
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import init_db, get_db, SessionLocal
from scheduler import AVSchedulerEngine
from models import User, Channel, Video, ABTest, Variation, TestStatus, MetricLog, PlanType, SiteAnnouncement, OAuthAuthCode, EmailVerificationCode
from schemas import ABTestCreate, ABTestResponse
from env_utils import is_dev_environment, allow_test_upgrade
from metrics_utils import compute_variation_vph
from thumbnail_store import process_image_for_youtube as _process_image_for_youtube, publish_local_image
from test_policy import BASIC_MIN_SWAP_INTERVAL_MINUTES, MAX_CONCURRENT_TESTS_PER_CHANNEL
from messages import msg, current_locale, set_request_locale, locale_from_accept_language, SUPPORTED_LOCALES

load_dotenv()

# 로그 단계는 LOG_LEVEL 환경 변수로 정한다 (기본 INFO, 로컬에서 자세히 보려면 backend/.env에 LOG_LEVEL=DEBUG).
# force=True: 먼저 import된 모듈이 로그 설정을 해 두었더라도 여기 설정이 이긴다.
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    force=True,
)
# DEBUG에서도 네트워크 라이브러리의 패킷 단위 기록까지 쏟아지지 않게 우리 코드 위주로 보이게 한다.
for _noisy in ("httpcore", "httpx", "urllib3", "hpack", "PIL", "multipart", "googleapiclient.discovery_cache", "python_multipart"):
    logging.getLogger(_noisy).setLevel(logging.INFO if LOG_LEVEL == "DEBUG" else logging.WARNING)
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

# H-1: OAuth state에 JWT 원문 대신 HMAC-signed nonce 사용
# Google OAuth URL에 JWT 전체를 state로 넣으면 구글 서버/프록시 로그에 남는다.
# 대신 user_id + 랜덤값을 HMAC으로 서명한 단기 nonce를 사용한다.
def _make_state_nonce(user_id: int) -> str:
    import secrets as _sec
    rand = _sec.token_urlsafe(24)
    payload = f"{user_id}:{rand}"
    sig = _hmac_lib.new(JWT_SECRET.encode(), payload.encode(), _hashlib.sha256).hexdigest()[:16]
    return f"{payload}:{sig}"

def _verify_state_nonce(state: str) -> int | None:
    try:
        last_colon = state.rfind(":")
        if last_colon < 0:
            return None
        payload, sig = state[:last_colon], state[last_colon + 1:]
        expected = _hmac_lib.new(JWT_SECRET.encode(), payload.encode(), _hashlib.sha256).hexdigest()[:16]
        if not _hmac_lib.compare_digest(sig, expected):
            return None
        uid_str = payload.split(":", 1)[0]
        return int(uid_str)
    except Exception:
        return None

def create_access_token(user_id: int, channel_id: int | None) -> str:
    """
    로그인은 개인 구글 계정(User)으로 하고, 그 계정에 YouTube 채널을 여러 개 연결한다.
    토큰에는 유저 신원(sub)과 "지금 보고 있는 채널"(channel_id)을 함께 담는다. 채널 전환은
    /api/channels/{id}/switch로 channel_id만 다른 새 토큰을 재발급받는다.
    아직 채널을 연결하지 않은 새 계정이면 channel_id가 없다 (채널 화면은 409 no_channel → 연결 화면).
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
    # L-3: HttpOnly 쿠키 우선 읽기, 없으면 Authorization 헤더 폴백 (구 버전 호환)
    token = request.cookies.get("auth_token")
    if not token:
        auth = request.headers.get("Authorization")
        if auth and auth.startswith("Bearer "):
            token = auth.split(" ")[1]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def _set_auth_cookie(response: JSONResponse, token: str):
    """HttpOnly 쿠키에 JWT를 설정한다.
    프론트(trythumbnailflow.com)와 API(api.trythumbnailflow.com)는 같은 사이트라 Lax로 충분하다.
    Lax면 다른 사이트에서 보낸 POST/DELETE 요청에는 쿠키가 붙지 않아 CSRF가 막힌다."""
    dev = is_dev_environment()
    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,
        secure=not dev,
        samesite="lax",
        max_age=60 * 60 * 24 * JWT_EXPIRE_DAYS,
        path="/",
        domain=None if dev else ".trythumbnailflow.com",
    )

def _clear_auth_cookie(response: JSONResponse):
    dev = is_dev_environment()
    response.delete_cookie(
        key="auth_token",
        path="/",
        secure=not dev,
        samesite="lax",
        httponly=True,
        domain=None if dev else ".trythumbnailflow.com",
    )

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
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    if not channel_id:
        # 로그인은 했지만 아직 채널을 연결하지 않았다 - 프론트가 이 코드를 보고 채널 연결 화면으로 보낸다
        raise HTTPException(status_code=409, detail="no_channel")
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

    # L-4: 브랜드 계정 로그인 시 @pages.plusgoogle.com 이메일이 저장되어 email만으로는
    # 관리자를 식별할 수 없다. google_user_id 기반 체크를 추가한다.
    admin_emails = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
    admin_gids   = {g.strip() for g in os.getenv("ADMIN_GOOGLE_USER_IDS", "").split(",") if g.strip()}
    is_admin = (
        (bool(user.email) and user.email.lower() in admin_emails)
        or (bool(user.google_user_id) and user.google_user_id in admin_gids)
    )
    if not is_admin:
        raise HTTPException(status_code=403, detail=msg("admin_forbidden"))
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

# L-2: 프로덕션(Cloudinary)에서는 로컬 uploads/ 를 공개 서빙하지 않는다.
os.makedirs("uploads", exist_ok=True)
if is_dev_environment():
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def apply_request_locale(request: Request, call_next):
    """프론트가 보낸 Accept-Language로 이 요청의 응답 메시지 언어를 정한다 (messages.msg가 읽음)."""
    set_request_locale(locale_from_accept_language(request.headers.get("accept-language")))
    started = time.perf_counter()
    response = await call_next(request)
    # DEBUG에서만: 요청마다 처리 시간까지 남겨 느린 API를 찾을 수 있게 한다
    logger.debug(
        f"{request.method} {request.url.path} -> {response.status_code} "
        f"({(time.perf_counter() - started) * 1000:.0f}ms, lang={current_locale()})"
    )
    return response

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
OAUTH_LOCALE_COOKIE = "oauth_locale"
# 로그인을 시작한 브라우저에만 심어 두는 값. 콜백의 state와 같아야 통과한다 -
# 남이 만든 구글 로그인 주소를 열어도(채널을 남의 계정에 연결시키는 공격) 이 쿠키가 없어 거부된다.
OAUTH_STATE_COOKIE = "oauth_state"
# 콜백이 발급한 auth_code를 같은 브라우저에서만 교환할 수 있게 묶어 두는 쿠키.
OAUTH_CODE_COOKIE = "oauth_pending_code"
# "다시 연동" 버튼으로 시작한 로그인이면, 다시 연결할 채널의 ID. 구글 화면은 모든 채널을 보여주므로
# 콜백에서 사용자가 고른 채널이 이 채널인지 확인하고, 다르면 아무것도 바꾸지 않는다.
OAUTH_RECONNECT_COOKIE = "oauth_reconnect"
OAUTH_COOKIE_PATH = "/api/auth"


def _set_oauth_cookie(response, key: str, value: str, max_age: int):
    response.set_cookie(
        key, value, max_age=max_age, path=OAUTH_COOKIE_PATH,
        httponly=True, samesite="lax", secure=not is_dev_environment(),
    )


def _oauth_redirect(url: str) -> RedirectResponse:
    """콜백을 끝내는 리다이렉트. 한 번 쓴 state/언어 쿠키는 지운다."""
    response = RedirectResponse(url)
    response.delete_cookie(OAUTH_STATE_COOKIE, path=OAUTH_COOKIE_PATH)
    response.delete_cookie(OAUTH_LOCALE_COOKIE, path=OAUTH_COOKIE_PATH)
    response.delete_cookie(OAUTH_RECONNECT_COOKIE, path=OAUTH_COOKIE_PATH)
    return response


def _login_locale(request: Request) -> str:
    """로그인을 시작한 화면의 언어(쿠키) → 없으면 브라우저 언어(Accept-Language)."""
    chosen = request.cookies.get(OAUTH_LOCALE_COOKIE)
    return chosen if chosen in SUPPORTED_LOCALES else locale_from_accept_language(request.headers.get("accept-language"))


LOGIN_SCOPE = "openid email profile"
CHANNEL_SCOPE = "openid email profile https://www.googleapis.com/auth/youtube.force-ssl"


def _google_auth_redirect(scope: str, prompt: str, state: str, locale: str | None, offline: bool) -> RedirectResponse:
    """구글 동의 화면으로 보내고, 같은 브라우저에서 돌아왔는지 대조할 state와 화면 언어를 쿠키에 남긴다."""
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": scope,
        "prompt": prompt,
        "state": state,
    }
    if offline:
        # 백그라운드 테스트에 쓸 refresh_token을 받는다. 예전에 승인한 권한도 이번 토큰에 담아,
        # 다시 연결할 때 YouTube 체크박스를 놓쳐도 계정에 남은 권한으로 동작하게 한다.
        params["access_type"] = "offline"
        params["include_granted_scopes"] = "true"
    response = RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote))
    _set_oauth_cookie(response, OAUTH_STATE_COOKIE, state, max_age=600)
    # 구글을 다녀오는 동안 시작한 화면 언어를 기억해 두었다가, 콜백에서 계정 언어로 저장한다.
    if locale in SUPPORTED_LOCALES:
        _set_oauth_cookie(response, OAUTH_LOCALE_COOKIE, locale, max_age=600)
    return response


@app.get("/api/auth/login")
def login_via_google(locale: str | None = None):
    """
    개인 구글 계정으로 로그인한다. 이메일·프로필만 요청하므로 구글은 브랜드 채널이 아닌 구글 계정만 보여준다.
    YouTube 채널은 로그인한 뒤 /api/auth/connect로 따로 연결한다.
    브라우저에 다른 계정의 로그인이 남아 있어도 그 계정과는 상관없는 새 로그인이다.
    """
    import secrets as _secrets
    return _google_auth_redirect(LOGIN_SCOPE, "select_account", _secrets.token_urlsafe(24), locale, offline=False)


@app.get("/api/auth/connect")
def connect_youtube_channel(request: Request, locale: str | None = None, reconnect: int | None = None):
    """
    로그인한 계정에 YouTube 채널을 연결한다 (첫 연결·채널 추가·다시 연동 모두).
    구글 화면에서 다른 구글 계정이나 브랜드 채널을 골라도, 채널은 지금 로그인한 계정에 붙는다.
    reconnect=채널ID면 "그 채널 다시 연동" 모드 - 콜백에서 같은 채널을 골랐을 때만 연동한다.
    """
    # L-3: 쿠키에서 현재 로그인 유저 ID를 읽는다 — JWT를 URL에 노출하지 않아도 됨
    try:
        user_id = int(_decode_token(request)["sub"])
    except Exception:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=session_expired")
    # state에 유저 ID를 서명해 담아 두면, 콜백이 이것을 보고 로그인이 아닌 채널 연결로 처리한다.
    response = _google_auth_redirect(CHANNEL_SCOPE, "consent select_account", _make_state_nonce(user_id), locale, offline=True)
    # 다시 연동은 로그인한 사람이 자기 채널에 대해서만 쓴다 (채널 소유 확인은 콜백에서).
    if reconnect:
        _set_oauth_cookie(response, OAUTH_RECONNECT_COOKIE, str(reconnect), max_age=600)
    return response

def _issue_auth_code_redirect(db: Session, request: Request, user: User, channel: Channel | None, extra_query: str = "") -> RedirectResponse:
    """
    로그인·채널 연결을 마치고 프론트로 보낸다 (C-1: JWT를 URL에 직접 싣지 않음).
    JWT 전체를 URL에 노출하면 브라우저 히스토리·서버 로그·Referer에 그대로 남는다.
    대신 단기(5분) 일회용 auth_code를 URL에 실어 보내고, 프론트가 /api/auth/exchange로 교환해 JWT를 받는다.
    아직 채널이 없는 계정이면 대시보드 대신 채널 연결 화면으로 보낸다.
    """
    import secrets as _secrets
    token = create_access_token(user.id, channel.id if channel else None)
    auth_code = _secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    # 만료된 코드 정리 (최대 행 수 제어)
    db.query(OAuthAuthCode).filter(OAuthAuthCode.expires_at < now).delete()
    db.add(OAuthAuthCode(code=auth_code, token=token, expires_at=now + timedelta(minutes=5)))
    # 언어를 아직 저장한 적 없는 계정이면 로그인 순간의 언어로 채운다 (알림 메일 언어에 쓰임).
    if not user.locale:
        user.locale = _login_locale(request)
    db.commit()
    page = "dashboard" if channel else "connect"
    response = _oauth_redirect(f"{FRONTEND_URL}/{page}?auth_code={auth_code}{extra_query}")
    # 이 auth_code는 이 브라우저에서만 교환되게 묶는다 - 남의 auth_code 주소를 열어
    # 공격자 계정으로 로그인되는 것(로그인 CSRF)을 막는다.
    _set_oauth_cookie(response, OAUTH_CODE_COOKIE, auth_code, max_age=300)
    return response


def _connect_error_redirect(db: Session, user_id: int, query: str) -> RedirectResponse:
    """채널을 연결하지 못했을 때: 이미 채널이 있으면 대시보드, 없으면 채널 연결 화면에서 이유를 보여준다."""
    has_channel = db.query(Channel).filter(Channel.user_id == user_id).first() is not None
    return _oauth_redirect(f"{FRONTEND_URL}/{'dashboard' if has_channel else 'connect'}?{query}")


def _finish_login(request: Request, db: Session, google_user_id: str, email: str) -> RedirectResponse:
    """개인 구글 계정으로 계정을 찾거나 만든다. 채널이 있으면 첫 채널로, 없으면 채널 연결 화면으로 들어간다."""
    user = db.query(User).filter(User.google_user_id == google_user_id).first()
    if not user:
        # 레거시 브릿지: google_user_id 도입 이전에 이메일만으로 저장된 유저가 있으면 그쪽에 채워 넣는다.
        user = db.query(User).filter(User.email == email).first()
        if user and not user.google_user_id:
            user.google_user_id = google_user_id
    if not user:
        user = User(google_user_id=google_user_id, email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
    channel = db.query(Channel).filter(Channel.user_id == user.id).order_by(Channel.id).first()
    logger.info(f"로그인: {email} (채널 {'있음' if channel else '없음'})")
    return _issue_auth_code_redirect(db, request, user, channel)


async def _finish_channel_connect(
    request: Request, db: Session, user_id: int, google_user_id: str,
    channel_id: str, channel_title: str, access_token: str, refresh_token: str | None,
) -> RedirectResponse:
    """구글 화면에서 고른 YouTube 채널을 로그인한 계정(user_id)에 연결한다."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        await _revoke_google_token(refresh_token or access_token)
        return _oauth_redirect(f"{FRONTEND_URL}/login?error=session_expired")

    # "다시 연동" 모드: 사용자가 고른 채널이 다시 연결하려던 그 채널인지 확인한다.
    # 다르면 아무것도 바꾸지 않고, 방금 받은 권한도 돌려준 뒤 올바른 채널을 고르라고 안내한다.
    reconnect_cookie = request.cookies.get(OAUTH_RECONNECT_COOKIE)
    if reconnect_cookie:
        try:
            expected = db.query(Channel).filter(Channel.id == int(reconnect_cookie)).first()
        except ValueError:
            expected = None
        if expected and expected.user_id == user.id and expected.youtube_channel_id != channel_id:
            logger.info(f"다시 연동 채널 불일치: 기대 {expected.youtube_channel_id}, 선택 {channel_id} - 변경 없음")
            await _revoke_google_token(refresh_token or access_token)
            expected_title = urllib.parse.quote(expected.channel_title or "")
            return _oauth_redirect(f"{FRONTEND_URL}/dashboard?error=reconnect_wrong_channel&expected={expected_title}")

    channel = db.query(Channel).filter(Channel.youtube_channel_id == channel_id).first()

    def _channel_limit_reached() -> bool:
        # 요금제별 채널 개수 상한 (멀티채널 관리는 PRO/AGENCY 차별화 포인트)
        from test_policy import max_channels_for_plan
        plan_value = user.plan.value if hasattr(user.plan, "value") else str(user.plan)
        existing_count = db.query(Channel).filter(Channel.user_id == user.id).count()
        if existing_count >= max_channels_for_plan(plan_value):
            logger.info(f"채널 연동 한도 초과: {user.email} (plan={plan_value}, 기존 {existing_count}개)")
            return True
        return False

    if channel and channel.user_id != user.id:
        # 다른 계정에 붙어 있는 채널. 그 계정에서 연동을 해제했거나, 그 계정이 지금 구글 화면에서 고른 바로 그
        # 구글 신원으로 만든 계정이면(2단계 로그인 전에 채널로 로그인해 생긴 계정 등) 이 계정으로 옮긴다.
        # 둘 다 원래 그 계정에 들어갈 수 있는 사람만 할 수 있는 일이라, 남의 연결된 채널을 빼앗는 데는 쓸 수 없다.
        previous_owner = channel.user
        same_identity = previous_owner is not None and previous_owner.google_user_id == google_user_id
        if channel.oauth_refresh_token and not same_identity:
            logger.info(f"채널 추가 거부: {channel_id}는 다른 계정({channel.user_id}) 소속 - 변경 없음")
            await _revoke_google_token(refresh_token or access_token)
            title = urllib.parse.quote(channel.channel_title or channel_title or "")
            return _connect_error_redirect(db, user.id, f"error=channel_owned_elsewhere&channel={title}")
        if _channel_limit_reached():
            await _revoke_google_token(refresh_token or access_token)
            return _connect_error_redirect(db, user.id, "error=channel_limit_reached")
        logger.info(f"채널 이전: {channel_id} 계정 {channel.user_id} → {user.id}")
        if previous_owner is not None and previous_owner.plan != PlanType.BASIC:
            logger.warning(f"채널 이전: 이전 계정({previous_owner.id})의 요금제 {previous_owner.plan}는 옮기지 않았습니다 - 확인 필요")
        channel.user = user
        _video_list_cache.pop(channel.id, None)

    if not channel:
        if _channel_limit_reached():
            return _connect_error_redirect(db, user.id, "error=channel_limit_reached")
        channel = Channel(user_id=user.id, youtube_channel_id=channel_id, channel_title=channel_title)

    if refresh_token:
        channel.oauth_refresh_token = refresh_token
        channel.needs_reconnect = False  # 재동의로 새 refresh_token을 받았으므로 재연동 필요 상태 해제

    channel.channel_title = channel_title
    db.add(channel)
    db.commit()
    db.refresh(channel)
    logger.info(f"유튜브 채널 연동 성공: {channel_title} ({user.email})")
    return _issue_auth_code_redirect(db, request, user, channel, f"&connected_channel={urllib.parse.quote(channel_title)}")


@app.get("/api/auth/callback")
async def google_auth_callback(request: Request, code: str | None = None, error: str | None = None, state: str | None = None, db: Session = Depends(get_db)):
    """구글 로그인·채널 연결이 끝나고 돌아오는 콜백. state에 유저 ID가 서명돼 있으면 채널 연결, 아니면 로그인이다."""
    # 이 브라우저에서 시작한 요청인지 확인한다 (10분 안에, 같은 브라우저에서 돌아왔을 때만 통과).
    expected_state = request.cookies.get(OAUTH_STATE_COOKIE)
    state_ok = bool(state and expected_state and _hmac_lib.compare_digest(state, expected_state))
    connecting_user_id = _verify_state_nonce(state) if state_ok else None

    if error or not code:
        if connecting_user_id:
            return _connect_error_redirect(db, connecting_user_id, "error=cancelled")
        return _oauth_redirect(f"{FRONTEND_URL}/login?error=cancelled")
    if not state_ok:
        logger.warning("OAuth state 불일치 - 이 브라우저에서 시작하지 않은 로그인이라 거부합니다.")
        return _oauth_redirect(f"{FRONTEND_URL}/login?error=session_expired")

    # 1. code를 이용해 access_token과 refresh_token 발급
    token_data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    # M-1: 문자열 비교 대신 is_dev_environment()로 SSL 검증 여부를 결정한다.
    ssl_verify = not is_dev_environment()

    async with httpx.AsyncClient(verify=ssl_verify) as client:
        token_res = await client.post("https://oauth2.googleapis.com/token", data=token_data)
        if token_res.status_code != 200:
            logger.error(f"Token error: {token_res.text}")
            raise HTTPException(status_code=400, detail=msg("oauth_token_failed"))

        token_json = token_res.json()
        access_token = token_json.get("access_token")
        refresh_token = token_json.get("refresh_token")  # 채널 연결(offline)에서만 발급됨
        headers = {"Authorization": f"Bearer {access_token}"}

        # 2. 사용자 정보 가져오기
        userinfo_res = await client.get("https://www.googleapis.com/oauth2/v2/userinfo", headers=headers)
        if userinfo_res.status_code != 200:
            logger.error(f"Userinfo error: {userinfo_res.text}")
            raise HTTPException(status_code=400, detail=msg("google_userinfo_failed"))
        userinfo_json = userinfo_res.json()
        # 🔒 유저 식별은 반드시 이 "id"(OIDC sub와 동일, 계정당 고유·불변) 기준으로 해야 한다.
        # 채널 연결 때 브랜드 채널을 고르면 그 채널 전용 신원과 "...@pages.plusgoogle.com" 같은 이메일이 온다.
        google_user_id = userinfo_json.get("id")
        email = userinfo_json.get("email")
        if not google_user_id:
            logger.error("구글 userinfo 응답에 id(sub)가 없습니다.")
            raise HTTPException(status_code=400, detail=msg("google_account_failed"))
        if not email:
            # User.email은 nullable=False라서, None인 채로 User를 만들면 DB commit 시점에 500이 난다.
            logger.error("구글 userinfo 응답에 email이 없습니다.")
            raise HTTPException(status_code=400, detail=msg("google_email_missing"))

        if not connecting_user_id:
            return _finish_login(request, db, google_user_id, email)

        # 3. 채널 연결이면 고른 YouTube 채널 정보 가져오기
        yt_res = await client.get("https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true", headers=headers)
        if yt_res.status_code == 403:
            # 동의 화면에서 YouTube 권한 체크를 빠뜨리면 여기서 403이 난다. "채널이 없다"와는 다른 원인이라 따로 알린다.
            # 토큰에 실제로 담긴 권한도 남긴다 - 동의 화면 문제인지, 토큰 문제인지 로그만 보고 가릴 수 있게
            logger.error(f"YouTube API 403 (granted scope: {token_json.get('scope')}): {yt_res.text}")
            return _connect_error_redirect(db, connecting_user_id, "error=youtube_permission_denied")
        yt_data = yt_res.json()
        if not yt_data.get("items"):
            return _connect_error_redirect(db, connecting_user_id, "error=no_youtube_channel")
        channel_id = yt_data["items"][0]["id"]
        channel_title = yt_data["items"][0]["snippet"]["title"]

    return await _finish_channel_connect(
        request, db, connecting_user_id, google_user_id, channel_id, channel_title, access_token, refresh_token,
    )

@app.post("/api/auth/logout")
def logout_user():
    """유저 단순 세션 로그아웃 엔드포인트 (채널 연동 토큰은 유지되어 백그라운드 A/B 테스트가 계속 실행됩니다)"""
    response = JSONResponse(content={"message": msg("logout_success")})
    _clear_auth_cookie(response)
    return response

@app.get("/api/auth/exchange")
def exchange_auth_code(request: Request, code: str, db: Session = Depends(get_db)):
    """OAuth 콜백 후 단기 auth_code를 실제 JWT로 교환합니다. 코드는 5분 내 1회, 콜백을 받은 브라우저에서만 유효합니다."""
    pending_code = request.cookies.get(OAUTH_CODE_COOKIE)
    if not pending_code or not _hmac_lib.compare_digest(pending_code, code):
        raise HTTPException(status_code=400, detail=msg("invalid_auth_code"))
    now = datetime.now(timezone.utc)
    entry = (
        db.query(OAuthAuthCode)
        .filter(OAuthAuthCode.code == code, OAuthAuthCode.used == False, OAuthAuthCode.expires_at > now)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=400, detail=msg("invalid_auth_code"))
    token = entry.token
    entry.used = True
    db.commit()
    # L-3: JWT를 응답 body 대신 HttpOnly 쿠키에 설정한다.
    response = JSONResponse(content={"ok": True})
    _set_auth_cookie(response, token)
    response.delete_cookie(OAUTH_CODE_COOKIE, path=OAUTH_COOKIE_PATH)
    return response

async def _revoke_google_token(refresh_token: str):
    """구글 쪽 앱 권한도 회수한다 (사용자의 구글 계정 '연결된 앱'에서 사라짐). 실패해도 연동 해제는 계속한다."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post("https://oauth2.googleapis.com/revoke", data={"token": refresh_token})
        if res.status_code != 200:
            logger.warning(f"구글 권한 회수 실패 (상태 코드 {res.status_code}) - 토큰은 DB에서 삭제합니다.")
    except Exception as e:
        logger.warning(f"구글 권한 회수 중 오류: {e} - 토큰은 DB에서 삭제합니다.")


@app.post("/api/channels/{target_channel_id}/disconnect")
async def disconnect_channel(target_channel_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    지정한 채널의 YouTube 연동을 해제합니다.
    switch_channel과 동일하게 같은 계정 소유 채널이면 지금 활성 채널이 아니어도 해제할 수 있다.
    채널 row/테스트 기록 자체는 지우지 않는다 - 재연동하면 다시 쓸 수 있어야 하고, cascade 삭제로
    과거 A/B 테스트 데이터까지 날아가면 안 되기 때문.

    권한이 사라지면 테스트 썸네일이 유튜브에 그대로 방치되므로, 아직 권한이 있는 지금
    진행 중인 테스트를 멈추고 썸네일·제목을 원본으로 되돌린 뒤 권한을 회수한다.
    """
    target = db.query(Channel).filter(Channel.id == target_channel_id).first()
    if not target or target.user_id != user.id:
        raise HTTPException(status_code=404, detail=msg("channel_not_owned"))

    refresh_token = target.oauth_refresh_token
    running_tests = (
        db.query(ABTest).join(Video)
        .filter(Video.channel_id == target.id, ABTest.status == TestStatus.RUNNING, ABTest.is_deleted == False)
        .all()
    )
    for test in running_tests:
        await _restore_original(test, db, refresh_token)
        test.status = TestStatus.STOPPED
        test.end_time = datetime.now(timezone.utc)

    if refresh_token:
        await _revoke_google_token(refresh_token)

    target.oauth_refresh_token = None
    target.needs_reconnect = False  # 완전히 연동 해제된 상태이므로 "재연동 필요" 배너와는 구분
    db.commit()
    _video_list_cache.pop(target.id, None)
    return {"message": msg("channel_disconnected_ok"), "stopped_tests": len(running_tests)}

@app.get("/api/channels")
def list_channels(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """현재 계정에 연동된 모든 YouTube 채널 목록 (멀티채널 전환 UI용). '활성' 채널은 지금 토큰이 가리키는 채널."""
    from test_policy import max_channels_for_plan

    active_channel_id = _decode_token(request).get("channel_id")
    channels = db.query(Channel).filter(Channel.user_id == user.id).order_by(Channel.id).all()
    plan_value = user.plan.value if hasattr(user.plan, "value") else "BASIC"

    return {
        "channels": [
            {
                "id": c.id,
                "channel_title": c.channel_title,
                "youtube_channel_id": c.youtube_channel_id,
                "needs_reconnect": c.needs_reconnect,
                "is_connected": bool(c.oauth_refresh_token),
                "is_active": c.id == active_channel_id,
                "thumbnail_permission": c.thumbnail_permission or "unknown",
            }
            for c in channels
        ],
        "max_channels": max_channels_for_plan(plan_value),
    }

@app.post("/api/channels/{target_channel_id}/switch")
def switch_channel(target_channel_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """대시보드에서 다른 연동 채널로 전환 - 같은 계정 소유 채널일 때만 새 토큰을 발급한다."""
    target = db.query(Channel).filter(Channel.id == target_channel_id).first()
    if not target or target.user_id != user.id:
        raise HTTPException(status_code=404, detail=msg("channel_not_owned"))

    token = create_access_token(user.id, target.id)
    # L-3: JWT를 응답 body 대신 HttpOnly 쿠키에 설정한다.
    response = JSONResponse(content={"ok": True, "channel_title": target.channel_title})
    _set_auth_cookie(response, token)
    return response

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
        raise HTTPException(status_code=404, detail=msg("channel_not_found"))
    if not target.oauth_refresh_token:
        raise HTTPException(status_code=400, detail=msg("channel_is_disconnected"))

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
        raise HTTPException(status_code=401, detail=msg("youtube_reconnect_required"))
    except Exception as e:
        logger.error(f"[Capabilities] 예상치 못한 에러: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=msg("permission_check_failed"))


@app.post("/api/settings/test-email")
@limiter.limit("3/hour")
def send_test_email(request: Request, db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """이메일 알림 테스트 전송 엔드포인트"""
    target_email = channel.user.email if channel and channel.user else os.getenv("ADMIN_EMAIL", "")
    
    from email_service import send_test_completion_email
    result = send_test_completion_email(
        user_email=target_email,
        video_title=msg("test_email_sample_title"),
        winner_name=msg("test_email_sample_winner"),
        views_gained=458,
        locale=current_locale(),
    )
    if result["simulated"]:
        message = msg("test_email_simulated", email=target_email)
    elif result["sent"]:
        message = msg("test_email_sent", email=target_email)
    else:
        message = msg("test_email_failed")

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
        raise HTTPException(status_code=403, detail=msg("max_concurrent_per_channel", limit=MAX_CONCURRENT_TESTS_PER_CHANNEL))

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
                raise HTTPException(status_code=403, detail=msg("basic_one_active"))
                
            # 2. 월간 누적 테스트 생성 횟수 제한 (4회)
            # M-5: YouTube 쿼터와 동일하게 PT 기준으로 월 시작을 계산한다.
            from zoneinfo import ZoneInfo as _ZoneInfo
            _pt = _ZoneInfo("America/Los_Angeles")
            _now_pt = datetime.now(_pt)
            _month_start_pt = _now_pt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            first_day_of_month = _month_start_pt.astimezone(timezone.utc)
            monthly_count = db.query(ABTest).join(Video).filter(
                Video.channel_id == channel.id,
                ABTest.start_time >= first_day_of_month,
            ).count()
            if monthly_count >= 4:
                raise HTTPException(status_code=403, detail=msg("basic_monthly_limit"))
                
            # 3. 교체 주기 제한 (짧은 주기는 시간대 편향이 커지고 Analytics 데이터와도 안 맞으므로 PRO 전용)
            if test_data.swap_interval_minutes < BASIC_MIN_SWAP_INTERVAL_MINUTES:
                raise HTTPException(status_code=403, detail=msg("basic_min_interval", hours=BASIC_MIN_SWAP_INTERVAL_MINUTES // 60))
                
            # 3. 썸네일 후보 개수 제한 (A, B, C 까지만 허용 = 최대 3개)
            if len(test_data.variations) > 3:
                raise HTTPException(status_code=403, detail=msg("basic_max_variants"))

    # 🔒 채널 범위로 조회해야 한다: Video.youtube_video_id는 DB 전역에서 unique라서, 채널 필터 없이
    # 조회하면 이미 다른 사용자가 등록해둔 영상 ID를 그대로 가져와 그 사람 채널에 테스트를 붙이게 된다
    # (그 뒤 스케줄러가 원래 소유자의 OAuth 토큰으로 실제 YouTube 썸네일/제목을 바꿔버리는 사고로 이어짐).
    video = db.query(Video).filter(Video.youtube_video_id == test_data.youtube_video_id, Video.channel_id == channel.id).first()
    if not video:
        # 이 youtube_video_id가 이미 "다른" 채널 소유로 등록되어 있다면(정상적으로는 발생하지 않아야 하지만,
        # 방어적으로) 그 영상을 가로채 테스트를 붙이지 못하도록 명확히 거부한다.
        existing_elsewhere = db.query(Video).filter(Video.youtube_video_id == test_data.youtube_video_id).first()
        if existing_elsewhere:
            raise HTTPException(status_code=403, detail=msg("video_other_channel"))
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

    return ABTestResponse(id=new_test.id, status=new_test.status.name, message=msg("test_started"))

@app.post("/api/tests/{test_id}/stop")
async def stop_ab_test(test_id: int, db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """진행 중인 A/B 테스트를 수동으로 중단하고 승자를 확정합니다."""
    test = db.query(ABTest).join(Video).filter(ABTest.id == test_id, Video.channel_id == channel.id).first()
    if not test:
        raise HTTPException(status_code=404, detail=msg("test_not_found_or_forbidden"))
    if test.is_deleted or test.status != TestStatus.RUNNING:
        raise HTTPException(status_code=400, detail=msg("only_running_can_stop"))

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
        if channel and channel.user and channel.user.email and channel.user.plan == PlanType.PRO and channel.user.email_alerts_enabled:
            from email_service import send_test_completion_email
            to_email = channel.user.notification_email if channel.user.notification_email and channel.user.notification_email_verified else channel.user.email
            await asyncio.to_thread(
                send_test_completion_email,
                user_email=to_email,
                video_title=winner_var.title_text or test.video.youtube_video_id,
                winner_name=winner_var.name,
                views_gained=winner_total_views,
                locale=channel.user.locale,
                thumbnail_url=winner_var.thumbnail_image_url,
                youtube_video_id=test.video.youtube_video_id,
            )

    db.commit()
    return {"message": msg("test_stopped"), "winner": winner_var.name if winner_var else None}

@app.get("/api/tests/{test_id}/debug")
async def debug_test_state(test_id: int, db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """테스트 현재 상태 및 썸네일 URL 디버그 정보 반환."""
    from datetime import datetime, timezone
    test = db.query(ABTest).join(Video).filter(ABTest.id == test_id, Video.channel_id == channel.id).first()
    if not test:
        raise HTTPException(status_code=404, detail=msg("test_not_found_or_forbidden"))

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
        raise HTTPException(status_code=404, detail=msg("test_not_found_or_forbidden"))
    if test.status != TestStatus.RUNNING:
        raise HTTPException(status_code=400, detail=msg("only_running_can_swap"))
    if test.manual_swap_used:
        raise HTTPException(status_code=429, detail=msg("manual_swap_once"))

    # 사용자가 누른 "지금 교체"는 시간대 균형과 상관없이 반드시 다른 후보로 바꾼다
    await scheduler_engine._do_swap(test, db, allow_stay=False)
    test.manual_swap_used = True
    db.commit()

    if channel.needs_reconnect:
        raise HTTPException(status_code=409, detail=msg("youtube_relogin_required"))
    if test.swap_failed:
        # 채널에 403 권한 오류가 기록됐으면 전용 메시지 반환
        perm_denied = channel.thumbnail_permission == "denied"
        if perm_denied:
            raise HTTPException(
                status_code=502,
                detail=msg("youtube_phone_verification")
            )
        raise HTTPException(status_code=502, detail=msg("thumbnail_swap_failed"))

    current_var = db.query(Variation).filter(Variation.id == test.current_variation_id).first()
    return {"message": msg("swap_done"), "current_variation": current_var.name if current_var else None}

@app.delete("/api/tests/{test_id}")
async def delete_ab_test(test_id: int, db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """테스트를 완전히 취소하고 삭제합니다. 유튜브 썸네일과 제목을 원본(Candidate A)으로 돌려놓습니다."""
    test = db.query(ABTest).filter(ABTest.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail=msg("test_not_found"))
        
    if not test.video or test.video.channel_id != channel.id:
        raise HTTPException(status_code=403, detail=msg("forbidden"))

    # 재시도/더블클릭으로 같은 삭제 요청이 두 번 오면, 이미 삭제된 테스트에 대해 원본 복구
    # YouTube 요청(썸네일 다운로드+업로드, 제목 변경)을 매번 다시 실행하는 걸 막는다.
    if test.is_deleted:
        return {"message": msg("test_cancelled")}

    await _restore_original(test, db, channel.oauth_refresh_token)

    # 논리적 삭제 (Soft Delete) - 쿼터 유지를 위해 DB에 남김
    test.is_deleted = True
    test.status = TestStatus.STOPPED
    db.commit()
    return {"message": msg("test_cancelled")}


async def _restore_original(test: ABTest, db: Session, refresh_token: str | None):
    """유튜브 썸네일과 제목을 원본(Candidate A)으로 되돌린다. 테스트 삭제와 채널 연동 해제에서 함께 쓴다."""
    if not refresh_token:
        return
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
                                await update_youtube_thumbnail(test.video.youtube_video_id, file_path, refresh_token)
                            else:
                                logger.error(f"원본 썸네일 복구 실패 (상태 코드: {resp.status_code})")
                    except Exception as e:
                        logger.error(f"원본 썸네일 복구 다운로드 에러: {e}")
            else:
                try:
                    file_name = original_var.thumbnail_image_url.split('/')[-1]
                    file_path = os.path.join("uploads", file_name)
                    if os.path.exists(file_path):
                        await update_youtube_thumbnail(test.video.youtube_video_id, file_path, refresh_token)
                except Exception as e:
                    logger.error(f"원본 썸네일 로컬 복구 실패: {e}")

        # 제목 복구
        if original_var.title_text:
            try:
                await update_youtube_title(test.video.youtube_video_id, original_var.title_text, refresh_token)
            except Exception as e:
                logger.error(f"원본 제목 복구 실패: {e}")

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
        raise HTTPException(status_code=400, detail=msg("file_type_not_allowed", allowed=', '.join(ALLOWED_EXTENSIONS)))
    
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=msg("content_type_not_allowed"))

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
                raise HTTPException(status_code=400, detail=msg("file_too_large"))
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
        raise HTTPException(status_code=400, detail=msg("invalid_image"))

    if detected_format not in ALLOWED_IMAGE_FORMATS:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail=msg("image_format_not_allowed", fmt=detected_format))

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
        raise HTTPException(status_code=400, detail=msg("file_type_not_allowed", allowed=', '.join(ALLOWED_EXTENSIONS)))

    headline = headline.strip()
    if not headline:
        raise HTTPException(status_code=400, detail=msg("headline_required"))
    if len(headline) > 60:
        raise HTTPException(status_code=400, detail=msg("headline_too_long"))

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
                raise HTTPException(status_code=400, detail=msg("file_too_large"))
            f.write(chunk)

    try:
        with Image.open(temp_input_path) as img:
            img.verify()
    except Exception:
        os.remove(temp_input_path)
        raise HTTPException(status_code=400, detail=msg("invalid_image"))

    output_filename = f"{uuid.uuid4()}.jpg"
    output_path = os.path.join(upload_dir, output_filename)

    try:
        from thumbnail_generator import generate_thumbnail
        generate_thumbnail(temp_input_path, headline, output_path)
    except Exception as e:
        logger.error(f"썸네일 자동 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=msg("thumbnail_generation_failed"))
    finally:
        if os.path.exists(temp_input_path):
            os.remove(temp_input_path)

    analysis = analyze_thumbnail(output_path)
    public_url = await publish_local_image(output_path, output_filename)

    return {"url": public_url, "filename": output_filename, "analysis": analysis}

from ml_scorer import analyze_thumbnail

@app.post("/api/analyze-thumbnail")
async def api_analyze_thumbnail(request: Request, channel: Channel = Depends(get_current_channel)):
    """업로드된 썸네일 이미지의 파일명을 받아 머신러닝(휴리스틱) 예측 점수를 반환합니다."""
    data = await request.json()
    filename = data.get("filename")
    if not filename:
        raise HTTPException(status_code=400, detail=msg("filename_missing"))

    # 🔒 filename은 클라이언트가 보내는 값이므로, os.path.basename으로 경로 조작(../ 등)을 제거하고
    # uploads/ 디렉터리 밖의 임의 파일을 열람하지 못하도록 막는다.
    safe_filename = os.path.basename(filename)
    if not safe_filename or safe_filename != filename:
        raise HTTPException(status_code=400, detail=msg("filename_invalid"))

    file_path = os.path.join("uploads", safe_filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail=msg("file_not_found"))
    result = analyze_thumbnail(file_path)
    return result

from youtube_api import get_recent_videos, TokenRevokedError
from quota_guard import record_usage

# 영상 목록은 자주 바뀌지 않으므로 채널별로 잠시 기억해 두고, 그 사이에는 유튜브를 다시 부르지 않는다
# (새 테스트 화면에 들어갈 때마다 쿼터 2~5유닛을 쓰던 것을 줄임). 새 영상을 바로 보고 싶으면 refresh=true.
VIDEO_LIST_CACHE_SECONDS = int(os.getenv("VIDEO_LIST_CACHE_SECONDS", str(15 * 60)))
_video_list_cache: dict[int, tuple[float, list]] = {}


@app.get("/api/videos")
@limiter.limit("30/minute")
async def get_channel_videos(request: Request, refresh: bool = False, db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """현재 연동된 채널의 최근 유튜브 영상 목록을 가져옵니다."""
    if not channel or not channel.oauth_refresh_token:
        raise HTTPException(status_code=400, detail=msg("no_channel_token"))

    cached = _video_list_cache.get(channel.id)
    if cached and not refresh and time.monotonic() - cached[0] < VIDEO_LIST_CACHE_SECONDS:
        logger.debug(f"[videos] 채널 {channel.id}: 기억해 둔 목록 사용 ({len(cached[1])}개, {time.monotonic() - cached[0]:.0f}초 전)")
        return {"videos": cached[1]}
    logger.debug(f"[videos] 채널 {channel.id}: 유튜브에서 새로 불러옴 (refresh={refresh})")

    try:
        videos, units = await get_recent_videos(channel.oauth_refresh_token)
    except TokenRevokedError:
        channel.needs_reconnect = True
        db.commit()
        raise HTTPException(status_code=409, detail=msg("youtube_relogin_required"))

    # 관리자 화면의 "오늘 쿼터 사용량"에 잡히도록 실제 호출 횟수를 기록한다
    if units:
        record_usage(db, units)
        db.commit()
    # 빈 목록은 조회 실패일 수도 있어 기억하지 않는다 (다음 요청에서 다시 시도)
    if videos:
        _video_list_cache[channel.id] = (time.monotonic(), videos)
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

# --- 결제 시스템 (Paddle Billing) ---
import httpx as _httpx
PADDLE_API_KEY   = os.getenv("PADDLE_API_KEY", "")
PADDLE_PRICE_ID  = os.getenv("PADDLE_PRICE_ID", "")
PADDLE_CLIENT_TOKEN = os.getenv("PADDLE_CLIENT_TOKEN", "")
PADDLE_ENVIRONMENT  = "sandbox" if os.getenv("PADDLE_ENVIRONMENT", "").strip().lower() == "sandbox" else "production"
PADDLE_API_BASE  = "https://sandbox-api.paddle.com" if PADDLE_ENVIRONMENT == "sandbox" else "https://api.paddle.com"

@app.get("/api/user/me")
def get_current_user_profile(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """로그인한 계정 정보·요금제와, 지금 보고 있는 채널(아직 연결 전이면 has_channel=False)을 반환합니다."""
    active_channel_id = _decode_token(request).get("channel_id")
    channel = (
        db.query(Channel).filter(Channel.id == int(active_channel_id), Channel.user_id == user.id).first()
        if active_channel_id else None
    )

    admin_emails = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
    is_admin = bool(user.email) and user.email.lower() in admin_emails

    return {
        "email": user.email,
        "plan": user.plan.value if hasattr(user.plan, "value") else str(user.plan),
        "is_pro": user.plan == PlanType.PRO or user.plan == PlanType.AGENCY,
        "has_channel": channel is not None,
        "channel_title": channel.channel_title if channel else None,
        "needs_reconnect": channel.needs_reconnect if channel else False,
        "is_connected": bool(channel and channel.oauth_refresh_token),
        "channel_id": channel.id if channel else None,
        "is_admin": is_admin,
        "notification_email": user.notification_email,
        "notification_email_verified": user.notification_email_verified,
        "email_alerts_enabled": user.email_alerts_enabled,
        "locale": user.locale,
    }

@app.patch("/api/user/preferences")
def update_user_preferences(
    payload: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """M-6: 이메일 알림 수신 여부 등 사용자 환경설정을 업데이트합니다."""
    if "email_alerts_enabled" in payload:
        user.email_alerts_enabled = bool(payload["email_alerts_enabled"])
    if "locale" in payload:
        if payload["locale"] not in SUPPORTED_LOCALES:
            raise HTTPException(status_code=400, detail=msg("unsupported_locale"))
        user.locale = payload["locale"]
    db.commit()
    return {"ok": True, "email_alerts_enabled": user.email_alerts_enabled, "locale": user.locale}

@app.post("/api/checkout/create-session")
async def create_checkout_session(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Paddle 트랜잭션을 생성하고, 프론트가 Paddle.js 오버레이로 결제창을 열 수 있도록 ID와 client token을 반환합니다."""
    if not PADDLE_API_KEY or not PADDLE_PRICE_ID or not PADDLE_CLIENT_TOKEN:
        raise HTTPException(status_code=503, detail=msg("payments_not_configured"))

    payload: dict = {
        "items": [{"price_id": PADDLE_PRICE_ID, "quantity": 1}],
        "custom_data": {"user_id": str(user.id)},
    }
    if user.email:
        payload["customer"] = {"email": user.email}

    try:
        async with _httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{PADDLE_API_BASE}/transactions",
                headers={"Authorization": f"Bearer {PADDLE_API_KEY}", "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        transaction_id = data["data"]["id"]
    except _httpx.HTTPStatusError as e:
        logger.error(f"[Paddle Checkout] 트랜잭션 생성 실패: {e.response.status_code} {e.response.text}")
        raise HTTPException(status_code=502, detail=msg("checkout_open_failed"))
    except Exception as e:
        logger.error(f"[Paddle Checkout] 트랜잭션 생성 실패: {e}")
        raise HTTPException(status_code=502, detail=msg("checkout_open_failed"))

    return {
        "transaction_id": transaction_id,
        "client_token": PADDLE_CLIENT_TOKEN,
        "environment": PADDLE_ENVIRONMENT,
    }

@app.post("/api/checkout/upgrade-test")
def upgrade_user_plan_test(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """결제 테스트용: 현재 유저의 요금제를 즉시 PRO로 업그레이드합니다. 프로덕션에서는 비활성."""
    if not allow_test_upgrade():
        raise HTTPException(status_code=403, detail=msg("upgrade_test_disabled"))
    user.plan = PlanType.PRO
    db.commit()
    return {"status": "success", "message": msg("upgraded_pro"), "plan": user.plan.value}

@app.get("/api/billing/portal")
async def get_billing_portal(user: User = Depends(get_current_user)):
    """
    Paddle 고객 포털(결제 정보·영수증·구독 해지) 주소를 발급한다.
    공식 방법인 portal-sessions로 로그인된 링크를 만들고, 응답의 urls.general.overview로 보낸다.
    (예전에 쓰던 auth-token은 Paddle.js용이라 포털이 로그인 화면으로 열렸다.)
    로그인은 개인 구글 계정으로만 하므로, 로그인한 사람이 곧 이 계정(과 결제)의 주인이다.
    """
    if not user.stripe_customer_id:
        raise HTTPException(status_code=404, detail=msg("no_billing_history"))

    # 구독 ID를 같이 넘기면 포털에 그 구독의 해지·결제수단 변경 바로가기도 만들어진다
    body = {"subscription_ids": [user.stripe_subscription_id]} if user.stripe_subscription_id else {}
    try:
        async with _httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{PADDLE_API_BASE}/customers/{user.stripe_customer_id}/portal-sessions",
                headers={"Authorization": f"Bearer {PADDLE_API_KEY}", "Content-Type": "application/json"},
                json=body,
            )
            resp.raise_for_status()
            portal_url = resp.json()["data"]["urls"]["general"]["overview"]
    except _httpx.HTTPStatusError as e:
        logger.error(f"[Paddle Portal] 포털 세션 생성 실패: {e.response.status_code} {e.response.text}")
        raise HTTPException(status_code=502, detail=msg("billing_portal_failed"))
    except Exception as e:
        logger.error(f"[Paddle Portal] 포털 URL 발급 실패: {e}")
        raise HTTPException(status_code=502, detail=msg("billing_portal_failed"))

    return {"url": portal_url}

# /api/webhook/paddle 엔드포인트는 webhook.py 라우터에서 처리합니다 (서명 검증 포함)

# --- 관리자 대시보드 (ADMIN_EMAILS 환경 변수에 등록된 계정만 접근 가능) ---

@app.get("/api/admin/stats")
def get_admin_stats(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    """가입자/채널/테스트 현황과 오늘의 YouTube API 쿼터 사용량을 한눈에 보여준다."""
    from quota_guard import get_today_usage, DAILY_QUOTA_LIMIT

    total_users = db.query(User).count()
    pro_users = db.query(User).filter(User.plan == PlanType.PRO).count()
    basic_users = db.query(User).filter(User.plan == PlanType.BASIC).count()

    # 연동 해제는 권한만 지우고 채널 기록은 남기므로, 권한(refresh_token)이 있는 채널만 "연결됨"으로 센다
    total_channels = db.query(Channel).count()
    connected = db.query(Channel).filter(Channel.oauth_refresh_token.isnot(None))
    connected_channels = connected.count()
    channels_needing_reconnect = connected.filter(Channel.needs_reconnect == True).count()

    active_tests = db.query(ABTest).filter(ABTest.status == TestStatus.RUNNING, ABTest.is_deleted == False).count()
    completed_tests = db.query(ABTest).filter(ABTest.status == TestStatus.COMPLETED).count()
    total_tests = db.query(ABTest).count()

    return {
        "users": {"total": total_users, "pro": pro_users, "basic": basic_users},
        "channels": {
            "total": total_channels,
            "connected": connected_channels,
            "disconnected": total_channels - connected_channels,
            "needs_reconnect": channels_needing_reconnect,
        },
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
                # 연동 해제한 채널은 기록만 남아 있으므로 연결된 채널과 따로 센다
                "channel_count": sum(1 for c in u.channels if c.oauth_refresh_token),
                "disconnected_channel_count": sum(1 for c in u.channels if not c.oauth_refresh_token),
                "has_paddle_customer": bool(u.stripe_customer_id),  # Paddle 고객 ID는 stripe_customer_id 컬럼을 재사용
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
        raise HTTPException(status_code=400, detail=msg("invalid_email"))

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
<h2 style="color:#06b6d4;">{msg('email_verify_heading')}</h2>
<p>{msg('email_verify_code_label')}</p>
<div style="font-size:36px;font-weight:900;letter-spacing:8px;color:#fff;background:#18181b;padding:20px 32px;border-radius:12px;display:inline-block;border:1px solid #06b6d4;">{code}</div>
<p style="color:#a1a1aa;margin-top:16px;">{msg('email_verify_expires')}</p>
</div>"""

    simulated = False
    if RESEND_API_KEY:
        try:
            res = _httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={"from": RESEND_FROM_EMAIL, "to": [email], "subject": msg("email_verify_subject"), "html": html},
                timeout=10,
            )
            if res.status_code not in (200, 201):
                logger.error(f"Resend error ({res.status_code}): {res.text}")
                raise HTTPException(status_code=502, detail=msg("email_send_failed", status=res.status_code))
            logger.info(f"[Resend] 인증 코드 발송 성공 → {email}")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Verification email send error: {e}")
            raise HTTPException(status_code=502, detail=msg("email_send_error"))
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
        raise HTTPException(status_code=400, detail=msg("verification_not_found"))
    if now > entry.expires_at:
        db.delete(entry)
        db.commit()
        raise HTTPException(status_code=400, detail=msg("verification_expired"))

    # 브루트포스 방지: 5회 초과 시 코드 무효화
    entry.attempts += 1
    if entry.attempts > 5:
        db.delete(entry)
        db.commit()
        raise HTTPException(status_code=429, detail=msg("verification_too_many"))

    db.commit()  # attempts 증가 저장

    if not _hmac.compare_digest(entry.code, code):
        remaining = 5 - entry.attempts
        raise HTTPException(status_code=400, detail=msg("verification_incorrect", remaining=remaining))

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

from webhook import router as paddle_router
app.include_router(paddle_router)
