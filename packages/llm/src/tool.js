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
Object.defineProperty(exports, "__esModule", { value: true });
exports.Tool = exports.ToolFailure = exports.toDefinitions = exports.tool = void 0;
exports.make = make;
var effect_1 = require("effect");
var schema_1 = require("./schema");
Object.defineProperty(exports, "ToolFailure", { enumerable: true, get: function () { return schema_1.ToolFailure; } });
function make(config) {
    if ("jsonSchema" in config) {
        return {
            description: config.description,
            parameters: effect_1.Schema.Unknown,
            success: effect_1.Schema.Unknown,
            execute: config.execute,
            _decode: effect_1.Effect.succeed,
            _encode: effect_1.Effect.succeed,
            _definition: new schema_1.ToolDefinition({
                name: "",
                description: config.description,
                inputSchema: config.jsonSchema,
            }),
        };
    }
    return {
        description: config.description,
        parameters: config.parameters,
        success: config.success,
        execute: config.execute,
        _decode: effect_1.Schema.decodeUnknownEffect(config.parameters),
        _encode: effect_1.Schema.encodeEffect(config.success),
        _definition: new schema_1.ToolDefinition({
            name: "",
            description: config.description,
            inputSchema: toJsonSchema(config.parameters),
        }),
    };
}
exports.tool = make;
/**
 * Convert a tools record into the `ToolDefinition[]` shape that
 * `LLMRequest.tools` expects. The runtime calls this internally; consumers
 * that build `LLMRequest` themselves can use it too.
 *
 * Tool names come from the record keys, so the per-tool cached
 * `_definition` is rebuilt with the correct name here. The JSON Schema body
 * is reused.
 */
var toDefinitions = function (tools) {
    return Object.entries(tools).map(function (_a) {
        var name = _a[0], item = _a[1];
        return new schema_1.ToolDefinition({
            name: name,
            description: item._definition.description,
            inputSchema: item._definition.inputSchema,
        });
    });
};
exports.toDefinitions = toDefinitions;
var toJsonSchema = function (schema) {
    var document = effect_1.Schema.toJsonSchemaDocument(schema);
    if (Object.keys(document.definitions).length === 0)
        return document.schema;
    return __assign(__assign({}, document.schema), { $defs: document.definitions });
};
exports.Tool = require("./tool");
