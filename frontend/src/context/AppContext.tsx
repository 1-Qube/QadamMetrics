"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Dataset, DiagnosticsResponse } from "@/types";
import { api } from "@/lib/api";

interface AppContextType {
  datasets: Dataset[];
  selectedDatasetId: string | null;
  selectedDataset: Dataset | null;
  diagnostics: DiagnosticsResponse | null;
  isLoadingDatasets: boolean;
  error: string | null;
  setSelectedDatasetId: (id: string | null) => void;
  refreshDatasets: () => Promise<void>;
  refreshDiagnostics: () => Promise<void>;
}

const AppContext = createContext<AppContextType | undefined>(undefined);
const STORAGE_KEY = "qm.selectedDatasetId";

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedDatasetId, setSelectedDatasetIdState] = useState<string | null>(null);
  const [diagnostics, setDiagnostics] = useState<DiagnosticsResponse | null>(null);
  const [isLoadingDatasets, setIsLoadingDatasets] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const setSelectedDatasetId = useCallback((id: string | null) => {
    setSelectedDatasetIdState(id);
    if (typeof window !== "undefined") {
      if (id) window.localStorage.setItem(STORAGE_KEY, id);
      else window.localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const refreshDatasets = useCallback(async () => {
    setIsLoadingDatasets(true);
    setError(null);
    try {
      const list = await api.getDatasets();
      setDatasets(list);
      setSelectedDatasetIdState((current) => {
        const stored = typeof window !== "undefined" ? window.localStorage.getItem(STORAGE_KEY) : null;
        const candidate = current || stored;
        if (candidate && list.some((d) => d.id === candidate)) return candidate;
        // Prefer real (non-synthetic) data when choosing a default.
        const real = list.find((d) => !d.is_synthetic);
        return (real || list[0])?.id ?? null;
      });
    } catch (err: any) {
      setError(err?.message || "Could not reach the QadamMetrics API.");
    } finally {
      setIsLoadingDatasets(false);
    }
  }, []);

  const refreshDiagnostics = useCallback(async () => {
    if (!selectedDatasetId) {
      setDiagnostics(null);
      return;
    }
    try {
      setDiagnostics(await api.getTopics(selectedDatasetId));
    } catch {
      setDiagnostics(null);
    }
  }, [selectedDatasetId]);

  useEffect(() => {
    refreshDatasets();
  }, [refreshDatasets]);

  useEffect(() => {
    setDiagnostics(null);
    refreshDiagnostics();
  }, [refreshDiagnostics]);

  const selectedDataset = useMemo(
    () => datasets.find((d) => d.id === selectedDatasetId) || null,
    [datasets, selectedDatasetId]
  );

  return (
    <AppContext.Provider
      value={{
        datasets,
        selectedDatasetId,
        selectedDataset,
        diagnostics,
        isLoadingDatasets,
        error,
        setSelectedDatasetId,
        refreshDatasets,
        refreshDiagnostics,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) throw new Error("useApp must be used within an AppProvider");
  return context;
}
