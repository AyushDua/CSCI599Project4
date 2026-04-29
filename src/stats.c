#include "stats.h"
#include <stdint.h>
#include <stddef.h>

/* ── Bug flags ── */
#if defined(STATS_BUG_S001)
/* Logic: stats_sum_i32 accumulates into int32_t instead of int64_t —
   silently overflows for large inputs. */
#define STATS_S001_INT32_ACCUM 1
#else
#define STATS_S001_INT32_ACCUM 0
#endif

#if defined(STATS_BUG_S002)
/* Boundary: stats_mean_f64 divides by (n-1) instead of n — sample mean
   instead of population mean, off by one element. */
#define STATS_S002_SAMPLE_MEAN 1
#else
#define STATS_S002_SAMPLE_MEAN 0
#endif

#if defined(STATS_BUG_S003)
/* Trap: stats_min_i32 missing null check on arr — dereferences null for n>0. */
#define STATS_S003_NULL_DEREF 1
#else
#define STATS_S003_NULL_DEREF 0
#endif

#if defined(STATS_BUG_S004)
/* Runtime-dependent: stats_dot_f32 only processes first n/2 elements
   (integer division), silently dropping the tail. */
#define STATS_S004_TRUNCATED_LOOP 1
#else
#define STATS_S004_TRUNCATED_LOOP 0
#endif

/* ── Implementation ── */

stats_status_t stats_sum_i32(const int32_t* arr, size_t n, int64_t* out) {
  if (!arr || !out) return STATS_ERR_NULL;
  if (n == 0) return STATS_ERR_EMPTY;

#if STATS_S001_INT32_ACCUM
  int32_t acc = 0;
  for (size_t i = 0; i < n; i++) acc += arr[i];
  *out = (int64_t)acc;
#else
  int64_t acc = 0;
  for (size_t i = 0; i < n; i++) acc += (int64_t)arr[i];
  *out = acc;
#endif
  return STATS_OK;
}

stats_status_t stats_min_i32(const int32_t* arr, size_t n, int32_t* out) {
  if (!out) return STATS_ERR_NULL;
  if (n == 0) return STATS_ERR_EMPTY;

#if STATS_S003_NULL_DEREF
  /* Bug S003: skip null check on arr */
  (void)0;
#else
  if (!arr) return STATS_ERR_NULL;
#endif

  int32_t m = arr[0];
  for (size_t i = 1; i < n; i++) {
    if (arr[i] < m) m = arr[i];
  }
  *out = m;
  return STATS_OK;
}

stats_status_t stats_max_i32(const int32_t* arr, size_t n, int32_t* out) {
  if (!arr || !out) return STATS_ERR_NULL;
  if (n == 0) return STATS_ERR_EMPTY;

  int32_t m = arr[0];
  for (size_t i = 1; i < n; i++) {
    if (arr[i] > m) m = arr[i];
  }
  *out = m;
  return STATS_OK;
}

stats_status_t stats_mean_f64(const double* arr, size_t n, double* out) {
  if (!arr || !out) return STATS_ERR_NULL;
  if (n == 0) return STATS_ERR_EMPTY;

  double sum = 0.0;
  for (size_t i = 0; i < n; i++) sum += arr[i];

#if STATS_S002_SAMPLE_MEAN
  *out = sum / (double)(n - 1);
#else
  *out = sum / (double)n;
#endif
  return STATS_OK;
}

stats_status_t stats_dot_f32(const float* a, const float* b, size_t n, float* out) {
  if (!a || !b || !out) return STATS_ERR_NULL;
  if (n == 0) return STATS_ERR_EMPTY;

  float acc = 0.0f;
#if STATS_S004_TRUNCATED_LOOP
  size_t count = n / 2;  /* Bug S004: processes only half the elements */
#else
  size_t count = n;
#endif
  for (size_t i = 0; i < count; i++) acc += a[i] * b[i];
  *out = acc;
  return STATS_OK;
}

stats_status_t stats_clamp_i32(int32_t* arr, size_t n, int32_t lo, int32_t hi) {
  if (!arr) return STATS_ERR_NULL;
  for (size_t i = 0; i < n; i++) {
    if (arr[i] < lo) arr[i] = lo;
    else if (arr[i] > hi) arr[i] = hi;
  }
  return STATS_OK;
}
