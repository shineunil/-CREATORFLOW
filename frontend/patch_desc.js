const fs = require('fs');
let content = fs.readFileSync('src/app/new/page.tsx', 'utf8');

const target_pattern = /<p className="text-zinc-400">.*?<\/p>/;
const replacement = `<p className="text-zinc-400">Upload multiple thumbnails and titles. We will find the best performing combination.</p>`;

content = content.replace(target_pattern, replacement);
fs.writeFileSync('src/app/new/page.tsx', content, 'utf8');
console.log('patched');
