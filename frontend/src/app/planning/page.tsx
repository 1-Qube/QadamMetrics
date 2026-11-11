"use client";

import React, { useState, useEffect } from "react";
import { useApp } from "@/context/AppContext";
import { api } from "@/lib/api";
import { OptimizationResponse, AllocationItem } from "@/types";
import {
  Sliders,
  Play,
  RotateCcw,
  AlertTriangle,
  Info,
  CheckCircle2,
  TrendingUp,
  Loader2,
  ArrowRight,
} from "lucide-react";

export default function PlanningPage() {
  const { selectedDatasetId } = useApp();
  const [optData, setOptData] = useState<OptimizationResponse | null>(null);
  const [allocations, setAllocations] = useState<AllocationItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Flight Simulator Parameters
  const [totalHours, setTotalHours] = useState<number>(100);
  const [beta, setBeta] = useState<number>(0.15);
  const [transferTau, setTransferTau] = useState<number>(0.25);
  const [targetAccuracy, setTargetAccuracy] = useState<number>(0.75);
  const [maxChangeHours, setMaxChangeHours] = useState<number>(4);

  // Custom topic hours proposed by user
  const [proposedHours, setProposedHours] = useState<Record<string, number>>({});

  const runSimulation = (opts: { useDefaults?: boolean } = {}) => {
    if (!selectedDatasetId) return;
    setLoading(true);
    setError(null);

    const edited = !opts.useDefaults && Object.keys(proposedHours).length > 0;
    api.optimizeScenarios(
      opts.useDefaults
        ? { dataset_id: selectedDatasetId }
        : {
            dataset_id: selectedDatasetId,
            total_hours: totalHours,
            beta,
            transfer_tau: transferTau,
            target_accuracy: targetAccuracy,
            max_change_hours: maxChangeHours,
            proposed_hours: edited ? proposedHours : undefined,
          }
    )
      .then((res) => {
        setOptData(res);
        if (opts.useDefaults && typeof res.total_hours === "number") setTotalHours(res.total_hours);
      })
      .catch((err) => {
        setOptData(null);
        setError(err?.message || "Simulation failed");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (selectedDatasetId) {
      setProposedHours({});
      runSimulation({ useDefaults: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDatasetId]);

  const handleHourChange = (topicId: string, val: number) => {
    setProposedHours((prev) => {
      const next: Record<string, number> = { ...prev };
      // Seed every topic with its current hours on first edit so the backend receives a full plan.
      if (Object.keys(next).length === 0) optData?.comparison.forEach((c) => (next[c.topic_id] = c.current));
      next[topicId] = Number.isFinite(val) ? Math.max(0, val) : 0;
      return next;
    });
  };

  const handleReset = () => {
    setBeta(0.15);
    setTransferTau(0.25);
    setTargetAccuracy(0.75);
    setMaxChangeHours(4);
    setProposedHours({});
    runSimulation({ useDefaults: true });
  };

  const topicNames = new Map<string, string>();
  optData?.scenarios.forEach((s) => s.hours.forEach((h) => topicNames.set(h.topic_id, h.topic_name)));
  const comparison = (optData?.comparison || []).map((c) => ({
    topic_id: c.topic_id,
    topic_name: topicNames.get(c.topic_id) || c.topic_id,
    current: c.current,
    lp_hours: c.lp_priority ?? c.current,
    nl_hours: c.nl_diminishing_returns ?? c.current,
    nl_delta: Math.round(((c.nl_diminishing_returns ?? c.current) - c.current) * 10) / 10,
    objective_sensitive: c.objective_sensitive,
  }));
  const maxHours = Math.max(1, ...comparison.flatMap((c) => [c.current, c.lp_hours, c.nl_hours]));
  const sumProposed = comparison.reduce((sum, c) => sum + (proposedHours[c.topic_id] ?? c.current), 0);
  const userScenario = optData?.scenarios.find((s) => s.name === "user_proposed");
  const currentScenario = optData?.scenarios.find((s) => s.name === "current");

  return (
    <div className="max-w-[1400px] mx-auto space-y-8 pb-16">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight text-[#151515] font-sans">
            Curriculum Planning & Hour Flight Simulator
          </h1>
          <p className="text-sm text-[#70706B] mt-1">
            Mathematical optimization under explicit assumptions (linear HiGHS vs diminishing-returns SLSQP). Projections are exploratory scenarios, not promised learning gains.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <button
            onClick={handleReset}
            className="px-3.5 py-2 bg-[#FFFFFF] border border-[#E6E5E0] hover:bg-[#F3F2EE] text-[#151515] rounded-xl text-xs font-semibold transition cursor-pointer flex items-center gap-1.5"
          >
            <RotateCcw className="w-3.5 h-3.5 text-[#70706B]" />
            <span>Reset Defaults</span>
          </button>
          <button
            onClick={() => runSimulation()}
            disabled={loading}
            className="px-4 py-2 bg-[#151515] text-white hover:bg-[#252525] rounded-xl text-xs font-semibold transition cursor-pointer flex items-center gap-1.5"
          >
            {loading ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-[#C9F542]" />
            ) : (
              <Play className="w-3.5 h-3.5 text-[#C9F542] fill-current" />
            )}
            <span>Recalculate Scenarios</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-800 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Epistemic Limitation Banner */}
      <div className="p-4 bg-[#FAF9F6] border border-[#E6E5E0] rounded-xl text-xs text-[#70706B] flex items-start gap-3">
        <Info className="w-5 h-5 text-[#151515] shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-bold text-[#151515] block">
            Simulation Assumption Disclosure
          </span>
          <p className="leading-relaxed">
            {optData?.assumptions?.statement ||
              "No empirical hour-to-learning curve is fitted from student tests. Objective deltas are mathematical exploration indexes, not percentage-point test score gains."}
          </p>
          {optData?.sensitivity_note && (
            <p className="text-[11px] text-amber-800 bg-amber-50 px-2 py-1 rounded inline-block mt-1">
              {optData.sensitivity_note}
            </p>
          )}
        </div>
      </div>

      {/* Simulator Controls & Parameters Panel */}
      <div className="bg-[#FFFFFF] border border-[#E6E5E0] rounded-xl p-6 shadow-2xs">
        <div className="flex items-center gap-2 mb-6">
          <div className="w-1 h-4 bg-[#C9F542] rounded-full" />
          <h2 className="font-bold text-base text-[#151515]">Flight Simulator Parameters</h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-6">
          {/* Total Budget Hours */}
          <div className="space-y-2">
            <div className="flex justify-between text-xs">
              <span className="text-[#70706B] font-medium">Total Term Hours</span>
              <span className="font-mono font-bold text-[#151515]">{totalHours}h</span>
            </div>
            <input
              type="range"
              min="10"
              max="400"
              step="1"
              value={totalHours}
              onChange={(e) => setTotalHours(Number(e.target.value))}
              className="w-full accent-[#151515] cursor-pointer"
            />
            <span className="text-[10px] text-[#95958E] block">Fixed instructional budget constraint</span>
          </div>

          {/* Diminishing Beta */}
          <div className="space-y-2">
            <div className="flex justify-between text-xs">
              <span className="text-[#70706B] font-medium">Diminishing Beta (&beta;)</span>
              <span className="font-mono font-bold text-[#151515]">{beta.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0.05"
              max="0.50"
              step="0.05"
              value={beta}
              onChange={(e) => setBeta(Number(e.target.value))}
              className="w-full accent-[#151515] cursor-pointer"
            />
            <span className="text-[10px] text-[#95958E] block">Curvature of learning returns</span>
          </div>

          {/* Transfer Tau */}
          <div className="space-y-2">
            <div className="flex justify-between text-xs">
              <span className="text-[#70706B] font-medium">Prerequisite Transfer (&tau;)</span>
              <span className="font-mono font-bold text-[#151515]">{transferTau.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0.00"
              max="0.80"
              step="0.05"
              value={transferTau}
              onChange={(e) => setTransferTau(Number(e.target.value))}
              className="w-full accent-[#151515] cursor-pointer"
            />
            <span className="text-[10px] text-[#95958E] block">Upstream multiplier for prereq need</span>
          </div>

          {/* Target Accuracy */}
          <div className="space-y-2">
            <div className="flex justify-between text-xs">
              <span className="text-[#70706B] font-medium">Target Mastery</span>
              <span className="font-mono font-bold text-[#151515]">{Math.round(targetAccuracy * 100)}%</span>
            </div>
            <input
              type="range"
              min="0.50"
              max="0.95"
              step="0.05"
              value={targetAccuracy}
              onChange={(e) => setTargetAccuracy(Number(e.target.value))}
              className="w-full accent-[#151515] cursor-pointer"
            />
            <span className="text-[10px] text-[#95958E] block">Desired proficiency goalpost</span>
          </div>

          {/* Max Change Constraint */}
          <div className="space-y-2">
            <div className="flex justify-between text-xs">
              <span className="text-[#70706B] font-medium">Max Disruption Cap</span>
              <span className="font-mono font-bold text-[#151515]">&plusmn;{maxChangeHours}h</span>
            </div>
            <input
              type="range"
              min="1"
              max="15"
              step="1"
              value={maxChangeHours}
              onChange={(e) => setMaxChangeHours(Number(e.target.value))}
              className="w-full accent-[#151515] cursor-pointer"
            />
            <span className="text-[10px] text-[#95958E] block">Limits swing from current schedule</span>
          </div>
        </div>
      </div>

      {/* Scenario Comparison Table */}
      <div className="bg-[#FFFFFF] border border-[#E6E5E0] rounded-xl shadow-2xs overflow-hidden">
        <div className="p-6 pb-4 border-b border-[#E6E5E0] flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="font-bold text-base text-[#151515]">
              Scenario Comparison Matrix
            </h2>
            <p className="text-xs text-[#70706B] mt-0.5">
              Compare current allocations with Linear Priority (HiGHS) and Diminishing Returns (SLSQP).
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs font-mono">
            <span className="text-[#70706B]">Budget: {totalHours}h</span>
            <span className={Math.abs(sumProposed - totalHours) < 0.01 ? "text-[#4F7700]" : "text-red-700"}>
              Your plan: {sumProposed.toFixed(1)}h
            </span>
          </div>
        </div>

        {userScenario && (
          <div
            className={`mx-6 mt-4 p-3 rounded-lg text-xs border ${
              userScenario.status === "ok" ? "bg-[#FAF9F6] border-[#E6E5E0] text-[#151515]" : "bg-red-50 border-red-200 text-red-800"
            }`}
          >
            {userScenario.status === "ok" ? (
              <>
                <strong>Your plan was evaluated.</strong> Diminishing-returns objective:{" "}
                <span className="font-mono">{userScenario.objective?.hypothetical_diminishing_returns?.toFixed(3) ?? "—"}</span> vs current{" "}
                <span className="font-mono">{currentScenario?.objective?.hypothetical_diminishing_returns?.toFixed(3) ?? "—"}</span>. Higher is better
                under the stated assumptions; it is not a predicted score.
              </>
            ) : (
              <>
                <strong>Your plan was not evaluated:</strong> {(userScenario as any).message || userScenario.note}
              </>
            )}
          </div>
        )}

        {loading ? (
          <div className="py-20 text-center text-xs text-[#70706B]">
            <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2 text-[#151515]" />
            Solving convex SLSQP and linear HiGHS optimization programs...
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="bg-[#FAF9F6] border-b border-[#E6E5E0] text-[#70706B] font-mono uppercase text-[10px] tracking-wider">
                  <th className="py-3 px-4 font-semibold">Topic</th>
                  <th className="py-3 px-4 font-semibold">Current Hours</th>
                  <th className="py-3 px-4 font-semibold">Your Plan</th>
                  <th className="py-3 px-4 font-semibold">Linear HiGHS</th>
                  <th className="py-3 px-4 font-semibold">Diminishing SLSQP</th>
                  <th className="py-3 px-4 font-semibold">SLSQP Delta</th>
                  <th className="py-3 px-4 font-semibold">Sensitivity</th>
                  <th className="py-3 px-4 font-semibold">Visual Allocation Comparison</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F3F2EE]">
                {comparison.map((row) => {
                  const delta = row.nl_delta;
                  const sign = delta > 0 ? "+" : "";

                  return (
                    <tr key={row.topic_id} className="hover:bg-[#FAF9F6] transition">
                      <td className="py-3 px-4">
                        <span className="font-mono text-[10px] text-[#70706B] block">
                          {row.topic_id}
                        </span>
                        <span className="font-semibold text-[#151515]">{row.topic_name}</span>
                      </td>
                      <td className="py-3 px-4 font-mono text-[#70706B] font-medium">
                        {row.current.toFixed(1)}h
                      </td>
                      <td className="py-3 px-4">
                        <input
                          type="number"
                          min={0}
                          step={0.5}
                          aria-label={`Your hours for ${row.topic_name}`}
                          value={proposedHours[row.topic_id] ?? row.current}
                          onChange={(e) => handleHourChange(row.topic_id, Number(e.target.value))}
                          className="w-20 bg-[#FAF9F6] border border-[#E6E5E0] rounded-md px-2 py-1 font-mono text-xs focus:outline-none focus:border-[#151515]"
                        />
                      </td>
                      <td className="py-3 px-4 font-mono font-medium text-[#151515]">
                        {row.lp_hours.toFixed(1)}h
                      </td>
                      <td className="py-3 px-4 font-mono font-bold text-[#151515]">
                        {row.nl_hours.toFixed(1)}h
                      </td>
                      <td className="py-3 px-4 font-mono">
                        <span
                          className={`font-semibold ${
                            delta > 0
                              ? "text-[#4F7700]"
                              : delta < 0
                              ? "text-red-700"
                              : "text-[#70706B]"
                          }`}
                        >
                          {sign}
                          {delta}h
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        {row.objective_sensitive ? (
                          <span className="inline-flex items-center gap-1 text-[10px] text-amber-800 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded font-medium">
                            <AlertTriangle className="w-3 h-3 text-amber-600" />
                            <span>Objective-sensitive</span>
                          </span>
                        ) : (
                          <span className="text-[#95958E] font-mono text-[11px]">Stable</span>
                        )}
                      </td>
                      <td className="py-3 px-4 min-w-[200px]">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="text-[9px] font-mono text-[#95958E] w-12">Current:</span>
                            <div className="flex-1 h-1.5 bg-[#F3F2EE] rounded-sm overflow-hidden">
                              <div
                                className="h-full bg-[#D1D0C9] rounded-sm"
                                style={{ width: `${Math.min(100, (row.current / maxHours) * 100)}%` }}
                              />
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-[9px] font-mono text-[#151515] w-12 font-bold">
                              SLSQP:
                            </span>
                            <div className="flex-1 h-1.5 bg-[#F3F2EE] rounded-sm overflow-hidden">
                              <div
                                className={`h-full ${
                                  delta > 0 ? "bg-[#C9F542]" : "bg-[#182B49]"
                                } rounded-sm`}
                                style={{ width: `${Math.min(100, (row.nl_hours / maxHours) * 100)}%` }}
                              />
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
