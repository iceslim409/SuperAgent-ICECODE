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
var __rest = (this && this.__rest) || function (s, e) {
    var t = {};
    for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0)
        t[p] = s[p];
    if (s != null && typeof Object.getOwnPropertySymbols === "function")
        for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
            if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i]))
                t[p[i]] = s[p[i]];
        }
    return t;
};
var __spreadArray = (this && this.__spreadArray) || function (to, from, pack) {
    if (pack || arguments.length === 2) for (var i = 0, l = from.length, ar; i < l; i++) {
        if (ar || !(i in from)) {
            if (!ar) ar = Array.prototype.slice.call(from, 0, i);
            ar[i] = from[i];
        }
    }
    return to.concat(ar || Array.prototype.slice.call(from));
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
exports.OpenAIResponses = exports.webSocketModel = exports.model = exports.webSocketRoute = exports.webSocketTransport = exports.route = exports.httpTransport = exports.protocol = exports.PATH = exports.DEFAULT_BASE_URL = void 0;
var effect_1 = require("effect");
var client_1 = require("../route/client");
var auth_1 = require("../route/auth");
var endpoint_1 = require("../route/endpoint");
var framing_1 = require("../route/framing");
var transport_1 = require("../route/transport");
var protocol_1 = require("../route/protocol");
var schema_1 = require("../schema");
var shared_1 = require("./shared");
var openai_options_1 = require("./utils/openai-options");
var tool_stream_1 = require("./utils/tool-stream");
var ADAPTER = "openai-responses";
exports.DEFAULT_BASE_URL = "https://api.openai.com/v1";
exports.PATH = "/responses";
// =============================================================================
// Request Body Schema
// =============================================================================
var OpenAIResponsesInputText = effect_1.Schema.Struct({
    type: effect_1.Schema.tag("input_text"),
    text: effect_1.Schema.String,
});
var OpenAIResponsesOutputText = effect_1.Schema.Struct({
    type: effect_1.Schema.tag("output_text"),
    text: effect_1.Schema.String,
});
var OpenAIResponsesInputItem = effect_1.Schema.Union([
    effect_1.Schema.Struct({ role: effect_1.Schema.tag("system"), content: effect_1.Schema.String }),
    effect_1.Schema.Struct({ role: effect_1.Schema.tag("user"), content: effect_1.Schema.Array(OpenAIResponsesInputText) }),
    effect_1.Schema.Struct({ role: effect_1.Schema.tag("assistant"), content: effect_1.Schema.Array(OpenAIResponsesOutputText) }),
    effect_1.Schema.Struct({
        type: effect_1.Schema.tag("function_call"),
        call_id: effect_1.Schema.String,
        name: effect_1.Schema.String,
        arguments: effect_1.Schema.String,
    }),
    effect_1.Schema.Struct({
        type: effect_1.Schema.tag("function_call_output"),
        call_id: effect_1.Schema.String,
        output: effect_1.Schema.String,
    }),
]);
var OpenAIResponsesTool = effect_1.Schema.Struct({
    type: effect_1.Schema.tag("function"),
    name: effect_1.Schema.String,
    description: effect_1.Schema.String,
    parameters: shared_1.JsonObject,
    strict: effect_1.Schema.optional(effect_1.Schema.Boolean),
});
var OpenAIResponsesToolChoice = effect_1.Schema.Union([
    effect_1.Schema.Literals(["auto", "none", "required"]),
    effect_1.Schema.Struct({ type: effect_1.Schema.tag("function"), name: effect_1.Schema.String }),
]);
// Fields shared between the HTTP body and the WebSocket `response.create`
// message. The HTTP body adds `stream: true`; the WebSocket message adds
// `type: "response.create"`. Defining the shared shape once keeps the two
// transports in sync without a destructure-and-strip dance.
var OpenAIResponsesCoreFields = {
    model: effect_1.Schema.String,
    input: effect_1.Schema.Array(OpenAIResponsesInputItem),
    tools: (0, shared_1.optionalArray)(OpenAIResponsesTool),
    tool_choice: effect_1.Schema.optional(OpenAIResponsesToolChoice),
    store: effect_1.Schema.optional(effect_1.Schema.Boolean),
    prompt_cache_key: effect_1.Schema.optional(effect_1.Schema.String),
    include: (0, shared_1.optionalArray)(effect_1.Schema.Literal("reasoning.encrypted_content")),
    reasoning: effect_1.Schema.optional(effect_1.Schema.Struct({
        effort: effect_1.Schema.optional(openai_options_1.OpenAIOptions.OpenAIReasoningEffort),
        summary: effect_1.Schema.optional(effect_1.Schema.Literal("auto")),
    })),
    text: effect_1.Schema.optional(effect_1.Schema.Struct({
        verbosity: effect_1.Schema.optional(openai_options_1.OpenAIOptions.OpenAITextVerbosity),
    })),
    max_output_tokens: effect_1.Schema.optional(effect_1.Schema.Number),
    temperature: effect_1.Schema.optional(effect_1.Schema.Number),
    top_p: effect_1.Schema.optional(effect_1.Schema.Number),
};
var OpenAIResponsesBody = effect_1.Schema.Struct(__assign(__assign({}, OpenAIResponsesCoreFields), { stream: effect_1.Schema.Literal(true) }));
var OpenAIResponsesWebSocketMessage = effect_1.Schema.StructWithRest(effect_1.Schema.Struct(__assign({ type: effect_1.Schema.tag("response.create") }, OpenAIResponsesCoreFields)), [effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.Unknown)]);
var encodeWebSocketMessage = effect_1.Schema.encodeSync(effect_1.Schema.fromJsonString(OpenAIResponsesWebSocketMessage));
var OpenAIResponsesUsage = effect_1.Schema.Struct({
    input_tokens: effect_1.Schema.optional(effect_1.Schema.Number),
    input_tokens_details: (0, shared_1.optionalNull)(effect_1.Schema.Struct({ cached_tokens: effect_1.Schema.optional(effect_1.Schema.Number) })),
    output_tokens: effect_1.Schema.optional(effect_1.Schema.Number),
    output_tokens_details: (0, shared_1.optionalNull)(effect_1.Schema.Struct({ reasoning_tokens: effect_1.Schema.optional(effect_1.Schema.Number) })),
    total_tokens: effect_1.Schema.optional(effect_1.Schema.Number),
});
var OpenAIResponsesStreamItem = effect_1.Schema.Struct({
    type: effect_1.Schema.String,
    id: effect_1.Schema.optional(effect_1.Schema.String),
    call_id: effect_1.Schema.optional(effect_1.Schema.String),
    name: effect_1.Schema.optional(effect_1.Schema.String),
    arguments: effect_1.Schema.optional(effect_1.Schema.String),
    // Hosted (provider-executed) tool fields. Each hosted tool item carries its
    // own subset of these — we capture them generically so we can surface the
    // call's typed input portion and round-trip the full result payload without
    // hand-rolling a per-tool schema.
    status: effect_1.Schema.optional(effect_1.Schema.String),
    action: effect_1.Schema.optional(effect_1.Schema.Unknown),
    queries: effect_1.Schema.optional(effect_1.Schema.Unknown),
    results: effect_1.Schema.optional(effect_1.Schema.Unknown),
    code: effect_1.Schema.optional(effect_1.Schema.String),
    container_id: effect_1.Schema.optional(effect_1.Schema.String),
    outputs: effect_1.Schema.optional(effect_1.Schema.Unknown),
    server_label: effect_1.Schema.optional(effect_1.Schema.String),
    output: effect_1.Schema.optional(effect_1.Schema.Unknown),
    error: effect_1.Schema.optional(effect_1.Schema.Unknown),
});
var OpenAIResponsesEvent = effect_1.Schema.Struct({
    type: effect_1.Schema.String,
    delta: effect_1.Schema.optional(effect_1.Schema.String),
    item_id: effect_1.Schema.optional(effect_1.Schema.String),
    item: effect_1.Schema.optional(OpenAIResponsesStreamItem),
    response: effect_1.Schema.optional(effect_1.Schema.Struct({
        id: effect_1.Schema.optional(effect_1.Schema.String),
        service_tier: effect_1.Schema.optional(effect_1.Schema.String),
        incomplete_details: (0, shared_1.optionalNull)(effect_1.Schema.Struct({ reason: effect_1.Schema.String })),
        usage: (0, shared_1.optionalNull)(OpenAIResponsesUsage),
    })),
    code: effect_1.Schema.optional(effect_1.Schema.String),
    message: effect_1.Schema.optional(effect_1.Schema.String),
});
var invalid = shared_1.ProviderShared.invalidRequest;
// =============================================================================
// Request Lowering
// =============================================================================
var lowerTool = function (tool) { return ({
    type: "function",
    name: tool.name,
    description: tool.description,
    parameters: tool.inputSchema,
}); };
var lowerToolChoice = function (toolChoice) {
    return shared_1.ProviderShared.matchToolChoice("OpenAI Responses", toolChoice, {
        auto: function () { return "auto"; },
        none: function () { return "none"; },
        required: function () { return "required"; },
        tool: function (name) { return ({ type: "function", name: name }); },
    });
};
var lowerToolCall = function (part) { return ({
    type: "function_call",
    call_id: part.id,
    name: part.name,
    arguments: shared_1.ProviderShared.encodeJson(part.input),
}); };
var lowerMessages = effect_1.Effect.fn("OpenAIResponses.lowerMessages")(function (request) {
    var system, input, _i, _a, message, content, _b, _c, part, content, _d, _e, part, _f, _g, part;
    return __generator(this, function (_h) {
        switch (_h.label) {
            case 0:
                system = request.system.length === 0 ? [] : [{ role: "system", content: shared_1.ProviderShared.joinText(request.system) }];
                input = __spreadArray([], system, true);
                _i = 0, _a = request.messages;
                _h.label = 1;
            case 1:
                if (!(_i < _a.length)) return [3 /*break*/, 19];
                message = _a[_i];
                if (!(message.role === "user")) return [3 /*break*/, 7];
                content = [];
                _b = 0, _c = message.content;
                _h.label = 2;
            case 2:
                if (!(_b < _c.length)) return [3 /*break*/, 6];
                part = _c[_b];
                if (!!shared_1.ProviderShared.supportsContent(part, ["text"])) return [3 /*break*/, 4];
                return [5 /*yield**/, __values(shared_1.ProviderShared.unsupportedContent("OpenAI Responses", "user", ["text"]))];
            case 3: return [2 /*return*/, _h.sent()];
            case 4:
                content.push(part);
                _h.label = 5;
            case 5:
                _b++;
                return [3 /*break*/, 2];
            case 6:
                input.push({ role: "user", content: content.map(function (part) { return ({ type: "input_text", text: part.text }); }) });
                return [3 /*break*/, 18];
            case 7:
                if (!(message.role === "assistant")) return [3 /*break*/, 13];
                content = [];
                _d = 0, _e = message.content;
                _h.label = 8;
            case 8:
                if (!(_d < _e.length)) return [3 /*break*/, 12];
                part = _e[_d];
                if (!!shared_1.ProviderShared.supportsContent(part, ["text", "tool-call"])) return [3 /*break*/, 10];
                return [5 /*yield**/, __values(shared_1.ProviderShared.unsupportedContent("OpenAI Responses", "assistant", ["text", "tool-call"]))];
            case 9: return [2 /*return*/, _h.sent()];
            case 10:
                if (part.type === "text") {
                    content.push(part);
                    return [3 /*break*/, 11];
                }
                if (part.type === "tool-call") {
                    input.push(lowerToolCall(part));
                    return [3 /*break*/, 11];
                }
                _h.label = 11;
            case 11:
                _d++;
                return [3 /*break*/, 8];
            case 12:
                if (content.length > 0)
                    input.push({ role: "assistant", content: content.map(function (part) { return ({ type: "output_text", text: part.text }); }) });
                return [3 /*break*/, 18];
            case 13:
                _f = 0, _g = message.content;
                _h.label = 14;
            case 14:
                if (!(_f < _g.length)) return [3 /*break*/, 18];
                part = _g[_f];
                if (!!shared_1.ProviderShared.supportsContent(part, ["tool-result"])) return [3 /*break*/, 16];
                return [5 /*yield**/, __values(shared_1.ProviderShared.unsupportedContent("OpenAI Responses", "tool", ["tool-result"]))];
            case 15: return [2 /*return*/, _h.sent()];
            case 16:
                input.push({ type: "function_call_output", call_id: part.id, output: shared_1.ProviderShared.toolResultText(part) });
                _h.label = 17;
            case 17:
                _f++;
                return [3 /*break*/, 14];
            case 18:
                _i++;
                return [3 /*break*/, 1];
            case 19: return [2 /*return*/, input];
        }
    });
});
var lowerOptions = effect_1.Effect.fn("OpenAIResponses.lowerOptions")(function (request) {
    var store, promptCacheKey, effort, summary, encryptedState, verbosity;
    return __generator(this, function (_a) {
        switch (_a.label) {
            case 0:
                store = openai_options_1.OpenAIOptions.store(request);
                promptCacheKey = openai_options_1.OpenAIOptions.promptCacheKey(request);
                effort = openai_options_1.OpenAIOptions.reasoningEffort(request);
                if (!(effort && !openai_options_1.OpenAIOptions.isReasoningEffort(effort))) return [3 /*break*/, 2];
                return [5 /*yield**/, __values(invalid("OpenAI Responses does not support reasoning effort ".concat(effort)))];
            case 1: return [2 /*return*/, _a.sent()];
            case 2:
                summary = openai_options_1.OpenAIOptions.reasoningSummary(request);
                encryptedState = openai_options_1.OpenAIOptions.encryptedReasoning(request);
                verbosity = openai_options_1.OpenAIOptions.textVerbosity(request);
                return [2 /*return*/, __assign(__assign(__assign(__assign(__assign({}, (store !== undefined ? { store: store } : {})), (promptCacheKey ? { prompt_cache_key: promptCacheKey } : {})), (encryptedState ? { include: ["reasoning.encrypted_content"] } : {})), (effort || summary ? { reasoning: { effort: effort, summary: summary } } : {})), (verbosity ? { text: { verbosity: verbosity } } : {}))];
        }
    });
});
var fromRequest = effect_1.Effect.fn("OpenAIResponses.fromRequest")(function (request) {
    var generation, _a, _b, _c;
    return __generator(this, function (_d) {
        switch (_d.label) {
            case 0:
                generation = request.generation;
                _a = { model: request.model.id };
                return [5 /*yield**/, __values(lowerMessages(request))];
            case 1:
                _a.input = _d.sent(), _a.tools = request.tools.length === 0 ? undefined : request.tools.map(lowerTool);
                if (!request.toolChoice) return [3 /*break*/, 3];
                return [5 /*yield**/, __values(lowerToolChoice(request.toolChoice))];
            case 2:
                _b = _d.sent();
                return [3 /*break*/, 4];
            case 3:
                _b = undefined;
                _d.label = 4;
            case 4:
                _c = [(_a.tool_choice = _b, _a.stream = true, _a.max_output_tokens = generation === null || generation === void 0 ? void 0 : generation.maxTokens, _a.temperature = generation === null || generation === void 0 ? void 0 : generation.temperature, _a.top_p = generation === null || generation === void 0 ? void 0 : generation.topP, _a)];
                return [5 /*yield**/, __values(lowerOptions(request))];
            case 5: return [2 /*return*/, __assign.apply(void 0, _c.concat([(_d.sent())]))];
        }
    });
});
// =============================================================================
// Stream Parsing
// =============================================================================
var mapUsage = function (usage) {
    var _a, _b;
    if (!usage)
        return undefined;
    return new schema_1.Usage({
        inputTokens: usage.input_tokens,
        outputTokens: usage.output_tokens,
        reasoningTokens: (_a = usage.output_tokens_details) === null || _a === void 0 ? void 0 : _a.reasoning_tokens,
        cacheReadInputTokens: (_b = usage.input_tokens_details) === null || _b === void 0 ? void 0 : _b.cached_tokens,
        totalTokens: shared_1.ProviderShared.totalTokens(usage.input_tokens, usage.output_tokens, usage.total_tokens),
        native: usage,
    });
};
var mapFinishReason = function (event, hasFunctionCall) {
    var _a, _b;
    var reason = (_b = (_a = event.response) === null || _a === void 0 ? void 0 : _a.incomplete_details) === null || _b === void 0 ? void 0 : _b.reason;
    if (reason === undefined || reason === null)
        return hasFunctionCall ? "tool-calls" : "stop";
    if (reason === "max_output_tokens")
        return "length";
    if (reason === "content_filter")
        return "content-filter";
    return hasFunctionCall ? "tool-calls" : "unknown";
};
var openaiMetadata = function (metadata) { return ({ openai: metadata }); };
// Hosted tool items (provider-executed) ship their typed input + status +
// result fields all in one item. We expose them as a `tool-call` +
// `tool-result` pair so consumers can treat them uniformly with client tools,
// only differentiated by `providerExecuted: true`.
//
// One record per OpenAI Responses item type that represents a hosted
// (provider-executed) tool call: the common name we surface, plus an `input`
// extractor that picks the fields the model actually populated for that tool.
// Falling back to `{}` when an entry isn't fully typed keeps unknown tools
// observable without rolling a per-tool schema.
var HOSTED_TOOLS = {
    web_search_call: { name: "web_search", input: function (item) { var _a; return (_a = item.action) !== null && _a !== void 0 ? _a : {}; } },
    web_search_preview_call: { name: "web_search_preview", input: function (item) { var _a; return (_a = item.action) !== null && _a !== void 0 ? _a : {}; } },
    file_search_call: { name: "file_search", input: function (item) { var _a; return ({ queries: (_a = item.queries) !== null && _a !== void 0 ? _a : [] }); } },
    code_interpreter_call: {
        name: "code_interpreter",
        input: function (item) { return ({ code: item.code, container_id: item.container_id }); },
    },
    computer_use_call: { name: "computer_use", input: function (item) { var _a; return (_a = item.action) !== null && _a !== void 0 ? _a : {}; } },
    image_generation_call: { name: "image_generation", input: function () { return ({}); } },
    mcp_call: {
        name: "mcp",
        input: function (item) { return ({ server_label: item.server_label, name: item.name, arguments: item.arguments }); },
    },
    local_shell_call: { name: "local_shell", input: function (item) { var _a; return (_a = item.action) !== null && _a !== void 0 ? _a : {}; } },
};
var isHostedToolItem = function (item) {
    return item.type in HOSTED_TOOLS && typeof item.id === "string" && item.id.length > 0;
};
// Round-trip the full item as the structured result so consumers can extract
// outputs / sources / status without re-decoding.
var hostedToolResult = function (item) {
    var isError = typeof item.error !== "undefined" && item.error !== null;
    return isError ? { type: "error", value: item.error } : { type: "json", value: item };
};
var hostedToolEvents = function (item) {
    var tool = HOSTED_TOOLS[item.type];
    var providerMetadata = openaiMetadata({ itemId: item.id });
    return [
        {
            type: "tool-call",
            id: item.id,
            name: tool.name,
            input: tool.input(item),
            providerExecuted: true,
            providerMetadata: providerMetadata,
        },
        {
            type: "tool-result",
            id: item.id,
            name: tool.name,
            result: hostedToolResult(item),
            providerExecuted: true,
            providerMetadata: providerMetadata,
        },
    ];
};
var NO_EVENTS = [];
// `response.completed` / `response.incomplete` are clean finishes that emit a
// `request-finish` event; `response.failed` is a hard failure that emits a
// `provider-error`. All three end the stream — kept in one set so `step` and
// the protocol's `terminal` predicate stay in sync.
var TERMINAL_TYPES = new Set(["response.completed", "response.incomplete", "response.failed"]);
var onOutputTextDelta = function (state, event) {
    if (!event.delta)
        return [state, NO_EVENTS];
    return [
        state,
        [
            __assign({ type: "text-delta", id: event.item_id, text: event.delta }, (event.item_id ? { providerMetadata: openaiMetadata({ itemId: event.item_id }) } : {})),
        ],
    ];
};
var onOutputItemAdded = function (state, event) {
    var _a, _b, _c;
    var item = event.item;
    if ((item === null || item === void 0 ? void 0 : item.type) !== "function_call" || !item.id)
        return [state, NO_EVENTS];
    return [
        {
            hasFunctionCall: state.hasFunctionCall,
            tools: tool_stream_1.ToolStream.start(state.tools, item.id, {
                id: (_a = item.call_id) !== null && _a !== void 0 ? _a : item.id,
                name: (_b = item.name) !== null && _b !== void 0 ? _b : "",
                input: (_c = item.arguments) !== null && _c !== void 0 ? _c : "",
                providerMetadata: openaiMetadata({ itemId: item.id }),
            }),
        },
        NO_EVENTS,
    ];
};
var onFunctionCallArgumentsDelta = effect_1.Effect.fn("OpenAIResponses.onFunctionCallArgumentsDelta")(function (state, event) {
    var result;
    return __generator(this, function (_a) {
        switch (_a.label) {
            case 0:
                if (!event.item_id || !event.delta)
                    return [2 /*return*/, [state, NO_EVENTS]];
                result = tool_stream_1.ToolStream.appendExisting(ADAPTER, state.tools, event.item_id, event.delta, "OpenAI Responses tool argument delta is missing its tool call");
                if (!tool_stream_1.ToolStream.isError(result)) return [3 /*break*/, 2];
                return [5 /*yield**/, __values(result)];
            case 1: return [2 /*return*/, _a.sent()];
            case 2: return [2 /*return*/, [
                    { hasFunctionCall: state.hasFunctionCall, tools: result.tools },
                    result.event ? [result.event] : NO_EVENTS,
                ]];
        }
    });
});
var onOutputItemDone = effect_1.Effect.fn("OpenAIResponses.onOutputItemDone")(function (state, event) {
    var item, tools, result, _a;
    return __generator(this, function (_b) {
        switch (_b.label) {
            case 0:
                item = event.item;
                if (!item)
                    return [2 /*return*/, [state, NO_EVENTS]];
                if (!(item.type === "function_call")) return [3 /*break*/, 5];
                if (!item.id || !item.call_id || !item.name)
                    return [2 /*return*/, [state, NO_EVENTS]];
                tools = state.tools[item.id]
                    ? state.tools
                    : tool_stream_1.ToolStream.start(state.tools, item.id, { id: item.call_id, name: item.name });
                if (!(item.arguments === undefined)) return [3 /*break*/, 2];
                return [5 /*yield**/, __values(tool_stream_1.ToolStream.finish(ADAPTER, tools, item.id))];
            case 1:
                _a = _b.sent();
                return [3 /*break*/, 4];
            case 2: return [5 /*yield**/, __values(tool_stream_1.ToolStream.finishWithInput(ADAPTER, tools, item.id, item.arguments))];
            case 3:
                _a = _b.sent();
                _b.label = 4;
            case 4:
                result = _a;
                return [2 /*return*/, [
                        { hasFunctionCall: result.event ? true : state.hasFunctionCall, tools: result.tools },
                        result.event ? [result.event] : NO_EVENTS,
                    ]];
            case 5:
                if (isHostedToolItem(item))
                    return [2 /*return*/, [state, hostedToolEvents(item)]];
                return [2 /*return*/, [state, NO_EVENTS]];
        }
    });
});
var onResponseFinish = function (state, event) {
    var _a, _b, _c;
    return [
        state,
        [
            __assign({ type: "request-finish", reason: mapFinishReason(event, state.hasFunctionCall), usage: mapUsage((_a = event.response) === null || _a === void 0 ? void 0 : _a.usage) }, (((_b = event.response) === null || _b === void 0 ? void 0 : _b.id) || ((_c = event.response) === null || _c === void 0 ? void 0 : _c.service_tier)
                ? {
                    providerMetadata: openaiMetadata({
                        responseId: event.response.id,
                        serviceTier: event.response.service_tier,
                    }),
                }
                : {})),
        ],
    ];
};
var onResponseFailed = function (state, event) {
    var _a, _b;
    return [
        state,
        [{ type: "provider-error", message: (_b = (_a = event.message) !== null && _a !== void 0 ? _a : event.code) !== null && _b !== void 0 ? _b : "OpenAI Responses response failed" }],
    ];
};
var onError = function (state, event) {
    var _a, _b;
    return [
        state,
        [{ type: "provider-error", message: (_b = (_a = event.message) !== null && _a !== void 0 ? _a : event.code) !== null && _b !== void 0 ? _b : "OpenAI Responses stream error" }],
    ];
};
var step = function (state, event) {
    if (event.type === "response.output_text.delta")
        return effect_1.Effect.succeed(onOutputTextDelta(state, event));
    if (event.type === "response.output_item.added")
        return effect_1.Effect.succeed(onOutputItemAdded(state, event));
    if (event.type === "response.function_call_arguments.delta")
        return onFunctionCallArgumentsDelta(state, event);
    if (event.type === "response.output_item.done")
        return onOutputItemDone(state, event);
    if (event.type === "response.completed" || event.type === "response.incomplete")
        return effect_1.Effect.succeed(onResponseFinish(state, event));
    if (event.type === "response.failed")
        return effect_1.Effect.succeed(onResponseFailed(state, event));
    if (event.type === "error")
        return effect_1.Effect.succeed(onError(state, event));
    return effect_1.Effect.succeed([state, NO_EVENTS]);
};
// =============================================================================
// Protocol And OpenAI Route
// =============================================================================
/**
 * The OpenAI Responses protocol — request body construction, body schema, and
 * the streaming-event state machine. Used by native OpenAI and (once
 * registered) Azure OpenAI Responses.
 */
exports.protocol = protocol_1.Protocol.make({
    id: ADAPTER,
    body: {
        schema: OpenAIResponsesBody,
        from: fromRequest,
    },
    stream: {
        event: protocol_1.Protocol.jsonEvent(OpenAIResponsesEvent),
        initial: function () { return ({ hasFunctionCall: false, tools: tool_stream_1.ToolStream.empty() }); },
        step: step,
        terminal: function (event) { return TERMINAL_TYPES.has(event.type); },
    },
});
var encodeBody = effect_1.Schema.encodeSync(effect_1.Schema.fromJsonString(OpenAIResponsesBody));
var transportBase = {
    endpoint: endpoint_1.Endpoint.path(exports.PATH),
    auth: auth_1.Auth.bearer(),
    encodeBody: encodeBody,
};
var routeDefaults = {
    baseURL: exports.DEFAULT_BASE_URL,
};
exports.httpTransport = transport_1.HttpTransport.httpJson(__assign(__assign({}, transportBase), { framing: framing_1.Framing.sse }));
exports.route = client_1.Route.make({
    id: ADAPTER,
    provider: "openai",
    protocol: exports.protocol,
    transport: exports.httpTransport,
    defaults: routeDefaults,
});
var decodeWebSocketMessage = shared_1.ProviderShared.validateWith(effect_1.Schema.decodeUnknownEffect(OpenAIResponsesWebSocketMessage));
var webSocketMessage = function (body) {
    return effect_1.Effect.gen(function () {
        var _stream, message;
        return __generator(this, function (_a) {
            switch (_a.label) {
                case 0:
                    if (!!shared_1.ProviderShared.isRecord(body)) return [3 /*break*/, 2];
                    return [5 /*yield**/, __values(shared_1.ProviderShared.invalidRequest("OpenAI Responses WebSocket body must be a JSON object"))];
                case 1: return [2 /*return*/, _a.sent()];
                case 2:
                    _stream = body.stream, message = __rest(body, ["stream"]);
                    return [5 /*yield**/, __values(decodeWebSocketMessage(__assign(__assign({}, message), { type: "response.create" })))];
                case 3: return [2 /*return*/, _a.sent()];
            }
        });
    });
};
exports.webSocketTransport = transport_1.WebSocketTransport.json(__assign(__assign({}, transportBase), { toMessage: webSocketMessage, encodeMessage: encodeWebSocketMessage }));
exports.webSocketRoute = client_1.Route.make({
    id: "".concat(ADAPTER, "-websocket"),
    provider: "openai",
    protocol: exports.protocol,
    transport: exports.webSocketTransport,
    defaults: routeDefaults,
});
// =============================================================================
// Model Helper
// =============================================================================
exports.model = exports.route.model;
exports.webSocketModel = exports.webSocketRoute.model;
exports.OpenAIResponses = require("./openai-responses");
