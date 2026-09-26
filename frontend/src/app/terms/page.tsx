import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import { getI18n } from "@/i18n/server";
import { localizePath } from "@/i18n/config";
import { publicPageMetadata } from "@/i18n/metadata";

export function generateMetadata() {
  return publicPageMetadata("/terms", (m) => ({ title: m.termsTitle, description: m.termsDescription }));
}

const linkClass = "text-cyan-400 underline underline-offset-2 hover:text-cyan-300 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400";

export default async function TermsPage() {
  const { locale, t } = await getI18n();

  return (
    <div className="min-h-screen bg-[#050505] text-zinc-300">
      <div className="max-w-3xl mx-auto px-6 py-16">
        <div className="flex items-center justify-between gap-4 mb-10">
          <Link href={localizePath("/", locale)} className="inline-flex items-center gap-2 text-zinc-400 hover:text-white transition-colors text-sm rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
            <ArrowLeft size={16} aria-hidden="true" /> {t.common.backToHome}
          </Link>
          <LanguageSwitcher />
        </div>

        {locale === "ko" ? <TermsKo /> : <TermsEn />}
      </div>
    </div>
  );
}

function TermsEn() {
  return (
    <>
      <h1 className="text-3xl font-black text-white mb-2">Terms of Service</h1>
      <p className="text-sm text-zinc-400 mb-10">Last updated: 2026-09-14</p>

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
          <h2 className="text-lg font-bold text-white mb-3">3. Use of YouTube and Google API Services</h2>
          <p className="mb-2 text-zinc-400">
            The Service accesses YouTube and Google API Services on your behalf to read and update video metadata (thumbnails and titles) and retrieve YouTube Analytics data. By using the Service, you agree to be bound by the{" "}
            <a href="https://www.youtube.com/t/terms" target="_blank" rel="noreferrer" className={linkClass}>
              YouTube Terms of Service
            </a>
            {" "}and acknowledge the{" "}
            <a href="https://policies.google.com/privacy" target="_blank" rel="noreferrer" className={linkClass}>
              Google Privacy Policy
            </a>
            . You are responsible for ensuring that any thumbnails or titles automatically applied by the Service comply with YouTube&apos;s policies and Community Guidelines. You can revoke the Service&apos;s access to your Google account at any time via{" "}
            <a href="https://myaccount.google.com/permissions" target="_blank" rel="noreferrer" className={linkClass}>
              Google Account Permissions
            </a>
            .
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">4. Plans</h2>
          <p className="text-zinc-400">
            We offer a BASIC (free) plan and a PRO plan. Limits on concurrent tests, swap interval, and candidate count for each plan are described in the app. Payments are processed via Paddle, and you can change or cancel your plan from the Settings page.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">5. Refunds</h2>
          <p className="text-zinc-400">
            All payments are non-refundable. You may cancel your subscription at any time from the Settings page; cancellation takes effect at the end of the current billing period and you retain access to PRO features until that date. We do not provide refunds or credits for partial billing periods, unused time, or unused features, except where required by applicable law. For billing questions, contact us at the email address below.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">6. Limitation of Liability</h2>
          <p className="text-zinc-400">
            The Service estimates performance based on data provided by the YouTube Data API and YouTube Analytics API. Due to the nature of these APIs (reporting delay, sample size, etc.), measured view counts and click-through rates may differ from YouTube&apos;s own statistics, and the Service does not guarantee any specific performance improvement.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">7. Changes to and Discontinuation of the Service</h2>
          <p className="text-zinc-400">
            We may modify features of the Service for operational or legal reasons, or discontinue it after providing prior notice.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">8. Contact</h2>
          <p className="text-zinc-400">
            For questions about using the Service, please contact us at admin@trythumbnailflow.com.
          </p>
        </section>
      </div>
    </>
  );
}

function TermsKo() {
  return (
    <>
      <h1 className="text-3xl font-black text-white mb-2">이용약관</h1>
      <p className="text-sm text-zinc-400 mb-6">최종 수정일: 2026-09-14</p>
      <p className="text-sm text-zinc-400 mb-10 rounded-xl border border-zinc-800 bg-zinc-900/40 px-4 py-3 break-keep">
        이 문서는 영어 원문을 번역한 것입니다. 번역본과 영어 원문의 내용이 다를 경우 영어 원문이 우선합니다. 영어 원문은 화면 위쪽의 EN을 눌러 볼 수 있습니다.
      </p>

      <div className="space-y-8 text-sm leading-relaxed break-keep">
        <section>
          <h2 className="text-lg font-bold text-white mb-3">1. 서비스 개요</h2>
          <p className="text-zinc-400">
            ThumbnailFlow(이하 &quot;서비스&quot;)는 사용자가 연동한 유튜브 영상에 썸네일과 제목 후보를 자동으로 번갈아 적용하고, 그 성과(조회수, 시간당 조회수(VPH), 실제 YouTube Analytics 클릭률)를 측정해 가장 성과가 좋은 조합을 찾아 주는 A/B 테스트 도구입니다.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">2. 계정 및 채널 연동</h2>
          <ul className="list-disc list-inside space-y-1 text-zinc-400">
            <li>구글 계정으로 로그인합니다. 서비스를 이용하려면 유튜브 채널 연동을 위한 OAuth 동의가 필요합니다.</li>
            <li>설정 페이지에서 언제든 채널 연동을 해제할 수 있으며, 해제하면 해당 채널에서 진행 중인 자동 교체가 즉시 중단됩니다.</li>
            <li>유튜브가 연동 토큰을 철회하거나 토큰이 만료되면, 서비스는 해당 채널의 자동 교체를 멈추고 다시 연동하도록 안내합니다.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">3. YouTube 및 Google API 서비스 이용</h2>
          <p className="mb-2 text-zinc-400">
            서비스는 영상 메타데이터(썸네일과 제목)를 읽고 수정하며 YouTube Analytics 데이터를 가져오기 위해 사용자를 대신해 YouTube 및 Google API 서비스에 접근합니다. 서비스를 이용하면{" "}
            <a href="https://www.youtube.com/t/terms" target="_blank" rel="noreferrer" className={linkClass}>
              YouTube 서비스 약관
            </a>
            에 동의하고{" "}
            <a href="https://policies.google.com/privacy" target="_blank" rel="noreferrer" className={linkClass}>
              Google 개인정보처리방침
            </a>
            을 확인한 것으로 봅니다. 서비스가 자동으로 적용하는 썸네일이나 제목이 유튜브 정책과 커뮤니티 가이드를 준수하는지는 사용자가 책임집니다. 서비스의 구글 계정 접근 권한은 언제든{" "}
            <a href="https://myaccount.google.com/permissions" target="_blank" rel="noreferrer" className={linkClass}>
              구글 계정 권한
            </a>
            에서 해제할 수 있습니다.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">4. 요금제</h2>
          <p className="text-zinc-400">
            BASIC(무료)과 PRO 요금제를 제공합니다. 요금제별 동시 테스트 수, 교체 주기, 후보 수 제한은 앱 안에 안내되어 있습니다. 결제는 Paddle을 통해 처리되며, 설정 페이지에서 요금제를 변경하거나 해지할 수 있습니다.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">5. 환불</h2>
          <p className="text-zinc-400">
            모든 결제는 환불되지 않습니다. 구독은 설정 페이지에서 언제든 해지할 수 있으며, 해지는 현재 결제 기간이 끝나는 시점에 적용되고 그때까지 PRO 기능을 계속 이용할 수 있습니다. 관련 법에서 요구하는 경우를 제외하고, 결제 기간 중 일부 기간, 사용하지 않은 기간이나 기능에 대한 환불이나 크레딧은 제공하지 않습니다. 결제 관련 문의는 아래 이메일 주소로 연락해 주세요.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">6. 책임의 제한</h2>
          <p className="text-zinc-400">
            서비스는 YouTube Data API와 YouTube Analytics API가 제공하는 데이터를 바탕으로 성과를 추정합니다. 이러한 API의 특성(보고 지연, 표본 크기 등)으로 인해 측정된 조회수와 클릭률은 유튜브 자체 통계와 다를 수 있으며, 서비스는 특정한 성과 향상을 보장하지 않습니다.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">7. 서비스의 변경 및 중단</h2>
          <p className="text-zinc-400">
            운영상 또는 법적인 이유로 서비스의 기능을 변경할 수 있으며, 사전 공지 후 서비스를 중단할 수 있습니다.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">8. 문의</h2>
          <p className="text-zinc-400">
            서비스 이용에 관한 문의는 admin@trythumbnailflow.com으로 연락해 주세요.
          </p>
        </section>
      </div>
    </>
  );
}
