export * from "./client.js"
export * from "./server.js"

import { createOpencodeClient } from "./client.js"
import { createOpencodeServer } from "./server.js"
import type { ServerOptions } from "./server.js"

export const ICECODE_SERVER_URL = "http://localhost:13210"

/**
 * Conectare directă la serverul Python ICECODE (fără a porni un server TS separat).
 * Serverul Python trebuie să ruleze deja pe portul 13210.
 */
export function connectToIcecode(options?: { baseUrl?: string }) {
  const baseUrl = options?.baseUrl ?? ICECODE_SERVER_URL
  return createOpencodeClient({ baseUrl })
}

/**
 * Pornire server TS (OpenCode-mode). Folosiţi `connectToIcecode()` dacă folosiţi backend-ul Python.
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
