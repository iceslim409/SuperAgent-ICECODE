"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Protocol = exports.jsonEvent = exports.make = void 0;
var effect_1 = require("effect");
/**
 * Construct a `Protocol` from its body and stream pieces:
 *
 * - `body.schema` infers the provider-native request body shape.
 * - `body.from` ties the common `LLMRequest` to the provider body.
 * - `stream.event` infers the decoded streaming event and the wire frame.
 * - `stream.initial`, `stream.step`, and `stream.onHalt` infer the parser state.
 *
 * Provider implementations should usually call `Protocol.make({ ... })`
 * without explicit type arguments; the schemas and parser functions are the
 * source of truth. The constructor remains as the public seam for future
 * cross-cutting concerns such as tracing or instrumentation.
 */
var make = function (input) { return input; };
exports.make = make;
var jsonEvent = function (schema) { return effect_1.Schema.fromJsonString(schema); };
exports.jsonEvent = jsonEvent;
exports.Protocol = require("./protocol");
