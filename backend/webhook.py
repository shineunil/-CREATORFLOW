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
from env_utils import is_dev_environment

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
    if not secret and not is_dev_environment():
        logger.error("[Paddle Webhook] 🚨 PADDLE_WEBHOOK_SECRET 미설정 - 프로덕션에서 웹훅 거부")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

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

        # 환불(adjustment) 이벤트는 subscription 이벤트와 페이로드 구조가 달라 이메일/custom_data가
        # 없고, customer_id로만 유저를 특정할 수 있다. 그래서 다른 이벤트들과 분리해서 먼저 처리한다.
        if event_type == "adjustment.updated":
            if data.get("action") == "refund" and data.get("status") == "approved":
                customer_id = data.get("customer_id")
                user = db.query(User).filter(User.paddle_customer_id == customer_id).first() if customer_id else None
                if not user:
                    logger.warning(f"[Paddle Webhook] 환불 승인됐지만 customer_id로 유저를 찾을 수 없음: {customer_id}")
                    return {"status": "user_not_found"}

                # 전액 환불이면 즉시 PRO 권한을 회수한다. 부분 환불(굿윌 크레딧 등)은 구독이 여전히
                # 유효한 경우가 많아 이것만으로 다운그레이드하지 않는다 - 실제 구독 취소는 별도로
                # subscription.canceled 이벤트가 온다.
                if data.get("type") == "full":
                    user.plan = PlanType.BASIC
                    db.commit()
                    logger.info(f"[Paddle Webhook] ⬇️ 환불 승인으로 유저(customer_id={customer_id})가 BASIC으로 다운그레이드 되었습니다.")
                else:
                    logger.info(f"[Paddle Webhook] 부분 환불 승인 (customer_id={customer_id}) - 플랜 변경 없음.")
            return {"status": "success"}

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
            # 고객 포털(구독 취소/다운그레이드/결제 내역 조회) 딥링크를 생성하려면 이 두 ID가 필요하다.
            # 구독이 갱신/변경될 때마다 최신 값으로 갱신해둔다.
            customer_id = data.get("customer_id")
            subscription_id = data.get("id")
            if customer_id:
                user.paddle_customer_id = customer_id
            if subscription_id:
                user.paddle_subscription_id = subscription_id
            if status in ["active", "trialing"]:
                user.plan = PlanType.PRO
                db.commit()
                logger.info(f"[Paddle Webhook] ✅ {email} → PRO 업그레이드 완료")
            else:
                db.commit()

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
