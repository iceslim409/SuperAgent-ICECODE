/**
 * ICECODE shared types — used across all packages
 */

export interface Message {
  id: string
  role: "user" | "assistant" | "system" | "tool"
  content: string
  timestamp: number
  metadata?: Record<string, unknown>
}

export interface Session {
  id: string
  title: string
  created: number
  updated: number
  messages: Message[]
  model?: string
  provider?: string
}

export interface Agent {
  id: string
  name: string
  model: string
  provider: string
  channelIds?: string[]
  systemPrompt?: string
  enabled: boolean
}

export interface Channel {
  id: string
  platform: string
  name: string
  config: Record<string, unknown>
  enabled: boolean
  status: "connected" | "disconnected" | "error" | "connecting"
}

export interface Skill {
  id: string
  name: string
  version: string
  description: string
  enabled: boolean
  triggers: string[]
  usageCount: number
}

export interface CronJob {
  id: string
  name: string
  schedule: string
  command: string
  enabled: boolean
  lastRun?: number
  nextRun?: number
}

export interface Provider {
  id: string
  name: string
  type: "anthropic" | "openai" | "google" | "openrouter" | "ollama" | "custom"
  apiKey?: string
  baseUrl?: string
  enabled: boolean
}

export type ModelProvider =
  | "anthropic" | "openai" | "google" | "openrouter" | "deepseek"
  | "xai" | "bedrock" | "azure" | "cloudflare" | "copilot"
  | "ollama" | "custom"

export interface ToolCall {
  id: string
  name: string
  input: Record<string, unknown>
  output?: unknown
  error?: string
  duration?: number
}

export interface GatewayStatus {
  connected: boolean
  pid?: number
  port?: number
  version?: string
  capabilities: string[]
}
