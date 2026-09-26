import type { NextConfig } from "next";

// 모든 페이지에 붙는 보안 헤더.
// - X-Frame-Options / frame-ancestors: 다른 사이트가 우리 페이지를 iframe으로 덮어 클릭을 유도하는 공격(클릭재킹) 차단
// - Permissions-Policy: 쓰지 않는 카메라·마이크·위치 권한 차단 (Paddle 결제창의 payment 권한은 건드리지 않음)
const securityHeaders = [
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async headers() {
    return [{ source: "/(.*)", headers: securityHeaders }];
  },
};

export default nextConfig;
