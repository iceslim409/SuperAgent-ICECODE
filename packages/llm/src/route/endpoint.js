"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Endpoint = exports.render = exports.path = void 0;
var ProviderShared = require("../protocols/shared");
/** Construct an `Endpoint` from a path string or path function. */
var path = function (value) { return ({ path: value }); };
exports.path = path;
var renderPart = function (part, input) {
    return typeof part === "function" ? part(input) : part;
};
var render = function (endpoint, input) {
    var url = new URL("".concat(ProviderShared.trimBaseUrl(input.request.model.baseURL)).concat(renderPart(endpoint.path, input)));
    var params = input.request.model.queryParams;
    if (params)
        for (var _i = 0, _a = Object.entries(params); _i < _a.length; _i++) {
            var _b = _a[_i], key = _b[0], value = _b[1];
            url.searchParams.set(key, value);
        }
    return url;
};
exports.render = render;
exports.Endpoint = require("./endpoint");
