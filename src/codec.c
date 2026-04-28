#include "codec.h"

static const char HEX[] = "0123456789abcdef";

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

  if (CODEC_TRAP_BUG_B003 && in_len == 2 && in[0] == 'h' && in[1] == 'i') {
    __builtin_trap();
  }

  size_t encode_len = in_len;
  if (CODEC_LOOP_BUG_B001 && in_len > 0) {
    encode_len = in_len - 1;
  }

  for (size_t i = 0; i < encode_len; i++) {
    const uint8_t b = in[i];
    out[2*i]     = HEX[(b >> 4) & 0xF];
    out[2*i + 1] = HEX[b & 0xF];
  }

  if (CODEC_LOOP_BUG_B001 && in_len > 0) {
    out[need - 2] = '0';
    out[need - 1] = '0';
  }

  *out_len = need;
  return CODEC_OK;
}