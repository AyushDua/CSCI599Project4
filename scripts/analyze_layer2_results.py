#!/usr/bin/env python3
import argparse
import csv
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path


MODE_RE = re.compile(r"(?:^|\s)mode=([a-z_]+)")
RUN_RE = re.compile(r"(?:^|\s)run_index=(\d+)")
RUN_SUFFIX_RE = re.compile(r"#run\d+$")
KEY_VALUE_RE = re.compile(r"([a-z_]+)=([^\s]+)")
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CHART_SCRIPT = ROOT / "scripts" / "render_layer2_chart.py"
DEFAULT_CHART_HTML = ROOT / "results" / "layer2_chart.html"
DEFAULT_CHART_FILE = ROOT / "results" / "layer2_chart.svg"
DEFAULT_MASTER_MATRIX = ROOT / "results" / "layer2_master_matrix.csv"
DEFAULT_RELATIONSHIP_MATRIX = ROOT / "results" / "layer2_relationship_matrix.csv"


def env_flag(name: str, default: bool) -> bool:
  raw = os.environ.get(name)
  if raw is None:
    return default
  return raw.strip().lower() not in {"0", "false", "no", "off"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize layer 2 Wasmtime CSV results.")
    parser.add_argument(
        "csv_path",
        nargs="?",
        default="results/run_results.csv",
        help="Path to the aggregated CSV file.",
    )
    parser.add_argument(
        "--summary-out",
        default="results/layer2_summary.csv",
        help="Where to write the per-bug summary CSV.",
    )
    parser.add_argument(
        "--mode-summary-out",
        default="results/layer2_mode_summary.csv",
        help="Where to write the per-bug per-mode summary CSV.",
    )
    parser.add_argument(
      "--master-matrix-out",
      default=str(DEFAULT_MASTER_MATRIX),
      help="Where to write the derived per-row Layer 2 master matrix CSV.",
    )
    parser.add_argument(
      "--relationship-matrix-out",
      default=str(DEFAULT_RELATIONSHIP_MATRIX),
      help="Where to write the compact relationship matrix CSV grouped by bug, mode, and test family.",
    )
    parser.add_argument(
      "--render-chart",
      dest="render_chart",
      action="store_true",
      default=env_flag("LAYER2_RENDER_CHART", True),
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
      default=env_flag("LAYER2_OPEN_CHART", True),
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
      help="Path to the generated chart file to open in the editor. Default: layer2_chart.svg.",
    )
    return parser.parse_args()


def ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def base_test_name(name: str) -> str:
    return RUN_SUFFIX_RE.sub("", name)


def extract_mode(details: str) -> str:
    match = MODE_RE.search(details or "")
    return match.group(1) if match else "unknown"


def extract_run_index(details: str) -> int:
    match = RUN_RE.search(details or "")
    return int(match.group(1)) if match else 1


def extract_detail_map(details: str):
    values = {}
    for key, value in KEY_VALUE_RE.findall(details or ""):
      values[key] = value
    return values


def classify_test_family(base_name: str) -> str:
    if base_name.startswith("invoke_"):
      return "invoke"
    if base_name.startswith("stdin_"):
      return "stdin"
    if base_name.startswith("boundary_len_"):
      return "boundary"
    if base_name.startswith("random_seed_"):
      return "random"
    if base_name.startswith("single_"):
      return "single_byte"
    if base_name.startswith("mixed_"):
      return "mixed_bytes"
    if base_name.startswith("ascii_"):
      return "ascii"
    if base_name.startswith("repeating_"):
      return "pattern"
    return "other"


def build_master_rows(rows):
    master_rows = []

    for row in rows:
      details = extract_detail_map(row.get("details", ""))
      base_name = base_test_name(row["test_name"])
      family = classify_test_family(base_name)
      outcome = row["outcome"]
      failure_kind = row["failure_kind"] or "none"

      master_rows.append({
          "bug_id": row["bug_id"],
          "mode": extract_mode(row.get("details", "")),
          "run_index": extract_run_index(row.get("details", "")),
          "test_name": row["test_name"],
          "base_test_name": base_name,
          "test_family": family,
          "runtime": row.get("runtime", ""),
          "outcome": outcome,
          "failure_kind": failure_kind,
          "detected": "yes" if outcome == "fail" else "no",
          "input_len": details.get("input_len", ""),
          "expected_len": details.get("expected_len", ""),
          "actual_len": details.get("actual_len", ""),
          "invoke_case_id": details.get("invoke_case_id", ""),
          "returned": details.get("returned", ""),
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
      key = (row["bug_id"], row["mode"], row["test_family"])
      stat = grouped[key]
      stat["total_rows"] += 1
      if row["outcome"] == "pass":
        stat["pass_rows"] += 1
      elif row["outcome"] == "fail":
        stat["fail_rows"] += 1
        stat["failure_kinds"][row["failure_kind"]] += 1

    relationship_rows = []
    for (bug_id, mode, test_family) in sorted(grouped):
      stat = grouped[(bug_id, mode, test_family)]
      relationship_rows.append({
          "bug_id": bug_id,
          "mode": mode,
          "test_family": test_family,
          "total_rows": stat["total_rows"],
          "pass_rows": stat["pass_rows"],
          "fail_rows": stat["fail_rows"],
          "detected": "yes" if stat["fail_rows"] > 0 else "no",
          "failure_output_mismatch": stat["failure_kinds"].get("output_mismatch", 0),
          "failure_trap": stat["failure_kinds"].get("trap", 0),
          "failure_exception": stat["failure_kinds"].get("exception", 0),
          "failure_exit_code": stat["failure_kinds"].get("exit_code", 0),
      })

    return relationship_rows


def analyze(rows):
    bug_stats = defaultdict(lambda: {
        "total_rows": 0,
        "pass_rows": 0,
        "fail_rows": 0,
        "skip_rows": 0,
        "failure_kinds": Counter(),
        "modes": set(),
        "max_run_index": 1,
    })
    mode_stats = defaultdict(lambda: {
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
      mode = extract_mode(row["details"])
      run_index = extract_run_index(row["details"])
      test_name = row["test_name"]
      base_name = base_test_name(test_name)

      stat = bug_stats[bug_id]
      stat["total_rows"] += 1
      stat["modes"].add(mode)
      stat["max_run_index"] = max(stat["max_run_index"], run_index)

      mode_stat = mode_stats[(bug_id, mode)]
      mode_stat["total_rows"] += 1

      if outcome == "pass":
        stat["pass_rows"] += 1
        mode_stat["pass_rows"] += 1
      elif outcome == "fail":
        stat["fail_rows"] += 1
        stat["failure_kinds"][failure_kind] += 1
        mode_stat["fail_rows"] += 1
        mode_stat["failure_kinds"][failure_kind] += 1
      else:
        stat["skip_rows"] += 1
        mode_stat["skip_rows"] += 1

      run_groups[(bug_id, mode, base_name)].append(outcome)

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
          "failure_output_mismatch": stat["failure_kinds"].get("output_mismatch", 0),
          "failure_trap": stat["failure_kinds"].get("trap", 0),
          "failure_exception": stat["failure_kinds"].get("exception", 0),
          "failure_exit_code": stat["failure_kinds"].get("exit_code", 0),
          "modes_seen": ";".join(sorted(stat["modes"])),
          "max_run_index": stat["max_run_index"],
          "flaky_tests": flaky_groups,
          "repeated_groups": repeated_groups,
          "flaky_rate": f"{(flaky_groups / repeated_groups):.3f}" if repeated_groups else "0.000",
      })

    mode_summary_rows = []
    for (bug_id, mode) in sorted(mode_stats):
      stat = mode_stats[(bug_id, mode)]
      mode_summary_rows.append({
          "bug_id": bug_id,
          "mode": mode,
          "total_rows": stat["total_rows"],
          "pass_rows": stat["pass_rows"],
          "fail_rows": stat["fail_rows"],
          "skip_rows": stat["skip_rows"],
          "detected": "yes" if stat["fail_rows"] > 0 else "no",
          "failure_output_mismatch": stat["failure_kinds"].get("output_mismatch", 0),
          "failure_trap": stat["failure_kinds"].get("trap", 0),
          "failure_exception": stat["failure_kinds"].get("exception", 0),
          "failure_exit_code": stat["failure_kinds"].get("exit_code", 0),
      })

    return summary_rows, mode_summary_rows


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
    print(f"[Layer2 Analysis] chart_html={args.chart_html}")
    print(f"[Layer2 Analysis] chart_file={args.chart_file}")

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
      print(f"[Layer2 Analysis] chart_open_skipped unsupported_platform={sys.platform}")
      return

    try:
      subprocess.run(opener, check=True)
      print(f"[Layer2 Analysis] chart_opened={chart_path}")
    except Exception as exc:
      print(f"[Layer2 Analysis] chart_open_failed={exc}")


def main() -> int:
    args = parse_args()

    if not os.path.exists(args.csv_path):
      print(f"Missing CSV: {args.csv_path}", file=sys.stderr)
      return 2

    with open(args.csv_path, newline="", encoding="utf-8") as handle:
      reader = csv.DictReader(handle)
      layer2_rows = [row for row in reader if row.get("layer") == "layer2_wasmtime"]

    summary_rows, mode_summary_rows = analyze(layer2_rows)
    master_matrix_rows = build_master_rows(layer2_rows)
    relationship_rows = build_relationship_rows(master_matrix_rows)
    write_csv(args.summary_out, summary_rows)
    write_csv(args.mode_summary_out, mode_summary_rows)
    write_csv(args.master_matrix_out, master_matrix_rows)
    write_csv(args.relationship_matrix_out, relationship_rows)

    print(f"[Layer2 Analysis] source_rows={len(layer2_rows)}")
    print(f"[Layer2 Analysis] summary_csv={args.summary_out}")
    print(f"[Layer2 Analysis] mode_summary_csv={args.mode_summary_out}")
    print(f"[Layer2 Analysis] master_matrix_csv={args.master_matrix_out}")
    print(f"[Layer2 Analysis] relationship_matrix_csv={args.relationship_matrix_out}")

    for row in summary_rows:
      print(
          "[Layer2 Analysis] "
          f"bug_id={row['bug_id']} "
          f"detected={row['detected']} "
          f"fail_rows={row['fail_rows']} "
          f"flaky_rate={row['flaky_rate']} "
          f"modes={row['modes_seen']}"
      )

    maybe_render_chart(args)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())