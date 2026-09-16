# ThumbnailFlow 시스템 순서도

## 1. 전체 아키텍처

```
[사용자 브라우저]
      │
      ▼
[프론트엔드 - Next.js]          trythumbnailflow.com (Vercel)
      │
      │ API 호출 (HTTP)
      ▼
[백엔드 - FastAPI]              creatorflow-backend-iudj.onrender.com (Render)
      │
      ├──▶ [Neon PostgreSQL]    유저/채널/테스트/썸네일 데이터 저장
      ├──▶ [Cloudinary]         업로드된 썸네일 이미지 영구 저장
      ├──▶ [YouTube Data API]   썸네일 교체 / 조회수 조회
      ├──▶ [Resend]             테스트 완료 이메일 알림 (PRO 전용)
      └──▶ [Paddle]             PRO 결제 처리
```

---

## 2. 사용자 로그인 흐름

```
사용자
  │
  ├─▶ "Google로 로그인" 클릭
  │
  ▼
Google OAuth 인증
  │  (YouTube 권한 포함)
  ▼
백엔드 /api/auth/callback
  │
  ├─▶ Google 계정 정보 수신
  ├─▶ YouTube 채널 정보 조회
  ├─▶ Neon DB → users / channels 테이블 생성 or 업데이트
  └─▶ JWT 토큰 발급 → 프론트엔드 쿠키 저장
  │
  ▼
대시보드 이동
```

---

## 3. A/B 테스트 생성 흐름

```
사용자 (대시보드 → 새 테스트)
  │
  ├─▶ YouTube 영상 URL 입력
  ├─▶ 썸네일 이미지 업로드 (최대 3개 BASIC / 5개 PRO)
  │       └─▶ Cloudinary 저장 → URL 반환
  ├─▶ 교체 주기 설정 (BASIC 최소 4시간 / PRO 최소 30분)
  │
  ▼
백엔드 /api/tests (POST)
  │
  ├─▶ BASIC 플랜 제한 체크
  │       ├─ 동시 진행 테스트 1개 이하인지
  │       ├─ 이번 달 테스트 4회 이하인지 (취소된 것도 포함)
  │       └─ 교체 주기 / 썸네일 개수 제한 확인
  │
  ├─▶ Neon DB → ab_tests / variations 테이블 저장
  │       └─ Variation A = 기존 YouTube 썸네일 (is_control: true)
  │          Variation B, C, ... = 새로 업로드한 썸네일
  │
  └─▶ 즉시 첫 번째 썸네일(Variation B) YouTube에 적용
              └─▶ YouTube Data API thumbnails.set() 호출
```

---

## 4. 자동 썸네일 교체 흐름 (APScheduler)

```
APScheduler (10분마다 실행)
  │
  ├─▶ Neon DB → RUNNING 상태 테스트 전체 조회
  │
  └─▶ 각 테스트별:
          │
          ├─▶ 마지막 교체 시간 + 교체 주기 비교
          │       └─ 교체 시간 안 됐으면 SKIP
          │
          ├─▶ 다음 Variation 선택
          │       └─ B → C → A(원본) → B → ... 순환
          │
          ├─▶ 썸네일 URL 확인
          │       ├─ Cloudinary URL → 그대로 다운로드
          │       └─ i.ytimg.com URL → maxresdefault.jpg 로 변환 후 다운로드
          │
          ├─▶ YouTube Data API thumbnails.set() 호출
          │       └─ 최소 640×360 이상 필요 (maxresdefault: 1280×720)
          │
          ├─▶ 조회수 기록 → Neon DB metrics_logs 저장
          │
          └─▶ 모든 Variation 순환 완료 + 충분한 데이터 수집 시
                  └─▶ 승자 확정 (VPH 가장 높은 Variation)
                          ├─▶ 승자 썸네일 YouTube에 영구 적용
                          ├─▶ 테스트 상태 COMPLETED 변경
                          └─▶ PRO 유저 → Resend 이메일 발송
```

---

## 5. 수동 조작 흐름

```
[Swap Thumbnail Now]          테스트당 1회 제한 (manual_swap_used)
  └─▶ 즉시 다음 Variation으로 교체

[Lock Winning Thumbnail]      테스트 조기 종료
  └─▶ 현재 가장 높은 VPH Variation 승자 확정
      ├─▶ YouTube에 영구 적용
      ├─▶ 테스트 상태 COMPLETED
      └─▶ PRO 유저 → 이메일 발송

[테스트 취소]
  └─▶ 원본 썸네일(Variation A) YouTube에 복원
      ├─▶ is_deleted = true (소프트 삭제)
      └─▶ 월간 테스트 횟수에 포함됨 (BASIC 4회 제한)
```

---

## 6. 결제 흐름 (Paddle)

```
사용자 → PRO 업그레이드 클릭
  │
  ▼
Paddle Checkout (결제창)
  │
  ▼
결제 완료
  │
  ▼
Paddle → 백엔드 Webhook (/api/webhooks/paddle)
  │
  ├─▶ 서명 검증 (PADDLE_WEBHOOK_SECRET)
  ├─▶ 이메일로 유저 조회
  └─▶ Neon DB → users.is_pro = true 업데이트
  │
  ▼
대시보드 → PRO 기능 활성화
```

---

## 7. 사용 중인 외부 서비스 요약

| 서비스 | 용도 | 무료 한도 |
|--------|------|-----------|
| Vercel | 프론트엔드 호스팅 | 월 100GB 대역폭 |
| Render | 백엔드 호스팅 | 월 750시간 |
| Neon | PostgreSQL DB | 0.5GB 스토리지 |
| Cloudinary | 썸네일 이미지 저장 | 월 25GB |
| YouTube Data API | 썸네일 교체 / 조회수 | 일 10,000 유닛 |
| Resend | 이메일 발송 | 월 3,000건 |
| Paddle | 결제 처리 | 건당 수수료 |
| Sentry | 에러 모니터링 | 월 5,000건 |
| UptimeRobot | Render 슬립 방지 핑 | 5분 간격 |

---

## 8. 플랜별 제한

| 항목 | BASIC (무료) | PRO ($29/월) |
|------|-------------|--------------|
| 월간 테스트 횟수 | 4회 (취소 포함) | 무제한 |
| 동시 진행 테스트 | 1개 | 무제한 |
| 썸네일 Variation | 최대 3개 (A/B/C) | 최대 5개 (A~E) |
| 최소 교체 주기 | 4시간 | 30분 |
| 승자 자동 적용 | ✅ | ✅ |
| 테스트 완료 이메일 | ❌ | ✅ |
