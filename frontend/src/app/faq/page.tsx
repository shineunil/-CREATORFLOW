import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import { getI18n } from "@/i18n/server";
import { localizePath } from "@/i18n/config";
import { publicPageMetadata } from "@/i18n/metadata";

export function generateMetadata() {
  return publicPageMetadata("/faq", (m) => ({ title: m.faqTitle, description: m.faqDescription }));
}

export default async function FAQPage() {
  const { locale, t } = await getI18n();

  return (
    <div className="min-h-screen bg-[#050505] text-zinc-300">
      <div className="max-w-3xl mx-auto px-6 py-16">
        <div className="flex items-center justify-between gap-4 mb-10">
          <Link
            href={localizePath("/", locale)}
            className="inline-flex items-center gap-2 text-zinc-400 hover:text-white transition-colors text-sm rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
          >
            <ArrowLeft size={16} aria-hidden="true" /> {t.common.backToHome}
          </Link>
          <LanguageSwitcher />
        </div>

        <h1 className="text-3xl font-black text-white mb-2">{t.faq.title}</h1>
        <p className="text-base text-zinc-400 mb-12 break-keep">
          {t.faq.introBefore}
          <a
            href="mailto:admin@trythumbnailflow.com"
            className="text-cyan-400 underline underline-offset-2 hover:text-cyan-300 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
          >
            {t.faq.introLink}
          </a>
          {t.faq.introAfter}
        </p>

        <div className="space-y-14">
          {t.faq.sections.map((section) => (
            <div key={section.section}>
              <h2 className="text-sm font-semibold uppercase tracking-widest text-cyan-500 mb-6">
                {section.section}
              </h2>
              <div className="space-y-8">
                {section.items.map((item) => (
                  <div key={item.q} className="border-b border-zinc-800 pb-8 last:border-0 last:pb-0">
                    <p className="text-base font-semibold text-white mb-2 break-keep">{item.q}</p>
                    <p className="text-base text-zinc-400 leading-relaxed break-keep">{item.a}</p>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-16 pt-10 border-t border-zinc-800 text-sm text-zinc-400 space-y-1">
          <p>
            {t.faq.seeAlso}{" "}
            <Link href={localizePath("/terms", locale)} className="text-cyan-400 underline underline-offset-2 hover:text-cyan-300 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
              {t.faq.terms}
            </Link>{" "}
            &amp;{" "}
            <Link href={localizePath("/privacy", locale)} className="text-cyan-400 underline underline-offset-2 hover:text-cyan-300 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
              {t.faq.privacy}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
