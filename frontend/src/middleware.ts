import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = ["/", "/login", "/privacy", "/terms", "/pricing-public", "/faq"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (PUBLIC_PATHS.includes(pathname)) {
    return NextResponse.next();
  }

  // auth_token 쿠키가 없으면 로그인 페이지로 즉시 리다이렉트
  const authToken = request.cookies.get("auth_token");
  if (!authToken) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    // 정적 파일·이미지·API 라우트 제외, 나머지 모든 경로에 적용
    "/((?!_next/static|_next/image|favicon.ico|api/).*)",
  ],
};
