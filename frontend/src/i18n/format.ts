import type { Locale } from "./config";

const INTL_LOCALE: Record<Locale, string> = { en: "en-US", ko: "ko-KR" };

const HAS_TIMEZONE = /(?:[zZ]|[+-]\d{2}:?\d{2})$/;

/**
 * 서버가 보낸 시각 문자열을 읽는다. 서버는 UTC로 저장하지만 DB에 따라 형식이 다르다:
 * SQLite는 "2026-09-29T10:00:00"(시간대 없음), Postgres는 "2026-09-29T10:00:00+00:00".
 * 시간대 표시가 없을 때만 UTC(Z)로 보고, 이미 있으면 그대로 읽는다 ("+00:00Z"는 잘못된 날짜가 됨).
 */
export function parseServerDate(value: string | number | Date): Date {
  if (typeof value !== "string") return new Date(value);
  return new Date(value.includes("T") && !HAS_TIMEZONE.test(value) ? `${value}Z` : value);
}

/** 한국어 "2026. 10. 3.", 영어 "10/3/2026" */
export function formatDate(value: string | number | Date | null | undefined, locale: Locale): string {
  if (value == null) return "-";
  const date = parseServerDate(value);
  return isNaN(date.getTime()) ? "-" : date.toLocaleDateString(INTL_LOCALE[locale]);
}

export function formatDateTime(value: string | number | Date | null | undefined, locale: Locale): string {
  if (value == null) return "-";
  const date = parseServerDate(value);
  return isNaN(date.getTime()) ? "-" : date.toLocaleString(INTL_LOCALE[locale]);
}

export function formatNumber(value: number, locale: Locale): string {
  return value.toLocaleString(INTL_LOCALE[locale]);
}
