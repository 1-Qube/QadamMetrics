"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useApp } from "@/context/AppContext";
import { api } from "@/lib/api";
import {
  KnowledgeGraphResponse,
  KnowledgeNode,
  OptimizationResponse,
  RecommendationsResponse,
  TextbookComparisonResponse,
  TopicDiagnostic,
} from "@/types";
import { ArrowRight, Info, Send, Sparkles, Loader2, Upload, AlertTriangle } from "lucide-react";

const pct = (v: number | null | undefined, digits = 0) =>
  v === null || v === undefined ? "—" : `${(v * 100).toFixed(digits)}%`;

function SectionTitle({ children, action }: { children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between mb-5">
      <div className="flex items-center gap-2">
        <div className="w-1 h-4 bg-[#C9F542] rounded-full" />
        <h3 className="font-bold text-base text-[#151515]">{children}</h3>
      </div>
      {action}
    </div>
  );
}

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse bg-[#F0EFEA] rounded ${className}`} />;
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div className="py-8 text-center text-xs text-[#95958E]">{children}</div>;
}

/** Walk verified prerequisites backwards from a target, preferring the weakest parent. */
function buildChain(target: KnowledgeNode, byId: Map<string, KnowledgeNode>, maxLen = 4): KnowledgeNode[] {
  const chain: KnowledgeNode[] = [target];
  const seen = new Set([target.id]);
  let cur = target;
  while (chain.length < maxLen) {
    const parents = cur.verified_prerequisites.map((id) => byId.get(id)).filter((n): n is KnowledgeNode => !!n && !seen.has(n.id));
    if (!parents.length) break;
    parents.sort((a, b) => (a.accuracy ?? 1) - (b.accuracy ?? 1));
    cur = parents[0];
    seen.add(cur.id);
    chain.unshift(cur);
  }
  return chain;
}

export default function OverviewPage() {
  const router = useRouter();
  const { selectedDatasetId, selectedDataset, diagnostics, isLoadingDatasets, error: ctxError } = useApp();

  const [graph, setGraph] = useState<KnowledgeGraphResponse | null>(null);
  const [textbooks, setTextbooks] = useState<TextbookComparisonResponse | null>(null);
  const [opt, setOpt] = useState<OptimizationResponse | null>(null);
  const [recs, setRecs] = useState<RecommendationsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [failures, setFailures] = useState<string[]>([]);

  const [aiQuestion, setAiQuestion] = useState("");
  const [aiAnswer, setAiAnswer] = useState<{ text: string; provider: string; warnings: string[] } | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  useEffect(() => {
    if (!selectedDatasetId) return;
    let alive = true;
    setLoading(true);
    setGraph(null);
    setTextbooks(null);
    setOpt(null);
    setRecs(null);
    Promise.allSettled([
      api.getKnowledgeGraph(selectedDatasetId),
      api.compareTextbooks(selectedDatasetId),
      api.optimizeScenarios({ dataset_id: selectedDatasetId }),
      api.getRecommendations(selectedDatasetId),
    ]).then(([g, t, o, r]) => {
      if (!alive) return;
      const failed: string[] = [];
      if (g.status === "fulfilled") setGraph(g.value); else failed.push("knowledge graph");
      if (t.status === "fulfilled") setTextbooks(t.value); else failed.push("textbooks");
      if (o.status === "fulfilled") setOpt(o.value); else failed.push("hour scenarios");
      if (r.status === "fulfilled") setRecs(r.value); else failed.push("recommendations");
      setFailures(failed);
      setLoading(false);
    });
    return () => {
      alive = false;
    };
  }, [selectedDatasetId]);

  const topicNames = useMemo(() => {
    const m = new Map<string, string>();
    diagnostics?.topics.forEach((t) => m.set(t.topic_id, t.topic_name));
    graph?.nodes.forEach((n) => !m.has(n.id) && m.set(n.id, n.label));
    return m;
  }, [diagnostics, graph]);

  const struggling: TopicDiagnostic[] = useMemo(
    () =>
      (diagnostics?.topics || [])
        .filter((t) => t.accuracy !== null && t.status !== "insufficient_data" && t.status !== "not_assessed")
        .sort((a, b) => (a.accuracy ?? 0) - (b.accuracy ?? 0))
        .slice(0, 6),
    [diagnostics]
  );

  const chain = useMemo(() => {
    if (!graph?.nodes.length) return [];
    const byId = new Map(graph.nodes.map((n) => [n.id, n]));
    // Target: weak topic with the deepest verified prerequisite chain, then highest downstream risk.
    const weak = graph.nodes.filter((n) => n.status === "weak");
    if (!weak.length) return [];
    const scored = weak
      .map((n) => ({ n, chain: buildChain(n, byId) }))
      .sort((a, b) => b.chain.length - a.chain.length || (a.n.accuracy ?? 1) - (b.n.accuracy ?? 1));
    return scored[0].chain;
  }, [graph]);

  const currentHours = useMemo(() => {
    const current = opt?.scenarios.find((s) => s.name === "current");
    return current ? current.hours.reduce((sum, h) => sum + h.hours, 0) : null;
  }, [opt]);

  const decisions = useMemo(
    () =>
      (opt?.comparison || [])
        .filter((r) => r.nl_diminishing_returns !== null && Math.abs((r.nl_diminishing_returns ?? 0) - r.current) >= 0.5)
        .sort((a, b) => Math.abs((b.nl_diminishing_returns ?? 0) - b.current) - Math.abs((a.nl_diminishing_returns ?? 0) - a.current))
        .slice(0, 5),
    [opt]
  );

  const topIncrease = useMemo(() => {
    const ups = (opt?.comparison || [])
      .map((r) => ({ ...r, delta: (r.nl_diminishing_returns ?? r.current) - r.current }))
      .filter((r) => r.delta >= 0.5)
      .sort((a, b) => b.delta - a.delta);
    return ups[0] || null;
  }, [opt]);

  const topIncreaseRec = useMemo(
    () => (topIncrease ? recs?.recommendations.find((r) => r.topics.includes(topIncrease.topic_id) && r.rule_id !== "coverage") : null),
    [recs, topIncrease]
  );

  const topicStatus = (id: string) => diagnostics?.topics.find((t) => t.topic_id === id);

  const askAi = async (q?: string) => {
    const question = (q ?? aiQuestion).trim();
    if (!question || !selectedDatasetId) return;
    setAiLoading(true);
    setAiAnswer(null);
    try {
      const res = await api.explain({ dataset_id: selectedDatasetId, task: "diagnostics", question });
      setAiAnswer({ text: res.text, provider: res.provider, warnings: res.warnings || [] });
    } catch (err: any) {
      setAiAnswer({ text: `The copilot request failed: ${err?.message || "server error"}.`, provider: "error", warnings: [] });
    } finally {
      setAiLoading(false);
    }
  };

  if (ctxError) {
    return (
      <div className="max-w-xl mx-auto py-20 text-center">
        <AlertTriangle className="w-8 h-8 mx-auto mb-4 text-red-600" />
        <h2 className="text-xl font-bold mb-2">The analytics API is unreachable</h2>
        <p className="text-sm text-[#70706B]">{ctxError}</p>
        <p className="text-xs text-[#95958E] mt-3 font-mono">Expected at {process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}</p>
      </div>
    );
  }

  if (!selectedDatasetId && !isLoadingDatasets) {
    return (
      <div className="max-w-2xl mx-auto py-20">
        <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight mb-3">Curriculum intelligence</h1>
        <p className="text-[#70706B] mb-10">Turn assessment data into better teaching decisions.</p>
        <div className="border border-[#E6E5E0] bg-white rounded-xl p-8">
          <h2 className="font-bold text-lg mb-2">No assessment data yet</h2>
          <p className="text-sm text-[#70706B] leading-relaxed mb-6">
            Upload a student item-response CSV from your school or district. Every figure on this dashboard is computed from that file — nothing is pre-filled.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link href="/data" className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#151515] text-white rounded-lg text-sm font-semibold hover:bg-[#2a2a2a]">
              <Upload className="w-4 h-4 text-[#C9F542]" />
              Import assessment data
            </Link>
            <Link href="/data" className="inline-flex items-center gap-2 px-5 py-2.5 border border-[#E6E5E0] rounded-lg text-sm font-semibold hover:bg-[#F3F2EE]">
              Open the synthetic demo
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const ov = diagnostics?.overview;
  const cov = diagnostics?.coverage;

  return (
    <div className="max-w-[1400px] mx-auto space-y-8 pb-16">
      <div>
        <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight text-[#151515] mb-2">Curriculum intelligence</h1>
        <p className="text-base text-[#70706B]">Turn assessment data into better teaching decisions.</p>
      </div>

      {selectedDataset?.is_synthetic && (
        <div className="p-3 border border-amber-200 bg-amber-50 rounded-lg text-xs text-amber-900 flex items-center gap-2">
          <Info className="w-4 h-4 shrink-0" />
          This dataset is generated demonstration data, not real students. Import your own records on the{" "}
          <Link href="/data" className="underline font-semibold">Data</Link> page.
        </div>
      )}

      {failures.length > 0 && (
        <div className="p-3 border border-red-200 bg-red-50 rounded-lg text-xs text-red-800">
          Some sections could not be loaded from the API: {failures.join(", ")}.
        </div>
      )}

      {/* KPIs — all from /api/analytics/topics and /api/optimization/scenarios */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 border border-[#E6E5E0] bg-white rounded-xl divide-y sm:divide-y-0 sm:divide-x divide-[#E6E5E0]">
        {[
          {
            value: ov ? ov.students.toLocaleString() : null,
            label: "Students",
            sub: ov ? `${ov.schools} schools · ${ov.responses.toLocaleString()} responses` : null,
          },
          {
            value: cov ? `${cov.assessed_topics}` : null,
            label: "Topics tracked",
            sub: cov ? `${cov.topics_meeting_minimum_n} with n ≥ ${diagnostics?.min_students}` : null,
          },
          {
            value: ov ? pct(ov.mean_student_topic_credit, 1) : null,
            label: "Average mastery",
            sub: ov ? `${ov.weak_topics} weak · ${ov.strong_topics} strong topics` : null,
          },
          {
            value: currentHours !== null ? `${Math.round(currentHours)}h` : loading ? null : "—",
            label: "Teaching time",
            sub: currentHours !== null ? "Current plan, all topics" : loading ? null : "No hour plan uploaded",
          },
        ].map((k) => (
          <div key={k.label} className="p-5">
            {k.value === null ? <Skeleton className="h-9 w-24 mb-2" /> : <div className="text-3xl font-extrabold tracking-tight">{k.value}</div>}
            <div className="text-xs font-medium text-[#151515] mt-1">{k.label}</div>
            {k.sub === null ? <Skeleton className="h-3 w-32 mt-1.5" /> : <div className="text-[11px] text-[#95958E] mt-0.5">{k.sub}</div>}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Struggling topics */}
        <section className="bg-white border border-[#E6E5E0] rounded-xl p-6">
          <SectionTitle
            action={
              <Link href="/topics" className="text-xs font-medium text-[#70706B] hover:text-[#151515] flex items-center gap-1">
                View details <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            }
          >
            Where students are struggling
          </SectionTitle>
          {!diagnostics ? (
            <div className="space-y-4">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-7" />)}</div>
          ) : struggling.length === 0 ? (
            <Empty>No topic has enough students for a classification yet.</Empty>
          ) : (
            <>
              <div className="space-y-3.5">
                {struggling.map((t) => {
                  const color = t.status === "weak" ? "bg-[#C9F542]" : t.status === "strong" ? "bg-[#182B49]" : "bg-[#D1D0C9]";
                  return (
                    <button
                      key={t.topic_id}
                      onClick={() => router.push(`/topics?topic=${encodeURIComponent(t.topic_id)}`)}
                      className="w-full text-left group"
                      title={`95% CI ${pct(t.ci_low)}–${pct(t.ci_high)}, n=${t.n_students}`}
                    >
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="font-medium text-[#151515] group-hover:underline truncate">{t.topic_name}</span>
                        <span className="font-semibold font-mono">{pct(t.accuracy)}</span>
                      </div>
                      <div className="relative w-full h-3 bg-[#F3F2EE] rounded-sm overflow-hidden">
                        <div className={`h-full ${color} rounded-sm`} style={{ width: `${Math.max(2, (t.accuracy ?? 0) * 100)}%` }} />
                        {t.ci_low !== null && t.ci_high !== null && (
                          <div
                            className="absolute top-1/2 h-px bg-[#151515]/50"
                            style={{ left: `${t.ci_low * 100}%`, width: `${(t.ci_high - t.ci_low) * 100}%` }}
                          />
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
              <div className="mt-5 pt-3 border-t border-[#F3F2EE] flex justify-between text-[11px] text-[#95958E] font-mono">
                <span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span>
              </div>
              <div className="mt-2 flex gap-4 text-[11px] text-[#70706B]">
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 bg-[#C9F542] rounded-sm" />Weak</span>
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 bg-[#D1D0C9] rounded-sm" />Inconclusive</span>
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 bg-[#182B49] rounded-sm" />Strong</span>
                <span className="ml-auto">Line = 95% CI</span>
              </div>
            </>
          )}
        </section>

        {/* Learning progression — derived from the verified prerequisite graph */}
        <section className="bg-white border border-[#E6E5E0] rounded-xl p-6 flex flex-col">
          <SectionTitle>Learning progression</SectionTitle>
          {!graph ? (
            <Skeleton className="h-40" />
          ) : chain.length === 0 ? (
            <Empty>No weak topic with verified prerequisites. Add prerequisite edges on the Knowledge Map.</Empty>
          ) : (
            <div className="flex-1 flex items-center">
              <div className="w-full flex items-start justify-between py-6">
                {chain.map((n, i) => {
                  const last = i === chain.length - 1;
                  const weak = n.status === "weak";
                  return (
                    <React.Fragment key={n.id}>
                      <button
                        onClick={() => router.push(`/topics?topic=${encodeURIComponent(n.id)}`)}
                        className="flex flex-col items-center group w-24"
                        title={`${n.label}: ${pct(n.accuracy)} mastery, ${n.descendant_count} downstream topics`}
                      >
                        <div
                          className={`w-14 h-14 rounded-full flex items-center justify-center font-mono font-bold text-xs border transition ${
                            last
                              ? "bg-[#C9F542] border-[#C9F542] ring-4 ring-[#F4FCE3]"
                              : weak
                              ? "bg-white border-[#C9F542] border-2 group-hover:border-[#151515]"
                              : "bg-white border-[#E6E5E0] group-hover:border-[#151515]"
                          }`}
                        >
                          {pct(n.accuracy)}
                        </div>
                        <span className="mt-3 text-xs font-medium text-[#151515] text-center leading-tight">{n.label}</span>
                        <span className="text-[10px] text-[#95958E] font-mono mt-0.5">{n.status ?? "—"}</span>
                      </button>
                      {!last && <div className="flex-1 mt-7 h-px bg-[#D1D0C9] relative"><span className="absolute -right-1 -top-[5px] text-[#B3B2AA] text-[10px]">▶</span></div>}
                    </React.Fragment>
                  );
                })}
              </div>
            </div>
          )}
          <div className="flex items-center justify-between text-xs text-[#70706B] pt-4 border-t border-[#F3F2EE]">
            <span>Verified prerequisite chain into the weakest bottleneck</span>
            <Link href="/knowledge-map" className="font-medium hover:text-[#151515] flex items-center gap-1">
              Full knowledge map <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
        </section>
      </div>

      {/* Curriculum decisions */}
      <section className="bg-white border border-[#E6E5E0] rounded-xl p-6">
        <SectionTitle
          action={
            <Link href="/planning" className="text-xs font-medium text-[#70706B] hover:text-[#151515] flex items-center gap-1">
              Open planner <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          }
        >
          Curriculum decisions
        </SectionTitle>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 overflow-x-auto">
            {!opt ? (
              loading ? <Skeleton className="h-40" /> : <Empty>No hour plan is attached to this dataset. Upload an allocations CSV to enable scenarios.</Empty>
            ) : decisions.length === 0 ? (
              <Empty>The diminishing-returns scenario keeps the current plan within ±0.5 h for every topic.</Empty>
            ) : (
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-[#E6E5E0] text-[#70706B] font-mono uppercase tracking-wider text-[10px]">
                    <th className="py-2.5 font-semibold">Topic</th>
                    <th className="py-2.5 font-semibold">Current</th>
                    <th className="py-2.5 font-semibold">Scenario</th>
                    <th className="py-2.5 font-semibold">Difference</th>
                    <th className="py-2.5 font-semibold">Evidence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#F3F2EE]">
                  {decisions.map((r) => {
                    const d = (r.nl_diminishing_returns ?? r.current) - r.current;
                    const t = topicStatus(r.topic_id);
                    return (
                      <tr key={r.topic_id} className="hover:bg-[#FAF9F6]">
                        <td className="py-3 font-medium">{topicNames.get(r.topic_id) || r.topic_id}</td>
                        <td className="py-3 font-mono text-[#70706B]">{r.current.toFixed(1)}h</td>
                        <td className="py-3 font-mono font-semibold">{(r.nl_diminishing_returns ?? 0).toFixed(1)}h</td>
                        <td className={`py-3 font-mono font-semibold ${d > 0 ? "text-[#4F7700]" : "text-[#70706B]"}`}>
                          {d > 0 ? "+" : ""}{d.toFixed(1)}h
                          {r.objective_sensitive && <span className="ml-1.5 text-[10px] text-amber-700" title="Linear and diminishing-returns scenarios disagree">⚠</span>}
                        </td>
                        <td className="py-3 text-[#70706B]">
                          {t ? `${t.status.replace("_", " ")} · ${pct(t.accuracy)} · n=${t.n_students}` : "not assessed"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
          <div className="lg:border-l lg:border-[#E6E5E0] lg:pl-8">
            <span className="inline-block bg-[#C9F542] text-[#151515] text-[11px] font-bold px-2.5 py-1 rounded-full mb-4">Recommended adjustment</span>
            {!opt ? (
              loading ? <Skeleton className="h-24" /> : <p className="text-xs text-[#95958E]">Requires an hour plan.</p>
            ) : topIncrease ? (
              <>
                <div className="text-4xl font-extrabold tracking-tight mb-1">+{topIncrease.delta.toFixed(1)} teaching hours</div>
                <div className="text-sm font-semibold mb-2">{topicNames.get(topIncrease.topic_id) || topIncrease.topic_id}</div>
                <p className="text-xs text-[#70706B] leading-relaxed">
                  {topIncreaseRec?.recommended_action || "Largest increase in the diminishing-returns scenario."}
                </p>
                <p className="text-[10px] text-[#95958E] mt-3">Hypothetical scenario — not a predicted score gain.</p>
              </>
            ) : (
              <p className="text-xs text-[#70706B]">No topic gains time in the current scenario.</p>
            )}
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Textbooks */}
        <section className="lg:col-span-2 bg-white border border-[#E6E5E0] rounded-xl p-6">
          <SectionTitle
            action={
              <Link href="/textbooks" className="text-xs font-medium text-[#70706B] hover:text-[#151515] flex items-center gap-1">
                Full analysis <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            }
          >
            Textbook comparison
          </SectionTitle>
          {!textbooks ? (
            loading ? <Skeleton className="h-24" /> : <Empty>Textbook comparison unavailable.</Empty>
          ) : textbooks.structural_comparison.length === 0 ? (
            <Empty>No textbooks uploaded. Add PDF or text files on the Textbooks page.</Empty>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
              <div className="space-y-3.5">
                {textbooks.structural_comparison.map((tb) => {
                  const top = tb.material_id === textbooks.highest_structural_coverage;
                  return (
                    <div key={tb.material_id}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="font-medium truncate max-w-[220px]">{tb.title || tb.material_id}</span>
                        <span className="font-semibold font-mono">{pct(tb.curriculum_coverage_ratio)}</span>
                      </div>
                      <div className="w-full h-2.5 bg-[#F3F2EE] rounded-sm overflow-hidden">
                        <div className={`h-full ${top ? "bg-[#182B49]" : "bg-[#D1D0C9]"} rounded-sm`} style={{ width: `${(tb.curriculum_coverage_ratio ?? 0) * 100}%` }} />
                      </div>
                      <div className="text-[10px] text-[#95958E] mt-1 font-mono">
                        {tb.counts.exercise} exercises · {tb.counts.example} examples · {tb.chapter_count} chapters
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="p-4 bg-[#FAF9F6] border border-[#E6E5E0] rounded-lg text-xs text-[#70706B] space-y-2">
                <div className="flex items-start gap-2 text-[#151515] font-medium">
                  <Info className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>
                    {textbooks.highest_structural_coverage
                      ? `${textbooks.structural_comparison.find((t) => t.material_id === textbooks.highest_structural_coverage)?.title || textbooks.highest_structural_coverage} covers the most curriculum topics.`
                      : "Only one textbook is available."}
                  </span>
                </div>
                <p className="text-[11px] text-[#95958E] leading-relaxed">{textbooks.structural_statement}</p>
              </div>
            </div>
          )}
        </section>

        {/* AI Methodologist */}
        <section className="bg-white border border-[#E6E5E0] rounded-xl p-5 flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4" />
              <span className="font-bold text-xs uppercase tracking-wider">AI Methodologist</span>
            </div>
            {aiAnswer && <span className="text-[10px] text-[#95958E] font-mono">{aiAnswer.provider}</span>}
          </div>
          {aiAnswer && (
            <div className="p-3 bg-[#FAF9F6] border border-[#E6E5E0] rounded-lg text-xs leading-relaxed mb-3 max-h-56 overflow-y-auto whitespace-pre-line">
              {aiAnswer.text}
              {aiAnswer.warnings.length > 0 && <div className="mt-2 text-[10px] text-amber-700">{aiAnswer.warnings.join(" ")}</div>}
            </div>
          )}
          <div className="mt-auto">
            <div className="relative flex items-center">
              <input
                value={aiQuestion}
                onChange={(e) => setAiQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && askAi()}
                placeholder="Ask QadamMetrics a question..."
                aria-label="Ask the AI methodologist"
                className="w-full bg-[#FAF9F6] border border-[#E6E5E0] rounded-lg pl-3 pr-10 py-2.5 text-xs placeholder-[#95958E] focus:outline-none focus:border-[#151515]"
              />
              <button
                onClick={() => askAi()}
                disabled={aiLoading || !aiQuestion.trim()}
                aria-label="Send question"
                className="absolute right-1.5 w-7 h-7 bg-[#151515] text-white rounded-md flex items-center justify-center hover:bg-[#333] disabled:opacity-40"
              >
                {aiLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin text-[#C9F542]" /> : <Send className="w-3.5 h-3.5" />}
              </button>
            </div>
            {struggling[0] && (
              <button
                onClick={() => {
                  const q = `Why are students struggling with ${struggling[0].topic_name.toLowerCase()}?`;
                  setAiQuestion(q);
                  askAi(q);
                }}
                className="mt-3 text-[11px] text-[#70706B] hover:text-[#151515] text-left"
              >
                Try: <span className="italic underline">“Why are students struggling with {struggling[0].topic_name.toLowerCase()}?”</span>
              </button>
            )}
            <p className="text-[10px] text-[#95958E] mt-2">Answers are restricted to numbers computed by the analytics engine.</p>
          </div>
        </section>
      </div>
    </div>
  );
}
