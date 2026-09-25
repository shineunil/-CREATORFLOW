"use client";

import { LOCALES } from "@/i18n/config";
import { useI18n } from "@/i18n/I18nProvider";

/** compact: 좁은 화면용 버튼 하나짜리 (누르면 다른 언어로 전환) */
/** className으로 display(예: "inline-flex", "hidden sm:inline-flex")를 넘긴다. 기본값은 항상 보이는 inline-flex. */
export default function LanguageSwitcher({ className, compact = false }: { className?: string; compact?: boolean }) {
  const { locale, setLocale, t } = useI18n();

  if (compact) {
    const other = LOCALES.find((l) => l !== locale) ?? locale;
    return (
      <button
        type="button"
        lang={other}
        onClick={() => setLocale(other)}
        aria-label={`${t.language.label}: ${t.language[other]}`}
        className={`h-8 min-w-8 px-2 rounded-full border border-zinc-700/70 bg-zinc-900/60 text-xs font-bold text-zinc-200 hover:text-white transition-colors cursor-pointer flex-shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 ${className ?? ""}`}
      >
        {other === "ko" ? "한" : "EN"}
      </button>
    );
  }

  return (
    <div
      role="group"
      aria-label={t.language.label}
      className={`items-center rounded-full border border-zinc-700/70 bg-zinc-900/60 p-0.5 text-xs font-bold flex-shrink-0 ${className ?? "inline-flex"}`}
    >
      {LOCALES.map((l) => (
        <button
          key={l}
          type="button"
          lang={l}
          onClick={() => setLocale(l)}
          aria-pressed={locale === l}
          className={`px-2.5 py-1 rounded-full transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 ${
            locale === l ? "bg-zinc-100 text-black" : "text-zinc-300 hover:text-white"
          }`}
        >
          {t.language[l]}
        </button>
      ))}
    </div>
  );
}
