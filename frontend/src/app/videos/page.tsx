"use client";

import React, { useState, useEffect } from "react";
import { FolderOpen, Sparkles, MonitorPlay, PlayCircle, Plus, Activity } from "lucide-react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

export default function VideosPage() {
  const [videos, setVideos] = useState<any[]>([]);
  const [activeTestVideoIds, setActiveTestVideoIds] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // 영상 목록과 현재 진행중인 테스트 목록을 동시에 가져옵니다.
    Promise.all([
      apiFetch("/api/videos").then(res => res.json()),
      apiFetch("/api/tests").then(res => res.json())
    ])
    .then(([videosData, testsData]) => {
      if (videosData.videos) {
        setVideos(videosData.videos);
      }
      
      if (testsData.tests) {
        // RUNNING 상태인 테스트들의 유튜브 비디오 ID만 추출하여 Set으로 저장
        const activeIds = new Set<string>(
          testsData.tests
            .filter((t: any) => t.status === "RUNNING")
            .map((t: any) => t.video_id)
        );
        setActiveTestVideoIds(activeIds);
      }
      
      setIsLoading(false);
    })
    .catch(err => {
      console.error("데이터 조회 실패:", err);
      setIsLoading(false);
    });
  }, []);

  return (
    <div className="w-full p-8 animate-fade-in-up">
      <div className="mb-10 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-black mb-2 flex items-center gap-3">
            <MonitorPlay className="text-red-500" size={32} /> 내 영상 목록
          </h1>
          <p className="text-zinc-400">연동된 유튜브 채널의 최근 업로드 영상들을 확인하고 바로 최적화를 시작하세요.</p>
        </div>
        
        </div>

      {isLoading ? (
        <div className="text-center py-20 text-zinc-400 animate-pulse">유튜브에서 영상을 불러오는 중입니다...</div>
      ) : videos.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-32 text-center bg-zinc-900/30 rounded-3xl border border-zinc-800/50 border-dashed">
          <div className="w-20 h-20 bg-zinc-800/50 rounded-full flex items-center justify-center mb-6">
            <FolderOpen size={32} className="text-zinc-500" />
          </div>
          <h2 className="text-2xl font-bold text-white mb-2">업로드된 영상이 없습니다</h2>
          <p className="text-zinc-400">채널에 아직 영상이 없거나, 불러올 수 없습니다.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {videos.map((v) => {
            const isTesting = activeTestVideoIds.has(v.id);
            
            return (
              <div 
                key={v.id} 
                className={`glass-panel rounded-2xl overflow-hidden group transition-all ${
                  isTesting 
                    ? "border-cyan-500/30 bg-cyan-950/10 shadow-[0_0_15px_rgba(6,182,212,0.1)]" 
                    : "border-zinc-800/50 bg-zinc-900/40 hover:border-cyan-500/30"
                }`}
              >
                {/* Thumbnail Area */}
                <div className="relative aspect-video bg-zinc-800 overflow-hidden">
                  <img 
                    src={v.thumbnail_url} 
                    alt={v.title} 
                    className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" 
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" />
                  
                  {isTesting ? (
                    <div className="absolute top-3 left-3 px-2 py-1 bg-cyan-500/20 border border-cyan-500/40 rounded text-xs font-bold text-cyan-400 flex items-center gap-1 backdrop-blur-md">
                      <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" /> 최적화 중
                    </div>
                  ) : (
                    <div className="absolute bottom-3 right-3 px-2 py-1 bg-black/80 rounded text-xs font-bold text-white flex items-center gap-1 backdrop-blur-sm">
                      <PlayCircle size={12} /> 영상
                    </div>
                  )}
                </div>

                {/* Content Area */}
                <div className="p-5 flex flex-col h-[180px]">
                  <h3 className={`font-bold text-sm line-clamp-2 leading-relaxed mb-3 transition-colors ${
                    isTesting ? "text-cyan-100" : "text-zinc-100 group-hover:text-cyan-400"
                  }`}>
                    {v.title}
                  </h3>
                  
                  <div className="flex items-center justify-between text-xs text-zinc-400 font-medium mb-auto">
                    <span>조회수 {parseInt(v.view_count || '0').toLocaleString()}회</span>
                    <span>{new Date(v.published_at).toLocaleDateString()}</span>
                  </div>

                  <div className="pt-4 border-t border-zinc-800/50">
                    {isTesting ? (
                      <Link 
                        href="/" 
                        className="w-full py-2.5 bg-cyan-900/30 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-900/50 hover:border-cyan-500/50 rounded-xl text-sm font-bold flex items-center justify-center gap-2 transition-all"
                      >
                        <Activity size={16} className="animate-pulse" /> ⏳ 최적화 진행 현황 보기
                      </Link>
                    ) : (
                      <Link 
                        href={`/new?videoId=${v.id}`} 
                        className="w-full py-2.5 bg-zinc-800/80 hover:bg-cyan-500/10 text-zinc-300 hover:text-cyan-400 border border-transparent hover:border-cyan-500/30 rounded-xl text-sm font-bold flex items-center justify-center gap-2 transition-all"
                      >
                        <Sparkles size={16} /> 썸네일 테스트 생성
                      </Link>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
