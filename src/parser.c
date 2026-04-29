#include "parser.h"
#include <stddef.h>

/* ── Bug flags ── */
#if defined(PARSER_BUG_Q001)
/* Off-by-one: writes null terminator one byte past field_cap, corrupting the
   byte after the output buffer. Detected by sentinel tests. */
#define PARSER_Q001_NULLTERM_OOB 1
#else
#define PARSER_Q001_NULLTERM_OOB 0
#endif

#if defined(PARSER_BUG_Q002)
/* Logic: skips the comma-advance after an unquoted field, so *in_pos stays
   on the delimiter and the next call re-reads the same field. */
#define PARSER_Q002_NO_ADVANCE 1
#else
#define PARSER_Q002_NO_ADVANCE 0
#endif

#if defined(PARSER_BUG_Q003)
/* Trap: missing null check on in_pos — dereferences null pointer. */
#define PARSER_Q003_NULL_DEREF 1
#else
#define PARSER_Q003_NULL_DEREF 0
#endif

#if defined(PARSER_BUG_Q004)
/* Runtime-dependent: ignores the closing quote of a quoted field, treating
   the trailing '"' as part of the content. Only manifests for quoted fields. */
#define PARSER_Q004_IGNORE_CLOSE_QUOTE 1
#else
#define PARSER_Q004_IGNORE_CLOSE_QUOTE 0
#endif

/* ── Implementation ── */

parser_status_t csv_next_field(
    const char* in,       size_t in_len,
    size_t*     in_pos,
    char*       field_out, size_t field_cap,
    size_t*     field_len_out)
{
  if (!in || !field_out || !field_len_out) return PARSER_ERR_NULL;

#if PARSER_Q003_NULL_DEREF
  /* Bug Q003: dereference in_pos without checking for null */
  (void)0;
#else
  if (!in_pos) return PARSER_ERR_NULL;
#endif

  if (*in_pos >= in_len) return PARSER_ERR_NO_MORE_FIELDS;

  *field_len_out = 0;

  size_t pos = *in_pos;
  size_t wpos = 0;   /* write position into field_out */

  if (in[pos] == '"') {
    /* Quoted field: consume opening quote */
    pos++;
    while (pos < in_len) {
      char c = in[pos];
#if PARSER_Q004_IGNORE_CLOSE_QUOTE
      /* Bug Q004: never treat '"' as closing quote — absorb it as content */
      if (wpos >= field_cap) return PARSER_ERR_OUTPUT_TOO_SMALL;
      field_out[wpos++] = c;
      pos++;
#else
      if (c == '"') {
        pos++; /* consume closing quote */
        break;
      }
      if (wpos >= field_cap) return PARSER_ERR_OUTPUT_TOO_SMALL;
      field_out[wpos++] = c;
      pos++;
#endif
    }
    /* Advance past trailing comma if present */
    if (pos < in_len && in[pos] == ',') pos++;
  } else {
    /* Unquoted field: read until comma or end */
    while (pos < in_len && in[pos] != ',') {
      if (wpos >= field_cap) return PARSER_ERR_OUTPUT_TOO_SMALL;
      field_out[wpos++] = in[pos];
      pos++;
    }
#if PARSER_Q002_NO_ADVANCE
    /* Bug Q002: don't advance past the comma */
    (void)0;
#else
    /* Advance past comma */
    if (pos < in_len && in[pos] == ',') pos++;
#endif
  }

  /* Null-terminate */
#if PARSER_Q001_NULLTERM_OOB
  /* Bug Q001: write null one byte past field_cap (off-by-one) */
  field_out[wpos] = '\0';  /* wpos may equal field_cap here */
#else
  if (wpos >= field_cap) return PARSER_ERR_OUTPUT_TOO_SMALL;
  field_out[wpos] = '\0';
#endif

  *field_len_out = wpos;
  *in_pos = pos;
  return PARSER_OK;
}

parser_status_t csv_count_fields(
    const char* in, size_t in_len,
    size_t*     count_out)
{
  if (!in || !count_out) return PARSER_ERR_NULL;

  if (in_len == 0) {
    *count_out = 0;
    return PARSER_OK;
  }

  size_t count = 1;
  size_t pos = 0;

  while (pos < in_len) {
    char c = in[pos];
    if (c == '"') {
      pos++; /* skip opening quote */
      while (pos < in_len) {
#if PARSER_Q004_IGNORE_CLOSE_QUOTE
        /* Bug Q004: never detect closing quote; comma inside quotes
           gets counted as a field separator */
        if (in[pos] == ',') { count++; }
        pos++;
#else
        if (in[pos] == '"') { pos++; break; } /* closing quote */
        pos++;
#endif
      }
      /* skip comma after quoted field */
      if (pos < in_len && in[pos] == ',') { count++; pos++; }
    } else if (c == ',') {
      count++;
      pos++;
    } else {
      pos++;
    }
  }

  *count_out = count;
  return PARSER_OK;
}
