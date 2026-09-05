from fastapi import APIRouter, Request, HTTPException
import json
import os
import hmac
import hashlib
import logging
from sqlalchemy.orm import Session
from database import get_db
from models import User, PlanType
from fastapi import Depends

logger = logging.getLogger(__name__)
router = APIRouter()

def verify_paddle_signature(body: bytes, signature_header: str, secret: str) -> bool:
    """
    Paddle 웹훅 서명을 검증합니다.
    Paddle은 'Paddle-Signature' 헤더에 'ts=타임스탬프;h1=서명해시' 형식으로 보냅니다.
    """
    if not secret or not signature_header:
        return False

    try:
        parts = dict(part.split("=", 1) for part in signature_header.split(";"))
        ts = parts.get("ts")
        h1 = parts.get("h1")
        if not ts or not h1:
            return False

        signed_payload = f"{ts}:{body.decode('utf-8')}"
        computed = hmac.new(
            secret.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(computed, h1)
    except Exception as e:
        logger.error(f"[Paddle Webhook] 서명 검증 중 오류: {e}")
        return False

@router.post("/api/webhooks/paddle")
async def paddle_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()

    # 🔒 Paddle 서명 검증 (보안 핵심)
    secret = os.getenv("PADDLE_WEBHOOK_SECRET", "")
    signature_header = request.headers.get("Paddle-Signature", "")

    if secret:  # 시크릿이 설정된 경우에만 서명 검증 (로컬 개발 환경 예외 처리)
        if not verify_paddle_signature(body, signature_header, secret):
            logger.warning("[Paddle Webhook] 🚨 서명 검증 실패 - 위조 요청 차단!")
            raise HTTPException(status_code=401, detail="Invalid Paddle webhook signature")

    try:
        payload = json.loads(body.decode("utf-8"))
        event_type = payload.get("event_type")
        data = payload.get("data", {})

        logger.info(f"[Paddle Webhook] 이벤트 수신: {event_type}")

        # 이메일 추출 (custom_data 우선, 없으면 customer 정보에서 추출)
        custom_data = data.get("custom_data") or {}
        email = custom_data.get("email")

        if not email:
            email = data.get("customer", {}).get("email")

        if not email:
            logger.info("[Paddle Webhook] 이메일 정보 없음. 무시합니다.")
            return {"status": "ignored"}

        logger.info(f"[Paddle Webhook] {event_type} → {email}")

        user = db.query(User).filter(User.email == email).first()
        if not user:
            logger.warning(f"[Paddle Webhook] 유저를 찾을 수 없음: {email}")
            return {"status": "user_not_found"}

        if event_type in ["subscription.created", "subscription.updated", "subscription.activated"]:
            status = data.get("status")
            if status in ["active", "trialing"]:
                user.plan = PlanType.PRO
                db.commit()
                logger.info(f"[Paddle Webhook] ✅ {email} → PRO 업그레이드 완료")

        elif event_type in ["subscription.canceled", "subscription.past_due"]:
            user.plan = PlanType.BASIC
            db.commit()
            logger.info(f"[Paddle Webhook] ⬇️ {email} → BASIC 다운그레이드 완료")

        return {"status": "success"}

    except json.JSONDecodeError:
        logger.error("[Paddle Webhook] 잘못된 JSON 형식")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except Exception as e:
        logger.error(f"[Paddle Webhook] 처리 중 오류: {e}")
        return {"status": "error"}
