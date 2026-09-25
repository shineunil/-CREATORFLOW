"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowRight, Crown, TrendingUp, Upload, RefreshCw, Award, Check, Minus, Clock, X, Megaphone } from "lucide-react";
import { useEffect, useState } from "react";
import { useI18n } from "@/i18n/I18nProvider";
import RichText from "@/i18n/RichText";

const LAUNCH_POPUP_KEY = "launch_popup_hidden";
const STEP_ICONS = [<Upload key="upload" size={16} />, <Clock key="clock" size={16} />, <RefreshCw key="rotate" size={16} />, <TrendingUp key="track" size={16} />, <Award key="award" size={16} />];

export default function LandingPage() {
  const { t, lp, locale } = useI18n();
  const L = t.landing;
  const [vph, setVph] = useState(42);
  const [popupVisible, setPopupVisible] = useState(false);
  const [hideToday, setHideToday] = useState(false);

  useEffect(() => {
    try {
      const hidden = localStorage.getItem(LAUNCH_POPUP_KEY);
      const today = new Date().toISOString().slice(0, 10);
      if (hidden === today) return;
    } catch {}
    setPopupVisible(true);
  }, []);

  const dismissPopup = () => {
    if (hideToday) {
      try {
        localStorage.setItem(LAUNCH_POPUP_KEY, new Date().toISOString().slice(0, 10));
      } catch {}
    }
    setPopupVisible(false);
  };

  // VPH(시간당 조회수) 올라가는 애니메이션 효과
  useEffect(() => {
    const timer = setTimeout(() => {
      const interval = setInterval(() => {
        setVph(prev => {
          if (prev >= 118) {
            clearInterval(interval);
            return 118;
          }
          return prev + 2;
        });
      }, 40);
      return () => clearInterval(interval);
    }, 1000);
    return () => clearTimeout(timer);
  }, []);

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "ThumbnailFlow",
    applicationCategory: "BusinessApplication",
    operatingSystem: "Web",
    url: "https://trythumbnailflow.com",
    description:
      "A/B testing tool that automatically rotates YouTube thumbnail and title variants on your live video and keeps the one with the highest views per hour.",
    offers: [
      {
        "@type": "Offer",
        price: "0",
        priceCurrency: "USD",
        name: "BASIC",
      },
      {
        "@type": "Offer",
        price: "29",
        priceCurrency: "USD",
        name: "PRO Premium",
        billingIncrement: "P1M",
      },
    ],
  };

  return (
    <div className="min-h-screen bg-[#050505] text-zinc-100 selection:bg-cyan-500/30 overflow-x-hidden">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      {/* Background */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1100px] h-[520px] bg-gradient-to-br from-cyan-600/10 via-transparent to-violet-600/10 blur-[130px] rounded-full pointer-events-none" aria-hidden="true" />

      {/* Hero Section */}
      <section className="relative pt-36 pb-20 px-6 max-w-6xl mx-auto text-center z-10">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: "easeOut" }}
        >
          <div className="inline-flex items-center gap-2 text-base font-semibold tracking-[0.12em] uppercase text-cyan-400/90 mb-7">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" aria-hidden="true" />
            {L.eyebrow}
          </div>

          {/* 한글은 글자 폭이 넓어 휴대폰에서 한 단계 작게 (데스크톱 크기는 같음) */}
          <h1 className={`${locale === "ko" ? "text-4xl" : "text-5xl"} md:text-7xl font-black tracking-tight mb-7 leading-[1.08] break-keep`}>
            {L.heroLine1}<br className="hidden md:block" />{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-violet-400">
              {L.heroGradient}
            </span>
            {L.heroBreakBeforeLine3 && <br className="hidden md:block" />}{" "}
            {L.heroLine3}
          </h1>

          <p className="text-lg md:text-xl text-white max-w-2xl mx-auto mb-11 leading-relaxed break-keep">
            {L.heroSub}
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href={lp("/login")}
              className="group relative flex items-center gap-2 px-8 py-4 bg-white text-black font-bold text-lg rounded-full overflow-hidden transition-transform hover:scale-[1.03] active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-black"
            >
              <span className="relative z-10">{L.heroCta}</span>
              <ArrowRight size={20} className="relative z-10 group-hover:translate-x-1 transition-transform" aria-hidden="true" />
            </Link>
          </div>
        </motion.div>

        {/* Visual A/B Test Showcase (Authentic YouTube UI) */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, delay: 0.25 }}
          className="mt-24 relative max-w-5xl mx-auto"
          aria-hidden="true"
        >
          <div className="relative bg-zinc-900/70 backdrop-blur-2xl border border-zinc-800 rounded-[2rem] p-6 md:p-10 shadow-2xl">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 md:gap-16 relative">

              {/* Thumbnail A (Control) */}
              <div className="relative rounded-2xl border border-zinc-800 bg-[#0f0f0f] p-4 md:p-5 flex flex-col">
                <div className="flex justify-between items-center mb-5">
                   <span className="bg-zinc-800 text-zinc-300 text-xs font-bold px-3 py-1.5 rounded-full uppercase tracking-wider">{L.showcase.control}</span>
                   <div className="text-right">
                     <div className="text-[10px] text-zinc-400 uppercase font-bold tracking-wide">{L.showcase.currentVph}</div>
                     <div className="text-xl font-black text-zinc-400">42</div>
                   </div>
                </div>

                <div className="flex flex-col">
                  <div className="relative rounded-xl overflow-hidden aspect-video">
                     <img src="/hero-control.jpg" alt={L.showcase.originalAlt} className="w-full h-full object-cover opacity-75 grayscale-[35%]" />
                     <div className="absolute bottom-1.5 right-1.5 bg-black/90 text-white text-xs font-medium px-1.5 py-0.5 rounded">
                       12:45
                     </div>
                  </div>
                  <div className="flex gap-3 mt-3">
                    <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-zinc-700 to-zinc-600 flex items-center justify-center text-sm font-bold text-zinc-300 flex-shrink-0 mt-0.5">
                       Y
                    </div>
                    <div className="flex flex-col text-left">
                      <h3 className="text-zinc-300 text-[15px] font-semibold leading-tight line-clamp-2">{L.showcase.videoTitle}</h3>
                      <span className="text-zinc-400 text-[13px] mt-1">{L.showcase.channel}</span>
                      <span className="text-zinc-400 text-[13px]">{L.showcase.swapped2h}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Thumbnail B (Winner) */}
              <div className="relative rounded-2xl border border-cyan-500/60 bg-[#0f0f0f] p-4 md:p-5 flex flex-col shadow-[0_0_30px_rgba(6,182,212,0.12)] overflow-hidden">
                <div className="absolute inset-0 bg-cyan-500/5 pointer-events-none" />

                <div className="flex justify-between items-center mb-5 relative z-10">
                   <span className="bg-cyan-500 text-black text-xs font-black px-3 py-1.5 rounded-full flex items-center gap-1.5 uppercase tracking-wider shadow-lg"><Crown size={14}/> {L.showcase.leading}</span>
                   <div className="text-right">
                     <div className="text-[10px] text-cyan-400 uppercase font-bold flex items-center justify-end gap-1 tracking-wide"><TrendingUp size={12}/> {L.showcase.liveVph}</div>
                     <div className="text-3xl font-black text-cyan-400">{vph}</div>
                   </div>
                </div>

                <div className="flex flex-col relative z-10">
                  <div className="relative rounded-xl overflow-hidden aspect-video">
                     <img src="/hero-leading.jpg" alt={L.showcase.variantAlt} className="w-full h-full object-cover transition-transform duration-500" />
                     <div className="absolute bottom-1.5 right-1.5 bg-black/90 text-white text-xs font-medium px-1.5 py-0.5 rounded">
                       12:45
                     </div>
                  </div>
                  <div className="flex gap-3 mt-3">
                    <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-cyan-600 to-blue-600 flex items-center justify-center text-sm font-bold text-white flex-shrink-0 mt-0.5">
                       Y
                    </div>
                    <div className="flex flex-col text-left">
                      <h3 className="text-white text-[15px] font-semibold leading-tight line-clamp-2">{L.showcase.videoTitle}</h3>
                      <span className="text-zinc-400 text-[13px] mt-1">{L.showcase.channel}</span>
                      <span className="text-zinc-400 text-[13px]">{L.showcase.swapped14m}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="hidden md:flex absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-14 h-14 bg-zinc-950 border border-zinc-700 rounded-full items-center justify-center z-20 shadow-2xl">
                <span className="text-lg font-black italic text-zinc-300">VS</span>
              </div>
            </div>
          </div>
        </motion.div>
      </section>

      {/* Process Section */}
      <section className="py-28 md:py-32 bg-zinc-950 border-t border-zinc-900 relative z-10">
        <div className="max-w-6xl mx-auto px-6">
          <div className="max-w-xl mb-20">
            <h2 className="text-3xl md:text-4xl font-black mb-4 break-keep">{L.processTitle}</h2>
            <p className="text-zinc-400 text-lg break-keep">{L.processSub}</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-x-6 gap-y-14">
            {L.steps.map((step, i) => (
              <StepCard
                key={step.title}
                delay={0.05 * (i + 1)}
                number={String(i + 1).padStart(2, "0")}
                icon={STEP_ICONS[i]}
                title={step.title}
                desc={step.desc}
                isLast={i === L.steps.length - 1}
              />
            ))}
          </div>

          <div className="mt-16 flex justify-center">
            <Link
              href={lp("/login")}
              className="group inline-flex items-center gap-2 px-7 py-3.5 bg-zinc-100 text-black font-bold rounded-full transition-transform hover:scale-[1.03] active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
            >
              {L.processCta}
              <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>

      {/* Comparison Section */}
      <section className="py-28 md:py-32 relative z-10">
        <div className="max-w-5xl mx-auto px-6">
          <div className="max-w-xl mb-16">
            <h2 className="text-3xl md:text-4xl font-black mb-4 break-keep">{L.compareTitle}</h2>
            <p className="text-zinc-400 text-lg break-keep">{L.compareSub}</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="rounded-2xl border border-cyan-500/40 bg-cyan-500/5 p-8 shadow-[0_0_30px_rgba(6,182,212,0.08)]">
              <h3 className="text-base font-bold uppercase tracking-wider text-cyan-400 mb-6">{L.compareYoutube}</h3>
              <ComparisonRow label={L.compareRows.candidates} value={L.compareYoutubeValues.candidates} />
              <ComparisonRow label={L.compareRows.time} value={L.compareYoutubeValues.time} />
              <ComparisonRow label={L.compareRows.override} value={L.compareYoutubeValues.override} />
              <ComparisonRow label={L.compareRows.channels} value={L.compareYoutubeValues.channels} />
            </div>

            <div className="rounded-2xl border border-cyan-500/40 bg-cyan-500/5 p-8 shadow-[0_0_30px_rgba(6,182,212,0.08)]">
              <h3 className="text-base font-bold uppercase tracking-wider text-cyan-400 mb-6">{L.compareUs}</h3>
              <ComparisonRow label={L.compareRows.candidates} value={L.compareUsValues.candidates} />
              <ComparisonRow label={L.compareRows.time} value={L.compareUsValues.time} />
              <ComparisonRow label={L.compareRows.override} value={L.compareUsValues.override} />
              <ComparisonRow label={L.compareRows.channels} value={L.compareUsValues.channels} />
            </div>
          </div>

          <p className="text-base text-zinc-400 mt-6 max-w-2xl break-keep">{L.compareNote}</p>

          <div className="mt-12">
            <Link
              href={lp("/login")}
              className="group inline-flex items-center gap-2 px-7 py-3.5 bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/20 font-bold rounded-full transition-all hover:scale-[1.03] active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-black"
            >
              {L.compareCta}
              <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="py-28 md:py-32 bg-zinc-950 border-t border-zinc-900 relative z-10">
        <div className="max-w-5xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-black mb-4 break-keep">{L.pricingTitle}</h2>
            <p className="text-zinc-400 text-lg break-keep">{L.pricingSub}</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            {/* Basic Plan */}
            <div className="rounded-3xl p-8 border border-cyan-500/50 bg-cyan-500/5 flex flex-col shadow-[0_0_40px_rgba(6,182,212,0.12)]">
              <h3 className="text-2xl font-bold mb-2 text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-400">{t.plans.basicName}</h3>
              <p className="text-zinc-400 text-base mb-6">{t.plans.basicDesc}</p>
              <div className="mb-8">
                <span className="text-4xl font-bold">$0</span>
                <span className="text-zinc-400"> {t.common.perMonth}</span>
              </div>
              <ul className="space-y-4 mb-10 flex-1">
                {[t.plans.basicFeatures.testsPerMonth, t.plans.basicFeatures.concurrent, t.plans.basicFeatures.variants, t.plans.basicFeatures.interval].map((feature) => (
                  <li key={feature} className="flex items-center gap-3 text-base text-zinc-300"><Check size={16} className="text-zinc-400 flex-shrink-0" aria-hidden="true" /> {feature}</li>
                ))}
                <li className="flex items-center gap-3 text-base text-zinc-300"><Check size={16} className="text-zinc-400 flex-shrink-0" aria-hidden="true" /> <span><RichText value={t.plans.autoApplyRich} strongClassName="font-semibold text-cyan-300" /></span></li>
              </ul>
              <Link href={lp("/login")} className="w-full py-4 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-white font-bold text-center transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
                {t.plans.startForFree}
              </Link>
            </div>

            {/* Pro Plan */}
            <div className="rounded-3xl p-8 border border-cyan-500/50 bg-cyan-500/5 flex flex-col relative overflow-hidden shadow-[0_0_40px_rgba(6,182,212,0.12)]">
              <div className="absolute top-0 right-0 bg-gradient-to-r from-cyan-500 to-blue-500 text-white text-xs font-bold px-4 py-1.5 rounded-bl-xl uppercase tracking-wider">
                {t.plans.mostPopular}
              </div>
              <h3 className="text-2xl font-bold mb-2 text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-400">{t.plans.proName}</h3>
              <p className="text-zinc-400 text-base mb-6">{t.plans.proDesc}</p>
              <div className="mb-8">
                <span className="text-4xl font-bold">$29</span>
                <span className="text-zinc-400"> {t.common.perMonth}</span>
              </div>
              <ul className="space-y-4 mb-10 flex-1">
                <ProFeature><RichText value={t.plans.proFeatures.testsPerMonth} strongClassName="font-semibold text-cyan-300" /></ProFeature>
                <ProFeature><RichText value={t.plans.proFeatures.concurrent} strongClassName="font-semibold text-cyan-300" /></ProFeature>
                <ProFeature>{t.plans.proFeatures.variants}</ProFeature>
                <ProFeature><RichText value={t.plans.proFeatures.interval} strongClassName="font-semibold text-cyan-300" /></ProFeature>
                <ProFeature><RichText value={t.plans.autoApplyRich} strongClassName="font-semibold text-cyan-300" /></ProFeature>
                <ProFeature><RichText value={t.plans.proFeatures.email} strongClassName="font-semibold text-cyan-300" /></ProFeature>
              </ul>
              <Link href={lp("/login")} className="w-full py-4 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-bold text-center transition-all shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
                {t.plans.getStarted}
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-28 md:py-32 relative overflow-hidden text-center z-10">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent to-cyan-950/10 pointer-events-none" />
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="max-w-3xl mx-auto px-6 relative z-10"
        >
          <h2 className={`${locale === "ko" ? "text-[28px]" : "text-4xl"} md:text-5xl font-black text-white mb-6 break-keep whitespace-pre-line`}>
            {L.finalTitle}
          </h2>
          <p className="text-xl text-zinc-400 mb-10 break-keep">
            {L.finalSub}
          </p>
          <Link href={lp("/login")} className="inline-flex items-center gap-2 px-10 py-4 bg-cyan-500 text-black hover:bg-cyan-400 rounded-full font-bold text-lg transition-all hover:scale-[1.03] active:scale-95 shadow-[0_0_40px_rgba(6,182,212,0.25)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-black">
            {L.finalCta}
            <ArrowRight size={20} aria-hidden="true" />
          </Link>
        </motion.div>
      </section>

      {/* Launch Announcement Popup */}
      {popupVisible && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="launch-popup-title"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
        >
          <div className="bg-zinc-950 border border-cyan-500/40 rounded-3xl p-6 md:p-8 max-w-md w-full shadow-[0_0_50px_rgba(6,182,212,0.2)] relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-cyan-500 via-blue-500 to-violet-500" aria-hidden="true" />

            <div className="flex justify-between items-start mb-4">
              <div className="flex items-center gap-2">
                <Megaphone size={20} className="text-cyan-400" aria-hidden="true" />
                <span className="text-xs font-bold uppercase tracking-wider text-cyan-400">{L.popup.notice}</span>
              </div>
              <button
                onClick={dismissPopup}
                aria-label={L.popup.close}
                className="text-zinc-400 hover:text-white p-1 rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
              >
                <X size={18} aria-hidden="true" />
              </button>
            </div>

            <h2 id="launch-popup-title" className="text-xl font-extrabold text-white mb-3">
              {L.popup.title}
            </h2>
            <p className="text-zinc-300 text-sm leading-relaxed mb-6 break-keep">
              <RichText value={L.popup.body} strongClassName="text-white font-semibold" />
            </p>

            <label className="flex items-center gap-2 mb-4 cursor-pointer select-none group">
              <input
                type="checkbox"
                checked={hideToday}
                onChange={e => setHideToday(e.target.checked)}
                className="w-4 h-4 rounded border-zinc-600 bg-zinc-800 accent-cyan-500 cursor-pointer"
              />
              <span className="text-xs text-zinc-400 group-hover:text-zinc-300 transition-colors">
                {L.popup.hideToday}
              </span>
            </label>

            <div className="flex gap-3">
              <button
                onClick={dismissPopup}
                className="flex-1 py-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-bold text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
              >
                {L.popup.closeButton}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="py-10 text-center border-t border-zinc-900 bg-zinc-950 relative z-10">
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 sm:gap-8 text-sm text-white">
          <span>© 2026 ThumbnailFlow</span>
          <a href="mailto:admin@trythumbnailflow.com" className="hover:text-zinc-300 transition-colors rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">{L.footer.support}</a>
          <Link href={lp("/privacy")} className="hover:text-zinc-300 transition-colors rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">{L.footer.privacy}</Link>
          <Link href={lp("/terms")} className="hover:text-zinc-300 transition-colors rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">{L.footer.terms}</Link>
          <Link href={lp("/faq")} className="hover:text-zinc-300 transition-colors rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">{L.footer.faq}</Link>
        </div>
      </footer>
    </div>
  );
}

function ProFeature({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex items-center gap-3 text-base text-zinc-100">
      <Check size={16} className="text-cyan-400 flex-shrink-0" aria-hidden="true" />
      <span>{children}</span>
    </li>
  );
}

function ComparisonRow({ label, value, muted, negative }: { label: string, value: string, muted?: boolean, negative?: boolean }) {
  return (
    <div className="flex items-start gap-3 py-3 border-b border-zinc-800/60 last:border-b-0">
      {negative ? (
        <Minus size={16} className="text-zinc-400 mt-0.5 flex-shrink-0" aria-hidden="true" />
      ) : (
        <Check size={16} className={`mt-0.5 flex-shrink-0 ${muted ? "text-zinc-400" : "text-cyan-400"}`} aria-hidden="true" />
      )}
      <div>
        <div className="text-sm text-zinc-400 uppercase tracking-wide mb-1">{label}</div>
        <div className={`text-base font-semibold ${muted || negative ? "text-zinc-400" : "text-zinc-100"}`}>{value}</div>
      </div>
    </div>
  );
}

function StepCard({ icon, number, title, desc, delay, isLast = false }: { icon: React.ReactNode, number: string, title: string, desc: string, delay: number, isLast?: boolean }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-50px" }}
      transition={{ duration: 0.5, delay }}
      className="relative"
    >
      <div className="relative z-10 mx-auto w-12 h-12 rounded-full bg-zinc-950 border border-white flex items-center justify-center text-sm font-bold text-white mb-6" aria-hidden="true">
        {number}
      </div>
      {!isLast && (
        <div className="hidden lg:block absolute top-6 left-[calc(50%+1.5rem)] -right-1/2" aria-hidden="true">
          <div className="h-px bg-white w-full" />
          <div className="absolute -top-[5px] right-1/2">
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <polygon points="0,0 10,5 0,10" fill="white" />
            </svg>
          </div>
        </div>
      )}
      <div className="flex items-center gap-2 text-cyan-400 mb-3" aria-hidden="true">
        {icon}
      </div>
      <h3 className="text-xl font-bold text-white mb-3 break-keep">{title}</h3>
      <p className="text-zinc-400 leading-relaxed break-keep">{desc}</p>
    </motion.div>
  );
}
