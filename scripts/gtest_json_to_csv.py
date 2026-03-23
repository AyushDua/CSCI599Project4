#!/usr/bin/env python3
import csv
import json
import os
import sys
from datetime import datetime, timezone

def classify_failure_kind(details: str) -> str:
    if not details:
        return ""
    d = details.lower()
    # heuristic: equality mismatch patterns
    if "expected equality of these values" in d or "which is:" in d and "expected:" in d:
        return "output_mismatch"
    return "assertion_fail"

def iso_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def ensure_header(csv_path: str):
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["timestamp","bug_id","layer","runtime","test_name","outcome","failure_kind","details"])

def normalize_list(x):
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]

def extract_suites(data):
    # gtest json sometimes: {"testsuites": {"testsuite":[...]}}
    ts = data.get("testsuites")
    if isinstance(ts, dict) and "testsuite" in ts:
        return normalize_list(ts["testsuite"])
    # sometimes already a list
    if isinstance(ts, list):
        return ts
    # fallback
    if "testsuite" in data:
        return normalize_list(data["testsuite"])
    return []

def extract_cases(suite_obj):
    # gtest json suite usually contains "testsuite": [cases...]
    if "testsuite" in suite_obj:
        return normalize_list(suite_obj["testsuite"])
    # fallback variants
    if "testcase" in suite_obj:
        return normalize_list(suite_obj["testcase"])
    return []

def failure_details(case_obj):
    fails = case_obj.get("failures")
    if not fails:
        return ""
    fails = normalize_list(fails)
    # gtest commonly puts text in "failure"
    texts = []
    for f in fails:
        if isinstance(f, dict):
            texts.append(f.get("failure") or f.get("message") or str(f))
        else:
            texts.append(str(f))
    msg = " | ".join(t.strip().replace("\n"," ") for t in texts if t)
    return msg[:1000]

def case_outcome(case_obj):
    # heuristics: failures => fail, NOTRUN => skip, otherwise pass
    if case_obj.get("failures"):
        return "fail"
    if case_obj.get("status") == "NOTRUN":
        return "skip"
    return "pass"

def main():
    if len(sys.argv) < 4:
        print("Usage: gtest_json_to_csv.py <gtest_json> <csv_out> <bug_id>", file=sys.stderr)
        sys.exit(2)

    json_path, csv_path, bug_id = sys.argv[1], sys.argv[2], sys.argv[3]
    layer = "layer1_native"
    runtime = "native"

    with open(json_path, "r") as f:
        data = json.load(f)

    ensure_header(csv_path)

    rows = []
    for suite in extract_suites(data):
        suite_name = suite.get("name") or suite.get("testsuite") or "UnknownSuite"
        for case in extract_cases(suite):
            case_name = case.get("name") or "UnknownCase"
            test_name = f"{suite_name}.{case_name}"
            outcome = case_outcome(case)
            details = failure_details(case)
            failure_kind = classify_failure_kind(details) if outcome == "fail" else ""
            rows.append([iso_now(), bug_id, layer, runtime, test_name, outcome, failure_kind, details])

    with open(csv_path, "a", newline="") as f:
        w = csv.writer(f)
        for r in rows:
            w.writerow(r)

    # Also print a tiny summary
    passed = sum(1 for r in rows if r[5] == "pass")
    failed = sum(1 for r in rows if r[5] == "fail")
    skipped = sum(1 for r in rows if r[5] == "skip")
    print(f"[Layer1 CSV] wrote {len(rows)} rows (pass={passed} fail={failed} skip={skipped}) -> {csv_path}")

if __name__ == "__main__":
    main()