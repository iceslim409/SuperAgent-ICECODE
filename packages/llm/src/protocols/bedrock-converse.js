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
exports.BedrockConverse = exports.model = exports.nativeCredentials = exports.route = exports.protocol = void 0;
var effect_1 = require("effect");
var client_1 = require("../route/client");
var endpoint_1 = require("../route/endpoint");
var protocol_1 = require("../route/protocol");
var schema_1 = require("../schema");
var bedrock_event_stream_1 = require("./bedrock-event-stream");
var shared_1 = require("./shared");
var bedrock_auth_1 = require("./utils/bedrock-auth");
var bedrock_cache_1 = require("./utils/bedrock-cache");
var bedrock_media_1 = require("./utils/bedrock-media");
var tool_stream_1 = require("./utils/tool-stream");
var ADAPTER = "bedrock-converse";
// =============================================================================
// Request Body Schema
// =============================================================================
var BedrockTextBlock = effect_1.Schema.Struct({
    text: effect_1.Schema.String,
});
var BedrockToolUseBlock = effect_1.Schema.Struct({
    toolUse: effect_1.Schema.Struct({
        toolUseId: effect_1.Schema.String,
        name: effect_1.Schema.String,
        input: effect_1.Schema.Unknown,
    }),
});
var BedrockToolResultContentItem = effect_1.Schema.Union([
    effect_1.Schema.Struct({ text: effect_1.Schema.String }),
    effect_1.Schema.Struct({ json: effect_1.Schema.Unknown }),
]);
var BedrockToolResultBlock = effect_1.Schema.Struct({
    toolResult: effect_1.Schema.Struct({
        toolUseId: effect_1.Schema.String,
        content: effect_1.Schema.Array(BedrockToolResultContentItem),
        status: effect_1.Schema.optional(effect_1.Schema.Literals(["success", "error"])),
    }),
});
var BedrockReasoningBlock = effect_1.Schema.Struct({
    reasoningContent: effect_1.Schema.Struct({
        reasoningText: effect_1.Schema.optional(effect_1.Schema.Struct({
            text: effect_1.Schema.String,
            signature: effect_1.Schema.optional(effect_1.Schema.String),
        })),
    }),
});
var BedrockUserBlock = effect_1.Schema.Union([
    BedrockTextBlock,
    bedrock_media_1.BedrockMedia.ImageBlock,
    bedrock_media_1.BedrockMedia.DocumentBlock,
    BedrockToolResultBlock,
    bedrock_cache_1.BedrockCache.CachePointBlock,
]);
var BedrockAssistantBlock = effect_1.Schema.Union([
    BedrockTextBlock,
    BedrockReasoningBlock,
    BedrockToolUseBlock,
    bedrock_cache_1.BedrockCache.CachePointBlock,
]);
var BedrockMessage = effect_1.Schema.Union([
    effect_1.Schema.Struct({ role: effect_1.Schema.Literal("user"), content: effect_1.Schema.Array(BedrockUserBlock) }),
    effect_1.Schema.Struct({ role: effect_1.Schema.Literal("assistant"), content: effect_1.Schema.Array(BedrockAssistantBlock) }),
]).pipe(effect_1.Schema.toTaggedUnion("role"));
var BedrockSystemBlock = effect_1.Schema.Union([BedrockTextBlock, bedrock_cache_1.BedrockCache.CachePointBlock]);
var BedrockTool = effect_1.Schema.Struct({
    toolSpec: effect_1.Schema.Struct({
        name: effect_1.Schema.String,
        description: effect_1.Schema.String,
        inputSchema: effect_1.Schema.Struct({
            json: shared_1.JsonObject,
        }),
    }),
});
var BedrockToolChoice = effect_1.Schema.Union([
    effect_1.Schema.Struct({ auto: effect_1.Schema.Struct({}) }),
    effect_1.Schema.Struct({ any: effect_1.Schema.Struct({}) }),
    effect_1.Schema.Struct({ tool: effect_1.Schema.Struct({ name: effect_1.Schema.String }) }),
]);
var BedrockBodyFields = {
    modelId: effect_1.Schema.String,
    messages: effect_1.Schema.Array(BedrockMessage),
    system: (0, shared_1.optionalArray)(BedrockSystemBlock),
    inferenceConfig: effect_1.Schema.optional(effect_1.Schema.Struct({
        maxTokens: effect_1.Schema.optional(effect_1.Schema.Number),
        temperature: effect_1.Schema.optional(effect_1.Schema.Number),
        topP: effect_1.Schema.optional(effect_1.Schema.Number),
        stopSequences: (0, shared_1.optionalArray)(effect_1.Schema.String),
    })),
    toolConfig: effect_1.Schema.optional(effect_1.Schema.Struct({
        tools: effect_1.Schema.Array(BedrockTool),
        toolChoice: effect_1.Schema.optional(BedrockToolChoice),
    })),
    additionalModelRequestFields: effect_1.Schema.optional(shared_1.JsonObject),
};
var BedrockConverseBody = effect_1.Schema.Struct(BedrockBodyFields);
var BedrockUsageSchema = effect_1.Schema.Struct({
    inputTokens: effect_1.Schema.optional(effect_1.Schema.Number),
    outputTokens: effect_1.Schema.optional(effect_1.Schema.Number),
    totalTokens: effect_1.Schema.optional(effect_1.Schema.Number),
    cacheReadInputTokens: effect_1.Schema.optional(effect_1.Schema.Number),
    cacheWriteInputTokens: effect_1.Schema.optional(effect_1.Schema.Number),
});
// Streaming event shape — the AWS event stream wraps each JSON payload by its
// `:event-type` header (e.g. `messageStart`, `contentBlockDelta`). We
// reconstruct that wrapping in `decodeFrames` below so the event schema can
// stay a plain discriminated record.
var BedrockEvent = effect_1.Schema.Struct({
    messageStart: effect_1.Schema.optional(effect_1.Schema.Struct({ role: effect_1.Schema.String })),
    contentBlockStart: effect_1.Schema.optional(effect_1.Schema.Struct({
        contentBlockIndex: effect_1.Schema.Number,
        start: effect_1.Schema.optional(effect_1.Schema.Struct({
            toolUse: effect_1.Schema.optional(effect_1.Schema.Struct({ toolUseId: effect_1.Schema.String, name: effect_1.Schema.String })),
        })),
    })),
    contentBlockDelta: effect_1.Schema.optional(effect_1.Schema.Struct({
        contentBlockIndex: effect_1.Schema.Number,
        delta: effect_1.Schema.optional(effect_1.Schema.Struct({
            text: effect_1.Schema.optional(effect_1.Schema.String),
            toolUse: effect_1.Schema.optional(effect_1.Schema.Struct({ input: effect_1.Schema.String })),
            reasoningContent: effect_1.Schema.optional(effect_1.Schema.Struct({
                text: effect_1.Schema.optional(effect_1.Schema.String),
                signature: effect_1.Schema.optional(effect_1.Schema.String),
            })),
        })),
    })),
    contentBlockStop: effect_1.Schema.optional(effect_1.Schema.Struct({ contentBlockIndex: effect_1.Schema.Number })),
    messageStop: effect_1.Schema.optional(effect_1.Schema.Struct({
        stopReason: effect_1.Schema.String,
        additionalModelResponseFields: effect_1.Schema.optional(effect_1.Schema.Unknown),
    })),
    metadata: effect_1.Schema.optional(effect_1.Schema.Struct({
        usage: effect_1.Schema.optional(BedrockUsageSchema),
        metrics: effect_1.Schema.optional(effect_1.Schema.Unknown),
    })),
    internalServerException: effect_1.Schema.optional(effect_1.Schema.Struct({ message: effect_1.Schema.String })),
    modelStreamErrorException: effect_1.Schema.optional(effect_1.Schema.Struct({ message: effect_1.Schema.String })),
    validationException: effect_1.Schema.optional(effect_1.Schema.Struct({ message: effect_1.Schema.String })),
    throttlingException: effect_1.Schema.optional(effect_1.Schema.Struct({ message: effect_1.Schema.String })),
    serviceUnavailableException: effect_1.Schema.optional(effect_1.Schema.Struct({ message: effect_1.Schema.String })),
});
// =============================================================================
// Request Lowering
// =============================================================================
var lowerTool = function (tool) { return ({
    toolSpec: {
        name: tool.name,
        description: tool.description,
        inputSchema: { json: tool.inputSchema },
    },
}); };
var textWithCache = function (text, cache) {
    var cachePoint = bedrock_cache_1.BedrockCache.block(cache);
    return cachePoint ? [{ text: text }, cachePoint] : [{ text: text }];
};
var lowerToolChoice = function (toolChoice) {
    return shared_1.ProviderShared.matchToolChoice("Bedrock Converse", toolChoice, {
        auto: function () { return ({ auto: {} }); },
        none: function () { return undefined; },
        required: function () { return ({ any: {} }); },
        tool: function (name) { return ({ tool: { name: name } }); },
    });
};
var lowerToolCall = function (part) { return ({
    toolUse: {
        toolUseId: part.id,
        name: part.name,
        input: part.input,
    },
}); };
var lowerToolResult = function (part) { return ({
    toolResult: {
        toolUseId: part.id,
        content: part.result.type === "text" || part.result.type === "error"
            ? [{ text: shared_1.ProviderShared.toolResultText(part) }]
            : [{ json: part.result.value }],
        status: part.result.type === "error" ? "error" : "success",
    },
}); };
var lowerMessages = effect_1.Effect.fn("BedrockConverse.lowerMessages")(function (request) {
    var messages, _i, _a, message, content_1, _b, _c, part, _d, _e, content_2, _f, _g, part, content, _h, _j, part;
    return __generator(this, function (_k) {
        switch (_k.label) {
            case 0:
                messages = [];
                _i = 0, _a = request.messages;
                _k.label = 1;
            case 1:
                if (!(_i < _a.length)) return [3 /*break*/, 21];
                message = _a[_i];
                if (!(message.role === "user")) return [3 /*break*/, 8];
                content_1 = [];
                _b = 0, _c = message.content;
                _k.label = 2;
            case 2:
                if (!(_b < _c.length)) return [3 /*break*/, 7];
                part = _c[_b];
                if (!!shared_1.ProviderShared.supportsContent(part, ["text", "media"])) return [3 /*break*/, 4];
                return [5 /*yield**/, __values(shared_1.ProviderShared.unsupportedContent("Bedrock Converse", "user", ["text", "media"]))];
            case 3: return [2 /*return*/, _k.sent()];
            case 4:
                if (part.type === "text") {
                    content_1.push.apply(content_1, textWithCache(part.text, part.cache));
                    return [3 /*break*/, 6];
                }
                if (!(part.type === "media")) return [3 /*break*/, 6];
                _e = (_d = content_1).push;
                return [5 /*yield**/, __values(bedrock_media_1.BedrockMedia.lower(part))];
            case 5:
                _e.apply(_d, [_k.sent()]);
                return [3 /*break*/, 6];
            case 6:
                _b++;
                return [3 /*break*/, 2];
            case 7:
                messages.push({ role: "user", content: content_1 });
                return [3 /*break*/, 20];
            case 8:
                if (!(message.role === "assistant")) return [3 /*break*/, 14];
                content_2 = [];
                _f = 0, _g = message.content;
                _k.label = 9;
            case 9:
                if (!(_f < _g.length)) return [3 /*break*/, 13];
                part = _g[_f];
                if (!!shared_1.ProviderShared.supportsContent(part, ["text", "reasoning", "tool-call"])) return [3 /*break*/, 11];
                return [5 /*yield**/, __values(shared_1.ProviderShared.unsupportedContent("Bedrock Converse", "assistant", [
                        "text",
                        "reasoning",
                        "tool-call",
                    ]))];
            case 10: return [2 /*return*/, _k.sent()];
            case 11:
                if (part.type === "text") {
                    content_2.push.apply(content_2, textWithCache(part.text, part.cache));
                    return [3 /*break*/, 12];
                }
                if (part.type === "reasoning") {
                    content_2.push({
                        reasoningContent: {
                            reasoningText: { text: part.text, signature: part.encrypted },
                        },
                    });
                    return [3 /*break*/, 12];
                }
                if (part.type === "tool-call") {
                    content_2.push(lowerToolCall(part));
                    return [3 /*break*/, 12];
                }
                _k.label = 12;
            case 12:
                _f++;
                return [3 /*break*/, 9];
            case 13:
                messages.push({ role: "assistant", content: content_2 });
                return [3 /*break*/, 20];
            case 14:
                content = [];
                _h = 0, _j = message.content;
                _k.label = 15;
            case 15:
                if (!(_h < _j.length)) return [3 /*break*/, 19];
                part = _j[_h];
                if (!!shared_1.ProviderShared.supportsContent(part, ["tool-result"])) return [3 /*break*/, 17];
                return [5 /*yield**/, __values(shared_1.ProviderShared.unsupportedContent("Bedrock Converse", "tool", ["tool-result"]))];
            case 16: return [2 /*return*/, _k.sent()];
            case 17:
                content.push(lowerToolResult(part));
                _k.label = 18;
            case 18:
                _h++;
                return [3 /*break*/, 15];
            case 19:
                messages.push({ role: "user", content: content });
                _k.label = 20;
            case 20:
                _i++;
                return [3 /*break*/, 1];
            case 21: return [2 /*return*/, messages];
        }
    });
});
// System prompts share the cache-point convention: emit the text block, then
// optionally a positional `cachePoint` marker.
var lowerSystem = function (system) {
    return system.flatMap(function (part) { return textWithCache(part.text, part.cache); });
};
var fromRequest = effect_1.Effect.fn("BedrockConverse.fromRequest")(function (request) {
    var toolChoice, _a, generation, _b;
    var _c;
    return __generator(this, function (_d) {
        switch (_d.label) {
            case 0:
                if (!request.toolChoice) return [3 /*break*/, 2];
                return [5 /*yield**/, __values(lowerToolChoice(request.toolChoice))];
            case 1:
                _a = _d.sent();
                return [3 /*break*/, 3];
            case 2:
                _a = undefined;
                _d.label = 3;
            case 3:
                toolChoice = _a;
                generation = request.generation;
                _b = {
                    modelId: request.model.id
                };
                return [5 /*yield**/, __values(lowerMessages(request))];
            case 4: return [2 /*return*/, (_b.messages = _d.sent(),
                    _b.system = request.system.length === 0 ? undefined : lowerSystem(request.system),
                    _b.inferenceConfig = (generation === null || generation === void 0 ? void 0 : generation.maxTokens) === undefined &&
                        (generation === null || generation === void 0 ? void 0 : generation.temperature) === undefined &&
                        (generation === null || generation === void 0 ? void 0 : generation.topP) === undefined &&
                        ((generation === null || generation === void 0 ? void 0 : generation.stop) === undefined || generation.stop.length === 0)
                        ? undefined
                        : {
                            maxTokens: generation === null || generation === void 0 ? void 0 : generation.maxTokens,
                            temperature: generation === null || generation === void 0 ? void 0 : generation.temperature,
                            topP: generation === null || generation === void 0 ? void 0 : generation.topP,
                            stopSequences: generation === null || generation === void 0 ? void 0 : generation.stop,
                        },
                    _b.toolConfig = request.tools.length > 0 && ((_c = request.toolChoice) === null || _c === void 0 ? void 0 : _c.type) !== "none"
                        ? { tools: request.tools.map(lowerTool), toolChoice: toolChoice }
                        : undefined,
                    _b)];
        }
    });
});
// =============================================================================
// Stream Parsing
// =============================================================================
var mapFinishReason = function (reason) {
    if (reason === "end_turn" || reason === "stop_sequence")
        return "stop";
    if (reason === "max_tokens")
        return "length";
    if (reason === "tool_use")
        return "tool-calls";
    if (reason === "content_filtered" || reason === "guardrail_intervened")
        return "content-filter";
    return "unknown";
};
var mapUsage = function (usage) {
    if (!usage)
        return undefined;
    return new schema_1.Usage({
        inputTokens: usage.inputTokens,
        outputTokens: usage.outputTokens,
        totalTokens: shared_1.ProviderShared.totalTokens(usage.inputTokens, usage.outputTokens, usage.totalTokens),
        cacheReadInputTokens: usage.cacheReadInputTokens,
        cacheWriteInputTokens: usage.cacheWriteInputTokens,
        native: usage,
    });
};
var step = function (state, event) {
    return effect_1.Effect.gen(function () {
        var index, index, result, result, usage, message, message;
        var _a, _b, _c, _d, _e, _f, _g, _h, _j, _k, _l, _m, _o, _p, _q, _r, _s, _t, _u, _v, _w, _x;
        return __generator(this, function (_y) {
            switch (_y.label) {
                case 0:
                    if ((_b = (_a = event.contentBlockStart) === null || _a === void 0 ? void 0 : _a.start) === null || _b === void 0 ? void 0 : _b.toolUse) {
                        index = event.contentBlockStart.contentBlockIndex;
                        return [2 /*return*/, [
                                __assign(__assign({}, state), { tools: tool_stream_1.ToolStream.start(state.tools, index, {
                                        id: event.contentBlockStart.start.toolUse.toolUseId,
                                        name: event.contentBlockStart.start.toolUse.name,
                                    }) }),
                                [],
                            ]];
                    }
                    if ((_d = (_c = event.contentBlockDelta) === null || _c === void 0 ? void 0 : _c.delta) === null || _d === void 0 ? void 0 : _d.text) {
                        return [2 /*return*/, [state, [{ type: "text-delta", text: event.contentBlockDelta.delta.text }]]];
                    }
                    if ((_g = (_f = (_e = event.contentBlockDelta) === null || _e === void 0 ? void 0 : _e.delta) === null || _f === void 0 ? void 0 : _f.reasoningContent) === null || _g === void 0 ? void 0 : _g.text) {
                        return [2 /*return*/, [
                                state,
                                [{ type: "reasoning-delta", text: event.contentBlockDelta.delta.reasoningContent.text }],
                            ]];
                    }
                    if (!((_j = (_h = event.contentBlockDelta) === null || _h === void 0 ? void 0 : _h.delta) === null || _j === void 0 ? void 0 : _j.toolUse)) return [3 /*break*/, 3];
                    index = event.contentBlockDelta.contentBlockIndex;
                    result = tool_stream_1.ToolStream.appendExisting(ADAPTER, state.tools, index, event.contentBlockDelta.delta.toolUse.input, "Bedrock Converse tool delta is missing its tool call");
                    if (!tool_stream_1.ToolStream.isError(result)) return [3 /*break*/, 2];
                    return [5 /*yield**/, __values(result)];
                case 1: return [2 /*return*/, _y.sent()];
                case 2: return [2 /*return*/, [__assign(__assign({}, state), { tools: result.tools }), result.event ? [result.event] : []]];
                case 3:
                    if (!event.contentBlockStop) return [3 /*break*/, 5];
                    return [5 /*yield**/, __values(tool_stream_1.ToolStream.finish(ADAPTER, state.tools, event.contentBlockStop.contentBlockIndex))];
                case 4:
                    result = _y.sent();
                    return [2 /*return*/, [__assign(__assign({}, state), { tools: result.tools }), result.event ? [result.event] : []]];
                case 5:
                    if (event.messageStop) {
                        return [2 /*return*/, [
                                __assign(__assign({}, state), { pendingFinish: { reason: mapFinishReason(event.messageStop.stopReason), usage: (_k = state.pendingFinish) === null || _k === void 0 ? void 0 : _k.usage } }),
                                [],
                            ]];
                    }
                    if (event.metadata) {
                        usage = mapUsage(event.metadata.usage);
                        return [2 /*return*/, [__assign(__assign({}, state), { pendingFinish: { reason: (_m = (_l = state.pendingFinish) === null || _l === void 0 ? void 0 : _l.reason) !== null && _m !== void 0 ? _m : "stop", usage: usage } }), []]];
                    }
                    if (event.internalServerException || event.modelStreamErrorException || event.serviceUnavailableException) {
                        message = (_t = (_r = (_p = (_o = event.internalServerException) === null || _o === void 0 ? void 0 : _o.message) !== null && _p !== void 0 ? _p : (_q = event.modelStreamErrorException) === null || _q === void 0 ? void 0 : _q.message) !== null && _r !== void 0 ? _r : (_s = event.serviceUnavailableException) === null || _s === void 0 ? void 0 : _s.message) !== null && _t !== void 0 ? _t : "Bedrock Converse stream error";
                        return [2 /*return*/, [state, [{ type: "provider-error", message: message, retryable: true }]]];
                    }
                    if (event.validationException || event.throttlingException) {
                        message = (_x = (_v = (_u = event.validationException) === null || _u === void 0 ? void 0 : _u.message) !== null && _v !== void 0 ? _v : (_w = event.throttlingException) === null || _w === void 0 ? void 0 : _w.message) !== null && _x !== void 0 ? _x : "Bedrock Converse error";
                        return [2 /*return*/, [
                                state,
                                [{ type: "provider-error", message: message, retryable: event.throttlingException !== undefined }],
                            ]];
                    }
                    return [2 /*return*/, [state, []]];
            }
        });
    });
};
var framing = bedrock_event_stream_1.BedrockEventStream.framing(ADAPTER);
var onHalt = function (state) {
    return state.pendingFinish
        ? [{ type: "request-finish", reason: state.pendingFinish.reason, usage: state.pendingFinish.usage }]
        : [];
};
// =============================================================================
// Protocol And Bedrock Route
// =============================================================================
/**
 * The Bedrock Converse protocol — request body construction, body schema, and
 * the streaming-event state machine.
 */
exports.protocol = protocol_1.Protocol.make({
    id: ADAPTER,
    body: {
        schema: BedrockConverseBody,
        from: fromRequest,
    },
    stream: {
        event: BedrockEvent,
        initial: function () { return ({ tools: tool_stream_1.ToolStream.empty(), pendingFinish: undefined }); },
        step: step,
        onHalt: onHalt,
    },
});
exports.route = client_1.Route.make({
    id: ADAPTER,
    protocol: exports.protocol,
    // Bedrock's URL embeds the region in the host (set on `model.baseURL` by
    // the provider helper from credentials) and the validated modelId in the
    // path. We read the validated body so the URL matches the body that gets
    // signed.
    endpoint: endpoint_1.Endpoint.path(function (_a) {
        var body = _a.body;
        return "/model/".concat(encodeURIComponent(body.modelId), "/converse-stream");
    }),
    auth: bedrock_auth_1.BedrockAuth.auth,
    framing: framing,
});
exports.nativeCredentials = bedrock_auth_1.BedrockAuth.nativeCredentials;
var bedrockModel = client_1.Route.model(exports.route, {
    provider: "bedrock",
}, {
    mapInput: function (input) {
        var _a, _b;
        var credentials = input.credentials, rest = __rest(input, ["credentials"]);
        var region = (_a = credentials === null || credentials === void 0 ? void 0 : credentials.region) !== null && _a !== void 0 ? _a : "us-east-1";
        return __assign(__assign({}, rest), { baseURL: (_b = rest.baseURL) !== null && _b !== void 0 ? _b : "https://bedrock-runtime.".concat(region, ".amazonaws.com"), native: (0, exports.nativeCredentials)(input.native, credentials) });
    },
});
exports.model = bedrockModel;
exports.BedrockConverse = require("./bedrock-converse");
