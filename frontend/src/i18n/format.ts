import type { Locale } from "./config";

const INTL_LOCALE: Record<Locale, string> = { en: "en-US", ko: "ko-KR" };

/** 한국어 "2026. 10. 3.", 영어 "10/3/2026" */
export function formatDate(value: string | number | Date | null | undefined, locale: Locale): string {
  if (value == null) return "-";
  const date = new Date(value);
  return isNaN(date.getTime()) ? "-" : date.toLocaleDateString(INTL_LOCALE[locale]);
}

export function formatDateTime(value: string | number | Date | null | undefined, locale: Locale): string {
  if (value == null) return "-";
  const date = new Date(value);
  return isNaN(date.getTime()) ? "-" : date.toLocaleString(INTL_LOCALE[locale]);
}

export function formatNumber(value: number, locale: Locale): string {
  return value.toLocaleString(INTL_LOCALE[locale]);
}
