import re
with open('src/app/new/page.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''                  )}
                </div>

                  <input 
                    type="text" 
                    value={v.title_text}
                    onChange={(e) => handleTitleChange(v.id, e.target.value)}
                    placeholder="클릭을 유도하는 제목을 입력하세요..."
                    className="w-full bg-zinc-900 border border-zinc-700 text-zinc-100 text-sm rounded-lg p-3 outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all placeholder:text-zinc-600"
                  />
                </div>
              </div>
            </div>'''

replacement = '''                  )}
                </div>

                <div className="flex-1 space-y-4">
                  <div>
                    <label className="block text-xs text-zinc-400 mb-1">테스트할 영상 제목</label>
                    <input 
                      type="text" 
                      value={v.title_text}
                      onChange={(e) => handleTitleChange(v.id, e.target.value)}
                      placeholder="클릭을 유도하는 제목을 입력하세요..."
                      className="w-full bg-zinc-900 border border-zinc-700 text-zinc-100 text-sm rounded-lg p-3 outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all placeholder:text-zinc-600"
                    />
                  </div>
                  
                  {v.ml_score !== null && (
                    <div className="bg-cyan-900/10 border border-cyan-800/50 rounded-lg p-3 flex items-start gap-3">
                      <div className="flex flex-col items-center justify-center bg-cyan-950 rounded-lg p-2 min-w-[60px]">
                        <span className="text-[10px] text-cyan-400 font-medium">예측 점수</span>
                        <span className="text-xl font-bold text-zinc-100">{v.ml_score}</span>
                      </div>
                      <div className="flex-1">
                        <h4 className="text-sm font-semibold text-cyan-300 mb-1 flex items-center gap-1">
                          <Settings2 size={14} /> AI 썸네일 분석 피드백
                        </h4>
                        <p className="text-xs text-zinc-300 leading-relaxed">{v.ml_feedback}</p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>'''

new_content = content.replace(target, replacement)
with open('src/app/new/page.tsx', 'w', encoding='utf-8') as f:
    f.write(new_content)
