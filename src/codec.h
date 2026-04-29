#pragma once
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
  CODEC_OK = 0,
  CODEC_ERR_NULL = 1,
  CODEC_ERR_OUTPUT_TOO_SMALL = 2
} codec_status_t;

/* ── Hex encoding ── */
size_t codec_hex_encode_out_len(size_t in_len);

codec_status_t codec_hex_encode(
    const uint8_t* in, size_t in_len,
    char* out, size_t out_cap,
    size_t* out_len);

/* ── Base64 encoding ── */
/* Returns the number of output bytes needed (includes padding, excludes NUL). */
size_t codec_base64_encode_out_len(size_t in_len);

codec_status_t codec_base64_encode(
    const uint8_t* in, size_t in_len,
    char* out, size_t out_cap,
    size_t* out_len);

/* ── UTF-8 utilities ── */
/*
 * Walk the UTF-8 byte sequence in[0..byte_count) and write the number of
 * Unicode codepoints (characters) into *codepoint_count_out.
 * Models the distinction between JS str.length (codepoints) and
 * TextEncoder.encode(str).length (bytes).
 */
codec_status_t codec_utf8_byte_len(
    const uint8_t* utf8_in, size_t byte_count,
    size_t* codepoint_count_out);

#ifdef __cplusplus
}
#endif