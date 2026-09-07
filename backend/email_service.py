import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "noreply@creatorflow.io")

def send_test_completion_email(user_email: str, video_title: str, winner_name: str, views_gained: int) -> dict:
    """
    A/B test completion email notification function.
    반환값: {"sent": bool, "simulated": bool} - SMTP 미설정 시에는 실제 발송 없이
    simulated=True로 표시되므로, 호출부에서 유저에게 "실제 발송 아님"을 명확히 알려야 한다.
    """
    if not user_email:
        logger.warning("Email missing")
        return {"sent": False, "simulated": False}

    subject = f"[CreatorFlow] A/B Test Completed! Winner: {winner_name}"
    html_content = f"""<div style="font-family: Arial, sans-serif; background-color: #0909b2; color: #f4f4f5; padding: 40px; border-radius: 16px;"><h2 style="color: #06b6d4;">A/B Experiment Completed</h2><p>Video: <strong>{video_title}</strong></p><hr style="border-color: #2727a;" /><div style="background-color: #18181b; padding: 20px; border-radius: 12px; border: 1px solid #06b6d4;"><h3 style="color: #22c5e;">Winner: {winner_name}</h3><p>Highest Views: +{views_gained} views</p></div></div>"""
    logger.info(f"[Email Notification] To: {user_email} winner={winner_name}")
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.info("SMTP 미설정 - 시뮬레이션 모드로 처리 (실제 이메일 발송 안 됨)")
        return {"sent": True, "simulated": True}

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = user_email
        msg.attach(MIMEText(html_content, "html"))
        # timeout 없이 열면 SMTP 서버가 응답 없이 패킷만 씹을 때(방화벽 등) 무한 대기할 수 있다.
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SENDER_EMAIL, [user_email], msg.as_string())
        logger.info(f"{user_email} email sent!")
        return {"sent": True, "simulated": False}
    except Exception as e:
        logger.error(f"Email error: {e}")
        return {"sent": False, "simulated": False}
