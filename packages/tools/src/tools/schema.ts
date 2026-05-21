import { Schema } from "effect"

import { Identifier } from "@/id/id"
import { zod } from "@icecode/core/effect-zod"
import { withStatics } from "@icecode/core/schema"

const toolIdSchema = Schema.String.check(Schema.isStartsWith("tool")).pipe(Schema.brand("ToolID"))

export type ToolID = typeof toolIdSchema.Type

export const ToolID = toolIdSchema.pipe(
  withStatics((schema: typeof toolIdSchema) => ({
    ascending: (id?: string) => schema.make(Identifier.ascending("tool", id)),
    zod: zod(schema),
  })),
)
