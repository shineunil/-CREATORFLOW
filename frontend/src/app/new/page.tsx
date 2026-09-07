"use client";

import React, { useState, useRef, Suspense } from "react";
import { ArrowLeft, UploadCloud, Upload, Plus, Play, CheckCircle2, Sparkles, Trash2, LayoutDashboard, RefreshCcw, Wand2, Loader2 } from "lucide-react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { useRouter, useSearchParams } from "next/navigation";
import Modal from "@/components/Modal";

function NewTestContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const videoIdFromUrl = searchParams.get("videoId");
  
  // Modal State
  const [modalConfig, setModalConfig] = useState<{
    isOpen: boolean;
    type?: "alert" | "confirm";
    variant?: "info" | "success" | "warning" | "error";
    title: string;
    message: string;
    confirmText?: string;
    cancelText?: string;
    onConfirm: () => void;
    onCancel?: () => void;
  }>({
    isOpen: false,
    title: "",
    message: "",
    onConfirm: () => {},
  });

  const showAlert = (title: string, message: string, variant: "info" | "success" | "warning" | "error" = "info", onConfirm?: () => void) => {
    setModalConfig({
      isOpen: true,
      type: "alert",
      variant,
      title,
      message,
      onConfirm: () => {
        setModalConfig(prev => ({ ...prev, isOpen: false }));
        if (onConfirm) onConfirm();
      }
    });
  };

  const [step, setStep] = useState(1);
  const [selectedVideo, setSelectedVideo] = useState<any>(null);
  
  // Variations state
  const [variations, setVariations] = useState<any[]>([
    { id: "B", title_text: "", thumbnail_image_url: null, analyzing: false, ml_score: null, ml_feedback: null, showGenerator: false, generateHeadline: "" },
  ]);
  
  const [swapInterval, setSwapInterval] = useState("240");
  const [durationHours, setDurationHours] = useState("24");
  
  const [videos, setVideos] = useState<any[]>([]);
  const [activeTestVideoIds, setActiveTestVideoIds] = useState<Set<string>>(new Set());
  const [userProfile, setUserProfile] = useState<any>({});

  // 후보별로 마지막으로 시작된 업로드 요청의 순번을 기록합니다.
  // 같은 후보에 연달아 빠르게 이미지를 올리면 네트워크 응답이 요청 순서와 다르게 도착할 수 있는데,
  // 이 토큰 없이는 먼저 보낸(느린) 요청의 응답이 나중에 도착해 최신 업로드 결과를 덮어써버립니다.
  const uploadTokenRef = useRef<Record<string, number>>({});
  
  React.useEffect(() => {
    apiFetch("/api/user/me")
      .then(res => res.json())
      .then(data => setUserProfile(data))
      .catch(err => console.error("Failed to fetch profile:", err));

    apiFetch("/api/tests")
      .then(res => res.json())
      .then(data => {
        if (data.tests) {
          const activeIds = new Set<string>();
          data.tests.forEach((t: any) => {
            if (t.status === "RUNNING") activeIds.add(t.video_id);
          });
          setActiveTestVideoIds(activeIds);
        }
      })
      .catch(err => console.error("Failed to fetch active tests:", err));

    apiFetch("/api/videos")
      .then(res => res.json())
      .then(data => {
        if (data.videos) {
          setVideos(data.videos);
          // 만약 URL에 videoId가 있다면 해당 영상을 찾아서 즉시 2단계로 넘어갑니다.
          if (videoIdFromUrl) {
            const target = data.videos.find((v: any) => v.id === videoIdFromUrl);
            if (target) {
              setSelectedVideo(target);
              setStep(2);
            }
          }
        }
      })
      .catch(err => console.error("Failed to fetch video list:", err));
  }, [videoIdFromUrl]);

  const handleTitleChange = (id: string, newTitle: string) => {
    setVariations(prev => prev.map(v => v.id === id ? { ...v, title_text: newTitle } : v));
  };

  // Image Upload
  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>, targetVarId: string) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // 이 업로드 요청이 해당 후보의 "최신" 요청임을 표시합니다. 응답이 도착했을 때 이 토큰이
    // 여전히 최신인 경우에만 화면에 반영해, 뒤늦게 도착한 이전 요청의 응답이 최신 업로드 결과를
    // 덮어쓰지 않도록 합니다.
    const myToken = (uploadTokenRef.current[targetVarId] || 0) + 1;
    uploadTokenRef.current[targetVarId] = myToken;
    const isStale = () => uploadTokenRef.current[targetVarId] !== myToken;

    setVariations(prev => prev.map(v => v.id === targetVarId ? { ...v, analyzing: true } : v));

    try {
      const formData = new FormData();
      formData.append("file", file, file.name);

      const response = await apiFetch("/api/upload", {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();

        // Call ML analysis
        const analyzeRes = await apiFetch("/api/analyze-thumbnail", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ filename: data.filename })
        });

        let score = null;
        let feedback = null;
        if (analyzeRes.ok) {
          const analyzeData = await analyzeRes.json();
          score = analyzeData.score;
          feedback = analyzeData.feedback;
        }

        if (isStale()) return;
        setVariations(prev => prev.map(v => v.id === targetVarId ? {
          ...v,
          thumbnail_image_url: data.url,
          ml_score: score,
          ml_feedback: feedback,
          analyzing: false
        } : v));
      } else {
        if (isStale()) return;
        showAlert("Upload Failed", "Failed to upload image.", "error");
        setVariations(prev => prev.map(v => v.id === targetVarId ? { ...v, analyzing: false } : v));
      }
    } catch (error) {
      console.error("Upload error:", error);
      if (isStale()) return;
      showAlert("Error Occurred", "An error occurred while uploading the image.", "error");
      setVariations(prev => prev.map(v => v.id === targetVarId ? { ...v, analyzing: false } : v));
    }
  };

  const toggleGenerator = (targetVarId: string) => {
    setVariations(prev => prev.map(v => v.id === targetVarId ? { ...v, showGenerator: !v.showGenerator } : v));
  };

  const handleGenerateHeadlineChange = (targetVarId: string, text: string) => {
    setVariations(prev => prev.map(v => v.id === targetVarId ? { ...v, generateHeadline: text } : v));
  };

  // AI Thumbnail Assist: 베이스 이미지 + 문구로 유튜브 규격 썸네일을 자동 생성 (PIL 기반, 외부 API 비용 없음)
  const handleGenerateThumbnail = async (e: React.ChangeEvent<HTMLInputElement>, targetVarId: string) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const targetVar = variations.find(v => v.id === targetVarId);
    const headline = (targetVar?.generateHeadline || "").trim();
    if (!headline) {
      showAlert("문구를 입력해주세요", "썸네일에 넣을 짧은 문구를 먼저 입력한 뒤 베이스 이미지를 선택해주세요.", "warning");
      e.target.value = "";
      return;
    }

    const myToken = (uploadTokenRef.current[targetVarId] || 0) + 1;
    uploadTokenRef.current[targetVarId] = myToken;
    const isStale = () => uploadTokenRef.current[targetVarId] !== myToken;

    setVariations(prev => prev.map(v => v.id === targetVarId ? { ...v, analyzing: true } : v));

    try {
      const formData = new FormData();
      formData.append("file", file, file.name);
      formData.append("headline", headline);

      const response = await apiFetch("/api/generate-thumbnail", {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        if (isStale()) return;
        setVariations(prev => prev.map(v => v.id === targetVarId ? {
          ...v,
          thumbnail_image_url: data.url,
          ml_score: data.analysis?.score ?? null,
          ml_feedback: data.analysis?.feedback ?? null,
          analyzing: false,
          showGenerator: false,
        } : v));
      } else {
        const err = await response.json().catch(() => ({}));
        if (isStale()) return;
        showAlert("생성 실패", err.detail || "썸네일 생성에 실패했습니다.", "error");
        setVariations(prev => prev.map(v => v.id === targetVarId ? { ...v, analyzing: false } : v));
      }
    } catch (error) {
      console.error("Generate thumbnail error:", error);
      if (isStale()) return;
      showAlert("오류 발생", "썸네일 생성 중 오류가 발생했습니다.", "error");
      setVariations(prev => prev.map(v => v.id === targetVarId ? { ...v, analyzing: false } : v));
    }
  };

  const addVariation = () => {
    if (!userProfile.is_pro && variations.length >= 2) {
      showAlert(
        "Candidate Limit Reached", 
        "BASIC 요금제는 최대 2개(B, C)까지만 추가 후보를 등록할 수 있습니다.\n더 많은 썸네일을 동시에 테스트하시려면 PRO 요금제로 업그레이드해주세요.", 
        "warning",
        () => router.push("/pricing")
      );
      return;
    }
    if (variations.length >= 4) {
      showAlert("Maximum Limit Reached", "Even on PRO plan, you can only test up to 4 extra candidates (5 total) simultaneously.", "warning");
      return;
    }
    
    setVariations(prev => {
      // Find the next available letter ID (B, C, D, E)
      const existingIds = prev.map(v => v.id);
      let nextId = "B";
      for (let i = 66; i <= 69; i++) {
        const letter = String.fromCharCode(i);
        if (!existingIds.includes(letter)) {
          nextId = letter;
          break;
        }
      }
      return [...prev, { id: nextId, title_text: "", thumbnail_image_url: null, analyzing: false, showGenerator: false, generateHeadline: "" }];
    });
  };

  const removeVariation = (idToRemove: string) => {
    setVariations(prev => prev.filter(v => v.id !== idToRemove));
  };

  const [isSubmittingTest, setIsSubmittingTest] = useState(false);

  const handleStartTest = async () => {
    if (!selectedVideo) {
      showAlert("Select a Video", "Please select an original video to optimize.", "warning");
      return;
    }
    if (isSubmittingTest) return;

    setIsSubmittingTest(true);
    try {
      const response = await apiFetch("/api/tests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          youtube_video_id: selectedVideo.id,
          swap_interval_minutes: parseInt(swapInterval),
          duration_hours: parseInt(durationHours),
          variations: [
            { 
              name: "Variation A", 
              title_text: selectedVideo.title || "Original Title", 
              is_control: true,
              thumbnail_image_url: selectedVideo.thumbnail_url || null
            },
            ...variations.map(v => ({
              name: `Variation ${v.id}`,
              title_text: v.title_text || `Test Title ${v.id}`,
              is_control: false,
              thumbnail_image_url: v.thumbnail_image_url || null
            }))
          ]
        })
      });
      
      if (!response.ok) {
        if (response.status === 403) {
           const errData = await response.json();
           showAlert(
             "Plan Limit Exceeded",
             errData.detail || "BASIC Plan Restriction에 도달했습니다.\n무제한 최적화를 원하시면 PRO 요금제로 업그레이드해주세요.",
             "warning",
             () => router.push("/pricing")
           );
        } else {
           const errData = await response.json().catch(() => ({}));
           showAlert("Execution Error", errData.detail || "An error occurred while executing the optimization.", "error");
        }
        return;
      }

      // 방금 만든 테스트의 영상을 즉시 "테스트 중"으로 표시 (이 화면으로 다시 돌아왔을 때
      // 이미 테스트 중인 영상에 또 테스트를 거는 걸 방지 - /api/tests 재요청 없이도 바로 반영)
      setActiveTestVideoIds(prev => new Set(prev).add(selectedVideo.id));
      setStep(3); // Success step
    } catch (e) {
      console.error(e);
      showAlert("Error Occurred", "A server communication error occurred. Please check your connection and try again.", "error");
    } finally {
      setIsSubmittingTest(false);
    }
  };

  return (
    <div className="w-full p-8 animate-fade-in-up">
      <Link href="/" className="inline-flex items-center gap-2 text-zinc-400 hover:text-white transition-colors mb-8 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
        <ArrowLeft size={20} aria-hidden="true" />
        <span className="font-semibold">Back to Dashboard</span>
      </Link>

      <div className="mb-10">
        <h1 className="text-3xl font-black mb-2 flex items-center gap-3">
          <Sparkles className="text-cyan-400" size={28} aria-hidden="true" /> Start New Thumbnail Optimization
        </h1>
        <p className="text-zinc-400">Upload multiple thumbnails and titles. We will find the best performing combination.</p>
      </div>

      {step === 1 && (
        <div className="space-y-6">
          <h2 className="text-xl font-bold border-b border-zinc-800 pb-4">1. Select Original Video</h2>
                    <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {videos.length === 0 ? (
              <div className="col-span-full text-center p-12 text-zinc-400 glass-panel rounded-2xl border border-zinc-800/50" role="status">
                Loading recent videos from your connected YouTube channel...
              </div>
            ) : (
              videos.map((v) => {
                const isTesting = activeTestVideoIds.has(v.id);
                return (
                  <div 
                    key={v.id} 
                    onClick={() => { if (!isTesting) { setSelectedVideo(v); setStep(2); } }}
                    className={`glass-panel rounded-xl overflow-hidden border border-zinc-800/50 flex flex-col group ${isTesting ? 'opacity-70 grayscale-[30%]' : 'cursor-pointer hover:border-cyan-500/50 hover:-translate-y-1 transition-all'}`}
                  >
                    <div className="relative aspect-video w-full overflow-hidden bg-zinc-900">
                      <img src={v.thumbnail_url} alt={v.title} className={`w-full h-full object-cover transition-transform ${!isTesting && 'group-hover:scale-105'}`} />
                      {isTesting && (
                        <div className="absolute top-2 right-2 flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-cyan-500/90 text-white text-xs font-bold shadow-lg backdrop-blur-md">
                          <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" aria-hidden="true" /> Testing
                        </div>
                      )}
                    </div>

                    <div className="p-4 flex-1 flex flex-col">
                      <h3 className="font-bold text-sm text-zinc-200 line-clamp-2 mb-2 group-hover:text-cyan-400 transition-colors flex-1">{v.title}</h3>
                      <div className="flex justify-between items-center text-xs text-zinc-400 mb-4">
                        <span>{parseInt(v.view_count || '0').toLocaleString()} views</span>
                        <span>{new Date(v.published_at).toLocaleDateString()}</span>
                      </div>

                      <button
                        disabled={isTesting}
                        onClick={() => { if (!isTesting) { setSelectedVideo(v); setStep(2); } }}
                        className={`w-full py-2.5 rounded-lg font-bold text-sm transition-all flex items-center justify-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 ${
                          isTesting
                            ? 'bg-zinc-800 text-zinc-400 cursor-not-allowed'
                            : 'bg-zinc-800/80 hover:bg-cyan-500 hover:text-white text-zinc-300'
                        }`}
                      >
                        {isTesting ? 'Optimization in progress' : 'Select for Test'}
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-8 animate-fade-in-up">
          <div className="glass-panel p-6 rounded-2xl border border-zinc-800/50 flex gap-6 items-center bg-zinc-900/30">
            <img src={selectedVideo?.thumbnail_url} alt="Original" className="w-48 rounded-xl" />
            <div>
              <div className="text-xs font-bold text-cyan-400 mb-2 uppercase tracking-wider">Original Video (Candidate A)</div>
              <h3 className="text-lg font-bold mb-1">{selectedVideo?.title}</h3>
              <p className="text-sm text-zinc-400">{parseInt(selectedVideo?.view_count || '0').toLocaleString()} views</p>
            </div>
            <button 
              onClick={() => { router.replace("/videos"); }} 
              className="ml-auto flex items-center gap-2 px-5 py-2.5 text-sm font-bold text-zinc-300 bg-zinc-800 border border-zinc-700 rounded-xl hover:bg-zinc-700 hover:text-white hover:border-zinc-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-900 transition-all cursor-pointer"
              aria-label="Change original video"
            >
              <RefreshCcw size={16} aria-hidden="true" />
              <span>변경</span>
            </button>
          </div>

          <div>
            <div className="flex items-center justify-between mb-4 border-b border-zinc-800 pb-4">
              <h2 className="text-xl font-bold flex items-center gap-2">
                2. Add Candidates
              </h2>
              <button onClick={addVariation} className="flex items-center gap-2 text-sm font-bold text-cyan-400 hover:text-cyan-300 transition-colors bg-cyan-950/30 px-4 py-2 rounded-full border border-cyan-500/20 hover:border-cyan-500/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
                <Plus size={16} aria-hidden="true" /> Add Candidate (Max 5)
              </button>
            </div>

            <div className="space-y-6">
              {variations.map((v) => (
                <div key={v.id} className="glass-panel p-6 rounded-2xl border border-zinc-800/50 relative group">
                  <div className="absolute top-0 left-0 bg-zinc-800 text-white font-bold px-5 py-2 rounded-br-2xl rounded-tl-2xl text-base">
                    Candidate {v.id}
                  </div>
                  
                  {variations.length > 1 && (
                    <button 
                      onClick={() => removeVariation(v.id)}
                      className="absolute -top-4 -right-4 w-11 h-11 bg-zinc-900 border border-zinc-700 rounded-full flex items-center justify-center text-zinc-400 hover:text-red-400 hover:border-red-600 hover:bg-red-950/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-900 transition-all z-10 shadow-lg cursor-pointer"
                      aria-label={`Delete Candidate ${v.id}`}
                      title={`Delete Candidate ${v.id}`}
                    >
                      <Trash2 size={20} aria-hidden="true" />
                    </button>
                  )}
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8 pt-4">
                    <div>
                      <label className="block text-base font-bold text-white mb-3">Test Thumbnail Image</label>
                      
                      {v.thumbnail_image_url ? (
                        <label className="block relative rounded-xl overflow-hidden group/img cursor-pointer">
                          <input 
                            type="file" 
                            onChange={(e) => handleImageUpload(e, v.id)} 
                            accept="image/png, image/jpeg" 
                            className="hidden" 
                          />
                          <img src={v.thumbnail_image_url} alt={`Thumbnail ${v.id}`} className={`w-full aspect-video object-cover ${v.analyzing ? 'opacity-50 blur-sm' : ''}`} />
                          {!v.analyzing && (
                            <div className="absolute inset-0 bg-black/60 opacity-0 group-hover/img:opacity-100 flex items-center justify-center transition-opacity backdrop-blur-sm">
                              <span className="font-bold text-white flex items-center gap-2"><Upload size={18} aria-hidden="true" /> Re-upload</span>
                            </div>
                          )}
                        </label>
                      ) : v.analyzing ? (
                        <div className="w-full aspect-video rounded-xl border-2 border-dashed border-zinc-700 bg-zinc-900/50 flex flex-col items-center justify-center" role="status">
                          <span className="w-8 h-8 rounded-full border-2 border-cyan-500 border-t-transparent animate-spin mb-3" aria-hidden="true"></span>
                          <span className="font-bold text-cyan-400">{v.showGenerator ? "썸네일 자동 생성 중..." : "업로드 및 분석 중..."}</span>
                        </div>
                      ) : v.showGenerator ? (
                        <div className="w-full aspect-video rounded-xl border-2 border-dashed border-violet-500/40 bg-violet-950/10 flex flex-col items-center justify-center p-5 gap-3">
                          <div className="flex items-center gap-2 text-violet-300 text-sm font-bold">
                            <Wand2 size={16} aria-hidden="true" /> AI Thumbnail Assist
                          </div>
                          <input
                            type="text"
                            value={v.generateHeadline}
                            onChange={(e) => handleGenerateHeadlineChange(v.id, e.target.value)}
                            placeholder="썸네일에 넣을 짧은 문구 (예: I BUILT THE ULTIMATE PC)"
                            maxLength={60}
                            className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500"
                          />
                          <label className="cursor-pointer w-full">
                            <input
                              type="file"
                              onChange={(e) => handleGenerateThumbnail(e, v.id)}
                              accept="image/png, image/jpeg, image/webp"
                              className="hidden"
                            />
                            <div className="flex items-center justify-center gap-2 w-full py-2.5 bg-violet-600/20 hover:bg-violet-600/30 border border-violet-500/40 rounded-lg text-sm font-bold text-violet-200 transition-colors">
                              <UploadCloud size={16} aria-hidden="true" /> 베이스 사진 선택 &amp; 생성
                            </div>
                          </label>
                          <button onClick={() => toggleGenerator(v.id)} className="text-xs text-zinc-400 hover:text-zinc-300 underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 rounded">
                            직접 업로드로 돌아가기
                          </button>
                        </div>
                      ) : (
                        <label className="block w-full aspect-video rounded-xl border-2 border-dashed border-zinc-700 bg-zinc-900/50 hover:bg-zinc-800/80 hover:border-cyan-500/50 flex flex-col items-center justify-center cursor-pointer transition-all group/upload relative">
                          <input
                            type="file"
                            onChange={(e) => handleImageUpload(e, v.id)}
                            accept="image/png, image/jpeg"
                            className="hidden"
                          />
                          <UploadCloud size={48} className="text-zinc-400 group-hover/upload:text-cyan-400 mb-4 transition-colors" aria-hidden="true" />
                          <span className="text-lg font-bold text-zinc-300 group-hover/upload:text-white">Click to upload image</span>
                          <span className="text-sm font-medium text-zinc-400 mt-2">Recommended: 1280x720 (Max 2MB)</span>
                          <button
                            type="button"
                            onClick={(e) => { e.preventDefault(); e.stopPropagation(); toggleGenerator(v.id); }}
                            className="mt-3 flex items-center gap-1.5 text-xs font-bold text-violet-400 hover:text-violet-300 px-3 py-1.5 rounded-full bg-violet-950/40 border border-violet-500/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                          >
                            <Wand2 size={12} aria-hidden="true" /> AI로 자동 생성해보기
                          </button>
                        </label>
                      )}
                    </div>
                    
                    <div className="space-y-6">
                      <div>
                        <label className="block text-base font-bold text-white mb-3">Test Title</label>
                        <input 
                          type="text" 
                          value={v.title_text}
                          onChange={(e) => handleTitleChange(v.id, e.target.value)}
                          placeholder="Same as original or try a new one"
                          className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
                        />
                      </div>
                      
                      {v.ml_score != null && (
                        <div className="p-4 bg-emerald-950/20 border border-emerald-500/20 rounded-xl">
                          <div className="flex items-center gap-2 mb-2">
                            <Sparkles size={16} className="text-emerald-400" aria-hidden="true" />
                            <span className="font-bold text-emerald-400 text-sm">AI Thumbnail Analysis Complete (Score: {v.ml_score}점)</span>
                          </div>
                          <p className="text-xs text-emerald-200/70">{v.ml_feedback}</p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h2 className="text-xl font-bold mb-4 border-b border-zinc-800 pb-4">3. Optimization Settings</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="glass-panel p-6 rounded-2xl border border-zinc-800/50">
                  <label className="block text-sm font-bold text-zinc-300 mb-2">Swap Interval</label>
                  <select
                    value={swapInterval}
                    onChange={(e) => {
                      // BASIC 요금제는 최소 4시간(240분) 주기부터 선택 가능 - backend/test_policy.py의
                      // BASIC_MIN_SWAP_INTERVAL_MINUTES와 동일한 기준
                      if (parseInt(e.target.value) < 240 && !userProfile.is_pro) {
                        showAlert("Plan Restriction", "Swap intervals shorter than 4 hours are a PRO feature.\nPlease upgrade to PRO to use this.", "warning", () => router.push("/pricing"));
                        return;
                      }
                      setSwapInterval(e.target.value);
                    }}
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-cyan-500 appearance-none"
                  >
                    <option value="240">Swap every 4 hours (Recommended)</option>
                    <option value="720">Swap every 12 hours</option>
                    <option value="1440">Swap every 24 hours</option>
                    <option value="120" disabled={!userProfile.is_pro} className="text-orange-500 font-bold">
                      🔑 Swap every 2 hours (PRO Only)
                    </option>
                    <option value="60" disabled={!userProfile.is_pro} className="text-orange-500 font-bold">
                      🔑 Swap every 1 hour (PRO Only)
                    </option>
                    <option value="30" disabled={!userProfile.is_pro} className="text-orange-500 font-bold">
                      🔑 Swap every 30 mins (PRO Only)
                    </option>
                  </select>
                  <p className="text-xs text-zinc-400 mt-2">Candidates are rotated on YouTube and compared by views gained per hour (VPH).</p>
                </div>

              <div className="glass-panel p-6 rounded-2xl border border-zinc-800/50">
                <label className="block text-sm font-bold text-zinc-300 mb-2">Total Optimization Duration</label>
                <select 
                  value={durationHours}
                  onChange={(e) => setDurationHours(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-cyan-500 appearance-none"
                >
                  <option value="24">Apply best thumbnail permanently after 24 hours</option>
                  <option value="48">Apply best thumbnail permanently after 48 hours</option>
                  <option value="72">Apply best thumbnail permanently after 72 hours</option>
                </select>
                <p className="text-xs text-zinc-400 mt-2">테스트가 끝나면 승리한 썸네일로 고정됩니다.</p>
              </div>
            </div>
          </div>

          <div className="pt-6 border-t border-zinc-800 flex flex-col items-end gap-2">
            <button
              onClick={handleStartTest}
              disabled={isSubmittingTest}
              className="px-10 py-4 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 rounded-xl font-black text-white shadow-lg hover:shadow-cyan-500/25 transition-all flex items-center gap-3 cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:from-cyan-600 disabled:hover:to-blue-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-900"
            >
              {isSubmittingTest ? (
                <>
                  <Loader2 size={20} className="animate-spin" aria-hidden="true" />
                  Applying to YouTube...
                </>
              ) : (
                <>
                  <Play size={20} className="fill-white" aria-hidden="true" />
                  Start Real-time Optimization Campaign
                </>
              )}
            </button>
            {isSubmittingTest && (
              <p className="text-xs text-zinc-400" role="status">테스트를 생성하는 중입니다...</p>
            )}
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="py-20 flex flex-col items-center justify-center text-center animate-fade-in-up">
          <div className="w-24 h-24 bg-emerald-500/10 border border-emerald-500/30 rounded-full flex items-center justify-center mb-8" aria-hidden="true">
            <CheckCircle2 size={48} className="text-emerald-400" />
          </div>
          <h2 className="text-4xl font-black mb-4">Optimization Campaign Started!</h2>
          <p className="text-xl text-zinc-400 max-w-lg mb-10">
            Your first candidate is being applied to YouTube right now — it may take a few seconds
            to show up on your video. From here, CreatorFlow rotates candidates automatically.
          </p>

          <div className="flex gap-4">
            <Link href="/" className="px-8 py-4 bg-zinc-900 hover:bg-zinc-800 rounded-xl font-bold border border-zinc-800 transition-colors flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
              <LayoutDashboard size={18} aria-hidden="true" /> View Status on Dashboard
            </Link>
          </div>
        </div>
      )}

      <Modal {...modalConfig} />
    </div>
  );
}

export default function NewTestPage() {
  return (
    <Suspense fallback={<div className="p-12 text-center text-zinc-400" role="status">Loading...</div>}>
      <NewTestContent />
    </Suspense>
  );
}
