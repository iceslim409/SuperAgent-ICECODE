"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Framing = exports.sse = void 0;
var ProviderShared = require("../protocols/shared");
/** Server-Sent Events framing. Used by every JSON-streaming HTTP provider. */
exports.sse = { id: "sse", frame: ProviderShared.sseFraming };
exports.Framing = require("./framing");
