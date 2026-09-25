import Link from "next/link";
import { ArrowLeft, Check, Crown, Zap } from "lucide-react";
import PaddleCheckoutButton from "@/components/PaddleCheckoutButton";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import RichText from "@/i18n/RichText";
import { getI18n } from "@/i18n/server";
import { localizePath } from "@/i18n/config";
import { publicPageMetadata } from "@/i18n/metadata";

export function generateMetadata() {
  return publicPageMetadata("/pricing-public", (m) => ({ title: m.pricingTitle, description: m.pricingDescription }));
}

export default async function PricingPublicPage() {
  const { locale, t } = await getI18n();
  const basic = t.plans.basicFeatures;
  const pro = t.plans.proFeatures;
  const strong = "font-semibold text-cyan-300";

  return (
    <div className="min-h-screen bg-[#050505] text-zinc-300">
      <div className="max-w-5xl mx-auto px-6 py-16">
        <div className="flex items-center justify-between gap-4 mb-10">
          <Link href={localizePath("/", locale)} className="inline-flex items-center gap-2 text-zinc-400 hover:text-white transition-colors text-sm rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
            <ArrowLeft size={16} aria-hidden="true" /> {t.common.backToHome}
          </Link>
          <LanguageSwitcher />
        </div>

        <div className="text-center mb-16">
          <h1 className="text-4xl font-black text-white mb-4">{t.pricingPublic.title}</h1>
          <p className="text-zinc-400 text-lg break-keep">{t.pricingPublic.sub}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">

          {/* Basic Plan */}
          <div className="rounded-3xl p-8 border border-zinc-800 bg-zinc-900/30 flex flex-col">
            <h2 className="text-2xl font-bold text-white mb-2">{t.plans.basicName}</h2>
            <p className="text-zinc-400 text-sm mb-6">{t.plans.basicDesc}</p>
            <div className="mb-8">
              <span className="text-5xl font-black text-white">$0</span>
              <span className="text-zinc-400 ml-1">{t.common.perMonth}</span>
            </div>
            <ul className="space-y-4 mb-10 flex-1">
              {[basic.testsPerMonth, basic.concurrent, basic.variants, basic.interval].map((feature) => (
                <li key={feature} className="flex items-center gap-3 text-sm text-zinc-300">
                  <Check size={16} className="text-zinc-400 flex-shrink-0" aria-hidden="true" />
                  {feature}
                </li>
              ))}
            </ul>
            <Link
              href={localizePath("/login", locale)}
              className="w-full py-4 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-white font-bold text-center transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
            >
              {t.plans.startForFree}
            </Link>
          </div>

          {/* Pro Plan */}
          <div className="rounded-3xl p-8 border border-cyan-500/50 bg-cyan-500/5 flex flex-col relative overflow-hidden shadow-[0_0_40px_rgba(6,182,212,0.12)]">
            <div className="absolute top-0 right-0 bg-gradient-to-r from-cyan-500 to-blue-500 text-white text-xs font-bold px-4 py-1.5 rounded-bl-xl uppercase tracking-wider flex items-center gap-1.5">
              <Zap size={12} fill="currentColor" aria-hidden="true" /> {t.plans.mostPopular}
            </div>
            <h2 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-400 mb-2 flex items-center gap-2">
              <Crown size={22} className="text-cyan-400" aria-hidden="true" />
              {t.plans.proName}
            </h2>
            <p className="text-zinc-400 text-sm mb-6">{t.plans.proDesc}</p>
            <div className="mb-8">
              <span className="text-5xl font-black text-white">$29</span>
              <span className="text-zinc-400 ml-1">{t.common.perMonth}</span>
            </div>
            <ul className="space-y-4 mb-10 flex-1">
              <ProFeature><RichText value={pro.testsPerMonth} strongClassName={strong} /></ProFeature>
              <ProFeature><RichText value={pro.concurrent} strongClassName={strong} /></ProFeature>
              <ProFeature>{pro.variants}</ProFeature>
              <ProFeature><RichText value={pro.interval} strongClassName={strong} /></ProFeature>
              <ProFeature><RichText value={pro.email} strongClassName={strong} /></ProFeature>
            </ul>
            <PaddleCheckoutButton />
          </div>
        </div>

        <div className="mt-12 text-center text-sm text-zinc-500">
          <RichText value={t.pricingPublic.paddleNote} strongClassName="text-zinc-400 font-medium" />
        </div>
      </div>
    </div>
  );
}

function ProFeature({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex items-center gap-3 text-sm text-zinc-100">
      <Check size={16} className="text-cyan-400 flex-shrink-0" aria-hidden="true" />
      <span>{children}</span>
    </li>
  );
}
