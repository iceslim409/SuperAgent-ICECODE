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
exports.LLMClient = exports.Route = exports.layerWithWebSocket = exports.layer = exports.streamRequest = exports.prepare = exports.Service = exports.modelRef = exports.httpOptions = exports.generationOptions = exports.modelLimits = void 0;
exports.make = make;
exports.stream = stream;
exports.generate = generate;
var effect_1 = require("effect");
var executor_1 = require("./executor");
var transport_1 = require("./transport");
var transport_2 = require("./transport");
var ProviderShared = require("../protocols/shared");
var ToolRuntime = require("../tool-runtime");
var schema_1 = require("../schema");
var routeRegistry = new Map();
// Route lookup is intentionally global: model refs name a route id, and
// importing the provider/protocol/custom-route module registers the runnable
// implementation. Duplicate ids are bugs because model refs cannot disambiguate
// them.
var register = function (route) {
    var existing = routeRegistry.get(route.id);
    if (existing && existing !== route)
        throw new Error("Duplicate LLM route id \"".concat(route.id, "\""));
    routeRegistry.set(route.id, route);
    return route;
};
var registeredRoute = function (id) { return routeRegistry.get(id); };
var modelWithDefaults = function (route, defaults, options) {
    return function (input) {
        var _a, _b, _c, _d, _e, _f;
        var mapped = options.mapInput === undefined ? input : options.mapInput(input);
        var provider = (_b = (_a = defaults.provider) !== null && _a !== void 0 ? _a : route.provider) !== null && _b !== void 0 ? _b : ("provider" in mapped ? mapped.provider : undefined);
        if (!provider)
            throw new Error("Route.model(".concat(route.id, ") requires a provider"));
        var baseURL = (_d = (_c = mapped.baseURL) !== null && _c !== void 0 ? _c : defaults.baseURL) !== null && _d !== void 0 ? _d : route.defaults.baseURL;
        if (!baseURL)
            throw new Error("Route.model(".concat(route.id, ") requires a baseURL \u2014 supply it via input, defaults, or route defaults"));
        var generation = (0, schema_1.mergeGenerationOptions)(route.defaults.generation, defaults.generation);
        var providerOptions = (0, schema_1.mergeProviderOptions)(route.defaults.providerOptions, defaults.providerOptions);
        var http = (0, schema_1.mergeHttpOptions)((0, exports.httpOptions)(route.defaults.http), (0, exports.httpOptions)(defaults.http));
        return (0, exports.modelRef)(__assign(__assign(__assign(__assign({}, route.defaults), defaults), mapped), { baseURL: baseURL, provider: provider, route: route.id, limits: (_f = (_e = mapped.limits) !== null && _e !== void 0 ? _e : defaults.limits) !== null && _f !== void 0 ? _f : route.defaults.limits, generation: (0, schema_1.mergeGenerationOptions)(generation, mapped.generation), providerOptions: (0, schema_1.mergeProviderOptions)(providerOptions, mapped.providerOptions), http: (0, schema_1.mergeHttpOptions)(http, (0, exports.httpOptions)(mapped.http)) }));
    };
};
var mergeRouteDefaults = function (base, patch) {
    var _a;
    return (__assign(__assign(__assign({}, base), patch), { limits: (_a = patch.limits) !== null && _a !== void 0 ? _a : base === null || base === void 0 ? void 0 : base.limits, generation: (0, schema_1.mergeGenerationOptions)((0, exports.generationOptions)(base === null || base === void 0 ? void 0 : base.generation), (0, exports.generationOptions)(patch.generation)), providerOptions: (0, schema_1.mergeProviderOptions)(base === null || base === void 0 ? void 0 : base.providerOptions, patch.providerOptions), http: (0, schema_1.mergeHttpOptions)((0, exports.httpOptions)(base === null || base === void 0 ? void 0 : base.http), (0, exports.httpOptions)(patch.http)) }));
};
exports.modelLimits = schema_1.ModelLimits.make;
var generationOptions = function (input) {
    return input === undefined ? undefined : schema_1.GenerationOptions.make(input);
};
exports.generationOptions = generationOptions;
var httpOptions = function (input) {
    if (input === undefined)
        return input;
    return schema_1.HttpOptions.make(input);
};
exports.httpOptions = httpOptions;
var modelRef = function (input) {
    return new schema_1.ModelRef(__assign(__assign({}, input), { id: schema_1.ModelID.make(input.id), provider: schema_1.ProviderID.make(input.provider), route: schema_1.RouteID.make(input.route), limits: (0, exports.modelLimits)(input.limits), generation: (0, exports.generationOptions)(input.generation), http: (0, exports.httpOptions)(input.http) }));
};
exports.modelRef = modelRef;
function model(route, defaults, options) {
    if (defaults === void 0) { defaults = {}; }
    if (options === void 0) { options = {}; }
    return modelWithDefaults(route, defaults, options);
}
var Service = /** @class */ (function (_super) {
    __extends(Service, _super);
    function Service() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    return Service;
}(effect_1.Context.Service()("@icecode/LLMClient")));
exports.Service = Service;
var noRoute = function (model) {
    return new schema_1.LLMError({
        module: "LLMClient",
        method: "resolveRoute",
        reason: new schema_1.NoRouteReason({ route: model.route, provider: model.provider, model: model.id }),
    });
};
var resolveRequestOptions = function (request) {
    var _a;
    return schema_1.LLMRequest.update(request, {
        generation: (_a = (0, schema_1.mergeGenerationOptions)(request.model.generation, request.generation)) !== null && _a !== void 0 ? _a : new schema_1.GenerationOptions({}),
        providerOptions: (0, schema_1.mergeProviderOptions)(request.model.providerOptions, request.providerOptions),
        http: (0, schema_1.mergeHttpOptions)(request.model.http, request.http),
    });
};
var streamError = function (route, message, cause) {
    var _a;
    var failed = (_a = cause.reasons.find(effect_1.Cause.isFailReason)) === null || _a === void 0 ? void 0 : _a.error;
    if (failed instanceof schema_1.LLMError)
        return failed;
    return ProviderShared.eventError(route, message, effect_1.Cause.pretty(cause));
};
function makeFromTransport(input) {
    var protocol = input.protocol;
    var decodeEventEffect = effect_1.Schema.decodeUnknownEffect(protocol.stream.event);
    var decodeEvent = function (route) { return function (frame) {
        return decodeEventEffect(frame).pipe(effect_1.Effect.mapError(function () {
            return ProviderShared.eventError(input.id, "Invalid ".concat(route, " stream event"), typeof frame === "string" ? frame : ProviderShared.encodeJson(frame));
        }));
    }; };
    var build = function (routeInput) {
        var _a;
        var route = {
            id: routeInput.id,
            provider: routeInput.provider === undefined ? undefined : schema_1.ProviderID.make(routeInput.provider),
            protocol: protocol.id,
            transport: routeInput.transport,
            defaults: (_a = routeInput.defaults) !== null && _a !== void 0 ? _a : {},
            body: protocol.body,
            with: function (patch) {
                var _a;
                var id = patch.id, provider = patch.provider, transport = patch.transport, defaults = __rest(patch, ["id", "provider", "transport"]);
                if (!id || id === routeInput.id)
                    throw new Error("Route.with(".concat(routeInput.id, ") requires a new route id"));
                return build(__assign(__assign({}, routeInput), { id: id, provider: provider !== null && provider !== void 0 ? provider : routeInput.provider, transport: (_a = transport) !== null && _a !== void 0 ? _a : routeInput.transport, defaults: mergeRouteDefaults(routeInput.defaults, defaults) }));
            },
            model: function (input) { return modelWithDefaults(route, {}, {})(input); },
            prepareTransport: routeInput.transport.prepare,
            streamPrepared: function (prepared, request, runtime) {
                var route = "".concat(request.model.provider, "/").concat(request.model.route);
                var events = routeInput.transport
                    .frames(prepared, request, runtime)
                    .pipe(effect_1.Stream.mapEffect(decodeEvent(route)), protocol.stream.terminal ? effect_1.Stream.takeUntil(protocol.stream.terminal) : function (stream) { return stream; });
                return events.pipe(effect_1.Stream.mapAccumEffect(protocol.stream.initial, protocol.stream.step, protocol.stream.onHalt ? { onHalt: protocol.stream.onHalt } : undefined), effect_1.Stream.catchCause(function (cause) { return effect_1.Stream.fail(streamError(route, "Failed to read ".concat(route, " stream"), cause)); }));
            },
        };
        return register(route);
    };
    return build(input);
}
function make(input) {
    if ("transport" in input)
        return makeFromTransport(input);
    var protocol = input.protocol;
    var encodeBody = effect_1.Schema.encodeSync(effect_1.Schema.fromJsonString(protocol.body.schema));
    return makeFromTransport({
        id: input.id,
        provider: input.provider,
        protocol: protocol,
        transport: transport_1.HttpTransport.httpJson({
            endpoint: input.endpoint,
            auth: input.auth,
            framing: input.framing,
            encodeBody: encodeBody,
            headers: input.headers,
        }),
        defaults: input.defaults,
    });
}
// `compile` is the important boundary: it turns a common `LLMRequest` into a
// validated provider body plus transport-private prepared data, but does not
// execute transport.
var compile = effect_1.Effect.fn("LLM.compile")(function (request) {
    var resolved, route, body, prepared;
    return __generator(this, function (_a) {
        switch (_a.label) {
            case 0:
                resolved = resolveRequestOptions(request);
                route = registeredRoute(resolved.model.route);
                if (!!route) return [3 /*break*/, 2];
                return [5 /*yield**/, __values(noRoute(resolved.model))];
            case 1: return [2 /*return*/, _a.sent()];
            case 2: return [5 /*yield**/, __values(route.body
                    .from(resolved)
                    .pipe(effect_1.Effect.flatMap(ProviderShared.validateWith(effect_1.Schema.decodeUnknownEffect(route.body.schema)))))];
            case 3:
                body = _a.sent();
                return [5 /*yield**/, __values(route.prepareTransport(body, resolved))];
            case 4:
                prepared = _a.sent();
                return [2 /*return*/, {
                        request: resolved,
                        route: route,
                        body: body,
                        prepared: prepared,
                    }];
        }
    });
});
var prepareWith = effect_1.Effect.fn("LLMClient.prepare")(function (request) {
    var compiled;
    var _a;
    return __generator(this, function (_b) {
        switch (_b.label) {
            case 0: return [5 /*yield**/, __values(compile(request))];
            case 1:
                compiled = _b.sent();
                return [2 /*return*/, new schema_1.PreparedRequest({
                        id: (_a = compiled.request.id) !== null && _a !== void 0 ? _a : "request",
                        route: compiled.route.id,
                        protocol: compiled.route.protocol,
                        model: compiled.request.model,
                        body: compiled.body,
                        metadata: { transport: compiled.route.transport.id },
                    })];
        }
    });
});
var streamRequestWith = function (runtime) { return function (request) {
    return effect_1.Stream.unwrap(effect_1.Effect.gen(function () {
        var compiled;
        return __generator(this, function (_a) {
            switch (_a.label) {
                case 0: return [5 /*yield**/, __values(compile(request))];
                case 1:
                    compiled = _a.sent();
                    return [2 /*return*/, compiled.route.streamPrepared(compiled.prepared, compiled.request, runtime)];
            }
        });
    }));
}; };
var isToolRunOptions = function (input) {
    return "request" in input && "tools" in input;
};
var streamWith = function (streamRequest) {
    return (function (input) {
        if (isToolRunOptions(input))
            return ToolRuntime.stream(__assign(__assign({}, input), { stream: streamRequest }));
        return streamRequest(input);
    });
};
var generateWith = function (stream) {
    return effect_1.Effect.fn("LLM.generate")(function (input) {
        var _a;
        return __generator(this, function (_b) {
            switch (_b.label) {
                case 0:
                    _a = schema_1.LLMResponse.bind;
                    return [5 /*yield**/, __values(stream(input).pipe(effect_1.Stream.runFold(function () { return ({ events: [], usage: undefined }); }, function (acc, event) {
                            acc.events.push(event);
                            if ("usage" in event && event.usage !== undefined)
                                acc.usage = event.usage;
                            return acc;
                        })))];
                case 1: return [2 /*return*/, new (_a.apply(schema_1.LLMResponse, [void 0, _b.sent()]))()];
            }
        });
    });
};
var prepare = function (request) {
    return prepareWith(request);
};
exports.prepare = prepare;
function stream(input) {
    return effect_1.Stream.unwrap(effect_1.Effect.gen(function () {
        return __generator(this, function (_a) {
            switch (_a.label) {
                case 0: return [5 /*yield**/, __values(Service)];
                case 1: return [2 /*return*/, (_a.sent()).stream(input)];
            }
        });
    }));
}
function generate(input) {
    return effect_1.Effect.gen(function () {
        return __generator(this, function (_a) {
            switch (_a.label) {
                case 0: return [5 /*yield**/, __values(Service)];
                case 1: return [5 /*yield**/, __values((_a.sent()).generate(input))];
                case 2: return [2 /*return*/, _a.sent()];
            }
        });
    });
}
var streamRequest = function (request) {
    return effect_1.Stream.unwrap(effect_1.Effect.gen(function () {
        return __generator(this, function (_a) {
            switch (_a.label) {
                case 0: return [5 /*yield**/, __values(Service)];
                case 1: return [2 /*return*/, (_a.sent()).stream(request)];
            }
        });
    }));
};
exports.streamRequest = streamRequest;
exports.layer = effect_1.Layer.effect(Service, effect_1.Effect.gen(function () {
    var stream, _a, _b, _c;
    return __generator(this, function (_d) {
        switch (_d.label) {
            case 0:
                _a = streamWith;
                _b = streamRequestWith;
                _c = {};
                return [5 /*yield**/, __values(executor_1.RequestExecutor.Service)];
            case 1:
                stream = _a.apply(void 0, [_b.apply(void 0, [(_c.http = _d.sent(), _c)])]);
                return [2 /*return*/, Service.of({ prepare: prepareWith, stream: stream, generate: generateWith(stream) })];
        }
    });
}));
exports.layerWithWebSocket = effect_1.Layer.effect(Service, effect_1.Effect.gen(function () {
    var stream, _a, _b, _c;
    return __generator(this, function (_d) {
        switch (_d.label) {
            case 0:
                _a = streamWith;
                _b = streamRequestWith;
                _c = {};
                return [5 /*yield**/, __values(executor_1.RequestExecutor.Service)];
            case 1:
                _c.http = _d.sent();
                return [5 /*yield**/, __values(transport_2.WebSocketExecutor.Service)];
            case 2:
                stream = _a.apply(void 0, [_b.apply(void 0, [(_c.webSocket = _d.sent(),
                            _c)])]);
                return [2 /*return*/, Service.of({ prepare: prepareWith, stream: stream, generate: generateWith(stream) })];
        }
    });
}));
exports.Route = { make: make, model: model };
exports.LLMClient = {
    Service: Service,
    layer: exports.layer,
    layerWithWebSocket: exports.layerWithWebSocket,
    prepare: exports.prepare,
    stream: stream,
    generate: generate,
    stepCountIs: ToolRuntime.stepCountIs,
};
