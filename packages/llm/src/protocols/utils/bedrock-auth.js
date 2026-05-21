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
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
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
exports.BedrockAuth = exports.nativeCredentials = exports.auth = exports.region = void 0;
var aws4fetch_1 = require("aws4fetch");
var effect_1 = require("effect");
var http_1 = require("effect/unstable/http");
var auth_1 = require("../../route/auth");
var shared_1 = require("../shared");
var NativeCredentials = effect_1.Schema.Struct({
    accessKeyId: effect_1.Schema.String,
    secretAccessKey: effect_1.Schema.String,
    region: effect_1.Schema.optional(effect_1.Schema.String),
    sessionToken: effect_1.Schema.optional(effect_1.Schema.String),
});
var decodeNativeCredentials = effect_1.Schema.decodeUnknownOption(NativeCredentials);
var region = function (request) {
    var _a, _b, _c;
    var fromNative = (_a = request.model.native) === null || _a === void 0 ? void 0 : _a.aws_region;
    if (typeof fromNative === "string" && fromNative !== "")
        return fromNative;
    return ((_c = decodeNativeCredentials((_b = request.model.native) === null || _b === void 0 ? void 0 : _b.aws_credentials).pipe(effect_1.Option.map(function (credentials) { return credentials.region; }), effect_1.Option.getOrUndefined)) !== null && _c !== void 0 ? _c : "us-east-1");
};
exports.region = region;
var credentialsFromInput = function (request) {
    var _a;
    return decodeNativeCredentials((_a = request.model.native) === null || _a === void 0 ? void 0 : _a.aws_credentials).pipe(effect_1.Option.map(function (creds) { var _a; return (__assign(__assign({}, creds), { region: (_a = creds.region) !== null && _a !== void 0 ? _a : (0, exports.region)(request) })); }), effect_1.Option.getOrUndefined);
};
var signRequest = function (input) {
    return effect_1.Effect.tryPromise({
        try: function () { return __awaiter(void 0, void 0, void 0, function () {
            var signed;
            return __generator(this, function (_a) {
                switch (_a.label) {
                    case 0: return [4 /*yield*/, new aws4fetch_1.AwsV4Signer({
                            url: input.url,
                            method: "POST",
                            headers: Object.entries(input.headers),
                            body: input.body,
                            region: input.credentials.region,
                            accessKeyId: input.credentials.accessKeyId,
                            secretAccessKey: input.credentials.secretAccessKey,
                            sessionToken: input.credentials.sessionToken,
                            service: "bedrock",
                        }).sign()];
                    case 1:
                        signed = _a.sent();
                        return [2 /*return*/, Object.fromEntries(signed.headers.entries())];
                }
            });
        }); },
        catch: function (error) {
            return shared_1.ProviderShared.invalidRequest("Bedrock Converse SigV4 signing failed: ".concat(error instanceof Error ? error.message : String(error)));
        },
    });
};
/**
 * Bedrock auth. `model.apiKey` (Bedrock's newer Bearer API key auth) wins if
 * set; otherwise sign the exact JSON bytes with SigV4 using credentials from
 * `model.native.aws_credentials`.
 */
exports.auth = auth_1.Auth.custom(function (input) {
    if (input.request.model.apiKey)
        return auth_1.Auth.toEffect(auth_1.Auth.bearer())(input);
    return effect_1.Effect.gen(function () {
        var credentials, headersForSigning, signed;
        return __generator(this, function (_a) {
            switch (_a.label) {
                case 0:
                    credentials = credentialsFromInput(input.request);
                    if (!!credentials) return [3 /*break*/, 2];
                    return [5 /*yield**/, __values(shared_1.ProviderShared.invalidRequest("Bedrock Converse requires either model.apiKey or AWS credentials in model.native.aws_credentials"))];
                case 1: return [2 /*return*/, _a.sent()];
                case 2:
                    headersForSigning = http_1.Headers.set(input.headers, "content-type", "application/json");
                    return [5 /*yield**/, __values(signRequest({ url: input.url, body: input.body, headers: headersForSigning, credentials: credentials }))];
                case 3:
                    signed = _a.sent();
                    return [2 /*return*/, http_1.Headers.setAll(headersForSigning, signed)];
            }
        });
    });
});
var nativeCredentials = function (native, credentials) {
    return credentials
        ? __assign(__assign({}, native), { aws_credentials: credentials, aws_region: credentials.region }) : native;
};
exports.nativeCredentials = nativeCredentials;
exports.BedrockAuth = require("./bedrock-auth");
