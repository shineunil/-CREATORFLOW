import io
import logging
import os
import uuid

import httpx
from PIL import Image

from storage import is_cloud_storage_configured, upload_thumbnail_to_cloud

logger = logging.getLogger(__name__)

UPLOAD_DIR = "uploads"
YOUTUBE_NATIVE_PREFIXES = ("https://i.ytimg.com/", "https://img.youtube.com/")
# 유튜브가 영상마다 제공하는 썸네일 크기. 고화질부터 시도하고, 없는 영상(오래되거나 저화질)은 다음 크기로 내려간다.
_YOUTUBE_THUMBNAIL_SIZES = ("maxresdefault.jpg", "sddefault.jpg", "hqdefault.jpg")


def is_youtube_native_url(url: str | None) -> bool:
    return bool(url) and url.startswith(YOUTUBE_NATIVE_PREFIXES)


def process_image_for_youtube(file_path: str) -> tuple[str, int, int, int, bool]:
    """
    YouTube 썸네일 규격에 맞게 이미지를 자동 조정하고, 저장 용량을 줄이기 위해 항상 JPEG로 다시 저장합니다.
    - 해상도: 비율을 유지한 채 1280×720을 꽉 채우는 크기로 맞춤 (작으면 키우고, 크면 줄임)
    - 용량: JPEG 품질 85로 저장 (유튜브도 썸네일을 다시 압축하므로 눈으로 보이는 차이는 거의 없음).
      그래도 2MB를 넘으면 품질을 더 낮춘다.
    Returns: (final_path, width, height, size_bytes, was_upscaled)
      was_upscaled는 작은 이미지를 키운 경우에만 True - 화질이 떨어질 수 있어 사용자에게 알려줄 때만 쓴다.
    """
    YOUTUBE_W = 1280
    YOUTUBE_H = 720
    YOUTUBE_MAX_BYTES = 2 * 1024 * 1024  # 2MB
    JPEG_QUALITY = 85

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

        # 1280×720을 꽉 채우는 배율 (16:9 이미지는 정확히 1280×720이 됨)
        scale = max(YOUTUBE_W / orig_w, YOUTUBE_H / orig_h)
        was_upscaled = scale > 1
        if scale != 1:
            resized = img.resize((round(orig_w * scale), round(orig_h * scale)), Image.LANCZOS)
            img.close()
            img = resized

        final_w, final_h = img.size

        # JPEG로 다시 저장 (85에서 시작해 2MB를 넘으면 40까지 5씩 낮춤)
        new_path = os.path.splitext(file_path)[0] + ".jpg"
        quality = JPEG_QUALITY
        buf = io.BytesIO()
        while quality >= 40:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
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

        return new_path, final_w, final_h, os.path.getsize(new_path), was_upscaled
    finally:
        try:
            img.close()
        except Exception:
            pass


async def publish_local_image(file_path: str, filename: str) -> str:
    """
    🌩️ 클라우드 스토리지(Cloudinary)가 설정되어 있으면 영구 URL로 업로드합니다.
    (로컬 디스크는 Render 재배포 시 초기화되므로, 프로덕션에서는 클라우드 URL을 DB에 저장해야 합니다.
     로컬 사본은 스케줄러의 로컬 캐시 용도로 그대로 유지합니다.)
    """
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    if not is_cloud_storage_configured():
        return f"{backend_url}/uploads/{filename}"

    with open(file_path, "rb") as f:
        file_bytes = f.read()
    cloud_url = await upload_thumbnail_to_cloud(file_bytes, filename)
    if cloud_url:
        return cloud_url

    logger.error("Cloudinary 업로드 실패 - 로컬 URL로 폴백합니다 (재배포 시 유실될 수 있음)")
    return f"{backend_url}/uploads/{filename}"


async def _download_youtube_thumbnail(youtube_video_id: str) -> bytes | None:
    """영상의 '지금' 썸네일을 받는다. 고화질이 없는 영상은 다음 크기로 내려간다."""
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for size in _YOUTUBE_THUMBNAIL_SIZES:
            try:
                res = await client.get(f"https://i.ytimg.com/vi/{youtube_video_id}/{size}")
            except Exception as e:
                logger.warning(f"[원본 보관] {youtube_video_id}/{size} 다운로드 오류: {e}")
                continue
            if res.status_code == 200 and res.content:
                return res.content
    return None


async def snapshot_original_thumbnail(youtube_video_id: str) -> str | None:
    """
    테스트가 영상의 썸네일을 바꾸기 '전에' 원본 썸네일을 받아 영구 저장하고 그 URL을 돌려준다.

    유튜브 썸네일 주소(i.ytimg.com/vi/영상ID/...)는 "그 영상의 지금 썸네일"을 가리켜서, 후보 B를 건 뒤에는
    같은 주소에서 B가 나온다. 그래서 원본(A)을 주소로만 기억하면 A 차례 교체·원본 승자 적용·취소 복구가
    모두 원본이 아닌 이미지로 이뤄진다. 첫 교체 전에 이미지 자체를 보관해 두어야 한다.
    실패하면 None (호출한 쪽은 원본을 잃지 않도록 교체를 미뤄야 함).
    """
    content = await _download_youtube_thumbnail(youtube_video_id)
    if not content:
        logger.error(f"[원본 보관] 영상 {youtube_video_id}의 현재 썸네일을 받지 못했습니다.")
        return None

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    raw_path = os.path.join(UPLOAD_DIR, f"original_{youtube_video_id}_{uuid.uuid4().hex[:8]}.img")
    try:
        with open(raw_path, "wb") as f:
            f.write(content)
        with Image.open(raw_path) as img:
            img.verify()
        final_path, *_ = process_image_for_youtube(raw_path)
    except Exception as e:
        logger.error(f"[원본 보관] 영상 {youtube_video_id} 썸네일 처리 실패: {e}")
        if os.path.exists(raw_path):
            os.remove(raw_path)
        return None

    return await publish_local_image(final_path, os.path.basename(final_path))
