export const LOCALES = ["en", "ko"] as const;
export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "en";
export const LOCALE_COOKIE = "NEXT_LOCALE";
export const LOCALE_HEADER = "x-locale";
/** /ko 를 뗀 페이지 경로. 서버에서 canonical·hreflang 주소를 만들 때 쓴다. */
export const PATH_HEADER = "x-locale-path";
export const LOCALE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

// 로그인 없이 볼 수 있는 페이지. 이 페이지들만 /ko 주소를 가진다 (앱 화면은 쿠키로 언어를 기억).
export const PUBLIC_PATHS = ["/", "/login", "/privacy", "/terms", "/pricing-public", "/faq"];

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (LOCALES as readonly string[]).includes(value);
}

export function isPublicPath(path: string): boolean {
  return PUBLIC_PATHS.includes(path);
}

/** "/ko/faq" → { locale: "ko", path: "/faq" }, "/faq" → { locale: null, path: "/faq" } */
export function stripLocalePrefix(pathname: string): { locale: Locale | null; path: string } {
  for (const locale of LOCALES) {
    if (locale === DEFAULT_LOCALE) continue;
    if (pathname === `/${locale}`) return { locale, path: "/" };
    if (pathname.startsWith(`/${locale}/`)) return { locale, path: pathname.slice(locale.length + 1) };
  }
  return { locale: null, path: pathname };
}

/** 공개 페이지 주소를 언어에 맞게 바꾼다. 앱 화면 주소는 그대로 둔다. */
export function localizePath(path: string, locale: Locale): string {
  if (locale === DEFAULT_LOCALE || !isPublicPath(path)) return path;
  return path === "/" ? `/${locale}` : `/${locale}${path}`;
}

/** Accept-Language 헤더에서 지원하는 언어 중 가장 선호도가 높은 것을 고른다. */
export function detectLocale(acceptLanguage: string | null): Locale {
  if (!acceptLanguage) return DEFAULT_LOCALE;
  const ranked = acceptLanguage
    .split(",")
    .map((part) => {
      const [tag, ...params] = part.trim().split(";");
      const q = params.find((p) => p.trim().startsWith("q="));
      return { base: tag.toLowerCase().split("-")[0], q: q ? Number(q.trim().slice(2)) || 0 : 1 };
    })
    .sort((a, b) => b.q - a.q);
  const match = ranked.find((r) => isLocale(r.base));
  return match ? (match.base as Locale) : DEFAULT_LOCALE;
}
