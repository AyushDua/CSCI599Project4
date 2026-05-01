#!/usr/bin/env python3
"""Render Layer 1 (native/GoogleTest) charts from run_results.csv.

Produces:
  results/layer1_chart.svg        — dashboard SVG (bug bars + suite bars)
  results/layer1_chart.html       — interactive HTML version
  results/layer1_visual_matrix.svg — bug × test-suite matrix
"""

import csv
import html
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN_RESULTS_CSV = ROOT / "results" / "run_results.csv"
OUT_HTML = ROOT / "results" / "layer1_chart.html"
OUT_SVG  = ROOT / "results" / "layer1_chart.svg"
OUT_MATRIX_SVG = ROOT / "results" / "layer1_visual_matrix.svg"

LAYER = "layer1_native"


def escape(text: str) -> str:
    return html.escape(str(text), quote=True)


# ── Data loading ──────────────────────────────────────────────────────────────

def load_layer1_rows() -> list:
    if not RUN_RESULTS_CSV.exists():
        return []
    with RUN_RESULTS_CSV.open(newline="", encoding="utf-8") as fh:
        return [r for r in csv.DictReader(fh) if r.get("layer", "").strip() == LAYER]


def build_bug_summary(rows: list) -> list:
    """Per bug_id: total, fail, pass, skip counts."""
    counts = defaultdict(lambda: {"total": 0, "fail": 0, "pass": 0, "skip": 0, "bug_id": ""})
    for r in rows:
        bid = r.get("bug_id", "").strip()
        out = r.get("outcome", "").strip().lower()
        if not bid:
            continue
        c = counts[bid]
        c["bug_id"] = bid
        c["total"] += 1
        if out == "fail":
            c["fail"] += 1
        elif out == "pass":
            c["pass"] += 1
        else:
            c["skip"] += 1

    result = []
    clean = [(k, v) for k, v in counts.items() if k.startswith("CLEAN")]
    bugs  = [(k, v) for k, v in counts.items() if not k.startswith("CLEAN")]
    for _, v in sorted(clean) + sorted(bugs):
        total = max(v["total"], 1)
        result.append({
            "bug_id":     v["bug_id"],
            "total_rows": v["total"],
            "fail_rows":  v["fail"],
            "pass_rows":  v["pass"],
            "skip_rows":  v["skip"],
            "detected":   "yes" if v["fail"] > 0 else "no",
            "fail_rate":  round(v["fail"] / total, 4),
        })
    return result


def build_suite_summary(rows: list) -> list:
    """Per test suite (first component of test_name before '.'): totals."""
    counts = defaultdict(lambda: {"total": 0, "fail": 0, "suite": ""})
    for r in rows:
        tname = r.get("test_name", "").strip()
        out   = r.get("outcome", "").strip().lower()
        suite = tname.split(".")[0] if "." in tname else tname
        if not suite:
            continue
        counts[suite]["suite"] = suite
        counts[suite]["total"] += 1
        if out == "fail":
            counts[suite]["fail"] += 1

    return sorted(
        [{"suite": v["suite"], "total_rows": v["total"], "fail_rows": v["fail"]}
         for v in counts.values()],
        key=lambda x: x["suite"]
    )


def build_matrix(rows: list) -> tuple:
    """Returns (bug_ids, suites, matrix[bug_id][suite] = {total, fail})."""
    bug_set   = set()
    suite_set = set()
    data = defaultdict(lambda: defaultdict(lambda: {"total": 0, "fail": 0}))

    for r in rows:
        bid   = r.get("bug_id", "").strip()
        tname = r.get("test_name", "").strip()
        out   = r.get("outcome", "").strip().lower()
        suite = tname.split(".")[0] if "." in tname else tname
        if not bid or not suite:
            continue
        bug_set.add(bid)
        suite_set.add(suite)
        data[bid][suite]["total"] += 1
        if out == "fail":
            data[bid][suite]["fail"] += 1

    clean = sorted(b for b in bug_set if b.startswith("CLEAN"))
    rest  = sorted(b for b in bug_set if not b.startswith("CLEAN"))
    bug_ids = clean + rest
    suites  = sorted(suite_set)
    return bug_ids, suites, data


# ── SVG helpers ───────────────────────────────────────────────────────────────

def _panel_shell(x, y, w, h, fill, stroke):
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="26" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        f'<rect x="{x+18}" y="{y+18}" width="{w-36}" height="{h-36}" '
        f'rx="22" fill="rgba(255,255,255,0.28)"/>'
    )


def _chart_grid(panel_x, panel_y, panel_w, panel_h, title,
                grid_color, axis_color, tick_color, max_value):
    left   = panel_x + 90
    right  = panel_x + panel_w - 60
    top    = panel_y + 78
    bottom = panel_y + panel_h - 78
    parts  = [
        f'<text x="{left}" y="{panel_y+52}" font-size="24" font-weight="700" '
        f'fill="#1f1810">{escape(title)}</text>',
        f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" '
        f'stroke="{axis_color}" stroke-width="2.5"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" '
        f'stroke="{axis_color}" stroke-width="2.5"/>',
    ]
    for tick in range(5):
        value = round(max_value * (4 - tick) / 4)
        y = top + (bottom - top) * tick / 4
        parts.append(f'<line x1="{left}" y1="{y}" x2="{right}" y2="{y}" '
                     f'stroke="{grid_color}" stroke-width="1.2"/>')
        parts.append(f'<text x="{left-14}" y="{y+5}" text-anchor="end" '
                     f'font-size="13" fill="{tick_color}">{value}</text>')
    return "".join(parts), left, right, top, bottom


# ── Dashboard SVG ─────────────────────────────────────────────────────────────

def render_dashboard_svg(bug_rows: list, suite_rows: list) -> str:
    width        = 1400
    margin       = 70
    panel_w      = width - margin * 2
    bug_panel_y  = 160
    panel_h      = 390
    suite_panel_y = bug_panel_y + panel_h + 34
    card_y       = suite_panel_y + panel_h + 34
    card_h       = max(190, 170 + max(0, len(bug_rows) - 1) * 150)
    height       = card_y + card_h + 50

    max_bug   = max([r["total_rows"] for r in bug_rows]   + [1])
    max_suite = max([r["total_rows"] for r in suite_rows] + [1])

    def bug_bars():
        grid, left, right, top, bottom = _chart_grid(
            margin, bug_panel_y, panel_w, panel_h,
            "Layer 1 Total Rows by Bug Variant",
            "#e2dccf", "#8a8478", "#574f45", max_bug)
        chart_w = right - left
        chart_h = bottom - top
        bar_gap  = 20
        bar_w    = min(120, max(40, (chart_w - bar_gap * max(len(bug_rows)-1, 0))
                                    // max(len(bug_rows), 1)))
        start_x  = left + max(0, (chart_w - (len(bug_rows)*bar_w + max(len(bug_rows)-1,0)*bar_gap)) / 2)
        parts    = [_panel_shell(margin, bug_panel_y, panel_w, panel_h, "#fffaf0", "#d9cdb6"), grid]
        for i, row in enumerate(bug_rows):
            total = row["total_rows"]; fail = row["fail_rows"]
            bh  = 0 if max_bug == 0 else chart_h * total / max_bug
            x   = start_x + i * (bar_w + bar_gap)
            y   = bottom - bh
            clr = "#2f7d4a" if fail == 0 else "#d95f02"
            parts += [
                f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" rx="10" fill="{clr}"/>',
                f'<text x="{x+bar_w/2}" y="{y-10}" text-anchor="middle" font-size="13" '
                f'font-weight="700" fill="#2f2419">{total}</text>',
                f'<text x="{x+bar_w/2}" y="{bottom+30}" text-anchor="middle" font-size="12" '
                f'font-weight="700" fill="#2f2419">{escape(row["bug_id"])}</text>',
                f'<text x="{x+bar_w/2}" y="{bottom+50}" text-anchor="middle" font-size="11" '
                f'fill="#574f45">fail={fail}</text>',
            ]
        return "".join(parts)

    def suite_bars():
        grid, left, right, top, bottom = _chart_grid(
            margin, suite_panel_y, panel_w, panel_h,
            "Layer 1 Total Rows by Test Suite",
            "#d9e5f0", "#7b8794", "#35526b", max_suite)
        chart_w = right - left
        chart_h = bottom - top
        bar_gap  = 14
        bar_w    = min(140, max(36, (chart_w - bar_gap * max(len(suite_rows)-1, 0))
                                     // max(len(suite_rows), 1)))
        start_x  = left + max(0, (chart_w - (len(suite_rows)*bar_w + max(len(suite_rows)-1,0)*bar_gap)) / 2)
        parts    = [_panel_shell(margin, suite_panel_y, panel_w, panel_h, "#f7fbff", "#cbd9e6"), grid]
        for i, row in enumerate(suite_rows):
            total = row["total_rows"]; fail = row["fail_rows"]
            bh  = 0 if max_suite == 0 else chart_h * total / max_suite
            x   = start_x + i * (bar_w + bar_gap)
            y   = bottom - bh
            clr = "#c44536" if fail else "#5b84e3"
            parts += [
                f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" rx="10" fill="{clr}"/>',
                f'<text x="{x+bar_w/2}" y="{y-10}" text-anchor="middle" font-size="12" '
                f'font-weight="700" fill="#1d2d3c">{total}</text>',
                f'<text x="{x+bar_w/2}" y="{bottom+30}" text-anchor="middle" font-size="11" '
                f'font-weight="700" fill="#1d2d3c" transform="rotate(-35,{x+bar_w/2},{bottom+30})">'
                f'{escape(row["suite"])}</text>',
                f'<text x="{x+bar_w/2}" y="{bottom+52}" text-anchor="middle" font-size="10" '
                f'fill="#35526b">fail={fail}</text>',
            ]
        return "".join(parts)

    def stat_cards():
        cx = margin
        parts = []
        for i, row in enumerate(bug_rows):
            y = card_y + i * 150
            parts.append(
                f'<rect x="{cx}" y="{y}" width="{panel_w}" height="130" rx="26" '
                f'fill="#ffffff" stroke="#d9cdb6" stroke-width="2"/>'
                f'<text x="{cx+28}" y="{y+42}" font-size="28" font-weight="700" '
                f'fill="#20180f">{escape(row["bug_id"])}</text>'
                f'<text x="{cx+28}" y="{y+84}" font-size="22" fill="#5a4d40">'
                f'<tspan font-weight="700">Detected:</tspan> {escape(row["detected"])}</text>'
                f'<text x="{cx+28}" y="{y+112}" font-size="22" fill="#5a4d40">'
                f'<tspan font-weight="700">Total rows:</tspan> {row["total_rows"]}</text>'
                f'<text x="{cx+500}" y="{y+84}" font-size="22" fill="#5a4d40">'
                f'<tspan font-weight="700">Fail rows:</tspan> {row["fail_rows"]}</text>'
                f'<text x="{cx+500}" y="{y+112}" font-size="22" fill="#5a4d40">'
                f'<tspan font-weight="700">Fail rate:</tspan> {row["fail_rate"]:.1%}</text>'
            )
        return "".join(parts)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" '
        f'aria-label="Layer 1 native chart dashboard" style="font-family: Helvetica, Arial, sans-serif;">'
        '<defs>'
        '<linearGradient id="bg" x1="0" x2="0" y1="0" y2="1">'
        '<stop offset="0%" stop-color="#f6f1e7"/>'
        '<stop offset="100%" stop-color="#efe6d7"/>'
        '</linearGradient>'
        '</defs>'
        f'<rect width="{width}" height="{height}" fill="url(#bg)"/>'
        f'<text x="{margin}" y="88" font-size="48" font-weight="700" fill="#20180f">'
        'Layer 1 Native Charts</text>'
        f'<text x="{margin}" y="126" font-size="22" fill="#5a4d40">'
        'Auto-generated from results/run_results.csv (layer1_native).</text>'
        f'{bug_bars()}'
        f'{suite_bars()}'
        f'{stat_cards()}'
        '</svg>'
    )


# ── Visual matrix SVG ─────────────────────────────────────────────────────────

def render_matrix_svg(bug_ids: list, suites: list, data: dict) -> str:
    cell_w = 130
    cell_h = 72
    left   = 200
    top    = 200

    width  = max(1200, left + len(suites) * (cell_w + 8) + 40)
    height = max(520,  top  + len(bug_ids) * (cell_h + 8) + 80)

    def cell_fill(cell):
        if cell is None:
            return "#e8e8e8"
        if cell["fail"] == 0:
            return "#dff3e4"
        if cell["fail"] == cell["total"]:
            return "#f8c4b4"
        return "#fde3b4"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" '
        f'aria-label="Layer 1 visual matrix" style="font-family: Helvetica, Arial, sans-serif;">',
        '<defs>',
        '<linearGradient id="matrixbg" x1="0" x2="0" y1="0" y2="1">',
        '  <stop offset="0%" stop-color="#f6f1e7"/>',
        '  <stop offset="100%" stop-color="#efe6d7"/>',
        '</linearGradient>',
        '</defs>',
        f'<rect width="{width}" height="{height}" fill="url(#matrixbg)"/>',
        f'<text x="60" y="72" font-size="44" font-weight="700" fill="#20180f">Layer 1 Visual Matrix</text>',
        f'<text x="60" y="108" font-size="20" fill="#5a4d40">'
        f'Rows = bug variants  |  cols = test suites  |  cells = fail/total</text>',
        f'<rect x="40" y="130" width="{width-80}" height="{height-170}" '
        f'rx="24" fill="#fffaf0" stroke="#d9cdb6" stroke-width="2"/>',
    ]

    # Column headers (rotated)
    for ci, suite in enumerate(suites):
        x = left + ci * (cell_w + 8) + cell_w // 2
        parts.append(
            f'<text x="{x}" y="{top - 14}" text-anchor="middle" '
            f'font-size="12" font-weight="700" fill="#333" '
            f'transform="rotate(-40,{x},{top-14})">{escape(suite)}</text>'
        )

    # Rows
    for ri, bug_id in enumerate(bug_ids):
        y = top + ri * (cell_h + 8)
        parts.append(
            f'<text x="{left-12}" y="{y + cell_h//2 + 5}" text-anchor="end" '
            f'font-size="14" font-weight="700" fill="#20180f">{escape(bug_id)}</text>'
        )
        for ci, suite in enumerate(suites):
            x    = left + ci * (cell_w + 8)
            cell = data[bug_id].get(suite)
            fill = cell_fill(cell)
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" '
                f'rx="12" fill="{fill}" stroke="#d3c7b4" stroke-width="1"/>'
            )
            if cell:
                label = f"{cell['fail']}/{cell['total']}"
                parts.append(
                    f'<text x="{x + cell_w//2}" y="{y + cell_h//2 + 6}" '
                    f'text-anchor="middle" font-size="15" font-weight="700" fill="#20180f">'
                    f'{escape(label)}</text>'
                )
            else:
                parts.append(
                    f'<text x="{x + cell_w//2}" y="{y + cell_h//2 + 6}" '
                    f'text-anchor="middle" font-size="13" fill="#888">—</text>'
                )

    # Legend
    legend_y = top + len(bug_ids) * (cell_h + 8) + 18
    for i, (fill, label) in enumerate([
        ("#dff3e4", "0 fail"), ("#fde3b4", "partial fail"),
        ("#f8c4b4", "all fail"), ("#e8e8e8", "no data"),
    ]):
        lx = left + i * 200
        parts += [
            f'<rect x="{lx}" y="{legend_y}" width="20" height="20" '
            f'rx="5" fill="{fill}" stroke="#cbbfa9"/>',
            f'<text x="{lx+28}" y="{legend_y+15}" font-size="14" fill="#5a4d40">{label}</text>',
        ]

    parts.append("</svg>")
    return "\n".join(parts)


# ── HTML dashboard ────────────────────────────────────────────────────────────

def build_html(bug_rows: list, suite_rows: list) -> str:
    def bug_chart_svg():
        width = 820; height = 320
        left = 90; right = 30; top = 30; bottom = 70
        ch = height - top - bottom
        cw = width - left - right
        max_v = max([r["total_rows"] for r in bug_rows] + [1])
        bar_gap = 20
        bar_w = min(130, max(40, (cw - bar_gap * (len(bug_rows)-1)) // max(len(bug_rows), 1)))
        parts = [
            f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Layer 1 bug chart">',
            f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fffdf7" rx="18"/>',
            f'<line x1="{left}" y1="{top+ch}" x2="{width-right}" y2="{top+ch}" stroke="#3b3b3b" stroke-width="2"/>',
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+ch}" stroke="#3b3b3b" stroke-width="2"/>',
            f'<text x="{left}" y="18" font-size="18" font-family="Helvetica,Arial,sans-serif" '
            f'font-weight="700">Layer 1 Total Rows by Bug Variant</text>',
        ]
        for tick in range(5):
            val = round(max_v * tick / 4)
            y = top + ch - (ch * tick / 4)
            parts += [
                f'<line x1="{left}" y1="{y}" x2="{width-right}" y2="{y}" stroke="#e2dccf" stroke-width="1"/>',
                f'<text x="{left-10}" y="{y+5}" text-anchor="end" font-size="12" fill="#574f45">{val}</text>',
            ]
        start_x = left + max(0, (cw - (len(bug_rows)*bar_w + (len(bug_rows)-1)*bar_gap)) / 2)
        for i, row in enumerate(bug_rows):
            total = row["total_rows"]; fail = row["fail_rows"]
            bh  = 0 if max_v == 0 else ch * total / max_v
            x   = start_x + i * (bar_w + bar_gap)
            y   = top + ch - bh
            clr = "#d95f02" if fail else "#2f7d4a"
            parts += [
                f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" rx="10" fill="{clr}"/>',
                f'<text x="{x+bar_w/2}" y="{y-8}" text-anchor="middle" font-size="13" '
                f'font-weight="700" fill="#2f2419">{total}</text>',
                f'<text x="{x+bar_w/2}" y="{top+ch+24}" text-anchor="middle" font-size="12" '
                f'font-weight="700" fill="#2f2419">{escape(row["bug_id"])}</text>',
                f'<text x="{x+bar_w/2}" y="{top+ch+42}" text-anchor="middle" font-size="11" '
                f'fill="#574f45">fail={fail}</text>',
            ]
        parts.append("</svg>")
        return "\n".join(parts)

    def suite_chart_svg():
        width = 820; height = 320
        left = 90; right = 30; top = 30; bottom = 80
        ch = height - top - bottom
        cw = width - left - right
        max_v = max([r["total_rows"] for r in suite_rows] + [1])
        bar_gap = 12
        bar_w = min(100, max(28, (cw - bar_gap * (len(suite_rows)-1)) // max(len(suite_rows), 1)))
        parts = [
            f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Layer 1 suite chart">',
            f'<rect x="0" y="0" width="{width}" height="{height}" fill="#f7fbff" rx="18"/>',
            f'<line x1="{left}" y1="{top+ch}" x2="{width-right}" y2="{top+ch}" stroke="#3b3b3b" stroke-width="2"/>',
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+ch}" stroke="#3b3b3b" stroke-width="2"/>',
            f'<text x="{left}" y="18" font-size="18" font-family="Helvetica,Arial,sans-serif" '
            f'font-weight="700">Layer 1 Total Rows by Test Suite</text>',
        ]
        for tick in range(5):
            val = round(max_v * tick / 4)
            y = top + ch - (ch * tick / 4)
            parts += [
                f'<line x1="{left}" y1="{y}" x2="{width-right}" y2="{y}" stroke="#d9e5f0" stroke-width="1"/>',
                f'<text x="{left-10}" y="{y+5}" text-anchor="end" font-size="12" fill="#35526b">{val}</text>',
            ]
        start_x = left + max(0, (cw - (len(suite_rows)*bar_w + (len(suite_rows)-1)*bar_gap)) / 2)
        for i, row in enumerate(suite_rows):
            total = row["total_rows"]; fail = row["fail_rows"]
            bh  = 0 if max_v == 0 else ch * total / max_v
            x   = start_x + i * (bar_w + bar_gap)
            y   = top + ch - bh
            clr = "#c44536" if fail else "#5b8def"
            parts += [
                f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" rx="10" fill="{clr}"/>',
                f'<text x="{x+bar_w/2}" y="{y-8}" text-anchor="middle" font-size="11" '
                f'font-weight="700" fill="#1d2d3c">{total}</text>',
                f'<text x="{x+bar_w/2}" y="{top+ch+20}" text-anchor="middle" font-size="9" '
                f'font-weight="700" fill="#1d2d3c" '
                f'transform="rotate(-40,{x+bar_w/2},{top+ch+20})">{escape(row["suite"])}</text>',
                f'<text x="{x+bar_w/2}" y="{top+ch+58}" text-anchor="middle" font-size="10" '
                f'fill="#35526b">fail={fail}</text>',
            ]
        parts.append("</svg>")
        return "\n".join(parts)

    cards = "".join(
        f'<div class="card">'
        f'<h3>{escape(r["bug_id"])}</h3>'
        f'<p><strong>Detected:</strong> {escape(r["detected"])}</p>'
        f'<p><strong>Total rows:</strong> {r["total_rows"]}</p>'
        f'<p><strong>Fail rows:</strong> {r["fail_rows"]}</p>'
        f'<p><strong>Fail rate:</strong> {r["fail_rate"]:.1%}</p>'
        f'</div>'
        for r in bug_rows
    )

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
    <title>Layer 1 Charts</title>
    <style>
      :root {{ color-scheme: light; --ink: #20180f; --muted: #5a4d40;
               --paper: #f3efe6; --panel: #fffaf0; --line: #d9cdb6; }}
      * {{ box-sizing: border-box; }}
      body {{ margin: 0; font-family: Helvetica, Arial, sans-serif; color: var(--ink);
              background: linear-gradient(180deg, #f6f1e7 0%, #efe6d7 100%); }}
      main {{ max-width: 980px; margin: 0 auto; padding: 32px 20px 48px; }}
      h1 {{ margin: 0 0 10px; font-size: 40px; line-height: 1.05; }}
      p.lead {{ margin: 0 0 24px; color: var(--muted); font-size: 18px; }}
      section {{ margin-top: 24px; }}
      .panel {{ background: var(--panel); border: 1px solid var(--line);
                border-radius: 22px; padding: 18px;
                box-shadow: 0 14px 30px rgba(64,46,25,0.08); }}
      .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; }}
      .card {{ background: #fff; border: 1px solid var(--line); border-radius: 16px; padding: 14px; }}
      .card h3 {{ margin: 0 0 10px; font-size: 18px; }}
      .card p {{ margin: 6px 0; color: var(--muted); }}
      svg {{ width: 100%; height: auto; display: block; }}
    </style>
  </head>
  <body>
    <main>
      <h1>Layer 1 Native Charts</h1>
      <p class="lead">Auto-generated from results/run_results.csv (layer1_native).</p>
      <section class="panel">{bug_chart_svg()}</section>
      <section class="panel">{suite_chart_svg()}</section>
      <section class="cards">{cards}</section>
    </main>
  </body>
</html>
"""


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    rows = load_layer1_rows()
    if not rows:
        print(f"[Layer1 Chart] No layer1_native rows found in {RUN_RESULTS_CSV} — skipping")
        return

    bug_rows   = build_bug_summary(rows)
    suite_rows = build_suite_summary(rows)
    bug_ids, suites, matrix_data = build_matrix(rows)

    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(build_html(bug_rows, suite_rows), encoding="utf-8")
    OUT_SVG.write_text(render_dashboard_svg(bug_rows, suite_rows), encoding="utf-8")
    OUT_MATRIX_SVG.write_text(render_matrix_svg(bug_ids, suites, matrix_data), encoding="utf-8")

    print(f"[Layer1 Chart] wrote {OUT_HTML}")
    print(f"[Layer1 Chart] wrote {OUT_SVG}")
    print(f"[Layer1 Chart] wrote {OUT_MATRIX_SVG}")


if __name__ == "__main__":
    main()
