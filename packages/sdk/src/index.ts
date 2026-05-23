export * from "./client.js"
export * from "./server.js"

import { createOpencodeClient } from "./client.js"
import { createOpencodeServer } from "./server.js"
import type { ServerOptions } from "./server.js"

export const ICECODE_SERVER_URL = "http://localhost:13210"

/**
 * Connect directly to the ICECODE Python server (without starting a separate TS server).
 * The Python server must already be running on port 13210.
 */
export function connectToIcecode(options?: { baseUrl?: string }) {
  const baseUrl = options?.baseUrl ?? ICECODE_SERVER_URL
  return createOpencodeClient({ baseUrl })
}

/**
 * Start TS server (OpenCode-mode). Use `connectToIcecode()` if you are using the Python backend.
 */
export async function createOpencode(options?: ServerOptions) {
  const server = await createOpencodeServer({
    ...options,
  })

  const client = createOpencodeClient({
    baseUrl: server.url,
  })

  return {
    client,
    server,
  }
}
