import Link from "next/link";
import { ArrowLeft, Check, Crown, Zap } from "lucide-react";

export const metadata = {
  title: "Pricing | ThumbnailFlow",
};

export default function PricingPublicPage() {
  return (
    <div className="min-h-screen bg-[#050505] text-zinc-300">
      <div className="max-w-5xl mx-auto px-6 py-16">
        <Link href="/" className="inline-flex items-center gap-2 text-zinc-400 hover:text-white transition-colors mb-10 text-sm rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
          <ArrowLeft size={16} aria-hidden="true" /> Back to Home
        </Link>

        <div className="text-center mb-16">
          <h1 className="text-4xl font-black text-white mb-4">Pricing Plans</h1>
          <p className="text-zinc-400 text-lg">Start free. Upgrade when you&apos;re ready to go unlimited.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">

          {/* Basic Plan */}
          <div className="rounded-3xl p-8 border border-zinc-800 bg-zinc-900/30 flex flex-col">
            <h2 className="text-2xl font-bold text-white mb-2">BASIC</h2>
            <p className="text-zinc-400 text-sm mb-6">For creators who want to try the service</p>
            <div className="mb-8">
              <span className="text-5xl font-black text-white">$0</span>
              <span className="text-zinc-400 ml-1">/ month</span>
            </div>
            <ul className="space-y-4 mb-10 flex-1">
              <li className="flex items-center gap-3 text-sm text-zinc-300">
                <Check size={16} className="text-zinc-400 flex-shrink-0" aria-hidden="true" />
                Max 4 tests per month
              </li>
              <li className="flex items-center gap-3 text-sm text-zinc-300">
                <Check size={16} className="text-zinc-400 flex-shrink-0" aria-hidden="true" />
                1 concurrent test
              </li>
              <li className="flex items-center gap-3 text-sm text-zinc-300">
                <Check size={16} className="text-zinc-400 flex-shrink-0" aria-hidden="true" />
                Up to 3 thumbnail variants (A / B / C)
              </li>
              <li className="flex items-center gap-3 text-sm text-zinc-300">
                <Check size={16} className="text-zinc-400 flex-shrink-0" aria-hidden="true" />
                4-hour minimum swap interval
              </li>
            </ul>
            <Link
              href="/login"
              className="w-full py-4 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-white font-bold text-center transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
            >
              Start for free
            </Link>
          </div>

          {/* Pro Plan */}
          <div className="rounded-3xl p-8 border border-cyan-500/50 bg-cyan-500/5 flex flex-col relative overflow-hidden shadow-[0_0_40px_rgba(6,182,212,0.12)]">
            <div className="absolute top-0 right-0 bg-gradient-to-r from-cyan-500 to-blue-500 text-white text-xs font-bold px-4 py-1.5 rounded-bl-xl uppercase tracking-wider flex items-center gap-1.5">
              <Zap size={12} fill="currentColor" aria-hidden="true" /> Most Popular
            </div>
            <h2 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-400 mb-2 flex items-center gap-2">
              <Crown size={22} className="text-cyan-400" aria-hidden="true" />
              PRO Premium
            </h2>
            <p className="text-zinc-400 text-sm mb-6">For serious creators who want to maximize views</p>
            <div className="mb-8">
              <span className="text-5xl font-black text-white">$29</span>
              <span className="text-zinc-400 ml-1">/ month</span>
            </div>
            <ul className="space-y-4 mb-10 flex-1">
              <li className="flex items-center gap-3 text-sm text-zinc-100">
                <Check size={16} className="text-cyan-400 flex-shrink-0" aria-hidden="true" />
                <span className="font-semibold text-cyan-300">Unlimited</span> tests per month
              </li>
              <li className="flex items-center gap-3 text-sm text-zinc-100">
                <Check size={16} className="text-cyan-400 flex-shrink-0" aria-hidden="true" />
                <span className="font-semibold text-cyan-300">Unlimited</span> concurrent tests
              </li>
              <li className="flex items-center gap-3 text-sm text-zinc-100">
                <Check size={16} className="text-cyan-400 flex-shrink-0" aria-hidden="true" />
                Up to 5 thumbnail variants (A ~ E)
              </li>
              <li className="flex items-center gap-3 text-sm text-zinc-100">
                <Check size={16} className="text-cyan-400 flex-shrink-0" aria-hidden="true" />
                <span className="font-semibold text-cyan-300">30-minute</span> swap interval
              </li>
              <li className="flex items-center gap-3 text-sm text-zinc-100">
                <Check size={16} className="text-cyan-400 flex-shrink-0" aria-hidden="true" />
                Test completion <span className="font-semibold text-cyan-300">email notification</span>
              </li>
            </ul>
            <button
              disabled
              title="Payment system coming soon"
              className="w-full py-4 rounded-xl bg-zinc-800 text-zinc-500 font-bold border border-zinc-700 cursor-not-allowed"
            >
              Coming Soon
            </button>
          </div>
        </div>

        <div className="mt-12 text-center text-sm text-zinc-500">
          Payments securely processed by <span className="text-zinc-400 font-medium">Paddle</span>. Cancel anytime.
        </div>
      </div>
    </div>
  );
}
