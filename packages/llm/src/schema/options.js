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
Object.defineProperty(exports, "__esModule", { value: true });
exports.CacheHint = exports.ModelRef = exports.ModelLimits = exports.mergeGenerationOptions = exports.GenerationOptions = exports.mergeHttpOptions = exports.HttpOptions = exports.mergeProviderOptions = exports.ProviderOptions = exports.mergeJsonRecords = void 0;
var effect_1 = require("effect");
var ids_1 = require("./ids");
var isRecord = function (value) {
    return typeof value === "object" && value !== null && !Array.isArray(value);
};
var mergeJsonRecords = function () {
    var items = [];
    for (var _i = 0; _i < arguments.length; _i++) {
        items[_i] = arguments[_i];
    }
    var defined = items.filter(function (item) { return item !== undefined; });
    if (defined.length === 0)
        return undefined;
    if (defined.length === 1 && Object.values(defined[0]).every(function (value) { return value !== undefined; }))
        return defined[0];
    var result = {};
    for (var _a = 0, defined_1 = defined; _a < defined_1.length; _a++) {
        var item = defined_1[_a];
        for (var _b = 0, _c = Object.entries(item); _b < _c.length; _b++) {
            var _d = _c[_b], key = _d[0], value = _d[1];
            if (value === undefined)
                continue;
            result[key] = isRecord(result[key]) && isRecord(value) ? (0, exports.mergeJsonRecords)(result[key], value) : value;
        }
    }
    return Object.keys(result).length === 0 ? undefined : result;
};
exports.mergeJsonRecords = mergeJsonRecords;
var mergeStringRecords = function () {
    var items = [];
    for (var _i = 0; _i < arguments.length; _i++) {
        items[_i] = arguments[_i];
    }
    var defined = items.filter(function (item) { return item !== undefined; });
    if (defined.length === 0)
        return undefined;
    if (defined.length === 1)
        return defined[0];
    var result = Object.fromEntries(defined.flatMap(function (item) {
        return Object.entries(item).filter(function (entry) { return entry[1] !== undefined; });
    }));
    return Object.keys(result).length === 0 ? undefined : result;
};
exports.ProviderOptions = effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.Unknown));
var mergeProviderOptions = function () {
    var items = [];
    for (var _i = 0; _i < arguments.length; _i++) {
        items[_i] = arguments[_i];
    }
    var result = {};
    for (var _a = 0, items_1 = items; _a < items_1.length; _a++) {
        var item = items_1[_a];
        if (!item)
            continue;
        for (var _b = 0, _c = Object.entries(item); _b < _c.length; _b++) {
            var _d = _c[_b], provider = _d[0], options = _d[1];
            var merged = (0, exports.mergeJsonRecords)(result[provider], options);
            if (merged)
                result[provider] = merged;
        }
    }
    return Object.keys(result).length === 0 ? undefined : result;
};
exports.mergeProviderOptions = mergeProviderOptions;
var HttpOptions = /** @class */ (function (_super) {
    __extends(HttpOptions, _super);
    function HttpOptions() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    return HttpOptions;
}(effect_1.Schema.Class("LLM.HttpOptions")({
    body: effect_1.Schema.optional(ids_1.JsonSchema),
    headers: effect_1.Schema.optional(effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.String)),
    query: effect_1.Schema.optional(effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.String)),
})));
exports.HttpOptions = HttpOptions;
(function (HttpOptions) {
    /** Normalize HTTP option input into the canonical `HttpOptions` class. */
    HttpOptions.make = function (input) { return (input instanceof HttpOptions ? input : new HttpOptions(input)); };
})(HttpOptions || (exports.HttpOptions = HttpOptions = {}));
var mergeHttpOptions = function () {
    var items = [];
    for (var _i = 0; _i < arguments.length; _i++) {
        items[_i] = arguments[_i];
    }
    var body = exports.mergeJsonRecords.apply(void 0, items.map(function (item) { return item === null || item === void 0 ? void 0 : item.body; }));
    var headers = mergeStringRecords.apply(void 0, items.map(function (item) { return item === null || item === void 0 ? void 0 : item.headers; }));
    var query = mergeStringRecords.apply(void 0, items.map(function (item) { return item === null || item === void 0 ? void 0 : item.query; }));
    if (!body && !headers && !query)
        return undefined;
    return new HttpOptions({ body: body, headers: headers, query: query });
};
exports.mergeHttpOptions = mergeHttpOptions;
var GenerationOptions = /** @class */ (function (_super) {
    __extends(GenerationOptions, _super);
    function GenerationOptions() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    return GenerationOptions;
}(effect_1.Schema.Class("LLM.GenerationOptions")({
    maxTokens: effect_1.Schema.optional(effect_1.Schema.Number),
    temperature: effect_1.Schema.optional(effect_1.Schema.Number),
    topP: effect_1.Schema.optional(effect_1.Schema.Number),
    topK: effect_1.Schema.optional(effect_1.Schema.Number),
    frequencyPenalty: effect_1.Schema.optional(effect_1.Schema.Number),
    presencePenalty: effect_1.Schema.optional(effect_1.Schema.Number),
    seed: effect_1.Schema.optional(effect_1.Schema.Number),
    stop: effect_1.Schema.optional(effect_1.Schema.Array(effect_1.Schema.String)),
})));
exports.GenerationOptions = GenerationOptions;
(function (GenerationOptions) {
    /** Normalize generation option input into the canonical `GenerationOptions` class. */
    GenerationOptions.make = function (input) {
        if (input === void 0) { input = {}; }
        return (input instanceof GenerationOptions ? input : new GenerationOptions(input));
    };
})(GenerationOptions || (exports.GenerationOptions = GenerationOptions = {}));
var latestGeneration = function (items, key) { var _a; return (_a = items.findLast(function (item) { return (item === null || item === void 0 ? void 0 : item[key]) !== undefined; })) === null || _a === void 0 ? void 0 : _a[key]; };
var mergeGenerationOptions = function () {
    var items = [];
    for (var _i = 0; _i < arguments.length; _i++) {
        items[_i] = arguments[_i];
    }
    var result = new GenerationOptions({
        maxTokens: latestGeneration(items, "maxTokens"),
        temperature: latestGeneration(items, "temperature"),
        topP: latestGeneration(items, "topP"),
        topK: latestGeneration(items, "topK"),
        frequencyPenalty: latestGeneration(items, "frequencyPenalty"),
        presencePenalty: latestGeneration(items, "presencePenalty"),
        seed: latestGeneration(items, "seed"),
        stop: latestGeneration(items, "stop"),
    });
    return Object.values(result).some(function (value) { return value !== undefined; }) ? result : undefined;
};
exports.mergeGenerationOptions = mergeGenerationOptions;
var ModelLimits = /** @class */ (function (_super) {
    __extends(ModelLimits, _super);
    function ModelLimits() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    return ModelLimits;
}(effect_1.Schema.Class("LLM.ModelLimits")({
    context: effect_1.Schema.optional(effect_1.Schema.Number),
    output: effect_1.Schema.optional(effect_1.Schema.Number),
})));
exports.ModelLimits = ModelLimits;
(function (ModelLimits) {
    /** Normalize model limit input into the canonical `ModelLimits` class. */
    ModelLimits.make = function (input) {
        return input instanceof ModelLimits ? input : new ModelLimits(input !== null && input !== void 0 ? input : {});
    };
})(ModelLimits || (exports.ModelLimits = ModelLimits = {}));
var ModelRef = /** @class */ (function (_super) {
    __extends(ModelRef, _super);
    function ModelRef() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    return ModelRef;
}(effect_1.Schema.Class("LLM.ModelRef")({
    id: ids_1.ModelID,
    provider: ids_1.ProviderID,
    route: ids_1.RouteID,
    baseURL: effect_1.Schema.String,
    /** Provider-specific API key convenience. Provider helpers normalize this into `auth`. */
    apiKey: effect_1.Schema.optional(effect_1.Schema.String),
    /** Optional transport auth policy. Opaque because it may contain functions. */
    auth: effect_1.Schema.optional(effect_1.Schema.Any),
    headers: effect_1.Schema.optional(effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.String)),
    /**
     * Query params appended to the request URL by `Endpoint.baseURL`. Used for
     * deployment-level URL-scoped settings such as Azure's `api-version` or any
     * provider that requires a per-request key in the URL. Generic concern, so
     * lives as a typed first-class field instead of `native`.
     */
    queryParams: effect_1.Schema.optional(effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.String)),
    limits: ModelLimits,
    /** Provider-neutral generation defaults. Request-level values override them. */
    generation: effect_1.Schema.optional(GenerationOptions),
    /** Provider-owned typed-at-the-facade options for non-portable knobs. */
    providerOptions: effect_1.Schema.optional(exports.ProviderOptions),
    /** Serializable raw HTTP overlays applied to the final outgoing request. */
    http: effect_1.Schema.optional(HttpOptions),
    /**
     * Provider-specific opaque options. Reach for this only when the value is
     * genuinely provider-private and does not fit a typed axis (e.g. Bedrock's
     * `aws_credentials` / `aws_region` for SigV4). Anything used by more than
     * one route should grow into a typed field instead.
     */
    native: effect_1.Schema.optional(effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.Unknown)),
})));
exports.ModelRef = ModelRef;
(function (ModelRef) {
    ModelRef.input = function (model) { return ({
        id: model.id,
        provider: model.provider,
        route: model.route,
        baseURL: model.baseURL,
        apiKey: model.apiKey,
        auth: model.auth,
        headers: model.headers,
        queryParams: model.queryParams,
        limits: model.limits,
        generation: model.generation,
        providerOptions: model.providerOptions,
        http: model.http,
        native: model.native,
    }); };
    ModelRef.update = function (model, patch) {
        if (Object.keys(patch).length === 0)
            return model;
        return new ModelRef(__assign(__assign({}, ModelRef.input(model)), patch));
    };
})(ModelRef || (exports.ModelRef = ModelRef = {}));
var CacheHint = /** @class */ (function (_super) {
    __extends(CacheHint, _super);
    function CacheHint() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    return CacheHint;
}(effect_1.Schema.Class("LLM.CacheHint")({
    type: effect_1.Schema.Literals(["ephemeral", "persistent"]),
    ttlSeconds: effect_1.Schema.optional(effect_1.Schema.Number),
})));
exports.CacheHint = CacheHint;
