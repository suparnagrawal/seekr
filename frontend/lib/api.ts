'use client';

import { API_V1, config } from './config';
import type { GraphData, GraphNode, GraphEdge } from './types';

function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const auth = localStorage.getItem('seekr_auth');
    return auth ? JSON.parse(auth).token : null;
  } catch {
    return null;
  }
}

function authHeaders(base: Record<string, string> = {}): Record<string, string> {
  const token = getToken();
  return token ? { ...base, Authorization: `Bearer ${token}` } : base;
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), config.requestTimeoutMs);
  try {
    const res = await fetch(`${API_V1}${path}`, {
      ...options,
      signal: controller.signal,
      headers: authHeaders({ 'Content-Type': 'application/json', ...(options.headers as Record<string, string>) }),
    });
    if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
    return res.json();
  } finally {
    clearTimeout(timeout);
  }
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export interface HealthStatus {
  ready: boolean;
  services: Record<string, string | null>;
}

export async function checkHealth(): Promise<HealthStatus> {
  return apiFetch('/ready');
}

export async function checkLiveness(): Promise<{ status: string }> {
  return apiFetch('/live');
}

// ---------------------------------------------------------------------------
// Document upload (real /upload endpoint)
// ---------------------------------------------------------------------------

export async function uploadDocument(file: File, mlGatewayUrl?: string): Promise<{ document_id: string; job_id: string; status: string }> {
  const maxBytes = config.maxUploadMb * 1024 * 1024;
  if (file.size > maxBytes) {
    throw new Error(`File exceeds the ${config.maxUploadMb} MB upload limit.`);
  }

  const form = new FormData();
  form.append('file', file);
  if (mlGatewayUrl) {
    form.append('ml_gateway_url', mlGatewayUrl);
  }

  const res = await fetch(`${API_V1}/upload`, {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Upload failed: ${res.status}`);
  }
  return res.json();
}

export async function retryDocument(documentId: string, mlGatewayUrl?: string): Promise<{ document_id: string; job_id: string; status: string }> {
  const url = new URL(`${API_V1}/retry/${encodeURIComponent(documentId)}`, window.location.origin);
  if (mlGatewayUrl) {
    url.searchParams.append('ml_gateway_url', mlGatewayUrl);
  }

  const res = await fetch(url.toString(), {
    method: 'POST',
    headers: authHeaders(),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Retry failed: ${res.status}`);
  }
  return res.json();
}

export async function cancelDocument(documentId: string): Promise<void> {
  const url = new URL(`${API_V1}/cancel/${encodeURIComponent(documentId)}`, window.location.origin);
  const res = await fetch(url.toString(), {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Cancel failed: ${res.status}`);
  }
}

export async function deleteDocument(documentId: string): Promise<void> {
  const url = new URL(`${API_V1}/documents/${encodeURIComponent(documentId)}`, window.location.origin);
  const res = await fetch(url.toString(), {
    method: 'DELETE',
    headers: authHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Delete failed: ${res.status}`);
  }
}


// ---------------------------------------------------------------------------
// Document ingestion status (real /status/{document_id} endpoint)
// ---------------------------------------------------------------------------

/** Mirrors the backend `DocumentStatusResponse` model exactly. */
export interface DocumentStatus {
  document_id: string;
  filename: string;
  /** UPLOADED → PARSED → EMBEDDED → COMPLETED (or FAILED). */
  overall_status: string;
  /** SUCCESS | FAILED | SKIPPED | null (graph extraction branch). */
  graph_job_status: string | null;
  error_message: string | null;
  page_count: number | null;
  chunk_count: number | null;
  uploaded_at: string;
  updated_at: string;
}

export async function getDocumentStatus(documentId: string): Promise<DocumentStatus> {
  return apiFetch<DocumentStatus>(`/status/${encodeURIComponent(documentId)}`);
}

export async function listDocuments(): Promise<DocumentStatus[]> {
  return apiFetch<DocumentStatus[]>('/documents');
}

// ---------------------------------------------------------------------------
// Knowledge graph (real structured /graph endpoint, backed by Neo4j)
// ---------------------------------------------------------------------------

export async function fetchGraph(tag: string, depth: number = config.defaultGraphDepth): Promise<GraphData> {
  const params = new URLSearchParams({ tag, depth: String(depth) });
  const data = await apiFetch<{ center: string; nodes: GraphNode[]; edges: GraphEdge[] }>(
    `/graph?${params.toString()}`,
  );
  return {
    center: data.center,
    nodes: data.nodes ?? [],
    edges: data.edges ?? [],
  };
}

// ---------------------------------------------------------------------------
// SSE streaming (copilot query + direct agent invocation)
// ---------------------------------------------------------------------------

export interface SSECallbacks {
  onToken: (text: string) => void;
  onCitation: (citation: { doc_id: string; filename: string; passage_id: string; chunk_index: number; page_numbers: number[]; headings: string[]; page: number | null }) => void;
  onAgentTrigger: (trigger: { worker: string; job_id: string }) => void;
  onReasoning: (content: string) => void;
  onToolCall: (toolName: string, toolArgs: Record<string, unknown>) => void;
  onToolResult: (toolName: string, result: unknown) => void;
  onError: (error: Error) => void;
  onDone: (answerId: string) => void;
}

function parseSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  callbacks: SSECallbacks,
  cancelled: { value: boolean },
): void {
  const decoder = new TextDecoder();
  let buffer = '';

  const processLines = (lines: string[]) => {
    let currentEvent = '';
    for (const line of lines) {
      if (cancelled.value) return;
      if (line.startsWith('event: ')) {
        currentEvent = line.slice(7).trim();
      } else if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6));
          switch (currentEvent) {
            case 'token': callbacks.onToken(data.text); break;
            case 'citation': callbacks.onCitation(data); break;
            case 'agent_trigger': callbacks.onAgentTrigger(data); break;
            case 'reasoning': callbacks.onReasoning(data.content); break;
            case 'tool_call': callbacks.onToolCall(data.tool_name, data.tool_args); break;
            case 'tool_result': callbacks.onToolResult(data.tool_name, data.result); break;
            case 'error': callbacks.onError(new Error(data.message)); break;
            case 'done': callbacks.onDone(data.answer_id); break;
          }
        } catch { }
        currentEvent = '';
      }
    }
  };

  (async () => {
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done || cancelled.value) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n');
        buffer = parts.pop() || '';
        processLines(parts);
      }
      if (buffer.trim()) processLines(buffer.split('\n'));
    } catch (err) {
      if (!cancelled.value) callbacks.onError(err as Error);
    }
  })();
}

function streamSSE(path: string, body: Record<string, unknown>, callbacks: SSECallbacks): () => void {
  const cancelled = { value: false };
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${API_V1}${path}`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        callbacks.onError(new Error(err.detail || `Request failed: ${res.status}`));
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) { callbacks.onError(new Error('No response body')); return; }
      parseSSEStream(reader, callbacks, cancelled);
    } catch (err) {
      if (!cancelled.value) callbacks.onError(err as Error);
    }
  })();

  return () => {
    cancelled.value = true;
    controller.abort();
  };
}

export function streamQuery(query: string, entityTag: string | null, callbacks: SSECallbacks): () => void {
  return streamSSE('/query', {
    query,
    session_id: `session-${Date.now()}`,
    focused_tag: entityTag || null,
  }, callbacks);
}

export function streamAgent(
  worker: 'asset' | 'diagnose' | 'comply',
  query: string,
  entityTag: string | null,
  callbacks: SSECallbacks,
): () => void {
  return streamSSE(`/agents/${worker}`, {
    query,
    session_id: `agent-${worker}-${Date.now()}`,
    focused_tag: entityTag || null,
  }, callbacks);
}
