#pragma once
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
  PARSER_OK = 0,
  PARSER_ERR_NULL = 1,
  PARSER_ERR_OUTPUT_TOO_SMALL = 2,
  PARSER_ERR_MALFORMED = 3,
  PARSER_ERR_NO_MORE_FIELDS = 4
} parser_status_t;

/*
 * Parse one CSV field from `in[*in_pos .. in_len)`, advancing *in_pos past
 * the trailing comma (or to in_len if this is the last field).
 * The field content is written to field_out and null-terminated.
 * Quoted fields strip the surrounding quotes; a comma inside quotes is literal.
 * Returns PARSER_ERR_NO_MORE_FIELDS if *in_pos >= in_len before parsing starts.
 */
parser_status_t csv_next_field(
    const char* in,       size_t in_len,
    size_t*     in_pos,
    char*       field_out, size_t field_cap,
    size_t*     field_len_out);

/*
 * Count the number of comma-separated fields in `in[0..in_len)`.
 * An empty string has 0 fields; a single comma has 2 fields.
 */
parser_status_t csv_count_fields(
    const char* in, size_t in_len,
    size_t*     count_out);

#ifdef __cplusplus
}
#endif
