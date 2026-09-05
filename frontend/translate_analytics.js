const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, 'src/app/analytics/page.tsx');
let content = fs.readFileSync(filePath, 'utf8');

const replacements = {
    "채널 종합 분석": "Channel Analytics Overview",
    "CREATORFLOW가 최적화한 데이터 통계입니다.": "Statistics of data optimized by CREATORFLOW.",
    "총 진행한 최적화": "Total Optimizations",
    "진행 중인 최적화": "Active Optimizations",
    "최적화로 확보한 추가 조회수": "Extra Views Gained from Optimization",
    "최적화 추가 조회수 누적 추이": "Cumulative Extra Views Trend",
    "테스트가 누적되면 차트가 표시됩니다.": "Chart will appear when enough test data is accumulated."
};

for (const [ko, en] of Object.entries(replacements)) {
    content = content.replaceAll(ko, en);
}

fs.writeFileSync(filePath, content, 'utf8');
console.log("Analytics translated.");
