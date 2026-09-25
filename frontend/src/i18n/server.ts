import { headers } from "next/headers";
import { DEFAULT_LOCALE, LOCALE_HEADER, PATH_HEADER, isLocale, type Locale } from "./config";
import { dictionaries } from "./dictionaries";

/** proxy.ts가 요청 헤더에 실어 보낸 언어를 읽는다 (서버 컴포넌트 전용). */
export async function getLocale(): Promise<Locale> {
  const value = (await headers()).get(LOCALE_HEADER);
  return isLocale(value) ? value : DEFAULT_LOCALE;
}

/** /ko 를 뗀 현재 페이지 경로 (예: /ko/faq → /faq). */
export async function getRequestPath(): Promise<string> {
  return (await headers()).get(PATH_HEADER) ?? "/";
}

export async function getI18n() {
  const locale = await getLocale();
  return { locale, t: dictionaries[locale] };
}
