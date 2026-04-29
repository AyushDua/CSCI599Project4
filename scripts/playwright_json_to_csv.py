#!/usr/bin/env python3
import csv
import json
import os
import sys
from datetime import datetime, timezone

MAX_DETAILS = 1000

def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def ensure_header(csv_path: str) -> None:
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                "timestamp",
                "bug_id",
                "layer",
                "runtime",
                "test_name",
                "outcome",
                "failure_kind",
                "details",
            ])

def normalize_list(x):
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]

def walk_suites(suites, prefix=""):
    """
    Playwright JSON structure (common):
      { "suites": [ { "title": "...", "suites": [...], "specs": [...] } ] }

    Each spec has: title, file, line, column, tests[]
    Each test has: projectName, results[]
    """
    for s in normalize_list(suites):
        title = s.get("title") or ""
        new_prefix = f"{prefix}::{title}" if title else prefix

        for spec in normalize_list(s.get("specs")):
            yield (new_prefix, spec)

        yield from walk_suites(s.get("suites"), new_prefix)

def extract_error_details(last_result: dict) -> str:
    """
    last_result may contain { error: { message, stack } } or other shapes.
    """
    err = last_result.get("error")
    if isinstance(err, dict):
        msg = err.get("message") or ""
        stack = err.get("stack") or ""
        details = (msg + ("\n" + stack if stack else "")).strip()
        return details[:MAX_DETAILS]
    if err is None:
        return ""
    return str(err)[:MAX_DETAILS]

def classify_failure_kind(status: str, details: str) -> str:
    """
    For Layer 3, typical failure types:
      - assertion_fail: expect(...) mismatch (Playwright assertions)
      - exception: runtime errors, page.evaluate errors, aborted, type errors, timeouts

    We keep it simple + robust by matching common patterns.
    """
    s = (status or "").lower()
    d = (details or "").lower()

    if s == "timedout":
        return "exception"

    # Common "exception-ish" patterns
    exception_markers = [
        "page.evaluate",
        "runtimeerror",
        "referenceerror",
        "typeerror",
        "syntaxerror",
        "aborted(",
        "uncaught",
        "error:",
        "wasm",
        "compileerror",
        "linkerror",
    ]
    if any(m in d for m in exception_markers):
        return "exception"

    # Common assertion patterns in Playwright
    assertion_markers = [
        "expect(",
        "toBe",
        "toEqual",
        "toContain",
        "toMatch",
        "assert",
        "expected",
        "received",
    ]
    if any(m.lower() in d for m in assertion_markers):
        return "assertion_fail"

    # Default to assertion_fail (most Playwright failures are assertions)
    return "assertion_fail"

def build_test_name(prefix: str, spec: dict, test: dict, run_index: int) -> str:
    """
    Create a stable human-readable test identifier.
    spec.title usually equals the test title, but we add file:line for uniqueness.
    """
    spec_title = spec.get("title") or "UnknownSpec"
    file = spec.get("file") or ""
    line = spec.get("line")
    loc = f"{file}:{line}" if file and line is not None else (file if file else "")

    # Some Playwright JSON shapes include test.title; some rely on spec.title only.
    test_title = test.get("title") or ""
    title = spec_title if not test_title or test_title == spec_title else f"{spec_title} :: {test_title}"

    if prefix:
        title = f"{prefix}::{title}"
    if loc:
        title = f"{title} ({loc})"

    if run_index > 1:
        title = f"{title}#run{run_index}"

    return title

def main():
    if len(sys.argv) < 4:
        print("Usage: playwright_json_to_csv.py <pw_json> <csv_out> <bug_id> [run_index]", file=sys.stderr)
        sys.exit(2)

    pw_json, csv_out, bug_id = sys.argv[1], sys.argv[2], sys.argv[3]
    run_index = int(sys.argv[4]) if len(sys.argv) >= 5 else 1
    layer = "layer3_browser"

    ensure_header(csv_out)

    # If Playwright didn't produce JSON (rare but possible), log a single row.
    if not os.path.exists(pw_json):
        with open(csv_out, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([iso_now(), bug_id, layer, "unknown", "playwright_report_missing", "fail", "exception",
                        f"Missing report file: {pw_json}"])
        print(f"[Layer3 CSV] report missing -> wrote 1 failure row to {csv_out}")
        sys.exit(1)

    with open(pw_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    suites = data.get("suites", [])

    for prefix, spec in walk_suites(suites, ""):
        for test in normalize_list(spec.get("tests")):
            runtime = (test.get("projectName") or "unknown").lower()
            results = normalize_list(test.get("results"))
            last = results[-1] if results else {}
            status = (last.get("status") or "unknown")

            if status == "passed":
                outcome = "pass"
                details = ""
                failure_kind = ""
            elif status in ("failed", "timedOut"):
                outcome = "fail"
                details = extract_error_details(last)
                failure_kind = classify_failure_kind(status, details)
            else:
                # skipped / interrupted / unknown
                outcome = "skip"
                details = status
                failure_kind = ""

            test_name = build_test_name(prefix, spec, test, run_index)

            rows.append([iso_now(), bug_id, layer, runtime, test_name, outcome, failure_kind, details])

    with open(csv_out, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerows(rows)

    passed = sum(1 for r in rows if r[5] == "pass")
    failed = sum(1 for r in rows if r[5] == "fail")
    skipped = sum(1 for r in rows if r[5] == "skip")
    print(f"[Layer3 CSV] wrote {len(rows)} rows (pass={passed} fail={failed} skip={skipped}) -> {csv_out}")

if __name__ == "__main__":
    main()
