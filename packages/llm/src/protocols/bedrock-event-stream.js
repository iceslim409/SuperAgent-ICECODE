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
exports.BedrockEventStream = exports.framing = void 0;
var eventstream_codec_1 = require("@smithy/eventstream-codec");
var util_utf8_1 = require("@smithy/util-utf8");
var effect_1 = require("effect");
var shared_1 = require("./shared");
// Bedrock streams responses using the AWS event stream binary protocol — each
// frame is `[length:4][headers-length:4][prelude-crc:4][headers][payload][crc:4]`.
// We use `@smithy/eventstream-codec` to validate framing and CRCs, then
// reconstruct the JSON wrapping by `:event-type` so the chunk schema can match.
var eventCodec = new eventstream_codec_1.EventStreamCodec(util_utf8_1.toUtf8, util_utf8_1.fromUtf8);
var utf8 = new TextDecoder();
var initialFrameBuffer = { buffer: new Uint8Array(0), offset: 0 };
var appendChunk = function (state, chunk) {
    var remaining = state.buffer.length - state.offset;
    // Compact: drop the consumed prefix and append the new chunk in one alloc.
    // This bounds buffer growth to at most one network chunk past the live
    // window, regardless of stream length.
    var next = new Uint8Array(remaining + chunk.length);
    next.set(state.buffer.subarray(state.offset), 0);
    next.set(chunk, remaining);
    return { buffer: next, offset: 0 };
};
var consumeFrames = function (route) { return function (state, chunk) {
    return effect_1.Effect.gen(function () {
        var cursor, out, _loop_1, state_1;
        var _a, _b;
        return __generator(this, function (_c) {
            switch (_c.label) {
                case 0:
                    cursor = appendChunk(state, chunk);
                    out = [];
                    _loop_1 = function () {
                        var view, totalLength, decoded, eventType, payload, parsed;
                        var _d;
                        return __generator(this, function (_e) {
                            switch (_e.label) {
                                case 0:
                                    view = cursor.buffer.subarray(cursor.offset);
                                    totalLength = new DataView(view.buffer, view.byteOffset, view.byteLength).getUint32(0, false);
                                    if (view.length < totalLength)
                                        return [2 /*return*/, "break"];
                                    return [5 /*yield**/, __values(effect_1.Effect.try({
                                            try: function () { return eventCodec.decode(view.subarray(0, totalLength)); },
                                            catch: function (error) {
                                                return shared_1.ProviderShared.eventError(route, "Failed to decode Bedrock Converse event-stream frame: ".concat(error instanceof Error ? error.message : String(error)));
                                            },
                                        }))];
                                case 1:
                                    decoded = _e.sent();
                                    cursor = { buffer: cursor.buffer, offset: cursor.offset + totalLength };
                                    if (((_a = decoded.headers[":message-type"]) === null || _a === void 0 ? void 0 : _a.value) !== "event")
                                        return [2 /*return*/, "continue"];
                                    eventType = (_b = decoded.headers[":event-type"]) === null || _b === void 0 ? void 0 : _b.value;
                                    if (typeof eventType !== "string")
                                        return [2 /*return*/, "continue"];
                                    payload = utf8.decode(decoded.body);
                                    if (!payload)
                                        return [2 /*return*/, "continue"];
                                    return [5 /*yield**/, __values(shared_1.ProviderShared.parseJson(route, payload, "Failed to parse Bedrock Converse event-stream payload"))];
                                case 2:
                                    parsed = (_e.sent());
                                    delete parsed.p;
                                    out.push((_d = {}, _d[eventType] = parsed, _d));
                                    return [2 /*return*/];
                            }
                        });
                    };
                    _c.label = 1;
                case 1:
                    if (!(cursor.buffer.length - cursor.offset >= 4)) return [3 /*break*/, 3];
                    return [5 /*yield**/, _loop_1()];
                case 2:
                    state_1 = _c.sent();
                    if (state_1 === "break")
                        return [3 /*break*/, 3];
                    return [3 /*break*/, 1];
                case 3: return [2 /*return*/, [cursor, out]];
            }
        });
    });
}; };
/**
 * AWS event-stream framing for Bedrock Converse. Each frame is decoded by
 * `@smithy/eventstream-codec` (length + header + payload + CRC) and rewrapped
 * under its `:event-type` header so the chunk schema can match the JSON
 * payload directly.
 */
var framing = function (route) { return ({
    id: "aws-event-stream",
    frame: function (bytes) { return bytes.pipe(effect_1.Stream.mapAccumEffect(function () { return initialFrameBuffer; }, consumeFrames(route))); },
}); };
exports.framing = framing;
exports.BedrockEventStream = require("./bedrock-event-stream");
