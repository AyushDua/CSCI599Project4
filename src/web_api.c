#include <stddef.h>
#include <stdint.h>
#include "codec.h"

#ifdef __EMSCRIPTEN__
#include <emscripten/emscripten.h>
#define EXPORT EMSCRIPTEN_KEEPALIVE
#else
#define EXPORT
#endif

EXPORT int codec_hex_encode_z(const uint8_t* in, size_t in_len, char* out, size_t out_cap) {
  if (out_cap == 0) return -(int)CODEC_ERR_OUTPUT_TOO_SMALL;

  size_t out_len = 0;
  codec_status_t st = codec_hex_encode(in, in_len, out, out_cap - 1, &out_len);
  if (st != CODEC_OK) return -(int)st;

  out[out_len] = '\0';
  return (int)out_len;
}