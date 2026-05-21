/**
 * ICECODE Gateway — TypeScript client for the Python multi-platform gateway
 * 34+ platform adapters running in the Python backend (port 13210)
 */

export interface GatewayChannel {
  id: string
  platform: string
  name: string
  enabled: boolean
  config?: Record<string, unknown>
}

export interface GatewayMessage {
  channel_id: string
  text: string
  attachments?: string[]
}

export interface GatewaySendResult {
  ok: boolean
  message_id?: string
  error?: string
}

export interface GatewayStatus {
  platform: string
  status: "connected" | "disconnected" | "error"
  channels: number
}

export class GatewayClient {
  private baseUrl: string

  constructor(baseUrl = "http://localhost:13210") {
    this.baseUrl = baseUrl
  }

  async listChannels(): Promise<GatewayChannel[]> {
    const res = await fetch(`${this.baseUrl}/api/channels`)
    if (!res.ok) throw new Error(`Gateway error: ${res.status}`)
    const data = await res.json() as { channels?: GatewayChannel[] }
    return data.channels ?? []
  }

  async sendMessage(msg: GatewayMessage): Promise<GatewaySendResult> {
    const res = await fetch(`${this.baseUrl}/api/gateway/send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(msg),
    })
    if (!res.ok) throw new Error(`Gateway send error: ${res.status}`)
    return res.json() as Promise<GatewaySendResult>
  }

  async getStatus(): Promise<GatewayStatus[]> {
    const res = await fetch(`${this.baseUrl}/api/gateway/status`)
    if (!res.ok) throw new Error(`Gateway status error: ${res.status}`)
    return res.json() as Promise<GatewayStatus[]>
  }

  async getPlatforms(): Promise<string[]> {
    const res = await fetch(`${this.baseUrl}/api/gateway/platforms`)
    if (!res.ok) return []
    const data = await res.json() as { platforms?: string[] }
    return data.platforms ?? []
  }

  async createChannel(platform: string, config: Record<string, unknown>): Promise<GatewayChannel> {
    const res = await fetch(`${this.baseUrl}/api/channels`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform, config }),
    })
    if (!res.ok) throw new Error(`Create channel error: ${res.status}`)
    return res.json() as Promise<GatewayChannel>
  }
}

export function createGatewayClient(baseUrl?: string): GatewayClient {
  return new GatewayClient(baseUrl)
}
