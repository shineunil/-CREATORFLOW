const fs = require('fs');
const path = require('path');

const replacements = {
    "🎉 PRO 요금제 업그레이드 완료!": "🎉 PRO Plan Upgraded!",
    "개발 및 테스트용 PRO 구독이 즉시 승인되었습니다.\\n이제 제한 없이 무제한 썸네일 최적화를 진행하실 수 있습니다!": "PRO subscription approved.\\nYou can now run unlimited optimizations!",
    "업그레이드 실패": "Upgrade Failed",
    "요금제 변경 중 오류가 발생했습니다.": "An error occurred while changing plans.",
    "통신 오류가 발생했습니다.": "A communication error occurred.",
    "알림": "Notice",
    "Paddle 결제 연동은 준비중입니다.": "Paddle payment integration is coming soon.",
    "요금제 안내": "Pricing Plans",
    "채널 성장에 맞춰 최적의 플랜을 선택하세요.": "Choose the best plan for your channel growth.",
    "BASIC (무료)": "BASIC (Free)",
    "서비스를 체험해보고 싶은 크리에이터용": "For creators who want to try the service",
    "월 최대 4회 테스트 생성 제한": "Max 4 tests per month",
    "동시 진행 가능한 테스트 1개 제한": "Max 1 concurrent test",
    "추가 후보 썸네일 최대 2개 (A, B, C)": "Max 2 extra thumbnails (A, B, C)",
    "최소 교체 주기 60분": "Minimum swap interval: 60 mins",
    "무료 플랜": "Free Plan",
    "현재 사용 중인 요금제": "Current Plan",
    "PRO 프리미엄": "PRO Premium",
    "조회수를 극대화하고 채널을 빠르게 성장시킬 진성 유튜버용": "For serious creators who want to maximize views",
    "무제한": "Unlimited",
    "월간 테스트 생성": "tests per month",
    "동시 다발적 테스트 진행": "concurrent tests",
    "추가 후보 썸네일 최대 4개 (A~E)": "Max 4 extra thumbnails (A~E)",
    "초고속 30분": "Ultra-fast 30 mins",
    "교체 주기 지원": "swap interval",
    "머신러닝 기반 썸네일 점수 예측 (출시 예정)": "ML thumbnail score prediction (Coming soon)",
    "현재 PRO 요금제 사용 중 (무제한 활성화됨)": "Currently on PRO (Unlimited features active)",
    "PRO 요금제로 업그레이드": "Upgrade to PRO",
    "PRO 프리미엄 결제": "PRO Premium Checkout",
    "구독 플랜": "Subscription Plan",
    "PRO 프리미엄 (월간)": "PRO Premium (Monthly)",
    "결제 금액": "Total Amount",
    "Paddle 결제 진행하기": "Proceed with Paddle Checkout",
    "⚡ 개발 테스트용 즉시 PRO 승인": "⚡ Instant PRO Approval (Dev Test)",
    "Paddle은 Merchant of Record(MoR)로서 안전한 글로벌 결제 및 세금 정산을 담당합니다.": "Paddle acts as the Merchant of Record (MoR) for secure global payments.",
    
    // Login
    "연동 및 시작하기": "Connect & Get Started",
    "테스트 기록이 없거나 데이터를 불러올 수 없습니다.": "No test history or unable to load data.",
    "채널 전체": "Entire Channel",
    "누적 획득 조회수": "Cumulative Extra Views",
    "완료된 최적화": "Completed Optimizations",
    "평균 효율 상승": "Average CTR Lift",
    "최근 7일": "Last 7 Days",
    "종합 리포트": "Comprehensive Report",
    "상세 리포트 준비 중": "Detailed report coming soon",
    "종료된 과거 최적화 기록을 확인할 수 있습니다.": "You can view past completed optimizations here."
};

const dir = path.join(__dirname, 'src/app');
const files = [
    'pricing/page.tsx',
    'analytics/page.tsx',
    'history/page.tsx',
    'login/page.tsx'
];

for (const file of files) {
    const filePath = path.join(dir, file);
    if (fs.existsSync(filePath)) {
        let content = fs.readFileSync(filePath, 'utf8');
        for (const [ko, en] of Object.entries(replacements)) {
            content = content.replaceAll(ko, en);
        }
        fs.writeFileSync(filePath, content, 'utf8');
        console.log("Translated: " + file);
    }
}
