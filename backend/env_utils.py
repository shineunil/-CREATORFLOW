import os


def is_dev_environment() -> bool:
    """로컬 개발 환경인지 판별합니다 (프로덕션 전용 가드에 사용)."""
    if os.getenv("ALLOW_TEST_UPGRADE", "").lower() in ("1", "true", "yes"):
        return True
    backend = os.getenv("BACKEND_URL", "http://localhost:8000")
    return "localhost" in backend or "127.0.0.1" in backend
