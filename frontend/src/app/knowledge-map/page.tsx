"use client";

import React, { useState, useEffect, useMemo } from "react";
import { useApp } from "@/context/AppContext";
import { api } from "@/lib/api";
import { KnowledgeGraphResponse, KnowledgeNode, KnowledgeRisk } from "@/types";
import {
  Network,
  AlertTriangle,
  CheckCircle2,
  GitCommit,
  Info,
  ArrowRight,
  Plus,
  Sparkles,
  Loader2,
  Layers,
  ChevronRight,
} from "lucide-react";

export default function KnowledgeMapPage() {
  const { selectedDatasetId } = useApp();
  const [graphData, setGraphData] = useState<KnowledgeGraphResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedNode, setSelectedNode] = useState<KnowledgeNode | null>(null);
  const [inferring, setInferring] = useState(false);
  const [candidates, setCandidates] = useState<any[] | null>(null);

  // New Edge form state
  const [sourceId, setSourceId] = useState("");
  const [targetId, setTargetId] = useState("");
  const [addingEdge, setAddingEdge] = useState(false);
  const [edgeSuccess, setEdgeSuccess] = useState<string | null>(null);

  const loadGraph = () => {
    if (!selectedDatasetId) return;
    setLoading(true);
    api.getKnowledgeGraph(selectedDatasetId)
      .then((res) => {
        setGraphData(res);
        if (res.nodes.length > 0 && !selectedNode) {
          setSelectedNode(res.nodes[0]);
        }
      })
      .catch((err) => setError(err?.message || "Failed to load knowledge graph"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadGraph();
  }, [selectedDatasetId]);

  const handleInfer = async () => {
    if (!selectedDatasetId) return;
    setInferring(true);
    setCandidates(null);
    try {
      const res = await api.inferEdges(selectedDatasetId);
      setCandidates(res.candidates || []);
    } catch (err: any) {
      alert("Inference failed: " + err?.message);
    } finally {
      setInferring(false);
    }
  };

  const handleAddEdge = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDatasetId || !sourceId || !targetId || sourceId === targetId) return;
    setAddingEdge(true);
    setEdgeSuccess(null);
    try {
      await api.addEdge(selectedDatasetId, {
        prerequisite_topic_id: sourceId,
        dependent_topic_id: targetId,
        relation_status: "verified",
        notes: "Asserted via QadamMetrics Knowledge Map UI",
      });
      setEdgeSuccess(`Edge ${sourceId} → ${targetId} added successfully.`);
      setSourceId("");
      setTargetId("");
      loadGraph();
    } catch (err: any) {
      alert("Failed to add edge: " + err?.message);
    } finally {
      setAddingEdge(false);
    }
  };

  // Group nodes by depth for stratified DAG progression view
  const nodesByDepth = useMemo(() => {
    if (!graphData?.nodes) return {};
    const map: Record<number, KnowledgeNode[]> = {};
    graphData.nodes.forEach((n) => {
      const depth = n.depth ?? 0;
      if (!map[depth]) map[depth] = [];
      map[depth].push(n);
    });
    return map;
  }, [graphData]);

  const maxDepth = useMemo(() => {
    const depths = Object.keys(nodesByDepth).map(Number);
    return depths.length > 0 ? Math.max(...depths) : 0;
  }, [nodesByDepth]);

  return (
    <div className="max-w-[1400px] mx-auto space-y-8 pb-16">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight text-[#151515] font-sans">
            Knowledge Map & Prerequisite Graph
          </h1>
          <p className="text-sm text-[#70706B] mt-1">
            Topological progression of curriculum topics. Verified edges represent curated prerequisites; inferred edges highlight co-failure correlation.
          </p>
        </div>

        <button
          onClick={handleInfer}
          disabled={inferring}
          className="inline-flex items-center gap-2 px-4 py-2 bg-[#151515] text-white hover:bg-[#252525] rounded-xl text-xs font-semibold transition disabled:opacity-50 cursor-pointer self-start sm:self-auto"
        >
          {inferring ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin text-[#C9F542]" />
          ) : (
            <Sparkles className="w-3.5 h-3.5 text-[#C9F542]" />
          )}
          <span>Infer Co-Failure Candidates</span>
        </button>
      </div>

      {/* Cycle Warning Banner if DAG has cycles */}
      {graphData?.cycles && graphData.cycles.length > 0 && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-xs text-red-800 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
          <div>
            <span className="font-bold block">Curriculum Prerequisite Cycles Detected!</span>
            <p className="mt-0.5">
              A curriculum must be an acyclic directed graph (DAG). The following circular dependencies exist:
              {graphData.cycles.map((c, i) => (
                <span key={i} className="block font-mono text-[11px] mt-1">
                  • {c.join(" → ")} → {c[0]}
                </span>
              ))}
            </p>
          </div>
        </div>
      )}

      {/* Main Grid: Interactive Stratified Canvas on Left, Inspector & Hypotheses on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Interactive Stratified Knowledge Graph Canvas */}
        <div className="lg:col-span-2 bg-[#FFFFFF] border border-[#E6E5E0] rounded-xl p-6 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-6 pb-4 border-b border-[#F3F2EE]">
              <div className="flex items-center gap-2">
                <div className="w-1 h-4 bg-[#C9F542] rounded-full" />
                <h2 className="font-bold text-base text-[#151515]">
                  Topological Progression DAG
                </h2>
              </div>
              <div className="flex items-center gap-3 text-xs font-mono text-[#70706B]">
                <span>{graphData?.node_count || 0} nodes</span>
                <span>•</span>
                <span>{graphData?.verified_edge_count || 0} verified edges</span>
                {graphData?.inferred_edge_count ? (
                  <>
                    <span>•</span>
                    <span className="text-[#4F7700]">
                      {graphData.inferred_edge_count} inferred
                    </span>
                  </>
                ) : null}
              </div>
            </div>

            {loading ? (
              <div className="py-24 text-center text-xs text-[#70706B]">
                <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-[#151515]" />
                Building curriculum dependency graph...
              </div>
            ) : (
              /* Stratified Topological Progression Columns */
              <div className="overflow-x-auto py-4">
                <div className="flex items-start gap-8 min-w-[650px]">
                  {Array.from({ length: maxDepth + 1 }).map((_, depthIdx) => {
                    const depthNodes = nodesByDepth[depthIdx] || [];
                    return (
                      <div key={depthIdx} className="flex-1 space-y-4">
                        {/* Column Header */}
                        <div className="text-center pb-2 border-b border-[#E6E5E0]">
                          <span className="font-mono text-[10px] text-[#95958E] uppercase tracking-wider block">
                            Stage {depthIdx}
                          </span>
                          <span className="text-xs font-semibold text-[#151515]">
                            {depthIdx === 0
                              ? "Foundations"
                              : depthIdx === maxDepth
                              ? "Capstone"
                              : `Tier ${depthIdx}`}
                          </span>
                        </div>

                        {/* Nodes in this column */}
                        <div className="space-y-3">
                          {depthNodes.map((node) => {
                            const isSelected = selectedNode?.id === node.id;
                            const isWeak = node.status === "weak";
                            const isStrong = node.status === "strong";

                            return (
                              <div
                                key={node.id}
                                onClick={() => setSelectedNode(node)}
                                className={`p-3 rounded-xl border text-left transition-all duration-150 cursor-pointer relative shadow-2xs ${
                                  isSelected
                                    ? "bg-[#C9F542] border-[#C9F542] text-[#151515] shadow-md ring-2 ring-[#C9F542]/40"
                                    : isWeak
                                    ? "bg-[#FFFFFF] border-amber-300 hover:border-amber-500"
                                    : isStrong
                                    ? "bg-[#FFFFFF] border-[#182B49]/40 hover:border-[#182B49]"
                                    : "bg-[#FFFFFF] border-[#E6E5E0] hover:border-[#151515]"
                                }`}
                              >
                                <div className="flex items-center justify-between text-[10px] font-mono mb-1">
                                  <span className={isSelected ? "font-bold" : "text-[#70706B]"}>
                                    {node.id}
                                  </span>
                                  {node.accuracy !== null && (
                                    <span className="font-bold">
                                      {Math.round(node.accuracy * 100)}%
                                    </span>
                                  )}
                                </div>
                                <span
                                  className={`block text-xs font-semibold leading-tight line-clamp-2 ${
                                    isSelected ? "text-[#151515]" : "text-[#151515]"
                                  }`}
                                >
                                  {node.label}
                                </span>

                                <div className="flex items-center gap-1.5 mt-2 pt-2 border-t border-black/5 text-[10px] text-[#70706B]">
                                  <span>Imp: {node.importance}</span>
                                  <span>•</span>
                                  <span>Desc: {node.descendant_count}</span>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Graph Legend */}
          <div className="pt-4 border-t border-[#F3F2EE] flex flex-wrap items-center justify-between gap-3 text-xs text-[#70706B]">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-[#C9F542]" />
                <span>Selected Topic</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full border border-amber-300" />
                <span>Weak Performance</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full border border-[#182B49]" />
                <span>Strong Mastery</span>
              </span>
            </div>
            <span className="text-[11px] text-[#95958E]">
              Click any topic card to inspect prerequisite & dependent linkages
            </span>
          </div>
        </div>

        {/* Right Column: Node Inspector & Add Edge */}
        <div className="space-y-6">
          {/* Node Inspector Card */}
          {selectedNode ? (
            <div className="bg-[#FFFFFF] border border-[#E6E5E0] rounded-xl p-6 shadow-2xs space-y-4">
              <div className="pb-3 border-b border-[#E6E5E0]">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono text-xs text-[#70706B] font-bold">
                    {selectedNode.id}
                  </span>
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${
                      selectedNode.status === "weak"
                        ? "bg-[#C9F542] text-[#151515]"
                        : selectedNode.status === "strong"
                        ? "bg-[#182B49] text-white"
                        : "bg-[#F3F2EE] text-[#70706B]"
                    }`}
                  >
                    {selectedNode.status}
                  </span>
                </div>
                <h3 className="font-bold text-base text-[#151515]">{selectedNode.label}</h3>
              </div>

              {/* Metrics */}
              <div className="grid grid-cols-2 gap-2 text-center text-xs">
                <div className="p-2.5 bg-[#FAF9F6] border border-[#E6E5E0] rounded-lg">
                  <span className="text-[10px] text-[#70706B] block">Importance Weight</span>
                  <span className="font-bold text-sm text-[#151515]">
                    {selectedNode.importance}
                  </span>
                </div>
                <div className="p-2.5 bg-[#FAF9F6] border border-[#E6E5E0] rounded-lg">
                  <span className="text-[10px] text-[#70706B] block">Downstream Dependents</span>
                  <span className="font-bold text-sm text-[#151515]">
                    {selectedNode.descendant_count}
                  </span>
                </div>
              </div>

              {/* Verified Prerequisites list */}
              <div>
                <span className="font-semibold text-xs text-[#151515] block mb-1.5">
                  Verified Prerequisites ({selectedNode.verified_prerequisites.length}):
                </span>
                {selectedNode.verified_prerequisites.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5 font-mono text-xs">
                    {selectedNode.verified_prerequisites.map((p) => (
                      <span
                        key={p}
                        className="px-2 py-1 bg-[#FAF9F6] border border-[#E6E5E0] rounded text-[#151515]"
                      >
                        ← {p}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span className="text-xs text-[#95958E] italic">
                    Foundational entry topic (no prerequisites).
                  </span>
                )}
              </div>

              {/* Dependents list */}
              <div>
                <span className="font-semibold text-xs text-[#151515] block mb-1.5">
                  Direct Dependents ({selectedNode.dependents.length}):
                </span>
                {selectedNode.dependents.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5 font-mono text-xs">
                    {selectedNode.dependents.map((d) => (
                      <span
                        key={d}
                        className="px-2 py-1 bg-[#FAF9F6] border border-[#E6E5E0] rounded text-[#151515]"
                      >
                        → {d}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span className="text-xs text-[#95958E] italic">
                    Terminal topic (no downstream dependents).
                  </span>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-[#FFFFFF] border border-[#E6E5E0] rounded-xl p-6 text-center text-xs text-[#70706B]">
              Select a node in the DAG to inspect connections.
            </div>
          )}

          {/* Add Prerequisite Edge Form */}
          <div className="bg-[#FFFFFF] border border-[#E6E5E0] rounded-xl p-5 shadow-2xs">
            <span className="font-bold text-xs text-[#151515] block mb-3 uppercase tracking-wider">
              Add Verified Prerequisite Edge
            </span>

            <form onSubmit={handleAddEdge} className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[10px] text-[#70706B] mb-1">Prerequisite</label>
                  <select
                    value={sourceId}
                    onChange={(e) => setSourceId(e.target.value)}
                    required
                    className="w-full bg-[#FAF9F6] border border-[#E6E5E0] rounded-lg p-2 text-xs text-[#151515] outline-none"
                  >
                    <option value="">Select source</option>
                    {graphData?.nodes.map((n) => (
                      <option key={n.id} value={n.id}>
                        {n.id}: {n.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-[10px] text-[#70706B] mb-1">Dependent</label>
                  <select
                    value={targetId}
                    onChange={(e) => setTargetId(e.target.value)}
                    required
                    className="w-full bg-[#FAF9F6] border border-[#E6E5E0] rounded-lg p-2 text-xs text-[#151515] outline-none"
                  >
                    <option value="">Select target</option>
                    {graphData?.nodes.map((n) => (
                      <option key={n.id} value={n.id}>
                        {n.id}: {n.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {edgeSuccess && (
                <div className="p-2 bg-[#F4FCE3] border border-[#D4F754] rounded text-[11px] text-[#3A6000]">
                  {edgeSuccess}
                </div>
              )}

              <button
                type="submit"
                disabled={addingEdge}
                className="w-full py-2 bg-[#151515] text-white rounded-lg text-xs font-semibold hover:bg-[#333333] transition disabled:opacity-50 cursor-pointer flex items-center justify-center gap-1.5"
              >
                {addingEdge ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-[#C9F542]" />
                ) : (
                  <Plus className="w-3.5 h-3.5" />
                )}
                <span>Assert Verified Edge</span>
              </button>
            </form>
          </div>

          {/* Inferred Candidates Modal/Panel */}
          {candidates && (
            <div className="bg-[#FFFFFF] border border-[#E6E5E0] rounded-xl p-5 shadow-2xs space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-bold text-xs text-[#151515] uppercase tracking-wider">
                  Inferred Co-Failure Candidates ({candidates.length})
                </span>
                <span className="text-[10px] text-[#95958E] font-mono">phi &ge; 0.25</span>
              </div>
              <p className="text-[11px] text-[#70706B] leading-relaxed">
                Candidates are statistical co-failure associations. They are not saved as curriculum prerequisites until verified by a methodologist.
              </p>

              {candidates.length === 0 ? (
                <div className="text-xs text-[#70706B] italic">
                  No co-failure candidates met the Matthews correlation threshold (phi &ge; 0.25 with n &ge; 40).
                </div>
              ) : (
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {candidates.map((cand, i) => (
                    <div
                      key={i}
                      className="p-2.5 bg-[#FAF9F6] border border-[#E6E5E0] rounded-lg text-xs flex items-center justify-between"
                    >
                      <div>
                        <span className="font-bold text-[#151515] font-mono">
                          {cand.prerequisite_topic_id} → {cand.dependent_topic_id}
                        </span>
                        <span className="block text-[10px] text-[#70706B]">
                          phi: {cand.confidence.toFixed(3)} (n={cand.n_students})
                        </span>
                      </div>
                      <button
                        onClick={async () => {
                          if (!selectedDatasetId) return;
                          await api.addEdge(selectedDatasetId, {
                            prerequisite_topic_id: cand.prerequisite_topic_id,
                            dependent_topic_id: cand.dependent_topic_id,
                            relation_status: "verified",
                            notes: `Promoted from statistical inference (phi=${cand.confidence.toFixed(2)})`,
                          });
                          loadGraph();
                        }}
                        className="px-2 py-1 bg-[#151515] text-white rounded text-[10px] font-semibold hover:bg-[#333333] cursor-pointer"
                      >
                        Verify
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
