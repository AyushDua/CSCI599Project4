#include <gtest/gtest.h>
#include <string>
#include <vector>
#include <cstdint>
#include <cstring>

extern "C" {
#include "codec.h"
}

// Tiny reference implementation used as an oracle in tests.
static std::string ref_hex(const std::vector<uint8_t>& in) {
  static const char* HEX = "0123456789abcdef";
  std::string out;
  out.reserve(in.size() * 2);
  for (uint8_t b : in) {
    out.push_back(HEX[(b >> 4) & 0xF]);
    out.push_back(HEX[b & 0xF]);
  }
  return out;
}

TEST(CodecHexEncode, EmptyInput) {
  char out[1] = {0};
  size_t out_len = 999;
  auto st = codec_hex_encode(nullptr, 0, out, 0, &out_len);
  EXPECT_EQ(st, CODEC_OK);
  EXPECT_EQ(out_len, 0u);
}

TEST(CodecHexEncode, BasicHi) {
  std::vector<uint8_t> in = {'h','i'};
  char out[64];
  size_t out_len = 0;

  auto st = codec_hex_encode(in.data(), in.size(), out, sizeof(out), &out_len);
  ASSERT_EQ(st, CODEC_OK);
  ASSERT_EQ(out_len, 4u);

  std::string got(out, out + out_len);
  EXPECT_EQ(got, "6869");
}

TEST(CodecHexEncode, SingleByte00) {
  std::vector<uint8_t> in = {0x00};
  char out[8];
  size_t out_len = 0;

  auto st = codec_hex_encode(in.data(), in.size(), out, sizeof(out), &out_len);
  ASSERT_EQ(st, CODEC_OK);
  EXPECT_EQ(std::string(out, out + out_len), "00");
}

TEST(CodecHexEncode, SingleByteFF) {
  std::vector<uint8_t> in = {0xFF};
  char out[8];
  size_t out_len = 0;

  auto st = codec_hex_encode(in.data(), in.size(), out, sizeof(out), &out_len);
  ASSERT_EQ(st, CODEC_OK);
  EXPECT_EQ(std::string(out, out + out_len), "ff");
}

TEST(CodecHexEncode, ContainsNullBytesNotCString) {
  std::vector<uint8_t> in = {0x00, 0x01, 0x00, 0x02};
  char out[64];
  size_t out_len = 0;

  auto st = codec_hex_encode(in.data(), in.size(), out, sizeof(out), &out_len);
  ASSERT_EQ(st, CODEC_OK);

  std::string got(out, out + out_len);
  EXPECT_EQ(got, "00010002");
}

// This test is important: it should FAIL if someone introduces an off-by-one bug
// or incorrect length accounting.
TEST(CodecHexEncode, OutLenMatchesExactly) {
  std::vector<uint8_t> in(16);
  for (size_t i = 0; i < in.size(); i++) in[i] = (uint8_t)i;

  char out[128];
  size_t out_len = 0;

  auto st = codec_hex_encode(in.data(), in.size(), out, sizeof(out), &out_len);
  ASSERT_EQ(st, CODEC_OK);
  EXPECT_EQ(out_len, codec_hex_encode_out_len(in.size()));

  std::string got(out, out + out_len);
  EXPECT_EQ(got, ref_hex(in));
}

TEST(CodecHexEncode, OutputExactlySizedBufferSucceeds) {
  std::vector<uint8_t> in = {0xAA, 0xBB};
  const size_t need = codec_hex_encode_out_len(in.size());
  std::vector<char> out(need);
  size_t out_len = 0;

  auto st = codec_hex_encode(in.data(), in.size(), out.data(), out.size(), &out_len);
  ASSERT_EQ(st, CODEC_OK);
  EXPECT_EQ(out_len, need);
  EXPECT_EQ(std::string(out.data(), out.data() + out_len), "aabb");
}

TEST(CodecHexEncode, OutputTooSmallReturnsErrorAndDoesNotWrite) {
  // This test is designed to catch a seeded bug where the size-check is removed.
  // Even without ASan, we can detect unintended writes using sentinels.
  std::vector<uint8_t> in = {0x01, 0x02};  // need 4 chars
  char out[3] = {'X','Y','Z'};
  size_t out_len = 123;

  auto st = codec_hex_encode(in.data(), in.size(), out, sizeof(out), &out_len);
  EXPECT_EQ(st, CODEC_ERR_OUTPUT_TOO_SMALL);
  EXPECT_EQ(out_len, 0u);
  EXPECT_EQ(out[0], 'X');
  EXPECT_EQ(out[1], 'Y');
  EXPECT_EQ(out[2], 'Z');
}

TEST(CodecHexEncode, NullOutLenIsError) {
  std::vector<uint8_t> in = {0x01};
  char out[8];
  auto st = codec_hex_encode(in.data(), in.size(), out, sizeof(out), nullptr);
  EXPECT_EQ(st, CODEC_ERR_NULL);
}

TEST(CodecHexEncode, NullInputWithPositiveLenIsError) {
  char out[8];
  size_t out_len = 0;
  auto st = codec_hex_encode(nullptr, 1, out, sizeof(out), &out_len);
  EXPECT_EQ(st, CODEC_ERR_NULL);
  EXPECT_EQ(out_len, 0u);
}

TEST(CodecHexEncode, NullOutputWithPositiveCapIsError) {
  std::vector<uint8_t> in = {0x01};
  size_t out_len = 0;
  auto st = codec_hex_encode(in.data(), in.size(), nullptr, 8, &out_len);
  EXPECT_EQ(st, CODEC_ERR_NULL);
  EXPECT_EQ(out_len, 0u);
}

TEST(CodecHexEncode, LargeInputMatchesReference) {
  // Another “bug catcher”: off-by-one loops or wrong indexing show up here.
  std::vector<uint8_t> in(1024);
  for (size_t i = 0; i < in.size(); i++) in[i] = (uint8_t)(i * 31u);

  std::vector<char> out(codec_hex_encode_out_len(in.size()));
  size_t out_len = 0;

  auto st = codec_hex_encode(in.data(), in.size(), out.data(), out.size(), &out_len);
  ASSERT_EQ(st, CODEC_OK);

  std::string got(out.data(), out.data() + out_len);
  EXPECT_EQ(got, ref_hex(in));
}

/*
 * Optional: intentional failing tests for demo.
 * These are DISABLED so they won't break normal runs.
 * Run them with: ./build/native/test_codec --gtest_also_run_disabled_tests
 */
TEST(CodecHexEncode, DISABLED_DemoIntentionalFail) {
  std::vector<uint8_t> in = {'h','i'};
  char out[64];
  size_t out_len = 0;
  auto st = codec_hex_encode(in.data(), in.size(), out, sizeof(out), &out_len);
  ASSERT_EQ(st, CODEC_OK);
  std::string got(out, out + out_len);
  EXPECT_EQ(got, "NOT_THE_RIGHT_HEX");
}