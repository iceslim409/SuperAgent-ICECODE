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
exports.ToolStream = exports.finishAll = exports.finishWithInput = exports.finish = exports.appendExisting = exports.appendOrStart = exports.start = exports.isError = exports.empty = void 0;
var effect_1 = require("effect");
var schema_1 = require("../../schema");
var shared_1 = require("../shared");
/** Create empty accumulator state for one provider stream. */
var empty = function () { return ({}); };
exports.empty = empty;
var withTool = function (tools, key, tool) {
    var _a;
    return __assign(__assign({}, tools), (_a = {}, _a[key] = tool, _a));
};
var withoutTool = function (tools, key) {
    var next = __assign({}, tools);
    delete next[key];
    return next;
};
var inputDelta = function (tool, text) { return (__assign({ type: "tool-input-delta", id: tool.id, name: tool.name, text: text }, (tool.providerMetadata ? { providerMetadata: tool.providerMetadata } : {}))); };
var toolCall = function (route, tool, inputOverride) {
    return (0, shared_1.parseToolInput)(route, tool.name, inputOverride !== null && inputOverride !== void 0 ? inputOverride : tool.input).pipe(effect_1.Effect.map(function (input) {
        return tool.providerExecuted
            ? __assign({ type: "tool-call", id: tool.id, name: tool.name, input: input, providerExecuted: true }, (tool.providerMetadata ? { providerMetadata: tool.providerMetadata } : {})) : __assign({ type: "tool-call", id: tool.id, name: tool.name, input: input }, (tool.providerMetadata ? { providerMetadata: tool.providerMetadata } : {}));
    }));
};
/** Store the updated tool and produce the optional public delta event. */
var appendTool = function (tools, key, tool, text) { return ({
    tools: withTool(tools, key, tool),
    tool: tool,
    event: text.length === 0 ? undefined : inputDelta(tool, text),
}); };
var isError = function (result) {
    return result instanceof schema_1.LLMError;
};
exports.isError = isError;
/**
 * Register a tool call whose start event arrived before any argument deltas.
 * Used by Anthropic `content_block_start`, Bedrock `contentBlockStart`, and
 * OpenAI Responses `response.output_item.added`.
 */
var start = function (tools, key, tool) { var _a; return withTool(tools, key, __assign(__assign({}, tool), { input: (_a = tool.input) !== null && _a !== void 0 ? _a : "" })); };
exports.start = start;
/**
 * Append a streamed argument delta, starting the tool if this provider encodes
 * identity on the first delta instead of a separate start event. OpenAI Chat has
 * this shape: `tool_calls[].index` is the stream key, and `id` / `name` may only
 * appear on the first delta for that index.
 */
var appendOrStart = function (route, tools, key, delta, missingToolMessage) {
    var _a, _b, _c;
    var current = tools[key];
    var id = (_a = delta.id) !== null && _a !== void 0 ? _a : current === null || current === void 0 ? void 0 : current.id;
    var name = (_b = delta.name) !== null && _b !== void 0 ? _b : current === null || current === void 0 ? void 0 : current.name;
    if (!id || !name)
        return (0, shared_1.eventError)(route, missingToolMessage);
    var tool = {
        id: id,
        name: name,
        input: "".concat((_c = current === null || current === void 0 ? void 0 : current.input) !== null && _c !== void 0 ? _c : "").concat(delta.text),
        providerExecuted: current === null || current === void 0 ? void 0 : current.providerExecuted,
        providerMetadata: current === null || current === void 0 ? void 0 : current.providerMetadata,
    };
    if (current && delta.text.length === 0 && current.id === id && current.name === name)
        return { tools: tools, tool: current };
    return appendTool(tools, key, tool, delta.text);
};
exports.appendOrStart = appendOrStart;
/**
 * Append argument text to a tool that must already have been started. This keeps
 * protocols honest when their stream grammar promises a start event before any
 * argument delta.
 */
var appendExisting = function (route, tools, key, text, missingToolMessage) {
    var current = tools[key];
    if (!current)
        return (0, shared_1.eventError)(route, missingToolMessage);
    if (text.length === 0)
        return { tools: tools, tool: current };
    return appendTool(tools, key, __assign(__assign({}, current), { input: "".concat(current.input).concat(text) }), text);
};
exports.appendExisting = appendExisting;
/**
 * Finalize one pending tool call: parse the accumulated raw JSON, remove it
 * from state, and return the optional public `tool-call` event. Missing keys are
 * a no-op because some providers emit stop events for non-tool content blocks.
 */
var finish = function (route, tools, key) {
    return effect_1.Effect.gen(function () {
        var tool, _a;
        return __generator(this, function (_b) {
            switch (_b.label) {
                case 0:
                    tool = tools[key];
                    if (!tool)
                        return [2 /*return*/, { tools: tools }];
                    _a = { tools: withoutTool(tools, key) };
                    return [5 /*yield**/, __values(toolCall(route, tool))];
                case 1: return [2 /*return*/, (_a.event = _b.sent(), _a)];
            }
        });
    });
};
exports.finish = finish;
/**
 * Finalize one pending tool call with an authoritative final input string.
 * OpenAI Responses can send accumulated deltas and then repeat the completed
 * arguments on `response.output_item.done`; the final value wins.
 */
var finishWithInput = function (route, tools, key, input) {
    return effect_1.Effect.gen(function () {
        var tool, _a;
        return __generator(this, function (_b) {
            switch (_b.label) {
                case 0:
                    tool = tools[key];
                    if (!tool)
                        return [2 /*return*/, { tools: tools }];
                    _a = { tools: withoutTool(tools, key) };
                    return [5 /*yield**/, __values(toolCall(route, tool, input))];
                case 1: return [2 /*return*/, (_a.event = _b.sent(), _a)];
            }
        });
    });
};
exports.finishWithInput = finishWithInput;
/**
 * Finalize every pending tool call at once. OpenAI Chat has this shape: it does
 * not emit per-tool stop events, so all accumulated calls finish when the choice
 * receives a terminal `finish_reason`.
 */
var finishAll = function (route, tools) {
    return effect_1.Effect.gen(function () {
        var pending, _a;
        return __generator(this, function (_b) {
            switch (_b.label) {
                case 0:
                    pending = Object.values(tools).filter(function (tool) { return tool !== undefined; });
                    _a = {
                        tools: (0, exports.empty)()
                    };
                    return [5 /*yield**/, __values(effect_1.Effect.forEach(pending, function (tool) { return toolCall(route, tool); }))];
                case 1: return [2 /*return*/, (_a.events = _b.sent(),
                        _a)];
            }
        });
    });
};
exports.finishAll = finishAll;
exports.ToolStream = require("./tool-stream");
