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
Object.defineProperty(exports, "__esModule", { value: true });
exports.ToolFailure = exports.LLMError = exports.LLMErrorReason = exports.UnknownProviderReason = exports.InvalidProviderOutputReason = exports.TransportReason = exports.ProviderInternalReason = exports.ContentPolicyReason = exports.QuotaExceededReason = exports.RateLimitReason = exports.AuthenticationReason = exports.NoRouteReason = exports.InvalidRequestReason = exports.HttpContext = exports.HttpRateLimitDetails = exports.HttpResponseDetails = exports.HttpRequestDetails = void 0;
var effect_1 = require("effect");
var ids_1 = require("./ids");
var HttpRequestDetails = /** @class */ (function (_super) {
    __extends(HttpRequestDetails, _super);
    function HttpRequestDetails() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    return HttpRequestDetails;
}(effect_1.Schema.Class("LLM.HttpRequestDetails")({
    method: effect_1.Schema.String,
    url: effect_1.Schema.String,
    headers: effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.String),
})));
exports.HttpRequestDetails = HttpRequestDetails;
var HttpResponseDetails = /** @class */ (function (_super) {
    __extends(HttpResponseDetails, _super);
    function HttpResponseDetails() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    return HttpResponseDetails;
}(effect_1.Schema.Class("LLM.HttpResponseDetails")({
    status: effect_1.Schema.Number,
    headers: effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.String),
})));
exports.HttpResponseDetails = HttpResponseDetails;
var HttpRateLimitDetails = /** @class */ (function (_super) {
    __extends(HttpRateLimitDetails, _super);
    function HttpRateLimitDetails() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    return HttpRateLimitDetails;
}(effect_1.Schema.Class("LLM.HttpRateLimitDetails")({
    retryAfterMs: effect_1.Schema.optional(effect_1.Schema.Number),
    limit: effect_1.Schema.optional(effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.String)),
    remaining: effect_1.Schema.optional(effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.String)),
    reset: effect_1.Schema.optional(effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.String)),
})));
exports.HttpRateLimitDetails = HttpRateLimitDetails;
var HttpContext = /** @class */ (function (_super) {
    __extends(HttpContext, _super);
    function HttpContext() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    return HttpContext;
}(effect_1.Schema.Class("LLM.HttpContext")({
    request: HttpRequestDetails,
    response: effect_1.Schema.optional(HttpResponseDetails),
    body: effect_1.Schema.optional(effect_1.Schema.String),
    bodyTruncated: effect_1.Schema.optional(effect_1.Schema.Boolean),
    requestId: effect_1.Schema.optional(effect_1.Schema.String),
    rateLimit: effect_1.Schema.optional(HttpRateLimitDetails),
})));
exports.HttpContext = HttpContext;
var InvalidRequestReason = /** @class */ (function (_super) {
    __extends(InvalidRequestReason, _super);
    function InvalidRequestReason() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    Object.defineProperty(InvalidRequestReason.prototype, "retryable", {
        get: function () {
            return false;
        },
        enumerable: false,
        configurable: true
    });
    return InvalidRequestReason;
}(effect_1.Schema.Class("LLM.Error.InvalidRequest")({
    _tag: effect_1.Schema.tag("InvalidRequest"),
    message: effect_1.Schema.String,
    parameter: effect_1.Schema.optional(effect_1.Schema.String),
    providerMetadata: effect_1.Schema.optional(ids_1.ProviderMetadata),
    http: effect_1.Schema.optional(HttpContext),
})));
exports.InvalidRequestReason = InvalidRequestReason;
var NoRouteReason = /** @class */ (function (_super) {
    __extends(NoRouteReason, _super);
    function NoRouteReason() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    Object.defineProperty(NoRouteReason.prototype, "retryable", {
        get: function () {
            return false;
        },
        enumerable: false,
        configurable: true
    });
    Object.defineProperty(NoRouteReason.prototype, "message", {
        get: function () {
            return "No LLM route for ".concat(this.provider, "/").concat(this.model, " using ").concat(this.route);
        },
        enumerable: false,
        configurable: true
    });
    return NoRouteReason;
}(effect_1.Schema.Class("LLM.Error.NoRoute")({
    _tag: effect_1.Schema.tag("NoRoute"),
    route: ids_1.RouteID,
    provider: ids_1.ProviderID,
    model: ids_1.ModelID,
})));
exports.NoRouteReason = NoRouteReason;
var AuthenticationReason = /** @class */ (function (_super) {
    __extends(AuthenticationReason, _super);
    function AuthenticationReason() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    Object.defineProperty(AuthenticationReason.prototype, "retryable", {
        get: function () {
            return false;
        },
        enumerable: false,
        configurable: true
    });
    return AuthenticationReason;
}(effect_1.Schema.Class("LLM.Error.Authentication")({
    _tag: effect_1.Schema.tag("Authentication"),
    message: effect_1.Schema.String,
    kind: effect_1.Schema.Literals(["missing", "invalid", "expired", "insufficient-permissions", "unknown"]),
    providerMetadata: effect_1.Schema.optional(ids_1.ProviderMetadata),
    http: effect_1.Schema.optional(HttpContext),
})));
exports.AuthenticationReason = AuthenticationReason;
var RateLimitReason = /** @class */ (function (_super) {
    __extends(RateLimitReason, _super);
    function RateLimitReason() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    Object.defineProperty(RateLimitReason.prototype, "retryable", {
        get: function () {
            return true;
        },
        enumerable: false,
        configurable: true
    });
    return RateLimitReason;
}(effect_1.Schema.Class("LLM.Error.RateLimit")({
    _tag: effect_1.Schema.tag("RateLimit"),
    message: effect_1.Schema.String,
    retryAfterMs: effect_1.Schema.optional(effect_1.Schema.Number),
    rateLimit: effect_1.Schema.optional(HttpRateLimitDetails),
    providerMetadata: effect_1.Schema.optional(ids_1.ProviderMetadata),
    http: effect_1.Schema.optional(HttpContext),
})));
exports.RateLimitReason = RateLimitReason;
var QuotaExceededReason = /** @class */ (function (_super) {
    __extends(QuotaExceededReason, _super);
    function QuotaExceededReason() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    Object.defineProperty(QuotaExceededReason.prototype, "retryable", {
        get: function () {
            return false;
        },
        enumerable: false,
        configurable: true
    });
    return QuotaExceededReason;
}(effect_1.Schema.Class("LLM.Error.QuotaExceeded")({
    _tag: effect_1.Schema.tag("QuotaExceeded"),
    message: effect_1.Schema.String,
    providerMetadata: effect_1.Schema.optional(ids_1.ProviderMetadata),
    http: effect_1.Schema.optional(HttpContext),
})));
exports.QuotaExceededReason = QuotaExceededReason;
var ContentPolicyReason = /** @class */ (function (_super) {
    __extends(ContentPolicyReason, _super);
    function ContentPolicyReason() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    Object.defineProperty(ContentPolicyReason.prototype, "retryable", {
        get: function () {
            return false;
        },
        enumerable: false,
        configurable: true
    });
    return ContentPolicyReason;
}(effect_1.Schema.Class("LLM.Error.ContentPolicy")({
    _tag: effect_1.Schema.tag("ContentPolicy"),
    message: effect_1.Schema.String,
    providerMetadata: effect_1.Schema.optional(ids_1.ProviderMetadata),
    http: effect_1.Schema.optional(HttpContext),
})));
exports.ContentPolicyReason = ContentPolicyReason;
var ProviderInternalReason = /** @class */ (function (_super) {
    __extends(ProviderInternalReason, _super);
    function ProviderInternalReason() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    Object.defineProperty(ProviderInternalReason.prototype, "retryable", {
        get: function () {
            return true;
        },
        enumerable: false,
        configurable: true
    });
    return ProviderInternalReason;
}(effect_1.Schema.Class("LLM.Error.ProviderInternal")({
    _tag: effect_1.Schema.tag("ProviderInternal"),
    message: effect_1.Schema.String,
    status: effect_1.Schema.Number,
    retryAfterMs: effect_1.Schema.optional(effect_1.Schema.Number),
    providerMetadata: effect_1.Schema.optional(ids_1.ProviderMetadata),
    http: effect_1.Schema.optional(HttpContext),
})));
exports.ProviderInternalReason = ProviderInternalReason;
var TransportReason = /** @class */ (function (_super) {
    __extends(TransportReason, _super);
    function TransportReason() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    Object.defineProperty(TransportReason.prototype, "retryable", {
        get: function () {
            return false;
        },
        enumerable: false,
        configurable: true
    });
    return TransportReason;
}(effect_1.Schema.Class("LLM.Error.Transport")({
    _tag: effect_1.Schema.tag("Transport"),
    message: effect_1.Schema.String,
    kind: effect_1.Schema.optional(effect_1.Schema.String),
    url: effect_1.Schema.optional(effect_1.Schema.String),
    http: effect_1.Schema.optional(HttpContext),
})));
exports.TransportReason = TransportReason;
var InvalidProviderOutputReason = /** @class */ (function (_super) {
    __extends(InvalidProviderOutputReason, _super);
    function InvalidProviderOutputReason() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    Object.defineProperty(InvalidProviderOutputReason.prototype, "retryable", {
        get: function () {
            return false;
        },
        enumerable: false,
        configurable: true
    });
    return InvalidProviderOutputReason;
}(effect_1.Schema.Class("LLM.Error.InvalidProviderOutput")({
    _tag: effect_1.Schema.tag("InvalidProviderOutput"),
    message: effect_1.Schema.String,
    route: effect_1.Schema.optional(effect_1.Schema.String),
    raw: effect_1.Schema.optional(effect_1.Schema.String),
    providerMetadata: effect_1.Schema.optional(ids_1.ProviderMetadata),
})));
exports.InvalidProviderOutputReason = InvalidProviderOutputReason;
var UnknownProviderReason = /** @class */ (function (_super) {
    __extends(UnknownProviderReason, _super);
    function UnknownProviderReason() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    Object.defineProperty(UnknownProviderReason.prototype, "retryable", {
        get: function () {
            return false;
        },
        enumerable: false,
        configurable: true
    });
    return UnknownProviderReason;
}(effect_1.Schema.Class("LLM.Error.UnknownProvider")({
    _tag: effect_1.Schema.tag("UnknownProvider"),
    message: effect_1.Schema.String,
    status: effect_1.Schema.optional(effect_1.Schema.Number),
    providerMetadata: effect_1.Schema.optional(ids_1.ProviderMetadata),
    http: effect_1.Schema.optional(HttpContext),
})));
exports.UnknownProviderReason = UnknownProviderReason;
exports.LLMErrorReason = effect_1.Schema.Union([
    InvalidRequestReason,
    NoRouteReason,
    AuthenticationReason,
    RateLimitReason,
    QuotaExceededReason,
    ContentPolicyReason,
    ProviderInternalReason,
    TransportReason,
    InvalidProviderOutputReason,
    UnknownProviderReason,
]).pipe(effect_1.Schema.toTaggedUnion("_tag"));
var LLMError = /** @class */ (function (_super) {
    __extends(LLMError, _super);
    function LLMError() {
        var _this = _super !== null && _super.apply(this, arguments) || this;
        _this.cause = _this.reason;
        return _this;
    }
    Object.defineProperty(LLMError.prototype, "retryable", {
        get: function () {
            return this.reason.retryable;
        },
        enumerable: false,
        configurable: true
    });
    Object.defineProperty(LLMError.prototype, "retryAfterMs", {
        get: function () {
            return "retryAfterMs" in this.reason ? this.reason.retryAfterMs : undefined;
        },
        enumerable: false,
        configurable: true
    });
    Object.defineProperty(LLMError.prototype, "message", {
        get: function () {
            return "".concat(this.module, ".").concat(this.method, ": ").concat(this.reason.message);
        },
        enumerable: false,
        configurable: true
    });
    return LLMError;
}(effect_1.Schema.TaggedErrorClass()("LLM.Error", {
    module: effect_1.Schema.String,
    method: effect_1.Schema.String,
    reason: exports.LLMErrorReason,
})));
exports.LLMError = LLMError;
/**
 * Failure type for tool execute handlers. Handlers must map their internal
 * errors to this shape; the runtime catches `ToolFailure`s and surfaces them
 * as `tool-error` events plus a `tool-result` of `type: "error"` so the model
 * can self-correct.
 *
 * Anything thrown or yielded by a handler that is not a `ToolFailure` is
 * treated as a defect and fails the stream.
 */
var ToolFailure = /** @class */ (function (_super) {
    __extends(ToolFailure, _super);
    function ToolFailure() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    return ToolFailure;
}(effect_1.Schema.TaggedErrorClass()("LLM.ToolFailure", {
    message: effect_1.Schema.String,
    metadata: effect_1.Schema.optional(effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.Unknown)),
})));
exports.ToolFailure = ToolFailure;
