#include <stddef.h>
#include <stdint.h>
#include "codec.h"
#include "parser.h"
#include "stats.h"

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

/* ── Parser exports ─────────────────────────────────────────────────────── */

/* Extract the field at 0-based field_index from a CSV string.
   Returns field length (>= 0) or negative error code. */
EXPORT int parser_get_field_z(
    const char* in, int in_len,
    int field_index,
    char* out, int out_cap)
{
  if (!in || !out || in_len < 0 || out_cap <= 0 || field_index < 0)
    return -(int)PARSER_ERR_NULL;
  size_t pos = 0;
  size_t flen = 0;
  parser_status_t st;
  for (int i = 0; i <= field_index; i++) {
    st = csv_next_field(in, (size_t)in_len, &pos, out, (size_t)out_cap, &flen);
    if (st != PARSER_OK) return -(int)st;
  }
  return (int)flen;
}

/* Low-level wrapper that passes in_pos directly to csv_next_field.
   Passing in_pos=0 (null Wasm pointer) triggers Q003 on buggy builds. */
EXPORT int parser_next_field_raw_z(
    const char* in, int in_len,
    int* in_pos,
    char* out, int out_cap)
{
  size_t flen = 0;
  parser_status_t st = csv_next_field(
      in, (size_t)(in_len < 0 ? 0 : in_len),
      (size_t*)in_pos,
      out, (size_t)(out_cap < 0 ? 0 : out_cap),
      &flen);
  if (st != PARSER_OK) return -(int)st;
  return (int)flen;
}

/* Returns field count (>= 0) or negative error code. */
EXPORT int parser_count_fields_z(const char* in, int in_len)
{
  if (!in || in_len < 0) return -(int)PARSER_ERR_NULL;
  size_t count = 0;
  parser_status_t st = csv_count_fields(in, (size_t)in_len, &count);
  if (st != PARSER_OK) return -(int)st;
  return (int)count;
}

/* ── Stats exports ──────────────────────────────────────────────────────── */

/* Sum returned as double to avoid BigInt in JS (covers int64 range for tests). */
EXPORT double stats_sum_z(const int32_t* arr, int n)
{
  int64_t result = 0;
  stats_status_t st = stats_sum_i32(arr, (size_t)(n < 0 ? 0 : n), &result);
  if (st != STATS_OK) return -1e18;
  return (double)result;
}

/* Returns INT32_MIN sentinel (0x80000000) on error. */
EXPORT int stats_min_z(const int32_t* arr, int n)
{
  int32_t result = 0;
  stats_status_t st = stats_min_i32(arr, (size_t)(n < 0 ? 0 : n), &result);
  if (st != STATS_OK) return (int)0x80000000;
  return (int)result;
}

EXPORT int stats_max_z(const int32_t* arr, int n)
{
  int32_t result = 0;
  stats_status_t st = stats_max_i32(arr, (size_t)(n < 0 ? 0 : n), &result);
  if (st != STATS_OK) return (int)0x80000000;
  return (int)result;
}

EXPORT double stats_mean_z(const double* arr, int n)
{
  double result = 0.0;
  stats_status_t st = stats_mean_f64(arr, (size_t)(n < 0 ? 0 : n), &result);
  if (st != STATS_OK) return -1e18;
  return result;
}

EXPORT float stats_dot_z(const float* a, const float* b, int n)
{
  float result = 0.0f;
  stats_status_t st = stats_dot_f32(a, b, (size_t)(n < 0 ? 0 : n), &result);
  if (st != STATS_OK) return -1e18f;
  return result;
}