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
exports.OpenAIChat = exports.model = exports.route = exports.httpTransport = exports.protocol = exports.bodyFields = exports.PATH = exports.DEFAULT_BASE_URL = void 0;
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
var ADAPTER = "openai-chat";
exports.DEFAULT_BASE_URL = "https://api.openai.com/v1";
exports.PATH = "/chat/completions";
// =============================================================================
// Request Body Schema
// =============================================================================
// The body schema is the provider-native JSON body. `fromRequest` below builds
// this shape from the common `LLMRequest`, then `Route.make` validates and
// JSON-encodes it before transport.
var OpenAIChatFunction = effect_1.Schema.Struct({
    name: effect_1.Schema.String,
    description: effect_1.Schema.String,
    parameters: shared_1.JsonObject,
});
var OpenAIChatTool = effect_1.Schema.Struct({
    type: effect_1.Schema.tag("function"),
    function: OpenAIChatFunction,
});
var OpenAIChatAssistantToolCall = effect_1.Schema.Struct({
    id: effect_1.Schema.String,
    type: effect_1.Schema.tag("function"),
    function: effect_1.Schema.Struct({
        name: effect_1.Schema.String,
        arguments: effect_1.Schema.String,
    }),
});
var OpenAIChatMessage = effect_1.Schema.Union([
    effect_1.Schema.Struct({ role: effect_1.Schema.Literal("system"), content: effect_1.Schema.String }),
    effect_1.Schema.Struct({ role: effect_1.Schema.Literal("user"), content: effect_1.Schema.String }),
    effect_1.Schema.Struct({
        role: effect_1.Schema.Literal("assistant"),
        content: effect_1.Schema.NullOr(effect_1.Schema.String),
        tool_calls: (0, shared_1.optionalArray)(OpenAIChatAssistantToolCall),
        reasoning_content: effect_1.Schema.optional(effect_1.Schema.String),
    }),
    effect_1.Schema.Struct({ role: effect_1.Schema.Literal("tool"), tool_call_id: effect_1.Schema.String, content: effect_1.Schema.String }),
]).pipe(effect_1.Schema.toTaggedUnion("role"));
var OpenAIChatToolChoice = effect_1.Schema.Union([
    effect_1.Schema.Literals(["auto", "none", "required"]),
    effect_1.Schema.Struct({
        type: effect_1.Schema.tag("function"),
        function: effect_1.Schema.Struct({ name: effect_1.Schema.String }),
    }),
]);
exports.bodyFields = {
    model: effect_1.Schema.String,
    messages: effect_1.Schema.Array(OpenAIChatMessage),
    tools: (0, shared_1.optionalArray)(OpenAIChatTool),
    tool_choice: effect_1.Schema.optional(OpenAIChatToolChoice),
    stream: effect_1.Schema.Literal(true),
    stream_options: effect_1.Schema.optional(effect_1.Schema.Struct({ include_usage: effect_1.Schema.Boolean })),
    store: effect_1.Schema.optional(effect_1.Schema.Boolean),
    reasoning_effort: effect_1.Schema.optional(openai_options_1.OpenAIOptions.OpenAIReasoningEffort),
    max_tokens: effect_1.Schema.optional(effect_1.Schema.Number),
    temperature: effect_1.Schema.optional(effect_1.Schema.Number),
    top_p: effect_1.Schema.optional(effect_1.Schema.Number),
    frequency_penalty: effect_1.Schema.optional(effect_1.Schema.Number),
    presence_penalty: effect_1.Schema.optional(effect_1.Schema.Number),
    seed: effect_1.Schema.optional(effect_1.Schema.Number),
    stop: (0, shared_1.optionalArray)(effect_1.Schema.String),
};
var OpenAIChatBody = effect_1.Schema.Struct(exports.bodyFields);
// =============================================================================
// Streaming Event Schema
// =============================================================================
// The event schema is one decoded SSE `data:` payload. `Framing.sse` splits the
// byte stream into strings, then `Protocol.jsonEvent` decodes each string into
// this provider-native event shape.
var OpenAIChatUsage = effect_1.Schema.Struct({
    prompt_tokens: effect_1.Schema.optional(effect_1.Schema.Number),
    completion_tokens: effect_1.Schema.optional(effect_1.Schema.Number),
    total_tokens: effect_1.Schema.optional(effect_1.Schema.Number),
    prompt_tokens_details: (0, shared_1.optionalNull)(effect_1.Schema.Struct({
        cached_tokens: effect_1.Schema.optional(effect_1.Schema.Number),
    })),
    completion_tokens_details: (0, shared_1.optionalNull)(effect_1.Schema.Struct({
        reasoning_tokens: effect_1.Schema.optional(effect_1.Schema.Number),
    })),
});
var OpenAIChatToolCallDeltaFunction = effect_1.Schema.Struct({
    name: (0, shared_1.optionalNull)(effect_1.Schema.String),
    arguments: (0, shared_1.optionalNull)(effect_1.Schema.String),
});
var OpenAIChatToolCallDelta = effect_1.Schema.Struct({
    index: effect_1.Schema.Number,
    id: (0, shared_1.optionalNull)(effect_1.Schema.String),
    function: (0, shared_1.optionalNull)(OpenAIChatToolCallDeltaFunction),
});
var OpenAIChatDelta = effect_1.Schema.Struct({
    content: (0, shared_1.optionalNull)(effect_1.Schema.String),
    tool_calls: (0, shared_1.optionalNull)(effect_1.Schema.Array(OpenAIChatToolCallDelta)),
});
var OpenAIChatChoice = effect_1.Schema.Struct({
    delta: (0, shared_1.optionalNull)(OpenAIChatDelta),
    finish_reason: (0, shared_1.optionalNull)(effect_1.Schema.String),
});
var OpenAIChatEvent = effect_1.Schema.Struct({
    choices: effect_1.Schema.Array(OpenAIChatChoice),
    usage: (0, shared_1.optionalNull)(OpenAIChatUsage),
});
var invalid = shared_1.ProviderShared.invalidRequest;
// =============================================================================
// Request Lowering
// =============================================================================
// Lowering is the only place that knows how common LLM messages map onto the
// OpenAI Chat wire format. Keep provider quirks here instead of leaking native
// fields into `LLMRequest`.
var lowerTool = function (tool) { return ({
    type: "function",
    function: {
        name: tool.name,
        description: tool.description,
        parameters: tool.inputSchema,
    },
}); };
var lowerToolChoice = function (toolChoice) {
    return shared_1.ProviderShared.matchToolChoice("OpenAI Chat", toolChoice, {
        auto: function () { return "auto"; },
        none: function () { return "none"; },
        required: function () { return "required"; },
        tool: function (name) { return ({ type: "function", function: { name: name } }); },
    });
};
var lowerToolCall = function (part) { return ({
    id: part.id,
    type: "function",
    function: {
        name: part.name,
        arguments: shared_1.ProviderShared.encodeJson(part.input),
    },
}); };
var openAICompatibleReasoningContent = function (native) {
    return (0, shared_1.isRecord)(native) && typeof native.reasoning_content === "string" ? native.reasoning_content : undefined;
};
var lowerUserMessage = effect_1.Effect.fn("OpenAIChat.lowerUserMessage")(function (message) {
    var content, _i, _a, part;
    return __generator(this, function (_b) {
        switch (_b.label) {
            case 0:
                content = [];
                _i = 0, _a = message.content;
                _b.label = 1;
            case 1:
                if (!(_i < _a.length)) return [3 /*break*/, 5];
                part = _a[_i];
                if (!!shared_1.ProviderShared.supportsContent(part, ["text"])) return [3 /*break*/, 3];
                return [5 /*yield**/, __values(shared_1.ProviderShared.unsupportedContent("OpenAI Chat", "user", ["text"]))];
            case 2: return [2 /*return*/, _b.sent()];
            case 3:
                content.push(part);
                _b.label = 4;
            case 4:
                _i++;
                return [3 /*break*/, 1];
            case 5: return [2 /*return*/, { role: "user", content: shared_1.ProviderShared.joinText(content) }];
        }
    });
});
var lowerAssistantMessage = effect_1.Effect.fn("OpenAIChat.lowerAssistantMessage")(function (message) {
    var content, toolCalls, _i, _a, part;
    var _b;
    return __generator(this, function (_c) {
        switch (_c.label) {
            case 0:
                content = [];
                toolCalls = [];
                _i = 0, _a = message.content;
                _c.label = 1;
            case 1:
                if (!(_i < _a.length)) return [3 /*break*/, 5];
                part = _a[_i];
                if (!!shared_1.ProviderShared.supportsContent(part, ["text", "tool-call"])) return [3 /*break*/, 3];
                return [5 /*yield**/, __values(shared_1.ProviderShared.unsupportedContent("OpenAI Chat", "assistant", ["text", "tool-call"]))];
            case 2: return [2 /*return*/, _c.sent()];
            case 3:
                if (part.type === "text") {
                    content.push(part);
                    return [3 /*break*/, 4];
                }
                if (part.type === "tool-call") {
                    toolCalls.push(lowerToolCall(part));
                    return [3 /*break*/, 4];
                }
                _c.label = 4;
            case 4:
                _i++;
                return [3 /*break*/, 1];
            case 5: return [2 /*return*/, {
                    role: "assistant",
                    content: content.length === 0 ? null : shared_1.ProviderShared.joinText(content),
                    tool_calls: toolCalls.length === 0 ? undefined : toolCalls,
                    reasoning_content: openAICompatibleReasoningContent((_b = message.native) === null || _b === void 0 ? void 0 : _b.openaiCompatible),
                }];
        }
    });
});
var lowerToolMessages = effect_1.Effect.fn("OpenAIChat.lowerToolMessages")(function (message) {
    var messages, _i, _a, part;
    return __generator(this, function (_b) {
        switch (_b.label) {
            case 0:
                messages = [];
                _i = 0, _a = message.content;
                _b.label = 1;
            case 1:
                if (!(_i < _a.length)) return [3 /*break*/, 5];
                part = _a[_i];
                if (!!shared_1.ProviderShared.supportsContent(part, ["tool-result"])) return [3 /*break*/, 3];
                return [5 /*yield**/, __values(shared_1.ProviderShared.unsupportedContent("OpenAI Chat", "tool", ["tool-result"]))];
            case 2: return [2 /*return*/, _b.sent()];
            case 3:
                messages.push({ role: "tool", tool_call_id: part.id, content: shared_1.ProviderShared.toolResultText(part) });
                _b.label = 4;
            case 4:
                _i++;
                return [3 /*break*/, 1];
            case 5: return [2 /*return*/, messages];
        }
    });
});
var lowerMessage = effect_1.Effect.fn("OpenAIChat.lowerMessage")(function (message) {
    return __generator(this, function (_a) {
        switch (_a.label) {
            case 0:
                if (!(message.role === "user")) return [3 /*break*/, 2];
                return [5 /*yield**/, __values(lowerUserMessage(message))];
            case 1: return [2 /*return*/, [_a.sent()]];
            case 2:
                if (!(message.role === "assistant")) return [3 /*break*/, 4];
                return [5 /*yield**/, __values(lowerAssistantMessage(message))];
            case 3: return [2 /*return*/, [_a.sent()]];
            case 4: return [5 /*yield**/, __values(lowerToolMessages(message))];
            case 5: return [2 /*return*/, _a.sent()];
        }
    });
});
var lowerMessages = effect_1.Effect.fn("OpenAIChat.lowerMessages")(function (request) {
    var system, _a, _b, _c;
    return __generator(this, function (_d) {
        switch (_d.label) {
            case 0:
                system = request.system.length === 0 ? [] : [{ role: "system", content: shared_1.ProviderShared.joinText(request.system) }];
                _a = [__spreadArray([], system, true)];
                _c = (_b = effect_1.Array).flatten;
                return [5 /*yield**/, __values(effect_1.Effect.forEach(request.messages, lowerMessage))];
            case 1: return [2 /*return*/, __spreadArray.apply(void 0, _a.concat([_c.apply(_b, [_d.sent()]), true]))];
        }
    });
});
var lowerOptions = effect_1.Effect.fn("OpenAIChat.lowerOptions")(function (request) {
    var store, reasoningEffort;
    return __generator(this, function (_a) {
        switch (_a.label) {
            case 0:
                store = openai_options_1.OpenAIOptions.store(request);
                reasoningEffort = openai_options_1.OpenAIOptions.reasoningEffort(request);
                if (!(reasoningEffort && !openai_options_1.OpenAIOptions.isReasoningEffort(reasoningEffort))) return [3 /*break*/, 2];
                return [5 /*yield**/, __values(invalid("OpenAI Chat does not support reasoning effort ".concat(reasoningEffort)))];
            case 1: return [2 /*return*/, _a.sent()];
            case 2: return [2 /*return*/, __assign(__assign({}, (store !== undefined ? { store: store } : {})), (reasoningEffort ? { reasoning_effort: reasoningEffort } : {}))];
        }
    });
});
var fromRequest = effect_1.Effect.fn("OpenAIChat.fromRequest")(function (request) {
    var generation, _a, _b, _c;
    return __generator(this, function (_d) {
        switch (_d.label) {
            case 0:
                generation = request.generation;
                _a = { model: request.model.id };
                return [5 /*yield**/, __values(lowerMessages(request))];
            case 1:
                _a.messages = _d.sent(), _a.tools = request.tools.length === 0 ? undefined : request.tools.map(lowerTool);
                if (!request.toolChoice) return [3 /*break*/, 3];
                return [5 /*yield**/, __values(lowerToolChoice(request.toolChoice))];
            case 2:
                _b = _d.sent();
                return [3 /*break*/, 4];
            case 3:
                _b = undefined;
                _d.label = 4;
            case 4:
                _c = [(_a.tool_choice = _b, _a.stream = true, _a.stream_options = { include_usage: true }, _a.max_tokens = generation === null || generation === void 0 ? void 0 : generation.maxTokens, _a.temperature = generation === null || generation === void 0 ? void 0 : generation.temperature, _a.top_p = generation === null || generation === void 0 ? void 0 : generation.topP, _a.frequency_penalty = generation === null || generation === void 0 ? void 0 : generation.frequencyPenalty, _a.presence_penalty = generation === null || generation === void 0 ? void 0 : generation.presencePenalty, _a.seed = generation === null || generation === void 0 ? void 0 : generation.seed, _a.stop = generation === null || generation === void 0 ? void 0 : generation.stop, _a)];
                return [5 /*yield**/, __values(lowerOptions(request))];
            case 5: return [2 /*return*/, __assign.apply(void 0, _c.concat([(_d.sent())]))];
        }
    });
});
// =============================================================================
// Stream Parsing
// =============================================================================
// Streaming parsers are small state machines: every event returns a new state
// plus the common `LLMEvent`s produced by that event. Tool calls are accumulated
// because OpenAI streams JSON arguments across multiple deltas.
var mapFinishReason = function (reason) {
    if (reason === "stop")
        return "stop";
    if (reason === "length")
        return "length";
    if (reason === "content_filter")
        return "content-filter";
    if (reason === "function_call" || reason === "tool_calls")
        return "tool-calls";
    return "unknown";
};
var mapUsage = function (usage) {
    var _a, _b;
    if (!usage)
        return undefined;
    return new schema_1.Usage({
        inputTokens: usage.prompt_tokens,
        outputTokens: usage.completion_tokens,
        reasoningTokens: (_a = usage.completion_tokens_details) === null || _a === void 0 ? void 0 : _a.reasoning_tokens,
        cacheReadInputTokens: (_b = usage.prompt_tokens_details) === null || _b === void 0 ? void 0 : _b.cached_tokens,
        totalTokens: shared_1.ProviderShared.totalTokens(usage.prompt_tokens, usage.completion_tokens, usage.total_tokens),
        native: usage,
    });
};
var step = function (state, event) {
    return effect_1.Effect.gen(function () {
        var events, usage, choice, finishReason, delta, toolDeltas, tools, _i, toolDeltas_1, tool, result, finished, _a;
        var _b, _c, _d, _e, _f, _g, _h, _j, _k;
        return __generator(this, function (_l) {
            switch (_l.label) {
                case 0:
                    events = [];
                    usage = (_b = mapUsage(event.usage)) !== null && _b !== void 0 ? _b : state.usage;
                    choice = event.choices[0];
                    finishReason = (choice === null || choice === void 0 ? void 0 : choice.finish_reason) ? mapFinishReason(choice.finish_reason) : state.finishReason;
                    delta = choice === null || choice === void 0 ? void 0 : choice.delta;
                    toolDeltas = (_c = delta === null || delta === void 0 ? void 0 : delta.tool_calls) !== null && _c !== void 0 ? _c : [];
                    tools = state.tools;
                    if (delta === null || delta === void 0 ? void 0 : delta.content)
                        events.push({ type: "text-delta", text: delta.content });
                    _i = 0, toolDeltas_1 = toolDeltas;
                    _l.label = 1;
                case 1:
                    if (!(_i < toolDeltas_1.length)) return [3 /*break*/, 5];
                    tool = toolDeltas_1[_i];
                    result = tool_stream_1.ToolStream.appendOrStart(ADAPTER, tools, tool.index, { id: (_d = tool.id) !== null && _d !== void 0 ? _d : undefined, name: (_f = (_e = tool.function) === null || _e === void 0 ? void 0 : _e.name) !== null && _f !== void 0 ? _f : undefined, text: (_h = (_g = tool.function) === null || _g === void 0 ? void 0 : _g.arguments) !== null && _h !== void 0 ? _h : "" }, "OpenAI Chat tool call delta is missing id or name");
                    if (!tool_stream_1.ToolStream.isError(result)) return [3 /*break*/, 3];
                    return [5 /*yield**/, __values(result)];
                case 2: return [2 /*return*/, _l.sent()];
                case 3:
                    tools = result.tools;
                    if (result.event)
                        events.push(result.event);
                    _l.label = 4;
                case 4:
                    _i++;
                    return [3 /*break*/, 1];
                case 5:
                    if (!(finishReason !== undefined && state.finishReason === undefined && Object.keys(tools).length > 0)) return [3 /*break*/, 7];
                    return [5 /*yield**/, __values(tool_stream_1.ToolStream.finishAll(ADAPTER, tools))];
                case 6:
                    _a = _l.sent();
                    return [3 /*break*/, 8];
                case 7:
                    _a = undefined;
                    _l.label = 8;
                case 8:
                    finished = _a;
                    return [2 /*return*/, [
                            {
                                tools: (_j = finished === null || finished === void 0 ? void 0 : finished.tools) !== null && _j !== void 0 ? _j : tools,
                                toolCallEvents: (_k = finished === null || finished === void 0 ? void 0 : finished.events) !== null && _k !== void 0 ? _k : state.toolCallEvents,
                                usage: usage,
                                finishReason: finishReason,
                            },
                            events,
                        ]];
            }
        });
    });
};
var finishEvents = function (state) {
    var hasToolCalls = state.toolCallEvents.length > 0;
    var reason = state.finishReason === "stop" && hasToolCalls ? "tool-calls" : state.finishReason;
    return __spreadArray(__spreadArray([], state.toolCallEvents, true), (reason ? [{ type: "request-finish", reason: reason, usage: state.usage }] : []), true);
};
// =============================================================================
// Protocol And OpenAI Route
// =============================================================================
/**
 * The OpenAI Chat protocol — request body construction, body schema, and the
 * streaming-event state machine. Reused by every route that speaks OpenAI Chat
 * over HTTP+SSE: native OpenAI, DeepSeek, TogetherAI, Cerebras, Baseten,
 * Fireworks, DeepInfra, and (once added) Azure OpenAI Chat.
 */
exports.protocol = protocol_1.Protocol.make({
    id: ADAPTER,
    body: {
        schema: OpenAIChatBody,
        from: fromRequest,
    },
    stream: {
        event: protocol_1.Protocol.jsonEvent(OpenAIChatEvent),
        initial: function () { return ({ tools: tool_stream_1.ToolStream.empty(), toolCallEvents: [] }); },
        step: step,
        onHalt: finishEvents,
    },
});
var encodeBody = effect_1.Schema.encodeSync(effect_1.Schema.fromJsonString(OpenAIChatBody));
exports.httpTransport = transport_1.HttpTransport.httpJson({
    endpoint: endpoint_1.Endpoint.path(exports.PATH),
    auth: auth_1.Auth.bearer(),
    framing: framing_1.Framing.sse,
    encodeBody: encodeBody,
});
exports.route = client_1.Route.make({
    id: ADAPTER,
    provider: "openai",
    protocol: exports.protocol,
    transport: exports.httpTransport,
    defaults: {
        baseURL: exports.DEFAULT_BASE_URL,
    },
});
// =============================================================================
// Model Helper
// =============================================================================
exports.model = exports.route.model;
exports.OpenAIChat = require("./openai-chat");
