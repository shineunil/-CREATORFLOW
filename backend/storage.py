import os
import time
import hashlib
import logging
import httpx

logger = logging.getLogger(__name__)

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
CLOUDINARY_FOLDER = os.getenv("CLOUDINARY_FOLDER", "creatorflow_thumbnails")


def is_cloud_storage_configured() -> bool:
    return bool(CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET)


def _sign_params(params: dict) -> str:
    """Cloudinary 서명 규칙: file/api_key/signature를 제외한 파라미터를 key=value로 정렬해 이어붙이고 API secret을 더해 SHA1."""
    to_sign = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    return hashlib.sha1(f"{to_sign}{CLOUDINARY_API_SECRET}".encode("utf-8")).hexdigest()


async def upload_thumbnail_to_cloud(file_bytes: bytes, filename: str) -> str | None:
    """
    Cloudinary에 썸네일 이미지를 업로드하고 영구 URL을 반환합니다.
    자격 증명이 설정되어 있지 않으면 None을 반환해 로컬 디스크 저장으로 폴백하게 합니다.
    (Render 등 배포 환경의 로컬 디스크는 재배포 시 초기화되어 파일이 유실되므로, 프로덕션에서는
    CLOUDINARY_CLOUD_NAME / CLOUDINARY_API_KEY / CLOUDINARY_API_SECRET 설정이 필수입니다.)
    """
    if not is_cloud_storage_configured():
        return None

    timestamp = str(int(time.time()))
    params_to_sign = {"timestamp": timestamp, "folder": CLOUDINARY_FOLDER}
    signature = _sign_params(params_to_sign)

    data = {
        "api_key": CLOUDINARY_API_KEY,
        "timestamp": timestamp,
        "folder": CLOUDINARY_FOLDER,
        "signature": signature,
    }
    files = {"file": (filename, file_bytes)}

    url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(url, data=data, files=files)
        if res.status_code != 200:
            logger.error(f"[Cloudinary] 업로드 실패 (상태 코드 {res.status_code}): {res.text}")
            return None
        return res.json().get("secure_url")
    except Exception as e:
        logger.error(f"[Cloudinary] 업로드 중 오류: {e}")
        return None


def cloud_public_id(url: str | None) -> str | None:
    """
    우리 Cloudinary 계정에 올린 이미지 주소면 그 public_id(폴더/파일명, 확장자 제외)를, 아니면 None.
    예: https://res.cloudinary.com/<cloud>/image/upload/v1712345/creatorflow_thumbnails/abc.jpg
        → creatorflow_thumbnails/abc
    유튜브 주소나 다른 계정의 주소는 None이라 절대 지우지 않는다.
    """
    if not url or not CLOUDINARY_CLOUD_NAME:
        return None
    prefix = f"https://res.cloudinary.com/{CLOUDINARY_CLOUD_NAME}/image/upload/"
    if not url.startswith(prefix):
        return None
    path = url[len(prefix):].split("?", 1)[0]
    parts = path.split("/")
    if parts and parts[0].startswith("v") and parts[0][1:].isdigit():
        parts = parts[1:]  # 버전(v1712345) 부분은 public_id가 아니다
    if not parts or not parts[-1]:
        return None
    parts[-1] = os.path.splitext(parts[-1])[0]
    return "/".join(parts)


async def delete_thumbnail_from_cloud(url: str) -> bool:
    """우리 Cloudinary에 올린 이미지를 지운다. 이미 없으면 지워진 것으로 본다. 우리 이미지가 아니면 False."""
    public_id = cloud_public_id(url)
    if not public_id or not is_cloud_storage_configured():
        return False
    timestamp = str(int(time.time()))
    data = {
        "public_id": public_id,
        "timestamp": timestamp,
        "api_key": CLOUDINARY_API_KEY,
        "signature": _sign_params({"public_id": public_id, "timestamp": timestamp}),
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/destroy", data=data)
        result = res.json().get("result") if res.status_code == 200 else None
        if result in ("ok", "not found"):
            return True
        logger.warning(f"[Cloudinary] 삭제 실패 ({res.status_code}, {result}): {public_id}")
        return False
    except Exception as e:
        logger.warning(f"[Cloudinary] 삭제 중 오류: {e}")
        return False
