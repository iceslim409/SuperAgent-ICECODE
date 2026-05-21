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
exports.AnthropicMessages = exports.model = exports.route = exports.protocol = exports.PATH = exports.DEFAULT_BASE_URL = void 0;
var effect_1 = require("effect");
var client_1 = require("../route/client");
var auth_1 = require("../route/auth");
var endpoint_1 = require("../route/endpoint");
var framing_1 = require("../route/framing");
var protocol_1 = require("../route/protocol");
var schema_1 = require("../schema");
var shared_1 = require("./shared");
var tool_stream_1 = require("./utils/tool-stream");
var ADAPTER = "anthropic-messages";
exports.DEFAULT_BASE_URL = "https://api.anthropic.com/v1";
exports.PATH = "/messages";
// =============================================================================
// Request Body Schema
// =============================================================================
var AnthropicCacheControl = effect_1.Schema.Struct({ type: effect_1.Schema.tag("ephemeral") });
var AnthropicTextBlock = effect_1.Schema.Struct({
    type: effect_1.Schema.tag("text"),
    text: effect_1.Schema.String,
    cache_control: effect_1.Schema.optional(AnthropicCacheControl),
});
var AnthropicThinkingBlock = effect_1.Schema.Struct({
    type: effect_1.Schema.tag("thinking"),
    thinking: effect_1.Schema.String,
    signature: effect_1.Schema.optional(effect_1.Schema.String),
    cache_control: effect_1.Schema.optional(AnthropicCacheControl),
});
var AnthropicToolUseBlock = effect_1.Schema.Struct({
    type: effect_1.Schema.tag("tool_use"),
    id: effect_1.Schema.String,
    name: effect_1.Schema.String,
    input: effect_1.Schema.Unknown,
    cache_control: effect_1.Schema.optional(AnthropicCacheControl),
});
var AnthropicServerToolUseBlock = effect_1.Schema.Struct({
    type: effect_1.Schema.tag("server_tool_use"),
    id: effect_1.Schema.String,
    name: effect_1.Schema.String,
    input: effect_1.Schema.Unknown,
    cache_control: effect_1.Schema.optional(AnthropicCacheControl),
});
// Server tool result blocks: web_search_tool_result, code_execution_tool_result,
// and web_fetch_tool_result. The provider executes the tool and inlines the
// structured result into the assistant turn — there is no client tool_result
// round-trip. We round-trip the structured `content` payload as opaque JSON so
// the next request can echo it back when continuing the conversation.
var AnthropicServerToolResultType = effect_1.Schema.Literals([
    "web_search_tool_result",
    "code_execution_tool_result",
    "web_fetch_tool_result",
]);
var AnthropicServerToolResultBlock = effect_1.Schema.Struct({
    type: AnthropicServerToolResultType,
    tool_use_id: effect_1.Schema.String,
    content: effect_1.Schema.Unknown,
    cache_control: effect_1.Schema.optional(AnthropicCacheControl),
});
var AnthropicToolResultBlock = effect_1.Schema.Struct({
    type: effect_1.Schema.tag("tool_result"),
    tool_use_id: effect_1.Schema.String,
    content: effect_1.Schema.String,
    is_error: effect_1.Schema.optional(effect_1.Schema.Boolean),
    cache_control: effect_1.Schema.optional(AnthropicCacheControl),
});
var AnthropicUserBlock = effect_1.Schema.Union([AnthropicTextBlock, AnthropicToolResultBlock]);
var AnthropicAssistantBlock = effect_1.Schema.Union([
    AnthropicTextBlock,
    AnthropicThinkingBlock,
    AnthropicToolUseBlock,
    AnthropicServerToolUseBlock,
    AnthropicServerToolResultBlock,
]);
var AnthropicMessage = effect_1.Schema.Union([
    effect_1.Schema.Struct({ role: effect_1.Schema.Literal("user"), content: effect_1.Schema.Array(AnthropicUserBlock) }),
    effect_1.Schema.Struct({ role: effect_1.Schema.Literal("assistant"), content: effect_1.Schema.Array(AnthropicAssistantBlock) }),
]).pipe(effect_1.Schema.toTaggedUnion("role"));
var AnthropicTool = effect_1.Schema.Struct({
    name: effect_1.Schema.String,
    description: effect_1.Schema.String,
    input_schema: shared_1.JsonObject,
    cache_control: effect_1.Schema.optional(AnthropicCacheControl),
});
var AnthropicToolChoice = effect_1.Schema.Union([
    effect_1.Schema.Struct({ type: effect_1.Schema.Literals(["auto", "any"]) }),
    effect_1.Schema.Struct({ type: effect_1.Schema.tag("tool"), name: effect_1.Schema.String }),
]);
var AnthropicThinking = effect_1.Schema.Struct({
    type: effect_1.Schema.tag("enabled"),
    budget_tokens: effect_1.Schema.Number,
});
var AnthropicBodyFields = {
    model: effect_1.Schema.String,
    system: (0, shared_1.optionalArray)(AnthropicTextBlock),
    messages: effect_1.Schema.Array(AnthropicMessage),
    tools: (0, shared_1.optionalArray)(AnthropicTool),
    tool_choice: effect_1.Schema.optional(AnthropicToolChoice),
    stream: effect_1.Schema.Literal(true),
    max_tokens: effect_1.Schema.Number,
    temperature: effect_1.Schema.optional(effect_1.Schema.Number),
    top_p: effect_1.Schema.optional(effect_1.Schema.Number),
    top_k: effect_1.Schema.optional(effect_1.Schema.Number),
    stop_sequences: (0, shared_1.optionalArray)(effect_1.Schema.String),
    thinking: effect_1.Schema.optional(AnthropicThinking),
};
var AnthropicMessagesBody = effect_1.Schema.Struct(AnthropicBodyFields);
var AnthropicUsage = effect_1.Schema.Struct({
    input_tokens: effect_1.Schema.optional(effect_1.Schema.Number),
    output_tokens: effect_1.Schema.optional(effect_1.Schema.Number),
    cache_creation_input_tokens: (0, shared_1.optionalNull)(effect_1.Schema.Number),
    cache_read_input_tokens: (0, shared_1.optionalNull)(effect_1.Schema.Number),
});
var AnthropicStreamBlock = effect_1.Schema.Struct({
    type: effect_1.Schema.String,
    id: effect_1.Schema.optional(effect_1.Schema.String),
    name: effect_1.Schema.optional(effect_1.Schema.String),
    text: effect_1.Schema.optional(effect_1.Schema.String),
    thinking: effect_1.Schema.optional(effect_1.Schema.String),
    signature: effect_1.Schema.optional(effect_1.Schema.String),
    input: effect_1.Schema.optional(effect_1.Schema.Unknown),
    // *_tool_result blocks arrive whole as content_block_start (no streaming
    // delta) with the structured payload in `content` and the originating
    // server_tool_use id in `tool_use_id`.
    tool_use_id: effect_1.Schema.optional(effect_1.Schema.String),
    content: effect_1.Schema.optional(effect_1.Schema.Unknown),
});
var AnthropicStreamDelta = effect_1.Schema.Struct({
    type: effect_1.Schema.optional(effect_1.Schema.String),
    text: effect_1.Schema.optional(effect_1.Schema.String),
    thinking: effect_1.Schema.optional(effect_1.Schema.String),
    partial_json: effect_1.Schema.optional(effect_1.Schema.String),
    signature: effect_1.Schema.optional(effect_1.Schema.String),
    stop_reason: (0, shared_1.optionalNull)(effect_1.Schema.String),
    stop_sequence: (0, shared_1.optionalNull)(effect_1.Schema.String),
});
var AnthropicEvent = effect_1.Schema.Struct({
    type: effect_1.Schema.String,
    index: effect_1.Schema.optional(effect_1.Schema.Number),
    message: effect_1.Schema.optional(effect_1.Schema.Struct({ usage: effect_1.Schema.optional(AnthropicUsage) })),
    content_block: effect_1.Schema.optional(AnthropicStreamBlock),
    delta: effect_1.Schema.optional(AnthropicStreamDelta),
    usage: effect_1.Schema.optional(AnthropicUsage),
    error: effect_1.Schema.optional(effect_1.Schema.Struct({ type: effect_1.Schema.String, message: effect_1.Schema.String })),
});
var invalid = shared_1.ProviderShared.invalidRequest;
// =============================================================================
// Request Lowering
// =============================================================================
var cacheControl = function (cache) {
    return (cache === null || cache === void 0 ? void 0 : cache.type) === "ephemeral" ? { type: "ephemeral" } : undefined;
};
var anthropicMetadata = function (metadata) { return ({ anthropic: metadata }); };
var signatureFromMetadata = function (metadata) {
    var anthropic = metadata === null || metadata === void 0 ? void 0 : metadata.anthropic;
    if (!shared_1.ProviderShared.isRecord(anthropic))
        return undefined;
    return typeof anthropic.signature === "string" ? anthropic.signature : undefined;
};
var lowerTool = function (tool) { return ({
    name: tool.name,
    description: tool.description,
    input_schema: tool.inputSchema,
}); };
var lowerToolChoice = function (toolChoice) {
    return shared_1.ProviderShared.matchToolChoice("Anthropic Messages", toolChoice, {
        auto: function () { return ({ type: "auto" }); },
        none: function () { return undefined; },
        required: function () { return ({ type: "any" }); },
        tool: function (name) { return ({ type: "tool", name: name }); },
    });
};
var lowerToolCall = function (part) { return ({
    type: "tool_use",
    id: part.id,
    name: part.name,
    input: part.input,
}); };
var lowerServerToolCall = function (part) { return ({
    type: "server_tool_use",
    id: part.id,
    name: part.name,
    input: part.input,
}); };
// Server tool result blocks are typed by name. Anthropic ships three today;
// extend this list when new server tools land. The block content is the
// structured payload returned by the provider, which we round-trip as-is.
var serverToolResultType = function (name) {
    if (name === "web_search")
        return "web_search_tool_result";
    if (name === "code_execution")
        return "code_execution_tool_result";
    if (name === "web_fetch")
        return "web_fetch_tool_result";
    return undefined;
};
var lowerServerToolResult = effect_1.Effect.fn("AnthropicMessages.lowerServerToolResult")(function (part) {
    var wireType;
    return __generator(this, function (_a) {
        switch (_a.label) {
            case 0:
                wireType = serverToolResultType(part.name);
                if (!!wireType) return [3 /*break*/, 2];
                return [5 /*yield**/, __values(invalid("Anthropic Messages does not know how to round-trip server tool result for ".concat(part.name)))];
            case 1: return [2 /*return*/, _a.sent()];
            case 2: return [2 /*return*/, { type: wireType, tool_use_id: part.id, content: part.result.value }];
        }
    });
});
var lowerMessages = effect_1.Effect.fn("AnthropicMessages.lowerMessages")(function (request) {
    var messages, _i, _a, message, content_1, _b, _c, part, content_2, _d, _e, part, _f, _g, content, _h, _j, part;
    var _k;
    return __generator(this, function (_l) {
        switch (_l.label) {
            case 0:
                messages = [];
                _i = 0, _a = request.messages;
                _l.label = 1;
            case 1:
                if (!(_i < _a.length)) return [3 /*break*/, 21];
                message = _a[_i];
                if (!(message.role === "user")) return [3 /*break*/, 7];
                content_1 = [];
                _b = 0, _c = message.content;
                _l.label = 2;
            case 2:
                if (!(_b < _c.length)) return [3 /*break*/, 6];
                part = _c[_b];
                if (!!shared_1.ProviderShared.supportsContent(part, ["text"])) return [3 /*break*/, 4];
                return [5 /*yield**/, __values(shared_1.ProviderShared.unsupportedContent("Anthropic Messages", "user", ["text"]))];
            case 3: return [2 /*return*/, _l.sent()];
            case 4:
                content_1.push({ type: "text", text: part.text, cache_control: cacheControl(part.cache) });
                _l.label = 5;
            case 5:
                _b++;
                return [3 /*break*/, 2];
            case 6:
                messages.push({ role: "user", content: content_1 });
                return [3 /*break*/, 20];
            case 7:
                if (!(message.role === "assistant")) return [3 /*break*/, 14];
                content_2 = [];
                _d = 0, _e = message.content;
                _l.label = 8;
            case 8:
                if (!(_d < _e.length)) return [3 /*break*/, 13];
                part = _e[_d];
                if (part.type === "text") {
                    content_2.push({ type: "text", text: part.text, cache_control: cacheControl(part.cache) });
                    return [3 /*break*/, 12];
                }
                if (part.type === "reasoning") {
                    content_2.push({
                        type: "thinking",
                        thinking: part.text,
                        signature: (_k = part.encrypted) !== null && _k !== void 0 ? _k : signatureFromMetadata(part.providerMetadata),
                    });
                    return [3 /*break*/, 12];
                }
                if (part.type === "tool-call") {
                    content_2.push(part.providerExecuted ? lowerServerToolCall(part) : lowerToolCall(part));
                    return [3 /*break*/, 12];
                }
                if (!(part.type === "tool-result" && part.providerExecuted)) return [3 /*break*/, 10];
                _g = (_f = content_2).push;
                return [5 /*yield**/, __values(lowerServerToolResult(part))];
            case 9:
                _g.apply(_f, [_l.sent()]);
                return [3 /*break*/, 12];
            case 10: return [5 /*yield**/, __values(invalid("Anthropic Messages assistant messages only support text, reasoning, and tool-call content for now"))];
            case 11: return [2 /*return*/, _l.sent()];
            case 12:
                _d++;
                return [3 /*break*/, 8];
            case 13:
                messages.push({ role: "assistant", content: content_2 });
                return [3 /*break*/, 20];
            case 14:
                content = [];
                _h = 0, _j = message.content;
                _l.label = 15;
            case 15:
                if (!(_h < _j.length)) return [3 /*break*/, 19];
                part = _j[_h];
                if (!!shared_1.ProviderShared.supportsContent(part, ["tool-result"])) return [3 /*break*/, 17];
                return [5 /*yield**/, __values(shared_1.ProviderShared.unsupportedContent("Anthropic Messages", "tool", ["tool-result"]))];
            case 16: return [2 /*return*/, _l.sent()];
            case 17:
                content.push({
                    type: "tool_result",
                    tool_use_id: part.id,
                    content: shared_1.ProviderShared.toolResultText(part),
                    is_error: part.result.type === "error" ? true : undefined,
                });
                _l.label = 18;
            case 18:
                _h++;
                return [3 /*break*/, 15];
            case 19:
                messages.push({ role: "user", content: content });
                _l.label = 20;
            case 20:
                _i++;
                return [3 /*break*/, 1];
            case 21: return [2 /*return*/, messages];
        }
    });
});
var anthropicOptions = function (request) { var _a; return (_a = request.providerOptions) === null || _a === void 0 ? void 0 : _a.anthropic; };
var lowerThinking = effect_1.Effect.fn("AnthropicMessages.lowerThinking")(function (request) {
    var thinking, budget;
    var _a;
    return __generator(this, function (_b) {
        switch (_b.label) {
            case 0:
                thinking = (_a = anthropicOptions(request)) === null || _a === void 0 ? void 0 : _a.thinking;
                if (!shared_1.ProviderShared.isRecord(thinking) || thinking.type !== "enabled")
                    return [2 /*return*/, undefined];
                budget = typeof thinking.budgetTokens === "number"
                    ? thinking.budgetTokens
                    : typeof thinking.budget_tokens === "number"
                        ? thinking.budget_tokens
                        : undefined;
                if (!(budget === undefined)) return [3 /*break*/, 2];
                return [5 /*yield**/, __values(invalid("Anthropic thinking provider option requires budgetTokens"))];
            case 1: return [2 /*return*/, _b.sent()];
            case 2: return [2 /*return*/, { type: "enabled", budget_tokens: budget }];
        }
    });
});
var fromRequest = effect_1.Effect.fn("AnthropicMessages.fromRequest")(function (request) {
    var toolChoice, _a, generation, _b;
    var _c, _d, _e;
    return __generator(this, function (_f) {
        switch (_f.label) {
            case 0:
                if (!request.toolChoice) return [3 /*break*/, 2];
                return [5 /*yield**/, __values(lowerToolChoice(request.toolChoice))];
            case 1:
                _a = _f.sent();
                return [3 /*break*/, 3];
            case 2:
                _a = undefined;
                _f.label = 3;
            case 3:
                toolChoice = _a;
                generation = request.generation;
                _b = {
                    model: request.model.id,
                    system: request.system.length === 0
                        ? undefined
                        : request.system.map(function (part) { return ({
                            type: "text",
                            text: part.text,
                            cache_control: cacheControl(part.cache),
                        }); })
                };
                return [5 /*yield**/, __values(lowerMessages(request))];
            case 4:
                _b.messages = _f.sent(),
                    _b.tools = request.tools.length === 0 || ((_c = request.toolChoice) === null || _c === void 0 ? void 0 : _c.type) === "none" ? undefined : request.tools.map(lowerTool),
                    _b.tool_choice = toolChoice,
                    _b.stream = true,
                    _b.max_tokens = (_e = (_d = generation === null || generation === void 0 ? void 0 : generation.maxTokens) !== null && _d !== void 0 ? _d : request.model.limits.output) !== null && _e !== void 0 ? _e : 4096,
                    _b.temperature = generation === null || generation === void 0 ? void 0 : generation.temperature,
                    _b.top_p = generation === null || generation === void 0 ? void 0 : generation.topP,
                    _b.top_k = generation === null || generation === void 0 ? void 0 : generation.topK,
                    _b.stop_sequences = generation === null || generation === void 0 ? void 0 : generation.stop;
                return [5 /*yield**/, __values(lowerThinking(request))];
            case 5: return [2 /*return*/, (_b.thinking = _f.sent(),
                    _b)];
        }
    });
});
// =============================================================================
// Stream Parsing
// =============================================================================
var mapFinishReason = function (reason) {
    if (reason === "end_turn" || reason === "stop_sequence" || reason === "pause_turn")
        return "stop";
    if (reason === "max_tokens")
        return "length";
    if (reason === "tool_use")
        return "tool-calls";
    if (reason === "refusal")
        return "content-filter";
    return "unknown";
};
var mapUsage = function (usage) {
    var _a, _b;
    if (!usage)
        return undefined;
    return new schema_1.Usage({
        inputTokens: usage.input_tokens,
        outputTokens: usage.output_tokens,
        cacheReadInputTokens: (_a = usage.cache_read_input_tokens) !== null && _a !== void 0 ? _a : undefined,
        cacheWriteInputTokens: (_b = usage.cache_creation_input_tokens) !== null && _b !== void 0 ? _b : undefined,
        totalTokens: shared_1.ProviderShared.totalTokens(usage.input_tokens, usage.output_tokens, undefined),
        native: usage,
    });
};
// Anthropic emits usage on `message_start` and again on `message_delta` — the
// final delta carries the authoritative totals. Right-biased merge: each
// field prefers `right` when defined, falls back to `left`. `totalTokens` is
// recomputed from the merged input/output to stay consistent.
var mergeUsage = function (left, right) {
    var _a, _b, _c, _d;
    if (!left)
        return right;
    if (!right)
        return left;
    var inputTokens = (_a = right.inputTokens) !== null && _a !== void 0 ? _a : left.inputTokens;
    var outputTokens = (_b = right.outputTokens) !== null && _b !== void 0 ? _b : left.outputTokens;
    return new schema_1.Usage({
        inputTokens: inputTokens,
        outputTokens: outputTokens,
        cacheReadInputTokens: (_c = right.cacheReadInputTokens) !== null && _c !== void 0 ? _c : left.cacheReadInputTokens,
        cacheWriteInputTokens: (_d = right.cacheWriteInputTokens) !== null && _d !== void 0 ? _d : left.cacheWriteInputTokens,
        totalTokens: shared_1.ProviderShared.totalTokens(inputTokens, outputTokens, undefined),
        native: __assign(__assign({}, left.native), right.native),
    });
};
// Server tool result blocks come whole in `content_block_start` (no streaming
// delta sequence). We convert the payload to a `tool-result` event with
// `providerExecuted: true`. The runtime appends it to the assistant message
// for round-trip; downstream consumers can inspect `result.value` for the
// structured payload.
var SERVER_TOOL_RESULT_NAMES = {
    web_search_tool_result: "web_search",
    code_execution_tool_result: "code_execution",
    web_fetch_tool_result: "web_fetch",
};
var isServerToolResultType = function (type) { return type in SERVER_TOOL_RESULT_NAMES; };
var serverToolResultEvent = function (block) {
    var _a;
    if (!block.type || !isServerToolResultType(block.type))
        return undefined;
    var errorPayload = typeof block.content === "object" && block.content !== null && "type" in block.content
        ? String(block.content.type)
        : "";
    var isError = errorPayload.endsWith("_tool_result_error");
    return {
        type: "tool-result",
        id: (_a = block.tool_use_id) !== null && _a !== void 0 ? _a : "",
        name: SERVER_TOOL_RESULT_NAMES[block.type],
        result: isError ? { type: "error", value: block.content } : { type: "json", value: block.content },
        providerExecuted: true,
        providerMetadata: anthropicMetadata({ blockType: block.type }),
    };
};
var NO_EVENTS = [];
var onMessageStart = function (state, event) {
    var _a;
    var usage = mapUsage((_a = event.message) === null || _a === void 0 ? void 0 : _a.usage);
    return [usage ? __assign(__assign({}, state), { usage: mergeUsage(state.usage, usage) }) : state, NO_EVENTS];
};
var onContentBlockStart = function (state, event) {
    var _a, _b;
    var block = event.content_block;
    if (!block)
        return [state, NO_EVENTS];
    if ((block.type === "tool_use" || block.type === "server_tool_use") && event.index !== undefined) {
        return [
            __assign(__assign({}, state), { tools: tool_stream_1.ToolStream.start(state.tools, event.index, {
                    id: (_a = block.id) !== null && _a !== void 0 ? _a : String(event.index),
                    name: (_b = block.name) !== null && _b !== void 0 ? _b : "",
                    providerExecuted: block.type === "server_tool_use",
                }) }),
            NO_EVENTS,
        ];
    }
    if (block.type === "text" && block.text) {
        return [state, [{ type: "text-delta", text: block.text }]];
    }
    if (block.type === "thinking" && block.thinking) {
        return [
            state,
            [
                __assign({ type: "reasoning-delta", text: block.thinking }, (block.signature ? { providerMetadata: anthropicMetadata({ signature: block.signature }) } : {})),
            ],
        ];
    }
    var result = serverToolResultEvent(block);
    return [state, result ? [result] : NO_EVENTS];
};
var onContentBlockDelta = effect_1.Effect.fn("AnthropicMessages.onContentBlockDelta")(function (state, event) {
    var delta, result;
    return __generator(this, function (_a) {
        switch (_a.label) {
            case 0:
                delta = event.delta;
                if ((delta === null || delta === void 0 ? void 0 : delta.type) === "text_delta" && delta.text) {
                    return [2 /*return*/, [state, [{ type: "text-delta", text: delta.text }]]];
                }
                if ((delta === null || delta === void 0 ? void 0 : delta.type) === "thinking_delta" && delta.thinking) {
                    return [2 /*return*/, [state, [{ type: "reasoning-delta", text: delta.thinking }]]];
                }
                if ((delta === null || delta === void 0 ? void 0 : delta.type) === "signature_delta" && delta.signature) {
                    return [2 /*return*/, [
                            state,
                            [{ type: "reasoning-delta", text: "", providerMetadata: anthropicMetadata({ signature: delta.signature }) }],
                        ]];
                }
                if (!((delta === null || delta === void 0 ? void 0 : delta.type) === "input_json_delta" && event.index !== undefined)) return [3 /*break*/, 3];
                if (!delta.partial_json)
                    return [2 /*return*/, [state, NO_EVENTS]];
                result = tool_stream_1.ToolStream.appendExisting(ADAPTER, state.tools, event.index, delta.partial_json, "Anthropic Messages tool argument delta is missing its tool call");
                if (!tool_stream_1.ToolStream.isError(result)) return [3 /*break*/, 2];
                return [5 /*yield**/, __values(result)];
            case 1: return [2 /*return*/, _a.sent()];
            case 2: return [2 /*return*/, [__assign(__assign({}, state), { tools: result.tools }), result.event ? [result.event] : NO_EVENTS]];
            case 3: return [2 /*return*/, [state, NO_EVENTS]];
        }
    });
});
var onContentBlockStop = effect_1.Effect.fn("AnthropicMessages.onContentBlockStop")(function (state, event) {
    var result;
    return __generator(this, function (_a) {
        switch (_a.label) {
            case 0:
                if (event.index === undefined)
                    return [2 /*return*/, [state, NO_EVENTS]];
                return [5 /*yield**/, __values(tool_stream_1.ToolStream.finish(ADAPTER, state.tools, event.index))];
            case 1:
                result = _a.sent();
                return [2 /*return*/, [__assign(__assign({}, state), { tools: result.tools }), result.event ? [result.event] : NO_EVENTS]];
        }
    });
});
var onMessageDelta = function (state, event) {
    var _a, _b;
    var usage = mergeUsage(state.usage, mapUsage(event.usage));
    return [
        __assign(__assign({}, state), { usage: usage }),
        [
            __assign({ type: "request-finish", reason: mapFinishReason((_a = event.delta) === null || _a === void 0 ? void 0 : _a.stop_reason), usage: usage }, (((_b = event.delta) === null || _b === void 0 ? void 0 : _b.stop_sequence)
                ? { providerMetadata: anthropicMetadata({ stopSequence: event.delta.stop_sequence }) }
                : {})),
        ],
    ];
};
var onError = function (state, event) {
    var _a, _b;
    return [
        state,
        [{ type: "provider-error", message: (_b = (_a = event.error) === null || _a === void 0 ? void 0 : _a.message) !== null && _b !== void 0 ? _b : "Anthropic Messages stream error" }],
    ];
};
var step = function (state, event) {
    if (event.type === "message_start")
        return effect_1.Effect.succeed(onMessageStart(state, event));
    if (event.type === "content_block_start")
        return effect_1.Effect.succeed(onContentBlockStart(state, event));
    if (event.type === "content_block_delta")
        return onContentBlockDelta(state, event);
    if (event.type === "content_block_stop")
        return onContentBlockStop(state, event);
    if (event.type === "message_delta")
        return effect_1.Effect.succeed(onMessageDelta(state, event));
    if (event.type === "error")
        return effect_1.Effect.succeed(onError(state, event));
    return effect_1.Effect.succeed([state, NO_EVENTS]);
};
// =============================================================================
// Protocol And Anthropic Route
// =============================================================================
/**
 * The Anthropic Messages protocol — request body construction, body schema,
 * and the streaming-event state machine. Used by native Anthropic Cloud and
 * (once registered) Vertex Anthropic / Bedrock-hosted Anthropic passthrough.
 */
exports.protocol = protocol_1.Protocol.make({
    id: ADAPTER,
    body: {
        schema: AnthropicMessagesBody,
        from: fromRequest,
    },
    stream: {
        event: protocol_1.Protocol.jsonEvent(AnthropicEvent),
        initial: function () { return ({ tools: tool_stream_1.ToolStream.empty() }); },
        step: step,
    },
});
exports.route = client_1.Route.make({
    id: ADAPTER,
    protocol: exports.protocol,
    endpoint: endpoint_1.Endpoint.path(exports.PATH),
    auth: auth_1.Auth.apiKeyHeader("x-api-key"),
    framing: framing_1.Framing.sse,
    headers: function () { return ({ "anthropic-version": "2023-06-01" }); },
});
// =============================================================================
// Model Helper
// =============================================================================
exports.model = client_1.Route.model(exports.route, {
    provider: "anthropic",
    baseURL: exports.DEFAULT_BASE_URL,
});
exports.AnthropicMessages = require("./anthropic-messages");
