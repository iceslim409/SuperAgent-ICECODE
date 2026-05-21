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
exports.ToolRuntime = exports.stream = exports.stepCountIs = void 0;
var effect_1 = require("effect");
var schema_1 = require("./schema");
var tool_1 = require("./tool");
var stepCountIs = function (count) {
    return function (state) {
        return state.step + 1 >= count;
    };
};
exports.stepCountIs = stepCountIs;
/**
 * Run a model with typed tools. This helper owns tool orchestration, while the
 * caller supplies the actual model stream function. It can advertise schemas
 * only (`toolExecution: "none"`), execute one step, or continue model rounds
 * when `stopWhen` is provided.
 */
var stream = function (options) {
    var _a;
    var concurrency = (_a = options.concurrency) !== null && _a !== void 0 ? _a : 10;
    var tools = options.tools;
    var runtimeTools = (0, tool_1.toDefinitions)(tools);
    var runtimeToolNames = new Set(runtimeTools.map(function (tool) { return tool.name; }));
    var initialRequest = runtimeTools.length === 0
        ? options.request
        : schema_1.LLMRequest.update(options.request, {
            tools: __spreadArray(__spreadArray([], options.request.tools.filter(function (tool) { return !runtimeToolNames.has(tool.name); }), true), runtimeTools, true),
        });
    var loop = function (request, step) {
        return effect_1.Stream.unwrap(effect_1.Effect.gen(function () {
            var state, modelStream, continuation;
            return __generator(this, function (_a) {
                state = { assistantContent: [], toolCalls: [], finishReason: undefined };
                modelStream = options
                    .stream(request)
                    .pipe(effect_1.Stream.tap(function (event) { return effect_1.Effect.sync(function () { return accumulate(state, event); }); }));
                continuation = effect_1.Stream.unwrap(effect_1.Effect.gen(function () {
                    var dispatched, resultStream;
                    return __generator(this, function (_a) {
                        switch (_a.label) {
                            case 0:
                                if (state.finishReason !== "tool-calls" || state.toolCalls.length === 0)
                                    return [2 /*return*/, effect_1.Stream.empty];
                                if (options.toolExecution === "none")
                                    return [2 /*return*/, effect_1.Stream.empty];
                                return [5 /*yield**/, __values(effect_1.Effect.forEach(state.toolCalls, function (call) { return dispatch(tools, call).pipe(effect_1.Effect.map(function (result) { return [call, result]; })); }, { concurrency: concurrency }))];
                            case 1:
                                dispatched = _a.sent();
                                resultStream = effect_1.Stream.fromIterable(dispatched.flatMap(function (_a) {
                                    var call = _a[0], result = _a[1];
                                    return emitEvents(call, result);
                                }));
                                if (!options.stopWhen)
                                    return [2 /*return*/, resultStream];
                                if (options.stopWhen({ step: step, request: request }))
                                    return [2 /*return*/, resultStream];
                                return [2 /*return*/, resultStream.pipe(effect_1.Stream.concat(loop(followUpRequest(request, state, dispatched), step + 1)))];
                        }
                    });
                }));
                return [2 /*return*/, modelStream.pipe(effect_1.Stream.concat(continuation))];
            });
        }));
    };
    return loop(initialRequest, 0);
};
exports.stream = stream;
var accumulate = function (state, event) {
    if (event.type === "text-delta") {
        appendStreamingText(state, "text", event.text, event.providerMetadata);
        return;
    }
    if (event.type === "reasoning-delta") {
        appendStreamingText(state, "reasoning", event.text, event.providerMetadata);
        return;
    }
    if (event.type === "tool-call") {
        var part = schema_1.ToolCallPart.make({
            id: event.id,
            name: event.name,
            input: event.input,
            providerExecuted: event.providerExecuted,
            providerMetadata: event.providerMetadata,
        });
        state.assistantContent.push(part);
        if (!event.providerExecuted)
            state.toolCalls.push(part);
        return;
    }
    if (event.type === "tool-result" && event.providerExecuted) {
        state.assistantContent.push(schema_1.ToolResultPart.make({
            id: event.id,
            name: event.name,
            result: event.result,
            providerExecuted: true,
            providerMetadata: event.providerMetadata,
        }));
        return;
    }
    if (event.type === "request-finish") {
        state.finishReason = event.reason;
    }
};
var sameProviderMetadata = function (left, right) {
    return left === right || JSON.stringify(left) === JSON.stringify(right);
};
var mergeProviderMetadata = function (left, right) {
    if (!left)
        return right;
    if (!right)
        return left;
    return Object.fromEntries(Array.from(new Set(__spreadArray(__spreadArray([], Object.keys(left), true), Object.keys(right), true))).map(function (provider) { return [
        provider,
        __assign(__assign({}, left[provider]), right[provider]),
    ]; }));
};
var appendStreamingText = function (state, type, text, providerMetadata) {
    var last = state.assistantContent.at(-1);
    if ((last === null || last === void 0 ? void 0 : last.type) === type && text.length === 0) {
        state.assistantContent[state.assistantContent.length - 1] = __assign(__assign({}, last), { providerMetadata: mergeProviderMetadata(last.providerMetadata, providerMetadata) });
        return;
    }
    if ((last === null || last === void 0 ? void 0 : last.type) === type && sameProviderMetadata(last.providerMetadata, providerMetadata)) {
        state.assistantContent[state.assistantContent.length - 1] = __assign(__assign({}, last), { text: "".concat(last.text).concat(text) });
        return;
    }
    state.assistantContent.push({ type: type, text: text, providerMetadata: providerMetadata });
};
var dispatch = function (tools, call) {
    var tool = tools[call.name];
    if (!tool)
        return effect_1.Effect.succeed({ type: "error", value: "Unknown tool: ".concat(call.name) });
    if (!tool.execute)
        return effect_1.Effect.succeed({ type: "error", value: "Tool has no execute handler: ".concat(call.name) });
    return decodeAndExecute(tool, call.input).pipe(effect_1.Effect.catchTag("LLM.ToolFailure", function (failure) {
        return effect_1.Effect.succeed({ type: "error", value: failure.message });
    }));
};
var decodeAndExecute = function (tool, input) {
    return tool._decode(input).pipe(effect_1.Effect.mapError(function (error) { return new schema_1.ToolFailure({ message: "Invalid tool input: ".concat(error.message) }); }), effect_1.Effect.flatMap(function (decoded) { return tool.execute(decoded); }), effect_1.Effect.flatMap(function (value) {
        return tool._encode(value).pipe(effect_1.Effect.mapError(function (error) {
            return new schema_1.ToolFailure({
                message: "Tool returned an invalid value for its success schema: ".concat(error.message),
            });
        }));
    }), effect_1.Effect.map(function (encoded) { return ({ type: "json", value: encoded }); }));
};
var emitEvents = function (call, result) {
    return result.type === "error"
        ? [
            { type: "tool-error", id: call.id, name: call.name, message: String(result.value) },
            { type: "tool-result", id: call.id, name: call.name, result: result },
        ]
        : [{ type: "tool-result", id: call.id, name: call.name, result: result }];
};
var followUpRequest = function (request, state, dispatched) {
    return schema_1.LLMRequest.update(request, {
        messages: __spreadArray(__spreadArray(__spreadArray([], request.messages, true), [
            schema_1.Message.assistant(state.assistantContent)
        ], false), dispatched.map(function (_a) {
            var call = _a[0], result = _a[1];
            return schema_1.Message.tool({ id: call.id, name: call.name, result: result });
        }), true),
    });
};
exports.ToolRuntime = { stream: exports.stream, stepCountIs: exports.stepCountIs };
