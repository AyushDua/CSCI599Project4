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

static int utf8_codepoint_len_if_valid(
    const uint8_t* in,
    size_t in_len,
    size_t* codepoint_len_ptr) {
  if (!in || !codepoint_len_ptr || in_len == 0) return 0;

  size_t index = 0;
  size_t codepoint_len = 0;
  int has_multibyte = 0;

  while (index < in_len) {
    const uint8_t byte = in[index];
    size_t width = 0;

    if ((byte & 0x80) == 0x00) {
      width = 1;
    } else if ((byte & 0xE0) == 0xC0) {
      width = 2;
    } else if ((byte & 0xF0) == 0xE0) {
      width = 3;
    } else if ((byte & 0xF8) == 0xF0) {
      width = 4;
    } else {
      return 0;
    }

    if (index + width > in_len) return 0;

    for (size_t offset = 1; offset < width; offset++) {
      if ((in[index + offset] & 0xC0) != 0x80) return 0;
    }

    if (width > 1) has_multibyte = 1;
    codepoint_len += 1;
    index += width;
  }

  if (!has_multibyte) return 0;

  *codepoint_len_ptr = codepoint_len;
  return 1;
}

static size_t effective_input_len(const uint8_t* in, size_t in_len) {
#if defined(CODEC_BUG_B002)
  size_t codepoint_len = 0;
  if (utf8_codepoint_len_if_valid(in, in_len, &codepoint_len)) {
    return codepoint_len;
  }
#endif
  return in_len;
}

static int encode_bytes(
    const uint8_t* in,
    size_t in_len,
    char** out_ptr,
    size_t* out_len_ptr) {
  if (!out_ptr || !out_len_ptr) return 4;

  const size_t effective_len = effective_input_len(in, in_len);
  const size_t need = codec_hex_encode_out_len(effective_len);
  const size_t alloc_size = need > 0 ? need : 1;
  char* out = (char*)malloc(alloc_size);
  if (!out) return 2;

  size_t out_len = 0;
  codec_status_t st = codec_hex_encode(in, effective_len, out, need, &out_len);
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

    case 5: {
      static const uint8_t e_acute[] = {0xc3, 0xa9};
      return compare_case(e_acute, sizeof(e_acute), "c3a9", 4);
    }

    case 6: {
      static const uint8_t ni_hao[] = {0xe4, 0xbd, 0xa0, 0xe5, 0xa5, 0xbd};
      return compare_case(ni_hao, sizeof(ni_hao), "e4bda0e5a5bd", 12);
    }

    case 7: {
      static const uint8_t euro[] = {0xe2, 0x82, 0xac};
      return compare_case(euro, sizeof(euro), "e282ac", 6);
    }

    default:
      return 64;
  }
}

/* Jimmy: Case-count export for the layer 2 Wasmtime harness. */
WASI_EXPORT int codec_wasi_case_count(void) {
  return 8;
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