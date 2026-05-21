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
Object.defineProperty(exports, "__esModule", { value: true });
exports.OpenAIProviderOptions = exports.withOpenAIOptions = exports.openAIDefaultOptions = exports.gpt5DefaultOptions = void 0;
var schema_1 = require("../schema");
var definedEntries = function (input) {
    return Object.entries(input).filter(function (entry) { return entry[1] !== undefined; });
};
var openAIProviderOptions = function (options) {
    var openai = Object.fromEntries(definedEntries({
        store: options === null || options === void 0 ? void 0 : options.store,
        promptCacheKey: options === null || options === void 0 ? void 0 : options.promptCacheKey,
        reasoningEffort: options === null || options === void 0 ? void 0 : options.reasoningEffort,
        reasoningSummary: options === null || options === void 0 ? void 0 : options.reasoningSummary,
        includeEncryptedReasoning: options === null || options === void 0 ? void 0 : options.includeEncryptedReasoning,
        textVerbosity: options === null || options === void 0 ? void 0 : options.textVerbosity,
    }));
    if (Object.keys(openai).length === 0)
        return undefined;
    return { openai: openai };
};
var gpt5DefaultOptions = function (modelID, options) {
    if (options === void 0) { options = {}; }
    var id = modelID.toLowerCase();
    if (!id.includes("gpt-5") || id.includes("gpt-5-chat") || id.includes("gpt-5-pro"))
        return undefined;
    return openAIProviderOptions({
        reasoningEffort: "medium",
        reasoningSummary: "auto",
        textVerbosity: options.textVerbosity === true && id.includes("gpt-5.") && !id.includes("codex") && !id.includes("-chat")
            ? "low"
            : undefined,
    });
};
exports.gpt5DefaultOptions = gpt5DefaultOptions;
var openAIDefaultOptions = function (modelID, options) {
    if (options === void 0) { options = {}; }
    return (0, schema_1.mergeProviderOptions)(openAIProviderOptions({ store: false }), (0, exports.gpt5DefaultOptions)(modelID, options));
};
exports.openAIDefaultOptions = openAIDefaultOptions;
var withOpenAIOptions = function (modelID, options, defaults) {
    if (defaults === void 0) { defaults = {}; }
    return __assign(__assign({}, options), { id: modelID, providerOptions: (0, schema_1.mergeProviderOptions)((0, exports.openAIDefaultOptions)(modelID, defaults), options.providerOptions) });
};
exports.withOpenAIOptions = withOpenAIOptions;
exports.OpenAIProviderOptions = require("./openai-options");
