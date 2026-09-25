import os
import logging
import httpx
import html as _html
import urllib.parse
from messages import msg

logger = logging.getLogger(__name__)

# Render 등 대부분의 무료/저가 클라우드 호스팅은 스팸 방지 차원에서 아웃바운드 SMTP 포트
# 자체를 네트워크 레벨에서 막아버린다 (smtplib로 보내면 "[Errno 101] Network is unreachable").
# 로컬에서는 일반 인터넷이라 SMTP가 멀쩡히 되어서 이 문제를 못 잡아냈었다 - 실제로 라이브에서만
# 재현됐다. HTTPS로 통신하는 Resend API로 바꿔서 이 포트 차단 자체를 우회한다.
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "ThumbnailFlow <onboarding@resend.dev>")

def send_test_completion_email(
    user_email: str,
    video_title: str,
    winner_name: str,
    views_gained: int,
    locale: str | None = None,
    thumbnail_url: str | None = None,
    youtube_video_id: str | None = None,
) -> dict:
    """
    A/B test completion email notification function.
    반환값: {"sent": bool, "simulated": bool} - RESEND_API_KEY 미설정 시에는 실제 발송 없이
    simulated=True로 표시되므로, 호출부에서 유저에게 "실제 발송 아님"을 명확히 알려야 한다.
    """
    if not user_email:
        logger.warning("Email missing")
        return {"sent": False, "simulated": False}

    safe_title = _html.escape(str(video_title))
    safe_winner = _html.escape(str(winner_name))
    lang = locale or "en"
    subject = msg("email_completion_subject", lang, winner=winner_name)

    # 메일 프로그램이 직접 불러올 수 있는 공개 https 주소(Cloudinary·유튜브)일 때만 이미지를 넣는다.
    thumbnail_html = ""
    if thumbnail_url and thumbnail_url.startswith("https://"):
        thumbnail_html = (
            f'<img src="{_html.escape(thumbnail_url, quote=True)}" alt="{msg("email_completion_thumb_alt", lang)}" width="480" '
            f'style="display: block; width: 100%; max-width: 480px; height: auto; border-radius: 8px; margin: 0 0 16px;" />'
        )
    button_html = ""
    if youtube_video_id:
        video_url = f"https://www.youtube.com/watch?v={urllib.parse.quote(youtube_video_id, safe='')}"
        button_html = (
            f'<p style="margin: 24px 0 0;"><a href="{video_url}" target="_blank" '
            f'style="display: inline-block; background-color: #06b6d4; color: #09090b; font-weight: bold; text-decoration: none; padding: 12px 24px; border-radius: 9999px;">'
            f'{msg("email_completion_watch", lang)}</a></p>'
        )

    html_content = f"""<div style="font-family: Arial, sans-serif; background-color: #09090b; color: #f4f4f5; padding: 40px; border-radius: 16px;"><h2 style="color: #06b6d4;">{msg('email_completion_heading', lang)}</h2><p>{msg('email_completion_video', lang)}: <strong>{safe_title}</strong></p><hr style="border-color: #27272a;" /><div style="background-color: #18181b; padding: 20px; border-radius: 12px; border: 1px solid #06b6d4;">{thumbnail_html}<h3 style="color: #22d3ee;">{msg('email_completion_winner', lang)}: {safe_winner}</h3><p>{msg('email_completion_views', lang, views=views_gained)}</p></div>{button_html}</div>"""
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
