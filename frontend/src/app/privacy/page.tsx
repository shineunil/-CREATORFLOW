import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import { getI18n } from "@/i18n/server";
import { localizePath } from "@/i18n/config";
import { publicPageMetadata } from "@/i18n/metadata";

export function generateMetadata() {
  return publicPageMetadata("/privacy", (m) => ({ title: m.privacyTitle, description: m.privacyDescription }));
}

const linkClass = "text-cyan-500 hover:underline rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400";

export default async function PrivacyPolicyPage() {
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

        {locale === "ko" ? <PrivacyKo /> : <PrivacyEn />}
      </div>
    </div>
  );
}

function PrivacyEn() {
  return (
    <>
      <h1 className="text-3xl font-black text-white mb-2">Privacy Policy</h1>
      <p className="text-sm text-zinc-400 mb-10">Last updated: 2026-09-14</p>

      <div className="space-y-8 text-sm leading-relaxed">
        <section>
          <h2 className="text-lg font-bold text-white mb-3">1. Information We Collect</h2>
          <p className="mb-2">ThumbnailFlow collects and processes the following information through Google Sign-In:</p>
          <ul className="list-disc list-inside space-y-1 text-zinc-400">
            <li>Your Google account email address and name (used for login and sending notifications)</li>
            <li>Connected YouTube channel information (channel ID, channel name)</li>
            <li>Titles, thumbnails, and view counts of connected YouTube videos (used to run A/B tests and measure performance)</li>
            <li>View counts and performance data of connected YouTube videos (used to measure A/B test results)</li>
            <li>Payment-related information (processed via Paddle; raw payment method details such as card numbers are never stored on ThumbnailFlow&apos;s servers)</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">2. Google OAuth Permissions We Request</h2>
          <p className="mb-2">
            To provide the Service, ThumbnailFlow requests the following OAuth permissions (scopes) from your Google account:
          </p>
          <ul className="list-disc list-inside space-y-1 text-zinc-400">
            <li><strong className="text-zinc-300">https://www.googleapis.com/auth/youtube.force-ssl</strong> — Read and update YouTube video metadata (thumbnails and titles) to run A/B test swaps on your behalf.</li>
            <li><strong className="text-zinc-300">https://www.googleapis.com/auth/userinfo.email</strong> — Identify your account and send service notifications.</li>
            <li><strong className="text-zinc-300">https://www.googleapis.com/auth/userinfo.profile</strong> — Display your name within the app.</li>
          </ul>
          <p className="mt-2 text-zinc-400">
            We request only the permissions necessary to deliver the Service. You can revoke these permissions at any time via{" "}
            <a href="https://myaccount.google.com/permissions" target="_blank" rel="noreferrer" className={linkClass}>
              Google Account Permissions
            </a>
            .
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">3. Use of YouTube API Services</h2>
          <p className="mb-2">
            ThumbnailFlow uses YouTube API Services. By using ThumbnailFlow, you agree to be bound by the{" "}
            <a href="https://www.youtube.com/t/terms" target="_blank" rel="noreferrer" className={linkClass}>
              YouTube Terms of Service
            </a>
            . For information on how Google collects and processes data, please see the{" "}
            <a href="https://policies.google.com/privacy" target="_blank" rel="noreferrer" className={linkClass}>
              Google Privacy Policy
            </a>
            .
          </p>
          <p className="mb-2">
            ThumbnailFlow&apos;s access to, and use of, information received from Google APIs adheres to the{" "}
            <a href="https://developers.google.com/terms/api-services-user-data-policy" target="_blank" rel="noreferrer" className={linkClass}>
              Google API Services User Data Policy
            </a>
            , including the Limited Use requirements. In practice this means:
          </p>
          <ul className="list-disc list-inside space-y-1 text-zinc-400 mt-2">
            <li>YouTube data is used only to provide and improve the thumbnail/title A/B testing features described in this policy — never to serve ads.</li>
            <li>We do not sell YouTube API data, and we do not transfer it to third parties except as needed to provide our service (e.g., our cloud image storage provider) or as required by law.</li>
            <li>No human reads your YouTube data except: with your explicit consent, for security purposes (e.g., investigating abuse), to comply with applicable law, or where the data has been aggregated and anonymized.</li>
            <li><strong className="text-zinc-300">Data obtained from Google APIs is never used to train AI or machine learning models.</strong></li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">4. How We Use Your Information</h2>
          <ul className="list-disc list-inside space-y-1 text-zinc-400">
            <li>Running automated thumbnail/title A/B test swaps</li>
            <li>Comparing candidate performance (view counts, VPH) and determining a winner</li>
            <li>Sending email notifications about test completion and plan/billing status</li>
            <li>Preventing abuse of the service and enforcing per-plan usage limits</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">5. Data Security</h2>
          <p className="text-zinc-400">
            We take reasonable technical and organizational measures to protect your information against unauthorized access, disclosure, or destruction. OAuth refresh tokens are stored encrypted and are used exclusively to operate the Service on your behalf. We do not store raw payment method details (e.g., card numbers) on our servers — all payment data is handled directly by Paddle, our payment provider.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">6. Data Retention, Deletion, and Third-Party Sharing</h2>
          <p className="mb-2">
            We use the information we collect solely to provide the service, and we do not sell or share it with third parties except where required by law.
          </p>
          <p className="mb-2">
            If you disconnect a channel from the Settings page, the stored OAuth refresh token for that channel is deleted immediately, and ThumbnailFlow permanently loses the ability to access that YouTube account.
          </p>
          <p>
            To request deletion of your entire account and all associated data (including video, test, and analytics records), contact us at the email address below. We will complete the deletion within 30 days of a verified request.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">7. Contact</h2>
          <p className="text-zinc-400">
            For privacy-related inquiries, please contact us via the in-app Settings page or at admin@trythumbnailflow.com.
          </p>
        </section>
      </div>
    </>
  );
}

function PrivacyKo() {
  return (
    <>
      <h1 className="text-3xl font-black text-white mb-2">개인정보처리방침</h1>
      <p className="text-sm text-zinc-400 mb-6">최종 수정일: 2026-09-14</p>
      <p className="text-sm text-zinc-400 mb-10 rounded-xl border border-zinc-800 bg-zinc-900/40 px-4 py-3 break-keep">
        이 문서는 영어 원문을 번역한 것입니다. 번역본과 영어 원문의 내용이 다를 경우 영어 원문이 우선합니다. 영어 원문은 화면 위쪽의 EN을 눌러 볼 수 있습니다.
      </p>

      <div className="space-y-8 text-sm leading-relaxed break-keep">
        <section>
          <h2 className="text-lg font-bold text-white mb-3">1. 수집하는 정보</h2>
          <p className="mb-2">ThumbnailFlow는 구글 로그인을 통해 다음 정보를 수집하고 처리합니다.</p>
          <ul className="list-disc list-inside space-y-1 text-zinc-400">
            <li>구글 계정 이메일 주소와 이름 (로그인 및 알림 발송에 사용)</li>
            <li>연동된 유튜브 채널 정보 (채널 ID, 채널 이름)</li>
            <li>연동된 유튜브 영상의 제목, 썸네일, 조회수 (A/B 테스트 실행과 성과 측정에 사용)</li>
            <li>연동된 유튜브 영상의 조회수와 성과 데이터 (A/B 테스트 결과 측정에 사용)</li>
            <li>결제 관련 정보 (Paddle을 통해 처리되며, 카드 번호 등 결제 수단의 원본 정보는 ThumbnailFlow 서버에 저장되지 않습니다)</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">2. 요청하는 구글 OAuth 권한</h2>
          <p className="mb-2">서비스를 제공하기 위해 ThumbnailFlow는 구글 계정에 다음 OAuth 권한(스코프)을 요청합니다.</p>
          <ul className="list-disc list-inside space-y-1 text-zinc-400">
            <li><strong className="text-zinc-300">https://www.googleapis.com/auth/youtube.force-ssl</strong> — 사용자를 대신해 A/B 테스트 교체를 실행하기 위해 유튜브 영상 메타데이터(썸네일과 제목)를 읽고 수정합니다.</li>
            <li><strong className="text-zinc-300">https://www.googleapis.com/auth/userinfo.email</strong> — 계정을 식별하고 서비스 알림을 보냅니다.</li>
            <li><strong className="text-zinc-300">https://www.googleapis.com/auth/userinfo.profile</strong> — 앱 안에서 이름을 표시합니다.</li>
          </ul>
          <p className="mt-2 text-zinc-400">
            서비스 제공에 꼭 필요한 권한만 요청합니다. 이 권한은 언제든{" "}
            <a href="https://myaccount.google.com/permissions" target="_blank" rel="noreferrer" className={linkClass}>
              구글 계정 권한
            </a>
            에서 해제할 수 있습니다.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">3. YouTube API 서비스 이용</h2>
          <p className="mb-2">
            ThumbnailFlow는 YouTube API 서비스를 사용합니다. ThumbnailFlow를 이용하면{" "}
            <a href="https://www.youtube.com/t/terms" target="_blank" rel="noreferrer" className={linkClass}>
              YouTube 서비스 약관
            </a>
            에 동의하게 됩니다. 구글이 데이터를 수집하고 처리하는 방식은{" "}
            <a href="https://policies.google.com/privacy" target="_blank" rel="noreferrer" className={linkClass}>
              Google 개인정보처리방침
            </a>
            을 참고해 주세요.
          </p>
          <p className="mb-2">
            ThumbnailFlow가 Google API로부터 받은 정보에 접근하고 이를 사용하는 방식은 제한적 사용(Limited Use) 요건을 포함한{" "}
            <a href="https://developers.google.com/terms/api-services-user-data-policy" target="_blank" rel="noreferrer" className={linkClass}>
              Google API 서비스 사용자 데이터 정책
            </a>
            을 준수합니다. 구체적으로는 다음과 같습니다.
          </p>
          <ul className="list-disc list-inside space-y-1 text-zinc-400 mt-2">
            <li>유튜브 데이터는 이 방침에 설명된 썸네일·제목 A/B 테스트 기능을 제공하고 개선하는 데에만 사용하며, 광고 게재에는 절대 사용하지 않습니다.</li>
            <li>유튜브 API 데이터를 판매하지 않으며, 서비스 제공에 필요한 경우(예: 클라우드 이미지 저장소 제공업체)나 법에 따라 요구되는 경우를 제외하고 제3자에게 전달하지 않습니다.</li>
            <li>사용자의 명시적 동의가 있는 경우, 보안상 필요한 경우(예: 악용 조사), 관련 법을 준수해야 하는 경우, 또는 데이터가 집계·익명화된 경우를 제외하고 사람이 유튜브 데이터를 열람하지 않습니다.</li>
            <li><strong className="text-zinc-300">Google API로부터 받은 데이터는 AI나 머신러닝 모델 학습에 절대 사용하지 않습니다.</strong></li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">4. 정보 이용 목적</h2>
          <ul className="list-disc list-inside space-y-1 text-zinc-400">
            <li>썸네일·제목 A/B 테스트 자동 교체 실행</li>
            <li>후보별 성과(조회수, VPH) 비교 및 승자 결정</li>
            <li>테스트 완료, 요금제·결제 상태에 관한 이메일 알림 발송</li>
            <li>서비스 악용 방지 및 요금제별 이용 한도 적용</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">5. 데이터 보안</h2>
          <p className="text-zinc-400">
            무단 접근, 공개, 파기로부터 정보를 보호하기 위해 합리적인 기술적·관리적 조치를 취합니다. OAuth 갱신 토큰은 암호화되어 저장되며, 사용자를 대신해 서비스를 운영하는 데에만 사용됩니다. 카드 번호 등 결제 수단의 원본 정보는 서버에 저장하지 않으며, 모든 결제 데이터는 결제 대행사인 Paddle이 직접 처리합니다.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">6. 데이터 보관, 삭제 및 제3자 제공</h2>
          <p className="mb-2">
            수집한 정보는 서비스 제공에만 사용하며, 법에 따라 요구되는 경우를 제외하고 제3자에게 판매하거나 제공하지 않습니다.
          </p>
          <p className="mb-2">
            설정 페이지에서 채널 연동을 해제하면 해당 채널에 저장된 OAuth 갱신 토큰이 즉시 삭제되며, ThumbnailFlow는 더 이상 그 유튜브 계정에 접근할 수 없습니다.
          </p>
          <p>
            계정 전체와 관련 데이터(영상, 테스트, 분석 기록 포함)의 삭제를 원하시면 아래 이메일 주소로 연락해 주세요. 본인 확인이 끝난 요청은 30일 이내에 삭제를 완료합니다.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">7. 문의</h2>
          <p className="text-zinc-400">
            개인정보 관련 문의는 앱의 설정 페이지나 admin@trythumbnailflow.com으로 연락해 주세요.
          </p>
        </section>
      </div>
    </>
  );
}
