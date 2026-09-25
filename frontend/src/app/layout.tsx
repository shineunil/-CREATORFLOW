import type { Metadata } from "next";
import { Geist, Geist_Mono, Noto_Sans_KR } from "next/font/google";
import "./globals.css";
import { I18nProvider } from "@/i18n/I18nProvider";
import { getLocale, getRequestPath } from "@/i18n/server";
import { dictionaries } from "@/i18n/dictionaries";
import { SITE_URL, publicPageSeo } from "@/i18n/metadata";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// Geist와 시스템 글꼴에는 한글이 없어서, 한글만 이 글꼴로 보이도록 글꼴 목록 뒤쪽에 둔다.
const notoSansKr = Noto_Sans_KR({
  variable: "--font-noto-kr",
  preload: false,
});

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  const path = await getRequestPath();
  const t = dictionaries[locale].meta;
  // 홈(app/page.tsx)은 클라이언트 컴포넌트라 metadata를 내보낼 수 없어서, 홈의 canonical·hreflang은 여기서 넣는다.
  // 다른 공개 페이지는 각자 generateMetadata로 덮어쓰고, 로그인 후 화면에는 canonical을 넣지 않는다.
  const home = publicPageSeo("/", locale, t.siteTitle, t.ogDescription);
  return {
    metadataBase: new URL(SITE_URL),
    title: {
      default: t.siteTitle,
      template: "%s | ThumbnailFlow",
    },
    description: t.siteDescription,
    keywords: t.keywords,
    authors: [{ name: "ThumbnailFlow" }],
    creator: "ThumbnailFlow",
    openGraph: home.openGraph,
    twitter: home.twitter,
    ...(path === "/" ? { alternates: home.alternates } : {}),
    verification: {
      other: {
        // 네이버 서치어드바이저 사이트 소유 확인
        "naver-site-verification": "7b49e4a5793d6a9c92125a13dda335fb8226d246",
      },
    },
    robots: {
      index: true,
      follow: true,
      googleBot: {
        index: true,
        follow: true,
      },
    },
  };
}

import ClientLayout from "@/components/layout/ClientLayout";
import { Analytics } from "@vercel/analytics/react";

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  return (
    <html
      lang={locale}
      className={`${geistSans.variable} ${geistMono.variable} ${notoSansKr.variable} h-full antialiased`}
    >
      <body className="min-h-full">
        <I18nProvider locale={locale}>
          <ClientLayout>
            {children}
          </ClientLayout>
        </I18nProvider>
        <Analytics />
      </body>
    </html>
  );
}
