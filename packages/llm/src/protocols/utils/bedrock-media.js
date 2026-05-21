"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.BedrockMedia = exports.lower = exports.DocumentBlock = exports.DocumentFormat = exports.ImageBlock = exports.ImageFormat = void 0;
var effect_1 = require("effect");
var shared_1 = require("../shared");
// Bedrock Converse accepts image `format` as the file extension and
// `source.bytes` as base64 in the JSON wire format.
exports.ImageFormat = effect_1.Schema.Literals(["png", "jpeg", "gif", "webp"]);
exports.ImageBlock = effect_1.Schema.Struct({
    image: effect_1.Schema.Struct({
        format: exports.ImageFormat,
        source: effect_1.Schema.Struct({ bytes: effect_1.Schema.String }),
    }),
});
// Bedrock document blocks require a user-facing name so the model can refer to
// the uploaded document.
exports.DocumentFormat = effect_1.Schema.Literals(["pdf", "csv", "doc", "docx", "xls", "xlsx", "html", "txt", "md"]);
exports.DocumentBlock = effect_1.Schema.Struct({
    document: effect_1.Schema.Struct({
        format: exports.DocumentFormat,
        name: effect_1.Schema.String,
        source: effect_1.Schema.Struct({ bytes: effect_1.Schema.String }),
    }),
});
var IMAGE_FORMATS = {
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/jpg": "jpeg",
    "image/gif": "gif",
    "image/webp": "webp",
};
var DOCUMENT_FORMATS = {
    "application/pdf": "pdf",
    "text/csv": "csv",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.ms-excel": "xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "text/html": "html",
    "text/plain": "txt",
    "text/markdown": "md",
};
var imageBlock = function (part, format) { return ({
    image: { format: format, source: { bytes: shared_1.ProviderShared.mediaBytes(part) } },
}); };
var documentBlock = function (part, format) {
    var _a;
    return ({
        document: {
            format: format,
            name: (_a = part.filename) !== null && _a !== void 0 ? _a : "document.".concat(format),
            source: { bytes: shared_1.ProviderShared.mediaBytes(part) },
        },
    });
};
// Route by MIME. Known image/document formats lower into a typed block; anything
// else fails with a clear error instead of silently degrading to a malformed
// document block. Image MIME types not in `IMAGE_FORMATS` (e.g. `image/svg+xml`)
// get an image-specific error so the caller knows it's a format-support issue,
// not a kind-detection issue.
var lower = function (part) {
    var mime = part.mediaType.toLowerCase();
    var imageFormat = IMAGE_FORMATS[mime];
    if (imageFormat)
        return effect_1.Effect.succeed(imageBlock(part, imageFormat));
    if (mime.startsWith("image/"))
        return shared_1.ProviderShared.invalidRequest("Bedrock Converse does not support image media type ".concat(part.mediaType));
    var documentFormat = DOCUMENT_FORMATS[mime];
    if (documentFormat)
        return effect_1.Effect.succeed(documentBlock(part, documentFormat));
    return shared_1.ProviderShared.invalidRequest("Bedrock Converse does not support media type ".concat(part.mediaType));
};
exports.lower = lower;
exports.BedrockMedia = require("./bedrock-media");
