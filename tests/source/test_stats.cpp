#include <gtest/gtest.h>
#include <cstdint>
#include <climits>
#include <cmath>

extern "C" {
#include "stats.h"
}

// ════════════════════════════════════════════════════════════════════════════
// Suite: StatsSum — Logic / integer-overflow tests
// ════════════════════════════════════════════════════════════════════════════

TEST(StatsSum, BasicSum) {
  const int32_t arr[] = {1, 2, 3};
  int64_t out = 0;
  ASSERT_EQ(stats_sum_i32(arr, 3, &out), STATS_OK);
  EXPECT_EQ(out, 6);
}

TEST(StatsSum, NegativeValues) {
  const int32_t arr[] = {-1, -2, 3};
  int64_t out = 0;
  ASSERT_EQ(stats_sum_i32(arr, 3, &out), STATS_OK);
  EXPECT_EQ(out, 0);
}

TEST(StatsSum, EmptyArray) {
  const int32_t arr[] = {1};
  int64_t out = 0;
  EXPECT_EQ(stats_sum_i32(arr, 0, &out), STATS_ERR_EMPTY);
}

TEST(StatsSum, NullArray) {
  int64_t out = 0;
  EXPECT_EQ(stats_sum_i32(nullptr, 3, &out), STATS_ERR_NULL);
}

TEST(StatsSum, S001_Int32Overflow) {
  // INT32_MAX + 1 overflows int32 but fits in int64.
  // Under S001 (int32 accumulator) the result wraps to a negative value.
  const int32_t arr[] = {INT32_MAX, 1};
  int64_t out = 0;
  ASSERT_EQ(stats_sum_i32(arr, 2, &out), STATS_OK);
  EXPECT_EQ(out, (int64_t)INT32_MAX + 1)
      << "int32 overflow in accumulator (S001?)";
}

// ════════════════════════════════════════════════════════════════════════════
// Suite: StatsMinMax — Boundary / runtime-dependent tests
// ════════════════════════════════════════════════════════════════════════════

TEST(StatsMinMax, MinBasic) {
  const int32_t arr[] = {3, 1, 2};
  int32_t out = 0;
  ASSERT_EQ(stats_min_i32(arr, 3, &out), STATS_OK);
  EXPECT_EQ(out, 1);
}

TEST(StatsMinMax, MaxBasic) {
  const int32_t arr[] = {3, 1, 2};
  int32_t out = 0;
  ASSERT_EQ(stats_max_i32(arr, 3, &out), STATS_OK);
  EXPECT_EQ(out, 3);
}

TEST(StatsMinMax, SingleElement) {
  const int32_t arr[] = {42};
  int32_t mn = 0, mx = 0;
  ASSERT_EQ(stats_min_i32(arr, 1, &mn), STATS_OK);
  ASSERT_EQ(stats_max_i32(arr, 1, &mx), STATS_OK);
  EXPECT_EQ(mn, 42);
  EXPECT_EQ(mx, 42);
}

TEST(StatsMinMax, AllSameValue) {
  const int32_t arr[] = {5, 5, 5, 5};
  int32_t mn = 0, mx = 0;
  ASSERT_EQ(stats_min_i32(arr, 4, &mn), STATS_OK);
  ASSERT_EQ(stats_max_i32(arr, 4, &mx), STATS_OK);
  EXPECT_EQ(mn, 5);
  EXPECT_EQ(mx, 5);
}

TEST(StatsMinMax, S003_NullDeref) {
  // Under S003, stats_min_i32 skips the null check and dereferences arr.
  // On clean build it must return STATS_ERR_NULL without crashing.
  int32_t out = 0;
  auto st = stats_min_i32(nullptr, 1, &out);
  EXPECT_EQ(st, STATS_ERR_NULL);
}

TEST(StatsMinMax, MinMaxBothExtremes) {
  const int32_t arr[] = {INT32_MIN, INT32_MAX};
  int32_t mn = 0, mx = 0;
  ASSERT_EQ(stats_min_i32(arr, 2, &mn), STATS_OK);
  ASSERT_EQ(stats_max_i32(arr, 2, &mx), STATS_OK);
  EXPECT_EQ(mn, INT32_MIN);
  EXPECT_EQ(mx, INT32_MAX);
}

// ════════════════════════════════════════════════════════════════════════════
// Suite: StatsMean — Logic / marshaling tests
// ════════════════════════════════════════════════════════════════════════════

TEST(StatsMean, MeanInteger) {
  const double arr[] = {1.0, 2.0, 3.0};
  double out = 0.0;
  ASSERT_EQ(stats_mean_f64(arr, 3, &out), STATS_OK);
  EXPECT_DOUBLE_EQ(out, 2.0);
}

TEST(StatsMean, MeanFractional) {
  const double arr[] = {1.0, 2.0};
  double out = 0.0;
  ASSERT_EQ(stats_mean_f64(arr, 2, &out), STATS_OK);
  EXPECT_DOUBLE_EQ(out, 1.5);
}

TEST(StatsMean, MeanSingleElement) {
  const double arr[] = {7.0};
  double out = 0.0;
  ASSERT_EQ(stats_mean_f64(arr, 1, &out), STATS_OK);
  EXPECT_DOUBLE_EQ(out, 7.0);
}

TEST(StatsMean, MeanEmpty) {
  const double arr[] = {1.0};
  double out = 0.0;
  EXPECT_EQ(stats_mean_f64(arr, 0, &out), STATS_ERR_EMPTY);
}

TEST(StatsMean, S002_SampleVsPopulation) {
  // Population mean of {1,2,3} = 2.0; sample mean (n-1 divisor) = 3.0.
  // Under S002 the result is 3.0 (wrong).
  const double arr[] = {1.0, 2.0, 3.0};
  double out = 0.0;
  ASSERT_EQ(stats_mean_f64(arr, 3, &out), STATS_OK);
  EXPECT_DOUBLE_EQ(out, 2.0) << "mean wrong (S002 — dividing by n-1 instead of n?)";
}

// ════════════════════════════════════════════════════════════════════════════
// Suite: StatsDotProduct — Runtime-dependent tests
// ════════════════════════════════════════════════════════════════════════════

TEST(StatsDotProduct, DotBasic) {
  // {1,2} · {3,4} = 3 + 8 = 11
  const float a[] = {1.0f, 2.0f};
  const float b[] = {3.0f, 4.0f};
  float out = 0.0f;
  ASSERT_EQ(stats_dot_f32(a, b, 2, &out), STATS_OK);
  EXPECT_FLOAT_EQ(out, 11.0f);
}

TEST(StatsDotProduct, DotWithZero) {
  const float a[] = {5.0f, 7.0f, 3.0f};
  const float b[] = {0.0f, 0.0f, 0.0f};
  float out = 99.0f;
  ASSERT_EQ(stats_dot_f32(a, b, 3, &out), STATS_OK);
  EXPECT_FLOAT_EQ(out, 0.0f);
}

TEST(StatsDotProduct, DotSingleElement) {
  const float a[] = {2.0f};
  const float b[] = {3.0f};
  float out = 0.0f;
  ASSERT_EQ(stats_dot_f32(a, b, 1, &out), STATS_OK);
  EXPECT_FLOAT_EQ(out, 6.0f);
}

TEST(StatsDotProduct, S004_TruncatedDotProduct) {
  // {1,2,3,4} · {1,1,1,1} = 10.
  // Under S004, only n/2 = 2 elements are processed → 1+2 = 3 (wrong).
  const float a[] = {1.0f, 2.0f, 3.0f, 4.0f};
  const float b[] = {1.0f, 1.0f, 1.0f, 1.0f};
  float out = 0.0f;
  ASSERT_EQ(stats_dot_f32(a, b, 4, &out), STATS_OK);
  EXPECT_FLOAT_EQ(out, 10.0f) << "dot product truncated (S004 — processing only n/2 elements?)";
}

TEST(StatsDotProduct, DotNullPointer) {
  const float b[] = {1.0f};
  float out = 0.0f;
  EXPECT_EQ(stats_dot_f32(nullptr, b, 1, &out), STATS_ERR_NULL);
}

// ════════════════════════════════════════════════════════════════════════════
// Suite: StatsClamp — In-place / Boundary tests
// ════════════════════════════════════════════════════════════════════════════

TEST(StatsClamp, ClampBasic) {
  int32_t arr[] = {-5, 3, 15};
  ASSERT_EQ(stats_clamp_i32(arr, 3, 0, 10), STATS_OK);
  EXPECT_EQ(arr[0], 0);
  EXPECT_EQ(arr[1], 3);
  EXPECT_EQ(arr[2], 10);
}

TEST(StatsClamp, ClampAllInRange) {
  int32_t arr[] = {2, 5, 8};
  ASSERT_EQ(stats_clamp_i32(arr, 3, 0, 10), STATS_OK);
  EXPECT_EQ(arr[0], 2);
  EXPECT_EQ(arr[1], 5);
  EXPECT_EQ(arr[2], 8);
}

TEST(StatsClamp, ClampSameLoHi) {
  // lo == hi: every element becomes that value
  int32_t arr[] = {-100, 0, 100};
  ASSERT_EQ(stats_clamp_i32(arr, 3, 7, 7), STATS_OK);
  EXPECT_EQ(arr[0], 7);
  EXPECT_EQ(arr[1], 7);
  EXPECT_EQ(arr[2], 7);
}

TEST(StatsClamp, ClampNullArray) {
  EXPECT_EQ(stats_clamp_i32(nullptr, 3, 0, 10), STATS_ERR_NULL);
}
