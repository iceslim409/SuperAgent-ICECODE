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
exports.provider = exports.model = exports.routes = exports.id = void 0;
var client_1 = require("../route/client");
var provider_1 = require("../provider");
var schema_1 = require("../schema");
var BedrockConverse = require("../protocols/bedrock-converse");
exports.id = schema_1.ProviderID.make("amazon-bedrock");
exports.routes = [BedrockConverse.route];
var bedrockBaseURL = function (region) { return "https://bedrock-runtime.".concat(region, ".amazonaws.com"); };
var converseModel = client_1.Route.model(BedrockConverse.route, {
    provider: "amazon-bedrock",
}, {
    mapInput: function (input) {
        var _a;
        var credentials = input.credentials, region = input.region, baseURL = input.baseURL, rest = __rest(input, ["credentials", "region", "baseURL"]);
        var resolvedRegion = (_a = region !== null && region !== void 0 ? region : credentials === null || credentials === void 0 ? void 0 : credentials.region) !== null && _a !== void 0 ? _a : "us-east-1";
        return __assign(__assign({}, rest), { baseURL: baseURL !== null && baseURL !== void 0 ? baseURL : bedrockBaseURL(resolvedRegion), native: BedrockConverse.nativeCredentials(input.native, credentials) });
    },
});
var model = function (modelID, options) {
    if (options === void 0) { options = {}; }
    return converseModel(__assign(__assign({}, options), { id: modelID }));
};
exports.model = model;
exports.provider = provider_1.Provider.make({
    id: exports.id,
    model: exports.model,
});
