#include <gtest/gtest.h>
#include <cstring>
#include <string>

extern "C" {
#include "parser.h"
}

// ════════════════════════════════════════════════════════════════════════════
// Suite: CsvNextField — Logic and Boundary tests
// ════════════════════════════════════════════════════════════════════════════

TEST(CsvNextField, SimpleField) {
  const char* row = "hello,world";
  size_t pos = 0;
  char field[32]; size_t flen = 0;
  auto st = csv_next_field(row, strlen(row), &pos, field, sizeof(field), &flen);
  ASSERT_EQ(st, PARSER_OK);
  EXPECT_EQ(std::string(field, flen), "hello");
  EXPECT_EQ(pos, 6u);  // past the comma
}

TEST(CsvNextField, LastField_NoTrailingComma) {
  const char* row = "hello,world";
  size_t pos = 6;  // start after first field's comma
  char field[32]; size_t flen = 0;
  auto st = csv_next_field(row, strlen(row), &pos, field, sizeof(field), &flen);
  ASSERT_EQ(st, PARSER_OK);
  EXPECT_EQ(std::string(field, flen), "world");
  EXPECT_EQ(pos, strlen(row));
}

TEST(CsvNextField, EmptyField) {
  // First field of ",a" is empty
  const char* row = ",a";
  size_t pos = 0;
  char field[32]; size_t flen = 0;
  auto st = csv_next_field(row, strlen(row), &pos, field, sizeof(field), &flen);
  ASSERT_EQ(st, PARSER_OK);
  EXPECT_EQ(flen, 0u);
  EXPECT_EQ(std::string(field), "");
  EXPECT_EQ(pos, 1u);  // past comma
}

TEST(CsvNextField, QuotedField) {
  // Comma inside quotes is literal field content
  const char* row = "\"ab,c\",d";
  size_t pos = 0;
  char field[32]; size_t flen = 0;
  auto st = csv_next_field(row, strlen(row), &pos, field, sizeof(field), &flen);
  ASSERT_EQ(st, PARSER_OK);
  EXPECT_EQ(std::string(field, flen), "ab,c");
}

TEST(CsvNextField, QuotedField_MixedContent) {
  const char* row = "\"hello world\"";
  size_t pos = 0;
  char field[32]; size_t flen = 0;
  auto st = csv_next_field(row, strlen(row), &pos, field, sizeof(field), &flen);
  ASSERT_EQ(st, PARSER_OK);
  EXPECT_EQ(std::string(field, flen), "hello world");
}

TEST(CsvNextField, FieldOutputTooSmall) {
  const char* row = "hello,world";
  size_t pos = 0;
  char field[2]; size_t flen = 0;  // only 2 bytes — "hello" needs 6 (5 + NUL)
  auto st = csv_next_field(row, strlen(row), &pos, field, sizeof(field), &flen);
  EXPECT_EQ(st, PARSER_ERR_OUTPUT_TOO_SMALL);
}

TEST(CsvNextField, FieldOutputExact) {
  // field_cap == field_len + 1 (for NUL) — must succeed
  const char* row = "abc,d";
  size_t pos = 0;
  char field[4]; size_t flen = 0;  // "abc" needs exactly 4 bytes (3 + NUL)
  auto st = csv_next_field(row, strlen(row), &pos, field, sizeof(field), &flen);
  ASSERT_EQ(st, PARSER_OK);
  EXPECT_EQ(std::string(field, flen), "abc");
}

TEST(CsvNextField, Q001_NullTermWritesPastCap) {
  // Bug Q001 writes NUL at index field_cap instead of field_cap-1.
  // We guard with a sentinel byte immediately after field_out.
  // On a clean build the sentinel ('Z') must survive.
  char buf[3] = {'?', '?', 'Z'};  // buf[0..1] = field_cap=2; buf[2] = sentinel
  const char* row = "a,b";
  size_t pos = 0;
  size_t flen = 0;
  // Provide only 2 bytes of field capacity (enough for "a" + NUL in clean build)
  auto st = csv_next_field(row, strlen(row), &pos, buf, 2, &flen);
  if (st == PARSER_OK) {
    // sentinel must not be overwritten
    EXPECT_EQ(buf[2], 'Z') << "sentinel overwritten (Q001 off-by-one null-term?)";
  }
  // Under Q001 the NUL lands at buf[2] clobbering 'Z'
}

TEST(CsvNextField, Q002_PosAdvancesAfterField) {
  // After parsing the first field, pos must point past the comma so that
  // the next call reads "world", not "hello" again.
  const char* row = "hello,world";
  size_t pos = 0;
  char field1[32]; size_t flen1 = 0;
  ASSERT_EQ(csv_next_field(row, strlen(row), &pos, field1, sizeof(field1), &flen1),
            PARSER_OK);
  size_t pos_after_first = pos;

  char field2[32]; size_t flen2 = 0;
  ASSERT_EQ(csv_next_field(row, strlen(row), &pos, field2, sizeof(field2), &flen2),
            PARSER_OK);
  EXPECT_EQ(std::string(field2, flen2), "world")
      << "second field re-reads first (Q002 — no pos advance?)";
  EXPECT_GT(pos, pos_after_first);
}

TEST(CsvNextField, Q003_NullInPosIsError) {
  // in_pos == nullptr must return PARSER_ERR_NULL without crashing
  const char* row = "hello";
  char field[32]; size_t flen = 0;
  auto st = csv_next_field(row, strlen(row), nullptr, field, sizeof(field), &flen);
  EXPECT_EQ(st, PARSER_ERR_NULL);
}

// ════════════════════════════════════════════════════════════════════════════
// Suite: CsvCountFields — Runtime-dependent tests
// ════════════════════════════════════════════════════════════════════════════

TEST(CsvCountFields, SingleField) {
  size_t count = 0;
  ASSERT_EQ(csv_count_fields("abc", 3, &count), PARSER_OK);
  EXPECT_EQ(count, 1u);
}

TEST(CsvCountFields, TwoFields) {
  size_t count = 0;
  ASSERT_EQ(csv_count_fields("a,b", 3, &count), PARSER_OK);
  EXPECT_EQ(count, 2u);
}

TEST(CsvCountFields, EmptyFields) {
  // ",," = three fields, all empty
  size_t count = 0;
  ASSERT_EQ(csv_count_fields(",,", 2, &count), PARSER_OK);
  EXPECT_EQ(count, 3u);
}

TEST(CsvCountFields, QuotedFieldWithComma) {
  // "a,b",c — the comma inside quotes is not a separator
  const char* row = "\"a,b\",c";
  size_t count = 0;
  ASSERT_EQ(csv_count_fields(row, strlen(row), &count), PARSER_OK);
  EXPECT_EQ(count, 2u);
}

TEST(CsvCountFields, Q004_QuotedClosingMissed) {
  // Under Q004, the closing '"' is never detected, so the next comma (or an
  // extra '"') gets counted as a separator, inflating the field count.
  const char* row = "\"abc\"";
  size_t count = 0;
  ASSERT_EQ(csv_count_fields(row, strlen(row), &count), PARSER_OK);
  // Clean: 1 field.  Q004: closing '"' not consumed → extra separator found.
  EXPECT_EQ(count, 1u) << "field count inflated (Q004 — closing quote ignored?)";
}

// ════════════════════════════════════════════════════════════════════════════
// Suite: CsvParserErrorHandling — Trap and error propagation
// ════════════════════════════════════════════════════════════════════════════

TEST(CsvParserErrorHandling, NullInputPointer) {
  size_t pos = 0; char field[8]; size_t flen = 0;
  auto st = csv_next_field(nullptr, 5, &pos, field, sizeof(field), &flen);
  EXPECT_EQ(st, PARSER_ERR_NULL);
}

TEST(CsvParserErrorHandling, NullFieldOut) {
  const char* row = "hello";
  size_t pos = 0; size_t flen = 0;
  auto st = csv_next_field(row, strlen(row), &pos, nullptr, 8, &flen);
  EXPECT_EQ(st, PARSER_ERR_NULL);
}

TEST(CsvParserErrorHandling, NullCountOut) {
  auto st = csv_count_fields("a,b", 3, nullptr);
  EXPECT_EQ(st, PARSER_ERR_NULL);
}

TEST(CsvParserErrorHandling, AtEndOfInput) {
  const char* row = "hi";
  size_t pos = strlen(row);  // already at end
  char field[8]; size_t flen = 0;
  auto st = csv_next_field(row, strlen(row), &pos, field, sizeof(field), &flen);
  EXPECT_EQ(st, PARSER_ERR_NO_MORE_FIELDS);
}
