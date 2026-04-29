#include <gtest/gtest.h>
#include <string>
#include <vector>
#include <cstdint>
#include <cstring>
#include <algorithm>
#include <climits>

extern "C" {
#include "codec.h"
}

// ─── Reference oracle (hex) ──────────────────────────────────────────────────
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

// ─── Reference oracle (base64) ───────────────────────────────────────────────
static std::string ref_base64(const std::vector<uint8_t>& in) {
  static const char* B64 =
      "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  std::string out;
  size_t i = 0;
  while (i + 3 <= in.size()) {
    uint32_t g = ((uint32_t)in[i]<<16)|((uint32_t)in[i+1]<<8)|(uint32_t)in[i+2];
    out += B64[(g>>18)&0x3F];
    out += B64[(g>>12)&0x3F];
    out += B64[(g>> 6)&0x3F];
    out += B64[ g     &0x3F];
    i += 3;
  }
  if (i + 1 == in.size()) {
    uint32_t g = (uint32_t)in[i]<<16;
    out += B64[(g>>18)&0x3F]; out += B64[(g>>12)&0x3F];
    out += '='; out += '=';
  } else if (i + 2 == in.size()) {
    uint32_t g = ((uint32_t)in[i]<<16)|((uint32_t)in[i+1]<<8);
    out += B64[(g>>18)&0x3F]; out += B64[(g>>12)&0x3F];
    out += B64[(g>> 6)&0x3F]; out += '=';
  }
  return out;
}

// ════════════════════════════════════════════════════════════════════════════
// Suite: CodecHexEncodeOutLen  — unit-test the helper function
// Category: Logic
// ════════════════════════════════════════════════════════════════════════════

TEST(CodecHexEncodeOutLen, ZeroLen) {
  EXPECT_EQ(codec_hex_encode_out_len(0), 0u);
}

TEST(CodecHexEncodeOutLen, SingleByte) {
  EXPECT_EQ(codec_hex_encode_out_len(1), 2u);
}

TEST(CodecHexEncodeOutLen, LargeValue) {
  EXPECT_EQ(codec_hex_encode_out_len(65536), 131072u);
}

// ════════════════════════════════════════════════════════════════════════════
// Suite: CodecHexEncode — original 12 tests + 14 new ones
// ════════════════════════════════════════════════════════════════════════════

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
  EXPECT_EQ(std::string(out, out + out_len), "6869");
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
  EXPECT_EQ(std::string(out, out + out_len), "00010002");
}

TEST(CodecHexEncode, OutLenMatchesExactly) {
  std::vector<uint8_t> in(16);
  for (size_t i = 0; i < in.size(); i++) in[i] = (uint8_t)i;
  char out[128];
  size_t out_len = 0;
  auto st = codec_hex_encode(in.data(), in.size(), out, sizeof(out), &out_len);
  ASSERT_EQ(st, CODEC_OK);
  EXPECT_EQ(out_len, codec_hex_encode_out_len(in.size()));
  EXPECT_EQ(std::string(out, out + out_len), ref_hex(in));
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
  std::vector<uint8_t> in = {0x01, 0x02};
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
  std::vector<uint8_t> in(1024);
  for (size_t i = 0; i < in.size(); i++) in[i] = (uint8_t)(i * 31u);
  std::vector<char> out(codec_hex_encode_out_len(in.size()));
  size_t out_len = 0;
  auto st = codec_hex_encode(in.data(), in.size(), out.data(), out.size(), &out_len);
  ASSERT_EQ(st, CODEC_OK);
  EXPECT_EQ(std::string(out.data(), out.data() + out_len), ref_hex(in));
}

// ── New positive cases (Logic / Boundary) ──────────────────────────────────

TEST(CodecHexEncode, TwoByteInput) {
  std::vector<uint8_t> in = {0x01, 0x02};
  char out[8]; size_t out_len = 0;
  ASSERT_EQ(codec_hex_encode(in.data(), in.size(), out, sizeof(out), &out_len), CODEC_OK);
  EXPECT_EQ(std::string(out, out + out_len), "0102");
}

TEST(CodecHexEncode, ThreeByteInput) {
  // Last byte must not be corrupted to "00" — catches B001
  std::vector<uint8_t> in = {0xDE, 0xAD, 0xBE};
  char out[8]; size_t out_len = 0;
  ASSERT_EQ(codec_hex_encode(in.data(), in.size(), out, sizeof(out), &out_len), CODEC_OK);
  EXPECT_EQ(std::string(out, out + out_len), "deadbe");
}

TEST(CodecHexEncode, AllZeroBytes) {
  std::vector<uint8_t> in(8, 0x00);
  char out[32]; size_t out_len = 0;
  ASSERT_EQ(codec_hex_encode(in.data(), in.size(), out, sizeof(out), &out_len), CODEC_OK);
  EXPECT_EQ(std::string(out, out + out_len), "0000000000000000");
}

TEST(CodecHexEncode, AllFFBytes) {
  // High nibble values — catches B004 (uppercase) and B005 (nibble swap)
  std::vector<uint8_t> in(4, 0xFF);
  char out[16]; size_t out_len = 0;
  ASSERT_EQ(codec_hex_encode(in.data(), in.size(), out, sizeof(out), &out_len), CODEC_OK);
  EXPECT_EQ(std::string(out, out + out_len), "ffffffff");
}

TEST(CodecHexEncode, FullByteRamp) {
  // All 256 byte values — exercises every nibble pair; catches B004/B005/B006
  std::vector<uint8_t> in(256);
  for (int i = 0; i < 256; i++) in[i] = (uint8_t)i;
  std::vector<char> out(codec_hex_encode_out_len(in.size()));
  size_t out_len = 0;
  ASSERT_EQ(codec_hex_encode(in.data(), in.size(), out.data(), out.size(), &out_len), CODEC_OK);
  EXPECT_EQ(std::string(out.data(), out.data() + out_len), ref_hex(in));
}

TEST(CodecHexEncode, AsciiDigitsInput) {
  std::vector<uint8_t> in = {'0','1','2','3','4','5','6','7','8','9'};
  char out[32]; size_t out_len = 0;
  ASSERT_EQ(codec_hex_encode(in.data(), in.size(), out, sizeof(out), &out_len), CODEC_OK);
  EXPECT_EQ(std::string(out, out + out_len), "30313233343536373839");
}

TEST(CodecHexEncode, OutputLenAlwaysDoubleInputLen) {
  // Loop over sizes 1-20: out_len must equal in_len * 2 every time
  for (size_t n = 1; n <= 20; n++) {
    std::vector<uint8_t> in(n, (uint8_t)(n * 7));
    std::vector<char> out(n * 2);
    size_t out_len = 0;
    ASSERT_EQ(codec_hex_encode(in.data(), n, out.data(), out.size(), &out_len), CODEC_OK)
        << "n=" << n;
    EXPECT_EQ(out_len, n * 2) << "n=" << n;
  }
}

TEST(CodecHexEncode, PowerOfTwoSizes) {
  for (size_t n : {2u, 4u, 8u, 16u, 32u, 64u}) {
    std::vector<uint8_t> in(n);
    for (size_t i = 0; i < n; i++) in[i] = (uint8_t)(i * 13 + 7);
    std::vector<char> out(n * 2);
    size_t out_len = 0;
    ASSERT_EQ(codec_hex_encode(in.data(), n, out.data(), out.size(), &out_len), CODEC_OK)
        << "n=" << n;
    EXPECT_EQ(std::string(out.data(), out.data() + out_len), ref_hex(in)) << "n=" << n;
  }
}

// ── New negative / boundary cases ──────────────────────────────────────────

TEST(CodecHexEncode, OutCapZeroWithNonNullOut) {
  // Empty input with zero-cap out but non-null pointers — valid call
  char out_buf[1] = {0};
  size_t out_len = 999;
  auto st = codec_hex_encode(nullptr, 0, out_buf, 0, &out_len);
  EXPECT_EQ(st, CODEC_OK);
  EXPECT_EQ(out_len, 0u);
}

TEST(CodecHexEncode, OutCapOneForTwoByteInput) {
  std::vector<uint8_t> in = {0x01, 0x02};
  char out[8]; size_t out_len = 0;
  auto st = codec_hex_encode(in.data(), in.size(), out, 1, &out_len);
  EXPECT_EQ(st, CODEC_ERR_OUTPUT_TOO_SMALL);
}

TEST(CodecHexEncode, OutCapNeedMinusOne) {
  std::vector<uint8_t> in(8, 0xAB);
  char out[20]; size_t out_len = 0;
  // need = 16, provide 15
  auto st = codec_hex_encode(in.data(), in.size(), out, 15, &out_len);
  EXPECT_EQ(st, CODEC_ERR_OUTPUT_TOO_SMALL);
}

TEST(CodecHexEncode, NullInputNullOutputZeroLen) {
  // Both null with zero lengths — API allows this as empty encode
  size_t out_len = 123;
  auto st = codec_hex_encode(nullptr, 0, nullptr, 0, &out_len);
  EXPECT_EQ(st, CODEC_OK);
  EXPECT_EQ(out_len, 0u);
}

TEST(CodecHexEncode, NullOutputZeroCapZeroLen) {
  // Non-null input, zero in_len, null output — nothing to encode, nothing to write
  std::vector<uint8_t> in = {0xAB};
  size_t out_len = 123;
  auto st = codec_hex_encode(in.data(), 0, nullptr, 0, &out_len);
  EXPECT_EQ(st, CODEC_OK);
  EXPECT_EQ(out_len, 0u);
}

TEST(CodecHexEncode, SentinelAfterTooSmallIsPreserved) {
  // 3-byte input needs 6 chars; out[5]='Z' sentinel must survive
  std::vector<uint8_t> in = {0x01, 0x02, 0x03};
  char out[7] = {'?','?','?','?','?','Z','\0'};
  size_t out_len = 0;
  auto st = codec_hex_encode(in.data(), in.size(), out, 5, &out_len);
  EXPECT_EQ(st, CODEC_ERR_OUTPUT_TOO_SMALL);
  EXPECT_EQ(out[5], 'Z');  // sentinel intact
}

// ════════════════════════════════════════════════════════════════════════════
// Suite: CodecHexEncodeBugDetectors — targeted canary tests
// These fail when the binary is built with the corresponding -DCODEC_BUG_Bxxx
// ════════════════════════════════════════════════════════════════════════════

TEST(CodecHexEncodeBugDetectors, B001_LastByteIsNotZero) {
  // B001 overwrites the last two output chars with "00"
  std::vector<uint8_t> in = {0x01, 0x02, 0xAB};
  char out[8]; size_t out_len = 0;
  ASSERT_EQ(codec_hex_encode(in.data(), in.size(), out, sizeof(out), &out_len), CODEC_OK);
  std::string got(out, out + out_len);
  EXPECT_EQ(got.substr(4), "ab") << "last byte corrupted (B001?)";
}

TEST(CodecHexEncodeBugDetectors, B001_AllInputBytesAppearInOutput) {
  std::vector<uint8_t> in(16);
  for (size_t i = 0; i < 16; i++) in[i] = (uint8_t)(i + 1);
  std::vector<char> out(32); size_t out_len = 0;
  ASSERT_EQ(codec_hex_encode(in.data(), in.size(), out.data(), out.size(), &out_len), CODEC_OK);
  EXPECT_EQ(std::string(out.data(), out.data() + out_len), ref_hex(in));
}

TEST(CodecHexEncodeBugDetectors, B001_OutputLenIsCorrectEvenWithBug) {
  // B001 still returns CODEC_OK and correct out_len, but corrupts content
  std::vector<uint8_t> in = {0xDE, 0xAD, 0xBE, 0xEF};
  std::vector<char> out(8); size_t out_len = 0;
  ASSERT_EQ(codec_hex_encode(in.data(), in.size(), out.data(), out.size(), &out_len), CODEC_OK);
  EXPECT_EQ(std::string(out.data(), out.data() + out_len), "deadbeef");
}

TEST(CodecHexEncodeBugDetectors, B003_SizeCheckEnforcedForExactTrigger) {
  // B003 removes the size check — with out_cap too small it would trap
  std::vector<uint8_t> in = {'h','i'};
  char out[8]; size_t out_len = 0;
  auto st = codec_hex_encode(in.data(), in.size(), out, 3, &out_len);
  EXPECT_EQ(st, CODEC_ERR_OUTPUT_TOO_SMALL);
}

TEST(CodecHexEncodeBugDetectors, B003_NoTrapOnExactTriggerWithGoodBuffer) {
  std::vector<uint8_t> in = {'h','i'};
  char out[8]; size_t out_len = 0;
  ASSERT_EQ(codec_hex_encode(in.data(), in.size(), out, 4, &out_len), CODEC_OK);
  EXPECT_EQ(std::string(out, out + out_len), "6869");
}

// ════════════════════════════════════════════════════════════════════════════
// Suite: CodecHexEncodeParam — parametric tests
// ════════════════════════════════════════════════════════════════════════════

using HexParam = std::pair<std::vector<uint8_t>, std::string>;

class CodecHexEncodeParam : public testing::TestWithParam<HexParam> {};

TEST_P(CodecHexEncodeParam, OutputMatchesExpected) {
  auto [in, expected] = GetParam();
  std::vector<char> out(expected.size() + 1);
  size_t out_len = 0;
  ASSERT_EQ(codec_hex_encode(
      in.empty() ? nullptr : in.data(), in.size(),
      out.data(), out.size(), &out_len), CODEC_OK);
  EXPECT_EQ(out_len, expected.size());
  EXPECT_EQ(std::string(out.data(), out.data() + out_len), expected);
}

TEST_P(CodecHexEncodeParam, OutLenHelperMatches) {
  auto [in, expected] = GetParam();
  EXPECT_EQ(codec_hex_encode_out_len(in.size()), expected.size());
}

TEST_P(CodecHexEncodeParam, ExactSizedBufferWorks) {
  auto [in, expected] = GetParam();
  if (expected.empty()) return;  // zero-capacity edge case covered elsewhere
  std::vector<char> out(expected.size());
  size_t out_len = 0;
  EXPECT_EQ(codec_hex_encode(
      in.data(), in.size(), out.data(), out.size(), &out_len), CODEC_OK);
}

static std::vector<uint8_t> vec255(uint8_t fill) {
  return std::vector<uint8_t>(255, fill);
}
static std::vector<uint8_t> vec256(uint8_t fill) {
  return std::vector<uint8_t>(256, fill);
}

INSTANTIATE_TEST_SUITE_P(
    KnownVectors,
    CodecHexEncodeParam,
    testing::Values(
        HexParam{{},                              ""},
        HexParam{{0x00},                          "00"},
        HexParam{{0xFF},                          "ff"},
        HexParam{{0x0F},                          "0f"},
        HexParam{{0xF0},                          "f0"},
        HexParam{{'h','i'},                       "6869"},
        HexParam{{0x01,0x02,0x03},               "010203"},
        HexParam{{0xDE,0xAD,0xBE,0xEF},         "deadbeef"},
        HexParam{{0x00,0xFF,0x00,0xFF},          "00ff00ff"},
        HexParam{{0x10,0x20,0x30},              "102030"},
        HexParam{{0xAA,0xBB,0xCC,0xDD},        "aabbccdd"},
        HexParam{vec255(0x42), ref_hex(vec255(0x42))},
        HexParam{vec256(0x42), ref_hex(vec256(0x42))}
    )
);

// ════════════════════════════════════════════════════════════════════════════
// Suite: CodecBase64 — base64 encoding tests
// Category: Logic, Boundary
// ════════════════════════════════════════════════════════════════════════════

TEST(CodecBase64, EmptyInput) {
  char out[8]; size_t out_len = 99;
  auto st = codec_base64_encode(nullptr, 0, out, 0, &out_len);
  EXPECT_EQ(st, CODEC_OK);
  EXPECT_EQ(out_len, 0u);
}

TEST(CodecBase64, OneByte) {
  std::vector<uint8_t> in = {0x00};
  char out[8]; size_t out_len = 0;
  ASSERT_EQ(codec_base64_encode(in.data(), in.size(), out, sizeof(out), &out_len), CODEC_OK);
  EXPECT_EQ(std::string(out, out + out_len), "AA==");
}

TEST(CodecBase64, TwoBytes) {
  std::vector<uint8_t> in = {0x00, 0x00};
  char out[8]; size_t out_len = 0;
  ASSERT_EQ(codec_base64_encode(in.data(), in.size(), out, sizeof(out), &out_len), CODEC_OK);
  EXPECT_EQ(std::string(out, out + out_len), "AAA=");
}

TEST(CodecBase64, ThreeBytes_NoPadding) {
  std::vector<uint8_t> in = {0x00, 0x00, 0x00};
  char out[8]; size_t out_len = 0;
  ASSERT_EQ(codec_base64_encode(in.data(), in.size(), out, sizeof(out), &out_len), CODEC_OK);
  EXPECT_EQ(std::string(out, out + out_len), "AAAA");
}

TEST(CodecBase64, KnownVector_hi) {
  std::vector<uint8_t> in = {'h','i'};
  char out[8]; size_t out_len = 0;
  ASSERT_EQ(codec_base64_encode(in.data(), in.size(), out, sizeof(out), &out_len), CODEC_OK);
  EXPECT_EQ(std::string(out, out + out_len), "aGk=");
}

TEST(CodecBase64, KnownVector_ABC) {
  std::vector<uint8_t> in = {'A','B','C'};
  char out[8]; size_t out_len = 0;
  ASSERT_EQ(codec_base64_encode(in.data(), in.size(), out, sizeof(out), &out_len), CODEC_OK);
  EXPECT_EQ(std::string(out, out + out_len), "QUJD");
}

TEST(CodecBase64, AllFFBytes_3) {
  std::vector<uint8_t> in = {0xFF, 0xFF, 0xFF};
  char out[8]; size_t out_len = 0;
  ASSERT_EQ(codec_base64_encode(in.data(), in.size(), out, sizeof(out), &out_len), CODEC_OK);
  EXPECT_EQ(std::string(out, out + out_len), ref_base64(in));
}

TEST(CodecBase64, OutCapTooSmall) {
  // need = 4 for 1 byte, provide 3
  std::vector<uint8_t> in = {0xAB};
  char out[8]; size_t out_len = 0;
  auto st = codec_base64_encode(in.data(), in.size(), out, 3, &out_len);
  EXPECT_EQ(st, CODEC_ERR_OUTPUT_TOO_SMALL);
}

TEST(CodecBase64, OutCapExact) {
  std::vector<uint8_t> in = {'A','B','C'};
  const size_t need = codec_base64_encode_out_len(in.size());
  std::vector<char> out(need); size_t out_len = 0;
  EXPECT_EQ(codec_base64_encode(in.data(), in.size(), out.data(), need, &out_len), CODEC_OK);
}

TEST(CodecBase64, B007_OutLenHelperOffByOne) {
  // Under B007, codec_base64_encode_out_len(3) returns 3 instead of 4.
  // An exactly-sized allocation based on the helper will be rejected.
  const size_t in_len = 3;
  const size_t reported = codec_base64_encode_out_len(in_len);
  // Clean: reported == 4; B007: reported == 3
  // We verify by doing the correct encode into an adequate buffer and
  // comparing out_len to reported_need — under B007 they differ.
  std::vector<uint8_t> in(in_len, 0x42);
  char out[8]; size_t out_len = 0;
  codec_base64_encode(in.data(), in.size(), out, sizeof(out), &out_len);
  EXPECT_EQ(out_len, reported)
      << "codec_base64_encode_out_len reports wrong size (B007?)";
}

// ════════════════════════════════════════════════════════════════════════════
// Suite: CodecUtf8ByteLen — UTF-8 codepoint counting
// Category: Logic, Marshaling, Trap
// ════════════════════════════════════════════════════════════════════════════

TEST(CodecUtf8ByteLen, AsciiOnly) {
  // "hello" = 5 ASCII bytes = 5 codepoints
  const uint8_t in[] = {'h','e','l','l','o'};
  size_t cp = 99;
  ASSERT_EQ(codec_utf8_byte_len(in, sizeof(in), &cp), CODEC_OK);
  EXPECT_EQ(cp, 5u);
}

TEST(CodecUtf8ByteLen, TwoByteChar) {
  // é = U+00E9 = 0xC3 0xA9 — 2 bytes, 1 codepoint
  const uint8_t in[] = {0xC3, 0xA9};
  size_t cp = 99;
  ASSERT_EQ(codec_utf8_byte_len(in, sizeof(in), &cp), CODEC_OK);
  EXPECT_EQ(cp, 1u);
}

TEST(CodecUtf8ByteLen, ThreeByteChar) {
  // € = U+20AC = 0xE2 0x82 0xAC — 3 bytes, 1 codepoint
  const uint8_t in[] = {0xE2, 0x82, 0xAC};
  size_t cp = 99;
  ASSERT_EQ(codec_utf8_byte_len(in, sizeof(in), &cp), CODEC_OK);
  EXPECT_EQ(cp, 1u);
}

TEST(CodecUtf8ByteLen, MixedAsciiAndMultibyte) {
  // "hé" = 'h' (0x68) + é (0xC3 0xA9) = 3 bytes, 2 codepoints
  const uint8_t in[] = {0x68, 0xC3, 0xA9};
  size_t cp = 99;
  ASSERT_EQ(codec_utf8_byte_len(in, sizeof(in), &cp), CODEC_OK);
  EXPECT_EQ(cp, 2u);
}

TEST(CodecUtf8ByteLen, B008_CountsCharsNotBytes) {
  // Under B008 the function returns the byte width sum (2) instead of
  // the codepoint count (1) for é — the JS str.length vs bytes.length bug.
  const uint8_t in[] = {0xC3, 0xA9};  // é
  size_t cp = 0;
  ASSERT_EQ(codec_utf8_byte_len(in, sizeof(in), &cp), CODEC_OK);
  // Clean: cp == 1.  B008: cp == 2.
  EXPECT_EQ(cp, 1u) << "codepoint count wrong (B008 — counting bytes not codepoints?)";
}

TEST(CodecUtf8ByteLen, NullInput) {
  size_t cp = 0;
  auto st = codec_utf8_byte_len(nullptr, 1, &cp);
  EXPECT_EQ(st, CODEC_ERR_NULL);
}

// ════════════════════════════════════════════════════════════════════════════
// Disabled demo (kept for compatibility)
// ════════════════════════════════════════════════════════════════════════════

TEST(CodecHexEncode, DISABLED_DemoIntentionalFail) {
  std::vector<uint8_t> in = {'h','i'};
  char out[64]; size_t out_len = 0;
  auto st = codec_hex_encode(in.data(), in.size(), out, sizeof(out), &out_len);
  ASSERT_EQ(st, CODEC_OK);
  EXPECT_EQ(std::string(out, out + out_len), "NOT_THE_RIGHT_HEX");
}
