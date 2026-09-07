import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export const metadata = {
  title: "Privacy Policy | CreatorFlow",
};

export default function PrivacyPolicyPage() {
  return (
    <div className="min-h-screen bg-[#050505] text-zinc-300">
      <div className="max-w-3xl mx-auto px-6 py-16">
        <Link href="/" className="inline-flex items-center gap-2 text-zinc-400 hover:text-white transition-colors mb-10 text-sm rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
          <ArrowLeft size={16} aria-hidden="true" /> Back to Home
        </Link>

        <h1 className="text-3xl font-black text-white mb-2">Privacy Policy</h1>
        <p className="text-sm text-zinc-400 mb-10">Last updated: 2026-09-07</p>

        <div className="space-y-8 text-sm leading-relaxed">
          <section>
            <h2 className="text-lg font-bold text-white mb-3">1. Information We Collect</h2>
            <p className="mb-2">CreatorFlow collects and processes the following information through Google Sign-In:</p>
            <ul className="list-disc list-inside space-y-1 text-zinc-400">
              <li>Your Google account email address and name (used for login and sending notifications)</li>
              <li>Connected YouTube channel information (channel ID, channel name)</li>
              <li>Titles, thumbnails, and view counts of connected YouTube videos (used to run A/B tests and measure performance)</li>
              <li>YouTube Analytics data per video — impressions and impressions click-through rate (CTR) — collected to more accurately measure the real-world performance of the thumbnails/titles the service automatically swaps</li>
              <li>Payment-related information (processed via Paddle; raw payment method details such as card numbers are never stored on CreatorFlow&apos;s servers)</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-bold text-white mb-3">2. Use of YouTube API Services</h2>
            <p className="mb-2">
              CreatorFlow uses YouTube API Services. By using CreatorFlow, you agree to be bound by the{" "}
              <a href="https://www.youtube.com/t/terms" target="_blank" rel="noreferrer" className="text-cyan-500 hover:underline rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
                YouTube Terms of Service
              </a>
              . For information on how Google collects and processes data, please see the{" "}
              <a href="https://policies.google.com/privacy" target="_blank" rel="noreferrer" className="text-cyan-500 hover:underline rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
                Google Privacy Policy
              </a>
              .
            </p>
            <p>
              CreatorFlow&apos;s access to, and use of, information received from Google APIs adheres to the{" "}
              <a href="https://developers.google.com/terms/api-services-user-data-policy" target="_blank" rel="noreferrer" className="text-cyan-500 hover:underline rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
                Google API Services User Data Policy
              </a>
              , including the Limited Use requirements. In practice this means:
            </p>
            <ul className="list-disc list-inside space-y-1 text-zinc-400 mt-2">
              <li>YouTube data is used only to provide and improve the thumbnail/title A/B testing features described in this policy — never to serve ads.</li>
              <li>We do not sell YouTube API data, and we do not transfer it to third parties except as needed to provide our service (e.g., our cloud image storage provider) or as required by law.</li>
              <li>No human reads your YouTube data except: with your explicit consent, for security purposes (e.g., investigating abuse), to comply with applicable law, or where the data has been aggregated and anonymized.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-bold text-white mb-3">3. How We Use Your Information</h2>
            <ul className="list-disc list-inside space-y-1 text-zinc-400">
              <li>Running automated thumbnail/title A/B test swaps</li>
              <li>Comparing candidate performance (view counts, VPH, YouTube Analytics CTR) and determining a winner</li>
              <li>Sending email notifications about test completion and plan/billing status</li>
              <li>Preventing abuse of the service and enforcing per-plan usage limits</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-bold text-white mb-3">4. Data Retention, Deletion, and Third-Party Sharing</h2>
            <p className="mb-2">
              We use the information we collect solely to provide the service, and we do not sell or share it with third parties except where required by law.
            </p>
            <p className="mb-2">
              If you disconnect a channel from the Settings page, the stored OAuth refresh token for that channel is deleted immediately, and CreatorFlow permanently loses the ability to access that YouTube account.
            </p>
            <p>
              To request deletion of your entire account and all associated data (including video, test, and analytics records), contact us at the email address below. We will complete the deletion within 30 days of a verified request.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-white mb-3">5. Contact</h2>
            <p className="text-zinc-400">
              For privacy-related inquiries, please contact us via the in-app Settings page or at support@creatorflow.io.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
