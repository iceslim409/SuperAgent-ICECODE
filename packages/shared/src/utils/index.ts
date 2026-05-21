/**
 * ICECODE shared utilities
 */

export function generateId(prefix = ""): string {
  return `${prefix}${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function formatDate(ts: number): string {
  return new Date(ts).toLocaleString()
}

export function truncate(str: string, maxLen: number): string {
  if (str.length <= maxLen) return str
  return str.slice(0, maxLen - 3) + "..."
}

export function parseEnv(key: string, fallback = ""): string {
  return (typeof process !== "undefined" && process.env[key]) || fallback
}
