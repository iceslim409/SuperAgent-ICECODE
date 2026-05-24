import { Context, Effect, Layer } from "effect"

interface EnvInterface {
  get(key: string): string | undefined
  set(key: string, value: string): void
  all(): Record<string, string>
}

class EnvService extends Context.Service<EnvService, EnvInterface>()("@icecode/Env") {}

const layer = Layer.effect(
  EnvService,
  Effect.gen(function* () {
    return EnvService.of({
      get: (key: string) => process.env[key],
      set: (key: string, value: string) => { process.env[key] = value },
      all: () => ({ ...process.env } as Record<string, string>),
    })
  }),
)

export const Env = {
  Service: EnvService,
  defaultLayer: layer,
  set: (key: string, value: string) => { process.env[key] = value },
}
