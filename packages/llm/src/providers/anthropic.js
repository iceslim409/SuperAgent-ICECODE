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
exports.provider = exports.model = exports.routes = exports.id = void 0;
var provider_1 = require("../provider");
var schema_1 = require("../schema");
var AnthropicMessages = require("../protocols/anthropic-messages");
exports.id = schema_1.ProviderID.make("anthropic");
exports.routes = [AnthropicMessages.route];
var model = function (id, options) {
    if (options === void 0) { options = {}; }
    return AnthropicMessages.model(__assign(__assign({}, options), { id: id }));
};
exports.model = model;
exports.provider = provider_1.Provider.make({
    id: exports.id,
    model: exports.model,
});
