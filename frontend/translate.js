const fs = require('fs');
const path = require('path');

const replacements = {
    "최적화 시작 전": "Not started",
    "종료된 최적화": "Finished",
    "시작:": "Started:",
    "최적화 진행 중 - ": "Running - ",
    "시간 후 종료 후 영구 적용": "h left until auto-apply",
    "최적화 취소 및 삭제": "Cancel & Delete Test",
    "진행 중인 테스트를 안전하게 취소하고 삭제하시겠습니까?\\n유튜브 영상의 썸네일을 안전하게 '기본(A)'으로 자동 복구하며 삭제된 테스트는 복구할 수 없습니다.": "Are you sure you want to safely cancel and delete this test?\\nThe thumbnail will be restored to 'Original (A)'. Deleted tests cannot be recovered.",
    "네, 안전하게 삭제합니다": "Yes, safely delete",
    "취소": "Cancel",
    "삭제 진행 중..": "Deleting...",
    "유튜브 썸네일을 안전하게 기본으로 복구하고 테스트를 삭제 중입니다.\\n잠시만 기다려주세요...": "Restoring thumbnail and deleting test.\\nPlease wait...",
    "삭제 완료": "Deleted",
    "테스트를 안전하게 취소하고 기본 썸네일로 복구했습니다.": "Test safely canceled and thumbnail restored.",
    "오류": "Error",
    "테스트 삭제 중 문제가 발생했습니다.": "An error occurred while deleting.",
    "네트워크 오류가 발생했습니다.": "A network error occurred.",
    "최적화 조기 종료": "End Test Early",
    "현재까지 가장 좋은 성과를 보인 썸네일로 영구 적용하고 최적화를 종료하시겠습니까?": "Apply the best performing thumbnail permanently and end the test?",
    "지금 즉시 적용": "Apply Now",
    "최적화 종료 중..": "Ending Test...",
    "유튜브 썸네일을 최종 승자로 지정하고 있습니다.\\n잠시만 기다려주세요...": "Setting the winning thumbnail.\\nPlease wait...",
    "성공": "Success",
    "테스트가 성공적으로 종료되었으며, 최고 효율의 썸네일이 유튜브에 반영되었습니다.": "Test ended successfully. The winning thumbnail has been applied.",
    "테스트 종료 중 문제가 발생했습니다.": "An error occurred while ending the test.",
    "자동 교체 성공": "Swap Successful",
    "유튜브 썸네일을 다음 후보로 즉시 교체했습니다.": "Thumbnail swapped successfully.",
    "교체 실패": "Swap Failed",
    "자동 교체에 실패했습니다.": "Failed to swap thumbnail.",
    "통신 중 문제가 발생했습니다.": "A communication error occurred.",
    "최적화 현황 대시보드": "Optimization Dashboard",
    "현재": "Currently",
    "개의 영상이 최적화 중입니다.": " videos are being optimized.",
    "로그아웃": "Log out",
    "데이터를 불러오는 중입니다...": "Loading data...",
    "진행 중인 최적화가 없습니다": "No active optimizations",
    "새로운 영상의 썸네일 A/B 테스트를 만들고 조회수를 극대화해보세요.": "Create a new A/B test and maximize your views.",
    "새 최적화 시작": "Create New Test",
    "실행 중": "Running",
    "최적화 완료": "Optimization Finished",
    "추가 조회수 획득": "Extra Views Gained",
    "회": " views",
    "총 후보 썸네일": "Total Candidates",
    "개": "",
    "교체 중..": "Swapping..",
    "썸네일 후보 강제 즉시 교체": "Force Swap Thumbnail",
    "최고 효율 썸네일로 영구 고정 (조기 종료)": "Lock Winning Thumbnail",
    "테스트 즉시 취소하고 원래 썸네일을 기본으로 복구합니다": "Cancel test and restore original thumbnail",
    "테스트 안전 취소 및 삭제": "Cancel & Delete Test",
    "이 썸네일 즉시 교체란?": "What is Force Swap?",
    "정해진 교체 시간을 무시하고 다음 썸네일 후보로 즉시 강제 교체해보는 기능입니다.": "It forcefully swaps to the next candidate, ignoring the scheduled interval.",
    "단, 교체 버튼을 누르더라도 유튜브 자체 서버의 반영 시간(캐시)으로 인해 실제 유튜브 화면에 표시되기까지 1~2분 정도 지연될 수 있습니다.": "Note: Due to YouTube cache, it may take 1-2 minutes to reflect on YouTube after clicking the button.",
    "1일차": "Day 1",
    "1위로 승리": "Winner",
    "썸네일": "Thumbnail",
    "썸네일 이미지": "Thumbnail Image",
    "누적 상승 조회수": "Cumulative Extra Views",
    "기록 시작일": "Started At",
    "총 획득 조회수": "Total Views Gained"
};

const filePath = path.join(__dirname, 'src/app/dashboard/page.tsx');
let content = fs.readFileSync(filePath, 'utf8');

for (const [ko, en] of Object.entries(replacements)) {
    content = content.replaceAll(ko, en);
}

fs.writeFileSync(filePath, content, 'utf8');
console.log("Dashboard translated.");
