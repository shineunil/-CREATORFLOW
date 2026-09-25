import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import {
  DEFAULT_LOCALE,
  LOCALE_COOKIE,
  LOCALE_COOKIE_MAX_AGE,
  LOCALE_HEADER,
  PATH_HEADER,
  type Locale,
  detectLocale,
  isLocale,
  isPublicPath,
  localizePath,
  stripLocalePrefix,
} from "@/i18n/config";

function rememberLocale(response: NextResponse, locale: Locale) {
  response.cookies.set(LOCALE_COOKIE, locale, { path: "/", maxAge: LOCALE_COOKIE_MAX_AGE, sameSite: "lax" });
  return response;
}

function withLocaleHeader(request: NextRequest, locale: Locale, path: string) {
  const headers = new Headers(request.headers);
  headers.set(LOCALE_HEADER, locale);
  headers.set(PATH_HEADER, path);
  return { request: { headers } };
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const { locale: urlLocale, path } = stripLocalePrefix(pathname);
  const cookieValue = request.cookies.get(LOCALE_COOKIE)?.value;

  // /ko/... 주소: 공개 페이지는 같은 페이지를 한국어로 보여주고, 앱 화면은 /ko 없는 주소로 보낸다.
  if (urlLocale) {
    const target = request.nextUrl.clone();
    target.pathname = path;
    const response = isPublicPath(path)
      ? NextResponse.rewrite(target, withLocaleHeader(request, urlLocale, path))
      : NextResponse.redirect(target);
    return cookieValue === urlLocale ? response : rememberLocale(response, urlLocale);
  }

  const locale = isLocale(cookieValue) ? cookieValue : detectLocale(request.headers.get("accept-language"));

  if (isPublicPath(pathname)) {
    if (locale !== DEFAULT_LOCALE) {
      const target = request.nextUrl.clone();
      target.pathname = localizePath(pathname, locale);
      return NextResponse.redirect(target);
    }
    return NextResponse.next(withLocaleHeader(request, locale, pathname));
  }

  // OAuth 콜백 후 auth_code 교환 중인 경우 — 쿠키 없어도 통과
  if (pathname === "/dashboard" && request.nextUrl.searchParams.get("auth_code")) {
    return NextResponse.next(withLocaleHeader(request, locale, pathname));
  }

  // auth_token 쿠키가 없으면 로그인 페이지로 즉시 리다이렉트
  if (!request.cookies.get("auth_token")) {
    return NextResponse.redirect(new URL(localizePath("/login", locale), request.url));
  }

  return NextResponse.next(withLocaleHeader(request, locale, pathname));
}

export const config = {
  matcher: [
    // _next 내부, API 라우트, 그리고 확장자 있는 정적 파일(이미지·폰트·css·js·robots.txt·sitemap.xml 등) 제외
    "/((?!_next|api/|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|css|js|woff2?|ttf|eot|map|txt|xml|webmanifest)$).*)",
  ],
};
