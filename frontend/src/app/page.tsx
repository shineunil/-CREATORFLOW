"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowRight, Crown, TrendingUp, Upload, RefreshCw, Award, Check, Minus } from "lucide-react";
import { useEffect, useState } from "react";

export default function LandingPage() {
  const [vph, setVph] = useState(42);

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

  return (
    <div className="min-h-screen bg-[#050505] text-zinc-100 selection:bg-cyan-500/30 overflow-x-hidden">
      {/* Background */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1100px] h-[520px] bg-gradient-to-br from-cyan-600/10 via-transparent to-violet-600/10 blur-[130px] rounded-full pointer-events-none" aria-hidden="true" />

      {/* Hero Section */}
      <section className="relative pt-36 pb-20 px-6 max-w-6xl mx-auto text-center z-10">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: "easeOut" }}
        >
          <div className="inline-flex items-center gap-2 text-xs font-semibold tracking-[0.2em] uppercase text-cyan-400/90 mb-7">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" aria-hidden="true" />
            Thumbnail testing for YouTube creators
          </div>

          <h1 className="text-5xl md:text-7xl font-black tracking-tight mb-7 leading-[1.08]">
            Same video.<br className="hidden md:block" />{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-violet-400">
              Different thumbnails.
            </span>{" "}
            One clear winner.
          </h1>

          <p className="text-lg md:text-xl text-zinc-400 max-w-2xl mx-auto mb-11 leading-relaxed">
            Upload a few thumbnail and title variants. CreatorFlow rotates them on your
            live video and ranks each by views earned per hour — not raw view count —
            so a slow afternoon slot never gets mistaken for a loser.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/login"
              className="group relative flex items-center gap-2 px-8 py-4 bg-white text-black font-bold text-lg rounded-full overflow-hidden transition-transform hover:scale-[1.03] active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-black"
            >
              <span className="relative z-10">Start testing — free</span>
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
                   <span className="bg-zinc-800 text-zinc-300 text-xs font-bold px-3 py-1.5 rounded-full uppercase tracking-wider">Control</span>
                   <div className="text-right">
                     <div className="text-[10px] text-zinc-500 uppercase font-bold tracking-wide">Current VPH</div>
                     <div className="text-xl font-black text-zinc-400">42</div>
                   </div>
                </div>

                <div className="flex flex-col">
                  <div className="relative rounded-xl overflow-hidden aspect-video">
                     <img src="/hero-control.jpg" alt="Original thumbnail" className="w-full h-full object-cover opacity-75 grayscale-[35%]" />
                     <div className="absolute bottom-1.5 right-1.5 bg-black/90 text-white text-xs font-medium px-1.5 py-0.5 rounded">
                       12:45
                     </div>
                  </div>
                  <div className="flex gap-3 mt-3">
                    <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-zinc-700 to-zinc-600 flex items-center justify-center text-sm font-bold text-zinc-300 flex-shrink-0 mt-0.5">
                       Y
                    </div>
                    <div className="flex flex-col text-left">
                      <h3 className="text-zinc-300 text-[15px] font-semibold leading-tight line-clamp-2">Under the Stars: I Saw You</h3>
                      <span className="text-zinc-500 text-[13px] mt-1">Your Channel</span>
                      <span className="text-zinc-500 text-[13px]">Swapped 2h ago</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Thumbnail B (Winner) */}
              <div className="relative rounded-2xl border border-cyan-500/60 bg-[#0f0f0f] p-4 md:p-5 flex flex-col shadow-[0_0_30px_rgba(6,182,212,0.12)] overflow-hidden">
                <div className="absolute inset-0 bg-cyan-500/5 pointer-events-none" />

                <div className="flex justify-between items-center mb-5 relative z-10">
                   <span className="bg-cyan-500 text-black text-xs font-black px-3 py-1.5 rounded-full flex items-center gap-1.5 uppercase tracking-wider shadow-lg"><Crown size={14}/> Leading</span>
                   <div className="text-right">
                     <div className="text-[10px] text-cyan-400 uppercase font-bold flex items-center justify-end gap-1 tracking-wide"><TrendingUp size={12}/> Live VPH</div>
                     <div className="text-3xl font-black text-cyan-400">{vph}</div>
                   </div>
                </div>

                <div className="flex flex-col relative z-10">
                  <div className="relative rounded-xl overflow-hidden aspect-video">
                     <img src="/hero-leading.jpg" alt="Variant thumbnail" className="w-full h-full object-cover transition-transform duration-500" />
                     <div className="absolute bottom-1.5 right-1.5 bg-black/90 text-white text-xs font-medium px-1.5 py-0.5 rounded">
                       12:45
                     </div>
                  </div>
                  <div className="flex gap-3 mt-3">
                    <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-cyan-600 to-blue-600 flex items-center justify-center text-sm font-bold text-white flex-shrink-0 mt-0.5">
                       Y
                    </div>
                    <div className="flex flex-col text-left">
                      <h3 className="text-white text-[15px] font-semibold leading-tight line-clamp-2">Under the Stars: I Saw You</h3>
                      <span className="text-zinc-400 text-[13px] mt-1">Your Channel</span>
                      <span className="text-zinc-400 text-[13px]">Swapped 14m ago</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="hidden md:flex absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-14 h-14 bg-zinc-950 border border-zinc-700 rounded-full items-center justify-center z-20 shadow-2xl">
                <span className="text-lg font-black italic text-zinc-500">VS</span>
              </div>
            </div>
          </div>
        </motion.div>
      </section>

      {/* Process Section */}
      <section className="py-28 md:py-32 bg-zinc-950 border-t border-zinc-900 relative z-10">
        <div className="max-w-6xl mx-auto px-6">
          <div className="max-w-xl mb-20">
            <h2 className="text-3xl md:text-4xl font-black mb-4">How it runs, end to end.</h2>
            <p className="text-zinc-400 text-lg">Three steps, entirely automated once you hit start.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-x-8 gap-y-14 relative">
            <div className="hidden md:block absolute top-6 left-[16.5%] right-[16.5%] h-px bg-gradient-to-r from-transparent via-zinc-800 to-transparent" aria-hidden="true" />

            <StepCard
              delay={0.05}
              number="01"
              icon={<Upload size={16} />}
              title="Upload your variants"
              desc="Add up to five thumbnail and title candidates for a video you've already published. Takes under a minute."
            />
            <StepCard
              delay={0.15}
              number="02"
              icon={<RefreshCw size={16} />}
              title="It rotates on its own"
              desc="CreatorFlow swaps the live thumbnail and title on a schedule — every 4+ hours on the free plan, as often as every 30 minutes on PRO — and discards the first few minutes after each swap so leftover exposure can't skew the count."
            />
            <StepCard
              delay={0.25}
              number="03"
              icon={<Award size={16} />}
              title="A winner gets locked in"
              desc="Once every variant has had a fair, full rotation and enough views to be meaningful, the highest-VPH candidate is applied permanently — and stays there."
            />
          </div>

          <div className="mt-16 flex justify-center">
            <Link
              href="/login"
              className="group inline-flex items-center gap-2 px-7 py-3.5 bg-zinc-100 text-black font-bold rounded-full transition-transform hover:scale-[1.03] active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
            >
              Try it on your own video
              <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>

      {/* Comparison Section */}
      <section className="py-28 md:py-32 relative z-10">
        <div className="max-w-5xl mx-auto px-6">
          <div className="max-w-xl mb-16">
            <h2 className="text-3xl md:text-4xl font-black mb-4">Doesn&apos;t YouTube already do this?</h2>
            <p className="text-zinc-400 text-lg">
              Yes — Test and Compare is a real, free, native feature. It&apos;s built for a slower, more
              conservative rollout. CreatorFlow is built for creators who want to iterate faster and
              run more than one channel.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/30 p-8">
              <h3 className="text-base font-bold uppercase tracking-wider text-zinc-400 mb-6">YouTube Test and Compare</h3>
              <ComparisonRow label="Candidates per test" value="Up to 3" muted />
              <ComparisonRow label="Time to a result" value="2+ weeks, 1–5K views/variant" muted />
              <ComparisonRow label="Manual override" value="Not available" negative />
              <ComparisonRow label="Manage multiple channels" value="One at a time in Studio" negative />
            </div>

            <div className="rounded-2xl border border-cyan-500/40 bg-cyan-500/5 p-8 shadow-[0_0_30px_rgba(6,182,212,0.08)]">
              <h3 className="text-base font-bold uppercase tracking-wider text-cyan-400 mb-6">CreatorFlow</h3>
              <ComparisonRow label="Candidates per test" value="Up to 5" />
              <ComparisonRow label="Time to a result" value="As fast as 30 minutes per swap" />
              <ComparisonRow label="Manual override" value="Force a swap or lock a winner anytime" />
              <ComparisonRow label="Manage multiple channels" value="One dashboard, switch instantly" />
            </div>
          </div>

          <p className="text-base text-zinc-400 mt-6 max-w-2xl">
            Faster iteration trades some statistical patience for speed — that&apos;s why CreatorFlow
            enforces its own minimum cycles and sample size before calling a winner, rather than
            declaring one on the first lucky swap.
          </p>

          <div className="mt-12">
            <Link
              href="/login"
              className="group inline-flex items-center gap-2 px-7 py-3.5 bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/20 font-bold rounded-full transition-all hover:scale-[1.03] active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-black"
            >
              Run your first test
              <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" aria-hidden="true" />
            </Link>
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
          <h2 className="text-4xl md:text-5xl font-black text-white mb-6">
            Stop guessing which thumbnail wins.
          </h2>
          <p className="text-xl text-zinc-400 mb-10">
            Every test runs in the background. Come back when there&apos;s a winner.
          </p>
          <Link href="/login" className="inline-flex items-center gap-2 px-10 py-4 bg-cyan-500 text-black hover:bg-cyan-400 rounded-full font-bold text-lg transition-all hover:scale-[1.03] active:scale-95 shadow-[0_0_40px_rgba(6,182,212,0.25)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-black">
            Start testing — free
            <ArrowRight size={20} aria-hidden="true" />
          </Link>
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="py-10 text-center border-t border-zinc-900 bg-zinc-950 relative z-10">
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 sm:gap-8 text-sm text-zinc-400">
          <span>© 2026 CreatorFlow</span>
          <Link href="/privacy" className="hover:text-zinc-300 transition-colors rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">Privacy Policy</Link>
          <Link href="/terms" className="hover:text-zinc-300 transition-colors rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">Terms of Service</Link>
        </div>
      </footer>
    </div>
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

function StepCard({ icon, number, title, desc, delay }: { icon: React.ReactNode, number: string, title: string, desc: string, delay: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-50px" }}
      transition={{ duration: 0.5, delay }}
      className="relative"
    >
      <div className="relative z-10 w-12 h-12 rounded-full bg-zinc-950 border border-zinc-800 flex items-center justify-center text-sm font-bold text-zinc-400 mb-6" aria-hidden="true">
        {number}
      </div>
      <div className="flex items-center gap-2 text-cyan-400 mb-3" aria-hidden="true">
        {icon}
      </div>
      <h3 className="text-xl font-bold text-white mb-3">{title}</h3>
      <p className="text-zinc-400 leading-relaxed">{desc}</p>
    </motion.div>
  );
}
