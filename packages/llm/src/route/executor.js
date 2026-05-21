"use strict";
var __extends = (this && this.__extends) || (function () {
    var extendStatics = function (d, b) {
        extendStatics = Object.setPrototypeOf ||
            ({ __proto__: [] } instanceof Array && function (d, b) { d.__proto__ = b; }) ||
            function (d, b) { for (var p in b) if (Object.prototype.hasOwnProperty.call(b, p)) d[p] = b[p]; };
        return extendStatics(d, b);
    };
    return function (d, b) {
        if (typeof b !== "function" && b !== null)
            throw new TypeError("Class extends value " + String(b) + " is not a constructor or null");
        extendStatics(d, b);
        function __() { this.constructor = d; }
        d.prototype = b === null ? Object.create(b) : (__.prototype = b.prototype, new __());
    };
})();
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
var __spreadArray = (this && this.__spreadArray) || function (to, from, pack) {
    if (pack || arguments.length === 2) for (var i = 0, l = from.length, ar; i < l; i++) {
        if (ar || !(i in from)) {
            if (!ar) ar = Array.prototype.slice.call(from, 0, i);
            ar[i] = from[i];
        }
    }
    return to.concat(ar || Array.prototype.slice.call(from));
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
exports.RequestExecutor = exports.defaultLayer = exports.layer = exports.Service = void 0;
var effect_1 = require("effect");
var http_1 = require("effect/unstable/http");
var schema_1 = require("../schema");
var Service = /** @class */ (function (_super) {
    __extends(Service, _super);
    function Service() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    return Service;
}(effect_1.Context.Service()("@icecode/LLM/RequestExecutor")));
exports.Service = Service;
var BODY_LIMIT = 16384;
var MAX_RETRIES = 2;
var BASE_DELAY_MS = 500;
var MAX_DELAY_MS = 10000;
var REDACTED = "<redacted>";
// One source of truth for what counts as a sensitive name across headers,
// URL query keys, and field names embedded inside request/response bodies.
//
// `SENSITIVE_NAME` is used as both a substring matcher (for free-form header
// names like `Authorization` / `X-API-Key`) and as the body-field alternation
// list. `SHORT_QUERY_NAME` covers anchored short keys like `?key=…` / `?sig=…`
// that are too generic to redact substring-style without false positives.
var SENSITIVE_NAME_SOURCE = "authorization|api[-_]?key|access[-_]?token|refresh[-_]?token|id[-_]?token|token|secret|credential|signature|x-amz-signature";
var SENSITIVE_NAME = new RegExp(SENSITIVE_NAME_SOURCE, "i");
var SHORT_QUERY_NAME = /^(key|sig)$/i;
var SENSITIVE_BODY_FIELD = new RegExp("(?:".concat(SENSITIVE_NAME_SOURCE, "|key)"), "i");
var REDACT_JSON_FIELD = new RegExp("(\"(?:".concat(SENSITIVE_BODY_FIELD.source, ")\"\\s*:\\s*)\"[^\"]*\""), "gi");
var REDACT_QUERY_FIELD = new RegExp("((?:".concat(SENSITIVE_BODY_FIELD.source, ")=)[^&\\s\"]+"), "gi");
var isSensitiveHeaderName = function (name) { return SENSITIVE_NAME.test(name); };
var isSensitiveQueryName = function (name) { return isSensitiveHeaderName(name) || SHORT_QUERY_NAME.test(name); };
var redactHeaders = function (headers, redactedNames) {
    return Object.fromEntries(Object.entries(http_1.Headers.redact(headers, __spreadArray(__spreadArray([], redactedNames, true), [SENSITIVE_NAME], false))).map(function (_a) {
        var name = _a[0], value = _a[1];
        return [
            name,
            String(value),
        ];
    }));
};
var redactUrl = function (value) {
    if (!URL.canParse(value))
        return REDACTED;
    var url = new URL(value);
    url.searchParams.forEach(function (_, key) {
        if (isSensitiveQueryName(key))
            url.searchParams.set(key, REDACTED);
    });
    return url.toString();
};
var normalizedHeaders = function (headers) {
    return Object.fromEntries(Object.entries(headers).map(function (_a) {
        var key = _a[0], value = _a[1];
        return [key.toLowerCase(), value];
    }));
};
var requestId = function (headers) {
    var _a, _b, _c, _d, _e;
    return ((_e = (_d = (_c = (_b = (_a = headers["x-request-id"]) !== null && _a !== void 0 ? _a : headers["request-id"]) !== null && _b !== void 0 ? _b : headers["x-amzn-requestid"]) !== null && _c !== void 0 ? _c : headers["x-amz-request-id"]) !== null && _d !== void 0 ? _d : headers["x-goog-request-id"]) !== null && _e !== void 0 ? _e : headers["cf-ray"]);
};
var retryableStatus = function (status) { return status === 429 || status === 503 || status === 504 || status === 529; };
var retryAfterMs = function (headers) {
    var millis = Number(headers["retry-after-ms"]);
    if (Number.isFinite(millis))
        return Math.max(0, millis);
    var value = headers["retry-after"];
    if (!value)
        return undefined;
    var seconds = Number(value);
    if (Number.isFinite(seconds))
        return Math.max(0, seconds * 1000);
    var date = Date.parse(value);
    if (!Number.isNaN(date))
        return Math.max(0, date - Date.now());
    return undefined;
};
var addRateLimitValue = function (target, key, value) {
    if (key.length > 0)
        target[key] = value;
};
var rateLimitDetails = function (headers, retryAfter) {
    var limit = {};
    var remaining = {};
    var reset = {};
    Object.entries(headers).forEach(function (_a) {
        var _b, _c, _d;
        var name = _a[0], value = _a[1];
        var openaiLimit = (_b = /^x-ratelimit-limit-(.+)$/.exec(name)) === null || _b === void 0 ? void 0 : _b[1];
        if (openaiLimit)
            return addRateLimitValue(limit, openaiLimit, value);
        var openaiRemaining = (_c = /^x-ratelimit-remaining-(.+)$/.exec(name)) === null || _c === void 0 ? void 0 : _c[1];
        if (openaiRemaining)
            return addRateLimitValue(remaining, openaiRemaining, value);
        var openaiReset = (_d = /^x-ratelimit-reset-(.+)$/.exec(name)) === null || _d === void 0 ? void 0 : _d[1];
        if (openaiReset)
            return addRateLimitValue(reset, openaiReset, value);
        var anthropic = /^anthropic-ratelimit-(.+)-(limit|remaining|reset)$/.exec(name);
        if (!anthropic)
            return;
        if (anthropic[2] === "limit")
            return addRateLimitValue(limit, anthropic[1], value);
        if (anthropic[2] === "remaining")
            return addRateLimitValue(remaining, anthropic[1], value);
        return addRateLimitValue(reset, anthropic[1], value);
    });
    if (retryAfter === undefined &&
        Object.keys(limit).length === 0 &&
        Object.keys(remaining).length === 0 &&
        Object.keys(reset).length === 0)
        return undefined;
    return new schema_1.HttpRateLimitDetails({
        retryAfterMs: retryAfter,
        limit: Object.keys(limit).length === 0 ? undefined : limit,
        remaining: Object.keys(remaining).length === 0 ? undefined : remaining,
        reset: Object.keys(reset).length === 0 ? undefined : reset,
    });
};
var requestDetails = function (request, redactedNames) {
    return new schema_1.HttpRequestDetails({
        method: request.method,
        url: redactUrl(request.url),
        headers: redactHeaders(request.headers, redactedNames),
    });
};
var responseDetails = function (response, redactedNames) {
    return new schema_1.HttpResponseDetails({
        status: response.status,
        headers: redactHeaders(response.headers, redactedNames),
    });
};
var secretValues = function (request) {
    var values = new Set();
    var add = function (value) {
        if (value.length < 4)
            return;
        values.add(value);
        values.add(encodeURIComponent(value));
    };
    Object.entries(request.headers).forEach(function (_a) {
        var _b;
        var name = _a[0], value = _a[1];
        if (!isSensitiveHeaderName(name))
            return;
        add(value);
        var bearer = (_b = /^Bearer\s+(.+)$/i.exec(value)) === null || _b === void 0 ? void 0 : _b[1];
        if (bearer)
            add(bearer);
    });
    if (!URL.canParse(request.url))
        return values;
    new URL(request.url).searchParams.forEach(function (value, key) {
        if (isSensitiveQueryName(key))
            add(value);
    });
    return values;
};
// Two passes: structural (redact `"name": "value"` and `name=value` patterns
// for any field name that looks sensitive) plus literal (replace any actual
// secret values we sent in the request, in case the response echoes one back).
var redactBody = function (body, request) {
    return Array.from(secretValues(request)).reduce(function (text, secret) { return text.split(secret).join(REDACTED); }, body.replace(REDACT_JSON_FIELD, "$1\"".concat(REDACTED, "\"")).replace(REDACT_QUERY_FIELD, "$1".concat(REDACTED)));
};
var responseBody = function (body, request) {
    if (body === undefined)
        return {};
    var redacted = redactBody(body, request);
    if (redacted.length <= BODY_LIMIT)
        return { body: redacted };
    return { body: redacted.slice(0, BODY_LIMIT), bodyTruncated: true };
};
var providerMessage = function (status, body) {
    if (body.body && body.body.length <= 500)
        return "Provider request failed with HTTP ".concat(status, ": ").concat(body.body);
    return "Provider request failed with HTTP ".concat(status);
};
var responseHttp = function (input) {
    return new schema_1.HttpContext(__assign(__assign({ request: requestDetails(input.request, input.redactedNames), response: responseDetails(input.response, input.redactedNames) }, input.body), { requestId: input.requestId, rateLimit: input.rateLimit }));
};
var statusReason = function (input) {
    var _a;
    var body = (_a = input.http.body) !== null && _a !== void 0 ? _a : "";
    if (/content[-_\s]?policy|content_filter|safety/i.test(body)) {
        return new schema_1.ContentPolicyReason({ message: input.message, http: input.http });
    }
    if (input.status === 401) {
        return new schema_1.AuthenticationReason({ message: input.message, kind: "invalid", http: input.http });
    }
    if (input.status === 403) {
        return new schema_1.AuthenticationReason({ message: input.message, kind: "insufficient-permissions", http: input.http });
    }
    if (input.status === 429) {
        if (/insufficient[-_\s]?quota|quota[-_\s]?exceeded/i.test(body)) {
            return new schema_1.QuotaExceededReason({ message: input.message, http: input.http });
        }
        return new schema_1.RateLimitReason({
            message: input.message,
            retryAfterMs: input.retryAfterMs,
            rateLimit: input.rateLimit,
            http: input.http,
        });
    }
    if (input.status === 400 || input.status === 404 || input.status === 409 || input.status === 422) {
        return new schema_1.InvalidRequestReason({ message: input.message, http: input.http });
    }
    if (input.status >= 500 || retryableStatus(input.status)) {
        return new schema_1.ProviderInternalReason({
            message: input.message,
            status: input.status,
            retryAfterMs: input.retryAfterMs,
            http: input.http,
        });
    }
    return new schema_1.UnknownProviderReason({ message: input.message, status: input.status, http: input.http });
};
var statusError = function (request, redactedNames) {
    return function (response) {
        return effect_1.Effect.gen(function () {
            var body, headers, retryAfter, rateLimit, details;
            return __generator(this, function (_a) {
                switch (_a.label) {
                    case 0:
                        if (response.status < 400)
                            return [2 /*return*/, response];
                        return [5 /*yield**/, __values(response.text.pipe(effect_1.Effect.catch(function () { return effect_1.Effect.void; })))];
                    case 1:
                        body = _a.sent();
                        headers = normalizedHeaders(response.headers);
                        retryAfter = retryAfterMs(headers);
                        rateLimit = rateLimitDetails(headers, retryAfter);
                        details = responseBody(body, request);
                        return [5 /*yield**/, __values(new schema_1.LLMError({
                                module: "RequestExecutor",
                                method: "execute",
                                reason: statusReason({
                                    status: response.status,
                                    message: providerMessage(response.status, details),
                                    retryAfterMs: retryAfter,
                                    rateLimit: rateLimit,
                                    http: responseHttp({
                                        request: request,
                                        response: response,
                                        redactedNames: redactedNames,
                                        body: details,
                                        requestId: requestId(headers),
                                        rateLimit: rateLimit,
                                    }),
                                }),
                            }))];
                    case 2: return [2 /*return*/, _a.sent()];
                }
            });
        });
    };
};
var toHttpError = function (redactedNames) { return function (error) {
    var _a;
    var transportError = function (input) {
        return new schema_1.LLMError({
            module: "RequestExecutor",
            method: "execute",
            reason: new schema_1.TransportReason({
                message: input.message,
                kind: input.kind,
                url: input.request ? redactUrl(input.request.url) : undefined,
                http: input.request ? new schema_1.HttpContext({ request: requestDetails(input.request, redactedNames) }) : undefined,
            }),
        });
    };
    if (effect_1.Cause.isTimeoutError(error)) {
        return transportError({ message: error.message, kind: "Timeout" });
    }
    if (!http_1.HttpClientError.isHttpClientError(error)) {
        return transportError({ message: "HTTP transport failed" });
    }
    var request = "request" in error ? error.request : undefined;
    if (error.reason._tag === "TransportError") {
        return transportError({
            message: (_a = error.reason.description) !== null && _a !== void 0 ? _a : "HTTP transport failed",
            kind: error.reason._tag,
            request: request,
        });
    }
    return transportError({
        message: "HTTP transport failed: ".concat(error.reason._tag),
        kind: error.reason._tag,
        request: request,
    });
}; };
var retryDelay = function (error, attempt) {
    if (error.retryAfterMs !== undefined)
        return effect_1.Effect.succeed(Math.min(error.retryAfterMs, MAX_DELAY_MS));
    return effect_1.Random.nextBetween(Math.min(BASE_DELAY_MS * Math.pow(2, attempt) * 0.8, MAX_DELAY_MS), Math.min(BASE_DELAY_MS * Math.pow(2, attempt) * 1.2, MAX_DELAY_MS)).pipe(effect_1.Effect.map(function (delay) { return Math.round(delay); }));
};
var retryStatusFailures = function (effect, retries, attempt) {
    if (retries === void 0) { retries = MAX_RETRIES; }
    if (attempt === void 0) { attempt = 0; }
    return effect_1.Effect.catchTag(effect, "LLM.Error", function (error) {
        if (!error.retryable || retries <= 0)
            return effect_1.Effect.fail(error);
        return retryDelay(error, attempt).pipe(effect_1.Effect.flatMap(function (delay) { return effect_1.Effect.sleep(delay); }), effect_1.Effect.flatMap(function () { return retryStatusFailures(effect, retries - 1, attempt + 1); }));
    });
};
exports.layer = effect_1.Layer.effect(Service, effect_1.Effect.gen(function () {
    var http, executeOnce;
    return __generator(this, function (_a) {
        switch (_a.label) {
            case 0: return [5 /*yield**/, __values(http_1.HttpClient.HttpClient)];
            case 1:
                http = _a.sent();
                executeOnce = function (request) {
                    return effect_1.Effect.gen(function () {
                        var redactedNames;
                        return __generator(this, function (_a) {
                            switch (_a.label) {
                                case 0: return [5 /*yield**/, __values(http_1.Headers.CurrentRedactedNames)];
                                case 1:
                                    redactedNames = _a.sent();
                                    return [5 /*yield**/, __values(http
                                            .execute(request)
                                            .pipe(effect_1.Effect.mapError(toHttpError(redactedNames)), effect_1.Effect.flatMap(statusError(request, redactedNames))))];
                                case 2: return [2 /*return*/, _a.sent()];
                            }
                        });
                    });
                };
                return [2 /*return*/, Service.of({
                        execute: function (request) { return retryStatusFailures(executeOnce(request)); },
                    })];
        }
    });
}));
exports.defaultLayer = exports.layer.pipe(effect_1.Layer.provide(http_1.FetchHttpClient.layer));
exports.RequestExecutor = require("./executor");
