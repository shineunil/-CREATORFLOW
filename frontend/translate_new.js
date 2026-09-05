const fs = require('fs');
const path = require('path');

const replacements = {
    "프로필 가져오기 실패:": "Failed to fetch profile:",
    "영상 목록 가져오기 실패:": "Failed to fetch video list:",
    "업로드 실패": "Upload Failed",
    "이미지 업로드에 실패했습니다.": "Failed to upload image.",
    "오류 발생": "Error Occurred",
    "이미지 업로드 중 오류가 발생했습니다.": "An error occurred while uploading the image.",
    "후보 추가 제한": "Candidate Limit Reached",
    "BASIC 요금제는 최대 2개(B, C)까지만 추가 후보를 등록할 수 있습니다.\\n더 많은 썸네일을 동시에 테스트하려면 PRO 요금제로 업그레이드해주세요.": "BASIC plan allows up to 2 extra candidates (B, C).\\nTo test more thumbnails simultaneously, please upgrade to PRO.",
    "최대 한도 도달": "Maximum Limit Reached",
    "PRO 요금제에서도 동시에 최대 4개의 추가 후보(총 5개)까지만 테스트할 수 있습니다.": "Even on PRO plan, you can only test up to 4 extra candidates (5 total) simultaneously.",
    "영상 선택 필요": "Select a Video",
    "최적화할 원본 영상을 선택해주세요.": "Please select an original video to optimize.",
    "요금제 한도 초과": "Plan Limit Exceeded",
    "BASIC 요금제 한도에 도달했습니다.\\n무제한 최적화를 원하시면 PRO 요금제로 업그레이드해주세요.": "BASIC plan limit reached.\\nUpgrade to PRO for unlimited optimizations.",
    "실행 오류": "Execution Error",
    "최적화 실행 중 오류가 발생했습니다.": "An error occurred while executing the optimization.",
    "서버 통신 중 오류가 발생했습니다.": "A server communication error occurred.",
    "대시보드로 돌아가기": "Back to Dashboard",
    "새 썸네일 최적화 시작": "Start New Thumbnail Optimization",
    "여러 개의 썸네일과 제목을 업로드하면 CREATORFLOW가 가장 실적이 좋은 조합을 찾아줍니다.": "Upload multiple thumbnails and titles, and CREATORFLOW will find the best performing combination.",
    "1. 최적화할 원본 영상 선택": "1. Select Original Video",
    "연동된 유튜브 채널에서 최근 영상을 불러오는 중이거나 없습니다.": "Loading recent videos from your connected YouTube channel...",
    "조회수": "Views:",
    "원본 영상 (후보 A)": "Original Video (Candidate A)",
    "원본 영상 변경": "Change original video",
    "2. 실험할 후보 추가": "2. Add Candidates",
    "후보 추가 (최대 5개)": "Add Candidate (Max 5)",
    "후보 ": "Candidate ",
    " 삭제": " Delete",
    " 삭제": "Delete",
    "테스트용 썸네일 이미지": "Test Thumbnail Image",
    "다시 업로드": "Re-upload",
    "업로드 중 분석 중..": "Uploading & Analyzing..",
    "클릭하여 이미지 업로드": "Click to upload image",
    "권장: 1280x720 (Max 2MB)": "Recommended: 1280x720 (Max 2MB)",
    "테스트용 제목": "Test Title",
    "원본 제목과 동일하거나 다르게 입력": "Same as original or try a new one",
    "AI 썸네일 분석 완료 (점수:": "AI Thumbnail Analysis Complete (Score:",
    "3. 최적화 설정": "3. Optimization Settings",
    "교체 주기": "Swap Interval",
    "요금제 제한": "Plan Restriction",
    "30분 교체 주기는 PRO 요금제 전용 기능입니다.\\n빠른 최적화를 원하시면 PRO로 업그레이드해주세요.": "The 30-minute swap interval is a PRO-only feature.\\nUpgrade to PRO for faster optimizations.",
    "매 1시간마다 교체 (권장)": "Swap every 1 hour (Recommended)",
    "매 2시간마다 교체": "Swap every 2 hours",
    "매 30분마다 교체 (PRO 전용)": "Swap every 30 mins (PRO Only)",
    "후보 썸네일을 유튜브에 교대로 적용하며 CTR을 측정합니다.": "We alternately apply candidate thumbnails on YouTube to measure CTR.",
    "총 최적화 시간": "Total Optimization Duration",
    "24시간 후 최고 효율 썸네일 영구 적용": "Apply best thumbnail permanently after 24 hours",
    "48시간 후 최고 효율 썸네일 영구 적용": "Apply best thumbnail permanently after 48 hours",
    "72시간 후 최고 효율 썸네일 영구 적용": "Apply best thumbnail permanently after 72 hours",
    "테스트가 끝나면 1위한 썸네일로 고정됩니다.": "After the test, the winning thumbnail will be locked in.",
    "실시간 최적화 캠페인 시작하기": "Start Real-time Optimization Campaign",
    "최적화 캠페인이 시작되었습니다!": "Optimization Campaign Started!",
    "CREATORFLOW 시스템이 유튜브와 연동하여 자동으로 썸네일을 교체하고 실시간 데이터를 분석합니다.": "CREATORFLOW system is connected to YouTube, automatically swapping thumbnails and analyzing real-time data.",
    "대시보드에서 현황 보기": "View Status on Dashboard",
    "로딩 중..": "Loading.."
};

const filePath = path.join(__dirname, 'src/app/new/page.tsx');
let content = fs.readFileSync(filePath, 'utf8');

for (const [ko, en] of Object.entries(replacements)) {
    content = content.replaceAll(ko, en);
}

fs.writeFileSync(filePath, content, 'utf8');
console.log("New page translated.");
