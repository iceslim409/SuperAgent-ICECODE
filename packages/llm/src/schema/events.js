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
Object.defineProperty(exports, "__esModule", { value: true });
exports.LLMResponse = exports.PreparedRequest = exports.LLMEvent = exports.ProviderErrorEvent = exports.RequestFinish = exports.StepFinish = exports.ToolError = exports.ToolResult = exports.ToolCall = exports.ToolInputDelta = exports.ReasoningDelta = exports.TextEnd = exports.TextDelta = exports.TextStart = exports.StepStart = exports.RequestStart = exports.Usage = void 0;
var effect_1 = require("effect");
var ids_1 = require("./ids");
var options_1 = require("./options");
var messages_1 = require("./messages");
var Usage = /** @class */ (function (_super) {
    __extends(Usage, _super);
    function Usage() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    return Usage;
}(effect_1.Schema.Class("LLM.Usage")({
    inputTokens: effect_1.Schema.optional(effect_1.Schema.Number),
    outputTokens: effect_1.Schema.optional(effect_1.Schema.Number),
    reasoningTokens: effect_1.Schema.optional(effect_1.Schema.Number),
    cacheReadInputTokens: effect_1.Schema.optional(effect_1.Schema.Number),
    cacheWriteInputTokens: effect_1.Schema.optional(effect_1.Schema.Number),
    totalTokens: effect_1.Schema.optional(effect_1.Schema.Number),
    native: effect_1.Schema.optional(effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.Unknown)),
})));
exports.Usage = Usage;
exports.RequestStart = effect_1.Schema.Struct({
    type: effect_1.Schema.Literal("request-start"),
    id: effect_1.Schema.String,
    model: options_1.ModelRef,
}).annotate({ identifier: "LLM.Event.RequestStart" });
exports.StepStart = effect_1.Schema.Struct({
    type: effect_1.Schema.Literal("step-start"),
    index: effect_1.Schema.Number,
}).annotate({ identifier: "LLM.Event.StepStart" });
exports.TextStart = effect_1.Schema.Struct({
    type: effect_1.Schema.Literal("text-start"),
    id: effect_1.Schema.String,
    providerMetadata: effect_1.Schema.optional(ids_1.ProviderMetadata),
}).annotate({ identifier: "LLM.Event.TextStart" });
exports.TextDelta = effect_1.Schema.Struct({
    type: effect_1.Schema.Literal("text-delta"),
    id: effect_1.Schema.optional(effect_1.Schema.String),
    text: effect_1.Schema.String,
    providerMetadata: effect_1.Schema.optional(ids_1.ProviderMetadata),
}).annotate({ identifier: "LLM.Event.TextDelta" });
exports.TextEnd = effect_1.Schema.Struct({
    type: effect_1.Schema.Literal("text-end"),
    id: effect_1.Schema.String,
    providerMetadata: effect_1.Schema.optional(ids_1.ProviderMetadata),
}).annotate({ identifier: "LLM.Event.TextEnd" });
exports.ReasoningDelta = effect_1.Schema.Struct({
    type: effect_1.Schema.Literal("reasoning-delta"),
    id: effect_1.Schema.optional(effect_1.Schema.String),
    text: effect_1.Schema.String,
    providerMetadata: effect_1.Schema.optional(ids_1.ProviderMetadata),
}).annotate({ identifier: "LLM.Event.ReasoningDelta" });
exports.ToolInputDelta = effect_1.Schema.Struct({
    type: effect_1.Schema.Literal("tool-input-delta"),
    id: effect_1.Schema.String,
    name: effect_1.Schema.String,
    text: effect_1.Schema.String,
    providerMetadata: effect_1.Schema.optional(ids_1.ProviderMetadata),
}).annotate({ identifier: "LLM.Event.ToolInputDelta" });
exports.ToolCall = effect_1.Schema.Struct({
    type: effect_1.Schema.Literal("tool-call"),
    id: effect_1.Schema.String,
    name: effect_1.Schema.String,
    input: effect_1.Schema.Unknown,
    providerExecuted: effect_1.Schema.optional(effect_1.Schema.Boolean),
    providerMetadata: effect_1.Schema.optional(ids_1.ProviderMetadata),
}).annotate({ identifier: "LLM.Event.ToolCall" });
exports.ToolResult = effect_1.Schema.Struct({
    type: effect_1.Schema.Literal("tool-result"),
    id: effect_1.Schema.String,
    name: effect_1.Schema.String,
    result: messages_1.ToolResultValue,
    providerExecuted: effect_1.Schema.optional(effect_1.Schema.Boolean),
    providerMetadata: effect_1.Schema.optional(ids_1.ProviderMetadata),
}).annotate({ identifier: "LLM.Event.ToolResult" });
exports.ToolError = effect_1.Schema.Struct({
    type: effect_1.Schema.Literal("tool-error"),
    id: effect_1.Schema.String,
    name: effect_1.Schema.String,
    message: effect_1.Schema.String,
    providerMetadata: effect_1.Schema.optional(ids_1.ProviderMetadata),
}).annotate({ identifier: "LLM.Event.ToolError" });
exports.StepFinish = effect_1.Schema.Struct({
    type: effect_1.Schema.Literal("step-finish"),
    index: effect_1.Schema.Number,
    reason: ids_1.FinishReason,
    usage: effect_1.Schema.optional(Usage),
    providerMetadata: effect_1.Schema.optional(ids_1.ProviderMetadata),
}).annotate({ identifier: "LLM.Event.StepFinish" });
exports.RequestFinish = effect_1.Schema.Struct({
    type: effect_1.Schema.Literal("request-finish"),
    reason: ids_1.FinishReason,
    usage: effect_1.Schema.optional(Usage),
    providerMetadata: effect_1.Schema.optional(ids_1.ProviderMetadata),
}).annotate({ identifier: "LLM.Event.RequestFinish" });
exports.ProviderErrorEvent = effect_1.Schema.Struct({
    type: effect_1.Schema.Literal("provider-error"),
    message: effect_1.Schema.String,
    retryable: effect_1.Schema.optional(effect_1.Schema.Boolean),
    providerMetadata: effect_1.Schema.optional(ids_1.ProviderMetadata),
}).annotate({ identifier: "LLM.Event.ProviderError" });
var llmEventTagged = effect_1.Schema.Union([
    exports.RequestStart,
    exports.StepStart,
    exports.TextStart,
    exports.TextDelta,
    exports.TextEnd,
    exports.ReasoningDelta,
    exports.ToolInputDelta,
    exports.ToolCall,
    exports.ToolResult,
    exports.ToolError,
    exports.StepFinish,
    exports.RequestFinish,
    exports.ProviderErrorEvent,
]).pipe(effect_1.Schema.toTaggedUnion("type"));
/**
 * camelCase aliases for `LLMEvent.guards` (provided by `Schema.toTaggedUnion`).
 * Lets consumers write `events.filter(LLMEvent.is.toolCall)` instead of
 * `events.filter(LLMEvent.guards["tool-call"])`.
 */
exports.LLMEvent = Object.assign(llmEventTagged, {
    is: {
        requestStart: llmEventTagged.guards["request-start"],
        stepStart: llmEventTagged.guards["step-start"],
        textStart: llmEventTagged.guards["text-start"],
        textDelta: llmEventTagged.guards["text-delta"],
        textEnd: llmEventTagged.guards["text-end"],
        reasoningDelta: llmEventTagged.guards["reasoning-delta"],
        toolInputDelta: llmEventTagged.guards["tool-input-delta"],
        toolCall: llmEventTagged.guards["tool-call"],
        toolResult: llmEventTagged.guards["tool-result"],
        toolError: llmEventTagged.guards["tool-error"],
        stepFinish: llmEventTagged.guards["step-finish"],
        requestFinish: llmEventTagged.guards["request-finish"],
        providerError: llmEventTagged.guards["provider-error"],
    },
});
var PreparedRequest = /** @class */ (function (_super) {
    __extends(PreparedRequest, _super);
    function PreparedRequest() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    return PreparedRequest;
}(effect_1.Schema.Class("LLM.PreparedRequest")({
    id: effect_1.Schema.String,
    route: ids_1.RouteID,
    protocol: ids_1.ProtocolID,
    model: options_1.ModelRef,
    body: effect_1.Schema.Unknown,
    metadata: effect_1.Schema.optional(effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.Unknown)),
})));
exports.PreparedRequest = PreparedRequest;
var responseText = function (events) {
    return events
        .filter(exports.LLMEvent.is.textDelta)
        .map(function (event) { return event.text; })
        .join("");
};
var responseReasoning = function (events) {
    return events
        .filter(exports.LLMEvent.is.reasoningDelta)
        .map(function (event) { return event.text; })
        .join("");
};
var responseUsage = function (events) {
    return events.reduce(function (usage, event) { return ("usage" in event && event.usage !== undefined ? event.usage : usage); }, undefined);
};
var LLMResponse = /** @class */ (function (_super) {
    __extends(LLMResponse, _super);
    function LLMResponse() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    Object.defineProperty(LLMResponse.prototype, "text", {
        /** Concatenated assistant text assembled from streamed `text-delta` events. */
        get: function () {
            return responseText(this.events);
        },
        enumerable: false,
        configurable: true
    });
    Object.defineProperty(LLMResponse.prototype, "reasoning", {
        /** Concatenated reasoning text assembled from streamed `reasoning-delta` events. */
        get: function () {
            return responseReasoning(this.events);
        },
        enumerable: false,
        configurable: true
    });
    Object.defineProperty(LLMResponse.prototype, "toolCalls", {
        /** Completed tool calls emitted by the provider. */
        get: function () {
            return this.events.filter(exports.LLMEvent.is.toolCall);
        },
        enumerable: false,
        configurable: true
    });
    return LLMResponse;
}(effect_1.Schema.Class("LLM.Response")({
    events: effect_1.Schema.Array(exports.LLMEvent),
    usage: effect_1.Schema.optional(Usage),
})));
exports.LLMResponse = LLMResponse;
(function (LLMResponse) {
    /** Concatenate assistant text from a response or collected event list. */
    LLMResponse.text = function (response) { return responseText(response.events); };
    /** Return response usage, falling back to the latest usage-bearing event. */
    LLMResponse.usage = function (response) { var _a; return (_a = response.usage) !== null && _a !== void 0 ? _a : responseUsage(response.events); };
    /** Return completed tool calls from a response or collected event list. */
    LLMResponse.toolCalls = function (response) { return response.events.filter(exports.LLMEvent.is.toolCall); };
    /** Concatenate reasoning text from a response or collected event list. */
    LLMResponse.reasoning = function (response) { return responseReasoning(response.events); };
})(LLMResponse || (exports.LLMResponse = LLMResponse = {}));
