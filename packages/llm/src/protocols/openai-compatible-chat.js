"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.OpenAICompatibleChat = exports.model = exports.route = void 0;
var client_1 = require("../route/client");
var endpoint_1 = require("../route/endpoint");
var framing_1 = require("../route/framing");
var OpenAIChat = require("./openai-chat");
var ADAPTER = "openai-compatible-chat";
/**
 * Route for non-OpenAI providers that expose an OpenAI Chat-compatible
 * `/chat/completions` endpoint. Reuses `OpenAIChat.protocol` end-to-end and
 * overrides only the route id so providers can be resolved per-family without
 * colliding with native OpenAI. The model carries the host on `baseURL`,
 * supplied by whichever profile/provider helper builds it.
 */
exports.route = client_1.Route.make({
    id: ADAPTER,
    protocol: OpenAIChat.protocol,
    endpoint: endpoint_1.Endpoint.path("/chat/completions"),
    framing: framing_1.Framing.sse,
});
exports.model = client_1.Route.model(exports.route);
exports.OpenAICompatibleChat = require("./openai-compatible-chat");
