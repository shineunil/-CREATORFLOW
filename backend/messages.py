"""
사용자에게 보이는 백엔드 메시지(오류 detail, 응답 message)의 영어·한국어 문구.
요청 언어는 프론트가 보내는 Accept-Language 헤더로 정하고(main.py 미들웨어가 설정),
요청 밖(스케줄러의 이메일 등)에서는 msg(..., locale=user.locale)처럼 직접 넘긴다.
"""
from contextvars import ContextVar

SUPPORTED_LOCALES = ("en", "ko")
DEFAULT_LOCALE = "en"

_request_locale: ContextVar[str] = ContextVar("request_locale", default=DEFAULT_LOCALE)


def locale_from_accept_language(header: str | None) -> str:
    if not header:
        return DEFAULT_LOCALE
    ranked = []
    for part in header.split(","):
        tag, *params = part.strip().split(";")
        q = 1.0
        for p in params:
            p = p.strip()
            if p.startswith("q="):
                try:
                    q = float(p[2:])
                except ValueError:
                    q = 0.0
        ranked.append((q, tag.strip().lower().split("-")[0]))
    for _, base in sorted(ranked, key=lambda r: -r[0]):
        if base in SUPPORTED_LOCALES:
            return base
    return DEFAULT_LOCALE


def set_request_locale(locale: str) -> None:
    _request_locale.set(locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE)


def current_locale() -> str:
    return _request_locale.get()


def normalize_locale(locale: str | None) -> str:
    return locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE


def msg(key: str, locale: str | None = None, **kwargs) -> str:
    text = MESSAGES[key][normalize_locale(locale) if locale else _request_locale.get()]
    return text.format(**kwargs) if kwargs else text


MESSAGES: dict[str, dict[str, str]] = {
    # --- 계정·인증 ---
    "admin_forbidden": {"en": "You don't have admin access.", "ko": "관리자 권한이 없습니다."},
    "oauth_token_failed": {"en": "Couldn't get a sign-in token from Google. Please try again.", "ko": "구글에서 로그인 토큰을 받지 못했습니다. 다시 시도해 주세요."},
    "google_userinfo_failed": {"en": "Couldn't load your Google profile. Please try again.", "ko": "구글 사용자 정보를 불러오지 못했습니다. 다시 시도해 주세요."},
    "google_account_failed": {"en": "Couldn't read your Google account details.", "ko": "구글 계정 정보를 가져오지 못했습니다."},
    "google_email_missing": {"en": "Couldn't read the email address from your Google account.", "ko": "구글 계정에서 이메일 정보를 가져오지 못했습니다."},
    "logout_success": {"en": "You've been logged out.", "ko": "로그아웃되었습니다."},
    "invalid_auth_code": {"en": "The sign-in code is invalid or has expired. Please sign in again.", "ko": "유효하지 않거나 만료된 인증 코드입니다. 다시 로그인해 주세요."},
    "user_not_found": {"en": "User not found.", "ko": "사용자를 찾을 수 없습니다."},
    "unsupported_locale": {"en": "Unsupported language.", "ko": "지원하지 않는 언어입니다."},

    # --- 채널 ---
    "channel_not_owned": {"en": "Channel not found, or it doesn't belong to this account.", "ko": "채널을 찾을 수 없거나 이 계정 소유가 아닙니다."},
    "channel_disconnected_ok": {"en": "The YouTube channel has been disconnected.", "ko": "YouTube 채널 연동이 해제되었습니다."},
    "channel_not_found": {"en": "Channel not found.", "ko": "채널을 찾을 수 없습니다."},
    "channel_is_disconnected": {"en": "This channel is disconnected.", "ko": "연동이 해제된 채널입니다."},
    "youtube_reconnect_required": {"en": "Your YouTube connection has expired. Please reconnect your channel.", "ko": "YouTube 연동이 만료되었습니다. 재연동이 필요합니다."},
    "youtube_relogin_required": {"en": "Your YouTube connection has expired. Please sign in again to reconnect your channel.", "ko": "YouTube 연동이 만료되었습니다. 다시 로그인해 채널을 재연동해 주세요."},
    "permission_check_failed": {"en": "Something went wrong while checking permissions.", "ko": "권한 확인 중 오류가 발생했습니다."},
    "no_channel_token": {"en": "No connected channel or sign-in token was found.", "ko": "연동된 채널이나 인증 토큰이 없습니다."},

    # --- 테스트 생성·요금제 한도 ---
    "max_concurrent_per_channel": {"en": "Each channel can run at most {limit} tests at the same time.", "ko": "채널당 동시 진행 가능한 테스트는 최대 {limit}개입니다."},
    "basic_one_active": {"en": "BASIC plan allows only 1 active test at a time. Upgrade to PRO for unlimited concurrent tests.", "ko": "BASIC 요금제는 한 번에 테스트 1개만 진행할 수 있습니다. 동시에 여러 테스트를 하려면 PRO로 업그레이드하세요."},
    "basic_monthly_limit": {"en": "You've used all 4 free tests this month. Upgrade to PRO for unlimited tests.", "ko": "이번 달 무료 테스트 4회를 모두 사용했습니다. 무제한으로 테스트하려면 PRO로 업그레이드하세요."},
    "basic_min_interval": {"en": "BASIC plan requires a minimum {hours}-hour swap interval. Shorter intervals are a PRO feature.", "ko": "BASIC 요금제의 최소 교체 주기는 {hours}시간입니다. 더 짧은 주기는 PRO 전용 기능입니다."},
    "basic_max_variants": {"en": "BASIC plan allows up to 3 thumbnail variants (A/B/C). Upgrade to PRO for up to 5 variants.", "ko": "BASIC 요금제는 썸네일 후보를 3개(A/B/C)까지 쓸 수 있습니다. 최대 5개까지 쓰려면 PRO로 업그레이드하세요."},
    "video_other_channel": {"en": "This video is already linked to another channel and cannot be used for a new test.", "ko": "이 영상은 이미 다른 채널에 연결되어 있어 새 테스트에 사용할 수 없습니다."},
    "test_started": {"en": "Your A/B test has started!", "ko": "A/B 테스트를 시작했습니다!"},

    # --- 테스트 조작 ---
    "test_not_found_or_forbidden": {"en": "Test not found, or you don't have access to it.", "ko": "테스트를 찾을 수 없거나 권한이 없습니다."},
    "test_not_found": {"en": "Test not found.", "ko": "테스트를 찾을 수 없습니다."},
    "forbidden": {"en": "You don't have permission to do this.", "ko": "권한이 없습니다."},
    "only_running_can_stop": {"en": "Only running tests can be stopped.", "ko": "진행 중인 테스트만 중단할 수 있습니다."},
    "test_stopped": {"en": "The test has been stopped and finalized.", "ko": "테스트를 중단하고 종료했습니다."},
    "only_running_can_swap": {"en": "Only running tests can be swapped.", "ko": "진행 중인 테스트만 교체할 수 있습니다."},
    "manual_swap_once": {"en": "Manual swap can only be used once per test.", "ko": "수동 즉시 교체는 테스트당 1회만 사용할 수 있습니다."},
    "youtube_phone_verification": {"en": "YouTube account verification is required. Please complete phone verification at youtube.com/features.", "ko": "YouTube 계정 인증이 필요합니다. youtube.com/features 에서 전화번호 인증을 완료해 주세요."},
    "thumbnail_swap_failed": {"en": "Failed to swap the YouTube thumbnail. The scheduler will retry automatically shortly.", "ko": "YouTube 썸네일 교체에 실패했습니다. 잠시 후 스케줄러가 자동으로 재시도합니다."},
    "swap_done": {"en": "The thumbnail/title was swapped right away.", "ko": "썸네일/제목을 바로 교체했습니다."},
    "test_cancelled": {"en": "The test was cancelled and the original was restored.", "ko": "테스트가 취소되고 원본으로 복구되었습니다."},

    # --- 업로드·썸네일 생성 ---
    "file_type_not_allowed": {"en": "This file type isn't allowed. Allowed: {allowed}", "ko": "허용되지 않는 파일 형식입니다. 허용: {allowed}"},
    "content_type_not_allowed": {"en": "This content type isn't allowed. Please upload an image file.", "ko": "허용되지 않는 Content-Type입니다. 이미지 파일만 업로드할 수 있습니다."},
    "file_too_large": {"en": "The file is larger than 10MB.", "ko": "파일 크기가 10MB를 초과합니다."},
    "invalid_image": {"en": "The file isn't a valid image.", "ko": "파일 내용이 올바른 이미지 형식이 아닙니다."},
    "image_format_not_allowed": {"en": "This image format isn't allowed (detected: {fmt}).", "ko": "허용되지 않는 이미지 형식입니다 (감지된 형식: {fmt})."},
    "headline_required": {"en": "Please enter a headline.", "ko": "문구를 입력해 주세요."},
    "headline_too_long": {"en": "Please keep the headline within 60 characters.", "ko": "문구는 60자 이내로 입력해 주세요."},
    "thumbnail_generation_failed": {"en": "Something went wrong while generating the thumbnail.", "ko": "썸네일 생성 중 오류가 발생했습니다."},
    "filename_missing": {"en": "No file name was provided.", "ko": "파일명이 제공되지 않았습니다."},
    "filename_invalid": {"en": "Invalid file name.", "ko": "올바르지 않은 파일명입니다."},
    "file_not_found": {"en": "File not found.", "ko": "파일을 찾을 수 없습니다."},

    # --- 결제 ---
    "payments_not_configured": {"en": "Payments aren't set up yet.", "ko": "결제 시스템이 아직 설정되지 않았습니다."},
    "checkout_open_failed": {"en": "Couldn't open the checkout. Please try again.", "ko": "결제창을 여는 데 실패했습니다. 다시 시도해 주세요."},
    "upgrade_test_disabled": {"en": "Test upgrade is disabled in production.", "ko": "운영 환경에서는 테스트 업그레이드를 사용할 수 없습니다."},
    "upgraded_pro": {"en": "You've been upgraded to the PRO plan!", "ko": "PRO 요금제로 업그레이드되었습니다!"},
    "no_billing_history": {"en": "No billing history found. Please complete a PRO payment first.", "ko": "결제 내역이 없습니다. PRO 결제를 진행한 뒤 다시 시도해 주세요."},
    "billing_portal_failed": {"en": "Couldn't open the billing portal.", "ko": "결제 관리 페이지를 여는 데 실패했습니다."},

    # --- 알림 이메일 ---
    "invalid_email": {"en": "Invalid email address.", "ko": "올바르지 않은 이메일 주소입니다."},
    "email_send_failed": {"en": "Failed to send the email. (Resend {status})", "ko": "이메일 발송에 실패했습니다. (Resend {status})"},
    "email_send_error": {"en": "Something went wrong while sending the email.", "ko": "이메일 발송 중 오류가 발생했습니다."},
    "verification_not_found": {"en": "No verification request found. Please request a new code.", "ko": "인증 요청을 찾을 수 없습니다. 새 코드를 요청해 주세요."},
    "verification_expired": {"en": "Verification code expired. Please request a new one.", "ko": "인증 코드가 만료되었습니다. 새 코드를 요청해 주세요."},
    "verification_too_many": {"en": "Too many attempts. Please request a new code.", "ko": "시도 횟수를 초과했습니다. 새 코드를 요청해 주세요."},
    "verification_incorrect": {"en": "Incorrect verification code. {remaining} attempt(s) remaining.", "ko": "인증 코드가 올바르지 않습니다. 남은 시도 횟수: {remaining}회"},
    "test_email_simulated": {"en": "Email isn't configured, so this ran in simulation mode. No email was actually sent to '{email}'.", "ko": "이메일 발송이 설정되어 있지 않아 시뮬레이션 모드로 처리했습니다. '{email}'로 실제 이메일은 발송되지 않았습니다."},
    "test_email_sent": {"en": "An A/B test winner notification was sent to '{email}'!", "ko": "'{email}' 주소로 A/B 테스트 승자 확정 알림 메일을 보냈습니다!"},
    "test_email_failed": {"en": "Failed to send the email.", "ko": "이메일 발송에 실패했습니다."},
    "test_email_sample_title": {"en": "Us in the Photo (Behind the Scenes)", "ko": "사진 속 우리 (비하인드 스페셜)"},
    "test_email_sample_winner": {"en": "Variation B (neon caption thumbnail)", "ko": "Variation B (네온 자막 강조 썸네일)"},

    # --- 썸네일 분석 피드백 (ml_scorer) ---
    "score_image_missing": {"en": "Image not found.", "ko": "이미지를 찾을 수 없습니다."},
    "score_great": {"en": "A very strong, eye-catching thumbnail overall!", "ko": "전반적으로 시선을 사로잡는 매우 훌륭한 썸네일입니다!"},
    "score_ok": {"en": "A decent thumbnail — a bit more contrast would help it stand out.", "ko": "무난한 썸네일이지만 조금 더 대비를 주면 눈에 띌 수 있습니다."},
    "score_weak": {"en": "It's dark or low-impact, so it's likely to get lost while scrolling.", "ko": "어둡거나 눈에 띄지 않아 스크롤 시 묻힐 확률이 높습니다."},
    "score_too_dark": {"en": "Brightness is too low, so it may be hard to see on mobile. Try brightening it.", "ko": "명도가 너무 낮아(어두움) 모바일에서 잘 안 보일 수 있습니다. 밝기를 올리세요."},
    "score_too_bright": {"en": "It's too bright and glaring. Try toning it down.", "ko": "명도가 너무 높아 눈이 부십니다. 톤다운이 필요합니다."},
    "score_colorful": {"en": "Vivid colors help grab attention.", "ko": "색채가 화려하여 시선을 끌기 좋습니다."},
    "score_error": {"en": "Error during analysis: {error}", "ko": "분석 중 오류 발생: {error}"},

    # --- 이메일 본문 ---
    "email_completion_subject": {"en": "[ThumbnailFlow] A/B Test Completed! Winner: {winner}", "ko": "[ThumbnailFlow] A/B 테스트 완료! 승자: {winner}"},
    "email_completion_heading": {"en": "A/B Experiment Completed", "ko": "A/B 테스트가 끝났습니다"},
    "email_completion_video": {"en": "Video", "ko": "영상"},
    "email_completion_winner": {"en": "Winner", "ko": "승자"},
    "email_completion_views": {"en": "Highest Views: +{views} views", "ko": "최고 조회수 증가: +{views}회"},
    "email_completion_thumb_alt": {"en": "Winning thumbnail", "ko": "이긴 썸네일"},
    "email_completion_watch": {"en": "Watch on YouTube", "ko": "영상 보러 가기"},
    "email_verify_subject": {"en": "[ThumbnailFlow] Email Verification Code", "ko": "[ThumbnailFlow] 이메일 인증 코드"},
    "email_verify_heading": {"en": "ThumbnailFlow Email Verification", "ko": "ThumbnailFlow 이메일 인증"},
    "email_verify_code_label": {"en": "Your verification code:", "ko": "인증 코드:"},
    "email_verify_expires": {"en": "This code expires in 10 minutes.", "ko": "이 코드는 10분 후에 만료됩니다."},
}
