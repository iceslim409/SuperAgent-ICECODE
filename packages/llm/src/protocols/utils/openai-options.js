"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.OpenAIOptions = exports.textVerbosity = exports.promptCacheKey = exports.encryptedReasoning = exports.reasoningSummary = exports.reasoningEffort = exports.store = exports.isReasoningEffort = exports.OpenAITextVerbosity = exports.OpenAIReasoningEffort = exports.OpenAIReasoningEfforts = void 0;
var effect_1 = require("effect");
var schema_1 = require("../../schema");
exports.OpenAIReasoningEfforts = schema_1.ReasoningEfforts.filter(function (effort) { return effort !== "max"; });
var REASONING_EFFORTS = new Set(schema_1.ReasoningEfforts);
var OPENAI_REASONING_EFFORTS = new Set(exports.OpenAIReasoningEfforts);
var TEXT_VERBOSITY = new Set(["low", "medium", "high"]);
exports.OpenAIReasoningEffort = effect_1.Schema.Literals(exports.OpenAIReasoningEfforts);
exports.OpenAITextVerbosity = schema_1.TextVerbosity;
var isAnyReasoningEffort = function (effort) {
    return typeof effort === "string" && REASONING_EFFORTS.has(effort);
};
var isReasoningEffort = function (effort) {
    return typeof effort === "string" && OPENAI_REASONING_EFFORTS.has(effort);
};
exports.isReasoningEffort = isReasoningEffort;
var isTextVerbosity = function (value) {
    return typeof value === "string" && TEXT_VERBOSITY.has(value);
};
var options = function (request) { var _a; return (_a = request.providerOptions) === null || _a === void 0 ? void 0 : _a.openai; };
var store = function (request) {
    var _a;
    var value = (_a = options(request)) === null || _a === void 0 ? void 0 : _a.store;
    return typeof value === "boolean" ? value : undefined;
};
exports.store = store;
var reasoningEffort = function (request) {
    var _a;
    var value = (_a = options(request)) === null || _a === void 0 ? void 0 : _a.reasoningEffort;
    return isAnyReasoningEffort(value) ? value : undefined;
};
exports.reasoningEffort = reasoningEffort;
var reasoningSummary = function (request) {
    var _a;
    return ((_a = options(request)) === null || _a === void 0 ? void 0 : _a.reasoningSummary) === "auto" ? "auto" : undefined;
};
exports.reasoningSummary = reasoningSummary;
var encryptedReasoning = function (request) { var _a; return ((_a = options(request)) === null || _a === void 0 ? void 0 : _a.includeEncryptedReasoning) === true ? true : undefined; };
exports.encryptedReasoning = encryptedReasoning;
var promptCacheKey = function (request) {
    var _a;
    var value = (_a = options(request)) === null || _a === void 0 ? void 0 : _a.promptCacheKey;
    return typeof value === "string" ? value : undefined;
};
exports.promptCacheKey = promptCacheKey;
var textVerbosity = function (request) {
    var _a;
    var value = (_a = options(request)) === null || _a === void 0 ? void 0 : _a.textVerbosity;
    return isTextVerbosity(value) ? value : undefined;
};
exports.textVerbosity = textVerbosity;
exports.OpenAIOptions = require("./openai-options");
