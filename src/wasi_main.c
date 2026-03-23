#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include "codec.h"

int main(void) {
  uint8_t in[4096];
  size_t n = fread(in, 1, sizeof(in), stdin);

  size_t need = codec_hex_encode_out_len(n);
  char* out = (char*)malloc(need);
  if (!out) return 2;

  size_t out_len = 0;
  codec_status_t st = codec_hex_encode(in, n, out, need, &out_len);
  if (st != CODEC_OK) {
    free(out);
    return 3;
  }

  fwrite(out, 1, out_len, stdout);
  fputc('\n', stdout);
  free(out);
  return 0;
}