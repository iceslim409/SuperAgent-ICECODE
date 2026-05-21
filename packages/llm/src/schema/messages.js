"use strict";
var __extends = (this && this.__extends) || (function () {
    var extendStatics = function (d, b) {
        extendStatics = Object.setPrototypeOf ||
            ({ __proto__: [] } instanceof Array && function (d, b) { d.__proto__ = b; }) ||
            function (d, b) { for (var p in b) if (Object.prototype.hasOwnProperty.call(b, p)) d[p] = b[p]; };
        return extendStatics(d, b);
    };
    return function (d, b) {
        if (typeof b !== "function" && b !== null)
            throw new TypeError("Class extends value " + String(b) + " is not a constructor or null");
        extendStatics(d, b);
        function __() { this.constructor = d; }
        d.prototype = b === null ? Object.create(b) : (__.prototype = b.prototype, new __());
    };
})();
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
var __spreadArray = (this && this.__spreadArray) || function (to, from, pack) {
    if (pack || arguments.length === 2) for (var i = 0, l = from.length, ar; i < l; i++) {
        if (ar || !(i in from)) {
            if (!ar) ar = Array.prototype.slice.call(from, 0, i);
            ar[i] = from[i];
        }
    }
    return to.concat(ar || Array.prototype.slice.call(from));
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.LLMRequest = exports.ResponseFormat = exports.ToolChoice = exports.ToolDefinition = exports.Message = exports.ContentPart = exports.ReasoningPart = exports.ToolResultPart = exports.ToolCallPart = exports.ToolResultValue = exports.MediaPart = exports.TextPart = exports.SystemPart = void 0;
var effect_1 = require("effect");
var ids_1 = require("./ids");
var options_1 = require("./options");
var isRecord = function (value) {
    return typeof value === "object" && value !== null && !Array.isArray(value);
};
var systemPartSchema = effect_1.Schema.Struct({
    type: effect_1.Schema.Literal("text"),
    text: effect_1.Schema.String,
    cache: effect_1.Schema.optional(options_1.CacheHint),
    metadata: effect_1.Schema.optional(effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.Unknown)),
}).annotate({ identifier: "LLM.SystemPart" });
var makeSystemPart = function (text) { return ({ type: "text", text: text }); };
exports.SystemPart = Object.assign(systemPartSchema, {
    make: makeSystemPart,
    content: function (input) {
        if (input === undefined)
            return [];
        return typeof input === "string" ? [makeSystemPart(input)] : Array.isArray(input) ? __spreadArray([], input, true) : [input];
    },
});
exports.TextPart = effect_1.Schema.Struct({
    type: effect_1.Schema.Literal("text"),
    text: effect_1.Schema.String,
    cache: effect_1.Schema.optional(options_1.CacheHint),
    metadata: effect_1.Schema.optional(effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.Unknown)),
    providerMetadata: effect_1.Schema.optional(ids_1.ProviderMetadata),
}).annotate({ identifier: "LLM.Content.Text" });
exports.MediaPart = effect_1.Schema.Struct({
    type: effect_1.Schema.Literal("media"),
    mediaType: effect_1.Schema.String,
    data: effect_1.Schema.Union([effect_1.Schema.String, effect_1.Schema.Uint8Array]),
    filename: effect_1.Schema.optional(effect_1.Schema.String),
    metadata: effect_1.Schema.optional(effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.Unknown)),
}).annotate({ identifier: "LLM.Content.Media" });
var isToolResultValue = function (value) {
    return isRecord(value) && (value.type === "text" || value.type === "json" || value.type === "error") && "value" in value;
};
exports.ToolResultValue = Object.assign(effect_1.Schema.Struct({
    type: effect_1.Schema.Literals(["json", "text", "error"]),
    value: effect_1.Schema.Unknown,
}).annotate({ identifier: "LLM.ToolResult" }), {
    make: function (value, type) {
        if (type === void 0) { type = "json"; }
        return isToolResultValue(value) ? value : { type: type, value: value };
    },
});
exports.ToolCallPart = Object.assign(effect_1.Schema.Struct({
    type: effect_1.Schema.Literal("tool-call"),
    id: effect_1.Schema.String,
    name: effect_1.Schema.String,
    input: effect_1.Schema.Unknown,
    providerExecuted: effect_1.Schema.optional(effect_1.Schema.Boolean),
    metadata: effect_1.Schema.optional(effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.Unknown)),
    providerMetadata: effect_1.Schema.optional(ids_1.ProviderMetadata),
}).annotate({ identifier: "LLM.Content.ToolCall" }), {
    make: function (input) { return (__assign({ type: "tool-call" }, input)); },
});
exports.ToolResultPart = Object.assign(effect_1.Schema.Struct({
    type: effect_1.Schema.Literal("tool-result"),
    id: effect_1.Schema.String,
    name: effect_1.Schema.String,
    result: exports.ToolResultValue,
    providerExecuted: effect_1.Schema.optional(effect_1.Schema.Boolean),
    metadata: effect_1.Schema.optional(effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.Unknown)),
    providerMetadata: effect_1.Schema.optional(ids_1.ProviderMetadata),
}).annotate({ identifier: "LLM.Content.ToolResult" }), {
    make: function (input) { return ({
        type: "tool-result",
        id: input.id,
        name: input.name,
        result: exports.ToolResultValue.make(input.result, input.resultType),
        providerExecuted: input.providerExecuted,
        metadata: input.metadata,
        providerMetadata: input.providerMetadata,
    }); },
});
exports.ReasoningPart = effect_1.Schema.Struct({
    type: effect_1.Schema.Literal("reasoning"),
    text: effect_1.Schema.String,
    encrypted: effect_1.Schema.optional(effect_1.Schema.String),
    metadata: effect_1.Schema.optional(effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.Unknown)),
    providerMetadata: effect_1.Schema.optional(ids_1.ProviderMetadata),
}).annotate({ identifier: "LLM.Content.Reasoning" });
exports.ContentPart = effect_1.Schema.Union([exports.TextPart, exports.MediaPart, exports.ToolCallPart, exports.ToolResultPart, exports.ReasoningPart]).pipe(effect_1.Schema.toTaggedUnion("type"));
var Message = /** @class */ (function (_super) {
    __extends(Message, _super);
    function Message() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    return Message;
}(effect_1.Schema.Class("LLM.Message")({
    id: effect_1.Schema.optional(effect_1.Schema.String),
    role: ids_1.MessageRole,
    content: effect_1.Schema.Array(exports.ContentPart),
    metadata: effect_1.Schema.optional(effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.Unknown)),
    native: effect_1.Schema.optional(effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.Unknown)),
})));
exports.Message = Message;
(function (Message) {
    Message.text = function (value) { return ({ type: "text", text: value }); };
    Message.content = function (input) {
        return typeof input === "string" ? [Message.text(input)] : Array.isArray(input) ? __spreadArray([], input, true) : [input];
    };
    Message.make = function (input) {
        if (input instanceof Message)
            return input;
        return new Message(__assign(__assign({}, input), { content: Message.content(input.content) }));
    };
    Message.user = function (content) { return Message.make({ role: "user", content: content }); };
    Message.assistant = function (content) { return Message.make({ role: "assistant", content: content }); };
    Message.tool = function (result) {
        return Message.make({ role: "tool", content: ["type" in result ? result : exports.ToolResultPart.make(result)] });
    };
})(Message || (exports.Message = Message = {}));
var ToolDefinition = /** @class */ (function (_super) {
    __extends(ToolDefinition, _super);
    function ToolDefinition() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    return ToolDefinition;
}(effect_1.Schema.Class("LLM.ToolDefinition")({
    name: effect_1.Schema.String,
    description: effect_1.Schema.String,
    inputSchema: ids_1.JsonSchema,
    metadata: effect_1.Schema.optional(effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.Unknown)),
    native: effect_1.Schema.optional(effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.Unknown)),
})));
exports.ToolDefinition = ToolDefinition;
(function (ToolDefinition) {
    /** Normalize tool definition input into the canonical `ToolDefinition` class. */
    ToolDefinition.make = function (input) { return (input instanceof ToolDefinition ? input : new ToolDefinition(input)); };
})(ToolDefinition || (exports.ToolDefinition = ToolDefinition = {}));
var ToolChoice = /** @class */ (function (_super) {
    __extends(ToolChoice, _super);
    function ToolChoice() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    return ToolChoice;
}(effect_1.Schema.Class("LLM.ToolChoice")({
    type: effect_1.Schema.Literals(["auto", "none", "required", "tool"]),
    name: effect_1.Schema.optional(effect_1.Schema.String),
})));
exports.ToolChoice = ToolChoice;
(function (ToolChoice) {
    var isMode = function (value) { return value === "auto" || value === "none" || value === "required"; };
    /** Select a specific named tool. */
    ToolChoice.named = function (value) { return new ToolChoice({ type: "tool", name: value }); };
    /** Normalize ergonomic tool-choice inputs into the canonical `ToolChoice` class. */
    ToolChoice.make = function (input) {
        if (input instanceof ToolChoice)
            return input;
        if (input instanceof ToolDefinition)
            return ToolChoice.named(input.name);
        if (typeof input === "string")
            return isMode(input) ? new ToolChoice({ type: input }) : ToolChoice.named(input);
        return new ToolChoice(input);
    };
})(ToolChoice || (exports.ToolChoice = ToolChoice = {}));
exports.ResponseFormat = effect_1.Schema.Union([
    effect_1.Schema.Struct({ type: effect_1.Schema.Literal("text") }),
    effect_1.Schema.Struct({ type: effect_1.Schema.Literal("json"), schema: ids_1.JsonSchema }),
    effect_1.Schema.Struct({ type: effect_1.Schema.Literal("tool"), tool: ToolDefinition }),
]).pipe(effect_1.Schema.toTaggedUnion("type"));
var LLMRequest = /** @class */ (function (_super) {
    __extends(LLMRequest, _super);
    function LLMRequest() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    return LLMRequest;
}(effect_1.Schema.Class("LLM.Request")({
    id: effect_1.Schema.optional(effect_1.Schema.String),
    model: options_1.ModelRef,
    system: effect_1.Schema.Array(exports.SystemPart),
    messages: effect_1.Schema.Array(Message),
    tools: effect_1.Schema.Array(ToolDefinition),
    toolChoice: effect_1.Schema.optional(ToolChoice),
    generation: effect_1.Schema.optional(options_1.GenerationOptions),
    providerOptions: effect_1.Schema.optional(options_1.ProviderOptions),
    http: effect_1.Schema.optional(options_1.HttpOptions),
    responseFormat: effect_1.Schema.optional(exports.ResponseFormat),
    metadata: effect_1.Schema.optional(effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.Unknown)),
})));
exports.LLMRequest = LLMRequest;
(function (LLMRequest) {
    LLMRequest.input = function (request) { return ({
        id: request.id,
        model: request.model,
        system: request.system,
        messages: request.messages,
        tools: request.tools,
        toolChoice: request.toolChoice,
        generation: request.generation,
        providerOptions: request.providerOptions,
        http: request.http,
        responseFormat: request.responseFormat,
        metadata: request.metadata,
    }); };
    LLMRequest.update = function (request, patch) {
        var _a;
        if (Object.keys(patch).length === 0)
            return request;
        return new LLMRequest(__assign(__assign(__assign({}, LLMRequest.input(request)), patch), { model: (_a = patch.model) !== null && _a !== void 0 ? _a : request.model }));
    };
})(LLMRequest || (exports.LLMRequest = LLMRequest = {}));
