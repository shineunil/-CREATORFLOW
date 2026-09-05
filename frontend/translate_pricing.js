const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, 'src/app/pricing/page.tsx');
let content = fs.readFileSync(filePath, 'utf8');

const replacements = {
    "🎉 PRO Plan Upgraded!": "🎉 PRO Plan Upgraded!",
    "오류 발생": "Error Occurred",
    "Paddle 결제 연동은 준비중입니다.": "Paddle integration is coming soon.",
    "현재 PRO 요금제 이용 중 (Unlimited 활성화됨)": "Currently on PRO (Unlimited Active)",
    "PRO Premium 결제": "PRO Premium Checkout",
    "PRO Premium (월간)": "PRO Premium (Monthly)",
    "⚡ 개발 테스트용 즉시 PRO 승인": "⚡ Instant PRO Approval (Dev Test)",
    "/ 월": "/ month",
    "닫기": "X"
};

for (const [ko, en] of Object.entries(replacements)) {
    content = content.replaceAll(ko, en);
}

fs.writeFileSync(filePath, content, 'utf8');
console.log("Pricing translated.");
