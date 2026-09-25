"use client";

import { createContext, useCallback, useContext, useMemo } from "react";
import { API_BASE_URL } from "@/lib/config";
import { LOCALE_COOKIE, LOCALE_COOKIE_MAX_AGE, localizePath, stripLocalePrefix, type Locale } from "./config";
import { dictionaries, type Dictionary } from "./dictionaries";

type I18nValue = {
  locale: Locale;
  t: Dictionary;
  /** 공개 페이지 링크를 현재 언어 주소로 바꾼다 ("/faq" → "/ko/faq"). */
  lp: (path: string) => string;
  setLocale: (next: Locale) => void;
};

const I18nContext = createContext<I18nValue | null>(null);

export function saveLocalePreference(locale: Locale) {
  // apiFetch는 401이면 /login으로 보내버리므로, 언어 저장 실패가 화면 이동을 일으키지 않게 fetch를 직접 쓴다.
  fetch(`${API_BASE_URL}/api/user/preferences`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ locale }),
    keepalive: true,
  }).catch(() => {});
}

export function I18nProvider({ locale, children }: { locale: Locale; children: React.ReactNode }) {
  const setLocale = useCallback(
    (next: Locale) => {
      if (next === locale) return;
      document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=${LOCALE_COOKIE_MAX_AGE}; samesite=lax`;
      try {
        if (localStorage.getItem("isLoggedIn")) saveLocalePreference(next);
      } catch {}
      // 서버에서 그리는 부분(html lang, FAQ·약관 페이지)까지 새 언어로 바꾸려면 페이지를 새로 불러와야 한다.
      const { path } = stripLocalePrefix(window.location.pathname);
      window.location.assign(localizePath(path, next) + window.location.search + window.location.hash);
    },
    [locale]
  );

  const value = useMemo<I18nValue>(
    () => ({ locale, t: dictionaries[locale], lp: (path) => localizePath(path, locale), setLocale }),
    [locale, setLocale]
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext);
  if (!value) throw new Error("useI18n must be used inside <I18nProvider>");
  return value;
}
