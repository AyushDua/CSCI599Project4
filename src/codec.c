#include "codec.h"

static const char HEX[] = "0123456789abcdef";

size_t codec_hex_encode_out_len(size_t in_len) {
  return in_len * 2;
}

codec_status_t codec_hex_encode(
    const uint8_t* in, size_t in_len,
    char* out, size_t out_cap,
    size_t* out_len) {

  if (!out_len) return CODEC_ERR_NULL;
  *out_len = 0;

  if (!in && in_len > 0) return CODEC_ERR_NULL;
  if (!out && out_cap > 0) return CODEC_ERR_NULL;

  const size_t need = codec_hex_encode_out_len(in_len);
  if (out_cap < need) return CODEC_ERR_OUTPUT_TOO_SMALL;

  for (size_t i = 0; i < in_len; i++) {
    const uint8_t b = in[i];
    out[2*i]     = HEX[(b >> 4) & 0xF];
    out[2*i + 1] = HEX[b & 0xF];
  }

  *out_len = need;
  return CODEC_OK;
}