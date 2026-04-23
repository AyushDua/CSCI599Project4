#!/usr/bin/env python3
import csv
import html
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SUMMARY_CSV = ROOT / "results" / "layer2_summary.csv"
MODE_SUMMARY_CSV = ROOT / "results" / "layer2_mode_summary.csv"
RELATIONSHIP_MATRIX_CSV = ROOT / "results" / "layer2_relationship_matrix.csv"
OUT_HTML = ROOT / "results" / "layer2_chart.html"
OUT_SVG = ROOT / "results" / "layer2_chart.svg"
OUT_MATRIX_SVG = ROOT / "results" / "layer2_visual_matrix.svg"


def read_csv(path: Path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def to_int(row, key):
    value = row.get(key, "0")
    try:
        return int(value)
    except ValueError:
        return 0


def to_float(row, key):
    value = row.get(key, "0")
    try:
        return float(value)
    except ValueError:
        return 0.0


def escape(text: str) -> str:
    return html.escape(text, quote=True)


def render_relationship_matrix_svg(rows):
  bug_ids = sorted({row.get("bug_id", "unknown") for row in rows})
  column_keys = sorted(
    {(row.get("mode", "unknown"), row.get("test_family", "other")) for row in rows},
    key=lambda item: (item[0], item[1]),
  )
  row_map = {
    (row.get("bug_id", "unknown"), row.get("mode", "unknown"), row.get("test_family", "other")): row
    for row in rows
  }

  width = max(1200, 280 + len(column_keys) * 135)
  height = max(520, 280 + len(bug_ids) * 110)
  left = 210
  top = 170
  cell_w = 125
  cell_h = 86

  def cell_fill(row):
    fail_rows = to_int(row, "fail_rows")
    total_rows = max(to_int(row, "total_rows"), 1)
    if fail_rows == 0:
      return "#dff3e4"
    if fail_rows == total_rows:
      return "#f8c4b4"
    return "#fde3b4"

  def cell_text(row):
    total_rows = to_int(row, "total_rows")
    fail_rows = to_int(row, "fail_rows")
    return f"{fail_rows}/{total_rows} fail"

  matrix_parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="Layer 2 visual matrix" style="font-family: Helvetica, Arial, sans-serif;">',
    '<defs>',
    '  <linearGradient id="matrixbg" x1="0" x2="0" y1="0" y2="1">',
    '    <stop offset="0%" stop-color="#f6f1e7"/>',
    '    <stop offset="100%" stop-color="#efe6d7"/>',
    '  </linearGradient>',
    '</defs>',
    f'<rect width="{width}" height="{height}" fill="url(#matrixbg)"/>',
    '<text x="60" y="76" font-size="48" font-weight="700" fill="#20180f">Layer 2 Visual Matrix</text>',
    '<text x="60" y="114" font-size="22" fill="#5a4d40">Rows = bug variants, columns = execution mode + test family, cells = fail/total.</text>',
    f'<rect x="40" y="140" width="{width - 80}" height="{height - 180}" rx="28" fill="#fffaf0" stroke="#d9cdb6" stroke-width="2"/>',
  ]

  legend_y = height - 78
  legend = [
    ("#dff3e4", "0 fail"),
    ("#fde3b4", "partial fail"),
    ("#f8c4b4", "all fail"),
  ]
  for index, (fill, label) in enumerate(legend):
    lx = 60 + index * 220
    matrix_parts.append(f'<rect x="{lx}" y="{legend_y}" width="24" height="24" rx="6" fill="{fill}" stroke="#cbbfa9"/>')
    matrix_parts.append(f'<text x="{lx + 36}" y="{legend_y + 18}" font-size="18" fill="#5a4d40">{label}</text>')

  for col_index, (mode, family) in enumerate(column_keys):
    x = left + col_index * cell_w
    matrix_parts.append(f'<text x="{x + cell_w / 2}" y="{top - 38}" text-anchor="middle" font-size="16" font-weight="700" fill="#1f1810">{escape(mode)}</text>')
    matrix_parts.append(f'<text x="{x + cell_w / 2}" y="{top - 16}" text-anchor="middle" font-size="14" fill="#5a4d40">{escape(family)}</text>')

  for row_index, bug_id in enumerate(bug_ids):
    y = top + row_index * cell_h
    matrix_parts.append(f'<text x="{left - 18}" y="{y + 48}" text-anchor="end" font-size="18" font-weight="700" fill="#20180f">{escape(bug_id)}</text>')
    for col_index, (mode, family) in enumerate(column_keys):
      x = left + col_index * cell_w
      row = row_map.get((bug_id, mode, family))
      fill = "#f3eee4"
      primary = "n/a"
      secondary = ""
      if row is not None:
        fill = cell_fill(row)
        primary = cell_text(row)
        if to_int(row, "failure_output_mismatch") > 0:
          secondary = f"mismatch={to_int(row, 'failure_output_mismatch')}"
        elif to_int(row, "failure_trap") > 0:
          secondary = f"trap={to_int(row, 'failure_trap')}"
        elif to_int(row, "failure_exception") > 0:
          secondary = f"exception={to_int(row, 'failure_exception')}"
        elif to_int(row, "failure_exit_code") > 0:
          secondary = f"exit={to_int(row, 'failure_exit_code')}"
        else:
          secondary = "detected=no"

      matrix_parts.append(f'<rect x="{x}" y="{y}" width="{cell_w - 8}" height="{cell_h - 10}" rx="14" fill="{fill}" stroke="#d3c7b4"/>')
      matrix_parts.append(f'<text x="{x + (cell_w - 8) / 2}" y="{y + 35}" text-anchor="middle" font-size="16" font-weight="700" fill="#20180f">{escape(primary)}</text>')
      matrix_parts.append(f'<text x="{x + (cell_w - 8) / 2}" y="{y + 58}" text-anchor="middle" font-size="12" fill="#5a4d40">{escape(secondary)}</text>')

  matrix_parts.append('</svg>')
  return "\n".join(matrix_parts)


def render_dashboard_svg(summary_rows, mode_rows):
  width = 1400
  page_margin = 70
  panel_width = width - page_margin * 2
  bug_panel_y = 160
  panel_height = 390
  mode_panel_y = bug_panel_y + panel_height + 34
  card_y = mode_panel_y + panel_height + 34
  card_height = max(190, 170 + max(0, len(summary_rows) - 1) * 150)
  height = card_y + card_height + 50
  max_summary = max([to_int(row, "total_rows") for row in summary_rows] + [1])
  max_mode = max([to_int(row, "total_rows") for row in mode_rows] + [1])

  def panel_shell(x, y, w, h, fill, stroke):
    return "".join([
      f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="26" fill="{fill}" stroke="{stroke}" stroke-width="2"/>',
      f'<rect x="{x + 18}" y="{y + 18}" width="{w - 36}" height="{h - 36}" rx="22" fill="rgba(255,255,255,0.28)"/>',
    ])

  def chart_grid(panel_x, panel_y, panel_w, panel_h, title, grid_color, axis_color, tick_color, max_value):
    left = panel_x + 90
    right = panel_x + panel_w - 60
    top = panel_y + 78
    bottom = panel_y + panel_h - 78
    parts = [
      f'<text x="{left}" y="{panel_y + 52}" font-size="24" font-weight="700" fill="#1f1810">{escape(title)}</text>',
      f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="{axis_color}" stroke-width="2.5"/>',
      f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="{axis_color}" stroke-width="2.5"/>',
    ]
    for tick in range(5):
      value = round(max_value * (4 - tick) / 4)
      y = top + (bottom - top) * tick / 4
      parts.append(f'<line x1="{left}" y1="{y}" x2="{right}" y2="{y}" stroke="{grid_color}" stroke-width="1.2"/>')
      parts.append(f'<text x="{left - 14}" y="{y + 5}" text-anchor="end" font-size="13" fill="{tick_color}">{value}</text>')
    return "".join(parts), left, right, top, bottom

  def bug_bars():
    panel_x = page_margin
    panel_y = bug_panel_y
    panel_w = panel_width
    panel_h = panel_height
    grid, left, right, top, bottom = chart_grid(
      panel_x,
      panel_y,
      panel_w,
      panel_h,
      "Layer 2 Total Rows by Bug Variant",
      "#e2dccf",
      "#8a8478",
      "#574f45",
      max_summary,
    )
    chart_w = right - left
    chart_h = bottom - top
    bar_gap = 34
    bar_width = min(160, max(72, (chart_w - bar_gap * max(len(summary_rows) - 1, 0)) / max(len(summary_rows), 1)))
    start_x = left + max(0, (chart_w - (len(summary_rows) * bar_width + max(len(summary_rows) - 1, 0) * bar_gap)) / 2)
    parts = [panel_shell(panel_x, panel_y, panel_w, panel_h, "#fffaf0", "#d9cdb6"), grid]
    for index, row in enumerate(summary_rows):
      total = to_int(row, "total_rows")
      fail = to_int(row, "fail_rows")
      flaky = to_float(row, "flaky_rate")
      bar_height = 0 if max_summary == 0 else chart_h * total / max_summary
      x = start_x + index * (bar_width + bar_gap)
      y = bottom - bar_height
      color = "#2f7d4a" if fail == 0 else "#d95f02"
      parts.extend([
        f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}" rx="12" fill="{color}"/>',
        f'<text x="{x + bar_width / 2}" y="{y - 10}" text-anchor="middle" font-size="14" font-weight="700" fill="#2f2419">{total}</text>',
        f'<text x="{x + bar_width / 2}" y="{bottom + 30}" text-anchor="middle" font-size="14" font-weight="700" fill="#2f2419">{escape(row.get("bug_id", "unknown"))}</text>',
        f'<text x="{x + bar_width / 2}" y="{bottom + 56}" text-anchor="middle" font-size="13" fill="#574f45">fail={fail} flaky={flaky:.3f}</text>',
      ])
    return "".join(parts)

  def mode_bars():
    panel_x = page_margin
    panel_y = mode_panel_y
    panel_w = panel_width
    panel_h = panel_height
    grid, left, right, top, bottom = chart_grid(
      panel_x,
      panel_y,
      panel_w,
      panel_h,
      "Layer 2 Total Rows by Execution Mode",
      "#d9e5f0",
      "#7b8794",
      "#35526b",
      max_mode,
    )
    chart_w = right - left
    chart_h = bottom - top
    bar_gap = 34
    bar_width = min(180, max(72, (chart_w - bar_gap * max(len(mode_rows) - 1, 0)) / max(len(mode_rows), 1)))
    start_x = left + max(0, (chart_w - (len(mode_rows) * bar_width + max(len(mode_rows) - 1, 0) * bar_gap)) / 2)
    parts = [panel_shell(panel_x, panel_y, panel_w, panel_h, "#f7fbff", "#cbd9e6"), grid]
    for index, row in enumerate(mode_rows):
      total = to_int(row, "total_rows")
      fail = to_int(row, "fail_rows")
      bar_height = 0 if max_mode == 0 else chart_h * total / max_mode
      x = start_x + index * (bar_width + bar_gap)
      y = bottom - bar_height
      color = "#5b84e3" if row.get("mode") == "start" else "#20b2aa"
      if fail:
        color = "#c44536"
      label = f"{row.get('bug_id', 'unknown')} / {row.get('mode', 'unknown')}"
      parts.extend([
        f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}" rx="12" fill="{color}"/>',
        f'<text x="{x + bar_width / 2}" y="{y - 10}" text-anchor="middle" font-size="14" font-weight="700" fill="#1d2d3c">{total}</text>',
        f'<text x="{x + bar_width / 2}" y="{bottom + 30}" text-anchor="middle" font-size="14" font-weight="700" fill="#1d2d3c">{escape(label)}</text>',
        f'<text x="{x + bar_width / 2}" y="{bottom + 56}" text-anchor="middle" font-size="13" fill="#35526b">fail={fail}</text>',
      ])
    return "".join(parts)

  def stat_cards():
    card_x = page_margin
    card_width = panel_width
    line_height = 42
    parts = []
    for index, row in enumerate(summary_rows):
      y = card_y + index * 150
      parts.append(
        "".join([
          f'<rect x="{card_x}" y="{y}" width="{card_width}" height="130" rx="26" fill="#ffffff" stroke="#d9cdb6" stroke-width="2"/>',
          f'<text x="{card_x + 28}" y="{y + 42}" font-size="28" font-weight="700" fill="#20180f">{escape(row.get("bug_id", "unknown"))}</text>',
          f'<text x="{card_x + 28}" y="{y + 42 + line_height}" font-size="22" fill="#5a4d40"><tspan font-weight="700">Detected:</tspan> {escape(row.get("detected", "no"))}</text>',
          f'<text x="{card_x + 28}" y="{y + 42 + line_height * 2}" font-size="22" fill="#5a4d40"><tspan font-weight="700">Total rows:</tspan> {escape(row.get("total_rows", "0"))}</text>',
          f'<text x="{card_x + 500}" y="{y + 42 + line_height}" font-size="22" fill="#5a4d40"><tspan font-weight="700">Modes:</tspan> {escape(row.get("modes_seen", "unknown"))}</text>',
          f'<text x="{card_x + 500}" y="{y + 42 + line_height * 2}" font-size="22" fill="#5a4d40"><tspan font-weight="700">Flaky rate:</tspan> {escape(row.get("flaky_rate", "0.000"))}</text>',
        ])
      )
    return "".join(parts)

  return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="Layer 2 Wasmtime chart dashboard" style="font-family: Helvetica, Arial, sans-serif;">
  <defs>
    <linearGradient id="bg" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%" stop-color="#f6f1e7"/>
      <stop offset="100%" stop-color="#efe6d7"/>
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" fill="url(#bg)"/>
  <text x="{page_margin}" y="88" font-size="48" font-weight="700" fill="#20180f">Layer 2 Wasmtime Charts</text>
  <text x="{page_margin}" y="126" font-size="22" fill="#5a4d40">Auto-generated from layer2_summary.csv and layer2_mode_summary.csv.</text>

  {bug_bars()}
  {mode_bars()}
  {stat_cards()}
</svg>'''


def render_bug_chart(summary_rows):
    width = 820
    height = 320
    left = 90
    right = 30
    top = 30
    bottom = 70
    chart_height = height - top - bottom
    chart_width = width - left - right
    max_value = max([to_int(row, "total_rows") for row in summary_rows] + [1])
    bar_gap = 24
    bar_width = min(140, max(48, (chart_width - bar_gap * (len(summary_rows) - 1)) // max(len(summary_rows), 1)))

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Layer 2 bug summary chart">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fffdf7" rx="18"/>',
        f'<line x1="{left}" y1="{top + chart_height}" x2="{width - right}" y2="{top + chart_height}" stroke="#3b3b3b" stroke-width="2"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + chart_height}" stroke="#3b3b3b" stroke-width="2"/>',
        f'<text x="{left}" y="18" font-size="18" font-family="Helvetica, Arial, sans-serif" font-weight="700">Layer 2 Total Rows by Bug Variant</text>',
    ]

    for tick in range(5):
        value = round(max_value * tick / 4)
        y = top + chart_height - (chart_height * tick / 4)
        parts.append(f'<line x1="{left}" y1="{y}" x2="{width - right}" y2="{y}" stroke="#e2dccf" stroke-width="1"/>')
        parts.append(f'<text x="{left - 10}" y="{y + 5}" text-anchor="end" font-size="12" fill="#574f45">{value}</text>')

    start_x = left + max(0, (chart_width - (len(summary_rows) * bar_width + (len(summary_rows) - 1) * bar_gap)) / 2)
    for index, row in enumerate(summary_rows):
        total = to_int(row, "total_rows")
        fail = to_int(row, "fail_rows")
        flaky = to_float(row, "flaky_rate")
        bar_height = 0 if max_value == 0 else chart_height * total / max_value
        x = start_x + index * (bar_width + bar_gap)
        y = top + chart_height - bar_height
        color = "#d95f02" if fail else "#2f7d4a"
        parts.append(f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}" rx="10" fill="{color}"/>')
        parts.append(f'<text x="{x + bar_width / 2}" y="{y - 8}" text-anchor="middle" font-size="13" font-weight="700" fill="#2f2419">{total}</text>')
        parts.append(f'<text x="{x + bar_width / 2}" y="{top + chart_height + 24}" text-anchor="middle" font-size="13" font-weight="700" fill="#2f2419">{escape(row.get("bug_id", "unknown"))}</text>')
        parts.append(f'<text x="{x + bar_width / 2}" y="{top + chart_height + 44}" text-anchor="middle" font-size="12" fill="#574f45">fail={fail} flaky={flaky:.3f}</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def render_mode_chart(mode_rows):
    width = 820
    height = 320
    left = 90
    right = 30
    top = 30
    bottom = 70
    chart_height = height - top - bottom
    chart_width = width - left - right
    max_value = max([to_int(row, "total_rows") for row in mode_rows] + [1])
    bar_gap = 24
    bar_width = min(140, max(48, (chart_width - bar_gap * (len(mode_rows) - 1)) // max(len(mode_rows), 1)))

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Layer 2 mode summary chart">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#f7fbff" rx="18"/>',
        f'<line x1="{left}" y1="{top + chart_height}" x2="{width - right}" y2="{top + chart_height}" stroke="#3b3b3b" stroke-width="2"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + chart_height}" stroke="#3b3b3b" stroke-width="2"/>',
        f'<text x="{left}" y="18" font-size="18" font-family="Helvetica, Arial, sans-serif" font-weight="700">Layer 2 Total Rows by Execution Mode</text>',
    ]

    for tick in range(5):
        value = round(max_value * tick / 4)
        y = top + chart_height - (chart_height * tick / 4)
        parts.append(f'<line x1="{left}" y1="{y}" x2="{width - right}" y2="{y}" stroke="#d9e5f0" stroke-width="1"/>')
        parts.append(f'<text x="{left - 10}" y="{y + 5}" text-anchor="end" font-size="12" fill="#35526b">{value}</text>')

    start_x = left + max(0, (chart_width - (len(mode_rows) * bar_width + (len(mode_rows) - 1) * bar_gap)) / 2)
    for index, row in enumerate(mode_rows):
        total = to_int(row, "total_rows")
        fail = to_int(row, "fail_rows")
        bar_height = 0 if max_value == 0 else chart_height * total / max_value
        x = start_x + index * (bar_width + bar_gap)
        y = top + chart_height - bar_height
        color = "#5b8def" if row.get("mode") == "start" else "#18a999"
        if fail:
            color = "#c44536"
        label = f"{row.get('bug_id', 'unknown')} / {row.get('mode', 'unknown')}"
        parts.append(f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}" rx="10" fill="{color}"/>')
        parts.append(f'<text x="{x + bar_width / 2}" y="{y - 8}" text-anchor="middle" font-size="13" font-weight="700" fill="#1d2d3c">{total}</text>')
        parts.append(f'<text x="{x + bar_width / 2}" y="{top + chart_height + 24}" text-anchor="middle" font-size="13" font-weight="700" fill="#1d2d3c">{escape(label)}</text>')
        parts.append(f'<text x="{x + bar_width / 2}" y="{top + chart_height + 44}" text-anchor="middle" font-size="12" fill="#35526b">fail={fail}</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def build_html(summary_rows, mode_rows):
    bug_chart = render_bug_chart(summary_rows) if summary_rows else "<p>No bug summary data found.</p>"
    mode_chart = render_mode_chart(mode_rows) if mode_rows else "<p>No mode summary data found.</p>"

    cards = []
    for row in summary_rows:
        cards.append(
            "".join(
                [
                    '<div class="card">',
                    f'<h3>{escape(row.get("bug_id", "unknown"))}</h3>',
                    f'<p><strong>Detected:</strong> {escape(row.get("detected", "no"))}</p>',
                    f'<p><strong>Total rows:</strong> {escape(row.get("total_rows", "0"))}</p>',
                    f'<p><strong>Modes:</strong> {escape(row.get("modes_seen", "unknown"))}</p>',
                    f'<p><strong>Flaky rate:</strong> {escape(row.get("flaky_rate", "0.000"))}</p>',
                    '</div>',
                ]
            )
        )

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Layer 2 Charts</title>
    <style>
      :root {{
        color-scheme: light;
        --ink: #20180f;
        --muted: #5a4d40;
        --paper: #f3efe6;
        --panel: #fffaf0;
        --line: #d9cdb6;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: Helvetica, Arial, sans-serif;
        color: var(--ink);
        background: linear-gradient(180deg, #f6f1e7 0%, #efe6d7 100%);
      }}
      main {{
        max-width: 980px;
        margin: 0 auto;
        padding: 32px 20px 48px;
      }}
      h1 {{
        margin: 0 0 10px;
        font-size: 40px;
        line-height: 1.05;
      }}
      p.lead {{
        margin: 0 0 24px;
        color: var(--muted);
        font-size: 18px;
      }}
      section {{ margin-top: 24px; }}
      .panel {{
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 22px;
        padding: 18px;
        box-shadow: 0 14px 30px rgba(64, 46, 25, 0.08);
      }}
      .cards {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 14px;
      }}
      .card {{
        background: #fff;
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 14px;
      }}
      .card h3 {{ margin: 0 0 10px; font-size: 18px; }}
      .card p {{ margin: 6px 0; color: var(--muted); }}
      svg {{ width: 100%; height: auto; display: block; }}
    </style>
  </head>
  <body>
    <main>
      <h1>Layer 2 Wasmtime Charts</h1>
      <p class="lead">Auto-generated from layer2_summary.csv and layer2_mode_summary.csv.</p>
      <section class="panel">{bug_chart}</section>
      <section class="panel">{mode_chart}</section>
      <section class="cards">{''.join(cards)}</section>
    </main>
  </body>
</html>
"""


def main():
    summary_rows = read_csv(SUMMARY_CSV)
    mode_rows = read_csv(MODE_SUMMARY_CSV)
    relationship_rows = read_csv(RELATIONSHIP_MATRIX_CSV)

    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(build_html(summary_rows, mode_rows), encoding="utf-8")
    OUT_SVG.write_text(render_dashboard_svg(summary_rows, mode_rows), encoding="utf-8")
    OUT_MATRIX_SVG.write_text(render_relationship_matrix_svg(relationship_rows), encoding="utf-8")
    print(f"[Layer2 Chart] wrote {OUT_HTML}")
    print(f"[Layer2 Chart] wrote {OUT_SVG}")
    print(f"[Layer2 Chart] wrote {OUT_MATRIX_SVG}")


if __name__ == "__main__":
    main()