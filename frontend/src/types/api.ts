export interface Citation {
  doc_id: string;
  case_name: string;
  citation: string | null;
  court: string;
  date: string | null;
  kanoon_url: string;
  excerpt: string;
  is_overruled: boolean;
}

export interface OverruledWarning {
  doc_id: string;
  case_name: string;
  overruled_by: string | null;
}

export interface QueryResponse {
  status: "COMPLETE" | "LOW_CONFIDENCE" | "NO_RESULTS" | "IN_PROGRESS";
  answer: string;
  citations: Citation[];
  overruled_warnings: OverruledWarning[];
  confidence: number;
  query_type: string | null;
  disclaimer: string;
  trace_id: string;
  latency_ms: number;
}

export interface HealthResponse {
  status: string;
  corpus_size: number;
  graph_nodes: number;
  graph_edges: number;
}

export type AgentName =
  | "QueryClassifier"
  | "RetrievalAgent"
  | "GraphTraversal"
  | "VerificationAnswer";

export type AgentStepStatus = "pending" | "active" | "done";

export interface AgentStep {
  id: AgentName;
  label: string;
  description: string;
  status: AgentStepStatus;
}

export interface StreamEvent {
  event: string;
  agent?: string;
  detail?: string;
  action?: string;
  data?: QueryResponse;
  trace_id?: string;
}
