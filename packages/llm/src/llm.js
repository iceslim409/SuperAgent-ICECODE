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
exports.GenerateObjectResponse = exports.updateRequest = exports.request = exports.requestInput = exports.stepCountIs = exports.stream = exports.generate = exports.generation = exports.toolChoice = exports.toolChoiceName = exports.toolMessage = exports.toolResult = exports.toolCall = exports.toolDefinition = exports.model = exports.assistant = exports.user = exports.message = exports.system = exports.text = exports.limits = void 0;
exports.generateObject = generateObject;
var effect_1 = require("effect");
var client_1 = require("./route/client");
var schema_1 = require("./schema");
var tool_1 = require("./tool");
exports.limits = client_1.modelLimits;
exports.text = schema_1.Message.text;
exports.system = schema_1.SystemPart.make;
exports.message = schema_1.Message.make;
exports.user = schema_1.Message.user;
exports.assistant = schema_1.Message.assistant;
exports.model = client_1.modelRef;
exports.toolDefinition = schema_1.ToolDefinition.make;
exports.toolCall = schema_1.ToolCallPart.make;
exports.toolResult = schema_1.ToolResultPart.make;
exports.toolMessage = schema_1.Message.tool;
exports.toolChoiceName = schema_1.ToolChoice.named;
exports.toolChoice = schema_1.ToolChoice.make;
exports.generation = schema_1.GenerationOptions.make;
exports.generate = client_1.LLMClient.generate;
exports.stream = client_1.LLMClient.stream;
exports.stepCountIs = client_1.LLMClient.stepCountIs;
var requestInput = function (input) { return (__assign({}, schema_1.LLMRequest.input(input))); };
exports.requestInput = requestInput;
var request = function (input) {
    var _a, _b;
    var requestSystem = input.system, prompt = input.prompt, messages = input.messages, tools = input.tools, requestToolChoice = input.toolChoice, requestGeneration = input.generation, requestProviderOptions = input.providerOptions, requestHttp = input.http, rest = __rest(input, ["system", "prompt", "messages", "tools", "toolChoice", "generation", "providerOptions", "http"]);
    return new schema_1.LLMRequest(__assign(__assign({}, rest), { system: schema_1.SystemPart.content(requestSystem), messages: __spreadArray(__spreadArray([], ((_a = messages === null || messages === void 0 ? void 0 : messages.map(exports.message)) !== null && _a !== void 0 ? _a : []), true), (prompt === undefined ? [] : [(0, exports.user)(prompt)]), true), tools: (_b = tools === null || tools === void 0 ? void 0 : tools.map(exports.toolDefinition)) !== null && _b !== void 0 ? _b : [], toolChoice: requestToolChoice ? (0, exports.toolChoice)(requestToolChoice) : undefined, generation: requestGeneration === undefined ? undefined : (0, exports.generation)(requestGeneration), providerOptions: requestProviderOptions, http: requestHttp === undefined ? undefined : schema_1.HttpOptions.make(requestHttp) }));
};
exports.request = request;
var updateRequest = function (input, patch) {
    return (0, exports.request)(__assign(__assign({}, (0, exports.requestInput)(input)), patch));
};
exports.updateRequest = updateRequest;
var GENERATE_OBJECT_TOOL_NAME = "generate_object";
var GENERATE_OBJECT_TOOL_DESCRIPTION = "Return the structured result by calling this tool.";
var GenerateObjectResponse = /** @class */ (function () {
    function GenerateObjectResponse(object, response) {
        this.object = object;
        this.response = response;
    }
    Object.defineProperty(GenerateObjectResponse.prototype, "events", {
        get: function () {
            return this.response.events;
        },
        enumerable: false,
        configurable: true
    });
    Object.defineProperty(GenerateObjectResponse.prototype, "usage", {
        get: function () {
            return this.response.usage;
        },
        enumerable: false,
        configurable: true
    });
    return GenerateObjectResponse;
}());
exports.GenerateObjectResponse = GenerateObjectResponse;
var runGenerateObject = effect_1.Effect.fn("LLM.generateObject")(function (options, tool) {
    var baseRequest, generateRequest, response, call, object;
    var _a;
    return __generator(this, function (_b) {
        switch (_b.label) {
            case 0:
                baseRequest = (0, exports.request)(options);
                generateRequest = schema_1.LLMRequest.update(baseRequest, {
                    toolChoice: schema_1.ToolChoice.named(GENERATE_OBJECT_TOOL_NAME),
                });
                return [5 /*yield**/, __values(client_1.LLMClient.generate({
                        request: generateRequest,
                        tools: (_a = {}, _a[GENERATE_OBJECT_TOOL_NAME] = tool, _a),
                        toolExecution: "none",
                    }))];
            case 1:
                response = _b.sent();
                call = response.toolCalls.find(function (event) { return schema_1.LLMEvent.is.toolCall(event) && event.name === GENERATE_OBJECT_TOOL_NAME; });
                if (!(!call || !schema_1.LLMEvent.is.toolCall(call))) return [3 /*break*/, 3];
                return [5 /*yield**/, __values(new schema_1.LLMError({
                        module: "LLM",
                        method: "generateObject",
                        reason: new schema_1.InvalidProviderOutputReason({
                            message: "generateObject: model did not call the forced `".concat(GENERATE_OBJECT_TOOL_NAME, "` tool"),
                        }),
                    }))];
            case 2: return [2 /*return*/, _b.sent()];
            case 3: return [5 /*yield**/, __values(tool._decode(call.input).pipe(effect_1.Effect.mapError(function (error) {
                    return new schema_1.LLMError({
                        module: "LLM",
                        method: "generateObject",
                        reason: new schema_1.InvalidProviderOutputReason({
                            message: "generateObject: tool input failed schema decode: ".concat(error.message),
                        }),
                    });
                })))];
            case 4:
                object = _b.sent();
                return [2 /*return*/, new GenerateObjectResponse(object, response)];
        }
    });
});
function generateObject(options) {
    if ("schema" in options) {
        var schema = options.schema, rest_1 = __rest(options, ["schema"]);
        return runGenerateObject(rest_1, (0, tool_1.make)({
            description: GENERATE_OBJECT_TOOL_DESCRIPTION,
            parameters: schema,
            success: effect_1.Schema.Unknown,
            execute: function () { return effect_1.Effect.void; },
        }));
    }
    var jsonSchema = options.jsonSchema, rest = __rest(options, ["jsonSchema"]);
    return runGenerateObject(rest, (0, tool_1.make)({
        description: GENERATE_OBJECT_TOOL_DESCRIPTION,
        jsonSchema: jsonSchema,
        execute: function () { return effect_1.Effect.void; },
    }));
}
