import type { Metadata } from "next";
import { LOCALES, localizePath, type Locale } from "./config";
import { dictionaries } from "./dictionaries";
import { getLocale } from "./server";

export const SITE_URL = "https://trythumbnailflow.com";

const OG_LOCALE: Record<Locale, string> = { en: "en_US", ko: "ko_KR" };

export function absoluteUrl(path: string, locale: Locale): string {
  const localized = localizePath(path, locale);
  return localized === "/" ? SITE_URL : `${SITE_URL}${localized}`;
}

/**
 * 공개 페이지용 canonical·hreflang·Open Graph. 자식 페이지의 openGraph/alternates는 부모 값을
 * 통째로 덮어쓰므로, 공개 페이지는 항상 이 함수로 한 번에 만든다.
 */
export function publicPageSeo(path: string, locale: Locale, title: string, description: string): Metadata {
  const t = dictionaries[locale].meta;
  const url = absoluteUrl(path, locale);
  // 링크 미리보기는 1200×630이 표준 (작은 이미지는 큰 카드 대신 작은 썸네일로 나온다) - app/og.png/route.tsx
  const images = [{ url: "/og.png", width: 1200, height: 630, alt: t.ogImageAlt }];
  return {
    description,
    alternates: {
      canonical: url,
      languages: {
        ...Object.fromEntries(LOCALES.map((l) => [l, absoluteUrl(path, l)])),
        "x-default": absoluteUrl(path, "en"),
      },
    },
    openGraph: {
      type: "website",
      siteName: "ThumbnailFlow",
      url,
      title,
      description,
      locale: OG_LOCALE[locale],
      alternateLocale: LOCALES.filter((l) => l !== locale).map((l) => OG_LOCALE[l]),
      images,
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: images.map((i) => i.url),
    },
  };
}

/** 공개 서브 페이지의 generateMetadata 본체. title은 루트 템플릿으로 "제목 | ThumbnailFlow"가 된다. */
export async function publicPageMetadata(
  path: string,
  pick: (meta: (typeof dictionaries)["en"]["meta"]) => { title: string; description: string }
): Promise<Metadata> {
  const locale = await getLocale();
  const { title, description } = pick(dictionaries[locale].meta);
  return { title, ...publicPageSeo(path, locale, `${title} | ThumbnailFlow`, description) };
}
