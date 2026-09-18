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
from test_policy import (
    has_enough_cycles,
    has_enough_sample,
    MIN_CYCLES,
    MIN_SAMPLE_VIEWS,
    MAX_AUTO_EXTENSIONS,
    SWAP_WARMUP_MINUTES,
)
from quota_guard import has_quota_for, record_usage, COST_VIDEOS_LIST, COST_VIDEOS_UPDATE, COST_THUMBNAILS_SET

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AVSchedulerEngine:
    def __init__(self, db_session_maker):
        self.scheduler = AsyncIOScheduler()
        self.db_session_maker = db_session_maker
        
        # 10분마다 실행하며, 교체 주기가 도달한 테스트만 처리합니다.
        self.scheduler.add_job(self.check_and_swap_variations, 'interval', minutes=10)

    def start(self):
        logger.info("🚀 A/B Test Scheduler Engine Started...")
        self.scheduler.start()

    async def check_and_swap_variations(self):
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

            enough_cycles = has_enough_cycles(test.swap_count, len(all_vars))
            enough_sample = has_enough_sample(total_views_gained)

            if not (enough_cycles and enough_sample) and test.extension_count < MAX_AUTO_EXTENSIONS:
                extension_minutes = test.swap_interval_minutes * max(len(all_vars), 1)
                test.end_time = test.end_time + timedelta(minutes=extension_minutes)
                test.extension_count += 1
                reasons = []
                if not enough_cycles:
                    reasons.append(f"사이클 부족({test.swap_count}/{MIN_CYCLES * len(all_vars)}회 교체)")
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
                    worst_case_cost = COST_THUMBNAILS_SET + COST_VIDEOS_UPDATE
                    if not has_quota_for(session, worst_case_cost):
                        logger.warning(
                            f"⚠️ YouTube API 일일 쿼터 소진 임박 - 테스트 ID [{test.id}] 승자 썸네일/제목 적용을 건너뜁니다 "
                            f"(DB상 승자 확정은 유지되나, YouTube에는 반영되지 않았습니다)"
                        )
                    else:
                        try:
                            if winner_var.thumbnail_image_url:
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
                                    record_usage(session, COST_THUMBNAILS_SET)
                                    if not thumb_ok:
                                        logger.error(f"⚠️ 테스트 ID [{test.id}] 승자 썸네일 YouTube 반영 실패 (API가 실패를 반환함)")
                            if winner_var.title_text:
                                title_ok = await update_youtube_title(test.video.youtube_video_id, winner_var.title_text, refresh_token)
                                record_usage(session, COST_VIDEOS_UPDATE)
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
                            views_gained=winner_total_views
                        )

            test.status = TestStatus.COMPLETED
            return

        # 재연동이 필요한 채널은 정상화 전까지 API 호출을 반복하지 않고 건너뜀
        if channel.needs_reconnect:
            return

        # 0-1. 워밍업 구간(스왑 직후 SWAP_WARMUP_MINUTES) 종료 시점에 조회수 기준선을 다시 캡처한다.
        #      직전 썸네일의 잔상 노출로 인한 조회수가 새 변인의 점수에 섞이는 것을 막기 위함.
        if not test.warmup_captured:
            minutes_since_swap = (datetime.now(timezone.utc) - test.last_swapped_at).total_seconds() / 60
            if minutes_since_swap >= SWAP_WARMUP_MINUTES:
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
            return # 아직 교체 주기가 안 됨

        await self._do_swap(test, session)

    async def _do_swap(self, test, session):
        """실제 YouTube 썸네일/제목 교체 및 성과 기록 수행"""

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

        # YouTube Data API 쿼터는 프로젝트(앱) 전체 공유 자원이므로, 소진 위험이 있으면
        # 이번 스왑을 건너뛴다 (last_swapped_at을 갱신하지 않으므로 다음 tick에 다시 시도됨).
        worst_case_cost = COST_VIDEOS_LIST + COST_THUMBNAILS_SET + COST_VIDEOS_UPDATE
        if not has_quota_for(session, worst_case_cost):
            logger.warning(f"⚠️ YouTube API 일일 쿼터 소진 임박 - 테스트 ID [{test.id}] 스왑을 건너뜁니다 (쿼터 리셋 후 자동 재개)")
            return

        # 현재 적용된 변인 가져오기 (처음 실행되는 경우엔 None일 수 있음)
        all_vars = session.query(Variation).filter(Variation.ab_test_id == test.id).order_by(Variation.id).all()
        current_var = session.query(Variation).filter(Variation.id == test.current_variation_id).first() if test.current_variation_id else None

        now = datetime.now(timezone.utc)

        # 2. YouTube API를 호출하여 현재 총 조회수 가져오기
        try:
            current_views = await get_video_views(test.video.youtube_video_id, refresh_token)
            record_usage(session, COST_VIDEOS_LIST)
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

        # 4. 다음 순서의 Variation 결정 (A -> B -> C -> A)
        next_var = self._get_next_variation(all_vars, current_var)
        if not next_var:
            logger.error(f"[스케줄러] 테스트 [{test.id}] 다음 변인을 찾을 수 없습니다. 스왑 건너뜀.")
            return

        # 5. YouTube API를 호출하여 실제 썸네일과 제목 교체
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
                        record_usage(session, COST_THUMBNAILS_SET)
                    else:
                        logger.warning(f"썸네일 파일을 찾을 수 없습니다: {file_path}")
                        thumbnail_ok = False

            title_ok = True
            if next_var.title_text:
                title_ok = await update_youtube_title(test.video.youtube_video_id, next_var.title_text, refresh_token)
                record_usage(session, COST_VIDEOS_UPDATE)
        except ThumbnailPermissionError:
            test.swap_failed = True
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
            # 새로 적용된 변인의 워밍업 구간 측정을 위해 기준선 재캡처를 대기 상태로 전환
            test.warmup_captured = False
            test.exposure_start_at = None
            logger.info(f"✅ 영상 [{test.video.youtube_video_id}] 변인이 '{next_var.name}'(으)로 성공적으로 교체되었습니다! (누적 스왑 {test.swap_count}회)")
        else:
            test.swap_failed = True
            still_showing = current_var.name if current_var else "초기 상태"
            logger.error(f"⚠️ 영상 [{test.video.youtube_video_id}] 변인 교체 실패 - 다음 스케줄러 주기에 재시도합니다 (현재 유지: {still_showing})")

    def _get_next_variation(self, variations, current_var):
        """B -> C -> A -> B 순환 로직 (최초 실행 시 컨트롤을 건너뛰고 첫 번째 새 썸네일부터 시작)"""
        if not variations:
            return None
        if not current_var:
            # 컨트롤(Variation A)은 이미 YouTube에 적용된 상태이므로 건너뛰고
            # 첫 번째 새 변인(Variation B)부터 즉시 적용
            non_control = [v for v in variations if not v.is_control]
            return non_control[0] if non_control else variations[0]
            
        try:
            # 리스트에서 현재 변인의 인덱스를 찾음
            current_idx = next(i for i, v in enumerate(variations) if v.id == current_var.id)
            next_idx = (current_idx + 1) % len(variations)
            return variations[next_idx]
        except StopIteration:
            return variations[0]
