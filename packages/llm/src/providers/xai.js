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
Object.defineProperty(exports, "__esModule", { value: true });
exports.apis = exports.model = exports.provider = exports.chat = exports.responses = exports.routes = exports.id = void 0;
var auth_options_1 = require("../route/auth-options");
var client_1 = require("../route/client");
var provider_1 = require("../provider");
var schema_1 = require("../schema");
var OpenAICompatibleProfiles = require("./openai-compatible-profile");
var OpenAICompatibleChat = require("../protocols/openai-compatible-chat");
var OpenAIResponses = require("../protocols/openai-responses");
exports.id = schema_1.ProviderID.make("xai");
exports.routes = [OpenAIResponses.route, OpenAICompatibleChat.route];
var responsesModel = client_1.Route.model(OpenAIResponses.route, { provider: exports.id });
var chatModel = OpenAICompatibleChat.model;
var auth = function (options) { return auth_options_1.AuthOptions.bearer(options, "XAI_API_KEY"); };
var responses = function (modelID, options) {
    var _a;
    if (options === void 0) { options = {}; }
    var _ = options.apiKey, rest = __rest(options, ["apiKey"]);
    return responsesModel(__assign(__assign({}, rest), { auth: auth(options), id: modelID, baseURL: (_a = options.baseURL) !== null && _a !== void 0 ? _a : OpenAICompatibleProfiles.profiles.xai.baseURL }));
};
exports.responses = responses;
var chat = function (modelID, options) {
    var _a;
    if (options === void 0) { options = {}; }
    var _ = options.apiKey, rest = __rest(options, ["apiKey"]);
    return chatModel(__assign(__assign({}, rest), { auth: auth(options), id: modelID, provider: exports.id, baseURL: (_a = options.baseURL) !== null && _a !== void 0 ? _a : OpenAICompatibleProfiles.profiles.xai.baseURL }));
};
exports.chat = chat;
exports.provider = provider_1.Provider.make({
    id: exports.id,
    model: exports.responses,
    apis: { responses: exports.responses, chat: exports.chat },
});
exports.model = exports.provider.model;
exports.apis = exports.provider.apis;
