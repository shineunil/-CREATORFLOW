import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export const metadata = {
  title: "FAQ | ThumbnailFlow",
  description: "Frequently asked questions about ThumbnailFlow — safety, how it works, billing, and channel setup.",
};

const faqs: { section: string; items: { q: string; a: string }[] }[] = [
  {
    section: "Safety & Security",
    items: [
      {
        q: "Is ThumbnailFlow safe for my YouTube channel?",
        a: "Yes, completely safe. ThumbnailFlow only changes thumbnails through Google's official YouTube Data API v3 — the same interface YouTube itself provides to creators. We never store your password or personal credentials. You can revoke our access at any time from Google Account Permissions.",
      },
      {
        q: "Does this violate YouTube's policies?",
        a: "No. YouTube allows creators to update thumbnails at any time, and ThumbnailFlow simply automates that process via the official API. There is no scraping, no third-party login interception, and no policy violation.",
      },
      {
        q: "Will my video look strange to viewers while a test is running?",
        a: "No. Thumbnail swaps are near-instant and viewers see only one thumbnail at a time — whichever is currently active. There is no flickering, no visible transition, and the swap has no effect on view counts, likes, or any other video metrics.",
      },
    ],
  },
  {
    section: "How It Works",
    items: [
      {
        q: "How many tests can I run on the free plan?",
        a: "The free (BASIC) plan allows up to 4 tests per month with 1 running at a time. Each test supports up to 3 thumbnail variants (A/B/C), and thumbnails are swapped no more than once every 4 hours.",
      },
      {
        q: "Is the winning thumbnail automatically applied when the test ends?",
        a: "Yes. Once all variants have been shown enough times, the variant with the highest Views Per Hour (VPH) is automatically locked in as the permanent thumbnail and the test closes.",
      },
      {
        q: "Can I stop a test before it finishes?",
        a: "Yes. You can manually stop a test at any time from the dashboard, and you can also immediately lock any specific variant as the winner without waiting for the test to complete.",
      },
    ],
  },
  {
    section: "Billing & Account",
    items: [
      {
        q: "Can I start for free without a credit card?",
        a: "Yes. The free BASIC plan requires only a Google account — no credit card, no trial period, no expiry.",
      },
      {
        q: "Can I cancel my PRO subscription at any time?",
        a: "Yes. You can cancel from Settings → Manage Subscription at any time. After cancellation your PRO features remain active until the end of the current billing period — you are never charged twice. All payments are non-refundable; we do not issue refunds or credits for unused time.",
      },
      {
        q: "Is my payment information secure?",
        a: "Yes. All payments are processed by Paddle, a certified payment provider. ThumbnailFlow never receives or stores your card number, CVV, or any raw payment details — only a secure customer reference ID is kept on our servers.",
      },
    ],
  },
  {
    section: "Channels & Technical",
    items: [
      {
        q: "How do I connect my YouTube channel?",
        a: "Just sign in with your Google account — your YouTube channel is connected automatically. No separate configuration is required.",
      },
      {
        q: "Can I manage multiple YouTube channels?",
        a: "Yes. You can add additional channels from Settings and switch between them directly from the dashboard.",
      },
      {
        q: "Does ThumbnailFlow work with YouTube Brand Accounts?",
        a: "Yes. When you sign in, Google may show a channel-selection screen if your Google account manages a Brand Account. In some cases YouTube also requires phone verification to grant API access for Brand Accounts.",
      },
      {
        q: "I use a Brand Account — where will email alerts go?",
        a: "Brand Account addresses are often unmonitored. To receive test-completion and billing notifications, register a personal email address in Settings → Notification Email.",
      },
    ],
  },
];

export default function FAQPage() {
  return (
    <div className="min-h-screen bg-[#050505] text-zinc-300">
      <div className="max-w-3xl mx-auto px-6 py-16">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-zinc-400 hover:text-white transition-colors mb-10 text-sm rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
        >
          <ArrowLeft size={16} aria-hidden="true" /> Back to Home
        </Link>

        <h1 className="text-3xl font-black text-white mb-2">Frequently Asked Questions</h1>
        <p className="text-base text-zinc-500 mb-12">
          Can&apos;t find your answer?{" "}
          <a
            href="mailto:admin@trythumbnailflow.com"
            className="text-cyan-500 hover:underline rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
          >
            Email us
          </a>{" "}
          and we&apos;ll get back to you.
        </p>

        <div className="space-y-14">
          {faqs.map((section) => (
            <div key={section.section}>
              <h2 className="text-sm font-semibold uppercase tracking-widest text-cyan-500 mb-6">
                {section.section}
              </h2>
              <div className="space-y-8">
                {section.items.map((item) => (
                  <div key={item.q} className="border-b border-zinc-800 pb-8 last:border-0 last:pb-0">
                    <p className="text-base font-semibold text-white mb-2">{item.q}</p>
                    <p className="text-base text-zinc-400 leading-relaxed">{item.a}</p>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-16 pt-10 border-t border-zinc-800 text-sm text-zinc-500 space-y-1">
          <p>
            See also:{" "}
            <Link href="/terms" className="text-cyan-500 hover:underline rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
              Terms of Service
            </Link>{" "}
            &amp;{" "}
            <Link href="/privacy" className="text-cyan-500 hover:underline rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
              Privacy Policy
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
