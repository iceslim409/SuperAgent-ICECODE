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
exports.provider = exports.model = exports.routes = exports.route = exports.protocol = exports.id = exports.profile = void 0;
var effect_1 = require("effect");
var client_1 = require("../route/client");
var endpoint_1 = require("../route/endpoint");
var framing_1 = require("../route/framing");
var provider_1 = require("../provider");
var protocol_1 = require("../route/protocol");
var schema_1 = require("../schema");
var OpenAICompatibleProfiles = require("./openai-compatible-profile");
var OpenAIChat = require("../protocols/openai-chat");
var shared_1 = require("../protocols/shared");
exports.profile = OpenAICompatibleProfiles.profiles.openrouter;
exports.id = schema_1.ProviderID.make(exports.profile.provider);
var ADAPTER = "openrouter";
var OpenRouterBody = effect_1.Schema.StructWithRest(effect_1.Schema.Struct(OpenAIChat.bodyFields), [
    effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.Any),
]);
exports.protocol = protocol_1.Protocol.make({
    id: "openrouter-chat",
    body: {
        schema: OpenRouterBody,
        from: function (request) {
            return OpenAIChat.protocol.body.from(request).pipe(effect_1.Effect.map(function (body) {
                var _a;
                return (__assign(__assign({}, body), bodyOptions((_a = request.providerOptions) === null || _a === void 0 ? void 0 : _a.openrouter)));
            }));
        },
    },
    stream: OpenAIChat.protocol.stream,
});
var bodyOptions = function (input) {
    var openrouter = (0, shared_1.isRecord)(input) ? input : {};
    return __assign(__assign(__assign({}, (openrouter.usage === true
        ? { usage: { include: true } }
        : (0, shared_1.isRecord)(openrouter.usage)
            ? { usage: openrouter.usage }
            : {})), ((0, shared_1.isRecord)(openrouter.reasoning) ? { reasoning: openrouter.reasoning } : {})), (typeof openrouter.promptCacheKey === "string" ? { prompt_cache_key: openrouter.promptCacheKey } : {}));
};
exports.route = client_1.Route.make({
    id: ADAPTER,
    protocol: exports.protocol,
    endpoint: endpoint_1.Endpoint.path("/chat/completions"),
    framing: framing_1.Framing.sse,
});
exports.routes = [exports.route];
var modelRef = client_1.Route.model(exports.route, {
    provider: exports.profile.provider,
    baseURL: exports.profile.baseURL,
});
var model = function (id, options) {
    if (options === void 0) { options = {}; }
    return modelRef(__assign(__assign({}, options), { id: id }));
};
exports.model = model;
exports.provider = provider_1.Provider.make({
    id: exports.id,
    model: exports.model,
});
