#include "codec.h"
#include <string.h>

/* ════════════════════════════════════════════════
   Hex lookup table — B004 flips to uppercase
   ════════════════════════════════════════════════ */
#if defined(CODEC_BUG_B004)
static const char HEX[] = "0123456789ABCDEF";
#else
static const char HEX[] = "0123456789abcdef";
#endif

/* ── Legacy bug-flag macros (kept for backward compat) ── */
#if defined(CODEC_BUG_B001)
#define CODEC_LOOP_BUG_B001 1
#else
#define CODEC_LOOP_BUG_B001 0
#endif

#if defined(CODEC_BUG_B003)
#define CODEC_TRAP_BUG_B003 1
#else
#define CODEC_TRAP_BUG_B003 0
#endif

/* ════════════════════════════════════════════════
   Hex encoding
   ════════════════════════════════════════════════ */

size_t codec_hex_encode_out_len(size_t in_len) {
  return in_len * 2;
}

codec_status_t codec_hex_encode(
    const uint8_t* in, size_t in_len,
    char* out, size_t out_cap,
    size_t* out_len)
{
  if (!out_len) return CODEC_ERR_NULL;
  *out_len = 0;

  if (!in && in_len > 0) return CODEC_ERR_NULL;
  if (!out && out_cap > 0) return CODEC_ERR_NULL;

  const size_t need = codec_hex_encode_out_len(in_len);
  if (out_cap < need) return CODEC_ERR_OUTPUT_TOO_SMALL;

  if (CODEC_TRAP_BUG_B003 && in_len == 2 && in[0] == 'h' && in[1] == 'i') {
    __builtin_trap();
  }

#if defined(CODEC_BUG_B006)
  /* Bug B006: always-zero output — correct length, all-'0' content */
  memset(out, '0', need);
  *out_len = need;
  return CODEC_OK;
#endif

  size_t encode_len = in_len;
  if (CODEC_LOOP_BUG_B001 && in_len > 0) {
    encode_len = in_len - 1;
  }

  for (size_t i = 0; i < encode_len; i++) {
    const uint8_t b = in[i];
#if defined(CODEC_BUG_B005)
    /* Bug B005: nibble swap — low nibble first */
    out[2*i]     = HEX[b & 0xF];
    out[2*i + 1] = HEX[(b >> 4) & 0xF];
#else
    out[2*i]     = HEX[(b >> 4) & 0xF];
    out[2*i + 1] = HEX[b & 0xF];
#endif
  }

  if (CODEC_LOOP_BUG_B001 && in_len > 0) {
    out[need - 2] = '0';
    out[need - 1] = '0';
  }

  *out_len = need;
  return CODEC_OK;
}

/* ════════════════════════════════════════════════
   Base64 encoding
   ════════════════════════════════════════════════ */

static const char B64[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

size_t codec_base64_encode_out_len(size_t in_len) {
#if defined(CODEC_BUG_B007)
  /* Bug B007: off-by-one — reports one byte less than needed */
  if (in_len == 0) return 0;
  return ((in_len + 2) / 3) * 4 - 1;
#else
  if (in_len == 0) return 0;
  return ((in_len + 2) / 3) * 4;
#endif
}

codec_status_t codec_base64_encode(
    const uint8_t* in, size_t in_len,
    char* out, size_t out_cap,
    size_t* out_len)
{
  if (!out_len) return CODEC_ERR_NULL;
  *out_len = 0;

  if (!in && in_len > 0) return CODEC_ERR_NULL;
  if (!out && out_cap > 0) return CODEC_ERR_NULL;

  /* Use the (potentially buggy) out-len helper for the capacity check so
     that B007 also triggers CODEC_ERR_OUTPUT_TOO_SMALL in tests that call
     codec_base64_encode with an exactly-sized buffer. */
  const size_t need = codec_base64_encode_out_len(in_len);
  if (out_cap < need) return CODEC_ERR_OUTPUT_TOO_SMALL;

  size_t wi = 0;
  size_t i = 0;

  while (i + 3 <= in_len) {
    uint32_t grp = ((uint32_t)in[i] << 16) |
                   ((uint32_t)in[i+1] << 8) |
                   (uint32_t)in[i+2];
    out[wi++] = B64[(grp >> 18) & 0x3F];
    out[wi++] = B64[(grp >> 12) & 0x3F];
    out[wi++] = B64[(grp >>  6) & 0x3F];
    out[wi++] = B64[ grp        & 0x3F];
    i += 3;
  }

  if (i + 1 == in_len) {
    uint32_t grp = (uint32_t)in[i] << 16;
    out[wi++] = B64[(grp >> 18) & 0x3F];
    out[wi++] = B64[(grp >> 12) & 0x3F];
    out[wi++] = '=';
    out[wi++] = '=';
  } else if (i + 2 == in_len) {
    uint32_t grp = ((uint32_t)in[i] << 16) | ((uint32_t)in[i+1] << 8);
    out[wi++] = B64[(grp >> 18) & 0x3F];
    out[wi++] = B64[(grp >> 12) & 0x3F];
    out[wi++] = B64[(grp >>  6) & 0x3F];
    out[wi++] = '=';
  }

  *out_len = wi;
  return CODEC_OK;
}

/* ════════════════════════════════════════════════
   UTF-8 utilities
   ════════════════════════════════════════════════ */

codec_status_t codec_utf8_byte_len(
    const uint8_t* utf8_in, size_t byte_count,
    size_t* codepoint_count_out)
{
  if (!codepoint_count_out) return CODEC_ERR_NULL;
  if (!utf8_in && byte_count > 0) return CODEC_ERR_NULL;

  size_t cp = 0;
  size_t i = 0;

  while (i < byte_count) {
    uint8_t b = utf8_in[i];
    size_t width;
    if      ((b & 0x80) == 0x00) width = 1;  /* 0xxxxxxx — ASCII */
    else if ((b & 0xE0) == 0xC0) width = 2;  /* 110xxxxx */
    else if ((b & 0xF0) == 0xE0) width = 3;  /* 1110xxxx */
    else if ((b & 0xF8) == 0xF0) width = 4;  /* 11110xxx */
    else                          width = 1;  /* continuation / invalid: skip one */

#if defined(CODEC_BUG_B008)
    /* Bug B008: counts bytes consumed instead of codepoints — the exact JS
       str.length vs TextEncoder.encode(str).length confusion. */
    cp += width;
#else
    cp += 1;
#endif
    i += width;
  }

  *codepoint_count_out = cp;
  return CODEC_OK;
}
