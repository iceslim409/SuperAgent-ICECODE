"use strict";
var __assign = (this && this.__assign) || function () {
    __assign = Object.assign || function(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p))
                t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};
var __generator = (this && this.__generator) || function (thisArg, body) {
    var _ = { label: 0, sent: function() { if (t[0] & 1) throw t[1]; return t[1]; }, trys: [], ops: [] }, f, y, t, g = Object.create((typeof Iterator === "function" ? Iterator : Object).prototype);
    return g.next = verb(0), g["throw"] = verb(1), g["return"] = verb(2), typeof Symbol === "function" && (g[Symbol.iterator] = function() { return this; }), g;
    function verb(n) { return function (v) { return step([n, v]); }; }
    function step(op) {
        if (f) throw new TypeError("Generator is already executing.");
        while (g && (g = 0, op[0] && (_ = 0)), _) try {
            if (f = 1, y && (t = op[0] & 2 ? y["return"] : op[0] ? y["throw"] || ((t = y["return"]) && t.call(y), 0) : y.next) && !(t = t.call(y, op[1])).done) return t;
            if (y = 0, t) op = [op[0] & 2, t.value];
            switch (op[0]) {
                case 0: case 1: t = op; break;
                case 4: _.label++; return { value: op[1], done: false };
                case 5: _.label++; y = op[1]; op = [0]; continue;
                case 7: op = _.ops.pop(); _.trys.pop(); continue;
                default:
                    if (!(t = _.trys, t = t.length > 0 && t[t.length - 1]) && (op[0] === 6 || op[0] === 2)) { _ = 0; continue; }
                    if (op[0] === 3 && (!t || (op[1] > t[0] && op[1] < t[3]))) { _.label = op[1]; break; }
                    if (op[0] === 6 && _.label < t[1]) { _.label = t[1]; t = op; break; }
                    if (t && _.label < t[2]) { _.label = t[2]; _.ops.push(op); break; }
                    if (t[2]) _.ops.pop();
                    _.trys.pop(); continue;
            }
            op = body.call(thisArg, _);
        } catch (e) { op = [6, e]; y = 0; } finally { f = t = 0; }
        if (op[0] & 5) throw op[1]; return { value: op[0] ? op[1] : void 0, done: true };
    }
};
var __values = (this && this.__values) || function(o) {
    var s = typeof Symbol === "function" && Symbol.iterator, m = s && o[s], i = 0;
    if (m) return m.call(o);
    if (o && typeof o.length === "number") return {
        next: function () {
            if (o && i >= o.length) o = void 0;
            return { value: o && o[i++], done: !o };
        }
    };
    throw new TypeError(s ? "Object is not iterable." : "Symbol.iterator is not defined.");
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.Gemini = exports.model = exports.route = exports.protocol = exports.DEFAULT_BASE_URL = void 0;
var effect_1 = require("effect");
var client_1 = require("../route/client");
var auth_1 = require("../route/auth");
var endpoint_1 = require("../route/endpoint");
var framing_1 = require("../route/framing");
var protocol_1 = require("../route/protocol");
var schema_1 = require("../schema");
var shared_1 = require("./shared");
var gemini_tool_schema_1 = require("./utils/gemini-tool-schema");
var ADAPTER = "gemini";
exports.DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta";
// =============================================================================
// Request Body Schema
// =============================================================================
var GeminiTextPart = effect_1.Schema.Struct({
    text: effect_1.Schema.String,
    thought: effect_1.Schema.optional(effect_1.Schema.Boolean),
    thoughtSignature: effect_1.Schema.optional(effect_1.Schema.String),
});
var GeminiInlineDataPart = effect_1.Schema.Struct({
    inlineData: effect_1.Schema.Struct({
        mimeType: effect_1.Schema.String,
        data: effect_1.Schema.String,
    }),
});
var GeminiFunctionCallPart = effect_1.Schema.Struct({
    functionCall: effect_1.Schema.Struct({
        name: effect_1.Schema.String,
        args: effect_1.Schema.Unknown,
    }),
    thoughtSignature: effect_1.Schema.optional(effect_1.Schema.String),
});
var GeminiFunctionResponsePart = effect_1.Schema.Struct({
    functionResponse: effect_1.Schema.Struct({
        name: effect_1.Schema.String,
        response: effect_1.Schema.Unknown,
    }),
});
var GeminiContentPart = effect_1.Schema.Union([
    GeminiTextPart,
    GeminiInlineDataPart,
    GeminiFunctionCallPart,
    GeminiFunctionResponsePart,
]);
var GeminiContent = effect_1.Schema.Struct({
    role: effect_1.Schema.Literals(["user", "model"]),
    parts: effect_1.Schema.Array(GeminiContentPart),
});
var GeminiSystemInstruction = effect_1.Schema.Struct({
    parts: effect_1.Schema.Array(effect_1.Schema.Struct({ text: effect_1.Schema.String })),
});
var GeminiFunctionDeclaration = effect_1.Schema.Struct({
    name: effect_1.Schema.String,
    description: effect_1.Schema.String,
    parameters: effect_1.Schema.optional(shared_1.JsonObject),
});
var GeminiTool = effect_1.Schema.Struct({
    functionDeclarations: effect_1.Schema.Array(GeminiFunctionDeclaration),
});
var GeminiToolConfig = effect_1.Schema.Struct({
    functionCallingConfig: effect_1.Schema.Struct({
        mode: effect_1.Schema.Literals(["AUTO", "NONE", "ANY"]),
        allowedFunctionNames: (0, shared_1.optionalArray)(effect_1.Schema.String),
    }),
});
var GeminiThinkingConfig = effect_1.Schema.Struct({
    thinkingBudget: effect_1.Schema.optional(effect_1.Schema.Number),
    includeThoughts: effect_1.Schema.optional(effect_1.Schema.Boolean),
});
var GeminiGenerationConfig = effect_1.Schema.Struct({
    maxOutputTokens: effect_1.Schema.optional(effect_1.Schema.Number),
    temperature: effect_1.Schema.optional(effect_1.Schema.Number),
    topP: effect_1.Schema.optional(effect_1.Schema.Number),
    topK: effect_1.Schema.optional(effect_1.Schema.Number),
    stopSequences: (0, shared_1.optionalArray)(effect_1.Schema.String),
    thinkingConfig: effect_1.Schema.optional(GeminiThinkingConfig),
});
var GeminiBodyFields = {
    contents: effect_1.Schema.Array(GeminiContent),
    systemInstruction: effect_1.Schema.optional(GeminiSystemInstruction),
    tools: (0, shared_1.optionalArray)(GeminiTool),
    toolConfig: effect_1.Schema.optional(GeminiToolConfig),
    generationConfig: effect_1.Schema.optional(GeminiGenerationConfig),
};
var GeminiBody = effect_1.Schema.Struct(GeminiBodyFields);
var GeminiUsage = effect_1.Schema.Struct({
    cachedContentTokenCount: effect_1.Schema.optional(effect_1.Schema.Number),
    thoughtsTokenCount: effect_1.Schema.optional(effect_1.Schema.Number),
    promptTokenCount: effect_1.Schema.optional(effect_1.Schema.Number),
    candidatesTokenCount: effect_1.Schema.optional(effect_1.Schema.Number),
    totalTokenCount: effect_1.Schema.optional(effect_1.Schema.Number),
});
var GeminiCandidate = effect_1.Schema.Struct({
    content: effect_1.Schema.optional(GeminiContent),
    finishReason: effect_1.Schema.optional(effect_1.Schema.String),
});
var GeminiEvent = effect_1.Schema.Struct({
    candidates: (0, shared_1.optionalArray)(GeminiCandidate),
    usageMetadata: effect_1.Schema.optional(GeminiUsage),
});
var invalid = shared_1.ProviderShared.invalidRequest;
var mediaData = shared_1.ProviderShared.mediaBytes;
// =============================================================================
// Tool Schema Conversion
// =============================================================================
// Tool-schema conversion has two distinct concerns:
//
// 1. Sanitize — fix common authoring mistakes Gemini rejects: integer/number
//    enums (must be strings), `required` entries that don't match a property,
//    untyped arrays (`items` must be present), and `properties`/`required`
//    keys on non-object scalars. Mirrors OpenCode's historical Gemini rules.
//
// 2. Project — lossy mapping from JSON Schema to Gemini's schema dialect:
//    drop empty objects, derive `nullable: true` from `type: [..., "null"]`,
//    coerce `const` to `[const]` enum, recurse properties/items, propagate
//    only an allowlisted set of keys (description, required, format, type,
//    properties, items, allOf, anyOf, oneOf, minLength). Anything outside the
//    allowlist (e.g. `additionalProperties`, `$ref`) is silently dropped.
//
// Sanitize runs first, then project. The implementation lives in
// `utils/gemini-tool-schema` so this protocol keeps the same shape as the other
// provider protocols.
// =============================================================================
// Request Lowering
// =============================================================================
var lowerTool = function (tool) { return ({
    name: tool.name,
    description: tool.description,
    parameters: gemini_tool_schema_1.GeminiToolSchema.convert(tool.inputSchema),
}); };
var lowerToolConfig = function (toolChoice) {
    return shared_1.ProviderShared.matchToolChoice("Gemini", toolChoice, {
        auto: function () { return ({ functionCallingConfig: { mode: "AUTO" } }); },
        none: function () { return ({ functionCallingConfig: { mode: "NONE" } }); },
        required: function () { return ({ functionCallingConfig: { mode: "ANY" } }); },
        tool: function (name) { return ({ functionCallingConfig: { mode: "ANY", allowedFunctionNames: [name] } }); },
    });
};
var lowerUserPart = function (part) {
    return part.type === "text" ? { text: part.text } : { inlineData: { mimeType: part.mediaType, data: mediaData(part) } };
};
var lowerToolCall = function (part) { return ({
    functionCall: { name: part.name, args: part.input },
}); };
var lowerMessages = effect_1.Effect.fn("Gemini.lowerMessages")(function (request) {
    var contents, _i, _a, message, parts_1, _b, _c, part, parts_2, _d, _e, part, parts, _f, _g, part;
    return __generator(this, function (_h) {
        switch (_h.label) {
            case 0:
                contents = [];
                _i = 0, _a = request.messages;
                _h.label = 1;
            case 1:
                if (!(_i < _a.length)) return [3 /*break*/, 20];
                message = _a[_i];
                if (!(message.role === "user")) return [3 /*break*/, 7];
                parts_1 = [];
                _b = 0, _c = message.content;
                _h.label = 2;
            case 2:
                if (!(_b < _c.length)) return [3 /*break*/, 6];
                part = _c[_b];
                if (!!shared_1.ProviderShared.supportsContent(part, ["text", "media"])) return [3 /*break*/, 4];
                return [5 /*yield**/, __values(shared_1.ProviderShared.unsupportedContent("Gemini", "user", ["text", "media"]))];
            case 3: return [2 /*return*/, _h.sent()];
            case 4:
                parts_1.push(lowerUserPart(part));
                _h.label = 5;
            case 5:
                _b++;
                return [3 /*break*/, 2];
            case 6:
                contents.push({ role: "user", parts: parts_1 });
                return [3 /*break*/, 19];
            case 7:
                if (!(message.role === "assistant")) return [3 /*break*/, 13];
                parts_2 = [];
                _d = 0, _e = message.content;
                _h.label = 8;
            case 8:
                if (!(_d < _e.length)) return [3 /*break*/, 12];
                part = _e[_d];
                if (!!shared_1.ProviderShared.supportsContent(part, ["text", "reasoning", "tool-call"])) return [3 /*break*/, 10];
                return [5 /*yield**/, __values(shared_1.ProviderShared.unsupportedContent("Gemini", "assistant", ["text", "reasoning", "tool-call"]))];
            case 9: return [2 /*return*/, _h.sent()];
            case 10:
                if (part.type === "text") {
                    parts_2.push({ text: part.text });
                    return [3 /*break*/, 11];
                }
                if (part.type === "reasoning") {
                    parts_2.push({ text: part.text, thought: true });
                    return [3 /*break*/, 11];
                }
                if (part.type === "tool-call") {
                    parts_2.push(lowerToolCall(part));
                    return [3 /*break*/, 11];
                }
                _h.label = 11;
            case 11:
                _d++;
                return [3 /*break*/, 8];
            case 12:
                contents.push({ role: "model", parts: parts_2 });
                return [3 /*break*/, 19];
            case 13:
                parts = [];
                _f = 0, _g = message.content;
                _h.label = 14;
            case 14:
                if (!(_f < _g.length)) return [3 /*break*/, 18];
                part = _g[_f];
                if (!!shared_1.ProviderShared.supportsContent(part, ["tool-result"])) return [3 /*break*/, 16];
                return [5 /*yield**/, __values(shared_1.ProviderShared.unsupportedContent("Gemini", "tool", ["tool-result"]))];
            case 15: return [2 /*return*/, _h.sent()];
            case 16:
                parts.push({
                    functionResponse: {
                        name: part.name,
                        response: {
                            name: part.name,
                            content: shared_1.ProviderShared.toolResultText(part),
                        },
                    },
                });
                _h.label = 17;
            case 17:
                _f++;
                return [3 /*break*/, 14];
            case 18:
                contents.push({ role: "user", parts: parts });
                _h.label = 19;
            case 19:
                _i++;
                return [3 /*break*/, 1];
            case 20: return [2 /*return*/, contents];
        }
    });
});
var geminiOptions = function (request) { var _a; return (_a = request.providerOptions) === null || _a === void 0 ? void 0 : _a.gemini; };
var thinkingConfig = function (request) {
    var _a;
    var value = (_a = geminiOptions(request)) === null || _a === void 0 ? void 0 : _a.thinkingConfig;
    if (!shared_1.ProviderShared.isRecord(value))
        return undefined;
    var result = {
        thinkingBudget: typeof value.thinkingBudget === "number" ? value.thinkingBudget : undefined,
        includeThoughts: typeof value.includeThoughts === "boolean" ? value.includeThoughts : undefined,
    };
    return Object.values(result).some(function (item) { return item !== undefined; }) ? result : undefined;
};
var fromRequest = effect_1.Effect.fn("Gemini.fromRequest")(function (request) {
    var toolsEnabled, generation, generationConfig, _a, _b;
    var _c;
    return __generator(this, function (_d) {
        switch (_d.label) {
            case 0:
                toolsEnabled = request.tools.length > 0 && ((_c = request.toolChoice) === null || _c === void 0 ? void 0 : _c.type) !== "none";
                generation = request.generation;
                generationConfig = {
                    maxOutputTokens: generation === null || generation === void 0 ? void 0 : generation.maxTokens,
                    temperature: generation === null || generation === void 0 ? void 0 : generation.temperature,
                    topP: generation === null || generation === void 0 ? void 0 : generation.topP,
                    topK: generation === null || generation === void 0 ? void 0 : generation.topK,
                    stopSequences: generation === null || generation === void 0 ? void 0 : generation.stop,
                    thinkingConfig: thinkingConfig(request),
                };
                _a = {};
                return [5 /*yield**/, __values(lowerMessages(request))];
            case 1:
                _a.contents = _d.sent(),
                    _a.systemInstruction = request.system.length === 0 ? undefined : { parts: [{ text: shared_1.ProviderShared.joinText(request.system) }] },
                    _a.tools = toolsEnabled ? [{ functionDeclarations: request.tools.map(lowerTool) }] : undefined;
                if (!(toolsEnabled && request.toolChoice)) return [3 /*break*/, 3];
                return [5 /*yield**/, __values(lowerToolConfig(request.toolChoice))];
            case 2:
                _b = _d.sent();
                return [3 /*break*/, 4];
            case 3:
                _b = undefined;
                _d.label = 4;
            case 4: return [2 /*return*/, (_a.toolConfig = _b,
                    _a.generationConfig = Object.values(generationConfig).some(function (value) { return value !== undefined; })
                        ? generationConfig
                        : undefined,
                    _a)];
        }
    });
});
// =============================================================================
// Stream Parsing
// =============================================================================
var mapUsage = function (usage) {
    if (!usage)
        return undefined;
    return new schema_1.Usage({
        inputTokens: usage.promptTokenCount,
        outputTokens: usage.candidatesTokenCount,
        reasoningTokens: usage.thoughtsTokenCount,
        cacheReadInputTokens: usage.cachedContentTokenCount,
        totalTokens: shared_1.ProviderShared.totalTokens(usage.promptTokenCount, usage.candidatesTokenCount, usage.totalTokenCount),
        native: usage,
    });
};
var mapFinishReason = function (finishReason, hasToolCalls) {
    if (finishReason === "STOP")
        return hasToolCalls ? "tool-calls" : "stop";
    if (finishReason === "MAX_TOKENS")
        return "length";
    if (finishReason === "IMAGE_SAFETY" ||
        finishReason === "RECITATION" ||
        finishReason === "SAFETY" ||
        finishReason === "BLOCKLIST" ||
        finishReason === "PROHIBITED_CONTENT" ||
        finishReason === "SPII")
        return "content-filter";
    if (finishReason === "MALFORMED_FUNCTION_CALL")
        return "error";
    return "unknown";
};
var finish = function (state) {
    return state.finishReason || state.usage
        ? [{ type: "request-finish", reason: mapFinishReason(state.finishReason, state.hasToolCalls), usage: state.usage }]
        : [];
};
var step = function (state, event) {
    var _a, _b, _c, _d;
    var nextState = __assign(__assign({}, state), { usage: event.usageMetadata ? ((_a = mapUsage(event.usageMetadata)) !== null && _a !== void 0 ? _a : state.usage) : state.usage });
    var candidate = (_b = event.candidates) === null || _b === void 0 ? void 0 : _b[0];
    if (!(candidate === null || candidate === void 0 ? void 0 : candidate.content))
        return effect_1.Effect.succeed([
            __assign(__assign({}, nextState), { finishReason: (_c = candidate === null || candidate === void 0 ? void 0 : candidate.finishReason) !== null && _c !== void 0 ? _c : nextState.finishReason }),
            [],
        ]);
    var events = [];
    var hasToolCalls = nextState.hasToolCalls;
    var nextToolCallId = nextState.nextToolCallId;
    for (var _i = 0, _e = candidate.content.parts; _i < _e.length; _i++) {
        var part = _e[_i];
        if ("text" in part && part.text.length > 0) {
            events.push({ type: part.thought ? "reasoning-delta" : "text-delta", text: part.text });
            continue;
        }
        if ("functionCall" in part) {
            var input = part.functionCall.args;
            var id = "tool_".concat(nextToolCallId++);
            events.push({ type: "tool-call", id: id, name: part.functionCall.name, input: input });
            hasToolCalls = true;
        }
    }
    return effect_1.Effect.succeed([
        __assign(__assign({}, nextState), { hasToolCalls: hasToolCalls, nextToolCallId: nextToolCallId, finishReason: (_d = candidate.finishReason) !== null && _d !== void 0 ? _d : nextState.finishReason }),
        events,
    ]);
};
// =============================================================================
// Protocol And Gemini Route
// =============================================================================
/**
 * The Gemini protocol — request body construction, body schema, and the
 * streaming-event state machine. Used by Google AI Studio Gemini and (once
 * registered) Vertex Gemini.
 */
exports.protocol = protocol_1.Protocol.make({
    id: ADAPTER,
    body: {
        schema: GeminiBody,
        from: fromRequest,
    },
    stream: {
        event: protocol_1.Protocol.jsonEvent(GeminiEvent),
        initial: function () { return ({ hasToolCalls: false, nextToolCallId: 0 }); },
        step: step,
        onHalt: finish,
    },
});
exports.route = client_1.Route.make({
    id: ADAPTER,
    protocol: exports.protocol,
    // Gemini's path embeds the model id and pins SSE framing at the URL level.
    endpoint: endpoint_1.Endpoint.path(function (_a) {
        var request = _a.request;
        return "/models/".concat(request.model.id, ":streamGenerateContent?alt=sse");
    }),
    auth: auth_1.Auth.apiKeyHeader("x-goog-api-key"),
    framing: framing_1.Framing.sse,
});
// =============================================================================
// Model Helper
// =============================================================================
exports.model = client_1.Route.model(exports.route, {
    provider: "google",
    baseURL: exports.DEFAULT_BASE_URL,
});
exports.Gemini = require("./gemini");
