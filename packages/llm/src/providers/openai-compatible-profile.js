"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.byProvider = exports.profiles = void 0;
exports.profiles = {
    baseten: { provider: "baseten", baseURL: "https://inference.baseten.co/v1" },
    cerebras: { provider: "cerebras", baseURL: "https://api.cerebras.ai/v1" },
    deepinfra: { provider: "deepinfra", baseURL: "https://api.deepinfra.com/v1/openai" },
    deepseek: { provider: "deepseek", baseURL: "https://api.deepseek.com/v1" },
    fireworks: { provider: "fireworks", baseURL: "https://api.fireworks.ai/inference/v1" },
    groq: { provider: "groq", baseURL: "https://api.groq.com/openai/v1" },
    openrouter: { provider: "openrouter", baseURL: "https://openrouter.ai/api/v1" },
    togetherai: { provider: "togetherai", baseURL: "https://api.together.xyz/v1" },
    xai: { provider: "xai", baseURL: "https://api.x.ai/v1" },
};
exports.byProvider = Object.fromEntries(Object.values(exports.profiles).map(function (profile) { return [profile.provider, profile]; }));
