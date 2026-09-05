const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, 'src/components/layout/Sidebar.tsx');
let content = fs.readFileSync(filePath, 'utf8');

const replacements = {
    'name: "대시보드", icon: LayoutDashboard, href: "/"': 'name: "Dashboard", icon: LayoutDashboard, href: "/dashboard"',
    'name: "대시보드", icon: LayoutDashboard, href: "/dashboard"': 'name: "Dashboard", icon: LayoutDashboard, href: "/dashboard"', // in case
    'name: "새 테스트"': 'name: "New Test"',
    'name: "내 비디오"': 'name: "Videos"',
    'name: "내 영상"': 'name: "Videos"',
    'name: "분석"': 'name: "Analytics"',
    'name: "기록"': 'name: "History"',
    'name: "요금제"': 'name: "Pricing"',
    '"무제한 최적화 활성됨"': '"Unlimited active tests"',
    '"무제한 최적화 활성화됨"': '"Unlimited active tests"',
    '"1개 최적화 진행 중"': '"1 active test limit"',
    '로그인 안됨': 'Not logged in'
};

for (const [ko, en] of Object.entries(replacements)) {
    content = content.replaceAll(ko, en);
}

// ensure we fix the mangled names if any? Wait, I will just use regex to replace MENUS block.
content = content.replace(/const MENUS = \[[\s\S]*?\];/, `const MENUS = [
  { name: "Dashboard", icon: LayoutDashboard, href: "/dashboard" },
  { name: "New Test", icon: FolderOpen, href: "/new" },
  { name: "Analytics", icon: BarChart3, href: "/analytics" },
  { name: "History", icon: History, href: "/history" },
  { name: "Pricing", icon: Settings, href: "/pricing" },
];`);

fs.writeFileSync(filePath, content, 'utf8');
console.log("Sidebar translated.");
