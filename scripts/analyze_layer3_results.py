#!/usr/bin/env python3
import argparse
import csv
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path


RUN_SUFFIX_RE = re.compile(r"#run\d+$")
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CHART_SCRIPT = ROOT / "scripts" / "render_layer3_chart.py"
DEFAULT_CHART_HTML = ROOT / "results" / "layer3_chart.html"
DEFAULT_CHART_FILE = ROOT / "results" / "layer3_chart.svg"
DEFAULT_MASTER_MATRIX = ROOT / "results" / "layer3_master_matrix.csv"
DEFAULT_RELATIONSHIP_MATRIX = ROOT / "results" / "layer3_relationship_matrix.csv"


def env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize layer 3 browser CSV results.")
    parser.add_argument(
        "csv_path",
        nargs="?",
        default="results/layer3_matrix.csv",
        help="Path to the aggregated CSV file.",
    )
    parser.add_argument(
        "--summary-out",
        default="results/layer3_summary.csv",
        help="Where to write the per-bug summary CSV.",
    )
    parser.add_argument(
        "--browser-summary-out",
        default="results/layer3_browser_summary.csv",
        help="Where to write the per-bug per-browser summary CSV.",
    )
    parser.add_argument(
        "--master-matrix-out",
        default=str(DEFAULT_MASTER_MATRIX),
        help="Where to write the derived per-row Layer 3 master matrix CSV.",
    )
    parser.add_argument(
        "--relationship-matrix-out",
        default=str(DEFAULT_RELATIONSHIP_MATRIX),
        help="Where to write the compact relationship matrix CSV grouped by bug, browser, and test family.",
    )
    parser.add_argument(
        "--render-chart",
        dest="render_chart",
        action="store_true",
        default=env_flag("LAYER3_RENDER_CHART", True),
        help="Render the HTML chart after writing summary CSV files. Default: enabled.",
    )
    parser.add_argument(
        "--no-render-chart",
        dest="render_chart",
        action="store_false",
        help="Skip chart rendering.",
    )
    parser.add_argument(
        "--open-chart",
        dest="open_chart",
        action="store_true",
        default=env_flag("LAYER3_OPEN_CHART", True),
        help="Open the chart after rendering it. Default: enabled.",
    )
    parser.add_argument(
        "--no-open-chart",
        dest="open_chart",
        action="store_false",
        help="Do not auto-open the chart.",
    )
    parser.add_argument(
        "--chart-script",
        default=str(DEFAULT_CHART_SCRIPT),
        help="Path to the chart rendering script.",
    )
    parser.add_argument(
        "--chart-html",
        default=str(DEFAULT_CHART_HTML),
        help="Path to the generated chart HTML file.",
    )
    parser.add_argument(
        "--chart-file",
        default=str(DEFAULT_CHART_FILE),
        help="Path to the generated chart file to open. Default: layer3_chart.svg.",
    )
    return parser.parse_args()


def ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def base_test_name(name: str) -> str:
    return RUN_SUFFIX_RE.sub("", name)


def extract_run_index(test_name: str) -> int:
    match = re.search(r"#run(\d+)$", test_name)
    return int(match.group(1)) if match else 1


def classify_test_family(base_name: str) -> str:
    t = base_name.lower()
    if "[b001 detector]" in t:
        return "b001"
    if "[b002 detector]" in t:
        return "b002"
    if "[b003 detector]" in t or "wasm trap" in t:
        return "b003"
    if "lowercase" in t or "format" in t or "nibble" in t:
        return "format"
    if "throws" in t or "error code" in t or "error propagation" in t:
        return "error_handling"
    return "baseline"


def build_master_rows(rows):
    master_rows = []
    for row in rows:
        base_name = base_test_name(row["test_name"])
        family = classify_test_family(base_name)
        outcome = row["outcome"]
        failure_kind = row["failure_kind"] or "none"

        master_rows.append({
            "bug_id": row["bug_id"],
            "browser": row.get("runtime", "unknown"),
            "run_index": extract_run_index(row["test_name"]),
            "test_name": row["test_name"],
            "base_test_name": base_name,
            "test_family": family,
            "outcome": outcome,
            "failure_kind": failure_kind,
            "detected": "yes" if outcome == "fail" else "no",
        })

    return master_rows


def build_relationship_rows(master_rows):
    grouped = defaultdict(lambda: {
        "total_rows": 0,
        "pass_rows": 0,
        "fail_rows": 0,
        "failure_kinds": Counter(),
    })

    for row in master_rows:
        key = (row["bug_id"], row["browser"], row["test_family"])
        stat = grouped[key]
        stat["total_rows"] += 1
        if row["outcome"] == "pass":
            stat["pass_rows"] += 1
        elif row["outcome"] == "fail":
            stat["fail_rows"] += 1
            stat["failure_kinds"][row["failure_kind"]] += 1

    relationship_rows = []
    for (bug_id, browser, test_family) in sorted(grouped):
        stat = grouped[(bug_id, browser, test_family)]
        relationship_rows.append({
            "bug_id": bug_id,
            "browser": browser,
            "test_family": test_family,
            "total_rows": stat["total_rows"],
            "pass_rows": stat["pass_rows"],
            "fail_rows": stat["fail_rows"],
            "detected": "yes" if stat["fail_rows"] > 0 else "no",
            "failure_assertion_fail": stat["failure_kinds"].get("assertion_fail", 0),
            "failure_exception": stat["failure_kinds"].get("exception", 0),
        })

    return relationship_rows


def analyze(rows):
    bug_stats = defaultdict(lambda: {
        "total_rows": 0,
        "pass_rows": 0,
        "fail_rows": 0,
        "skip_rows": 0,
        "failure_kinds": Counter(),
        "browsers": set(),
        "max_run_index": 1,
    })
    browser_stats = defaultdict(lambda: {
        "total_rows": 0,
        "pass_rows": 0,
        "fail_rows": 0,
        "skip_rows": 0,
        "failure_kinds": Counter(),
    })
    run_groups = defaultdict(list)

    for row in rows:
        bug_id = row["bug_id"]
        outcome = row["outcome"]
        failure_kind = row["failure_kind"] or "none"
        browser = row.get("runtime", "unknown")
        run_index = extract_run_index(row["test_name"])
        base_name = base_test_name(row["test_name"])

        stat = bug_stats[bug_id]
        stat["total_rows"] += 1
        stat["browsers"].add(browser)
        stat["max_run_index"] = max(stat["max_run_index"], run_index)

        browser_stat = browser_stats[(bug_id, browser)]
        browser_stat["total_rows"] += 1

        if outcome == "pass":
            stat["pass_rows"] += 1
            browser_stat["pass_rows"] += 1
        elif outcome == "fail":
            stat["fail_rows"] += 1
            stat["failure_kinds"][failure_kind] += 1
            browser_stat["fail_rows"] += 1
            browser_stat["failure_kinds"][failure_kind] += 1
        else:
            stat["skip_rows"] += 1
            browser_stat["skip_rows"] += 1

        run_groups[(bug_id, browser, base_name)].append(outcome)

    summary_rows = []
    for bug_id in sorted(bug_stats):
        stat = bug_stats[bug_id]
        groups = [
            outcomes
            for (group_bug, _, _), outcomes in run_groups.items()
            if group_bug == bug_id
        ]
        flaky_groups = sum(1 for outcomes in groups if len(set(outcomes)) > 1)
        repeated_groups = sum(1 for outcomes in groups if len(outcomes) > 1)
        summary_rows.append({
            "bug_id": bug_id,
            "total_rows": stat["total_rows"],
            "pass_rows": stat["pass_rows"],
            "fail_rows": stat["fail_rows"],
            "skip_rows": stat["skip_rows"],
            "detected": "yes" if stat["fail_rows"] > 0 else "no",
            "failure_assertion_fail": stat["failure_kinds"].get("assertion_fail", 0),
            "failure_exception": stat["failure_kinds"].get("exception", 0),
            "browsers_seen": ";".join(sorted(stat["browsers"])),
            "max_run_index": stat["max_run_index"],
            "flaky_tests": flaky_groups,
            "repeated_groups": repeated_groups,
            "flaky_rate": f"{(flaky_groups / repeated_groups):.3f}" if repeated_groups else "0.000",
        })

    browser_summary_rows = []
    for (bug_id, browser) in sorted(browser_stats):
        stat = browser_stats[(bug_id, browser)]
        browser_summary_rows.append({
            "bug_id": bug_id,
            "browser": browser,
            "total_rows": stat["total_rows"],
            "pass_rows": stat["pass_rows"],
            "fail_rows": stat["fail_rows"],
            "skip_rows": stat["skip_rows"],
            "detected": "yes" if stat["fail_rows"] > 0 else "no",
            "failure_assertion_fail": stat["failure_kinds"].get("assertion_fail", 0),
            "failure_exception": stat["failure_kinds"].get("exception", 0),
        })

    return summary_rows, browser_summary_rows


def write_csv(path: str, rows) -> None:
    ensure_parent(path)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        if rows:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        else:
            handle.write("")


def maybe_render_chart(args: argparse.Namespace) -> None:
    if not args.render_chart:
        return

    subprocess.run([sys.executable, args.chart_script], check=True)
    print(f"[Layer3 Analysis] chart_html={args.chart_html}")
    print(f"[Layer3 Analysis] chart_file={args.chart_file}")

    if not args.open_chart:
        return

    chart_path = Path(args.chart_file).resolve()
    opener = None
    if sys.platform == "darwin":
        opener = ["open", "-a", "Visual Studio Code", str(chart_path)]
    elif sys.platform.startswith("linux"):
        opener = ["xdg-open", str(chart_path)]
    elif os.name == "nt":
        opener = ["cmd", "/c", "start", "", str(chart_path)]

    if opener is None:
        print(f"[Layer3 Analysis] chart_open_skipped unsupported_platform={sys.platform}")
        return

    try:
        subprocess.run(opener, check=True)
        print(f"[Layer3 Analysis] chart_opened={chart_path}")
    except Exception as exc:
        print(f"[Layer3 Analysis] chart_open_failed={exc}")


def main() -> int:
    args = parse_args()

    if not os.path.exists(args.csv_path):
        print(f"Missing CSV: {args.csv_path}", file=sys.stderr)
        return 2

    with open(args.csv_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        layer3_rows = [row for row in reader if row.get("layer") == "layer3_browser"]

    summary_rows, browser_summary_rows = analyze(layer3_rows)
    master_matrix_rows = build_master_rows(layer3_rows)
    relationship_rows = build_relationship_rows(master_matrix_rows)
    write_csv(args.summary_out, summary_rows)
    write_csv(args.browser_summary_out, browser_summary_rows)
    write_csv(args.master_matrix_out, master_matrix_rows)
    write_csv(args.relationship_matrix_out, relationship_rows)

    print(f"[Layer3 Analysis] source_rows={len(layer3_rows)}")
    print(f"[Layer3 Analysis] summary_csv={args.summary_out}")
    print(f"[Layer3 Analysis] browser_summary_csv={args.browser_summary_out}")
    print(f"[Layer3 Analysis] master_matrix_csv={args.master_matrix_out}")
    print(f"[Layer3 Analysis] relationship_matrix_csv={args.relationship_matrix_out}")

    for row in summary_rows:
        print(
            "[Layer3 Analysis] "
            f"bug_id={row['bug_id']} "
            f"detected={row['detected']} "
            f"fail_rows={row['fail_rows']} "
            f"flaky_rate={row['flaky_rate']} "
            f"browsers={row['browsers_seen']}"
        )

    maybe_render_chart(args)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
