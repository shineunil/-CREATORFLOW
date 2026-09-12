import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export const metadata = {
  title: "Terms of Service | ThumbnailFlow",
};

export default function TermsPage() {
  return (
    <div className="min-h-screen bg-[#050505] text-zinc-300">
      <div className="max-w-3xl mx-auto px-6 py-16">
        <Link href="/" className="inline-flex items-center gap-2 text-zinc-400 hover:text-white transition-colors mb-10 text-sm rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
          <ArrowLeft size={16} aria-hidden="true" /> Back to Home
        </Link>

        <h1 className="text-3xl font-black text-white mb-2">Terms of Service</h1>
        <p className="text-sm text-zinc-400 mb-10">Last updated: 2026-09-08</p>

        <div className="space-y-8 text-sm leading-relaxed">
          <section>
            <h2 className="text-lg font-bold text-white mb-3">1. Overview of the Service</h2>
            <p className="text-zinc-400">
              ThumbnailFlow (the &quot;Service&quot;) is an A/B testing tool that automatically rotates thumbnail and title candidates on a user&apos;s connected YouTube video, measures their performance (view count, views-per-hour (VPH), and actual YouTube Analytics CTR), and identifies the best-performing combination.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-white mb-3">2. Account and Channel Connection</h2>
            <ul className="list-disc list-inside space-y-1 text-zinc-400">
              <li>You sign in with your Google account. Using the Service requires granting OAuth consent to connect a YouTube channel.</li>
              <li>You may disconnect a channel at any time from the Settings page; doing so immediately stops any in-progress automated swaps for that channel.</li>
              <li>If YouTube revokes or expires the connection token, the Service pauses automated swaps for that channel and prompts you to reconnect.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-bold text-white mb-3">3. Plans</h2>
            <p className="text-zinc-400">
              We offer a BASIC (free) plan and a PRO plan. Limits on concurrent tests, swap interval, and candidate count for each plan are described in the app. Payments are processed via Paddle, and you can change or cancel your plan from the Settings page.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-white mb-3">4. Refunds</h2>
            <p className="text-zinc-400">
              You may request a full refund of your PRO plan payment within 7 days of the payment date, provided you have not used the Service during that period (i.e., you have not created any A/B test). Once you have created at least one test, or once 7 days have passed since payment, that payment becomes non-refundable, except where a refund is required by applicable law. To request a refund, contact us at the email address below; refunds are reviewed and processed through Paddle, our payment provider.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-white mb-3">5. Limitation of Liability</h2>
            <p className="text-zinc-400">
              The Service estimates performance based on data provided by the YouTube Data API and YouTube Analytics API. Due to the nature of these APIs (reporting delay, sample size, etc.), measured view counts and click-through rates may differ from YouTube&apos;s own statistics, and the Service does not guarantee any specific performance improvement. You are responsible for ensuring that any thumbnails or titles automatically applied by the Service comply with YouTube&apos;s policies and Community Guidelines.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-white mb-3">6. Changes to and Discontinuation of the Service</h2>
            <p className="text-zinc-400">
              We may modify features of the Service for operational or legal reasons, or discontinue it after providing prior notice.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-white mb-3">7. Contact</h2>
            <p className="text-zinc-400">
              For questions about using the Service, please contact us at kising26903854@gmail.com.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
