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
