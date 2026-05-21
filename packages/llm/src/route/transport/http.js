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
var __generator = (this && this.__generator) || function (thisArg, body) {
    var _ = { label: 0, sent: function() { if (t[0] & 1) throw t[1]; return t[1]; }, trys: [], ops: [] }, f, y, t, g = Object.create((typeof Iterator === "function" ? Iterator : Object).prototype);
    return g.next = verb(0), g["throw"] = verb(1), g["return"] = verb(2), typeof Symbol === "function" && (g[Symbol.iterator] = function() { return this; }), g;
    function verb(n) { return function (v) { return step([n, v]); }; }
    function step(op) {
        if (f) throw new TypeError("Generator is already executing.");
        while (g && (g = 0, op[0] && (_ = 0)), _) try {
            if (f = 1, y && (t = op[0] & 2 ? y["return"] : op[0] ? y["throw"] || ((t = y["return"]) && t.call(y), 0) : y.next) && !(t = t.call(y, op[1])).done) return t;
            if (y = 0, t) op = [op[0] & 2, t.value];
            switch (op[0]) {
                case 0: case 1: t = op; break;
                case 4: _.label++; return { value: op[1], done: false };
                case 5: _.label++; y = op[1]; op = [0]; continue;
                case 7: op = _.ops.pop(); _.trys.pop(); continue;
                default:
                    if (!(t = _.trys, t = t.length > 0 && t[t.length - 1]) && (op[0] === 6 || op[0] === 2)) { _ = 0; continue; }
                    if (op[0] === 3 && (!t || (op[1] > t[0] && op[1] < t[3]))) { _.label = op[1]; break; }
                    if (op[0] === 6 && _.label < t[1]) { _.label = t[1]; t = op; break; }
                    if (t && _.label < t[2]) { _.label = t[2]; _.ops.push(op); break; }
                    if (t[2]) _.ops.pop();
                    _.trys.pop(); continue;
            }
            op = body.call(thisArg, _);
        } catch (e) { op = [6, e]; y = 0; } finally { f = t = 0; }
        if (op[0] & 5) throw op[1]; return { value: op[0] ? op[1] : void 0, done: true };
    }
};
var __values = (this && this.__values) || function(o) {
    var s = typeof Symbol === "function" && Symbol.iterator, m = s && o[s], i = 0;
    if (m) return m.call(o);
    if (o && typeof o.length === "number") return {
        next: function () {
            if (o && i >= o.length) o = void 0;
            return { value: o && o[i++], done: !o };
        }
    };
    throw new TypeError(s ? "Object is not iterable." : "Symbol.iterator is not defined.");
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.httpJson = exports.jsonRequestParts = void 0;
var effect_1 = require("effect");
var http_1 = require("effect/unstable/http");
var auth_1 = require("../auth");
var endpoint_1 = require("../endpoint");
var ProviderShared = require("../../protocols/shared");
var schema_1 = require("../../schema");
var applyQuery = function (url, query) {
    if (!query)
        return url;
    var next = new URL(url);
    Object.entries(query).forEach(function (_a) {
        var key = _a[0], value = _a[1];
        return next.searchParams.set(key, value);
    });
    return next.toString();
};
var bodyWithOverlay = function (body, request, encodeBody) {
    return effect_1.Effect.gen(function () {
        var overlaid;
        var _a, _b;
        return __generator(this, function (_c) {
            switch (_c.label) {
                case 0:
                    if (((_a = request.http) === null || _a === void 0 ? void 0 : _a.body) === undefined)
                        return [2 /*return*/, { jsonBody: body, bodyText: encodeBody(body) }];
                    if (ProviderShared.isRecord(body)) {
                        overlaid = (_b = (0, schema_1.mergeJsonRecords)(body, request.http.body)) !== null && _b !== void 0 ? _b : {};
                        return [2 /*return*/, { jsonBody: overlaid, bodyText: ProviderShared.encodeJson(overlaid) }];
                    }
                    return [5 /*yield**/, __values(ProviderShared.invalidRequest("http.body can only overlay JSON object request bodies"))];
                case 1: return [2 /*return*/, _c.sent()];
            }
        });
    });
};
var jsonRequestParts = function (input) {
    return effect_1.Effect.gen(function () {
        var url, body, headers;
        var _a, _b, _c, _d;
        return __generator(this, function (_e) {
            switch (_e.label) {
                case 0:
                    url = applyQuery((0, endpoint_1.render)(input.endpoint, { request: input.request, body: input.body }).toString(), (_a = input.request.http) === null || _a === void 0 ? void 0 : _a.query);
                    return [5 /*yield**/, __values(bodyWithOverlay(input.body, input.request, input.encodeBody))];
                case 1:
                    body = _e.sent();
                    return [5 /*yield**/, __values(auth_1.Auth.toEffect(auth_1.Auth.isAuth(input.request.model.auth) ? input.request.model.auth : input.auth)({
                            request: input.request,
                            method: "POST",
                            url: url,
                            body: body.bodyText,
                            headers: http_1.Headers.fromInput(__assign(__assign(__assign({}, ((_c = (_b = input.headers) === null || _b === void 0 ? void 0 : _b.call(input, { request: input.request })) !== null && _c !== void 0 ? _c : {})), input.request.model.headers), (_d = input.request.http) === null || _d === void 0 ? void 0 : _d.headers)),
                        }))];
                case 2:
                    headers = _e.sent();
                    return [2 /*return*/, { url: url, jsonBody: body.jsonBody, bodyText: body.bodyText, headers: headers }];
            }
        });
    });
};
exports.jsonRequestParts = jsonRequestParts;
var httpJson = function (input) { return ({
    id: "http-json",
    with: function (patch) { return (0, exports.httpJson)(__assign(__assign({}, input), patch)); },
    prepare: function (body, request) {
        var _a;
        return (0, exports.jsonRequestParts)({
            body: body,
            request: request,
            endpoint: input.endpoint,
            auth: (_a = input.auth) !== null && _a !== void 0 ? _a : auth_1.Auth.bearer(),
            encodeBody: input.encodeBody,
            headers: input.headers,
        }).pipe(effect_1.Effect.map(function (parts) { return ({
            request: ProviderShared.jsonPost({ url: parts.url, body: parts.bodyText, headers: parts.headers }),
            framing: input.framing,
        }); }));
    },
    frames: function (prepared, request, runtime) {
        return effect_1.Stream.unwrap(runtime.http
            .execute(prepared.request)
            .pipe(effect_1.Effect.map(function (response) {
            return prepared.framing.frame(response.stream.pipe(effect_1.Stream.mapError(function (error) {
                return ProviderShared.eventError("".concat(request.model.provider, "/").concat(request.model.route), "Failed to read ".concat(request.model.provider, "/").concat(request.model.route, " stream"), ProviderShared.errorText(error));
            })));
        })));
    },
}); };
exports.httpJson = httpJson;
