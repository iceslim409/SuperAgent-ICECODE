/**
 * @icecode/server — TypeScript type exports for the ICECODE backend API.
 *
 * The actual server runs as a Python FastAPI process on port 13210.
 * This package provides shared TypeScript types and a lightweight HTTP client
 * for frontend/CLI packages to communicate with the Python backend.
 */

export const ICECODE_API_PORT = 13210;
export const ICECODE_API_BASE = `http://localhost:${ICECODE_API_PORT}`;

// ── Shared API types ──────────────────────────────────────────────────────────

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  model?: string;
  provider?: string;
  base_url?: string;
  max_iterations?: number;
}

export interface StreamChunk {
  type: "text" | "tool_call" | "tool_result" | "usage" | "session" | "done" | "error";
  content?: string;
  session_id?: string;
  name?: string;
  args?: Record<string, unknown>;
  result?: unknown;
  usage?: UsageStats;
}

export interface UsageStats {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  tool_calls?: number;
  iterations?: number;
  elapsed_seconds?: number;
}

export interface Session {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface KanbanTask {
  id: string;
  title: string;
  status: "todo" | "in_progress" | "done";
  priority: "low" | "medium" | "high";
  created_at: string;
}

// ── Minimal HTTP client ───────────────────────────────────────────────────────

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${ICECODE_API_BASE}${path}`);
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${ICECODE_API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export async function* streamChat(request: ChatRequest): AsyncGenerator<StreamChunk> {
  const res = await fetch(`${ICECODE_API_BASE}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok || !res.body) throw new Error(`Stream error ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.startsWith("data:")) continue;
      const raw = line.slice(5).trim();
      if (!raw || raw === "[DONE]") continue;
      try {
        yield JSON.parse(raw) as StreamChunk;
      } catch {
        // skip malformed
      }
    }
  }
}
