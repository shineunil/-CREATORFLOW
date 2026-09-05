import asyncio
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Import models and APIs safely
from models import ABTest, TestStatus, Variation, MetricLog, Channel, Video
from youtube_api import get_video_views, update_youtube_thumbnail, update_youtube_title

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
        logger.info(f"[{datetime.utcnow()}] 엔진 가동: 진행 중인 테스트 탐색 시작...")
        
        Session = self.db_session_maker()
        try:
            # 1. 진행 중(RUNNING)인 모든 A/B 테스트 조회
            active_tests = Session.query(ABTest).filter(ABTest.status == TestStatus.RUNNING).all()
            
            for test in active_tests:
                await self._process_single_test(test, Session)
                
            Session.commit()
        except Exception as e:
            Session.rollback()
            logger.error(f"스케줄러 에러 발생: {e}")
        finally:
            Session.close()

    async def _process_single_test(self, test, session):
        """단일 A/B 테스트에 대한 조회수 측정 및 썸네일 교체 로직"""
        
        # 0. 테스트 기간(end_time)이 만료되었는지 확인
        if test.end_time and datetime.utcnow() >= test.end_time:
            logger.info(f"🏁 테스트 ID [{test.id}] (영상: {test.video.youtube_video_id}) 기간 종료! 승자 확정 진행 중...")
            
            # 최종 승자 변인(조회수 증가량이 가장 높은 변인) 찾기
            all_vars = session.query(Variation).filter(Variation.ab_test_id == test.id).all()
            winner_var = None
            max_views = -1
            
            for var in all_vars:
                # 각 변인의 총 획득 조회수 계산
                logs = session.query(MetricLog).filter(MetricLog.variation_id == var.id).all()
                total_gained = sum(l.views_gained for l in logs)
                if total_gained > max_views:
                    max_views = total_gained
                    winner_var = var
            
            if winner_var:
                winner_var.is_winner = True
                logger.info(f"🏆 최종 승자 확정: [{winner_var.name}] (+{max_views} 조회수 획득)")
                
                # 승자 썸네일/제목을 유튜브에 최종 적용
                channel = test.video.channel
                refresh_token = channel.oauth_refresh_token
                if refresh_token and winner_var.thumbnail_image_url:
                    import os
                    file_name = winner_var.thumbnail_image_url.split('/')[-1]
                    file_path = os.path.join("uploads", file_name)
                    if os.path.exists(file_path):
                        await update_youtube_thumbnail(test.video.youtube_video_id, file_path, refresh_token)
                if refresh_token and winner_var.title_text:
                    await update_youtube_title(test.video.youtube_video_id, winner_var.title_text, refresh_token)
                
                # 유저에게 A/B 테스트 종료 및 승자 확정 이메일 발송
                if channel.user and channel.user.email:
                    from email_service import send_test_completion_email
                    send_test_completion_email(
                        user_email=channel.user.email,
                        video_title=winner_var.title_text or test.video.youtube_video_id,
                        winner_name=winner_var.name,
                        views_gained=max_views
                    )
            
            test.status = TestStatus.COMPLETED
            return

        # 1. 교체 주기가 되었는지 확인 (ex. 120분이 지났는가?)
        time_since_last_swap = datetime.utcnow() - test.last_swapped_at
        if time_since_last_swap < timedelta(minutes=test.swap_interval_minutes):
            return # 아직 교체 주기가 안 됨
            
        await self._do_swap(test, session)

    async def _do_swap(self, test, session):
        """실제 YouTube 썸네일/제목 교체 및 성과 기록 수행"""
        logger.info(f"▶ 영상 [{test.video.youtube_video_id}] VPH 측정 및 스왑 시작")

        channel = test.video.channel
        refresh_token = channel.oauth_refresh_token
        
        if not refresh_token:
            logger.error(f"채널에 리프레시 토큰이 없어 조작할 수 없습니다: {channel.id}")
            return

        # 현재 적용된 변인 가져오기 (처음 실행되는 경우엔 None일 수 있음)
        all_vars = session.query(Variation).filter(Variation.ab_test_id == test.id).order_by(Variation.id).all()
        current_var = session.query(Variation).filter(Variation.id == test.current_variation_id).first() if test.current_variation_id else None
        
        # 2. YouTube API를 호출하여 현재 총 조회수 가져오기
        current_views = await get_video_views(test.video.youtube_video_id, refresh_token)
        
        # 3. VPH(시간당 획득한 조회수) 계산 및 MetricLog 기록
        if current_var:
            delta_views = current_views - test.last_views_snapshot
            if delta_views < 0: delta_views = 0 # 예외 방지
            
            new_log = MetricLog(
                variation_id=current_var.id, 
                views_gained=delta_views
            )
            session.add(new_log)
            logger.info(f" - [{current_var.name}] 성과 기록: +{delta_views} views")
        
        # 4. 다음 순서의 Variation 결정 (A -> B -> C -> A)
        next_var = self._get_next_variation(all_vars, current_var)
        
        # 5. YouTube API를 호출하여 실제 썸네일과 제목 교체
        if next_var.thumbnail_image_url:
            import os
            file_name = next_var.thumbnail_image_url.split('/')[-1]
            file_path = os.path.join("uploads", file_name)
            
            if not os.path.exists(file_path) and next_var.thumbnail_image_url.startswith("http"):
                import httpx
                try:
                    # 💥 비동기(async) 다운로드로 메인 이벤트 루프 블로킹(셀프 데드락) 방지
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(next_var.thumbnail_image_url)
                        if resp.status_code == 200:
                            with open(file_path, "wb") as f:
                                f.write(resp.content)
                            logger.info(f"새 썸네일 다운로드 완료: {file_path}")
                        else:
                            logger.error(f"썸네일 다운로드 실패 (상태 코드: {resp.status_code})")
                except Exception as e:
                    logger.error(f"썸네일 다운로드 에러: {e}")
            
            if os.path.exists(file_path):
                await update_youtube_thumbnail(test.video.youtube_video_id, file_path, refresh_token)
            else:
                logger.warning(f"썸네일 파일을 찾을 수 없습니다: {file_path}")
        
        if next_var.title_text:
            await update_youtube_title(test.video.youtube_video_id, next_var.title_text, refresh_token)
        
        # 6. DB 업데이트
        test.current_variation_id = next_var.id
        test.last_swapped_at = datetime.utcnow()
        test.last_views_snapshot = current_views # 다음 측정을 위해 현재 조회수 스냅샷 저장
        
        logger.info(f"✅ 영상 [{test.video.youtube_video_id}] 변인이 '{next_var.name}'(으)로 성공적으로 교체되었습니다!")

    def _get_next_variation(self, variations, current_var):
        """A -> B -> C -> A 순환 로직"""
        if not variations:
            return None
        if not current_var:
            return variations[0] # 최초 실행 시 첫 번째 변인 선택
            
        try:
            # 리스트에서 현재 변인의 인덱스를 찾음
            current_idx = next(i for i, v in enumerate(variations) if v.id == current_var.id)
            next_idx = (current_idx + 1) % len(variations)
            return variations[next_idx]
        except StopIteration:
            return variations[0]
