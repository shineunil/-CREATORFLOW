const fs = require('fs');

let content = fs.readFileSync('src/app/new/page.tsx', 'utf8');

const target_pattern = /<div className="grid grid-cols-1 md:grid-cols-2 gap-4">.*?<\/div>\s*\)\)\s*\)\}\s*<\/div>/s;

const replacement = `          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {videos.length === 0 ? (
              <div className="col-span-full text-center p-12 text-zinc-500 glass-panel rounded-2xl border border-zinc-800/50">
                Loading recent videos from your connected YouTube channel...
              </div>
            ) : (
              videos.map((v) => {
                const isTesting = activeTestVideoIds.has(v.id);
                return (
                  <div 
                    key={v.id} 
                    className={\`glass-panel rounded-xl overflow-hidden border border-zinc-800/50 flex flex-col group \${isTesting ? 'opacity-70 grayscale-[30%]' : 'cursor-pointer hover:border-cyan-500/50 hover:-translate-y-1 transition-all'}\`}
                  >
                    <div className="relative aspect-video w-full overflow-hidden bg-zinc-900">
                      <img src={v.thumbnail_url} alt={v.title} className={\`w-full h-full object-cover transition-transform \${!isTesting && 'group-hover:scale-105'}\`} />
                      {isTesting && (
                        <div className="absolute top-2 right-2 flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-cyan-500/90 text-white text-xs font-bold shadow-lg backdrop-blur-md">
                          <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" /> Testing
                        </div>
                      )}
                    </div>
                    
                    <div className="p-4 flex-1 flex flex-col">
                      <h3 className="font-bold text-sm text-zinc-200 line-clamp-2 mb-2 group-hover:text-cyan-400 transition-colors flex-1">{v.title}</h3>
                      <div className="flex justify-between items-center text-xs text-zinc-500 mb-4">
                        <span>{parseInt(v.view_count).toLocaleString()} views</span>
                        <span>{new Date(v.published_at).toLocaleDateString()}</span>
                      </div>
                      
                      <button 
                        disabled={isTesting}
                        onClick={() => { if (!isTesting) { setSelectedVideo(v); setStep(2); } }}
                        className={\`w-full py-2.5 rounded-lg font-bold text-sm transition-all flex items-center justify-center gap-2 \${
                          isTesting 
                            ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed' 
                            : 'bg-zinc-800/80 hover:bg-cyan-500 hover:text-white text-zinc-300'
                        }\`}
                      >
                        {isTesting ? 'Optimization in progress' : 'Select for Test'}
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>`;

content = content.replace(target_pattern, replacement);

fs.writeFileSync('src/app/new/page.tsx', content, 'utf8');
console.log('patched');
