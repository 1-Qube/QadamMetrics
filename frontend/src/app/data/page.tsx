"use client";

import React, { useState, useEffect } from "react";
import { useApp } from "@/context/AppContext";
import { api } from "@/lib/api";
import {
  UploadCloud,
  FileSpreadsheet,
  AlertTriangle,
  CheckCircle2,
  Trash2,
  Sparkles,
  Info,
  Loader2,
  ArrowRight,
} from "lucide-react";

export default function DataManagementPage() {
  const { datasets, selectedDatasetId, setSelectedDatasetId, refreshDatasets } = useApp();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isSynthetic, setIsSynthetic] = useState(false);
  const [responsesFile, setResponsesFile] = useState<File | null>(null);
  const [topicsFile, setTopicsFile] = useState<File | null>(null);
  const [prereqFile, setPrereqFile] = useState<File | null>(null);
  const [allocFile, setAllocFile] = useState<File | null>(null);

  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<any | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [issues, setIssues] = useState<any[]>([]);
  const [loadingIssues, setLoadingIssues] = useState(false);

  useEffect(() => {
    if (!selectedDatasetId) return;
    setLoadingIssues(true);
    api.getDatasetIssues(selectedDatasetId, 50)
      .then((data) => setIssues(data || []))
      .catch(() => setIssues([]))
      .finally(() => setLoadingIssues(false));
  }, [selectedDatasetId]);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!responsesFile) {
      setUploadError("Responses CSV file is required.");
      return;
    }

    setUploading(true);
    setUploadError(null);
    setUploadResult(null);

    const formData = new FormData();
    formData.append("name", name || responsesFile.name);
    formData.append("description", description);
    formData.append("is_synthetic", String(isSynthetic));
    formData.append("responses", responsesFile);
    if (topicsFile) formData.append("topics", topicsFile);
    if (prereqFile) formData.append("prerequisites", prereqFile);
    if (allocFile) formData.append("allocations", allocFile);

    try {
      const res = await api.importDataset(formData);
      setUploadResult(res);
      await refreshDatasets();
      if (res.dataset_id) {
        setSelectedDatasetId(res.dataset_id);
      }
      // Reset form
      setName("");
      setDescription("");
      setResponsesFile(null);
      setTopicsFile(null);
      setPrereqFile(null);
      setAllocFile(null);
    } catch (err: any) {
      setUploadError(err?.message || "Upload failed. Please check CSV format.");
    } finally {
      setUploading(false);
    }
  };

  const handleDemo = async () => {
    setUploading(true);
    setUploadError(null);
    try {
      const res = await api.loadDemoDataset(12);
      await refreshDatasets();
      if (res.dataset_id) setSelectedDatasetId(res.dataset_id);
      setUploadResult({ ...res, status: "synthetic demo loaded" });
    } catch (err: any) {
      setUploadError(err?.message || "Could not load the synthetic demo.");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this dataset?")) return;
    try {
      await api.deleteDataset(id);
      if (id === selectedDatasetId) setSelectedDatasetId(null);
      await refreshDatasets();
    } catch (err: any) {
      alert("Failed to delete dataset: " + err?.message);
    }
  };

  return (
    <div className="max-w-[1400px] mx-auto space-y-8 pb-16">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight text-[#151515] font-sans">
            Data Management
          </h1>
          <p className="text-sm text-[#70706B] mt-1">
            Ingest student item-response data, topic catalogs, and curriculum allocations with strict row-level validation.
          </p>
        </div>
        <button
          type="button"
          onClick={handleDemo}
          disabled={uploading}
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#151515] text-white rounded-lg text-sm font-semibold disabled:opacity-60"
        >
          <Sparkles className="w-4 h-4 text-[#C9F542]" />
          Load synthetic demo
        </button>
      </div>

      {/* Grid: Upload Card on Left, Format Guide on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Upload Form */}
        <div className="lg:col-span-2 bg-[#FFFFFF] border border-[#E6E5E0] rounded-xl p-6 shadow-2xs">
          <div className="flex items-center gap-2 mb-6">
            <div className="w-1 h-4 bg-[#C9F542] rounded-full" />
            <h2 className="font-bold text-base text-[#151515]">Upload Dataset Files</h2>
          </div>

          <form onSubmit={handleUpload} className="space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-[#151515] mb-1">
                  Dataset Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Grade 8 Mathematics Autumn 2024"
                  className="w-full bg-[#FAF9F6] border border-[#E6E5E0] rounded-lg px-3 py-2 text-xs text-[#151515] focus:outline-none focus:border-[#151515]"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-[#151515] mb-1">
                  Description (optional)
                </label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="e.g. Standardized district benchmark assessment"
                  className="w-full bg-[#FAF9F6] border border-[#E6E5E0] rounded-lg px-3 py-2 text-xs text-[#151515] focus:outline-none focus:border-[#151515]"
                />
              </div>
            </div>

            <div className="flex items-center gap-2 py-1">
              <input
                type="checkbox"
                id="syntheticCheck"
                checked={isSynthetic}
                onChange={(e) => setIsSynthetic(e.target.checked)}
                className="w-4 h-4 accent-[#151515] rounded cursor-pointer"
              />
              <label htmlFor="syntheticCheck" className="text-xs text-[#70706B] cursor-pointer">
                Mark as synthetic / demonstration data (stamped as <code className="text-[#151515] font-mono">evidence_class: synthetic</code>)
              </label>
            </div>

            {/* File Inputs Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              {/* Primary Responses File (Required) */}
              <div className="border border-dashed border-[#D1D0C9] rounded-xl p-4 bg-[#FAF9F6] hover:border-[#151515] transition">
                <div className="flex items-center gap-2 mb-2">
                  <FileSpreadsheet className="w-4 h-4 text-[#151515]" />
                  <span className="text-xs font-semibold text-[#151515]">
                    Responses CSV <span className="text-red-500">*</span>
                  </span>
                </div>
                <input
                  type="file"
                  accept=".csv"
                  required
                  onChange={(e) => setResponsesFile(e.target.files?.[0] || null)}
                  className="text-xs text-[#70706B] file:mr-2 file:py-1 file:px-2.5 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-[#151515] file:text-white hover:file:bg-[#333333] cursor-pointer"
                />
                <span className="block text-[10px] text-[#95958E] mt-1">
                  student_id, school_id, grade_level, topic_id, score/is_correct
                </span>
              </div>

              {/* Topics CSV */}
              <div className="border border-dashed border-[#D1D0C9] rounded-xl p-4 bg-[#FAF9F6] hover:border-[#151515] transition">
                <div className="flex items-center gap-2 mb-2">
                  <FileSpreadsheet className="w-4 h-4 text-[#70706B]" />
                  <span className="text-xs font-semibold text-[#151515]">Topics CSV (Optional)</span>
                </div>
                <input
                  type="file"
                  accept=".csv"
                  onChange={(e) => setTopicsFile(e.target.files?.[0] || null)}
                  className="text-xs text-[#70706B] file:mr-2 file:py-1 file:px-2.5 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-[#E6E5E0] file:text-[#151515] hover:file:bg-[#D1D0C9] cursor-pointer"
                />
                <span className="block text-[10px] text-[#95958E] mt-1">
                  topic_id, topic_name, grade_level, description
                </span>
              </div>

              {/* Prerequisites CSV */}
              <div className="border border-dashed border-[#D1D0C9] rounded-xl p-4 bg-[#FAF9F6] hover:border-[#151515] transition">
                <div className="flex items-center gap-2 mb-2">
                  <FileSpreadsheet className="w-4 h-4 text-[#70706B]" />
                  <span className="text-xs font-semibold text-[#151515]">Prerequisites CSV (Optional)</span>
                </div>
                <input
                  type="file"
                  accept=".csv"
                  onChange={(e) => setPrereqFile(e.target.files?.[0] || null)}
                  className="text-xs text-[#70706B] file:mr-2 file:py-1 file:px-2.5 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-[#E6E5E0] file:text-[#151515] hover:file:bg-[#D1D0C9] cursor-pointer"
                />
                <span className="block text-[10px] text-[#95958E] mt-1">
                  prerequisite_topic_id, dependent_topic_id, relation_status
                </span>
              </div>

              {/* Allocations CSV */}
              <div className="border border-dashed border-[#D1D0C9] rounded-xl p-4 bg-[#FAF9F6] hover:border-[#151515] transition">
                <div className="flex items-center gap-2 mb-2">
                  <FileSpreadsheet className="w-4 h-4 text-[#70706B]" />
                  <span className="text-xs font-semibold text-[#151515]">Allocations CSV (Optional)</span>
                </div>
                <input
                  type="file"
                  accept=".csv"
                  onChange={(e) => setAllocFile(e.target.files?.[0] || null)}
                  className="text-xs text-[#70706B] file:mr-2 file:py-1 file:px-2.5 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-[#E6E5E0] file:text-[#151515] hover:file:bg-[#D1D0C9] cursor-pointer"
                />
                <span className="block text-[10px] text-[#95958E] mt-1">
                  topic_id, hours, min_hours, max_hours, importance_weight
                </span>
              </div>
            </div>

            {/* Error / Success Alerts */}
            {uploadError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{uploadError}</span>
              </div>
            )}

            {uploadResult && (
              <div className="p-3 bg-[#F4FCE3] border border-[#D4F754] rounded-lg text-xs text-[#3A6000] flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  <span>
                    Import complete! Accepted: {uploadResult.rows_accepted} rows (Rejected:{" "}
                    {uploadResult.rows_rejected}, Duplicates: {uploadResult.rows_duplicate}).
                  </span>
                </div>
                <span className="font-mono text-[10px]">{uploadResult.dataset_id}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={uploading}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#151515] text-white rounded-lg text-xs font-semibold hover:bg-[#333333] transition disabled:opacity-50 cursor-pointer"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-[#C9F542]" />
                  <span>Validating and ingesting rows...</span>
                </>
              ) : (
                <>
                  <UploadCloud className="w-4 h-4 text-[#C9F542]" />
                  <span>Ingest & Validate Dataset</span>
                </>
              )}
            </button>
          </form>
        </div>

        {/* Right Card: Format Specification & Epistemic Rules */}
        <div className="bg-[#FFFFFF] border border-[#E6E5E0] rounded-xl p-6 shadow-2xs space-y-4">
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 text-[#151515]" />
            <h3 className="font-bold text-sm text-[#151515]">Validation Guarantees</h3>
          </div>

          <div className="text-xs text-[#70706B] space-y-3 leading-relaxed">
            <p>
              <strong className="text-[#151515]">Zero Silent Dropping:</strong> Problematic or malformed rows are never silently discarded. Every validation warning is reported with line numbers.
            </p>
            <p>
              <strong className="text-[#151515]">Dataset Isolation:</strong> School and student IDs are strictly scoped by <code className="font-mono text-[#151515]">dataset_id</code>. No student records leak across uploads.
            </p>
            <p>
              <strong className="text-[#151515]">Credit Normalization:</strong> Scores are clipped to [0, 1]. If <code className="font-mono text-[#151515]">is_correct</code> is provided, credit is 1.0 or 0.0.
            </p>
          </div>

          <div className="pt-3 border-t border-[#F3F2EE]">
            <span className="text-[11px] font-mono text-[#95958E] uppercase tracking-wider block mb-2">
              Required CSV Columns
            </span>
            <div className="flex flex-wrap gap-1.5 font-mono text-[10px]">
              {[
                "student_id",
                "school_id",
                "grade_level",
                "subject_id",
                "topic_id",
                "assessment_id",
                "question_id",
                "is_correct / score",
              ].map((col) => (
                <span
                  key={col}
                  className="px-2 py-0.5 bg-[#FAF9F6] border border-[#E6E5E0] rounded text-[#151515]"
                >
                  {col}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Row: Existing Datasets Table */}
      <div className="bg-[#FFFFFF] border border-[#E6E5E0] rounded-xl p-6 shadow-2xs">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="w-1 h-4 bg-[#C9F542] rounded-full" />
            <h2 className="font-bold text-base text-[#151515]">Stored Datasets</h2>
          </div>
          <span className="text-xs text-[#70706B] font-mono">{datasets.length} datasets</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#E6E5E0] text-[#70706B] font-mono uppercase tracking-wider text-[10px]">
                <th className="py-2.5 font-semibold">Dataset Name</th>
                <th className="py-2.5 font-semibold">ID</th>
                <th className="py-2.5 font-semibold">Evidence Class</th>
                <th className="py-2.5 font-semibold">Status</th>
                <th className="py-2.5 font-semibold">Created</th>
                <th className="py-2.5 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F3F2EE]">
              {datasets.map((d) => {
                const isSelected = d.id === selectedDatasetId;
                return (
                  <tr
                    key={d.id}
                    className={`hover:bg-[#FAF9F6] transition ${
                      isSelected ? "bg-[#FAF9F6]" : ""
                    }`}
                  >
                    <td className="py-3 font-semibold text-[#151515] flex items-center gap-2">
                      {isSelected && (
                        <span className="w-1.5 h-1.5 rounded-full bg-[#C9F542]" />
                      )}
                      <span>{d.name}</span>
                    </td>
                    <td className="py-3 font-mono text-[11px] text-[#70706B]">{d.id.slice(0, 12)}...</td>
                    <td className="py-3">
                      <span
                        className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${
                          d.is_synthetic
                            ? "bg-amber-50 text-amber-800 border-amber-200"
                            : "bg-[#F4FCE3] text-[#426900] border-[#D4F754]"
                        }`}
                      >
                        {d.evidence_class}
                      </span>
                    </td>
                    <td className="py-3 text-[#70706B] capitalize">{d.status}</td>
                    <td className="py-3 text-[#70706B]">
                      {new Date(d.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 text-right space-x-2">
                      {!isSelected && (
                        <button
                          onClick={() => setSelectedDatasetId(d.id)}
                          className="px-2.5 py-1 text-[11px] font-medium bg-[#151515] text-white rounded hover:bg-[#333333] transition cursor-pointer"
                        >
                          Select
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(d.id)}
                        className="px-2.5 py-1 text-[11px] font-medium text-red-600 hover:bg-red-50 rounded transition cursor-pointer"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Row: Import Issues / Validation Log for Selected Dataset */}
      {selectedDatasetId && (
        <div className="bg-[#FFFFFF] border border-[#E6E5E0] rounded-xl p-6 shadow-2xs">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className="w-1 h-4 bg-[#C9F542] rounded-full" />
              <h2 className="font-bold text-base text-[#151515]">
                Validation Issues & Audit Log ({issues.length})
              </h2>
            </div>
            <span className="text-xs text-[#70706B]">
              Active dataset: <code className="font-mono text-[#151515]">{selectedDatasetId}</code>
            </span>
          </div>

          {loadingIssues ? (
            <div className="py-6 text-center text-xs text-[#70706B]">
              <Loader2 className="w-4 h-4 animate-spin mx-auto mb-2" />
              Loading validation issues...
            </div>
          ) : issues.length === 0 ? (
            <div className="py-6 text-center text-xs text-[#70706B] flex items-center justify-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-[#4F7700]" />
              <span>Clean ingestion. No validation errors or dropped rows recorded.</span>
            </div>
          ) : (
            <div className="overflow-x-auto max-h-72">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-[#E6E5E0] text-[#70706B] text-[10px] uppercase">
                    <th className="py-2 font-semibold">Row</th>
                    <th className="py-2 font-semibold">Severity</th>
                    <th className="py-2 font-semibold">Code</th>
                    <th className="py-2 font-semibold">Message</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#F3F2EE] text-[11px]">
                  {issues.map((issue, idx) => (
                    <tr key={idx} className="hover:bg-[#FAF9F6]">
                      <td className="py-2 text-[#70706B]">{issue.row_number || "-"}</td>
                      <td className="py-2">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] uppercase ${
                            issue.severity === "error"
                              ? "bg-red-100 text-red-700"
                              : "bg-amber-100 text-amber-800"
                          }`}
                        >
                          {issue.severity}
                        </span>
                      </td>
                      <td className="py-2 text-[#151515] font-semibold">{issue.code}</td>
                      <td className="py-2 text-[#70706B]">{issue.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
