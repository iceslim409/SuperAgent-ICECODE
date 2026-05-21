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
exports.apis = exports.model = exports.provider = exports.chat = exports.responsesWebSocket = exports.responses = exports.routes = exports.id = void 0;
var auth_options_1 = require("../route/auth-options");
var provider_1 = require("../provider");
var schema_1 = require("../schema");
var OpenAIChat = require("../protocols/openai-chat");
var OpenAIResponses = require("../protocols/openai-responses");
var openai_options_1 = require("./openai-options");
exports.id = schema_1.ProviderID.make("openai");
exports.routes = [OpenAIResponses.route, OpenAIResponses.webSocketRoute, OpenAIChat.route];
var auth = function (options) { return auth_options_1.AuthOptions.bearer(options, "OPENAI_API_KEY"); };
var responses = function (id, options) {
    if (options === void 0) { options = {}; }
    var _ = options.apiKey, rest = __rest(options, ["apiKey"]);
    return OpenAIResponses.model((0, openai_options_1.withOpenAIOptions)(id, __assign(__assign({}, rest), { auth: auth(options) }), { textVerbosity: true }));
};
exports.responses = responses;
var responsesWebSocket = function (id, options) {
    if (options === void 0) { options = {}; }
    var _ = options.apiKey, rest = __rest(options, ["apiKey"]);
    return OpenAIResponses.webSocketModel((0, openai_options_1.withOpenAIOptions)(id, __assign(__assign({}, rest), { auth: auth(options) }), { textVerbosity: true }));
};
exports.responsesWebSocket = responsesWebSocket;
var chat = function (id, options) {
    if (options === void 0) { options = {}; }
    var _ = options.apiKey, rest = __rest(options, ["apiKey"]);
    return OpenAIChat.model((0, openai_options_1.withOpenAIOptions)(id, __assign(__assign({}, rest), { auth: auth(options) })));
};
exports.chat = chat;
exports.provider = provider_1.Provider.make({
    id: exports.id,
    model: exports.responses,
    apis: { responses: exports.responses, responsesWebSocket: exports.responsesWebSocket, chat: exports.chat },
});
exports.model = exports.provider.model;
exports.apis = exports.provider.apis;
