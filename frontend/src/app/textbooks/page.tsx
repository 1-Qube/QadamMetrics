"use client";

import React, { useState, useEffect } from "react";
import { useApp } from "@/context/AppContext";
import { api } from "@/lib/api";
import { TextbookComparisonResponse, TextbookComparisonItem } from "@/types";
import {
  BookMarked,
  BookOpen,
  Upload,
  AlertTriangle,
  Info,
  CheckCircle2,
  Brain,
  FileText,
  Loader2,
  TrendingUp,
} from "lucide-react";

export default function TextbooksPage() {
  const { selectedDatasetId } = useApp();
  const [data, setData] = useState<TextbookComparisonResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Ingestion form state
  const [materialId, setMaterialId] = useState("");
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState(false);

  const loadData = () => {
    if (!selectedDatasetId) return;
    setLoading(true);
    api.compareTextbooks(selectedDatasetId)
      .then((res) => setData(res))
      .catch((err) => setError(err?.message || "Failed to load textbook comparison"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, [selectedDatasetId]);

  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDatasetId || !file || !materialId) return;

    setUploading(true);
    setUploadSuccess(false);

    const formData = new FormData();
    formData.append("dataset_id", selectedDatasetId);
    formData.append("material_id", materialId);
    formData.append("title", title || materialId);
    formData.append("upload", file);

    try {
      await api.ingestTextbook(formData);
      setUploadSuccess(true);
      setMaterialId("");
      setTitle("");
      setFile(null);
      loadData();
    } catch (err: any) {
      alert("Failed to ingest textbook: " + err?.message);
    } finally {
      setUploading(false);
    }
  };

  const textbooks: TextbookComparisonItem[] = data?.structural_comparison || [];

  return (
    <div className="max-w-[1400px] mx-auto space-y-8 pb-16">
      {/* Header */}
      <div>
        <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight text-[#151515] font-sans">
          Textbook Structure & Alignment Analysis
        </h1>
        <p className="text-sm text-[#70706B] mt-1">
          Structural comparison of curriculum materials: cognitive demand, exercise distribution, and topic alignment.
        </p>
      </div>

      {/* Epistemological Safeguard Alert Banner */}
      <div className="p-4 bg-[#FAF9F6] border border-[#E6E5E0] rounded-xl text-xs text-[#70706B] flex items-start gap-3">
        <Info className="w-5 h-5 text-[#151515] shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-bold text-[#151515] block">
            Methodological Notice: Alignment &ne; Causal Efficacy
          </span>
          <p className="leading-relaxed">
            {data?.structural_statement ||
              "Structural coverage is an inherent property of the text. It does not establish which textbook helps students learn more."}
          </p>
          {data?.outcome_statement && (
            <p className="text-[11px] text-[#95958E] italic">{data.outcome_statement}</p>
          )}
        </div>
      </div>

      {/* Main Grid: Comparison Cards on Left, Ingest Form on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Side-by-side Textbook Cards */}
        <div className="lg:col-span-2 space-y-6">
          {loading ? (
            <div className="p-16 bg-[#FFFFFF] border border-[#E6E5E0] rounded-xl text-center text-xs text-[#70706B]">
              <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-[#151515]" />
              Parsing textbook documents and Bloom cognitive demand levels...
            </div>
          ) : textbooks.length === 0 ? (
            <div className="p-16 bg-[#FFFFFF] border border-[#E6E5E0] rounded-xl text-center text-xs text-[#70706B]">
              No textbooks ingested for this dataset yet. Use the upload form on the right to upload a PDF or text file.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {textbooks.map((tb, idx) => {
                const cov = tb.curriculum_coverage_ratio
                  ? Math.round(tb.curriculum_coverage_ratio * 100)
                  : 0;
                const isWinner = tb.material_id === data?.highest_structural_coverage;

                return (
                  <div
                    key={tb.material_id}
                    className={`bg-[#FFFFFF] border rounded-xl p-6 shadow-2xs space-y-5 transition ${
                      isWinner
                        ? "border-[#151515] ring-2 ring-[#C9F542]"
                        : "border-[#E6E5E0] hover:border-[#D1D0C9]"
                    }`}
                  >
                    {/* Header */}
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-mono text-[10px] text-[#70706B] font-bold">
                            {tb.material_id}
                          </span>
                          {isWinner && (
                            <span className="bg-[#C9F542] text-[#151515] text-[10px] font-bold px-2 py-0.5 rounded-full uppercase">
                              Highest Coverage
                            </span>
                          )}
                        </div>
                        <h3 className="font-bold text-base text-[#151515]">{tb.title || tb.material_id}</h3>
                      </div>
                      <BookOpen className="w-5 h-5 text-[#70706B]" />
                    </div>

                    {/* Coverage Progress */}
                    <div className="space-y-1.5">
                      <div className="flex justify-between text-xs">
                        <span className="text-[#70706B]">Curriculum Alignment</span>
                        <span className="font-bold text-[#151515]">{cov}%</span>
                      </div>
                      <div className="w-full h-3 bg-[#F3F2EE] rounded-sm overflow-hidden">
                        <div
                          className={`h-full ${
                            isWinner ? "bg-[#182B49]" : "bg-[#D1D0C9]"
                          } rounded-sm transition-all duration-500`}
                          style={{ width: `${cov}%` }}
                        />
                      </div>
                    </div>

                    {/* Content Block Metrics Grid */}
                    <div className="grid grid-cols-3 gap-2 text-center text-xs">
                      <div className="p-2 bg-[#FAF9F6] border border-[#E6E5E0] rounded-lg">
                        <span className="text-[10px] text-[#70706B] block">Chapters</span>
                        <span className="font-bold text-sm text-[#151515]">
                          {tb.chapter_count || "—"}
                        </span>
                      </div>
                      <div className="p-2 bg-[#FAF9F6] border border-[#E6E5E0] rounded-lg">
                        <span className="text-[10px] text-[#70706B] block">Exercises</span>
                        <span className="font-bold text-sm text-[#151515]">
                          {tb.counts?.exercise ?? "—"}
                        </span>
                      </div>
                      <div className="p-2 bg-[#FAF9F6] border border-[#E6E5E0] rounded-lg">
                        <span className="text-[10px] text-[#70706B] block">Variety Stems</span>
                        <span className="font-bold text-sm text-[#151515]">
                          {tb.exercise_variety ?? "—"}
                        </span>
                      </div>
                    </div>

                    {/* Cognitive Demand Breakdown (Bloom taxonomy) */}
                    {tb.cognitive_demand && (
                      <div className="space-y-2 pt-2 border-t border-[#F3F2EE]">
                        <span className="text-[11px] font-semibold text-[#151515] flex items-center gap-1.5">
                          <Brain className="w-3.5 h-3.5 text-[#70706B]" />
                          <span>Cognitive Demand (Bloom)</span>
                        </span>
                        <div className="grid grid-cols-2 gap-1.5 text-[10px] font-mono">
                          {Object.entries(tb.cognitive_demand).map(([level, count]) => (
                            <div
                              key={level}
                              className="px-2 py-1 bg-[#FAF9F6] border border-[#E6E5E0] rounded flex justify-between"
                            >
                              <span className="capitalize text-[#70706B]">{level}</span>
                              <span className="font-bold text-[#151515]">{count}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Col: Ingest New Textbook Document */}
        <div className="bg-[#FFFFFF] border border-[#E6E5E0] rounded-xl p-6 shadow-2xs space-y-5 h-fit">
          <div className="flex items-center gap-2">
            <div className="w-1 h-4 bg-[#C9F542] rounded-full" />
            <h2 className="font-bold text-base text-[#151515]">Ingest New Textbook</h2>
          </div>

          <p className="text-xs text-[#70706B] leading-relaxed">
            Upload educational textbooks in <code className="font-mono text-[#151515]">.pdf</code> or{" "}
            <code className="font-mono text-[#151515]">.txt</code> format. The analytical engine extracts chapters, definitions, worked examples, practice problems, and Bloom cognitive demands.
          </p>

          <form onSubmit={handleIngest} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-[#151515] mb-1">
                Textbook ID <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                required
                value={materialId}
                onChange={(e) => setMaterialId(e.target.value)}
                placeholder="e.g. TB_GAMMA"
                className="w-full bg-[#FAF9F6] border border-[#E6E5E0] rounded-lg px-3 py-2 text-xs text-[#151515] focus:outline-none focus:border-[#151515]"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-[#151515] mb-1">
                Title / Publisher
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Modern Algebra: Grade 8 Edition"
                className="w-full bg-[#FAF9F6] border border-[#E6E5E0] rounded-lg px-3 py-2 text-xs text-[#151515] focus:outline-none focus:border-[#151515]"
              />
            </div>

            <div className="border border-dashed border-[#D1D0C9] rounded-xl p-4 bg-[#FAF9F6] hover:border-[#151515] transition">
              <input
                type="file"
                accept=".txt,.pdf"
                required
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="text-xs text-[#70706B] file:mr-2 file:py-1 file:px-2.5 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-[#151515] file:text-white cursor-pointer"
              />
              <span className="block text-[10px] text-[#95958E] mt-1">
                PDF or TXT documents up to 32 MB
              </span>
            </div>

            {uploadSuccess && (
              <div className="p-3 bg-[#F4FCE3] border border-[#D4F754] rounded-lg text-xs text-[#3A6000] flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>Textbook ingested and structural index updated.</span>
              </div>
            )}

            <button
              type="submit"
              disabled={uploading}
              className="w-full py-2.5 bg-[#151515] text-white rounded-lg text-xs font-semibold hover:bg-[#333333] transition disabled:opacity-50 cursor-pointer flex items-center justify-center gap-1.5"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-[#C9F542]" />
                  <span>Extracting structure and keywords...</span>
                </>
              ) : (
                <>
                  <Upload className="w-3.5 h-3.5 text-[#C9F542]" />
                  <span>Ingest Textbook Document</span>
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
