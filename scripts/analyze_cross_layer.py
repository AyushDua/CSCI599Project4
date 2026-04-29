#!/usr/bin/env python3
"""Cross-layer bug detection analysis.

Reads results/run_results.csv and produces:
  results/cross_layer_matrix.csv    — per (bug_id, layer) pass/fail counts
  results/cross_layer_heatmap.svg   — colour-coded heatmap
  results/cross_layer_report.md     — Markdown summary
"""

import argparse
import csv
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


# ── Constants ────────────────────────────────────────────────────────────────

LAYERS = ["layer1_native", "layer2_wasmtime", "layer3_browser"]
LAYER_LABELS = {
    "layer1_native":   "Layer 1\n(native / GoogleTest)",
    "layer2_wasmtime": "Layer 2\n(Wasmtime / WASI)",
    "layer3_browser":  "Layer 3\n(Browser / Playwright)",
}
REQUIRED_COLS = {"bug_id", "layer", "outcome", "failure_kind"}


# ── Data loading ─────────────────────────────────────────────────────────────

def load_rows(csv_path: str) -> list:
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    if rows:
        missing = REQUIRED_COLS - set(rows[0].keys())
        if missing:
            sys.exit(f"[cross_layer] CSV missing columns: {missing}")
    return rows


def build_matrix(rows: list) -> dict:
    """matrix[bug_id][layer] = {"total", "pass", "fail", "skip", "failure_kinds": Counter}"""
    matrix = defaultdict(lambda: defaultdict(lambda: {
        "total": 0, "pass": 0, "fail": 0, "skip": 0,
        "failure_kinds": Counter()
    }))
    for row in rows:
        bug_id = row.get("bug_id", "").strip()
        layer  = row.get("layer",  "").strip()
        outcome = row.get("outcome", "").strip().lower()
        fkind   = row.get("failure_kind", "").strip() or "none"
        if not bug_id or not layer:
            continue
        cell = matrix[bug_id][layer]
        cell["total"] += 1
        if outcome == "pass":
            cell["pass"] += 1
        elif outcome == "fail":
            cell["fail"] += 1
            cell["failure_kinds"][fkind] += 1
        else:
            cell["skip"] += 1
    return matrix


def sorted_bug_ids(matrix: dict) -> list:
    ids = sorted(matrix.keys())
    # Put CLEAN_* variants first
    clean = [b for b in ids if b.startswith("CLEAN")]
    rest  = [b for b in ids if not b.startswith("CLEAN")]
    return clean + rest


# ── CSV output ───────────────────────────────────────────────────────────────

def write_matrix_csv(matrix: dict, bug_ids: list, out_path: str) -> None:
    fieldnames = [
        "bug_id", "layer", "total", "pass_count", "fail_count", "skip_count",
        "pass_rate", "fail_rate", "detected",
        "fkind_output_mismatch", "fkind_trap", "fkind_exception",
        "fkind_assertion_fail", "fkind_exit_code",
    ]
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for bug_id in bug_ids:
            for layer in LAYERS:
                cell = matrix[bug_id].get(layer)
                if cell is None:
                    continue
                total = cell["total"] or 1
                fk = cell["failure_kinds"]
                w.writerow({
                    "bug_id": bug_id,
                    "layer":  layer,
                    "total":  cell["total"],
                    "pass_count":  cell["pass"],
                    "fail_count":  cell["fail"],
                    "skip_count":  cell["skip"],
                    "pass_rate":   round(cell["pass"] / total, 4),
                    "fail_rate":   round(cell["fail"] / total, 4),
                    "detected":    "yes" if cell["fail"] > 0 else "no",
                    "fkind_output_mismatch": fk.get("output_mismatch", 0),
                    "fkind_trap":            fk.get("trap", 0),
                    "fkind_exception":       fk.get("exception", 0),
                    "fkind_assertion_fail":  fk.get("assertion_fail", 0),
                    "fkind_exit_code":       fk.get("exit_code", 0),
                })
    print(f"[cross_layer] wrote {out_path}")


# ── SVG heatmap ──────────────────────────────────────────────────────────────

def _cell_colour(cell) -> str:
    if cell is None:
        return "#dddddd"  # grey: layer never ran
    fail = cell["fail"]
    total = cell["total"]
    if total == 0 or fail == 0:
        return "#d4edda"  # green: all pass
    if fail == total:
        return "#f8d7da"  # red: all fail
    return "#fff3cd"      # yellow: partial


def _dominant_kind(cell) -> str:
    if cell is None or not cell["failure_kinds"]:
        return ""
    return cell["failure_kinds"].most_common(1)[0][0]


def render_heatmap_svg(matrix: dict, bug_ids: list, out_path: str) -> None:
    CELL_W, CELL_H = 200, 74
    LEFT_PAD, TOP_PAD = 220, 140
    LEGEND_H = 70

    n_bugs   = len(bug_ids)
    n_layers = len(LAYERS)
    width  = LEFT_PAD + n_layers * (CELL_W + 10) + 20
    height = TOP_PAD + n_bugs * (CELL_H + 8) + LEGEND_H + 20

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#f8f9fa"/>',
        # Title
        f'<text x="{width//2}" y="38" text-anchor="middle" '
        f'font-size="17" font-weight="bold" font-family="monospace" fill="#222">'
        f'Cross-Layer Bug Detection Heatmap</text>',
        f'<text x="{width//2}" y="60" text-anchor="middle" '
        f'font-size="11" font-family="sans-serif" fill="#555">'
        f'rows = bug variants  |  cols = testing layers  |  cell = fail / total</text>',
    ]

    # Column headers
    for ci, layer in enumerate(LAYERS):
        cx = LEFT_PAD + ci * (CELL_W + 10) + CELL_W // 2
        label = LAYER_LABELS[layer].replace("\n", "&#10;")
        for li, part in enumerate(LAYER_LABELS[layer].split("\n")):
            lines.append(
                f'<text x="{cx}" y="{95 + li * 18}" text-anchor="middle" '
                f'font-size="12" font-weight="bold" font-family="sans-serif" fill="#333">'
                f'{part}</text>'
            )

    # Rows
    for ri, bug_id in enumerate(bug_ids):
        row_y = TOP_PAD + ri * (CELL_H + 8)

        # Row label
        lines.append(
            f'<text x="{LEFT_PAD - 8}" y="{row_y + CELL_H // 2 + 5}" '
            f'text-anchor="end" font-size="12" font-family="monospace" fill="#222">'
            f'{bug_id}</text>'
        )

        for ci, layer in enumerate(LAYERS):
            cell = matrix[bug_id].get(layer)
            cx   = LEFT_PAD + ci * (CELL_W + 10)
            colour = _cell_colour(cell)

            lines.append(
                f'<rect x="{cx}" y="{row_y}" width="{CELL_W}" height="{CELL_H}" '
                f'rx="10" ry="10" fill="{colour}" stroke="#bbb" stroke-width="1"/>'
            )

            if cell is not None:
                label_main = f"{cell['fail']}/{cell['total']}"
                label_sub  = _dominant_kind(cell)
            else:
                label_main = "—"
                label_sub  = "no data"

            lines.append(
                f'<text x="{cx + CELL_W // 2}" y="{row_y + CELL_H // 2 - 4}" '
                f'text-anchor="middle" font-size="15" font-weight="bold" '
                f'font-family="monospace" fill="#222">{label_main}</text>'
            )
            if label_sub:
                lines.append(
                    f'<text x="{cx + CELL_W // 2}" y="{row_y + CELL_H // 2 + 14}" '
                    f'text-anchor="middle" font-size="10" font-family="sans-serif" '
                    f'fill="#555">{label_sub}</text>'
                )

    # Legend
    legend_y = TOP_PAD + n_bugs * (CELL_H + 8) + 20
    legend_items = [
        ("#d4edda", "All pass (0 failures)"),
        ("#fff3cd", "Partial detection"),
        ("#f8d7da", "All fail (fully detected)"),
        ("#dddddd", "No data (layer not run)"),
    ]
    lx = LEFT_PAD
    for colour, label in legend_items:
        lines.append(f'<rect x="{lx}" y="{legend_y}" width="18" height="18" '
                     f'fill="{colour}" stroke="#aaa" stroke-width="1" rx="3"/>')
        lines.append(f'<text x="{lx + 22}" y="{legend_y + 13}" font-size="11" '
                     f'font-family="sans-serif" fill="#333">{label}</text>')
        lx += 200

    lines.append("</svg>")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"[cross_layer] wrote {out_path}")


# ── Markdown report ──────────────────────────────────────────────────────────

def write_markdown_report(matrix: dict, bug_ids: list, csv_path: str,
                           svg_path: str, out_path: str) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "# Cross-Layer Bug Detection Report",
        "",
        f"Generated: {now}  |  Source: `{csv_path}`",
        "",
        "## Summary Table",
        "",
    ]

    # Table header
    header = "| Bug ID | Layer 1 (fail/total) | Layer 2 (fail/total) | Layer 3 (fail/total) | Best Layer |"
    sep    = "|--------|----------------------|----------------------|----------------------|------------|"
    lines += [header, sep]

    for bug_id in bug_ids:
        cells = []
        best_rate = -1.0
        best_layer = "—"
        for layer in LAYERS:
            cell = matrix[bug_id].get(layer)
            if cell is None:
                cells.append("—")
            else:
                rate = cell["fail"] / cell["total"] if cell["total"] else 0
                cells.append(f"{cell['fail']}/{cell['total']}")
                if rate > best_rate:
                    best_rate = rate
                    best_layer = layer.replace("layer1_native", "Layer 1") \
                                      .replace("layer2_wasmtime", "Layer 2") \
                                      .replace("layer3_browser", "Layer 3")
        if best_rate == 0:
            best_layer = "none"
        lines.append(f"| {bug_id} | {cells[0]} | {cells[1]} | {cells[2]} | {best_layer} |")

    lines += ["", "## Per-Bug Analysis", ""]

    for bug_id in bug_ids:
        lines.append(f"### {bug_id}")
        for layer in LAYERS:
            cell = matrix[bug_id].get(layer)
            if cell is None:
                lines.append(f"- **{layer}**: no data")
            elif cell["fail"] == 0:
                lines.append(f"- **{layer}**: ✓ no failures ({cell['total']} tests passed)")
            else:
                dominant = _dominant_kind(cell)
                lines.append(
                    f"- **{layer}**: {cell['fail']}/{cell['total']} tests failed "
                    f"(dominant: `{dominant}`)"
                )
        lines.append("")

    # Cross-layer observations
    detected_by_layer = {l: 0 for l in LAYERS}
    layer_unique = []
    for bug_id in bug_ids:
        if bug_id.startswith("CLEAN"):
            continue
        detected_in = [l for l in LAYERS if matrix[bug_id].get(l, {}).get("fail", 0) > 0]
        for l in detected_in:
            detected_by_layer[l] += 1
        if len(detected_in) == 1:
            layer_unique.append((bug_id, detected_in[0]))

    lines += [
        "## Cross-Layer Observations",
        "",
        f"- Layer 1 (native) detects **{detected_by_layer['layer1_native']}** bug variant(s).",
        f"- Layer 2 (Wasmtime) detects **{detected_by_layer['layer2_wasmtime']}** bug variant(s).",
        f"- Layer 3 (Browser) detects **{detected_by_layer['layer3_browser']}** bug variant(s).",
    ]
    if layer_unique:
        unique_strs = [f"`{b}` (only in {l.replace('layer','Layer ').replace('_native','').replace('_wasmtime','').replace('_browser','')})"
                       for b, l in layer_unique]
        lines.append(f"- Layer-unique detections: {', '.join(unique_strs)}.")
    else:
        lines.append("- No bug is detectable in exactly one layer.")

    svg_rel = os.path.relpath(svg_path, os.path.dirname(out_path))
    lines += [
        "",
        "## Heatmap",
        "",
        f"![Cross-layer heatmap]({svg_rel})",
        "",
    ]

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"[cross_layer] wrote {out_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Cross-layer bug detection analysis")
    p.add_argument("--csv",     default="results/run_results.csv")
    p.add_argument("--out-dir", default="results/")
    p.add_argument("--no-svg",  action="store_true")
    p.add_argument("--no-md",   action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)

    if not os.path.exists(args.csv):
        print(f"[cross_layer] CSV not found: {args.csv} — skipping")
        return 0

    rows    = load_rows(args.csv)
    matrix  = build_matrix(rows)
    bug_ids = sorted_bug_ids(matrix)

    matrix_csv = str(out_dir / "cross_layer_matrix.csv")
    heatmap_svg = str(out_dir / "cross_layer_heatmap.svg")
    report_md   = str(out_dir / "cross_layer_report.md")

    write_matrix_csv(matrix, bug_ids, matrix_csv)

    if not args.no_svg:
        render_heatmap_svg(matrix, bug_ids, heatmap_svg)

    if not args.no_md:
        write_markdown_report(matrix, bug_ids, args.csv, heatmap_svg, report_md)

    # Console summary
    print("\n[cross_layer] Detection summary:")
    for bug_id in bug_ids:
        row_parts = []
        for layer in LAYERS:
            cell = matrix[bug_id].get(layer)
            if cell is None:
                row_parts.append(f"{layer[:7]}=—")
            else:
                row_parts.append(f"{layer[:7]}={cell['fail']}/{cell['total']}")
        print(f"  {bug_id:<20} {' | '.join(row_parts)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
