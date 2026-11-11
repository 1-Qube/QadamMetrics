import {
  Dataset,
  DiagnosticsOverviewResponse,
  DiagnosticsResponse,
  KnowledgeGraphResponse,
  TextbookSummary,
  TextbookComparisonResponse,
  AllocationItem,
  OptimizationResponse,
  RecommendationsResponse,
  InferenceCandidate,
  CopilotStatus,
  CopilotResponse,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

function ownerToken(): string {
  if (typeof window === "undefined") return "";
  const key = "qm.ownerToken";
  let token = window.localStorage.getItem(key);
  if (!token) {
    token = crypto.randomUUID().replace(/-/g, "");
    window.localStorage.setItem(key, token);
  }
  return token;
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers = new Headers(options.headers || {});
  const token = ownerToken();
  if (token) headers.set("X-Owner-Token", token);

  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(url, {
    ...options,
    headers,
    signal: options.signal ?? AbortSignal.timeout(120000),
  });

  const json = await response.json().catch(() => ({}));

  if (!response.ok) {
    const errorMsg =
      json?.error?.message ||
      json?.detail ||
      `Request failed with status ${response.status}`;
    throw new Error(errorMsg);
  }

  // The backend wraps responses in {"data": ...}
  return (json.data !== undefined ? json.data : json) as T;
}

export const api = {
  // System Health
  async getHealth() {
    return request<{
      status: string;
      version: string;
      environment: string;
      database: string;
      database_dialect: string;
      ai: { configured: boolean; required: boolean };
    }>("/health");
  },

  // Datasets
  async getDatasets(): Promise<Dataset[]> {
    return request<Dataset[]>("/api/datasets");
  },

  async getDataset(id: string): Promise<Dataset> {
    return request<Dataset>(`/api/datasets/${id}`);
  },

  async loadDemoDataset(studentsPerSchoolGrade = 24): Promise<{
    dataset_id: string;
    rows_accepted: number;
    evidence_class: string;
    name: string;
  }> {
    return request<{
      dataset_id: string;
      rows_accepted: number;
      evidence_class: string;
      name: string;
    }>(`/api/datasets/demo?students_per_school_grade=${studentsPerSchoolGrade}`, {
      method: "POST",
    });
  },

  async importDataset(formData: FormData): Promise<{
    dataset_id: string;
    status: string;
    rows_accepted: number;
    rows_rejected: number;
    rows_duplicate: number;
  }> {
    return request("/api/datasets/import", {
      method: "POST",
      body: formData,
    });
  },

  async deleteDataset(id: string): Promise<{ deleted: boolean; dataset_id: string }> {
    return request<{ deleted: boolean; dataset_id: string }>(`/api/datasets/${id}`, {
      method: "DELETE",
    });
  },

  async getDatasetIssues(id: string, limit = 100): Promise<Array<{
    row_number: number | null;
    severity: string;
    code: string;
    message: string;
  }>> {
    return request(`/api/datasets/${id}/issues?limit=${limit}`);
  },

  // Analytics & Diagnostics
  async getOverview(datasetId: string, minStudents = 30): Promise<DiagnosticsOverviewResponse> {
    return request<DiagnosticsOverviewResponse>(
      `/api/analytics/overview?dataset_id=${datasetId}&min_students=${minStudents}`
    );
  },

  async getTopics(datasetId: string, minStudents = 30): Promise<DiagnosticsResponse> {
    return request<DiagnosticsResponse>(
      `/api/analytics/topics?dataset_id=${datasetId}&min_students=${minStudents}`
    );
  },

  async getTopicDetail(topicId: string, datasetId: string, minStudents = 30) {
    return request<{
      topic: any;
      by_school: any[];
      by_grade: any[];
      over_time: any[];
      distribution: any;
      evidence_class: string;
    }>(`/api/analytics/topics/${topicId}?dataset_id=${datasetId}&min_students=${minStudents}`);
  },

  // Knowledge Graph
  async getKnowledgeGraph(datasetId: string, minStudents = 30): Promise<KnowledgeGraphResponse> {
    return request<KnowledgeGraphResponse>(
      `/api/knowledge-graph?dataset_id=${datasetId}&min_students=${minStudents}`
    );
  },

  async addEdge(
    datasetId: string,
    body: {
      prerequisite_topic_id: string;
      dependent_topic_id: string;
      relation_status?: string;
      notes?: string;
    }
  ) {
    return request(`/api/knowledge-graph/edges?dataset_id=${datasetId}`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  async inferEdges(datasetId: string) {
    return request<{ candidates: InferenceCandidate[] }>(`/api/knowledge-graph/infer?dataset_id=${datasetId}`, {
      method: "POST",
    });
  },

  // Textbooks
  async getTextbooks(datasetId: string): Promise<TextbookSummary[]> {
    return request<TextbookSummary[]>(`/api/textbooks?dataset_id=${datasetId}`);
  },

  async getTextbookDetail(materialId: string, datasetId: string) {
    return request<{
      material_id: string;
      title: string;
      structure: any;
      is_synthetic: boolean;
    }>(`/api/textbooks/${materialId}?dataset_id=${datasetId}`);
  },

  async compareTextbooks(datasetId: string): Promise<TextbookComparisonResponse> {
    return request<TextbookComparisonResponse>(
      `/api/textbook-comparison?dataset_id=${datasetId}`,
      { method: "POST" }
    );
  },

  async ingestTextbook(formData: FormData) {
    return request("/api/textbooks/ingest", {
      method: "POST",
      body: formData,
    });
  },

  // Curriculum Planning / Optimization
  async getAllocations(datasetId: string): Promise<AllocationItem[]> {
    return request<AllocationItem[]>(`/api/curriculum/allocations?dataset_id=${datasetId}`);
  },

  async optimizeScenarios(body: {
    dataset_id: string;
    total_hours?: number;
    beta?: number;
    transfer_tau?: number;
    target_accuracy?: number;
    max_change_hours?: number;
    proposed_hours?: Record<string, number>;
  }): Promise<OptimizationResponse> {
    return request<OptimizationResponse>("/api/optimization/scenarios", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  // Recommendations
  async getRecommendations(datasetId: string): Promise<RecommendationsResponse> {
    return request<RecommendationsResponse>(`/api/recommendations?dataset_id=${datasetId}`);
  },

  // Reports
  async generateReport(body: { dataset_id: string; title?: string }): Promise<{
    report_id: string;
    title: string;
    formats: string[];
  }> {
    return request("/api/reports/generate", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  async getReportDetail(reportId: string): Promise<Record<string, any>> {
    return request<Record<string, any>>(`/api/reports/${reportId}`);
  },

  getReportDownloadUrl(reportId: string, format: "pdf" | "csv" | "json"): string {
    return `${API_BASE}/api/reports/${reportId}/download?format=${format}`;
  },

  // AI Copilot
  async getAiStatus(): Promise<CopilotStatus> {
    return request<CopilotStatus>("/api/ai/status");
  },

  async explain(body: {
    dataset_id?: string;
    task?: string;
    question?: string;
    facts?: Record<string, any>;
  }): Promise<CopilotResponse> {
    return request<CopilotResponse>("/api/ai/explain", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
};
