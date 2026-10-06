"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Clock, Crown, Radio } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { CHANNEL_SWITCHED_EVENT } from "@/lib/channelSwitch";
import { useI18n } from "@/i18n/I18nProvider";
import { formatNumber, parseServerDate } from "@/i18n/format";

type TestSummary = {
  test_id: number;
  video_id: string;
  status: string;
  variations: { name: string; title_text: string | null }[];
};

type Window = { start: string; end: string; hours: number; views_gained: number; vph: number };

type InsightVariation = {
  id: number;
  name: string;
  title_text: string | null;
  thumbnail_image_url: string | null;
  is_control: boolean;
  is_winner: boolean;
  is_live: boolean;
  total_hours: number;
  total_views_gained: number;
  vph: number;
  windows: Window[];
  hourly_minutes: number[];
  hourly_views: number[];
};

type Insights = { test_id: number; status: string; live_since: string | null; variations: InsightVariation[] };

const BLOCKS = 4; // 새벽·오전·오후·저녁 (6시간씩)

/** 서버가 준 UTC 0~23시 칸을 내 기기 시간대로 옮겨 6시간 묶음 4개로 합친다. 30분 단위 시간대는 가까운 시로 근사. */
function toLocalBlocks(utcHourly: number[], offsetHours: number): number[] {
  const blocks = new Array(BLOCKS).fill(0);
  utcHourly.forEach((value, utcHour) => {
    const localHour = (((utcHour + offsetHours) % 24) + 24) % 24;
    blocks[Math.floor(localHour / 6)] += value;
  });
  return blocks;
}

function round1(value: number) {
  return Math.round(value * 10) / 10;
}

export default function TestInsights() {
  const { t, locale } = useI18n();
  const A = t.analytics;
  const intl = locale === "ko" ? "ko-KR" : "en-US";

  const [tests, setTests] = useState<TestSummary[] | null>(null);
  const [testId, setTestId] = useState<number | null>(null);
  const [insights, setInsights] = useState<Insights | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "error">("idle");
  // "몇 분째 측정 중"은 데이터를 받은 시각 기준으로 센다 (화면을 그릴 때마다 시계를 읽지 않게)
  const [loadedAt, setLoadedAt] = useState(0);
  const [offsetHours] = useState(() => Math.round(-new Date().getTimezoneOffset() / 60));

  // 테스트를 빠르게 바꿔 고르면 늦게 온 예전 응답이 화면을 덮지 않게, 마지막으로 요청한 테스트만 반영한다
  const latestRequest = useRef<number | null>(null);

  const selectTest = useCallback((id: number | null) => {
    latestRequest.current = id;
    setTestId(id);
    if (id == null) {
      setInsights(null);
      return;
    }
    setState("loading");
    apiFetch(`/api/tests/${id}/insights`)
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load insights (${res.status})`);
        return res.json();
      })
      .then((data: Insights) => {
        if (latestRequest.current !== id) return;
        setInsights(data);
        setLoadedAt(Date.now());
        // 처음 고르는 후보: 지금 걸려 있는 후보 → 승자 → 첫 후보
        const first = data.variations.find((v) => v.is_live) ?? data.variations.find((v) => v.is_winner) ?? data.variations[0];
        setSelectedId(first ? first.id : null);
        setState("idle");
      })
      .catch(() => {
        if (latestRequest.current === id) setState("error");
      });
  }, []);

  const loadTests = useCallback(() => {
    apiFetch("/api/tests")
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load tests (${res.status})`);
        return res.json();
      })
      .then((data) => {
        const list: TestSummary[] = data.tests || [];
        setTests(list);
        // 진행 중인 테스트가 있으면 그것부터 보여 준다
        const preferred = list.find((x) => x.status === "RUNNING") ?? list[0];
        selectTest(preferred ? preferred.test_id : null);
      })
      .catch(() => {
        setTests([]);
        setState("error");
      });
  }, [selectTest]);

  useEffect(() => {
    loadTests();
    window.addEventListener(CHANNEL_SWITCHED_EVENT, loadTests);
    return () => window.removeEventListener(CHANNEL_SWITCHED_EVENT, loadTests);
  }, [loadTests]);

  const blockRows = useMemo(() => {
    if (!insights) return [];
    return insights.variations.map((v) => {
      const minutes = toLocalBlocks(v.hourly_minutes, offsetHours);
      const views = toLocalBlocks(v.hourly_views, offsetHours);
      return {
        id: v.id,
        name: v.name,
        cells: minutes.map((m, i) => ({ hours: round1(m / 60), vph: m > 0 ? round1(views[i] / (m / 60)) : null })),
      };
    });
  }, [insights, offsetHours]);

  // 시간대마다 가장 높은 VPH를 강조한다
  const bestInBlock = useMemo(
    () =>
      Array.from({ length: BLOCKS }, (_, i) => {
        const values = blockRows.map((r) => r.cells[i].vph).filter((v): v is number => v != null);
        return values.length > 1 ? Math.max(...values) : null;
      }),
    [blockRows],
  );

  const formatWhen = (iso: string) =>
    parseServerDate(iso).toLocaleString(intl, { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });

  const testLabel = (test: TestSummary) => {
    const original = test.variations.find((v) => v.name.endsWith("A")) ?? test.variations[0];
    const title = original?.title_text || test.video_id;
    return `${title} · ${A.status[test.status] ?? test.status}`;
  };

  const selected = insights?.variations.find((v) => v.id === selectedId) ?? null;
  const liveMinutes =
    insights?.live_since && loadedAt ? Math.max(0, Math.floor((loadedAt - parseServerDate(insights.live_since).getTime()) / 60000)) : null;

  return (
    <section className="glass-panel p-6 md:p-8 rounded-2xl border border-zinc-800/50 mt-6">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
        <div className="min-w-0">
          <h2 className="text-xl font-bold mb-1">{A.testSection}</h2>
          <p className="text-sm text-zinc-400 break-keep">{A.testSectionSub}</p>
        </div>
        {tests && tests.length > 0 && (
          <div className="w-full sm:w-auto min-w-0">
            <label htmlFor="insights-test" className="sr-only">{A.selectTest}</label>
            <select
              id="insights-test"
              value={testId ?? ""}
              onChange={(e) => selectTest(Number(e.target.value))}
              className="w-full sm:w-80 max-w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-cyan-500"
            >
              {tests.map((test) => (
                <option key={test.test_id} value={test.test_id}>{testLabel(test)}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {tests === null || (state === "loading" && !insights) ? (
        <p className="text-sm text-zinc-400" role="status">{A.loading}</p>
      ) : state === "error" ? (
        <p className="text-sm text-amber-300" role="alert">{A.loadFailed}</p>
      ) : tests.length === 0 || !insights ? (
        <p className="text-sm text-zinc-400">{A.noTests}</p>
      ) : (
        <div className="flex flex-col gap-8">
          {/* 후보 썸네일 - 누르면 아래에 그 후보의 상세가 나온다 */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3" role="tablist" aria-label={A.candidate}>
            {insights.variations.map((v) => {
              const active = v.id === selectedId;
              return (
                <button
                  key={v.id}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  onClick={() => setSelectedId(v.id)}
                  className={`text-left rounded-xl border p-2 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 ${active ? "border-cyan-500 bg-cyan-950/20" : "border-zinc-800 hover:border-zinc-600"}`}
                >
                  <div className="relative w-full aspect-video rounded-lg overflow-hidden bg-zinc-800">
                    {v.thumbnail_image_url ? (
                      <img src={v.thumbnail_image_url} alt={v.name} className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-[11px] text-zinc-400">{t.common.noImage}</div>
                    )}
                    {v.is_live && (
                      <span className="absolute top-1.5 left-1.5 inline-flex items-center gap-1 text-[10px] font-bold bg-emerald-500 text-black px-1.5 py-0.5 rounded">
                        <Radio size={10} aria-hidden="true" /> {A.live}
                      </span>
                    )}
                    {v.is_winner && (
                      <span className="absolute top-1.5 right-1.5 inline-flex items-center gap-1 text-[10px] font-bold bg-amber-400 text-black px-1.5 py-0.5 rounded">
                        <Crown size={10} aria-hidden="true" /> {A.winner}
                      </span>
                    )}
                  </div>
                  <div className="mt-2 flex items-baseline justify-between gap-2">
                    <span className="text-xs font-bold text-zinc-200 truncate">{v.name}</span>
                    <span className="text-xs font-bold text-cyan-400 tabular-nums whitespace-nowrap">{formatNumber(v.vph, locale)} VPH</span>
                  </div>
                </button>
              );
            })}
          </div>

          {selected && (
            <div className="flex flex-col gap-5" role="tabpanel">
              <div>
                <h3 className="text-base font-bold text-white break-keep">{selected.title_text || A.noTitle}</h3>
                {selected.is_live && liveMinutes != null && (
                  <p className="mt-1 text-xs text-emerald-300 inline-flex items-center gap-1.5">
                    <Clock size={12} aria-hidden="true" /> {A.liveSince(liveMinutes)}
                  </p>
                )}
              </div>

              <dl className="grid grid-cols-3 gap-3">
                {[
                  { label: A.exposure, value: A.hours(selected.total_hours) },
                  { label: A.viewsGained, value: `+${formatNumber(selected.total_views_gained, locale)}` },
                  { label: A.vph, value: formatNumber(selected.vph, locale) },
                ].map((item) => (
                  <div key={item.label} className="rounded-xl bg-zinc-900/60 border border-zinc-800 p-3 min-w-0">
                    <dt className="text-[11px] text-zinc-400">{item.label}</dt>
                    <dd className="text-lg font-bold text-white tabular-nums truncate">{item.value}</dd>
                  </div>
                ))}
              </dl>

              <div>
                <h4 className="text-sm font-bold text-zinc-200 mb-2">{A.windowsTitle}</h4>
                {selected.windows.length === 0 ? (
                  <p className="text-sm text-zinc-400 break-keep">{A.noWindows}</p>
                ) : (
                  <div className="overflow-x-auto rounded-xl border border-zinc-800">
                    <table className="w-full text-sm">
                      <thead className="bg-zinc-900/80 text-zinc-400 text-xs">
                        <tr>
                          <th className="text-left font-medium px-3 py-2">{A.windowPeriod}</th>
                          <th className="text-right font-medium px-3 py-2">{A.windowHours}</th>
                          <th className="text-right font-medium px-3 py-2">{A.windowViews}</th>
                          <th className="text-right font-medium px-3 py-2">{A.windowVph}</th>
                        </tr>
                      </thead>
                      <tbody className="tabular-nums">
                        {selected.windows.map((w) => (
                          <tr key={`${w.start}-${w.end}`} className="border-t border-zinc-800/70">
                            <td className="px-3 py-2 whitespace-nowrap text-zinc-300">{formatWhen(w.start)} – {formatWhen(w.end)}</td>
                            <td className="px-3 py-2 text-right text-zinc-300">{A.hours(w.hours)}</td>
                            <td className="px-3 py-2 text-right text-zinc-300">+{formatNumber(w.views_gained, locale)}</td>
                            <td className="px-3 py-2 text-right font-bold text-cyan-400">{formatNumber(w.vph, locale)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* 시간대별 비교 - 모든 후보를 한눈에 */}
          <div>
            <h4 className="text-sm font-bold text-zinc-200 mb-1">{A.timeTitle}</h4>
            <p className="text-xs text-zinc-400 mb-3 break-keep">{A.timeNote}</p>
            <div className="overflow-x-auto rounded-xl border border-zinc-800">
              <table className="w-full text-sm">
                <thead className="bg-zinc-900/80 text-zinc-400 text-xs">
                  <tr>
                    <th className="text-left font-medium px-3 py-2">{A.candidate}</th>
                    {A.blocks.map((label) => (
                      <th key={label} className="text-right font-medium px-3 py-2 whitespace-nowrap">{label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="tabular-nums">
                  {blockRows.map((row) => (
                    <tr
                      key={row.id}
                      className={`border-t border-zinc-800/70 ${row.id === selectedId ? "bg-cyan-950/20" : ""}`}
                    >
                      <td className="px-3 py-2 font-bold text-zinc-200 whitespace-nowrap">{row.name}</td>
                      {row.cells.map((cell, i) => (
                        <td key={i} className="px-3 py-2 text-right whitespace-nowrap">
                          {cell.vph == null ? (
                            <span className="text-zinc-600">–</span>
                          ) : (
                            <>
                              <span className={cell.vph === bestInBlock[i] ? "font-bold text-cyan-400" : "text-zinc-200"}>
                                {formatNumber(cell.vph, locale)}
                              </span>
                              <span className="text-zinc-500 text-xs"> ({A.hours(cell.hours)})</span>
                            </>
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
