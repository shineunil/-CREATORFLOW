# CreatorFlow 보완 할 일

측정(허위 CTR)과 배포·보안을 나눠서 진행한다.  
시크릿·키 값은 이 파일에 적지 않는다. 호스트 환경 변수만 사용한다.

---

## 실사용 중 발견된 버그 (라이브 계정으로 직접 테스트하다 발견)

- 🐛 **`create_ab_test`의 `UnboundLocalError`** — 새로 추가한 "채널당 동시 테스트 상한" 체크가 함수 맨 위에서 `TestStatus.RUNNING`을 참조하는데, 그 아래 원래 있던 `from models import PlanType, TestStatus`(중복 - 이미 모듈 상단에서 import돼 있었음) 때문에 파이썬이 `TestStatus`를 함수 전체에서 지역변수로 취급해 발생. 중복 import 줄 삭제로 수정.
- 🐛 **`quota_guard.record_usage()`의 세션 버그 (더 심각함)** — `_do_swap()`이 한 요청 안에서 `record_usage()`를 최대 3번(조회수 조회/썸네일 교체/제목 교체) 연달아 호출하는데, DB 세션이 `autoflush=False`라서 두 번째·세 번째 호출이 첫 호출에서 방금 add()한(아직 flush 안 된) "오늘" 행을 못 보고 같은 날짜로 또 새 행을 insert하려다 `UniqueViolation`으로 커밋 전체가 롤백됨.
  - 수정: `record_usage()` 끝에 `session.flush()` 추가.
  - **테스트 인프라 자체의 구멍도 같이 고침**: `tests/conftest.py`의 `db_session` fixture가 `sessionmaker()` 기본값(`autoflush=True`)을 쓰고 있어서 프로덕션 설정(`autoflush=False`, `database.py`)과 달랐음 — 그래서 기존 pytest가 이 버그를 못 잡았음. fixture를 프로덕션과 동일하게 맞추고, 정확히 이 시나리오(한 세션에서 3번 연속 호출 후 commit)를 재현하는 회귀 테스트 추가.
  - ⚠️ **실사용 데이터에 남은 부작용**: 이 버그가 터지기 전에 이미 `update_youtube_thumbnail`/`update_youtube_title` 실제 API 호출은 성공한 뒤였고, 그 다음 DB 커밋에서만 실패해 롤백됨. 즉 **실제 유튜브 영상은 첫 후보(변인 A)로 이미 바뀌었을 가능성이 높은데, DB의 `current_variation_id`는 계속 null로 남아있는 상태**. 다음 스케줄러 사이클(또는 수동 "즉시 교체" 클릭) 때 같은 변인을 다시 적용하며 자동으로 동기화됨 (변인 A가 control이라 실질적 화면 변화는 없을 가능성 높음) — 데이터 정합성 문제일 뿐 사용자 액션 불필요.
  - 라이브 DB의 `api_quota_usage` 테이블은 확인 결과 깨끗함 (실패한 트랜잭션이 통째로 롤백되어 중복/잔여 행 없음).
- 🎨 **UX 문제 2개 (사용자가 실사용하며 발견)**:
  1. **"Start Real-time Optimization Campaign" 클릭 시 아무 반응 없음** — 로딩 상태가 전혀 없어서 사용자가 에러난 줄 착각. 근본 원인은 `create_ab_test`가 응답 전에 실제 YouTube API 호출(`_do_swap`)이 끝나길 동기적으로 기다렸던 것 — 몇 초씩 걸릴 수 있는데 버튼은 그대로였음.
     - **근본 수정**: 첫 후보 적용을 `BackgroundTasks`로 백그라운드에서 처리하도록 변경 — API가 테스트/변인 생성 직후 즉시 응답하고, 실제 유튜브 적용은 응답 후 백그라운드에서 이어짐. (요청 스코프 DB 세션은 응답 직후 닫히므로, 백그라운드 작업은 `SessionLocal()`로 새 세션을 연다.)
     - 추가로 프론트에 로딩 스피너 + 버튼 비활성화 + "테스트를 생성하는 중입니다..." 안내 문구 추가 (방어적 차원, 응답이 빨라져도 즉각적인 시각 피드백은 항상 필요).
     - 실패 시 백엔드가 보낸 실제 에러 메시지(`errData.detail`)를 그대로 보여주도록 수정 (기존엔 항상 똑같은 "An error occurred" 문구만 떴음).
  2. **테스트 중인 영상도 "Select for Test" 버튼이 안 바뀐 것처럼 보인 문제** — 실제 코드에는 이미 `activeTestVideoIds`로 테스트 중인 영상을 구분하는 로직이 있었음(배지+비활성화 버튼). 근본 원인은 위 #1(무반응)과 겹쳐서, 사용자가 "실패했다"고 착각하고 새로고침 없이 같은 화면에서 재시도했을 가능성이 높음 — `/new` 페이지가 `/api/tests`를 최초 마운트 시 한 번만 불러오기 때문에, 세션 안에서 방금 만든 테스트가 화면에 즉시 반영 안 됐을 수 있음. 테스트 생성 성공 시 `activeTestVideoIds`에 해당 영상을 즉시 추가하도록 방어적으로 수정.

---

## 제품 방향 — 멀티채널/에이전시 차별화 (신규)

**배경**: 2025년 12월 유튜브가 네이티브 "Test and Compare" 기능(썸네일/제목 최대 3개 후보, watch-time-per-impression 기준 승자 판정, 무료, Partner Program 불필요)을 전체 크리에이터에게 공개했음. "썸네일 A/B 테스트 자동화" 자체는 더 이상 독점적 판매 포인트가 아님. 한 계정으로 여러 채널을 관리하는 멀티채널/에이전시 기능을 핵심 차별화 지점으로 삼기로 함.

- [x] **멀티채널 계정 지원** (1단계: 연동 + 전환)
  - 인증 모델 변경: JWT가 이제 `sub`(user_id)와 `channel_id`(현재 보고 있는 채널)를 함께 담음. 기존 방식(`sub`=channel_id)으로 발급된 토큰은 무효화되므로, 배포 시 **기존 로그인 세션은 전부 재로그인 필요** (지금 라이브 DB엔 유저 1명뿐이라 비용 적음).
  - `get_current_channel`이 `channel.user_id`가 토큰의 user_id와 일치하는지 검증 (다른 계정 채널을 흉내내지 못하도록).
  - `GET /api/channels` (연동된 채널 목록 + 활성 채널 표시), `POST /api/channels/{id}/switch` (소유권 확인 후 해당 채널로 스코프된 새 토큰 발급) 신규 추가.
  - 요금제별 채널 연동 상한: BASIC=1, PRO=3, AGENCY=20 (`test_policy.py`의 `MAX_CHANNELS_PER_PLAN`, env로 override 가능). OAuth 콜백에서 신규 채널 연동 시 한도 확인, 초과 시 `?error=channel_limit_reached`로 리다이렉트.
  - 이미 다른 계정이 연동해둔 채널을 다시 연동 시도하면(같은 브랜드 계정을 여러 사람이 관리하는 경우 등), 새로 로그인한 이메일이 아니라 **원래 소유자 명의**로 토큰이 발급되도록 처리 (계정 탈취 방지).
  - 프론트: `TopHeader`에 채널 전환 드롭다운(연동 채널 목록 + "다른 채널 연동하기") 추가, `settings` 페이지에 채널 목록 섹션 추가, 대시보드가 `?error=channel_limit_reached`를 감지해 업그레이드 안내.
  - 실제 라이브 DB(사용자 본인 계정)에 대해 브라우저로 직접 채널 전환 드롭다운·설정 페이지 렌더링까지 확인함.
  - ⚠️ **아직 안 한 것 (2단계, 필요시 진행)**: 채널별 disconnect는 아직 "활성 채널만" 지원 (비활성 채널을 끊으려면 먼저 전환 필요). 에이전시용 팀 시트(여러 사람이 한 계정 공유), 채널별 라벨/그룹핑, 통합 리포트(여러 채널 합산 대시보드) 등은 아직 없음.
- [x] **"빠른 반복 + 더 많은 후보" 포지셔닝** — 사실 메커니즘 자체(최대 5개 후보, 실시간 스왑)는 이미 구현돼 있었음(스키마 max=5, PRO는 30분 주기까지). 실제로 빠져있던 건 이 차별화를 알리는 것.
  - 랜딩 페이지에 "Doesn't YouTube already do this?" 비교 섹션 추가 — YouTube Test and Compare(최대 3개, 2주+, 수동 오버라이드 없음, 채널 1개씩) vs CreatorFlow(최대 5개, 30분~, 강제 스왑/즉시 승자 확정, 멀티채널 대시보드)를 사실 기반으로 정직하게 비교. YouTube 기능 자체를 깎아내리지 않고 "왜 다른 선택지가 필요한지"를 설명하는 톤으로 작성.
  - 하단에 "빠른 반복은 통계적 신중함과 트레이드오프이며, 그래서 최소 사이클/표본 크기를 강제한다"는 문구 추가 — 앞서 구현한 사이클/워밍업/표본 로직이 왜 있는지를 이 포지셔닝과 연결.
  - `pricing` 페이지의 BASIC 카드에 남아있던 오래된 문구("Minimum swap interval: 60 mins")를 실제 값(4시간)으로 수정.
- [x] **AI Thumbnail Assist (테스트 자체가 아닌 인접 기능 번들링)** — 썸네일 후보를 직접 만들어주는 기능. 실제 AI 이미지 생성(text-to-image)이 아니라, **PIL 기반 템플릿 자동 보정** 방식으로 구현 (사용자 확인하에 결정 — 외부 API 키/비용 없이 지금 바로 동작).
  - `backend/thumbnail_generator.py`: 베이스 이미지를 16:9(1280x720)로 센터 크롭 → `ml_scorer.py`가 이미 정의한 이상적 명도(150)/대비(70)/채도(65) 타깃으로 자동 보정(`ImageEnhance`) → 볼드체 헤드라인을 흰색+검은 외곽선으로 얹음. 3줄 넘으면 폰트 자동 축소.
  - 새 엔드포인트 `POST /api/generate-thumbnail` (베이스 이미지 + headline 폼 필드) — 매직바이트 검증 재사용, 생성 직후 `ml_scorer.analyze_thumbnail()`로 점수까지 반환, `/api/upload`와 클라우드 업로드 로직 공유(`publish_local_image` 헬퍼로 추출).
  - 프론트 `/new` 페이지: 후보 업로드 드롭존에 "AI로 자동 생성해보기" 토글 추가 → 문구 입력 + 베이스 사진 선택 시 자동 생성, 기존 업로드와 동일하게 점수/피드백 UI 재사용.
  - 🐛 **사용자가 발견해서 즉시 수정한 버그**: 처음에 쓴 "Anton" 폰트(라틴 문자 전용)로는 한글 헤드라인이 전부 네모(tofu) 박스로 깨졌음. 이 앱의 실사용자가 한국 크리에이터인데 정작 한글이 안 되는 채로 나갈 뻔함. `backend/assets/fonts/BlackHanSans-Regular.ttf`(한글+영문+숫자 지원하는 볼드 디스플레이 폰트, OFL 라이선스)로 교체해 해결. 재발 방지용 회귀 테스트(`test_font_actually_supports_hangul_glyphs`, `test_generate_thumbnail_wraps_korean_headline_without_error`) 추가.
  - pytest 5개 추가(해상도 정확성, 긴 문구 줄바꿈, 세로/가로 다양한 입력 처리, 한글 렌더링, 폰트 한글 글리프 실존 여부) + 실제 브라우저에서 canvas로 만든 테스트 이미지를 파일 입력에 주입해 전체 흐름(업로드→생성→점수 표시, 영문/한글 둘 다) 검증 완료.
  - 비용: $0 (외부 API 없음, 기존 Pillow 의존성만 사용).

---

## 이번 주 — 코드 (P0 / P1)

### 보안·배포가 깨지는 것부터

- [x] `frontend/src/app/login/page.tsx` 로그인 URL을 `localhost:8000` 하드코딩 대신 `API_BASE_URL` 사용
- [x] `POST /api/tests/{id}/swap`에 `get_current_channel` 인증·소유권 검사 추가
- [x] `POST /api/checkout/upgrade-test`는 개발 환경에서만 동작하게 하거나 프로덕션에서 제거
- [x] JWT에 `exp`(예: 7일), `iat` 추가. 만료된 토큰은 401
- [x] OAuth 콜백 `?token=` 수신 후 URL에서 쿼리 제거 (히스토리·리퍼러에 토큰 잔류 방지)
- [x] Paddle 웹훅: `PADDLE_WEBHOOK_SECRET`이 없으면 프로덕션에서 실패하도록 (서명 검증 스킵 금지)
- [x] Lemon Squeezy 웹훅도 시크릿 없으면 프로덕션에서 거부

### 지표를 정직하게

- [x] API/차트 필드명 `ctr` → `views_gained` 또는 `vph`
- [x] 대시보드·생성·랜딩 카피에서 “CTR 측정” 표현 제거. “구간 조회수 증가 / 시간당 조회수(VPH)”로 표기
- [x] 후보 비교는 raw 합이 아니라 **노출 시간으로 나눈 VPH** (`views_gained / hours_exposed`). `MetricLog.hours_exposed` 컬럼 추가 + `backend/metrics_utils.py`의 `compute_variation_vph()`로 승자 판정(`main.py` stop, `scheduler.py` 종료 시점) 통일. `/api/tests`, `/api/history` 응답에도 `vph` 필드 추가.
  - ⚠️ 라이브 DB(Postgres)에 컬럼이 없으므로 배포 전 반드시 `backend/migrate_add_hours_exposed.py` 1회 실행 필요 (DATABASE_URL 환경 변수로 라이브 DB를 가리킨 채 실행). 로컬 SQLite도 기존 파일을 쓰고 있다면 동일하게 실행.
  - 마이그레이션 이전에 쌓인 MetricLog는 `hours_exposed=0`으로 남아 있고, 그런 로그만 있는 변인은 VPH 대신 raw 합계로 폴백 비교됨(소급 보정 불가).
- [x] 스케줄러 조회 시 `is_deleted == True` 테스트 제외
- [x] 테스트 생성 직후 첫 후보(또는 control)를 YouTube에 바로 적용 (지금은 interval만큼 기다림)

### 스케줄러 안정성

- [x] 썸네일/제목 API 실패 시에도 RUNNING으로 두고 잘못된 구간에 점수를 붙이지 않기 (실패 플래그·재시도)
  - `ABTest.swap_failed` 플래그 추가. 썸네일/제목 갱신 중 하나라도 실패하면 `current_variation_id`를 갱신하지 않고 이전 변인을 유지 → 다음 측정 구간이 실제로 아직 안 바뀐 화면에 새 변인 점수로 잘못 붙는 것을 방지.
  - 조회수 측정(`MetricLog` 기록)은 스왑 성공 여부와 무관하게 항상 수행 (측정 자체는 유효한 데이터이므로).
  - `swap_failed=True`인 테스트는 전체 교체 주기를 기다리지 않고 다음 스케줄러 tick(10분)마다 재시도.
  - `/api/tests/{id}/swap` 수동 즉시 교체 버튼도 실패 시 502로 응답하도록 수정 (이전엔 실패해도 항상 “성공” 메시지를 반환했음).
- [x] refresh token 무효 시 채널을 “재연동 필요” 상태로 표시, 유저에게 재동의 유도
  - `Channel.needs_reconnect` 플래그 추가. `youtube_api.py`에서 Google `RefreshError`(토큰 만료/철회)를 `TokenRevokedError`로 구분해 감지.
  - 감지되면 채널을 재연동 필요 상태로 표시하고, 정상화 전까지 스케줄러가 해당 채널의 API 호출을 반복하지 않도록 스킵.
  - 유저가 `/login`으로 재로그인(기존에도 `prompt=consent`라 새 refresh_token 발급됨)하면 자동으로 플래그 해제.
  - `/api/user/me`에 `needs_reconnect` 필드 노출, 대시보드 상단에 재연동 안내 배너 + “채널 재연동하기” 버튼 추가.
  - ⚠️ 라이브 DB 마이그레이션 필요: `backend/migrate_add_reliability_columns.py` 1회 실행 (`channels.needs_reconnect`, `ab_tests.swap_failed` 컬럼 추가).

---

## 이번 주 — 운영

- [x] `live_environment_setup.txt` 등 평문 키가 있는 파일을 git에서 제외 (`.gitignore`)
- [x] `backend/.env.example`에 커밋되어 있던 실제 GOOGLE_CLIENT_SECRET / PADDLE_API_KEY / PADDLE_WEBHOOK_SECRET / JWT_SECRET 값을 플레이스홀더로 교체 (단, git 이력엔 남아있으므로 **재발급은 여전히 필수**)
- [x] `backend/sql_app.db` git 추적 해제 + `.gitignore`에 `backend/*.db` 추가
- [x] 루트에 하드코딩된 Paddle 키 참조 디버그 스크립트 삭제 (`check_transaction.js`, `check_price.js`, `fetch_price.js`, `check_db.js/py`, `downgrade.js`, `search*.js/py`) — `search.py`는 이 프로젝트와 무관한 로컬 PC 경로까지 참조하고 있었음
- [ ] 해당 키들이 이미 커밋·공유됐으므로 DB / Google OAuth / JWT / Paddle 키 **전부 재발급(rotate)** — 각 서비스 콘솔에서 사용자가 직접 수행 필요
- [ ] Render·Vercel에는 환경 변수만 등록. 저장소에는 `.env.example`(이름만, 값 없음)
- [x] 업로드를 Render 로컬 `uploads/`가 아니라 클라우드 URL로 저장하도록 백엔드 변경 (`backend/storage.py`, Cloudinary 연동. `/api/upload`가 설정되어 있으면 Cloudinary에 업로드 후 영구 URL 반환, 미설정 시 기존처럼 로컬 저장으로 자동 폴백)
- [x] 스케줄러 승자 적용·스왑이 로컬 파일 대신 클라우드 URL을 쓰도록 수정 — 기존에도 URL이 `http`로 시작하면 로컬 캐시가 없을 때 다운로드하는 로직이 있었으나, 지금까지는 그 URL 자체가 자기 자신의(재배포 시 사라지는) 로컬 경로를 가리키고 있어 실효성이 없었음. 이제 Cloudinary의 진짜 영구 URL을 가리키므로 재배포 후에도 정상 동작.
- [ ] **사용자 액션 필요**: cloudinary.com 무료 계정 생성 후 `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET`를 Render 환경 변수로 등록 (`backend/.env.example` 참고). 설정 전까지는 기존과 동일하게 로컬 디스크에 저장되어 재배포 시 유실 위험이 남아있음.

---

## 다음 스프린트 — 측정 고도화

짧은 교체 주기(30~60분)로는 Analytics CTR을 자를 수 없다.  
실시간은 VPH, 확정은 일 단위 CTR로 이원화한다.

- [x] 승자 확정 전 **최소 2~3 사이클** (시간대가 후보마다 돌아가게)
- [x] 교체 직후 워밍업 구간(10~20분) 조회수는 점수에서 제외
- [x] 최소 표본: 총 조회수 증가가 N 미만이면 승자 없음 / 테스트 연장
  - 새 모듈 `backend/test_policy.py`에 정책 상수 + 판정 함수 정리 (`MIN_CYCLES=2`, `MIN_SAMPLE_VIEWS=50`, `MAX_AUTO_EXTENSIONS=2`, `SWAP_WARMUP_MINUTES=15`, `BASIC_MIN_SWAP_INTERVAL_MINUTES=240` — 모두 env로 override 가능, `.env.example` 참고).
  - `ABTest`에 `swap_count`(누적 성공 스왑 수), `extension_count`(자동 연장 횟수), `warmup_captured`/`exposure_start_at`(워밍업 재캡처 상태) 컬럼 추가.
  - 스케줄러가 테스트 종료 시점에 사이클·표본이 부족하면 승자를 확정하지 않고 `swap_interval × 변인 수`만큼 자동 연장(최대 2회) 후 계속 RUNNING. 2회 넘게 부족해도 결국 있는 데이터로 확정(무한 연장 방지).
  - 워밍업: 스왑 후 `SWAP_WARMUP_MINUTES`가 지난 시점에 조회수 기준선을 한 번 더 캡처(`exposure_start_at`)해, 그 이전(직전 썸네일 잔상 노출 구간)은 노출 시간·조회수 계산에서 제외.
  - ⚠️ **의도적으로 범위에서 제외**: 수동 "테스트 조기 종료(Lock Winning Thumbnail)" 버튼은 이 게이트를 적용하지 않음 — 유저의 명시적 조기 확정 요청이므로 그대로 즉시 승자를 확정함. 자동(스케줄러) 종료 시점에만 사이클/표본 게이트가 걸림.
  - ⚠️ 라이브 DB 마이그레이션 필요: `backend/migrate_add_test_policy_columns.py` 1회 실행.
- [x] BASIC 기본 주기를 더 길게 (예: 4~24시간). 짧은 주기는 PRO만
  - 백엔드 `BASIC_MIN_SWAP_INTERVAL_MINUTES=240`(4시간)으로 검증 로직 변경. 프론트 [new/page.tsx](frontend/src/app/new/page.tsx) 주기 선택 옵션도 4h/12h/24h(전체 이용 가능)와 2h/1h/30분(PRO 전용)으로 재구성, 기본값도 4시간으로 변경.
- [x] OAuth 스코프에 `yt-analytics.readonly` 추가
- [x] 테스트 종료(또는 매일) 영상별 `impressions`, `impressionsCtr` 수집
- [x] 최종 승자 뱃지는 Analytics CTR 기준으로 (VPH는 진행 중 보조 지표)
  - ⚠️ **설계 결정(사용자 확인 완료)**: 승자 확정 로직은 그대로 VPH 기준 유지. Analytics CTR은 승자를 바꾸지 않고 대시보드에 참고 지표로만 노출. 이유: Analytics 데이터는 최대 하루 지연되고 변인 단위가 아닌 영상 전체 단위로만 제공되어, 실시간 승자 확정에 쓰기엔 부정확함.
  - 새 테이블 `DailyAnalytics` (video 단위, date/impressions/impressions_ctr) — 새 테이블이라 `Base.metadata.create_all()`이 자동 생성함 (별도 마이그레이션 스크립트 불필요).
  - `backend/youtube_api.py`에 `get_daily_video_analytics()` 추가 (YouTube Analytics API v2, `impressions`+`impressionsClickThroughRate`, `dimensions=day`).
  - 스케줄러에 6시간 주기 `collect_daily_analytics` 잡 추가 — 최근 4일 구간을 매번 다시 덮어써 API 지연분을 따라잡음. 테스트가 하나라도 있었던 영상만 대상.
  - `/api/tests`, `/api/history` 응답에 `daily_analytics` 필드 추가, 대시보드에 “Analytics CTR (참고용, 최대 1일 지연)” 표시 추가.
  - 🔴 **미검증 - 실제로 동작하지 않을 가능성 있음 (배포 후 최우선 확인 필요)**: 공식 문서(`developers.google.com/youtube/analytics/channel_reports`)의 리포트 테이블을 직접 확인한 결과 `impressions`/`impressionsClickThroughRate`(썸네일 노출/클릭률) 조합이 문서에 없음 — 문서에 있는 impression/CTR류 메트릭은 전부 annotation(`annotationClickThroughRate`)·카드(`cardClickRate`)·광고(`adImpressions`)뿐. 구글 개발자 포럼에서도 2024.11~2025.04 사이 여러 명이 "YouTube Studio 화면엔 노출수/CTR이 보이는데 API로는 못 가져온다"고 동일하게 제보했고 구글 측 답변은 없었음. 즉 **TODO에 원래 있던 전제("Analytics API로 impressions/impressionsCtr 수집 가능")부터 틀렸을 가능성**이 있음. 코드는 실패해도 조용히 빈 배열을 반환해 앱이 죽지는 않지만(`DailyAnalytics`가 계속 비어있을 뿐), `yt-analytics.readonly`는 구글이 민감한 스코프로 분류해 기존 유저 전원 재동의 + 앱 재검증이 필요하므로 비용이 작지 않음. 사용자 확인 하에 스코프/코드는 일단 그대로 두고 배포 후 실제 연동 계정으로 호출 테스트하기로 결정함 — **배포 직후 실제 채널로 `collect_daily_analytics` 로그를 확인해 데이터가 들어오는지 반드시 검증할 것.** 안 들어오면 스코프를 되돌리고(재동의 비용 계속 발생 방지) 이 기능 자체를 재설계해야 함.
- [x] 개인정보처리방침에 “채널 분석 데이터를 읽는다” 명시 (스코프 심사)
  - `#` placeholder였던 이용약관/개인정보처리방침 링크를 실제 페이지로 교체: [frontend/src/app/privacy/page.tsx](frontend/src/app/privacy/page.tsx), [frontend/src/app/terms/page.tsx](frontend/src/app/terms/page.tsx) 신규 작성, `/login` 페이지에서 연결.
  - 개인정보처리방침에 YouTube Analytics(impressions/CTR) 수집 사실 명시.
  - ⚠️ 이메일 주소(support@creatorflow.io)는 플레이스홀더 — 실제 연락처로 교체 필요.
  - ⚠️ **아직 남음**: 이 스코프는 구글이 “민감한 스코프(Sensitive scope)”로 분류하므로, 실제 배포 전 구글 OAuth 동의 화면 검증(재검토) 절차가 필요할 수 있음 — “그다음” 섹션의 “구글 클라우드 앱 검증”과 연결됨.

---

## 그다음 — 제품·심사·오픈

- [x] 이용약관 / 개인정보처리방침 실제 페이지 (`#` 링크 제거) — 지난 턴에 완료
  - 🐛 **테스트 중 발견/수정한 버그**: `ClientLayout.tsx`의 `PUBLIC_PATHS`에 `/privacy`, `/terms`가 빠져있어서, 로그인 안 한 방문자가 이 페이지들에 들어오면 즉시 `/login`으로 튕겨나갔음(=신규 방문자에게 사실상 접근 불가 상태였음, 구글 심사 요건과 정면으로 충돌). `PUBLIC_PATHS`에 두 경로 추가로 수정.
- [x] 채널당 동시 테스트·YouTube API 일일 쿼터 가드
  - `backend/quota_guard.py` 신규: 새 테이블 `ApiQuotaUsage`(날짜별 사용량, 태평양 시간 기준 리셋)로 프로젝트 전체 공유 쿼터를 추적. `videos.list`=1, `videos.update`=50, `thumbnails.set`=50 (공식 문서로 재확인한 값).
  - 스케줄러가 매 스왑 전에 잔여 쿼터를 확인, 부족하면 그 tick만 건너뛰고 다음 tick(또는 쿼터 리셋 후)에 자동 재시도.
  - 채널당 동시 테스트 개수에 요금제 무관 절대 상한 추가 (`MAX_CONCURRENT_TESTS_PER_CHANNEL=20`) — 기존엔 PRO/AGENCY가 완전 무제한이라 한 채널이 전체 서비스의 쿼터를 소진시킬 수 있었음.
- [x] 업로드 파일: 확장자만이 아니라 실제 이미지 시그니처 검증
  - `/api/upload`에 Pillow(`Image.verify()`) 기반 매직바이트 검증 추가. 실제로 텍스트 파일을 `.jpg`로 위장해 업로드 테스트 → 차단 확인, 진짜 이미지 업로드 → 정상 통과 확인.
- [x] SMTP 미설정 시 API/UI에 “시뮬레이션(실제 미발송)” 표시
  - `email_service.py`가 `bool` 대신 `{“sent”, “simulated”}` 반환하도록 변경. `/api/settings/test-email` 응답과 설정 페이지 알림 문구가 실제 발송 여부를 정확히 반영하도록 수정 — 기존엔 SMTP 설정 여부와 무관하게 프론트에 항상 “완벽하게 발송됨”이라는 하드코딩된 문구가 떠서, 실제로는 시뮬레이션인데도 진짜 발송된 것처럼 보였음.
- [ ] Paddle sandbox 결제 → 웹훅 → 대시보드 PRO 업그레이드 E2E 확인 — **사용자 액션 필요** (실제 Paddle sandbox 계정으로 직접 클릭)
- [ ] 구글 클라우드 앱 검증: 정책 페이지 + 썸네일 교체 데모 영상 — **사용자 액션 필요** (정책 페이지는 이제 준비됨, 구글 콘솔 제출은 직접)
- [ ] 커스텀 도메인 연결 — **사용자 액션 필요** (도메인 등록/DNS는 대행 불가)
- [ ] Paddle·OAuth를 sandbox에서 live 키로 교체 — **사용자 액션 필요** (실제 라이브 키 발급은 각 서비스 콘솔에서 직접)

---

## 테스트 인프라 (신규 구축)

- 로컬에 Python 3.12 설치(winget) + `pip install -r requirements.txt` + pytest. 이전까지는 이 세션에서 작성한 백엔드 코드를 문법조차 검증 안 해봤음.
- 라이브 DB(Neon Postgres)에 마이그레이션 3종 전부 실행 완료 (`migrate_add_hours_exposed.py`, `migrate_add_reliability_columns.py`, `migrate_add_test_policy_columns.py`). 실행 중 Windows 콘솔(cp949) 인코딩 문제로 이모지 print가 크래시 → 트랜잭션 롤백되는 버그 발견, 전부 수정 후 재실행해 확인.
- `backend/tests/`에 pytest 단위테스트 19개 작성 (VPH 계산, 사이클/표본 정책, 스왑 성공/실패/재시도, 워밍업 제외, 토큰 만료 처리, 쿼터 가드) — 전부 mock 기반이라 실제 계정 없이도 회귀 검증 가능. 전부 통과.
- `.claude/launch.json` 추가: 백엔드(uvicorn)/프론트엔드(next dev)를 각각 미리보기로 띄울 수 있음.
- 프론트엔드 `npm run build` / `tsc --noEmit` 클린 확인.
- 실제 라이브 DB(사용자 본인 계정, `users=1, channels=1`)에 연결해 `/api/user/me`, `/api/tests`, `/api/history`, `/api/analytics` 등 읽기 전용 인증 엔드포인트 동작 확인. 실제 YouTube API를 건드리는 쓰기 동작(테스트 생성/수동 스왑)은 사용자 본인 채널에 실제로 영향을 주므로 의도적으로 자동 실행하지 않음 — 이런 E2E는 사용자가 직접 UI로 진행.
- Neon Postgres가 유휴 커넥션을 끊어서 스케줄러가 `SSL connection has been closed unexpectedly` 에러를 실제로 내는 것을 확인 → `database.py`에 `pool_pre_ping=True, pool_recycle=300` 추가로 수정.
- ⚠️ **자체 수정한 실수**: 세션 초반에 `frontend/AGENTS.md`/`CLAUDE.md`를 "프롬프트 인젝션"으로 잘못 판단해 삭제했었음. 이번에 `node_modules/next/AGENTS.md`와 `node_modules/next/dist/server/lib/generate-agent-files.js`를 직접 확인한 결과, 그 파일은 Next.js가 실제로 자동 생성하는 정식 파일임이 확인되어 원상 복구함. (git 인덱스에 D+?? 잔재가 남아있어 `git add`로 한 번 정리 필요 — 자동 승인 분류기가 막아서 직접 정리는 못 함)

---

## 알아둘 것 (나중에 구멍 나기 쉬운 부분)

- `frontend/AGENTS.md`(+ 이를 불러오던 `frontend/CLAUDE.md`)가 "next dev가 자동 생성했다"고 주장하며 AI 코딩 에이전트에게 가짜 문서 경로를 읽고 지시를 따르라고 유도하는 내용이었음. 실제 Next.js는 이런 파일을 생성하지 않음 — 프롬프트 인젝션으로 판단되어 두 파일 모두 삭제함. 어디서 왔는지(직접 작성/템플릿/외부 유입) 확인 필요.

- `PlanType.AGENCY`는 Enum만 있고 제한 로직은 BASIC vs 나머지다. AGENCY 상품을 팔 거면 한도를 따로 정한다.
- 구글은 재로그인 때 refresh token을 안 줄 수 있다. 기존 유효 토큰을 빈 값으로 덮어쓰지 말 것.
- 차트/카피만 CTR로 바꿔도 Data API `viewCount`는 노출·클릭이 아니다. Analytics 연동 전까지 “CTR 측정”이라고 쓰지 않는다.

---

## 권장 진행 순서

1. ~~로그인 URL + swap 인증 + upgrade-test 차단 + JWT 만료~~ (완료)  
2. 시크릿 정리·회전 + 이미지 클라우드 저장  
3. CTR 문구 제거 + VPH + `is_deleted` 제외 + 생성 직후 첫 적용  
4. Paddle 웹훅 E2E  
5. Analytics 일 단위 CTR 확정  
6. 정책 페이지·구글 심사·도메인·live 키  
