// Types mirror the FastAPI responses in app/services/analytics_service.py.
// Field names here must match the backend exactly; do not invent fields.

export type EvidenceClass = "synthetic" | "uploaded" | string;

export interface Dataset {
  id: string;
  name: string;
  description?: string;
  evidence_class: EvidenceClass;
  is_synthetic: boolean;
  status: string;
  created_at: string;
  summary?: Record<string, any>;
}

export interface OverviewMetrics {
  responses: number;
  students: number;
  schools: number;
  topics_assessed: number;
  mean_student_topic_credit: number | null;
  weak_topics: number;
  strong_topics: number;
  insufficient_or_unassessed: number;
}

export interface CoverageMetrics {
  assessed_topics: number;
  catalog_topics: number;
  topics_meeting_minimum_n: number;
  questions: number;
}

export interface DiagnosticsOverviewResponse {
  overview: OverviewMetrics;
  coverage: CoverageMetrics;
  evidence_class: EvidenceClass;
  limitations: string[];
}

export type TopicStatus = "weak" | "strong" | "inconclusive" | "insufficient_data" | "not_assessed";

export interface TopicDiagnostic {
  topic_id: string;
  topic_name: string;
  grade_levels?: number[];
  n_schools?: number;
  n_questions?: number;
  n_students: number;
  n_items: number;
  accuracy: number | null;
  ci_low: number | null;
  ci_high: number | null;
  wilson_item_low?: number | null;
  wilson_item_high?: number | null;
  status: TopicStatus;
  difficulty_index: number | null;
  flags: string[];
  explanation: string;
}

export interface SchoolTopicRow {
  topic_id: string;
  school_id: string;
  n_students: number;
  accuracy: number | null;
  ci_low: number | null;
  ci_high: number | null;
  meets_school_minimum: boolean;
}

export interface TimeTopicRow {
  topic_id: string;
  assessment_date: string;
  n_students: number;
  accuracy: number | null;
  ci_low: number | null;
  ci_high: number | null;
}

export interface DiagnosticsResponse {
  methodology_version: string;
  evidence_class: EvidenceClass;
  min_students: number;
  overview: OverviewMetrics;
  coverage: CoverageMetrics;
  topics: TopicDiagnostic[];
  by_school: SchoolTopicRow[];
  by_grade: Array<{ topic_id: string; grade_level: number; n_students: number; accuracy: number | null }>;
  over_time: TimeTopicRow[];
  distribution: Array<{ topic_id: string; bins: Array<{ bin: string; students: number; share: number }> }>;
  limitations: string[];
}

export interface KnowledgeNode {
  id: string;
  label: string;
  grade_level?: number | null;
  depth?: number | null;
  importance: number;
  ancestor_count: number;
  descendant_count: number;
  accuracy: number | null;
  n_students?: number | null;
  status: TopicStatus | null;
  flags: string[];
  verified_prerequisites: string[];
  inferred_prerequisites: string[];
  dependents: string[];
}

export interface KnowledgeEdge {
  source: string;
  target: string;
  status: "verified" | "inferred";
  source_kind?: string;
  notes?: string;
  established?: boolean;
}

export interface KnowledgeRisk {
  topic_id: string;
  topic_name: string;
  observation: string;
  upstream_gap_hypothesis: boolean;
  weak_verified_prerequisites: string[];
  descendant_count: number;
  downstream_risk_index: number;
  reasoning: string;
  claim_level: string;
}

export interface KnowledgeGraphResponse {
  methodology_version: string;
  acyclic: boolean;
  cycles: string[][];
  node_count: number;
  edge_count: number;
  verified_edge_count: number;
  inferred_edge_count: number;
  nodes: KnowledgeNode[];
  edges: KnowledgeEdge[];
  risks: KnowledgeRisk[];
  limitations: string[];
}

export interface InferenceCandidate {
  prerequisite_topic_id: string;
  dependent_topic_id: string;
  confidence: number;
  n_students: number;
  notes: string;
}

export interface TextbookSummary {
  material_id: string;
  title: string;
  is_synthetic: boolean;
  has_text: boolean;
  counts?: Record<string, number>;
}

export interface TextbookComparisonItem {
  material_id: string;
  title: string;
  is_synthetic: boolean;
  chapter_count: number;
  counts: { definition: number; explanation: number; example: number; exercise: number; question: number };
  exercise_variety: number;
  cognitive_demand: Record<string, number>;
  topics_mentioned: string[];
  curriculum_coverage_ratio: number | null;
  expression_count: number;
  explanation_completeness_proxy: number | null;
}

export interface TextbookComparisonResponse {
  status: string;
  structural_comparison: TextbookComparisonItem[];
  highest_structural_coverage: string | null;
  structural_statement: string;
  outcome_association: Array<{ material_id: string; n_students: number; mean_credit: number; note: string }>;
  outcome_statement: string;
  limitations: string[];
}

export interface AllocationItem {
  topic_id: string;
  topic_name?: string;
  hours: number;
  min_hours: number;
  max_hours: number;
  importance_weight: number;
}

export interface ScenarioHour {
  topic_id: string;
  topic_name: string;
  hours: number;
  delta_from_current: number;
}

export interface OptimizationScenario {
  name: string;
  status: string;
  note?: string;
  objective?: Record<string, number>;
  hours: ScenarioHour[];
}

export interface ComparisonRow {
  topic_id: string;
  current: number;
  lp_priority: number | null;
  nl_diminishing_returns: number | null;
  objective_sensitive: boolean;
}

export interface OptimizationResponse {
  status: string;
  message?: string;
  total_hours: number;
  assumptions: Record<string, any>;
  scenarios: OptimizationScenario[];
  comparison: ComparisonRow[];
  sensitivity_note?: string;
  limitations: string[];
}

export interface RecommendationItem {
  id: string;
  rule_id: string;
  issue: string;
  confirmed_observation: string;
  possible_explanations: string[];
  evidence: Record<string, any>;
  topics: string[];
  recommended_action: string;
  expected_impact_direction: string;
  evidence_confidence: string;
  intervention_confidence: string;
}

export interface RecommendationsResponse {
  evidence_class: EvidenceClass;
  count: number;
  recommendations: RecommendationItem[];
  limitations: string[];
}

export interface CopilotStatus {
  provider: "gemini" | "deterministic_fallback";
  configured: boolean;
  model: string | null;
}

export interface CopilotResponse {
  provider: string;
  used_fallback: boolean;
  text: string;
  warnings: string[];
  numeric_validation: "passed" | "failed" | "fallback";
}
