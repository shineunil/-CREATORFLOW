const fs = require('fs');
let content = fs.readFileSync('src/app/new/page.tsx', 'utf8');

content = content.replace(/"BASIC \?금\?는 최\? 2\?B, C\)까\?\?추\? \?보\?\?록\?\?\?\?\?\?습\?다\.\\n\?\?많\? \?네\?을 \?시\?\?\?스\?\n\?려\?PRO \?금\?로 \?그\?이\?해주세\?\?"/g, '"BASIC plan can add up to 2 extra thumbnails (B, C).\\nPlease upgrade to PRO to test more thumbnails."');

content = content.replace(/errData\.detail \|\| "BASIC Plan Restriction\?\?\?\?달\?습\?다\.\\n무제\?\?최적\?\? \?\하\?면 PRO \?금\?로 \?\그\?이\?해주세\?\?"/g, 'errData.detail || "BASIC Plan Restriction reached.\\nPlease upgrade to PRO for unlimited optimizations."');

content = content.replace(/<span>변\\?\/span>/g, '<span>Change</span>');

content = content.replace(/<span className="font-bold text-cyan-400">\?로\?\?\?분석 \?\.\.<\/span>/g, '<span className="font-bold text-cyan-400">Uploading and Analyzing...</span>');

content = content.replace(/AI Thumbnail Analysis Complete \(Score:\n \{v\.ml_score\}\?\?/g, 'AI Thumbnail Analysis Complete (Score: {v.ml_score}/100)');
content = content.replace(/AI Thumbnail Analysis Complete \(Score: \{v\.ml_score\}\?\?/g, 'AI Thumbnail Analysis Complete (Score: {v.ml_score}/100)');

content = content.replace(/<p className="text-xs text-zinc-500 mt-2">\?스\?\? \?나\?\?리\?\?\?네\?로 고정\?\니\?\?<\/p>/g, '<p className="text-xs text-zinc-500 mt-2">The best thumbnail will be permanently applied when the test ends.</p>');

fs.writeFileSync('src/app/new/page.tsx', content, 'utf8');
console.log('misc patched');
