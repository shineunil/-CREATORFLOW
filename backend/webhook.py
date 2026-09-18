from fastapi import APIRouter, Request, HTTPException
import os
import logging
import stripe
from sqlalchemy.orm import Session
from database import get_db
from models import User, PlanType
from fastapi import Depends
from env_utils import is_dev_environment

logger = logging.getLogger(__name__)
router = APIRouter()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


@router.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    if not secret and not is_dev_environment():
        logger.error("[Stripe Webhook] 🚨 STRIPE_WEBHOOK_SECRET 미설정 - 프로덕션에서 웹훅 거부")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    if secret:
        try:
            event = stripe.Webhook.construct_event(body, sig_header, secret)
            event = event.to_dict()  # Stripe SDK v8+ returns object, not dict
        except stripe.SignatureVerificationError:
            logger.warning("[Stripe Webhook] 🚨 서명 검증 실패 - 위조 요청 차단!")
            raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid payload")
    else:
        import json
        event = json.loads(body)

    event_type = event["type"]
    data_obj = event["data"]["object"]
    logger.info(f"[Stripe Webhook] 이벤트 수신: {event_type}")

    if event_type == "checkout.session.completed":
        customer_id = data_obj.get("customer")
        subscription_id = data_obj.get("subscription")
        customer_email = data_obj.get("customer_email") or data_obj.get("customer_details", {}).get("email")
        user_id = data_obj.get("metadata", {}).get("user_id")

        # M-4: metadata.user_id만 사용. email 폴백은 타 유저의 이메일로 오인 업그레이드 위험이 있다.
        user = None
        if user_id:
            try:
                user = db.query(User).filter(User.id == int(user_id)).first()
            except (ValueError, TypeError):
                pass

        if user:
            user.plan = PlanType.PRO
            if customer_id:
                user.stripe_customer_id = customer_id
            if subscription_id:
                user.stripe_subscription_id = subscription_id
            db.commit()
            logger.info(f"[Stripe Webhook] ✅ user_id={user.id} ({user.email}) → PRO 업그레이드 완료")
        else:
            logger.warning(f"[Stripe Webhook] 유저를 찾을 수 없음 (user_id={user_id}, email={customer_email})")

    elif event_type == "customer.subscription.deleted":
        customer_id = data_obj.get("customer")
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first() if customer_id else None
        if user:
            user.plan = PlanType.BASIC
            db.commit()
            logger.info(f"[Stripe Webhook] ⬇️ user_id={user.id} → BASIC 다운그레이드 (구독 취소)")
        else:
            logger.warning(f"[Stripe Webhook] 구독 취소 이벤트 - customer_id로 유저 찾기 실패: {customer_id}")

    elif event_type == "invoice.payment_failed":
        customer_id = data_obj.get("customer")
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first() if customer_id else None
        if user:
            user.plan = PlanType.BASIC
            db.commit()
            logger.info(f"[Stripe Webhook] ⬇️ user_id={user.id} → BASIC 다운그레이드 (결제 실패)")

    return {"status": "success"}
