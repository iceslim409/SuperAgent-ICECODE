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
exports.apis = exports.provider = exports.model = exports.chat = exports.responses = exports.routes = exports.id = void 0;
var auth_1 = require("../route/auth");
var client_1 = require("../route/client");
var provider_1 = require("../provider");
var schema_1 = require("../schema");
var OpenAIChat = require("../protocols/openai-chat");
var OpenAIResponses = require("../protocols/openai-responses");
var openai_options_1 = require("./openai-options");
exports.id = schema_1.ProviderID.make("azure");
var routeAuth = auth_1.Auth.remove("authorization").andThen(auth_1.Auth.apiKeyHeader("api-key"));
var resourceBaseURL = function (resourceName) { return "https://".concat(resourceName.trim(), ".openai.azure.com/openai/v1"); };
var responsesRoute = OpenAIResponses.route.with({
    id: "azure-openai-responses",
    provider: exports.id,
    transport: OpenAIResponses.httpTransport.with({ auth: routeAuth }),
});
var chatRoute = OpenAIChat.route.with({
    id: "azure-openai-chat",
    provider: exports.id,
    transport: OpenAIChat.httpTransport.with({ auth: routeAuth }),
});
exports.routes = [responsesRoute, chatRoute];
var mapInput = function (input) {
    var _a, _b, _c;
    var _ = input.apiKey, apiVersion = input.apiVersion, resourceName = input.resourceName, useCompletionUrls = input.useCompletionUrls, rest = __rest(input, ["apiKey", "apiVersion", "resourceName", "useCompletionUrls"]);
    return __assign(__assign({}, (0, openai_options_1.withOpenAIOptions)(input.id, rest)), { auth: "auth" in input && input.auth
            ? input.auth
            : auth_1.Auth.remove("authorization").andThen(auth_1.Auth.optional("apiKey" in input ? input.apiKey : undefined, "apiKey")
                .orElse(auth_1.Auth.config("AZURE_OPENAI_API_KEY"))
                .pipe(auth_1.Auth.header("api-key"))), 
        // AtLeastOne guarantees at least one is set; baseURL wins if both are.
        baseURL: (_a = rest.baseURL) !== null && _a !== void 0 ? _a : resourceBaseURL(resourceName), queryParams: __assign(__assign({}, rest.queryParams), { "api-version": (_c = apiVersion !== null && apiVersion !== void 0 ? apiVersion : (_b = rest.queryParams) === null || _b === void 0 ? void 0 : _b["api-version"]) !== null && _c !== void 0 ? _c : "v1" }) });
};
var chatModel = client_1.Route.model(chatRoute, {}, { mapInput: mapInput });
var responsesModel = client_1.Route.model(responsesRoute, {}, { mapInput: mapInput });
var responses = function (modelID, options) {
    return responsesModel(__assign(__assign({}, options), { id: modelID }));
};
exports.responses = responses;
var chat = function (modelID, options) { return chatModel(__assign(__assign({}, options), { id: modelID })); };
exports.chat = chat;
var model = function (modelID, options) {
    if (options.useCompletionUrls === true)
        return (0, exports.chat)(modelID, options);
    return (0, exports.responses)(modelID, options);
};
exports.model = model;
exports.provider = provider_1.Provider.make({
    id: exports.id,
    model: exports.model,
    apis: { responses: exports.responses, chat: exports.chat },
});
exports.apis = exports.provider.apis;
