"use client";

import React, { useEffect, useState } from "react";
import { useApp } from "@/context/AppContext";
import { api } from "@/lib/api";
import { Server, Sparkles, CheckCircle2, Database, RefreshCw } from "lucide-react";

const PROFILE_KEY = "qm.institutionProfile";

export default function SettingsPage() {
  const { selectedDataset, diagnostics } = useApp();
  const [health, setHealth] = useState<any | null>(null);
  const [aiStatus, setAiStatus] = useState<any | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  const [institutionName, setInstitutionName] = useState("");
  const [contactName, setContactName] = useState("");
  const [savedAt, setSavedAt] = useState<string | null>(null);

  const checkBackend = () => {
    setChecking(true);
    setHealthError(null);
    Promise.allSettled([api.getHealth(), api.getAiStatus()]).then(([h, a]) => {
      if (h.status === "fulfilled") setHealth(h.value);
      else {
        setHealth(null);
        setHealthError(String(h.reason?.message || h.reason));
      }
      setAiStatus(a.status === "fulfilled" ? a.value : null);
      setChecking(false);
    });
  };

  useEffect(() => {
    checkBackend();
    try {
      const saved = JSON.parse(window.localStorage.getItem(PROFILE_KEY) || "{}");
      setInstitutionName(saved.institutionName || "");
      setContactName(saved.contactName || "");
    } catch {
      /* ignore malformed storage */
    }
  }, []);

  const save = (e: React.FormEvent) => {
    e.preventDefault();
    window.localStorage.setItem(PROFILE_KEY, JSON.stringify({ institutionName, contactName }));
    setSavedAt(new Date().toLocaleTimeString());
  };

  const Row = ({ icon: Icon, title, detail, state, ok }: any) => (
    <div className="p-3 bg-[#FAF9F6] border border-[#E6E5E0] rounded-lg flex items-center justify-between text-xs">
      <div className="flex items-center gap-2.5">
        <Icon className="w-4 h-4" />
        <div>
          <span className="font-semibold block">{title}</span>
          <span className="text-[10px] text-[#70706B] font-mono">{detail}</span>
        </div>
      </div>
      <span
        className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border ${
          ok === null ? "bg-[#F3F2EE] text-[#70706B] border-[#E6E5E0]" : ok ? "bg-[#F4FCE3] text-[#426900] border-[#D4F754]" : "bg-red-50 text-red-700 border-red-200"
        }`}
      >
        {state}
      </span>
    </div>
  );

  return (
    <div className="max-w-[1400px] mx-auto space-y-8 pb-16">
      <div>
        <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight">Settings</h1>
        <p className="text-sm text-[#70706B] mt-1">Institution profile and analytics service status.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="bg-white border border-[#E6E5E0] rounded-xl p-6 space-y-5">
          <div className="flex items-center gap-2">
            <div className="w-1 h-4 bg-[#C9F542] rounded-full" />
            <h2 className="font-bold text-base">Institution profile</h2>
          </div>
          <form onSubmit={save} className="space-y-4">
            <div>
              <label htmlFor="inst" className="block text-xs font-medium mb-1">Institution name</label>
              <input id="inst" value={institutionName} onChange={(e) => setInstitutionName(e.target.value)} placeholder="e.g. Almaty Department of Education"
                className="w-full bg-[#FAF9F6] border border-[#E6E5E0] rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-[#151515]" />
            </div>
            <div>
              <label htmlFor="contact" className="block text-xs font-medium mb-1">Responsible methodologist</label>
              <input id="contact" value={contactName} onChange={(e) => setContactName(e.target.value)} placeholder="Name and role"
                className="w-full bg-[#FAF9F6] border border-[#E6E5E0] rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-[#151515]" />
            </div>
            {savedAt && (
              <div className="p-2.5 bg-[#F4FCE3] border border-[#D4F754] rounded-lg text-xs text-[#3A6000] flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4" /> Saved in this browser at {savedAt}. The backend has no user-profile endpoint yet.
              </div>
            )}
            <button type="submit" className="px-4 py-2 bg-[#151515] text-white rounded-lg text-xs font-semibold hover:bg-[#333]">Save profile</button>
          </form>

          <div className="pt-4 border-t border-[#F3F2EE] text-xs space-y-1.5">
            <span className="font-semibold block mb-1">Active dataset</span>
            {selectedDataset ? (
              <>
                <div className="flex justify-between"><span className="text-[#70706B]">Name</span><span>{selectedDataset.name}</span></div>
                <div className="flex justify-between"><span className="text-[#70706B]">Evidence class</span><span className="font-mono">{selectedDataset.evidence_class}</span></div>
                <div className="flex justify-between"><span className="text-[#70706B]">Imported</span><span>{new Date(selectedDataset.created_at).toLocaleString()}</span></div>
                {diagnostics && (
                  <div className="flex justify-between"><span className="text-[#70706B]">Classification threshold</span><span className="font-mono">n ≥ {diagnostics.min_students}</span></div>
                )}
              </>
            ) : (
              <span className="text-[#95958E]">None selected.</span>
            )}
          </div>
        </section>

        <section className="bg-white border border-[#E6E5E0] rounded-xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-1 h-4 bg-[#C9F542] rounded-full" />
              <h2 className="font-bold text-base">Service status</h2>
            </div>
            <button onClick={checkBackend} disabled={checking} aria-label="Refresh status" className="p-1.5 hover:bg-[#F3F2EE] rounded-md text-[#70706B]">
              <RefreshCw className={`w-3.5 h-3.5 ${checking ? "animate-spin" : ""}`} />
            </button>
          </div>
          {healthError && <div className="p-2.5 bg-red-50 border border-red-200 rounded-lg text-xs text-red-800">API unreachable: {healthError}</div>}
          <Row icon={Server} title="Analytics API" detail={health ? `v${health.version} · ${health.environment}` : checking ? "checking…" : "—"}
            state={health ? health.status : checking ? "…" : "down"} ok={health ? health.status === "ok" : checking ? null : false} />
          <Row icon={Database} title="Database" detail={health ? health.database_dialect : "—"}
            state={health ? health.database : "—"} ok={health ? health.database === "up" : null} />
          <Row icon={Sparkles} title="AI copilot" detail={aiStatus ? aiStatus.model || "deterministic template" : "—"}
            state={aiStatus ? (aiStatus.configured ? "gemini" : "fallback") : "—"} ok={aiStatus ? true : null} />
          <p className="text-[11px] text-[#70706B] leading-relaxed">
            The AI key lives only on the server. The copilot narrates engine output and discards answers that contain numbers not present in the analytics.
          </p>
        </section>
      </div>
    </div>
  );
}
