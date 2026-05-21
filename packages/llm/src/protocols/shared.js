"use strict";
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
exports.ProviderShared = exports.jsonPost = exports.validateWith = exports.unsupportedContent = exports.supportsContent = exports.matchToolChoice = exports.invalidRequest = exports.sseFraming = exports.errorText = exports.toolResultText = exports.trimBaseUrl = exports.mediaBytes = exports.parseToolInput = exports.joinText = exports.parseJson = exports.eventError = exports.totalTokens = exports.isRecord = exports.optionalNull = exports.optionalArray = exports.JsonObject = exports.encodeJson = exports.decodeJson = exports.Json = void 0;
var node_buffer_1 = require("node:buffer");
var effect_1 = require("effect");
var Sse = require("effect/unstable/encoding/Sse");
var http_1 = require("effect/unstable/http");
var schema_1 = require("../schema");
exports.Json = effect_1.Schema.fromJsonString(effect_1.Schema.Unknown);
exports.decodeJson = effect_1.Schema.decodeUnknownSync(exports.Json);
exports.encodeJson = effect_1.Schema.encodeSync(exports.Json);
exports.JsonObject = effect_1.Schema.Record(effect_1.Schema.String, effect_1.Schema.Unknown);
var optionalArray = function (schema) { return effect_1.Schema.optional(effect_1.Schema.Array(schema)); };
exports.optionalArray = optionalArray;
var optionalNull = function (schema) { return effect_1.Schema.optional(effect_1.Schema.NullOr(schema)); };
exports.optionalNull = optionalNull;
/**
 * Plain-record narrowing. Excludes arrays so routes checking nested JSON
 * Schema fragments don't accidentally treat a tuple as a key/value bag.
 */
var isRecord = function (value) {
    return typeof value === "object" && value !== null && !Array.isArray(value);
};
exports.isRecord = isRecord;
/**
 * `Usage.totalTokens` policy shared by every route. Honors a provider-
 * supplied total; otherwise falls back to `inputTokens + outputTokens` only
 * when at least one is defined. Returns `undefined` when neither input nor
 * output is known so routes don't publish a misleading `0`.
 */
var totalTokens = function (inputTokens, outputTokens, total) {
    if (total !== undefined)
        return total;
    if (inputTokens === undefined && outputTokens === undefined)
        return undefined;
    return (inputTokens !== null && inputTokens !== void 0 ? inputTokens : 0) + (outputTokens !== null && outputTokens !== void 0 ? outputTokens : 0);
};
exports.totalTokens = totalTokens;
var eventError = function (route, message, raw) {
    return new schema_1.LLMError({
        module: "ProviderShared",
        method: "stream",
        reason: new schema_1.InvalidProviderOutputReason({ route: route, message: message, raw: raw }),
    });
};
exports.eventError = eventError;
var parseJson = function (route, input, message) {
    return effect_1.Effect.try({
        try: function () { return (0, exports.decodeJson)(input); },
        catch: function () { return (0, exports.eventError)(route, message, input); },
    });
};
exports.parseJson = parseJson;
/**
 * Join the `text` field of a list of parts with newlines. Used by routes
 * that flatten system / message content arrays into a single provider string
 * (OpenAI Chat `system` content, OpenAI Responses `system` content, Gemini
 * `systemInstruction.parts[].text`).
 */
var joinText = function (parts) { return parts.map(function (part) { return part.text; }).join("\n"); };
exports.joinText = joinText;
/**
 * Parse the streamed JSON input of a tool call. Treats an empty string as
 * `"{}"` — providers occasionally finish a tool call without ever emitting
 * input deltas (e.g. zero-arg tools). The error message is uniform across
 * routes: `Invalid JSON input for <route> tool call <name>`.
 */
var parseToolInput = function (route, name, raw) {
    return (0, exports.parseJson)(route, raw || "{}", "Invalid JSON input for ".concat(route, " tool call ").concat(name));
};
exports.parseToolInput = parseToolInput;
/**
 * Encode a `MediaPart`'s raw bytes for inclusion in a JSON request body.
 * `data: string` is assumed to already be base64 (matches caller convention
 * across Gemini / Bedrock); `data: Uint8Array` is base64-encoded here. Used
 * by every route that supports image / document inputs.
 */
var mediaBytes = function (part) {
    return typeof part.data === "string" ? part.data : node_buffer_1.Buffer.from(part.data).toString("base64");
};
exports.mediaBytes = mediaBytes;
var trimBaseUrl = function (value) { return value.replace(/\/+$/, ""); };
exports.trimBaseUrl = trimBaseUrl;
var toolResultText = function (part) {
    if (part.result.type === "text" || part.result.type === "error")
        return String(part.result.value);
    return (0, exports.encodeJson)(part.result.value);
};
exports.toolResultText = toolResultText;
var errorText = function (error) {
    if (error instanceof Error)
        return error.message;
    if (typeof error === "string")
        return error;
    if (typeof error === "number" || typeof error === "boolean" || typeof error === "bigint")
        return String(error);
    if (error === null)
        return "null";
    if (error === undefined)
        return "undefined";
    return "Unknown stream error";
};
exports.errorText = errorText;
/**
 * `framing` step for Server-Sent Events. Decodes UTF-8, runs the SSE channel
 * decoder, and drops empty / `[DONE]` keep-alive events so the downstream
 * `decodeChunk` sees one JSON string per element. The SSE channel emits a
 * `Retry` control event on its error channel; we drop it here (we don't
 * implement client-driven retries) so the public error channel stays
 * `LLMError`.
 */
var sseFraming = function (bytes) {
    return bytes.pipe(effect_1.Stream.decodeText(), effect_1.Stream.pipeThroughChannel(Sse.decode()), effect_1.Stream.catchTag("Retry", function () { return effect_1.Stream.empty; }), effect_1.Stream.filter(function (event) { return event.data.length > 0 && event.data !== "[DONE]"; }), effect_1.Stream.map(function (event) { return event.data; }));
};
exports.sseFraming = sseFraming;
/**
 * Canonical invalid-request constructor. Lift one-line `const invalid =
 * (message) => invalidRequest(message)` aliases out of every
 * route so the error constructor lives in one place. If we ever extend
 * `InvalidRequestReason` with route context or trace metadata, the change
 * lands here.
 */
var invalidRequest = function (message) {
    return new schema_1.LLMError({
        module: "ProviderShared",
        method: "request",
        reason: new schema_1.InvalidRequestReason({ message: message }),
    });
};
exports.invalidRequest = invalidRequest;
var matchToolChoice = function (route, toolChoice, cases) {
    return effect_1.Effect.gen(function () {
        return __generator(this, function (_a) {
            switch (_a.label) {
                case 0:
                    if (toolChoice.type === "auto")
                        return [2 /*return*/, cases.auto()];
                    if (toolChoice.type === "none")
                        return [2 /*return*/, cases.none()];
                    if (toolChoice.type === "required")
                        return [2 /*return*/, cases.required()];
                    if (!!toolChoice.name) return [3 /*break*/, 2];
                    return [5 /*yield**/, __values((0, exports.invalidRequest)("".concat(route, " tool choice requires a tool name")))];
                case 1: return [2 /*return*/, _a.sent()];
                case 2: return [2 /*return*/, cases.tool(toolChoice.name)];
            }
        });
    });
};
exports.matchToolChoice = matchToolChoice;
var formatContentTypes = function (types) {
    var _a;
    if (types.length <= 1)
        return (_a = types[0]) !== null && _a !== void 0 ? _a : "";
    if (types.length === 2)
        return "".concat(types[0], " and ").concat(types[1]);
    return "".concat(types.slice(0, -1).join(", "), ", and ").concat(types.at(-1));
};
var supportsContent = function (part, types) { return types.includes(part.type); };
exports.supportsContent = supportsContent;
var unsupportedContent = function (route, role, types) { return (0, exports.invalidRequest)("".concat(route, " ").concat(role, " messages only support ").concat(formatContentTypes(types), " content for now")); };
exports.unsupportedContent = unsupportedContent;
/**
 * Build a `validate` step from a Schema decoder. Replaces the per-route
 * lambda body `(payload) => decode(payload).pipe(Effect.mapError((e) =>
 * invalid(e.message)))`. Any decode error is translated into
 * `LLMError` carrying the original parse-error message.
 */
var validateWith = function (decode) {
    return function (payload) {
        return decode(payload).pipe(effect_1.Effect.mapError(function (error) { return (0, exports.invalidRequest)(error.message); }));
    };
};
exports.validateWith = validateWith;
/**
 * Build an HTTP POST with a JSON body. Sets `content-type: application/json`
 * automatically after caller-supplied headers so routes cannot accidentally
 * send JSON with a stale content type. The body is passed pre-encoded so
 * routes can choose between
 * `Schema.encodeSync(payload)` and `ProviderShared.encodeJson(payload)`.
 */
var jsonPost = function (input) {
    return http_1.HttpClientRequest.post(input.url).pipe(http_1.HttpClientRequest.setHeaders(http_1.Headers.set(http_1.Headers.fromInput(input.headers), "content-type", "application/json")), http_1.HttpClientRequest.bodyText(input.body, "application/json"));
};
exports.jsonPost = jsonPost;
exports.ProviderShared = require("./shared");
