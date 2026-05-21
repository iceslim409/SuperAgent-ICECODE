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
exports.apis = exports.provider = exports.model = exports.chat = exports.responses = exports.routes = exports.shouldUseResponsesApi = exports.id = void 0;
var client_1 = require("../route/client");
var provider_1 = require("../provider");
var schema_1 = require("../schema");
var OpenAIChat = require("../protocols/openai-chat");
var OpenAIResponses = require("../protocols/openai-responses");
var openai_options_1 = require("./openai-options");
exports.id = schema_1.ProviderID.make("github-copilot");
var shouldUseResponsesApi = function (modelID) {
    var model = String(modelID);
    var match = /^gpt-(\d+)/.exec(model);
    if (!match)
        return false;
    return Number(match[1]) >= 5 && !model.startsWith("gpt-5-mini");
};
exports.shouldUseResponsesApi = shouldUseResponsesApi;
exports.routes = [OpenAIResponses.route, OpenAIChat.route];
var mapInput = function (input) { return (0, openai_options_1.withOpenAIOptions)(input.id, input); };
var chatModel = client_1.Route.model(OpenAIChat.route, { provider: exports.id }, { mapInput: mapInput });
var responsesModel = client_1.Route.model(OpenAIResponses.route, { provider: exports.id }, { mapInput: mapInput });
var responses = function (modelID, options) {
    return responsesModel(__assign(__assign({}, options), { id: modelID }));
};
exports.responses = responses;
var chat = function (modelID, options) { return chatModel(__assign(__assign({}, options), { id: modelID })); };
exports.chat = chat;
var model = function (modelID, options) {
    var create = (0, exports.shouldUseResponsesApi)(modelID) ? responsesModel : chatModel;
    return create(__assign(__assign({}, options), { id: modelID }));
};
exports.model = model;
exports.provider = provider_1.Provider.make({
    id: exports.id,
    model: exports.model,
    apis: { responses: exports.responses, chat: exports.chat },
});
exports.apis = exports.provider.apis;
