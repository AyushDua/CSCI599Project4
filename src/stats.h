#pragma once
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
  STATS_OK = 0,
  STATS_ERR_NULL = 1,
  STATS_ERR_EMPTY = 2,
  STATS_ERR_OVERFLOW = 3
} stats_status_t;

/* Sum of n int32 values into an int64 accumulator (avoids overflow). */
stats_status_t stats_sum_i32(const int32_t* arr, size_t n, int64_t* out);

/* Minimum of n int32 values. */
stats_status_t stats_min_i32(const int32_t* arr, size_t n, int32_t* out);

/* Maximum of n int32 values. */
stats_status_t stats_max_i32(const int32_t* arr, size_t n, int32_t* out);

/* Arithmetic mean of n double values. */
stats_status_t stats_mean_f64(const double* arr, size_t n, double* out);

/* Dot product of two float arrays of length n. */
stats_status_t stats_dot_f32(const float* a, const float* b, size_t n, float* out);

/* Clamp each element of arr[0..n) to [lo, hi] in-place. */
stats_status_t stats_clamp_i32(int32_t* arr, size_t n, int32_t lo, int32_t hi);

#ifdef __cplusplus
}
#endif
