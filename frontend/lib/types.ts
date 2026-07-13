export type Role = 'technician' | 'engineer' | 'compliance_officer' | 'admin';

export interface User {
  id: string;
  username: string;
  role: Role;
  display_name: string;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface GraphNode {
  id: string;
  tag: string;
  label: string;
  type: 'equipment' | 'document' | 'procedure' | 'system' | 'component' | 'failure_mode';
  properties: Record<string, unknown>;
  confidence?: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relationship: string;
  confidence: number;
  properties?: Record<string, unknown>;
}

export interface GraphData {
  center: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface CopilotMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  agent_trigger?: AgentTrigger;
  reasoning_steps?: string[];
  timestamp: number;
  streaming?: boolean;
}

export interface Citation {
  doc_id: string;
  passage_id: string;
  page: number;
  title?: string;
  snippet?: string;
}

export interface AgentTrigger {
  worker: 'diagnose' | 'comply' | 'asset' | 'asset_risk';
  job_id: string;
}

export interface SSEEvent {
  event: 'token' | 'citation' | 'agent_trigger' | 'reasoning' | 'tool_call' | 'tool_result' | 'error' | 'done';
  data: TokenEvent | CitationEvent | AgentTriggerEvent | ReasoningEvent | ToolCallEvent | ToolResultEvent | ErrorEvent | DoneEvent;
}

export interface ReasoningEvent {
  content: string;
}

export interface ToolCallEvent {
  tool_name: string;
  tool_args: Record<string, unknown>;
}

export interface ToolResultEvent {
  tool_name: string;
  result: unknown;
}

export interface TokenEvent {
  text: string;
}

export interface CitationEvent {
  doc_id: string;
  passage_id: string;
  page: number;
}

export interface AgentTriggerEvent {
  worker: string;
  job_id: string;
}

export interface DoneEvent {
  answer_id: string;
}

export interface ComplianceGap {
  equipment_tag: string;
  equipment_name: string;
  regulation: string;
  status: 'red' | 'amber' | 'green';
  missing_evidence: string[];
  last_checked: string;
}

export interface ComplianceReport {
  score: number;
  checked: number;
  missing: number;
  gaps: ComplianceGap[];
}

export interface DiagnoseJob {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  equipment_tag: string;
  steps: ReasoningStep[];
  result?: DiagnoseResult;
}

export interface ReasoningStep {
  id: string;
  worker: string;
  action: string;
  detail: string;
  timestamp: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
  duration_ms?: number;
}

export interface DiagnoseResult {
  diagnosis: string;
  confidence: number;
  recommended_actions: string[];
  supporting_evidence: Citation[];
}

export interface MaintenanceEvent {
  id: string;
  date: string;
  type: 'inspection' | 'repair' | 'replacement' | 'calibration' | 'incident';
  description: string;
  severity?: 'low' | 'medium' | 'high' | 'critical';
  technician?: string;
}

export interface LinkedDocument {
  id: string;
  title: string;
  type: 'manual' | 'procedure' | 'report' | 'regulation' | 'drawing';
  relevance: number;
  pages: number;
  last_updated: string;
}

export interface RiskAssessment {
  tag: string;
  equipment_name: string;
  overall_risk: number;
  factors: RiskFactor[];
  trend: 'improving' | 'stable' | 'degrading';
}

export interface RiskFactor {
  name: string;
  score: number;
  weight: number;
  description: string;
}

export interface EntityFeedback {
  entity_tag: string;
  correction_type: 'relationship' | 'property' | 'classification';
  original_value: string;
  corrected_value: string;
  notes?: string;
}
