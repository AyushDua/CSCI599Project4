#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include "codec.h"

#if defined(__wasm__) || defined(__wasi__)
#define WASI_EXPORT __attribute__((visibility("default")))
#else
#define WASI_EXPORT
#endif

static int encode_bytes(
    const uint8_t* in,
    size_t in_len,
    char** out_ptr,
    size_t* out_len_ptr) {
  if (!out_ptr || !out_len_ptr) return 4;

  const size_t need = codec_hex_encode_out_len(in_len);
  const size_t alloc_size = need > 0 ? need : 1;
  char* out = (char*)malloc(alloc_size);
  if (!out) return 2;

  size_t out_len = 0;
  codec_status_t st = codec_hex_encode(in, in_len, out, need, &out_len);
  if (st != CODEC_OK) {
    free(out);
    return 10 + (int)st;
  }

  *out_ptr = out;
  *out_len_ptr = out_len;
  return 0;
}

static int compare_case(
    const uint8_t* in,
    size_t in_len,
    const char* expected,
    size_t expected_len) {
  char* out = NULL;
  size_t out_len = 0;
  const int rc = encode_bytes(in, in_len, &out, &out_len);
  if (rc != 0) return rc;

  const int ok = out_len == expected_len && memcmp(out, expected, expected_len) == 0;
  free(out);
  return ok ? 0 : 1;
}

/* Jimmy: Layer 2 invoke-mode markers live below. */
WASI_EXPORT int codec_wasi_invoke_case(int case_id) {
  switch (case_id) {
    case 0:
      return compare_case(NULL, 0, "", 0);

    case 1: {
      static const uint8_t hi[] = {'h', 'i'};
      return compare_case(hi, sizeof(hi), "6869", 4);
    }

    case 2: {
      static const uint8_t abc[] = {'A', 'B', 'C'};
      return compare_case(abc, sizeof(abc), "414243", 6);
    }

    case 3: {
      static const uint8_t bytes[] = {0x00, 0x01, 0x02, 0x7f, 0x80, 0xff};
      return compare_case(bytes, sizeof(bytes), "0001027f80ff", 12);
    }

    case 4: {
      uint8_t bytes[256];
      for (size_t i = 0; i < sizeof(bytes); i++) {
        bytes[i] = (uint8_t)i;
      }

      char expected[512];
      static const char HEX[] = "0123456789abcdef";
      for (size_t i = 0; i < sizeof(bytes); i++) {
        expected[2 * i] = HEX[(bytes[i] >> 4) & 0xF];
        expected[2 * i + 1] = HEX[bytes[i] & 0xF];
      }

      return compare_case(bytes, sizeof(bytes), expected, sizeof(expected));
    }

    default:
      return 64;
  }
}

/* Jimmy: Case-count export for the layer 2 Wasmtime harness. */
WASI_EXPORT int codec_wasi_case_count(void) {
  return 5;
}

int main(void) {
  uint8_t in[4096];
  const size_t n = fread(in, 1, sizeof(in), stdin);

  char* out = NULL;
  size_t out_len = 0;
  const int rc = encode_bytes(in, n, &out, &out_len);
  if (rc != 0) return rc;

  fwrite(out, 1, out_len, stdout);
  fputc('\n', stdout);
  free(out);
  return 0;
}