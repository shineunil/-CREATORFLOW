const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, 'src/app/history/page.tsx');
let content = fs.readFileSync(filePath, 'utf8');

const replacements = {
    "최적화 기록": "Optimization History",
    "과거에 Completed Optimizations 캠페인 결과입니다.": "Past optimization campaign results.",
    "과거에 완료된 최적화 캠페인 결과입니다.": "Past optimization campaign results.",
    "Completed Optimizations 기록이 없습니다.": "No completed optimization records found.",
    "완료된 최적화 기록이 없습니다.": "No completed optimization records found.",
    "테스트 종료:": "Test Ended:"
};

for (const [ko, en] of Object.entries(replacements)) {
    content = content.replaceAll(ko, en);
}

fs.writeFileSync(filePath, content, 'utf8');
console.log("History translated.");
