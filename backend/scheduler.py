import asyncio
import logging
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Import models and APIs safely
from models import ABTest, TestStatus, Variation, MetricLog
from youtube_api import (
    get_video_views,
    update_youtube_thumbnail,
    update_youtube_title,
    TokenRevokedError,
    ThumbnailPermissionError,
)
from metrics_utils import compute_variation_vph
from billing import expire_due_plans
from rotation import pick_next_variation
from thumbnail_store import is_youtube_native_url, snapshot_original_thumbnail
from test_policy import (
    has_enough_cycles,
    has_enough_sample,
    MIN_CYCLES,
    MIN_SAMPLE_VIEWS,
    MAX_AUTO_EXTENSIONS,
    warmup_minutes_for,
)
from quota_guard import has_quota_for, record_usage, check_and_reserve_usage, COST_VIDEOS_LIST, COST_VIDEOS_UPDATE, COST_THUMBNAILS_SET

# 로그 형식·단계는 main.py에서 한 번에 정한다 (LOG_LEVEL 환경 변수).
logger = logging.getLogger(__name__)


def _live_title(all_vars, current_var) -> str:
    """지금 유튜브에 걸려 있는 제목. 교체한 적이 없으면 원본(A)의 제목 = 테스트 시작 때의 영상 제목."""
    if current_var is not None:
        return current_var.title_text or ""
    control = next((v for v in all_vars if v.is_control), None)
    return (control.title_text or "") if control else ""


def _title_differs(new_title, live_title) -> bool:
    """새 제목이 있고 지금 제목과 다를 때만 제목 교체(쿼터 51)가 필요하다."""
    return bool(new_title) and new_title.strip() != (live_title or "").strip()

_JOB_ID = "ab-test-tick"
RETRY_MINUTES = 10       # 교체 실패·쿼터 부족 등으로 이번에 처리하지 못한 일을 다시 볼 간격
MAX_SLEEP_MINUTES = 60   # 할 일이 없어도 이 간격으로는 한 번 확인한다 (놓친 변화가 있어도 오래 멈추지 않게)
WAKE_BUFFER_SECONDS = 5  # 기한 직후에 깨어나야 "기한이 지났다"로 판정된다


def _as_utc(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def next_wake_time(tests, now: datetime) -> datetime:
    """
    진행 중인 테스트들이 다음에 할 일(워밍업 끝 측정 시작, 교체, 테스트 종료)이 생기는 가장 이른 시각.
    예전엔 10분마다 DB를 훑어서 측정 시작·교체가 최대 10분씩 늦었고(30분 주기면 측정 시간의 2/3가 버려짐),
    할 일이 없어도 DB를 깨워 Neon 무료 컴퓨트 시간을 계속 썼다. 이제는 필요한 시각에만 깨어난다.
    """
    due = []
    for test in tests:
        if test.end_time:
            due.append(_as_utc(test.end_time))
        channel = test.video.channel if test.video else None
        if channel is not None and channel.needs_reconnect:
            continue  # 재연동 전까지는 교체하지 않는다 (종료 시각만 챙긴다)
        if test.swap_failed:
            due.append(now + timedelta(minutes=RETRY_MINUTES))
            continue
        last = _as_utc(test.last_swapped_at) if test.last_swapped_at else now
        if not test.warmup_captured:
            due.append(last + timedelta(minutes=warmup_minutes_for(test.swap_interval_minutes)))
        due.append(last + timedelta(minutes=test.swap_interval_minutes or 0))

    wake = now + timedelta(minutes=MAX_SLEEP_MINUTES)
    for moment in due:
        if moment <= now:
            # 기한이 지났는데 이번에 처리하지 못했다 (쿼터 부족, 일시 오류 등) - 곧바로 다시 돌지 않고 잠시 뒤 재시도
            moment = now + timedelta(minutes=RETRY_MINUTES)
        wake = min(wake, moment)
    return wake + timedelta(seconds=WAKE_BUFFER_SECONDS)


class AVSchedulerEngine:
    def __init__(self, db_session_maker):
        self.scheduler = AsyncIOScheduler()
        self.db_session_maker = db_session_maker
        self._wake_requested = False
        # 서버가 켜지면 곧 한 번 확인하고, 그 뒤로는 다음 할 일이 생기는 시각에 맞춰 스스로 다시 예약한다.
        self._schedule(datetime.now(timezone.utc) + timedelta(seconds=10))

    def _schedule(self, run_at: datetime):
        self.scheduler.add_job(
            self.check_and_swap_variations, "date", run_date=run_at, id=_JOB_ID, replace_existing=True,
            # 서버가 잠깐 바빠 몇 초 늦어도 건너뛰지 않게 (건너뛰면 다음 예약이 끊긴다)
            misfire_grace_time=3600, coalesce=True,
        )

    def wake_soon(self):
        """테스트를 만들거나 직접 교체한 직후처럼 일정이 바뀌었을 때, 몇 초 뒤 다시 확인하게 한다."""
        self._wake_requested = True
        self._schedule(datetime.now(timezone.utc) + timedelta(seconds=3))

    def start(self):
        logger.info("🚀 A/B Test Scheduler Engine Started...")
        self.scheduler.start()

    async def check_and_swap_variations(self):
        self._wake_requested = False
        next_run = datetime.now(timezone.utc) + timedelta(minutes=RETRY_MINUTES)
        try:
            self._expire_canceled_plans()
            await self._run_due_tests()
            next_run = self._compute_next_run()
        finally:
            # 처리 중에 새 테스트가 생겼으면(wake_soon) 그 테스트도 곧 보도록, 아니면 다음 할 일 시각에 맞춰 예약
            if self._wake_requested:
                next_run = datetime.now(timezone.utc) + timedelta(seconds=3)
                self._wake_requested = False
            self._schedule(next_run)
            logger.info(f"다음 확인: {next_run.isoformat(timespec='seconds')}")

    def _expire_canceled_plans(self):
        """해지 후 결제 기간이 끝난 PRO를 BASIC으로. 어차피 깨어난 김에 확인한다 (DB를 따로 깨우지 않음)."""
        session = self.db_session_maker()
        try:
            expire_due_plans(session, datetime.now(timezone.utc))
        except Exception as e:
            session.rollback()
            logger.error(f"해지 플랜 만료 처리 실패 - 다음 확인 때 다시 시도합니다: {e}")
        finally:
            session.close()

    def _compute_next_run(self) -> datetime:
        session = self.db_session_maker()
        try:
            running = session.query(ABTest).filter(ABTest.status == TestStatus.RUNNING, ABTest.is_deleted == False).all()
            return next_wake_time(running, datetime.now(timezone.utc))
        except Exception as e:
            logger.error(f"다음 확인 시각 계산 실패 - {RETRY_MINUTES}분 뒤 다시 확인합니다: {e}")
            return datetime.now(timezone.utc) + timedelta(minutes=RETRY_MINUTES)
        finally:
            session.close()

    async def _run_due_tests(self):
        logger.info(f"[{datetime.now(timezone.utc).isoformat()}] Scheduler tick: scanning active tests...")

        Session = self.db_session_maker()
        try:
            # 1. 진행 중(RUNNING)인 모든 A/B 테스트 조회
            active_tests = Session.query(ABTest).filter(
                ABTest.status == TestStatus.RUNNING,
                ABTest.is_deleted == False
            ).all()
            
            for test in active_tests:
                # 🔒 테스트 하나마다 개별적으로 커밋한다. 한 트랜잭션으로 묶어서 배치 끝에 한 번만
                # 커밋하면, 이 중 한 테스트에서 예외가 나는 순간(예: Neon SSL 연결 끊김) 이번 틱에서
                # 이미 처리한 다른 테스트들의 VPH/스왑 결과까지 통째로 롤백되어 유실된다.
                try:
                    await self._process_single_test(test, Session)
                    Session.commit()
                except Exception as e:
                    Session.rollback()
                    logger.error(f"테스트 ID [{test.id}] 처리 중 에러 발생 - 이번 틱은 건너뛰고 다음 테스트로 계속 진행합니다: {e}")
        except Exception as e:
            Session.rollback()
            logger.error(f"스케줄러 에러 발생: {e}")
        finally:
            Session.close()

    async def _process_single_test(self, test, session):
        """단일 A/B 테스트에 대한 조회수 측정 및 썸네일 교체 로직"""

        channel = test.video.channel

        # 0. 테스트 기간(end_time)이 만료되었는지 확인
        if test.end_time and datetime.now(timezone.utc) >= test.end_time:
            all_vars = session.query(Variation).filter(Variation.ab_test_id == test.id).all()
            total_views_gained = sum(sum(l.views_gained for l in v.metric_logs) for v in all_vars)

            measured_windows = [len(v.metric_logs) for v in all_vars]
            enough_cycles = has_enough_cycles(measured_windows)
            enough_sample = has_enough_sample(total_views_gained)

            if not (enough_cycles and enough_sample) and test.extension_count < MAX_AUTO_EXTENSIONS:
                extension_minutes = test.swap_interval_minutes * max(len(all_vars), 1)
                test.end_time = test.end_time + timedelta(minutes=extension_minutes)
                test.extension_count += 1
                reasons = []
                if not enough_cycles:
                    reasons.append(f"측정 부족(후보별 {measured_windows}구간, 후보마다 {MIN_CYCLES}구간 필요)")
                if not enough_sample:
                    reasons.append(f"표본 부족(누적 +{total_views_gained} views < {MIN_SAMPLE_VIEWS})")
                logger.info(
                    f"⏳ 테스트 ID [{test.id}] 승자 확정 보류 - {', '.join(reasons)}. "
                    f"{extension_minutes}분 자동 연장 ({test.extension_count}/{MAX_AUTO_EXTENSIONS}회째)"
                )
                return

            logger.info(f"🏁 테스트 ID [{test.id}] (영상: {test.video.youtube_video_id}) 기간 종료! 승자 확정 진행 중...")

            # 최종 승자 변인(노출 시간당 조회수 = VPH가 가장 높은 변인) 찾기
            winner_var = None
            max_vph = -1.0

            for var in all_vars:
                vph = compute_variation_vph(var)
                if vph > max_vph:
                    max_vph = vph
                    winner_var = var

            if winner_var:
                winner_var.is_winner = True
                winner_total_views = sum(l.views_gained for l in winner_var.metric_logs)
                logger.info(f"🏆 최종 승자 확정: [{winner_var.name}] ({max_vph:.1f} VPH, 누적 +{winner_total_views} 조회수)")

                # 승자 썸네일/제목을 유튜브에 최종 적용 (실패해도 DB상의 승자 확정 자체는 유지)
                refresh_token = channel.oauth_refresh_token
                if refresh_token and not channel.needs_reconnect:
                    # 🔒 _do_swap과 동일하게, 쿼터가 부족하면 시도조차 하지 않는다. 체크 없이 그냥
                    # 호출하면 Google이 403 quotaExceeded를 반환해도 update_youtube_thumbnail이
                    # 조용히 False를 반환할 뿐이라, DB엔 "승자 확정됨"이라 남지만 실제 YouTube
                    # 썸네일은 예전 것 그대로 남는 상황이 아무 로그 없이 발생할 수 있었다.
                    # 이미 유튜브에 걸려 있는 것은 다시 올리지 않는다 (승자가 지금 적용 중이면 썸네일 생략,
                    # 제목이 지금과 같으면 제목 생략). 직전 교체가 실패했으면 유튜브 상태를 확신할 수 없어 둘 다 적용한다.
                    live_var = next((v for v in all_vars if v.id == test.current_variation_id), None)
                    state_known = not test.swap_failed
                    winner_is_live = state_known and live_var is not None and live_var.id == winner_var.id
                    apply_thumbnail = bool(winner_var.thumbnail_image_url) and not winner_is_live
                    apply_title = bool(winner_var.title_text) and (
                        not state_known or _title_differs(winner_var.title_text, _live_title(all_vars, live_var))
                    )
                    # L-5: check_and_reserve_usage로 확인+예약을 원자적으로 처리 (TOCTOU 방지)
                    apply_cost = (COST_THUMBNAILS_SET if apply_thumbnail else 0) + (COST_VIDEOS_UPDATE if apply_title else 0)
                    if apply_cost == 0:
                        logger.info(f" - [테스트 {test.id}] 승자 [{winner_var.name}]가 이미 유튜브에 적용되어 있어 추가 교체 없음")
                    elif not check_and_reserve_usage(session, apply_cost):
                        logger.warning(
                            f"⚠️ YouTube API 일일 쿼터 소진 임박 - 테스트 ID [{test.id}] 승자 썸네일/제목 적용을 건너뜁니다 "
                            f"(DB상 승자 확정은 유지되나, YouTube에는 반영되지 않았습니다)"
                        )
                    else:
                        try:
                            if apply_thumbnail:
                                import os, re as _re2
                                _YT_NATIVE = ("https://i.ytimg.com/", "https://img.youtube.com/")
                                win_url = winner_var.thumbnail_image_url
                                if any(win_url.startswith(p) for p in _YT_NATIVE):
                                    win_url = _re2.sub(r'/[^/]+\.jpg$', '/maxresdefault.jpg', win_url)
                                win_file = os.path.join("uploads", win_url.split('/')[-1] + "_" + str(winner_var.id))
                                if not os.path.exists(win_file) and win_url.startswith("http"):
                                    import httpx as _httpx
                                    try:
                                        async with _httpx.AsyncClient() as _c:
                                            _r = await _c.get(win_url)
                                            if _r.status_code == 200:
                                                with open(win_file, "wb") as _f:
                                                    _f.write(_r.content)
                                    except Exception as _e:
                                        logger.error(f"승자 썸네일 다운로드 에러: {_e}")
                                if os.path.exists(win_file):
                                    thumb_ok = await update_youtube_thumbnail(test.video.youtube_video_id, win_file, refresh_token)
                                    if not thumb_ok:
                                        logger.error(f"⚠️ 테스트 ID [{test.id}] 승자 썸네일 YouTube 반영 실패 (API가 실패를 반환함)")
                            if apply_title:
                                title_ok = await update_youtube_title(test.video.youtube_video_id, winner_var.title_text, refresh_token)
                                if not title_ok:
                                    logger.error(f"⚠️ 테스트 ID [{test.id}] 승자 제목 YouTube 반영 실패 (API가 실패를 반환함)")
                        except TokenRevokedError:
                            channel.needs_reconnect = True
                            logger.warning(f"⚠️ 채널 [{channel.id}] YouTube 연동이 만료/철회되어 재연동이 필요합니다. (승자 확정은 정상 처리됨)")

                # 테스트 완료 이메일 알림 — PRO 유저 전용
                # notification_email(인증된 별도 수신 이메일)이 있으면 우선 사용, 없으면 로그인 이메일로 발송
                from models import PlanType
                if (
                    channel.user
                    and channel.user.plan == PlanType.PRO
                    and channel.user.email_alerts_enabled
                ):
                    send_to = (
                        channel.user.notification_email
                        if channel.user.notification_email and channel.user.notification_email_verified
                        else channel.user.email
                    )
                    if send_to:
                        from email_service import send_test_completion_email
                        await asyncio.to_thread(
                            send_test_completion_email,
                            user_email=send_to,
                            video_title=winner_var.title_text or test.video.youtube_video_id,
                            winner_name=winner_var.name,
                            views_gained=winner_total_views,
                            locale=channel.user.locale,
                            thumbnail_url=winner_var.thumbnail_image_url,
                            youtube_video_id=test.video.youtube_video_id,
                        )

            test.status = TestStatus.COMPLETED
            return

        # 재연동이 필요한 채널은 정상화 전까지 API 호출을 반복하지 않고 건너뜀
        if channel.needs_reconnect:
            logger.debug(f" - [테스트 {test.id}] 채널 {channel.id} 재연동 필요 - 건너뜀")
            return

        # 0-1. 워밍업 구간(스왑 직후, 교체 주기의 10% · 3~15분) 종료 시점에 조회수 기준선을 다시 캡처한다.
        #      직전 썸네일의 잔상 노출로 인한 조회수가 새 변인의 점수에 섞이는 것을 막기 위함.
        if not test.warmup_captured:
            minutes_since_swap = (datetime.now(timezone.utc) - _as_utc(test.last_swapped_at)).total_seconds() / 60
            if minutes_since_swap >= warmup_minutes_for(test.swap_interval_minutes):
                refresh_token = channel.oauth_refresh_token
                if refresh_token:
                    try:
                        baseline_views = await get_video_views(test.video.youtube_video_id, refresh_token)
                        record_usage(session, COST_VIDEOS_LIST)
                        test.last_views_snapshot = baseline_views
                        test.exposure_start_at = datetime.now(timezone.utc)
                        test.warmup_captured = True
                        logger.info(f" - [테스트 {test.id}] 워밍업 종료, 조회수 기준선 재캡처 ({baseline_views} views)")
                    except TokenRevokedError:
                        channel.needs_reconnect = True
                        logger.warning(f"⚠️ 채널 [{channel.id}] YouTube 연동이 만료/철회되어 재연동이 필요합니다.")
                        return

        # 1. 교체 주기가 되었는지 확인 (ex. 120분이 지났는가?). 단, 직전 스왑이 실패했다면
        #    (swap_failed) 전체 주기를 기다리지 않고 다음 스케줄러 tick마다 재시도한다.
        time_since_last_swap = datetime.now(timezone.utc) - test.last_swapped_at
        interval_elapsed = time_since_last_swap >= timedelta(minutes=test.swap_interval_minutes)
        if not interval_elapsed and not test.swap_failed:
            remaining = timedelta(minutes=test.swap_interval_minutes) - time_since_last_swap
            logger.debug(f" - [테스트 {test.id}] 다음 교체까지 {remaining.total_seconds() / 60:.0f}분 남음 - 대기")
            return # 아직 교체 주기가 안 됨

        await self._do_swap(test, session)

    async def _do_swap(self, test, session, allow_stay: bool = True):
        """
        실제 YouTube 썸네일/제목 교체 및 성과 기록 수행.
        allow_stay: 시간대 균형상 지금 후보를 한 구간 더 두는 것이 맞으면 교체하지 않고 측정만 끊어 기록한다.
                    사용자가 누른 "지금 교체"는 반드시 다른 후보로 바꿔야 하므로 False로 부른다.
        """

        # 🔒 스케줄러의 자동 스왑과 사용자의 수동 강제 스왑(force_swap)/정지가 같은 테스트에 동시에
        # 걸리면 둘 다 같은 last_views_snapshot을 기준으로 delta_views를 계산하고 쿼터를 중복
        # 차감할 수 있다. 이 테스트 행에 락을 걸어 직렬화하고, 락을 얻은 뒤엔 그 사이 다른 트랜잭션이
        # 이미 이 테스트를 스왑/종료했을 수 있으므로 최신 상태를 다시 확인한다.
        original_test_id = test.id
        test = session.query(ABTest).filter(ABTest.id == original_test_id).with_for_update().first()
        if not test or test.status != TestStatus.RUNNING:
            logger.info(f"테스트 ID [{original_test_id}]는 이미 종료/삭제되어 스왑을 건너뜁니다.")
            return

        logger.info(f"▶ 영상 [{test.video.youtube_video_id}] VPH 측정 및 스왑 시작")

        channel = test.video.channel
        refresh_token = channel.oauth_refresh_token

        if not refresh_token:
            logger.error(f"채널에 리프레시 토큰이 없어 조작할 수 없습니다: {channel.id}")
            return

        # 첫 교체(B 적용) 전에 원본(A) 썸네일 이미지를 보관한다. 유튜브 썸네일 주소는 "지금 썸네일"을
        # 가리켜서 B를 건 뒤에는 원본을 다시 받을 수 없다. 보관에 실패하면 원본을 잃지 않도록 교체를 미루고
        # 다음 tick에 다시 시도한다.
        if test.current_variation_id is None:
            if not await self._keep_original_thumbnail(test, session):
                test.swap_failed = True
                return
            # 보관 결과를 커밋하면서 행 잠금이 풀렸으니 다시 잡고, 그 사이 다른 요청이 먼저 교체했는지 확인한다.
            test = session.query(ABTest).filter(ABTest.id == original_test_id).with_for_update().first()
            if not test or test.status != TestStatus.RUNNING or test.current_variation_id is not None:
                return

        # 현재 적용된 변인과 다음 변인 (DB만 본다. 처음 실행되는 경우 current_var는 None)
        all_vars = session.query(Variation).filter(Variation.ab_test_id == test.id).order_by(Variation.id).all()
        current_var = session.query(Variation).filter(Variation.id == test.current_variation_id).first() if test.current_variation_id else None
        # 직전 교체가 실패했으면 유튜브에 무엇이 걸려 있는지 확신할 수 없으니, 유지하지 않고 다시 교체한다
        next_var = self._get_next_variation(
            session, test, all_vars, current_var, allow_stay=allow_stay and not test.swap_failed,
        )
        if not next_var:
            logger.error(f"[스케줄러] 테스트 [{test.id}] 다음 변인을 찾을 수 없습니다. 스왑 건너뜀.")
            return
        stays = current_var is not None and next_var.id == current_var.id

        # 제목이 지금 유튜브에 걸린 제목과 같으면 제목 교체를 건너뛴다 (썸네일만 테스트하는 경우 쿼터가 절반).
        needs_title = not stays and _title_differs(next_var.title_text, _live_title(all_vars, current_var))
        needs_thumbnail = not stays and bool(next_var.thumbnail_image_url)

        # YouTube Data API 쿼터는 프로젝트(앱) 전체 공유 자원이므로, 소진 위험이 있으면
        # 이번 스왑을 건너뛴다 (last_swapped_at을 갱신하지 않으므로 다음 tick에 다시 시도됨).
        # L-5: check_and_reserve_usage로 확인+예약을 원자적으로 처리 (TOCTOU 방지). 실제로 할 작업만큼만 예약한다.
        swap_cost = COST_VIDEOS_LIST + (COST_THUMBNAILS_SET if needs_thumbnail else 0) + (COST_VIDEOS_UPDATE if needs_title else 0)
        if not check_and_reserve_usage(session, swap_cost):
            logger.warning(f"⚠️ YouTube API 일일 쿼터 소진 임박 - 테스트 ID [{test.id}] 스왑을 건너뜁니다 (쿼터 리셋 후 자동 재개)")
            return

        now = datetime.now(timezone.utc)

        # 2. YouTube API를 호출하여 현재 총 조회수 가져오기
        try:
            current_views = await get_video_views(test.video.youtube_video_id, refresh_token)
        except TokenRevokedError:
            channel.needs_reconnect = True
            logger.warning(f"⚠️ 채널 [{channel.id}] YouTube 연동이 만료/철회되어 재연동이 필요합니다.")
            return

        # 3. VPH(시간당 획득한 조회수) 계산 및 MetricLog 기록
        #    (스왑 성공 여부와 무관하게, 지금까지 실제로 노출된 구간에 대한 유효한 측정값이므로 항상 기록한다)
        #    워밍업 기준선이 캡처된 경우, 측정 시작점을 last_swapped_at이 아니라 exposure_start_at으로 사용해
        #    직전 썸네일의 잔상 노출 구간을 노출 시간에서 배제한다.
        if current_var:
            delta_views = current_views - test.last_views_snapshot
            if delta_views < 0: delta_views = 0 # 예외 방지
            measurement_start = test.exposure_start_at or test.last_swapped_at
            hours_exposed = max((now - measurement_start).total_seconds() / 3600, 0)

            new_log = MetricLog(
                variation_id=current_var.id,
                views_gained=delta_views,
                hours_exposed=hours_exposed
            )
            session.add(new_log)
            logger.info(f" - [{current_var.name}] 성과 기록: +{delta_views} views / {hours_exposed:.2f}h 노출")

        # last_views_snapshot은 스왑 성공 후에만 갱신 (실패 시 기준선 오염 방지)
        test.last_swapped_at = now

        # 4. 시간대 균형상 지금 후보를 한 구간 더 두는 경우: 유튜브는 그대로 두고 측정 구간만 새로 시작한다.
        #    화면이 바뀌지 않았으니 워밍업(직전 썸네일 잔상 제외)도 필요 없다.
        if stays:
            test.last_views_snapshot = current_views
            test.exposure_start_at = now
            test.warmup_captured = True
            test.swap_failed = False
            logger.info(f"⏸ 영상 [{test.video.youtube_video_id}] 시간대 균형을 위해 '{next_var.name}'를 한 구간 더 유지합니다")
            return

        # 5. YouTube API를 호출하여 실제 썸네일과 제목 교체 (다음 변인은 위에서 시간대 균형으로 정함)
        try:
            thumbnail_ok = True
            if next_var.thumbnail_image_url:
                import os

                import re as _re
                _YOUTUBE_NATIVE_PREFIXES = ("https://i.ytimg.com/", "https://img.youtube.com/")
                is_youtube_native = any(next_var.thumbnail_image_url.startswith(p) for p in _YOUTUBE_NATIVE_PREFIXES)

                # YouTube 원본 URL은 hqdefault.jpg(480x360)라 API 최소 요건 미달.
                # maxresdefault.jpg(1280x720)로 교체해 업로드한다.
                download_url = next_var.thumbnail_image_url
                if is_youtube_native:
                    download_url = _re.sub(r'/[^/]+\.jpg$', '/maxresdefault.jpg', download_url)

                file_name = download_url.split('/')[-1] + "_" + str(next_var.id)
                file_path = os.path.join("uploads", file_name)

                import os as _os
                _backend_url = _os.getenv("BACKEND_URL", "")
                allowed_prefixes = tuple(filter(None, [
                    "https://res.cloudinary.com/",
                    "https://cloudinary.com/",
                    "https://i.ytimg.com/",
                    "https://img.youtube.com/",
                    _backend_url if _backend_url else None,
                ]))
                url_is_safe = not download_url.startswith("http") or \
                              any(download_url.startswith(p) for p in allowed_prefixes)

                if not os.path.exists(file_path) and download_url.startswith("http"):
                    if not url_is_safe:
                        logger.warning(f"허용되지 않은 썸네일 URL 도메인 — 다운로드 건너뜀: {download_url[:80]}")
                        thumbnail_ok = False
                    else:
                        import httpx
                        try:
                            async with httpx.AsyncClient() as client:
                                resp = await client.get(download_url)
                                if resp.status_code == 200:
                                    with open(file_path, "wb") as f:
                                        f.write(resp.content)
                                    logger.info(f"새 썸네일 다운로드 완료: {file_path}")
                                else:
                                    logger.error(f"썸네일 다운로드 실패 (상태 코드: {resp.status_code})")
                        except Exception as e:
                            logger.error(f"썸네일 다운로드 에러: {e}")

                if thumbnail_ok:
                    if os.path.exists(file_path):
                        thumbnail_ok = await update_youtube_thumbnail(test.video.youtube_video_id, file_path, refresh_token)
                    else:
                        logger.warning(f"썸네일 파일을 찾을 수 없습니다: {file_path}")
                        thumbnail_ok = False

            title_ok = True
            if needs_title:
                title_ok = await update_youtube_title(test.video.youtube_video_id, next_var.title_text, refresh_token)
            else:
                logger.debug(f" - [테스트 {test.id}] 제목이 지금과 같아 제목 교체 건너뜀")
        except ThumbnailPermissionError:
            test.swap_failed = True
            channel.thumbnail_permission = "denied"
            logger.warning(f"⚠️ 채널 [{channel.id}] YouTube 맞춤 썸네일 권한 없음 — youtube.com/features 에서 계정 인증 필요")
            return
        except TokenRevokedError:
            channel.needs_reconnect = True
            test.swap_failed = True
            logger.warning(f"⚠️ 채널 [{channel.id}] YouTube 연동이 만료/철회되어 재연동이 필요합니다.")
            return

        # 6. 실제로 YouTube에 반영된 경우에만 "현재 변인"을 교체한다.
        #    실패 시 현재 변인을 그대로 유지해, 다음 측정 구간이 엉뚱한 변인 점수로 기록되는 것을 방지한다.
        if thumbnail_ok and title_ok:
            test.last_views_snapshot = current_views  # 성공 시에만 기준선 갱신
            test.current_variation_id = next_var.id
            test.swap_failed = False
            test.swap_count += 1
            if next_var.thumbnail_image_url:
                channel.thumbnail_permission = "allowed"
            # 새로 적용된 변인의 워밍업 구간 측정을 위해 기준선 재캡처를 대기 상태로 전환
            test.warmup_captured = False
            test.exposure_start_at = None
            logger.info(f"✅ 영상 [{test.video.youtube_video_id}] 변인이 '{next_var.name}'(으)로 성공적으로 교체되었습니다! (누적 스왑 {test.swap_count}회)")
        else:
            test.swap_failed = True
            still_showing = current_var.name if current_var else "초기 상태"
            logger.error(f"⚠️ 영상 [{test.video.youtube_video_id}] 변인 교체 실패 - 다음 스케줄러 주기에 재시도합니다 (현재 유지: {still_showing})")

    async def _keep_original_thumbnail(self, test, session) -> bool:
        """원본(A)의 썸네일이 아직 유튜브 주소면 이미지를 받아 영구 URL로 바꿔 둔다. 이미 보관됐거나 없으면 True."""
        control = session.query(Variation).filter(Variation.ab_test_id == test.id, Variation.is_control == True).first()
        if not control or not is_youtube_native_url(control.thumbnail_image_url):
            return True
        kept_url = await snapshot_original_thumbnail(test.video.youtube_video_id)
        if not kept_url:
            logger.error(f"⚠️ 테스트 ID [{test.id}] 원본 썸네일을 보관하지 못해 첫 교체를 미룹니다 (다음 주기에 재시도).")
            return False
        control.thumbnail_image_url = kept_url
        session.commit()  # 원본 보관은 이후 교체 성공 여부와 무관하게 남겨야 한다
        logger.info(f" - [테스트 {test.id}] 원본 썸네일 보관 완료: {kept_url}")
        return True

    def _get_next_variation(self, session, test, variations, current_var, allow_stay: bool = True):
        """
        다음에 걸 후보. 첫 교체는 원본(A)이 이미 걸려 있으니 B부터, 그 뒤로는 다가오는 시간대에
        지금까지 가장 덜 걸렸던 후보를 고른다 (rotation.py).
        """
        now = datetime.now(timezone.utc)
        var_ids = [v.id for v in variations]
        logs = session.query(MetricLog).filter(MetricLog.variation_id.in_(var_ids)).all() if var_ids else []
        exposures = [
            (log.variation_id, log.measured_at - timedelta(hours=log.hours_exposed or 0), log.measured_at)
            for log in logs if log.measured_at
        ]
        if current_var is not None:
            # 지금 걸려 있는 후보의 이번 구간(아직 기록 전)도 넣어야, 방금까지 걸린 시간대가 반영된다
            exposures.append((current_var.id, test.exposure_start_at or test.last_swapped_at, now))
        return pick_next_variation(
            variations, current_var, exposures, now, test.swap_interval_minutes, allow_stay=allow_stay,
        )
