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
exports.GeminiToolSchema = exports.convert = void 0;
var shared_1 = require("../shared");
// Gemini accepts a JSON Schema-like dialect for tool parameters, but rejects a
// handful of common JSON Schema shapes. Keep this projection isolated so the
// Gemini protocol file still reads like the other protocol modules.
var SCHEMA_INTENT_KEYS = [
    "type",
    "properties",
    "items",
    "prefixItems",
    "enum",
    "const",
    "$ref",
    "additionalProperties",
    "patternProperties",
    "required",
    "not",
    "if",
    "then",
    "else",
];
var isRecord = shared_1.ProviderShared.isRecord;
var hasCombiner = function (schema) {
    return isRecord(schema) && (Array.isArray(schema.anyOf) || Array.isArray(schema.oneOf) || Array.isArray(schema.allOf));
};
var hasSchemaIntent = function (schema) {
    return isRecord(schema) && (hasCombiner(schema) || SCHEMA_INTENT_KEYS.some(function (key) { return key in schema; }));
};
var sanitizeNode = function (schema) {
    var _a;
    if (!isRecord(schema))
        return Array.isArray(schema) ? schema.map(sanitizeNode) : schema;
    var result = Object.fromEntries(Object.entries(schema).map(function (_a) {
        var key = _a[0], value = _a[1];
        return [
            key,
            key === "enum" && Array.isArray(value) ? value.map(String) : sanitizeNode(value),
        ];
    }));
    if (Array.isArray(result.enum) && (result.type === "integer" || result.type === "number"))
        result.type = "string";
    var properties = result.properties;
    if (result.type === "object" && isRecord(properties) && Array.isArray(result.required)) {
        result.required = result.required.filter(function (field) { return typeof field === "string" && field in properties; });
    }
    if (result.type === "array" && !hasCombiner(result)) {
        result.items = (_a = result.items) !== null && _a !== void 0 ? _a : {};
        if (isRecord(result.items) && !hasSchemaIntent(result.items))
            result.items = __assign(__assign({}, result.items), { type: "string" });
    }
    if (typeof result.type === "string" && result.type !== "object" && !hasCombiner(result)) {
        delete result.properties;
        delete result.required;
    }
    return result;
};
var emptyObjectSchema = function (schema) {
    return schema.type === "object" &&
        (!isRecord(schema.properties) || Object.keys(schema.properties).length === 0) &&
        !schema.additionalProperties;
};
var projectNode = function (schema) {
    if (!isRecord(schema))
        return undefined;
    if (emptyObjectSchema(schema))
        return undefined;
    return Object.fromEntries([
        ["description", schema.description],
        ["required", schema.required],
        ["format", schema.format],
        ["type", Array.isArray(schema.type) ? schema.type.filter(function (type) { return type !== "null"; })[0] : schema.type],
        ["nullable", Array.isArray(schema.type) && schema.type.includes("null") ? true : undefined],
        ["enum", schema.const !== undefined ? [schema.const] : schema.enum],
        [
            "properties",
            isRecord(schema.properties)
                ? Object.fromEntries(Object.entries(schema.properties).map(function (_a) {
                    var key = _a[0], value = _a[1];
                    return [key, projectNode(value)];
                }))
                : undefined,
        ],
        [
            "items",
            Array.isArray(schema.items)
                ? schema.items.map(projectNode)
                : schema.items === undefined
                    ? undefined
                    : projectNode(schema.items),
        ],
        ["allOf", Array.isArray(schema.allOf) ? schema.allOf.map(projectNode) : undefined],
        ["anyOf", Array.isArray(schema.anyOf) ? schema.anyOf.map(projectNode) : undefined],
        ["oneOf", Array.isArray(schema.oneOf) ? schema.oneOf.map(projectNode) : undefined],
        ["minLength", schema.minLength],
    ].filter(function (entry) { return entry[1] !== undefined; }));
};
var convert = function (schema) { return projectNode(sanitizeNode(schema)); };
exports.convert = convert;
exports.GeminiToolSchema = require("./gemini-tool-schema");
