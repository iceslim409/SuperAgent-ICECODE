"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.BedrockCache = exports.block = exports.CachePointBlock = void 0;
var effect_1 = require("effect");
// Bedrock cache markers are positional: emit a `cachePoint` block immediately
// after the content the caller wants treated as a cacheable prefix.
exports.CachePointBlock = effect_1.Schema.Struct({
    cachePoint: effect_1.Schema.Struct({ type: effect_1.Schema.tag("default") }),
});
// Bedrock recently added optional `ttl: "5m" | "1h"` on cachePoint. Map
// `CacheHint.ttlSeconds` here once a recorded cassette validates the wire shape.
var DEFAULT = { cachePoint: { type: "default" } };
var block = function (cache) {
    if ((cache === null || cache === void 0 ? void 0 : cache.type) !== "ephemeral" && (cache === null || cache === void 0 ? void 0 : cache.type) !== "persistent")
        return undefined;
    return DEFAULT;
};
exports.block = block;
exports.BedrockCache = require("./bedrock-cache");
