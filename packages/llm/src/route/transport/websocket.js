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
exports.WebSocketTransport = exports.WebSocketExecutor = exports.json = exports.messageText = exports.fromWebSocket = exports.open = exports.Service = void 0;
var effect_1 = require("effect");
var auth_1 = require("../auth");
var schema_1 = require("../../schema");
var HttpTransport = require("./http");
var Service = /** @class */ (function (_super) {
    __extends(Service, _super);
    function Service() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    return Service;
}(effect_1.Context.Service()("@icecode/LLM/WebSocketExecutor")));
exports.Service = Service;
var transportError = function (method, message, input) {
    if (input === void 0) { input = {}; }
    return new schema_1.LLMError({
        module: "WebSocketExecutor",
        method: method,
        reason: new schema_1.TransportReason({ message: message, url: input.url, kind: input.kind }),
    });
};
var eventMessage = function (event) {
    if ("message" in event && typeof event.message === "string")
        return event.message;
    return event.type;
};
var binaryMessage = function (data) {
    if (data instanceof Uint8Array)
        return data;
    if (data instanceof ArrayBuffer)
        return new Uint8Array(data);
    if (ArrayBuffer.isView(data))
        return new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
    return undefined;
};
var waitOpen = function (ws, input) {
    if (ws.readyState === globalThis.WebSocket.OPEN)
        return effect_1.Effect.void;
    if (ws.readyState === globalThis.WebSocket.CLOSING || ws.readyState === globalThis.WebSocket.CLOSED) {
        return effect_1.Effect.fail(transportError("open", "WebSocket closed before opening (state ".concat(ws.readyState, ")"), {
            url: input.url,
            kind: "open",
        }));
    }
    return effect_1.Effect.callback(function (resume, signal) {
        var cleanup = function () {
            ws.removeEventListener("open", onOpen);
            ws.removeEventListener("error", onError);
            ws.removeEventListener("close", onClose);
            signal.removeEventListener("abort", onAbort);
        };
        var onAbort = function () {
            cleanup();
            if (ws.readyState !== globalThis.WebSocket.CLOSED && ws.readyState !== globalThis.WebSocket.CLOSING)
                ws.close(1000);
        };
        var onOpen = function () {
            cleanup();
            resume(effect_1.Effect.void);
        };
        var onError = function (event) {
            cleanup();
            resume(effect_1.Effect.fail(transportError("open", "Failed to open WebSocket: ".concat(eventMessage(event)), { url: input.url, kind: "open" })));
        };
        var onClose = function (event) {
            cleanup();
            resume(effect_1.Effect.fail(transportError("open", "WebSocket closed before opening with code ".concat(event.code), {
                url: input.url,
                kind: "open",
            })));
        };
        ws.addEventListener("open", onOpen, { once: true });
        ws.addEventListener("error", onError, { once: true });
        ws.addEventListener("close", onClose, { once: true });
        signal.addEventListener("abort", onAbort, { once: true });
    });
};
var webSocketUrl = function (value) {
    return effect_1.Effect.try({
        try: function () {
            var url = new URL(value);
            if (url.protocol === "https:") {
                url.protocol = "wss:";
                return url.toString();
            }
            if (url.protocol === "http:") {
                url.protocol = "ws:";
                return url.toString();
            }
            throw new Error("Unsupported WebSocket URL protocol ".concat(url.protocol));
        },
        catch: function (error) {
            return transportError("prepare", error instanceof Error ? error.message : "Invalid WebSocket URL", {
                url: value,
                kind: "websocket",
            });
        },
    });
};
var open = function (input) {
    return effect_1.Effect.try({
        try: function () {
            return new globalThis.WebSocket(input.url, { headers: input.headers });
        },
        catch: function (error) {
            return transportError("open", error instanceof Error ? error.message : "Failed to construct WebSocket", {
                url: input.url,
                kind: "open",
            });
        },
    }).pipe(effect_1.Effect.flatMap(function (ws) { return (0, exports.fromWebSocket)(ws, input); }));
};
exports.open = open;
var fromWebSocket = function (ws, input) {
    return effect_1.Effect.gen(function () {
        var messages, onMessage, onError, onClose, cleanup;
        return __generator(this, function (_a) {
            switch (_a.label) {
                case 0: return [5 /*yield**/, __values(waitOpen(ws, input))];
                case 1:
                    _a.sent();
                    return [5 /*yield**/, __values(effect_1.Queue.bounded(128))];
                case 2:
                    messages = _a.sent();
                    onMessage = function (event) {
                        if (typeof event.data === "string")
                            return effect_1.Queue.offerUnsafe(messages, event.data);
                        var binary = binaryMessage(event.data);
                        if (binary)
                            return effect_1.Queue.offerUnsafe(messages, binary);
                        effect_1.Queue.failCauseUnsafe(messages, effect_1.Cause.fail(transportError("message", "Unsupported WebSocket message payload", { url: input.url, kind: "message" })));
                    };
                    onError = function (event) {
                        effect_1.Queue.failCauseUnsafe(messages, effect_1.Cause.fail(transportError("message", "WebSocket error: ".concat(eventMessage(event)), { url: input.url, kind: "message" })));
                    };
                    onClose = function (event) {
                        if (event.code === 1000 || event.code === 1005)
                            return effect_1.Queue.endUnsafe(messages);
                        effect_1.Queue.failCauseUnsafe(messages, effect_1.Cause.fail(transportError("message", "WebSocket closed with code ".concat(event.code), { url: input.url, kind: "close" })));
                    };
                    cleanup = effect_1.Effect.sync(function () {
                        ws.removeEventListener("message", onMessage);
                        ws.removeEventListener("error", onError);
                        ws.removeEventListener("close", onClose);
                    }).pipe(effect_1.Effect.andThen(effect_1.Queue.shutdown(messages)));
                    ws.addEventListener("message", onMessage);
                    ws.addEventListener("error", onError);
                    ws.addEventListener("close", onClose);
                    return [2 /*return*/, {
                            sendText: function (message) {
                                return effect_1.Effect.try({
                                    try: function () { return ws.send(message); },
                                    catch: function (error) {
                                        return transportError("sendText", error instanceof Error ? error.message : "Failed to send WebSocket message", {
                                            url: input.url,
                                            kind: "write",
                                        });
                                    },
                                });
                            },
                            messages: effect_1.Stream.fromQueue(messages),
                            close: cleanup.pipe(effect_1.Effect.andThen(effect_1.Effect.sync(function () {
                                if (ws.readyState === globalThis.WebSocket.CLOSED || ws.readyState === globalThis.WebSocket.CLOSING)
                                    return;
                                ws.close(1000);
                            }))),
                        }];
            }
        });
    });
};
exports.fromWebSocket = fromWebSocket;
var messageText = function (message, decoder) {
    return typeof message === "string" ? message : decoder.decode(message);
};
exports.messageText = messageText;
var json = function (input) { return ({
    id: "websocket-json",
    with: function (patch) { return (0, exports.json)(__assign(__assign({}, input), patch)); },
    prepare: function (body, request) {
        return effect_1.Effect.gen(function () {
            var parts, _a, _b, _c;
            var _d;
            return __generator(this, function (_e) {
                switch (_e.label) {
                    case 0: return [5 /*yield**/, __values(HttpTransport.jsonRequestParts({
                            body: body,
                            request: request,
                            endpoint: input.endpoint,
                            auth: (_d = input.auth) !== null && _d !== void 0 ? _d : auth_1.Auth.bearer(),
                            encodeBody: input.encodeBody,
                            headers: input.headers,
                        }))];
                    case 1:
                        parts = _e.sent();
                        _a = {};
                        return [5 /*yield**/, __values(webSocketUrl(parts.url))];
                    case 2:
                        _a.url = _e.sent(),
                            _a.headers = parts.headers;
                        _c = (_b = input).encodeMessage;
                        return [5 /*yield**/, __values(input.toMessage(parts.jsonBody))];
                    case 3: return [2 /*return*/, (_a.message = _c.apply(_b, [_e.sent()]),
                            _a)];
                }
            });
        });
    },
    frames: function (prepared, _request, runtime) {
        var webSocket = runtime.webSocket;
        if (!webSocket) {
            return effect_1.Stream.fail(transportError("json", "WebSocket JSON transport requires WebSocketExecutor.Service", {
                url: prepared.url,
                kind: "websocket",
            }));
        }
        var decoder = new TextDecoder();
        return effect_1.Stream.unwrap(effect_1.Effect.gen(function () {
            var connection;
            return __generator(this, function (_a) {
                switch (_a.label) {
                    case 0: return [5 /*yield**/, __values(effect_1.Effect.acquireRelease(webSocket.open({ url: prepared.url, headers: prepared.headers }), function (connection) { return connection.close; }))];
                    case 1:
                        connection = _a.sent();
                        return [5 /*yield**/, __values(connection.sendText(prepared.message))];
                    case 2:
                        _a.sent();
                        return [2 /*return*/, connection.messages.pipe(effect_1.Stream.map(function (message) { return (0, exports.messageText)(message, decoder); }))];
                }
            });
        }));
    },
}); };
exports.json = json;
exports.WebSocketExecutor = {
    Service: Service,
    open: exports.open,
    fromWebSocket: exports.fromWebSocket,
    messageText: exports.messageText,
};
exports.WebSocketTransport = {
    json: exports.json,
};
