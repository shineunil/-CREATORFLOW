"use client";

import React, { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";

export default function HistoryPage() {
  const [tests, setTests] = useState<any[]>([]);

  useEffect(() => {
    apiFetch("/api/history")
      .then(res => res.json())
      .then(data => {
        if (data.tests) setTests(data.tests);
      })
      .catch(console.error);
  }, []);

  return (
    <div className="w-full p-8 animate-fade-in-up">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Optimization History</h1>
        <p className="text-zinc-400">Past optimization campaign results.</p>
      </div>

      <div className="space-y-6">
        {tests.length === 0 ? (
          <div className="text-center py-20 text-zinc-500 glass-panel rounded-2xl border border-zinc-800/50">
            No completed optimization records found.
          </div>
        ) : (
          tests.map((test, i) => (
            <div key={i} className="glass-panel p-6 rounded-2xl border border-zinc-800/50 flex flex-col md:flex-row justify-between gap-6">
              <div>
                <p className="text-xs text-zinc-500 mb-2">Test Ended: {new Date(test.end_time).toLocaleDateString()}</p>
                <h3 className="text-lg font-bold">{test.video?.youtube_video_id}</h3>
              </div>
              <div className="flex gap-4">
                {test.variations?.map((v: any) => (
                  <div key={v.id} className="p-3 bg-zinc-900/50 rounded-lg text-sm border border-zinc-800">
                    <div className="font-bold">{v.title_text}</div>
                    <div className="text-zinc-400">{v.views_gained} views gained</div>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
