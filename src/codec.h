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

size_t codec_hex_encode_out_len(size_t in_len);

codec_status_t codec_hex_encode(
    const uint8_t* in, size_t in_len,
    char* out, size_t out_cap,
    size_t* out_len);

#ifdef __cplusplus
}
#endif