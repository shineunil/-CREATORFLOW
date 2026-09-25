import type { MetadataRoute } from "next";
import { LOCALES } from "@/i18n/config";
import { absoluteUrl } from "@/i18n/metadata";

const PAGES: { path: string; changeFrequency: "weekly" | "monthly" | "yearly"; priority: number }[] = [
  { path: "/", changeFrequency: "weekly", priority: 1.0 },
  { path: "/pricing-public", changeFrequency: "monthly", priority: 0.8 },
  { path: "/faq", changeFrequency: "monthly", priority: 0.6 },
  { path: "/terms", changeFrequency: "yearly", priority: 0.3 },
  { path: "/privacy", changeFrequency: "yearly", priority: 0.3 },
];

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();

  // 언어별 주소를 모두 싣고, 각 항목에 서로의 번역 주소(hreflang)를 알려준다.
  return PAGES.flatMap(({ path, changeFrequency, priority }) =>
    LOCALES.map((locale) => ({
      url: absoluteUrl(path, locale),
      lastModified: now,
      changeFrequency,
      priority,
      alternates: {
        languages: Object.fromEntries(LOCALES.map((l) => [l, absoluteUrl(path, l)])),
      },
    }))
  );
}
