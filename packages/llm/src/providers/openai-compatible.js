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
exports.togetherai = exports.groq = exports.fireworks = exports.deepseek = exports.deepinfra = exports.cerebras = exports.baseten = exports.provider = exports.profileModel = exports.model = exports.routes = exports.id = void 0;
var provider_1 = require("../provider");
var schema_1 = require("../schema");
var OpenAICompatibleChat = require("../protocols/openai-compatible-chat");
var openai_compatible_profile_1 = require("./openai-compatible-profile");
exports.id = schema_1.ProviderID.make("openai-compatible");
exports.routes = [OpenAICompatibleChat.route];
var model = function (id, options) {
    return OpenAICompatibleChat.model(__assign(__assign({}, options), { id: id, provider: schema_1.ProviderID.make(options.provider) }));
};
exports.model = model;
var profileModel = function (profile, id, options) {
    var _a;
    if (options === void 0) { options = {}; }
    return OpenAICompatibleChat.model(__assign(__assign({}, options), { id: id, provider: profile.provider, baseURL: (_a = options.baseURL) !== null && _a !== void 0 ? _a : profile.baseURL }));
};
exports.profileModel = profileModel;
var define = function (profile) {
    return provider_1.Provider.make({
        id: schema_1.ProviderID.make(profile.provider),
        model: function (id, options) {
            if (options === void 0) { options = {}; }
            return (0, exports.profileModel)(profile, id, options);
        },
    });
};
exports.provider = provider_1.Provider.make({
    id: exports.id,
    model: function (id, options) { var _a; return (0, exports.model)(id, __assign(__assign({}, options), { provider: (_a = options.provider) !== null && _a !== void 0 ? _a : "openai-compatible" })); },
});
exports.baseten = define(openai_compatible_profile_1.profiles.baseten);
exports.cerebras = define(openai_compatible_profile_1.profiles.cerebras);
exports.deepinfra = define(openai_compatible_profile_1.profiles.deepinfra);
exports.deepseek = define(openai_compatible_profile_1.profiles.deepseek);
exports.fireworks = define(openai_compatible_profile_1.profiles.fireworks);
exports.groq = define(openai_compatible_profile_1.profiles.groq);
exports.togetherai = define(openai_compatible_profile_1.profiles.togetherai);
