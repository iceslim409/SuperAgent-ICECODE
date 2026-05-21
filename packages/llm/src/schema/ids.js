"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ProviderMetadata = exports.JsonSchema = exports.FinishReason = exports.MessageRole = exports.TextVerbosity = exports.ReasoningEffort = exports.ReasoningEfforts = exports.ProviderID = exports.ModelID = exports.RouteID = exports.ProtocolID = void 0;
var effect_1 = require("effect");
/** Stable string identifier for a protocol implementation. */
exports.ProtocolID = effect_1.Schema.String;
/** Stable string identifier for the runnable route. */
exports.RouteID = effect_1.Schema.String;
exports.ModelID = effect_1.Schema.String.pipe(effect_1.Schema.brand("LLM.ModelID"));
exports.ProviderID = effect_1.Schema.String.pipe(effect_1.Schema.brand("LLM.ProviderID"));
exports.ReasoningEfforts = ["none", "minimal", "low", "medium", "high", "xhigh", "max"];
exports.ReasoningEffort = effect_1.Schema.Literals(exports.ReasoningEfforts);
exports.TextVerbosity = effect_1.Schema.Literals(["low", "medium", "high"]);
exports.MessageRole = effect_1.Schema.Literals(["user", "assistant", "tool"]);
exports.FinishReason = effect_1.Schema.Literals(["stop", "length", "tool-calls", "content-filter", "error", "unknown"]);
exports.JsonSchema = effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.Unknown);
exports.ProviderMetadata = effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.Unknown));
