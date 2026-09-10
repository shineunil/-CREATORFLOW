import os
import logging
import httpx

logger = logging.getLogger(__name__)

# Render 등 대부분의 무료/저가 클라우드 호스팅은 스팸 방지 차원에서 아웃바운드 SMTP 포트
# 자체를 네트워크 레벨에서 막아버린다 (smtplib로 보내면 "[Errno 101] Network is unreachable").
# 로컬에서는 일반 인터넷이라 SMTP가 멀쩡히 되어서 이 문제를 못 잡아냈었다 - 실제로 라이브에서만
# 재현됐다. HTTPS로 통신하는 Resend API로 바꿔서 이 포트 차단 자체를 우회한다.
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "CreatorFlow <onboarding@resend.dev>")

def send_test_completion_email(user_email: str, video_title: str, winner_name: str, views_gained: int) -> dict:
    """
    A/B test completion email notification function.
    반환값: {"sent": bool, "simulated": bool} - RESEND_API_KEY 미설정 시에는 실제 발송 없이
    simulated=True로 표시되므로, 호출부에서 유저에게 "실제 발송 아님"을 명확히 알려야 한다.
    """
    if not user_email:
        logger.warning("Email missing")
        return {"sent": False, "simulated": False}

    subject = f"[CreatorFlow] A/B Test Completed! Winner: {winner_name}"
    html_content = f"""<div style="font-family: Arial, sans-serif; background-color: #0909b2; color: #f4f4f5; padding: 40px; border-radius: 16px;"><h2 style="color: #06b6d4;">A/B Experiment Completed</h2><p>Video: <strong>{video_title}</strong></p><hr style="border-color: #2727a;" /><div style="background-color: #18181b; padding: 20px; border-radius: 12px; border: 1px solid #06b6d4;"><h3 style="color: #22c5e;">Winner: {winner_name}</h3><p>Highest Views: +{views_gained} views</p></div></div>"""
    logger.info(f"[Email Notification] To: {user_email} winner={winner_name}")
    if not RESEND_API_KEY:
        logger.info("RESEND_API_KEY 미설정 - 시뮬레이션 모드로 처리 (실제 이메일 발송 안 됨)")
        return {"sent": True, "simulated": True}

    try:
        res = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={
                "from": RESEND_FROM_EMAIL,
                "to": [user_email],
                "subject": subject,
                "html": html_content,
            },
            timeout=10,
        )
        if res.status_code >= 400:
            logger.error(f"Email error: Resend API {res.status_code} - {res.text}")
            return {"sent": False, "simulated": False}
        logger.info(f"{user_email} email sent!")
        return {"sent": True, "simulated": False}
    except Exception as e:
        logger.error(f"Email error: {e}")
        return {"sent": False, "simulated": False}
