/**
 * ============================================================
 *  CREATORFLOW 프론트엔드 전역 설정 파일
 * ============================================================
 *  라이브 전환 시 이 파일만 수정하면 됩니다!
 *  수정 후 git push → Vercel 자동 재배포됩니다.
 * ============================================================
 */

// -------------------------------------------------------
// 1. 백엔드 API 주소
//    [라이브 전환 시] 커스텀 도메인으로 바꾸고 싶다면
//    "https://api.creatorflow.com" 으로 교체
// -------------------------------------------------------
export const API_BASE_URL =
  typeof window !== "undefined" && window.location.hostname !== "localhost"
    ? "https://creatorflow-1-7ng3.onrender.com"   // 라이브 백엔드 주소
    : "http://localhost:8000";                      // 로컬 개발용 (자동 적용)

// -------------------------------------------------------
// 2. Paddle 결제 설정
//    [라이브 전환 시] 아래 3가지를 Paddle 대시보드의
//    "Live" 탭에서 발급받은 값으로 교체
// -------------------------------------------------------
export const PADDLE_CONFIG = {
  // [라이브 전환 시] "sandbox" → "production" 으로 변경
  environment: "sandbox" as "sandbox" | "production",

  // [라이브 전환 시] Paddle 대시보드 Developer Tools → Client-side token
  // test_xxx... → live_xxx... 으로 변경
  clientToken: "test_9238033b9dedeeb22b63d067626",

  // [라이브 전환 시] Paddle 대시보드 Catalog → Prices → PRO Price ID
  // pri_01m1psq... → 라이브 Price ID 로 변경
  proPriceId: "pri_01m1psq971t3sy5h2xq0venhsg",
};
