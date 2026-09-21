from fastapi import APIRouter, Request, HTTPException, Depends
import os, logging, hmac, hashlib, json
from sqlalchemy.orm import Session
from database import get_db
from models import User, PlanType

logger = logging.getLogger(__name__)
router = APIRouter()


def _verify_paddle_signature(body: bytes, header: str, secret: str) -> bool:
    """Paddle v2 웹훅 서명 검증. header 형식: ts=TIMESTAMP;h1=HMAC_SHA256"""
    try:
        parts = dict(p.split("=", 1) for p in header.split(";"))
        ts = parts.get("ts", "")
        h1 = parts.get("h1", "")
        signed = f"{ts}:{body.decode()}"
        expected = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, h1)
    except Exception:
        return False


@router.post("/api/webhook/paddle")
async def paddle_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    sig_header = request.headers.get("Paddle-Signature", "")
    secret = os.getenv("PADDLE_WEBHOOK_SECRET", "")

    if secret:
        if not _verify_paddle_signature(body, sig_header, secret):
            logger.warning("[Paddle Webhook] 🚨 서명 검증 실패 - 위조 요청 차단!")
            raise HTTPException(status_code=400, detail="Invalid Paddle webhook signature")

    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = event.get("event_type", "")
    data = event.get("data", {})
    logger.info(f"[Paddle Webhook] 이벤트 수신: {event_type}")

    if event_type == "transaction.completed":
        custom_data = data.get("custom_data") or {}
        user_id = custom_data.get("user_id")
        customer_id = data.get("customer_id")
        subscription_id = data.get("subscription_id")

        user = None
        if user_id:
            try:
                user = db.query(User).filter(User.id == int(user_id)).first()
            except (ValueError, TypeError):
                pass

        if user:
            user.plan = PlanType.PRO
            if customer_id:
                user.stripe_customer_id = customer_id    # Paddle customer ID 재사용
            if subscription_id:
                user.stripe_subscription_id = subscription_id  # Paddle subscription ID 재사용
            db.commit()
            logger.info(f"[Paddle Webhook] ✅ user_id={user.id} ({user.email}) → PRO 업그레이드")
        else:
            logger.warning(f"[Paddle Webhook] 유저 찾기 실패 (user_id={user_id})")

    elif event_type in ("subscription.canceled", "subscription.paused"):
        subscription_id = data.get("id")
        user = db.query(User).filter(User.stripe_subscription_id == subscription_id).first() if subscription_id else None
        if user:
            user.plan = PlanType.BASIC
            db.commit()
            logger.info(f"[Paddle Webhook] ⬇️ user_id={user.id} → BASIC 다운그레이드")
        else:
            logger.warning(f"[Paddle Webhook] 구독 취소 - subscription_id로 유저 찾기 실패: {subscription_id}")

    elif event_type == "subscription.updated":
        # 구독 상태 변경 (예: paused → active 등)
        subscription_id = data.get("id")
        status = data.get("status", "")
        user = db.query(User).filter(User.stripe_subscription_id == subscription_id).first() if subscription_id else None
        if user and status == "active":
            user.plan = PlanType.PRO
            db.commit()
            logger.info(f"[Paddle Webhook] ✅ user_id={user.id} → PRO 복원 (구독 재활성)")

    return {"status": "success"}
