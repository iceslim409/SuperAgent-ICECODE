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
exports.Auth = exports.toEffect = exports.apiKeyHeader = exports.apiKey = exports.passthrough = exports.custom = exports.remove = exports.headers = exports.none = exports.effect = exports.config = exports.optional = exports.value = exports.isAuth = exports.MissingCredentialError = void 0;
exports.bearer = bearer;
exports.header = header;
exports.bearerHeader = bearerHeader;
var effect_1 = require("effect");
var http_1 = require("effect/unstable/http");
var schema_1 = require("../schema");
var MissingCredentialError = /** @class */ (function (_super) {
    __extends(MissingCredentialError, _super);
    function MissingCredentialError(source) {
        var _this = _super.call(this, "Missing auth credential: ".concat(source)) || this;
        _this.source = source;
        _this._tag = "MissingCredentialError";
        return _this;
    }
    return MissingCredentialError;
}(Error));
exports.MissingCredentialError = MissingCredentialError;
var isAuth = function (input) {
    return typeof input === "object" && input !== null && "apply" in input && typeof input.apply === "function";
};
exports.isAuth = isAuth;
var credential = function (load) {
    var self = {
        load: load,
        orElse: function (that) { return credential(load.pipe(effect_1.Effect.catch(function () { return that.load; }))); },
        bearer: function () { return fromCredential(self, function (secret) { return ({ authorization: "Bearer ".concat(secret) }); }); },
        header: function (name) { return fromCredential(self, function (secret) {
            var _a;
            return (_a = {}, _a[name] = secret, _a);
        }); },
        pipe: function (f) { return f(self); },
    };
    return self;
};
var auth = function (apply) {
    var self = {
        apply: apply,
        andThen: function (that) {
            return auth(function (input) { return apply(input).pipe(effect_1.Effect.flatMap(function (headers) { return that.apply(__assign(__assign({}, input), { headers: headers })); })); });
        },
        orElse: function (that) { return auth(function (input) { return apply(input).pipe(effect_1.Effect.catch(function () { return that.apply(input); })); }); },
        pipe: function (f) { return f(self); },
    };
    return self;
};
var fromCredential = function (source, render) {
    return auth(function (input) {
        return source.load.pipe(effect_1.Effect.map(function (secret) { return http_1.Headers.setAll(input.headers, render(effect_1.Redacted.value(secret))); }));
    });
};
var secretEffect = function (secret, source) {
    var redacted = typeof secret === "string" ? effect_1.Redacted.make(secret) : secret;
    if (effect_1.Redacted.value(redacted) === "")
        return effect_1.Effect.fail(new MissingCredentialError(source));
    return effect_1.Effect.succeed(redacted);
};
var credentialFromSecret = function (secret, source) {
    if (typeof secret === "string" || effect_1.Redacted.isRedacted(secret))
        return credential(secretEffect(secret, source));
    return credential(effect_1.Effect.gen(function () {
        var _a;
        return __generator(this, function (_b) {
            switch (_b.label) {
                case 0:
                    _a = secretEffect;
                    return [5 /*yield**/, __values(secret)];
                case 1: return [5 /*yield**/, __values(_a.apply(void 0, [_b.sent(), source]))];
                case 2: return [2 /*return*/, _b.sent()];
            }
        });
    }));
};
var value = function (secret, source) {
    if (source === void 0) { source = "value"; }
    return credentialFromSecret(secret, source);
};
exports.value = value;
var optional = function (secret, source) {
    if (source === void 0) { source = "optional value"; }
    return secret === undefined
        ? credential(effect_1.Effect.fail(new MissingCredentialError(source)))
        : credentialFromSecret(secret, source);
};
exports.optional = optional;
var config = function (name) { return credentialFromSecret(effect_1.Config.redacted(name), name); };
exports.config = config;
var effect = function (load) { return credential(load); };
exports.effect = effect;
exports.none = auth(function (input) { return effect_1.Effect.succeed(input.headers); });
var headers = function (input) {
    return auth(function (inputAuth) { return effect_1.Effect.succeed(http_1.Headers.setAll(inputAuth.headers, input)); });
};
exports.headers = headers;
var remove = function (name) { return auth(function (input) { return effect_1.Effect.succeed(http_1.Headers.remove(input.headers, name)); }); };
exports.remove = remove;
var custom = function (apply) { return auth(apply); };
exports.custom = custom;
exports.passthrough = exports.none;
var fromModelApiKey = function (from) {
    return auth(function (_a) {
        var request = _a.request, headers = _a.headers;
        var key = request.model.apiKey;
        if (!key)
            return effect_1.Effect.succeed(headers);
        return effect_1.Effect.succeed(http_1.Headers.setAll(headers, from(key)));
    });
};
var credentialInput = function (source) {
    return typeof source === "string" || effect_1.Redacted.isRedacted(source) || effect_1.Config.isConfig(source)
        ? credentialFromSecret(source, "value")
        : source;
};
function bearer(source) {
    if (source === undefined)
        return fromModelApiKey(function (key) { return ({ authorization: "Bearer ".concat(key) }); });
    return credentialInput(source).bearer();
}
exports.apiKey = bearer;
var apiKeyHeader = function (name) { return fromModelApiKey(function (key) {
    var _a;
    return (_a = {}, _a[name] = key, _a);
}); };
exports.apiKeyHeader = apiKeyHeader;
function header(name, source) {
    if (source === undefined) {
        return function (next) { return credentialInput(next).header(name); };
    }
    return credentialInput(source).header(name);
}
function bearerHeader(name, source) {
    var render = function (input) { return fromCredential(credentialInput(input), function (secret) {
        var _a;
        return (_a = {}, _a[name] = "Bearer ".concat(secret), _a);
    }); };
    if (source === undefined)
        return render;
    return render(source);
}
var toLLMError = function (error) {
    if (error instanceof MissingCredentialError || error instanceof effect_1.Config.ConfigError) {
        return new schema_1.LLMError({
            module: "Auth",
            method: "apply",
            reason: error instanceof MissingCredentialError
                ? new schema_1.AuthenticationReason({ message: error.message, kind: "missing" })
                : new schema_1.InvalidRequestReason({ message: "Failed to resolve auth config: ".concat(error.message) }),
        });
    }
    return error;
};
var toEffect = function (input) {
    return function (authInput) {
        return input.apply(authInput).pipe(effect_1.Effect.mapError(toLLMError));
    };
};
exports.toEffect = toEffect;
exports.Auth = require("./auth");
