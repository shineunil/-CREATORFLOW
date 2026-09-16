import os


def is_dev_environment() -> bool:
    """로컬 개발 환경인지 판별합니다 (프로덕션 전용 가드에 사용)."""
    backend = os.getenv("BACKEND_URL", "http://localhost:8000")
    return "localhost" in backend or "127.0.0.1" in backend


def allow_test_upgrade() -> bool:
    """테스트용 PRO 업그레이드를 허용할지 판별합니다 (로컬 개발 전용).
    웹훅 서명 검증과는 독립적으로 관리해 프로덕션에서 실수로 활성화되지 않도록 합니다."""
    return is_dev_environment() and os.getenv("ALLOW_TEST_UPGRADE", "").lower() in ("1", "true", "yes")
