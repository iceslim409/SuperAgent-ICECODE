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
exports.apis = exports.provider = exports.model = exports.workersAI = exports.aiGateway = exports.routes = exports.workersAIRoute = exports.aiGatewayRoute = exports.workersAIBaseURL = exports.aiGatewayBaseURL = exports.workersAIAuthEnvVars = exports.aiGatewayAuthEnvVars = exports.id = exports.workersAIID = exports.aiGatewayID = void 0;
var provider_1 = require("../provider");
var OpenAICompatibleChat = require("../protocols/openai-compatible-chat");
var auth_1 = require("../route/auth");
var auth_options_1 = require("../route/auth-options");
var client_1 = require("../route/client");
var schema_1 = require("../schema");
exports.aiGatewayID = schema_1.ProviderID.make("cloudflare-ai-gateway");
exports.workersAIID = schema_1.ProviderID.make("cloudflare-workers-ai");
exports.id = exports.aiGatewayID;
exports.aiGatewayAuthEnvVars = ["CLOUDFLARE_API_TOKEN", "CF_AIG_TOKEN"];
exports.workersAIAuthEnvVars = ["CLOUDFLARE_API_KEY", "CLOUDFLARE_WORKERS_AI_TOKEN"];
var aiGatewayBaseURL = function (input) {
    var _a;
    if (input.baseURL)
        return input.baseURL;
    if (!input.accountId)
        throw new Error("Cloudflare.aiGateway requires accountId unless baseURL is supplied");
    return "https://gateway.ai.cloudflare.com/v1/".concat(encodeURIComponent(input.accountId), "/").concat(encodeURIComponent(((_a = input.gatewayId) === null || _a === void 0 ? void 0 : _a.trim()) || "default"), "/compat");
};
exports.aiGatewayBaseURL = aiGatewayBaseURL;
var aiGatewayAuth = function (input) {
    if ("auth" in input && input.auth)
        return input.auth;
    var gateway = auth_1.Auth.optional(input.gatewayApiKey, "gatewayApiKey")
        .orElse(auth_1.Auth.config("CLOUDFLARE_API_TOKEN"))
        .orElse(auth_1.Auth.config("CF_AIG_TOKEN"))
        .pipe(auth_1.Auth.bearerHeader("cf-aig-authorization"));
    if (!("apiKey" in input) || input.apiKey === undefined)
        return gateway;
    if (input.gatewayApiKey === undefined)
        return auth_1.Auth.bearer(input.apiKey);
    return auth_1.Auth.bearerHeader("cf-aig-authorization", input.gatewayApiKey).andThen(auth_1.Auth.bearer(input.apiKey));
};
var workersAIBaseURL = function (input) {
    if (input.baseURL)
        return input.baseURL;
    if (!input.accountId)
        throw new Error("Cloudflare.workersAI requires accountId unless baseURL is supplied");
    return "https://api.cloudflare.com/client/v4/accounts/".concat(encodeURIComponent(input.accountId), "/ai/v1");
};
exports.workersAIBaseURL = workersAIBaseURL;
var workersAIAuth = function (input) {
    return auth_options_1.AuthOptions.bearer(input, exports.workersAIAuthEnvVars);
};
exports.aiGatewayRoute = OpenAICompatibleChat.route.with({
    id: "cloudflare-ai-gateway",
    provider: exports.aiGatewayID,
});
exports.workersAIRoute = OpenAICompatibleChat.route.with({
    id: "cloudflare-workers-ai",
    provider: exports.workersAIID,
});
exports.routes = [exports.aiGatewayRoute, exports.workersAIRoute];
var aiGatewayModel = client_1.Route.model(exports.aiGatewayRoute, {
    provider: exports.id,
}, {
    mapInput: function (input) {
        var _accountId = input.accountId, _gatewayId = input.gatewayId, _apiKey = input.apiKey, _gatewayApiKey = input.gatewayApiKey, _auth = input.auth, rest = __rest(input, ["accountId", "gatewayId", "apiKey", "gatewayApiKey", "auth"]);
        return __assign(__assign({}, rest), { auth: aiGatewayAuth(input), baseURL: (0, exports.aiGatewayBaseURL)(input) });
    },
});
var workersAIModel = client_1.Route.model(exports.workersAIRoute, {
    provider: exports.workersAIID,
}, {
    mapInput: function (input) {
        var _accountId = input.accountId, _apiKey = input.apiKey, _auth = input.auth, rest = __rest(input, ["accountId", "apiKey", "auth"]);
        return __assign(__assign({}, rest), { auth: workersAIAuth(input), baseURL: (0, exports.workersAIBaseURL)(input) });
    },
});
var aiGateway = function (modelID, options) {
    return aiGatewayModel(__assign(__assign({}, options), { id: modelID }));
};
exports.aiGateway = aiGateway;
var workersAI = function (modelID, options) {
    return workersAIModel(__assign(__assign({}, options), { id: modelID }));
};
exports.workersAI = workersAI;
exports.model = exports.aiGateway;
exports.provider = provider_1.Provider.make({
    id: exports.id,
    model: exports.model,
    apis: { aiGateway: exports.aiGateway, workersAI: exports.workersAI },
});
exports.apis = exports.provider.apis;
