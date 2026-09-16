import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const SITE_URL = "https://trythumbnailflow.com";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "ThumbnailFlow — Thumbnail A/B Testing for YouTube",
    template: "%s | ThumbnailFlow",
  },
  description:
    "Upload thumbnail and title variants, let ThumbnailFlow rotate them on your live video, and keep the one with the highest views per hour. Free to start.",
  keywords: [
    "YouTube thumbnail A/B testing",
    "thumbnail split test",
    "YouTube thumbnail optimizer",
    "increase YouTube views",
    "YouTube CTR tool",
    "thumbnail testing tool",
  ],
  authors: [{ name: "ThumbnailFlow" }],
  creator: "ThumbnailFlow",
  openGraph: {
    type: "website",
    locale: "en_US",
    url: SITE_URL,
    siteName: "ThumbnailFlow",
    title: "ThumbnailFlow — Thumbnail A/B Testing for YouTube",
    description:
      "Automatically rotate thumbnail variants on your live YouTube video and keep the one with the highest views per hour.",
    images: [
      {
        url: "/hero-leading.jpg",
        width: 480,
        height: 360,
        alt: "ThumbnailFlow — YouTube Thumbnail A/B Testing",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "ThumbnailFlow — Thumbnail A/B Testing for YouTube",
    description:
      "Automatically rotate thumbnail variants on your live YouTube video and keep the one with the highest views per hour.",
    images: ["/hero-leading.jpg"],
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

import ClientLayout from "@/components/layout/ClientLayout";
import { Analytics } from "@vercel/analytics/react";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full">
        <ClientLayout>
          {children}
        </ClientLayout>
        <Analytics />
      </body>
    </html>
  );
}
