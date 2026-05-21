"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AuthOptions = exports.bearer = void 0;
var auth_1 = require("./auth");
/**
 * Standard bearer-auth resolution for providers: honor an explicit `auth`
 * override, otherwise resolve `apiKey` (option > config var) and apply it as
 * a bearer token.
 */
var bearer = function (options, envVar) {
    if ("auth" in options && options.auth)
        return options.auth;
    return (Array.isArray(envVar) ? envVar : [envVar])
        .reduce(function (auth, name) { return auth.orElse(auth_1.Auth.config(name)); }, auth_1.Auth.optional("apiKey" in options ? options.apiKey : undefined, "apiKey"))
        .bearer();
};
exports.bearer = bearer;
exports.AuthOptions = require("./auth-options");
