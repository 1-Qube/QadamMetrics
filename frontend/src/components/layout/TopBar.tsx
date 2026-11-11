"use client";

import React, { useMemo } from "react";
import { useApp } from "@/context/AppContext";
import { Calendar, School, Database } from "lucide-react";

// Scope pills show facts derived from the loaded dataset. The backend has no
// school or academic-year filter parameter, so these are read-only on purpose.
export function TopBar() {
  const { datasets, selectedDatasetId, selectedDataset, setSelectedDatasetId, diagnostics } = useApp();

  const period = useMemo(() => {
    const dates = (diagnostics?.over_time || []).map((r) => r.assessment_date).filter(Boolean).sort();
    if (!dates.length) return null;
    const first = dates[0];
    const last = dates[dates.length - 1];
    return first === last ? first : `${first} → ${last}`;
  }, [diagnostics]);

  const schools = diagnostics?.overview?.schools;

  return (
    <header className="h-16 px-8 border-b border-[#E6E5E0] bg-[#FAF9F6] flex items-center justify-between sticky top-0 z-20 gap-4">
      <div className="flex items-center gap-3 min-w-0">
        <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-[#E6E5E0] rounded-lg text-xs font-medium text-[#151515] min-w-0">
          <Database className="w-3.5 h-3.5 text-[#95958E] shrink-0" />
          <span className="shrink-0">Dataset:</span>
          {datasets.length === 0 ? (
            <span className="text-[#95958E]">None loaded</span>
          ) : (
            <select
              aria-label="Active dataset"
              value={selectedDatasetId || ""}
              onChange={(e) => setSelectedDatasetId(e.target.value)}
              className="bg-transparent font-semibold cursor-pointer outline-none text-[#151515] max-w-[260px] truncate"
            >
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          )}
        </div>
        {selectedDataset?.is_synthetic && (
          <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full border bg-amber-50 text-amber-800 border-amber-200 shrink-0">
            Demonstration data
          </span>
        )}
      </div>

      <div className="hidden md:flex items-center gap-3">
        {period && (
          <div className="flex items-center gap-2 px-3.5 py-1.5 bg-white border border-[#E6E5E0] rounded-lg text-xs text-[#151515]">
            <Calendar className="w-3.5 h-3.5 text-[#70706B]" />
            <span className="text-[#70706B]">Assessment period:</span>
            <span className="font-semibold font-mono">{period}</span>
          </div>
        )}
        {schools !== undefined && (
          <div className="flex items-center gap-2 px-3.5 py-1.5 bg-white border border-[#E6E5E0] rounded-lg text-xs text-[#151515]">
            <School className="w-3.5 h-3.5 text-[#70706B]" />
            <span className="text-[#70706B]">Schools:</span>
            <span className="font-semibold">{schools}</span>
          </div>
        )}
      </div>
    </header>
  );
}
