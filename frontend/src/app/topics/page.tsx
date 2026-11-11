"use client";

import React, { useState, useEffect, useMemo } from "react";
import { useApp } from "@/context/AppContext";
import { api } from "@/lib/api";
import { DiagnosticsResponse, TopicDiagnostic, TopicStatus } from "@/types";
import {
  Search,
  Filter,
  AlertCircle,
  CheckCircle2,
  HelpCircle,
  ArrowUpDown,
  X,
  School,
  GraduationCap,
  TrendingDown,
  TrendingUp,
  Loader2,
  Info,
} from "lucide-react";

export default function TopicsPage() {
  const { selectedDatasetId } = useApp();
  const [data, setData] = useState<DiagnosticsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [gradeFilter, setGradeFilter] = useState<string>("all");
  const [minStudents, setMinStudents] = useState<number>(30);

  // Selected topic detail modal
  const [activeTopic, setActiveTopic] = useState<TopicDiagnostic | null>(null);
  const [activeTopicDetail, setActiveTopicDetail] = useState<any | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    if (!selectedDatasetId) return;
    setLoading(true);
    setError(null);
    api.getTopics(selectedDatasetId, minStudents)
      .then((res) => {
        setData(res);
        const wanted = new URLSearchParams(window.location.search).get("topic");
        const match = wanted ? res.topics.find((t) => t.topic_id === wanted) : undefined;
        if (match) handleSelectTopic(match);
      })
      .catch((err) => setError(err?.message || "Failed to load topics"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDatasetId, minStudents]);

  const handleSelectTopic = async (topic: TopicDiagnostic) => {
    setActiveTopic(topic);
    if (!selectedDatasetId) return;
    setLoadingDetail(true);
    try {
      const res = await api.getTopicDetail(topic.topic_id, selectedDatasetId, minStudents);
      setActiveTopicDetail(res);
    } catch {
      setActiveTopicDetail(null);
    } finally {
      setLoadingDetail(false);
    }
  };

  // Filtered topics
  const filteredTopics = useMemo(() => {
    if (!data?.topics) return [];
    return data.topics.filter((topic) => {
      const matchesSearch =
        topic.topic_name.toLowerCase().includes(search.toLowerCase()) ||
        topic.topic_id.toLowerCase().includes(search.toLowerCase());
      const matchesStatus =
        statusFilter === "all" || topic.status === statusFilter;
      const matchesGrade =
        gradeFilter === "all" ||
        (topic.grade_levels && topic.grade_levels.includes(Number(gradeFilter)));
      return matchesSearch && matchesStatus && matchesGrade;
    });
  }, [data, search, statusFilter, gradeFilter]);

  // Available grade levels
  const availableGrades = useMemo(() => {
    if (!data?.topics) return [];
    const grades = new Set<number>();
    data.topics.forEach((t) => t.grade_levels?.forEach((g) => grades.add(g)));
    return Array.from(grades).sort((a, b) => a - b);
  }, [data]);

  return (
    <div className="max-w-[1400px] mx-auto space-y-8 pb-16">
      {/* Header */}
      <div>
        <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight text-[#151515] font-sans">
          Topics & Curriculum Performance
        </h1>
        <p className="text-sm text-[#70706B] mt-1">
          Rigorous conservative classification: topics are labeled weak or strong only when sample sizes and Student-t intervals allow it.
        </p>
      </div>

      {/* Filters Bar */}
      <div className="bg-[#FFFFFF] border border-[#E6E5E0] rounded-xl p-4 shadow-2xs flex flex-wrap items-center justify-between gap-4">
        {/* Search Input */}
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 text-[#95958E] absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search topic by name or ID (e.g. Factoring, T06)..."
            className="w-full bg-[#FAF9F6] border border-[#E6E5E0] rounded-lg pl-9 pr-3 py-2 text-xs text-[#151515] focus:outline-none focus:border-[#151515]"
          />
        </div>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Status Filter */}
          <div className="flex items-center gap-2 text-xs">
            <span className="text-[#70706B] font-medium">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-[#FAF9F6] border border-[#E6E5E0] rounded-lg px-2.5 py-1.5 text-xs text-[#151515] font-medium cursor-pointer outline-none"
            >
              <option value="all">All Classifications</option>
              <option value="weak">Weak (CI High &lt; 0.60)</option>
              <option value="strong">Strong (CI Low &gt;= 0.75)</option>
              <option value="inconclusive">Inconclusive</option>
              <option value="insufficient_data">Insufficient Data (&lt; {minStudents})</option>
              <option value="not_assessed">Not Assessed</option>
            </select>
          </div>

          {/* Grade Filter */}
          {availableGrades.length > 0 && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-[#70706B] font-medium">Grade:</span>
              <select
                value={gradeFilter}
                onChange={(e) => setGradeFilter(e.target.value)}
                className="bg-[#FAF9F6] border border-[#E6E5E0] rounded-lg px-2.5 py-1.5 text-xs text-[#151515] font-medium cursor-pointer outline-none"
              >
                <option value="all">All Grades</option>
                {availableGrades.map((g) => (
                  <option key={g} value={g}>
                    Grade {g}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Min Students Slider / Selector */}
          <div className="flex items-center gap-2 text-xs pl-2 border-l border-[#E6E5E0]">
            <span className="text-[#70706B]">Threshold n:</span>
            <select
              value={minStudents}
              onChange={(e) => setMinStudents(Number(e.target.value))}
              className="bg-[#FAF9F6] border border-[#E6E5E0] rounded-lg px-2 py-1.5 text-xs text-[#151515] font-mono cursor-pointer outline-none"
            >
              <option value="15">15</option>
              <option value="30">30 (Default)</option>
              <option value="50">50</option>
              <option value="100">100</option>
            </select>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-800">{error}</div>
      )}

      {/* Main Table */}
      <div className="bg-[#FFFFFF] border border-[#E6E5E0] rounded-xl shadow-2xs overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-xs text-[#70706B]">
            <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2 text-[#151515]" />
            Evaluating student response credit and intervals...
          </div>
        ) : filteredTopics.length === 0 ? (
          <div className="py-16 text-center text-xs text-[#70706B]">
            No curriculum topics match the current filter criteria.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="bg-[#FAF9F6] border-b border-[#E6E5E0] text-[#70706B] font-mono uppercase text-[10px] tracking-wider">
                  <th className="py-3 px-4 font-semibold">ID</th>
                  <th className="py-3 px-4 font-semibold">Topic Name</th>
                  <th className="py-3 px-4 font-semibold">Classification</th>
                  <th className="py-3 px-4 font-semibold">Mean Accuracy</th>
                  <th className="py-3 px-4 font-semibold">95% Student-t CI</th>
                  <th className="py-3 px-4 font-semibold">Difficulty Index</th>
                  <th className="py-3 px-4 font-semibold">Sample (Students / Items)</th>
                  <th className="py-3 px-4 font-semibold">Disparity Flags</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F3F2EE]">
                {filteredTopics.map((topic) => {
                  const pct =
                    topic.accuracy !== null ? Math.round(topic.accuracy * 100) : null;
                  const ciLow =
                    topic.ci_low !== null ? Math.round(topic.ci_low * 100) : null;
                  const ciHigh =
                    topic.ci_high !== null ? Math.round(topic.ci_high * 100) : null;

                  const hasDisparity =
                    topic.flags && topic.flags.includes("inconsistent_across_schools");

                  return (
                    <tr
                      key={topic.topic_id}
                      onClick={() => handleSelectTopic(topic)}
                      className="hover:bg-[#FAF9F6] transition cursor-pointer group"
                    >
                      <td className="py-3 px-4 font-mono font-medium text-[#70706B] group-hover:text-[#151515]">
                        {topic.topic_id}
                      </td>
                      <td className="py-3 px-4 font-semibold text-[#151515]">
                        {topic.topic_name}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider border ${
                            topic.status === "weak"
                              ? "bg-[#C9F542] text-[#151515] border-[#C9F542]"
                              : topic.status === "strong"
                              ? "bg-[#182B49] text-white border-[#182B49]"
                              : topic.status === "inconclusive"
                              ? "bg-[#F3F2EE] text-[#70706B] border-[#E6E5E0]"
                              : "bg-gray-100 text-gray-500 border-gray-200"
                          }`}
                        >
                          {topic.status === "weak" && (
                            <span className="w-1.5 h-1.5 rounded-full bg-[#151515]" />
                          )}
                          <span>{topic.status.replace("_", " ")}</span>
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono font-bold text-[#151515]">
                        {pct !== null ? `${pct}%` : "—"}
                      </td>
                      <td className="py-3 px-4 font-mono text-[11px] text-[#70706B]">
                        {ciLow !== null && ciHigh !== null ? `[${ciLow}%, ${ciHigh}%]` : "—"}
                      </td>
                      <td className="py-3 px-4 font-mono text-[#70706B]">
                        {topic.difficulty_index !== null
                          ? topic.difficulty_index.toFixed(2)
                          : "—"}
                      </td>
                      <td className="py-3 px-4 text-[#70706B]">
                        <span className="font-semibold text-[#151515]">{topic.n_students}</span>{" "}
                        students / {topic.n_items} items
                      </td>
                      <td className="py-3 px-4">
                        {hasDisparity ? (
                          <span className="inline-flex items-center gap-1 text-[10px] text-amber-800 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-md font-medium">
                            <AlertCircle className="w-3 h-3 text-amber-600" />
                            <span>Inconsistent across schools</span>
                          </span>
                        ) : (
                          <span className="text-[#95958E]">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Slide-out Topic Detail Modal / Drawer */}
      {activeTopic && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-[#FFFFFF] border border-[#E6E5E0] rounded-2xl max-w-2xl w-full p-6 shadow-xl space-y-6 max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex items-start justify-between pb-4 border-b border-[#E6E5E0]">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono text-xs text-[#70706B]">{activeTopic.topic_id}</span>
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${
                      activeTopic.status === "weak"
                        ? "bg-[#C9F542] text-[#151515]"
                        : activeTopic.status === "strong"
                        ? "bg-[#182B49] text-white"
                        : "bg-[#F3F2EE] text-[#70706B]"
                    }`}
                  >
                    {activeTopic.status}
                  </span>
                </div>
                <h2 className="text-xl font-bold text-[#151515]">{activeTopic.topic_name}</h2>
              </div>
              <button
                onClick={() => setActiveTopic(null)}
                className="w-8 h-8 rounded-lg hover:bg-[#F3F2EE] flex items-center justify-center text-[#70706B] hover:text-[#151515] transition cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Explanation Quote */}
            <div className="p-4 bg-[#FAF9F6] border border-[#E6E5E0] rounded-xl text-xs text-[#151515] leading-relaxed">
              <span className="font-semibold block text-[#70706B] text-[10px] uppercase font-mono mb-1">
                Engine Diagnosis
              </span>
              {activeTopic.explanation}
            </div>

            {/* KPI Breakdown */}
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="p-3 bg-[#FAF9F6] rounded-xl border border-[#E6E5E0]">
                <span className="text-[10px] text-[#70706B] block">Mean Credit</span>
                <span className="text-xl font-extrabold text-[#151515] font-mono">
                  {activeTopic.accuracy !== null
                    ? `${Math.round(activeTopic.accuracy * 100)}%`
                    : "—"}
                </span>
              </div>
              <div className="p-3 bg-[#FAF9F6] rounded-xl border border-[#E6E5E0]">
                <span className="text-[10px] text-[#70706B] block">95% Student-t CI</span>
                <span className="text-sm font-bold text-[#151515] font-mono">
                  {activeTopic.ci_low !== null && activeTopic.ci_high !== null
                    ? `[${Math.round(activeTopic.ci_low * 100)}%, ${Math.round(activeTopic.ci_high * 100)}%]`
                    : "—"}
                </span>
              </div>
              <div className="p-3 bg-[#FAF9F6] rounded-xl border border-[#E6E5E0]">
                <span className="text-[10px] text-[#70706B] block">Difficulty Index</span>
                <span className="text-xl font-extrabold text-[#151515] font-mono">
                  {activeTopic.difficulty_index !== null
                    ? activeTopic.difficulty_index.toFixed(2)
                    : "—"}
                </span>
              </div>
            </div>

            {/* School Disparity Breakdown */}
            {activeTopicDetail?.by_school && activeTopicDetail.by_school.length > 0 && (
              <div className="space-y-3">
                <span className="font-bold text-xs text-[#151515] flex items-center gap-1.5">
                  <School className="w-3.5 h-3.5 text-[#70706B]" />
                  <span>Performance across schools</span>
                </span>
                <div className="space-y-2">
                  {activeTopicDetail.by_school.map((s: any) => {
                    const acc = s.accuracy !== null ? Math.round(s.accuracy * 100) : 0;
                    return (
                      <div key={s.school_id} className="space-y-1">
                        <div className="flex justify-between text-xs">
                          <span className="font-medium text-[#151515]">
                            {s.school_name || s.school_id} ({s.n_students} students)
                          </span>
                          <span className="font-mono font-semibold">{acc}%</span>
                        </div>
                        <div className="w-full h-2 bg-[#F3F2EE] rounded-sm overflow-hidden">
                          <div
                            className="h-full bg-[#151515] rounded-sm"
                            style={{ width: `${acc}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="text-right pt-2 border-t border-[#E6E5E0]">
              <button
                onClick={() => setActiveTopic(null)}
                className="px-4 py-2 bg-[#151515] text-white rounded-lg text-xs font-semibold hover:bg-[#333333] transition cursor-pointer"
              >
                Close Details
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
