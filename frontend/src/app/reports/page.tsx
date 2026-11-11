"use client";

import React, { useState } from "react";
import { useApp } from "@/context/AppContext";
import { api } from "@/lib/api";
import {
  FileText,
  Download,
  FileSpreadsheet,
  FileCode,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Clock,
  ShieldCheck,
} from "lucide-react";

interface GeneratedReportInfo {
  report_id: string;
  title: string;
  formats: string[];
  created_at: string;
}

export default function ReportsPage() {
  const { selectedDatasetId, selectedDataset } = useApp();
  const [reportTitle, setReportTitle] = useState("");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Local list of generated reports in session
  const [reports, setReports] = useState<GeneratedReportInfo[]>([]);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDatasetId) {
      setError("Please select a dataset first.");
      return;
    }

    setGenerating(true);
    setError(null);

    try {
      const res = await api.generateReport({
        dataset_id: selectedDatasetId,
        title: reportTitle || `Curriculum Analysis: ${selectedDataset?.name || "Standard Report"}`,
      });

      const newReport: GeneratedReportInfo = {
        report_id: res.report_id,
        title: res.title,
        formats: res.formats || ["pdf", "csv", "json"],
        created_at: new Date().toLocaleTimeString(),
      };

      setReports((prev) => [newReport, ...prev]);
      setReportTitle("");
    } catch (err: any) {
      setError(err?.message || "Failed to generate report");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="max-w-[1400px] mx-auto space-y-8 pb-16">
      {/* Header */}
      <div>
        <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight text-[#151515] font-sans">
          Executive Curriculum Reports
        </h1>
        <p className="text-sm text-[#70706B] mt-1">
          Compile publication-ready aggregated reports across assessment diagnostics, knowledge graph dependencies, textbook comparisons, and hour scenarios.
        </p>
      </div>

      {/* Privacy Notice Banner */}
      <div className="p-4 bg-[#FAF9F6] border border-[#E6E5E0] rounded-xl text-xs text-[#70706B] flex items-start gap-3">
        <ShieldCheck className="w-5 h-5 text-[#151515] shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-bold text-[#151515] block">
            Student Data Privacy & Anonymity Guarantee
          </span>
          <p className="leading-relaxed">
            All generated reports contain aggregated metrics only. Raw student IDs, individual item response scores, and personal records are permanently excluded from report payloads.
          </p>
        </div>
      </div>

      {/* Generate Report Form Card */}
      <div className="bg-[#FFFFFF] border border-[#E6E5E0] rounded-xl p-6 shadow-2xs max-w-2xl">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-1 h-4 bg-[#C9F542] rounded-full" />
          <h2 className="font-bold text-base text-[#151515]">Generate New Executive Dossier</h2>
        </div>

        <form onSubmit={handleGenerate} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-[#151515] mb-1">
              Report Title (optional)
            </label>
            <input
              type="text"
              value={reportTitle}
              onChange={(e) => setReportTitle(e.target.value)}
              placeholder="e.g. Annual Mathematics Curriculum Reform Brief 2024"
              className="w-full bg-[#FAF9F6] border border-[#E6E5E0] rounded-lg px-3 py-2 text-xs text-[#151515] focus:outline-none focus:border-[#151515]"
            />
          </div>

          <div className="text-xs text-[#70706B] space-y-1">
            <span className="font-semibold text-[#151515] block">Generated Sections:</span>
            <ul className="list-disc list-inside space-y-0.5 pl-1 text-[11px] text-[#70706B]">
              <li>Dataset Overview & Assessment Coverage</li>
              <li>Topic-level Diagnostic Classifications & Intervals</li>
              <li>Knowledge Dependency Risks & Cycles</li>
              <li>Textbook Structural Comparison & Cognitive Demand</li>
              <li>Curriculum Hour Scenarios (Linear HiGHS vs SLSQP)</li>
              <li>Epistemic Limitations & Methodological Definitions</li>
            </ul>
          </div>

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={generating}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#151515] text-white rounded-lg text-xs font-semibold hover:bg-[#333333] transition disabled:opacity-50 cursor-pointer"
          >
            {generating ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin text-[#C9F542]" />
                <span>Compiling analytical sections and generating PDF...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 text-[#C9F542]" />
                <span>Compile & Generate Report</span>
              </>
            )}
          </button>
        </form>
      </div>

      {/* Generated Reports Table */}
      <div className="bg-[#FFFFFF] border border-[#E6E5E0] rounded-xl p-6 shadow-2xs">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="w-1 h-4 bg-[#C9F542] rounded-full" />
            <h2 className="font-bold text-base text-[#151515]">Generated Dossiers & Downloads</h2>
          </div>
          <span className="text-xs text-[#70706B] font-mono">{reports.length} available</span>
        </div>

        {reports.length === 0 ? (
          <div className="py-12 text-center text-xs text-[#70706B]">
            No reports generated in this session yet. Click "Compile & Generate Report" above to create one.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-[#E6E5E0] text-[#70706B] font-mono uppercase tracking-wider text-[10px]">
                  <th className="py-2.5 font-semibold">Report Title</th>
                  <th className="py-2.5 font-semibold">Report ID</th>
                  <th className="py-2.5 font-semibold">Created</th>
                  <th className="py-2.5 font-semibold text-right">Available Downloads</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F3F2EE]">
                {reports.map((r) => (
                  <tr key={r.report_id} className="hover:bg-[#FAF9F6] transition">
                    <td className="py-3 font-semibold text-[#151515] flex items-center gap-2">
                      <FileText className="w-4 h-4 text-[#151515]" />
                      <span>{r.title}</span>
                    </td>
                    <td className="py-3 font-mono text-[11px] text-[#70706B]">{r.report_id}</td>
                    <td className="py-3 text-[#70706B]">{r.created_at}</td>
                    <td className="py-3 text-right space-x-2">
                      {/* PDF download */}
                      <a
                        href={api.getReportDownloadUrl(r.report_id, "pdf")}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold bg-[#151515] text-white hover:bg-[#333333] rounded transition"
                      >
                        <Download className="w-3 h-3 text-[#C9F542]" />
                        <span>PDF</span>
                      </a>

                      {/* CSV ZIP download */}
                      <a
                        href={api.getReportDownloadUrl(r.report_id, "csv")}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold bg-[#FAF9F6] border border-[#E6E5E0] hover:bg-[#F3F2EE] text-[#151515] rounded transition"
                      >
                        <FileSpreadsheet className="w-3 h-3 text-[#70706B]" />
                        <span>CSV ZIP</span>
                      </a>

                      {/* JSON download */}
                      <a
                        href={api.getReportDownloadUrl(r.report_id, "json")}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold bg-[#FAF9F6] border border-[#E6E5E0] hover:bg-[#F3F2EE] text-[#151515] rounded transition"
                      >
                        <FileCode className="w-3 h-3 text-[#70706B]" />
                        <span>JSON</span>
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
