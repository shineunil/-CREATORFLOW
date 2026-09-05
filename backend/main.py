import os
import logging
import uuid
import shutil
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import httpx
import urllib.parse
import certifi

import jwt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import init_db, get_db, SessionLocal
from scheduler import AVSchedulerEngine
from models import User, Channel, Video, ABTest, Variation, TestStatus, MetricLog, PlanType
from schemas import ABTestCreate, ABTestResponse

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("🚨 JWT_SECRET 환경 변수가 설정되지 않았습니다. .env 파일을 확인하세요.")
JWT_ALGORITHM = "HS256"
security = HTTPBearer()

def get_current_channel(request: Request, db: Session = Depends(get_db)):
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        channel_id = payload.get("sub")
        if not channel_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        channel = db.query(Channel).filter(Channel.id == int(channel_id)).first()
        if not channel:
            raise HTTPException(status_code=401, detail="Channel not found")
        return channel
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


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
def login_via_google():
    """구글 로그인 페이지로 리다이렉트합니다."""
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
    return RedirectResponse(auth_url)

@app.get("/api/auth/callback")
async def google_auth_callback(code: str, db: Session = Depends(get_db)):
    """구글 로그인 성공 시 되돌아오는 콜백 엔드포인트"""
    
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
        
        # 2. 이메일 정보 가져오기
        userinfo_res = await client.get("https://www.googleapis.com/oauth2/v2/userinfo", headers=headers)
        email = userinfo_res.json().get("email")
        
        # 3. 유튜브 채널 정보 가져오기
        yt_res = await client.get("https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true", headers=headers)
        yt_data = yt_res.json()
        
        if not yt_data.get("items"):
            return RedirectResponse(f"{FRONTEND_URL}/?error=no_youtube_channel")
            
        channel_id = yt_data["items"][0]["id"]
        channel_title = yt_data["items"][0]["snippet"]["title"]
        
    # 4. DB 저장 로직 (유저 및 채널)
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
        
    channel = db.query(Channel).filter(Channel.youtube_channel_id == channel_id).first()
    if not channel:
        channel = Channel(user_id=user.id, youtube_channel_id=channel_id, channel_title=channel_title)
    
    if refresh_token:
        channel.oauth_refresh_token = refresh_token
        
    channel.channel_title = channel_title
    db.add(channel)
    db.commit()
    
    logger.info(f"유튜브 채널 연동 성공: {channel_title} ({email})")
    
    # 5. 프론트엔드로 리다이렉트 (JWT 발급 포함)
    token = jwt.encode({"sub": str(channel.id)}, JWT_SECRET, algorithm=JWT_ALGORITHM)
    channel_title_encoded = urllib.parse.quote(channel_title)
    return RedirectResponse(f"{FRONTEND_URL}/dashboard?token={token}&connected_channel={channel_title_encoded}")

@app.post("/api/auth/logout")
def logout_user():
    """유저 단순 세션 로그아웃 엔드포인트 (채널 연동 토큰은 유지되어 백그라운드 A/B 테스트가 계속 실행됩니다)"""
    return {"message": "성공적으로 로그아웃되었습니다."}

@app.post("/api/auth/disconnect-channel")
def disconnect_channel(db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """YouTube 채널 연동 해제 엔드포인트 (현재 로그인된 채널의 OAuth 리프레시 토큰만 삭제)"""
    channel.oauth_refresh_token = None
    db.commit()
    return {"message": "YouTube 채널 연동이 완벽하게 해제되었습니다."}

@app.post("/api/settings/test-email")
def send_test_email(db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """이메일 알림 테스트 전송 엔드포인트"""
    target_email = channel.user.email if channel and channel.user else "godlove3854@gmail.com"
    
    from email_service import send_test_completion_email
    success = send_test_completion_email(
        user_email=target_email,
        video_title="사진 속 우리 (비하인드 스페셜)",
        winner_name="Variation B (네온 자막 강조 썸네일)",
        views_gained=458
    )
    return {
        "status": "ok" if success else "error",
        "target_email": target_email,
        "message": f"'{target_email}' 주소로 A/B 테스트 승자 확정 이메일 알림이 성공적으로 전송(시뮬레이션) 되었습니다!"
    }

# --- A/B Test 로직 ---
@app.post("/api/tests", response_model=ABTestResponse)
def create_ab_test(test_data: ABTestCreate, db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """프론트엔드에서 보낸 설정값으로 새로운 A/B 테스트를 DB에 생성합니다."""
    
    # [요금제 제한 로직 추가]
    user = channel.user
    if user:
        from models import PlanType, TestStatus
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
                
            # 3. 교체 주기 제한
            if test_data.swap_interval_minutes < 60:
                raise HTTPException(status_code=403, detail="BASIC 요금제는 최소 60분 주기로만 테스트할 수 있습니다. 30분 교체는 PRO 요금제 전용입니다.")
                
            # 3. 썸네일 후보 개수 제한 (A, B, C 까지만 허용 = 최대 3개)
            if len(test_data.variations) > 3:
                raise HTTPException(status_code=403, detail="BASIC 요금제는 원본 포함 최대 3개의 후보까지만 테스트할 수 있습니다. 무제한 추가를 원하시면 PRO로 업그레이드해주세요.")

    video = db.query(Video).filter(Video.youtube_video_id == test_data.youtube_video_id).first()
    if not video:
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
    
    return ABTestResponse(id=new_test.id, status=new_test.status.name, message="A/B 테스트가 성공적으로 시작되었습니다!")

@app.post("/api/tests/{test_id}/stop")
async def stop_ab_test(test_id: int, db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """진행 중인 A/B 테스트를 수동으로 중단하고 승자를 확정합니다."""
    test = db.query(ABTest).join(Video).filter(ABTest.id == test_id, Video.channel_id == channel.id).first()
    if not test:
        raise HTTPException(status_code=404, detail="테스트를 찾을 수 없거나 권한이 없습니다.")
    
    test.status = TestStatus.COMPLETED
    test.end_time = datetime.utcnow()
    
    # 승자 확정 (가장 많은 조회수를 얻은 변인)
    all_vars = db.query(Variation).filter(Variation.ab_test_id == test.id).all()
    winner_var = None
    max_views = -1
    for var in all_vars:
        logs = db.query(MetricLog).filter(MetricLog.variation_id == var.id).all()
        total_gained = sum(l.views_gained for l in logs)
        if total_gained > max_views:
            max_views = total_gained
            winner_var = var
            
    if winner_var:
        winner_var.is_winner = True
        channel = test.video.channel
        if channel and channel.user and channel.user.email:
            from email_service import send_test_completion_email
            send_test_completion_email(
                user_email=channel.user.email,
                video_title=winner_var.title_text or test.video.youtube_video_id,
                winner_name=winner_var.name,
                views_gained=max_views
            )
        
    db.commit()
    return {"message": "테스트가 성공적으로 중단 및 종료되었습니다.", "winner": winner_var.name if winner_var else None}

@app.post("/api/tests/{test_id}/swap")
async def force_swap_ab_test(test_id: int, db: Session = Depends(get_db)):
    """테스트 대기 시간을 기다리지 않고 즉시 다음 변인(썸네일/제목)으로 교체 테스트를 실행합니다."""
    test = db.query(ABTest).filter(ABTest.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="테스트를 찾을 수 없습니다.")
    if test.status != TestStatus.RUNNING:
        raise HTTPException(status_code=400, detail="진행 중인 테스트만 교체 가능합니다.")
        
    await scheduler_engine._do_swap(test, db)
    db.commit()
    
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
        
    return {"url": f"{BACKEND_URL}/uploads/{unique_filename}", "filename": unique_filename}

from ml_scorer import analyze_thumbnail

@app.post("/api/analyze-thumbnail")
async def api_analyze_thumbnail(request: Request):
    """업로드된 썸네일 이미지의 파일명을 받아 머신러닝(휴리스틱) 예측 점수를 반환합니다."""
    data = await request.json()
    filename = data.get("filename")
    if not filename:
        raise HTTPException(status_code=400, detail="파일명이 제공되지 않았습니다.")
        
    file_path = os.path.join("uploads", filename)
    result = analyze_thumbnail(file_path)
    return result

from youtube_api import get_recent_videos

@app.get("/api/videos")
async def get_channel_videos(db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """현재 연동된 채널의 최근 유튜브 영상 목록을 가져옵니다."""
    if not channel or not channel.oauth_refresh_token:
        raise HTTPException(status_code=400, detail="연동된 채널이나 인증 토큰이 없습니다.")
        
    videos = await get_recent_videos(channel.oauth_refresh_token)
    return {"videos": videos}

from sqlalchemy import func

@app.get("/api/analytics")
def get_analytics(db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """채널의 전체 통계 데이터를 반환합니다."""
    if not channel:
        return {"total_tests": 0, "total_views_gained": 0, "active_tests": 0}
        
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

    return {
        "total_tests": total_tests,
        "active_tests": active_tests,
        "total_views_gained": total_views_gained
    }

@app.get("/api/history")
def get_history(db: Session = Depends(get_db), channel: Channel = Depends(get_current_channel)):
    """채널의 완료된 테스트 기록을 반환합니다."""
    if not channel:
        return {"tests": []}
        
    tests = db.query(ABTest).join(Video).filter(Video.channel_id == channel.id, ABTest.status == TestStatus.COMPLETED).order_by(ABTest.id.desc()).all()
    
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
                "total_views_gained": sum(log.views_gained for log in var.metric_logs)
            })
            
        result.append({
            "test_id": test.id,
            "video_id": test.video.youtube_video_id,
            "status": test.status.name,
            "swap_interval": test.swap_interval_minutes,
            "end_time": test.end_time.isoformat() if test.end_time else None,
            "variations": vars_data
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
                    "ctr": log.views_gained
                })
            
            # 로그가 아직 없는 경우 (첫 측정 전) 실제 시작 시각을 표시
            if not chart_data:
                start_label = test.start_time.strftime("%m-%d %H:%M") if test.start_time else "방금 전"
                chart_data = [
                    {"day": start_label, "ctr": 0}
                ]
                
            vars_data.append({
                "id": var.id,
                "name": var.name,
                "title_text": var.title_text,
                "thumbnail_image_url": var.thumbnail_image_url,
                "is_winner": var.is_winner,
                "chart_data": chart_data,
                "total_views_gained": sum(log.views_gained for log in var.metric_logs)
            })
            
        result.append({
            "test_id": test.id,
            "video_id": test.video.youtube_video_id,
            "status": test.status.name,
            "swap_interval": test.swap_interval_minutes,
            "start_time": test.start_time.isoformat() if test.start_time else None,
            "end_time": test.end_time.isoformat() if test.end_time else None,
            "variations": vars_data
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
        return {"email": None, "plan": "BASIC", "is_pro": False, "channel_title": None}
        
    return {
        "email": user.email,
        "plan": user.plan.value if hasattr(user.plan, "value") else str(user.plan),
        "is_pro": user.plan == PlanType.PRO or user.plan == PlanType.AGENCY,
        "channel_title": channel.channel_title
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
    """결제 테스트용: 현재 유저의 요금제를 즉시 PRO로 업그레이드합니다."""
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
    secret = os.getenv("LEMON_SQUEEZY_WEBHOOK_SECRET", "").encode("utf-8")
    signature = request.headers.get("x-signature")
    
    payload = await request.body()
    if secret and signature:
        computed_signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, computed_signature):
            logger.warning("Invalid Lemon Squeezy webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

    data = await request.json()
    event_name = data.get("meta", {}).get("event_name")
    
    if event_name in ["subscription_created", "order_created", "subscription_updated"]:
        custom_data = data.get("meta", {}).get("custom_data", {})
        user_email = custom_data.get("user_email")
        
        if not user_email:
            user_email = data.get("data", {}).get("attributes", {}).get("user_email")
            
        if user_email:
            user = db.query(User).filter(User.email == user_email).first()
            if user:
                user.plan = PlanType.PRO
                db.commit()
                logger.info(f"🎉 웹훅 수신: 유저 {user_email}의 요금제가 PRO로 성공적으로 업그레이드 되었습니다.")
                
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

# /api/webhooks/paddle 엔드포인트는 webhook.py 라우터에서 처리합니다 (서명 검증 포함)

from webhook import router as webhook_router
app.include_router(webhook_router)
