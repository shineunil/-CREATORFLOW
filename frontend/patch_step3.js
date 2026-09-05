const fs = require('fs');
let content = fs.readFileSync('src/app/new/page.tsx', 'utf8');

const target_pattern = /<div className="glass-panel p-6 rounded-2xl border border-zinc-800\/50">\s*<label className="block text-sm font-bold text-zinc-300 mb-2">Swap Interval<\/label>.*?<\/p>\s*<\/div>/s;

const replacement = `<div className="glass-panel p-6 rounded-2xl border border-zinc-800/50">
                  <label className="block text-sm font-bold text-zinc-300 mb-2">Swap Interval</label>
                  <select 
                    value={swapInterval}
                    onChange={(e) => {
                      if (e.target.value === "30" && !userProfile.is_pro) {
                        showAlert("Plan Restriction", "30-min Swap Interval is a PRO feature.\\nPlease upgrade to PRO to use this.", "warning", () => router.push("/pricing"));
                        return;
                      }
                      setSwapInterval(e.target.value);
                    }}
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-cyan-500 appearance-none"
                  >
                    <option value="60">Swap every 1 hour (Recommended)</option>
                    <option value="120">Swap every 2 hours</option>
                    <option value="30" disabled={!userProfile.is_pro} className="text-orange-500 font-bold">
                      🔑 Swap every 30 mins (PRO Only)
                    </option>
                  </select>
                  <p className="text-xs text-zinc-500 mt-2">Candidates are rotated on YouTube to measure CTR.</p>
                </div>`;

content = content.replace(target_pattern, replacement);
fs.writeFileSync('src/app/new/page.tsx', content, 'utf8');
console.log('patched');
