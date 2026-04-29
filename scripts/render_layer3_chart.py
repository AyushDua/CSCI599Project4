#!/usr/bin/env python3
import csv
import html
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SUMMARY_CSV = ROOT / "results" / "layer3_summary.csv"
BROWSER_SUMMARY_CSV = ROOT / "results" / "layer3_browser_summary.csv"
RELATIONSHIP_MATRIX_CSV = ROOT / "results" / "layer3_relationship_matrix.csv"
OUT_HTML = ROOT / "results" / "layer3_chart.html"
OUT_SVG = ROOT / "results" / "layer3_chart.svg"
OUT_MATRIX_SVG = ROOT / "results" / "layer3_visual_matrix.svg"

BROWSER_COLORS = {
    "chromium": "#4285f4",
    "firefox":  "#e05c2a",
    "webkit":   "#34a853",
}


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
        {(row.get("browser", "unknown"), row.get("test_family", "other")) for row in rows},
        key=lambda item: (item[0], item[1]),
    )
    row_map = {
        (row.get("bug_id", "unknown"), row.get("browser", "unknown"), row.get("test_family", "other")): row
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

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="Layer 3 visual matrix" style="font-family: Helvetica, Arial, sans-serif;">',
        '<defs>',
        '  <linearGradient id="matrixbg" x1="0" x2="0" y1="0" y2="1">',
        '    <stop offset="0%" stop-color="#f0f4ff"/>',
        '    <stop offset="100%" stop-color="#e6eeff"/>',
        '  </linearGradient>',
        '</defs>',
        f'<rect width="{width}" height="{height}" fill="url(#matrixbg)"/>',
        '<text x="60" y="76" font-size="48" font-weight="700" fill="#1a1f3a">Layer 3 Visual Matrix</text>',
        '<text x="60" y="114" font-size="22" fill="#4a5270">Rows = bug variants, columns = browser + test family, cells = fail/total.</text>',
        f'<rect x="40" y="140" width="{width - 80}" height="{height - 180}" rx="28" fill="#f8faff" stroke="#c8d0e8" stroke-width="2"/>',
    ]

    legend_y = height - 78
    legend = [("#dff3e4", "0 fail"), ("#fde3b4", "partial fail"), ("#f8c4b4", "all fail")]
    for index, (fill, label) in enumerate(legend):
        lx = 60 + index * 220
        parts.append(f'<rect x="{lx}" y="{legend_y}" width="24" height="24" rx="6" fill="{fill}" stroke="#b0bcd4"/>')
        parts.append(f'<text x="{lx + 36}" y="{legend_y + 18}" font-size="18" fill="#4a5270">{label}</text>')

    for col_index, (browser, family) in enumerate(column_keys):
        x = left + col_index * cell_w
        parts.append(f'<text x="{x + cell_w / 2}" y="{top - 38}" text-anchor="middle" font-size="16" font-weight="700" fill="#1a1f3a">{escape(browser)}</text>')
        parts.append(f'<text x="{x + cell_w / 2}" y="{top - 16}" text-anchor="middle" font-size="14" fill="#4a5270">{escape(family)}</text>')

    for row_index, bug_id in enumerate(bug_ids):
        y = top + row_index * cell_h
        parts.append(f'<text x="{left - 18}" y="{y + 48}" text-anchor="end" font-size="18" font-weight="700" fill="#1a1f3a">{escape(bug_id)}</text>')
        for col_index, (browser, family) in enumerate(column_keys):
            x = left + col_index * cell_w
            row = row_map.get((bug_id, browser, family))
            fill = "#edf0f8"
            primary = "n/a"
            secondary = ""
            if row is not None:
                fill = cell_fill(row)
                primary = cell_text(row)
                if to_int(row, "failure_assertion_fail") > 0:
                    secondary = f"assert={to_int(row, 'failure_assertion_fail')}"
                elif to_int(row, "failure_exception") > 0:
                    secondary = f"exception={to_int(row, 'failure_exception')}"
                else:
                    secondary = "detected=no"
            parts.append(f'<rect x="{x}" y="{y}" width="{cell_w - 8}" height="{cell_h - 10}" rx="14" fill="{fill}" stroke="#c0cce0"/>')
            parts.append(f'<text x="{x + (cell_w - 8) / 2}" y="{y + 35}" text-anchor="middle" font-size="16" font-weight="700" fill="#1a1f3a">{escape(primary)}</text>')
            parts.append(f'<text x="{x + (cell_w - 8) / 2}" y="{y + 58}" text-anchor="middle" font-size="12" fill="#4a5270">{escape(secondary)}</text>')

    parts.append('</svg>')
    return "\n".join(parts)


def render_dashboard_svg(summary_rows, browser_rows):
    width = 1400
    page_margin = 70
    panel_width = width - page_margin * 2
    bug_panel_y = 160
    panel_height = 390
    browser_panel_y = bug_panel_y + panel_height + 34
    card_y = browser_panel_y + panel_height + 34
    card_height = max(190, 170 + max(0, len(summary_rows) - 1) * 150)
    height = card_y + card_height + 50
    max_summary = max([to_int(row, "total_rows") for row in summary_rows] + [1])
    max_browser = max([to_int(row, "total_rows") for row in browser_rows] + [1])

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
            f'<text x="{left}" y="{panel_y + 52}" font-size="24" font-weight="700" fill="#1a1f3a">{escape(title)}</text>',
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
            panel_x, panel_y, panel_w, panel_h,
            "Layer 3 Total Rows by Bug Variant",
            "#dce3f5", "#7880a0", "#3a4070", max_summary,
        )
        chart_w = right - left
        chart_h = bottom - top
        bar_gap = 34
        bar_width = min(160, max(72, (chart_w - bar_gap * max(len(summary_rows) - 1, 0)) / max(len(summary_rows), 1)))
        start_x = left + max(0, (chart_w - (len(summary_rows) * bar_width + max(len(summary_rows) - 1, 0) * bar_gap)) / 2)
        parts = [panel_shell(panel_x, panel_y, panel_w, panel_h, "#f0f4ff", "#c8d0e8"), grid]
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
                f'<text x="{x + bar_width / 2}" y="{y - 10}" text-anchor="middle" font-size="14" font-weight="700" fill="#1a1f3a">{total}</text>',
                f'<text x="{x + bar_width / 2}" y="{bottom + 30}" text-anchor="middle" font-size="14" font-weight="700" fill="#1a1f3a">{escape(row.get("bug_id", "unknown"))}</text>',
                f'<text x="{x + bar_width / 2}" y="{bottom + 56}" text-anchor="middle" font-size="13" fill="#3a4070">fail={fail} flaky={flaky:.3f}</text>',
            ])
        return "".join(parts)

    def browser_bars():
        panel_x = page_margin
        panel_y = browser_panel_y
        panel_w = panel_width
        panel_h = panel_height
        grid, left, right, top, bottom = chart_grid(
            panel_x, panel_y, panel_w, panel_h,
            "Layer 3 Total Rows by Browser",
            "#d9e5f0", "#7b8794", "#35526b", max_browser,
        )
        chart_w = right - left
        chart_h = bottom - top
        bar_gap = 28
        bar_width = min(160, max(60, (chart_w - bar_gap * max(len(browser_rows) - 1, 0)) / max(len(browser_rows), 1)))
        start_x = left + max(0, (chart_w - (len(browser_rows) * bar_width + max(len(browser_rows) - 1, 0) * bar_gap)) / 2)
        parts = [panel_shell(panel_x, panel_y, panel_w, panel_h, "#f7fbff", "#cbd9e6"), grid]
        for index, row in enumerate(browser_rows):
            total = to_int(row, "total_rows")
            fail = to_int(row, "fail_rows")
            bar_height = 0 if max_browser == 0 else chart_h * total / max_browser
            x = start_x + index * (bar_width + bar_gap)
            y = bottom - bar_height
            browser = row.get("browser", "unknown")
            color = BROWSER_COLORS.get(browser, "#888888")
            if fail:
                color = "#c44536"
            label = f"{row.get('bug_id', 'unknown')} / {browser}"
            parts.extend([
                f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}" rx="12" fill="{color}"/>',
                f'<text x="{x + bar_width / 2}" y="{y - 10}" text-anchor="middle" font-size="14" font-weight="700" fill="#1d2d3c">{total}</text>',
                f'<text x="{x + bar_width / 2}" y="{bottom + 30}" text-anchor="middle" font-size="13" font-weight="700" fill="#1d2d3c">{escape(label)}</text>',
                f'<text x="{x + bar_width / 2}" y="{bottom + 54}" text-anchor="middle" font-size="13" fill="#35526b">fail={fail}</text>',
            ])
        return "".join(parts)

    def stat_cards():
        card_x = page_margin
        card_width = panel_width
        line_height = 42
        parts = []
        for index, row in enumerate(summary_rows):
            y = card_y + index * 150
            parts.append("".join([
                f'<rect x="{card_x}" y="{y}" width="{card_width}" height="130" rx="26" fill="#ffffff" stroke="#c8d0e8" stroke-width="2"/>',
                f'<text x="{card_x + 28}" y="{y + 42}" font-size="28" font-weight="700" fill="#1a1f3a">{escape(row.get("bug_id", "unknown"))}</text>',
                f'<text x="{card_x + 28}" y="{y + 42 + line_height}" font-size="22" fill="#4a5270"><tspan font-weight="700">Detected:</tspan> {escape(row.get("detected", "no"))}</text>',
                f'<text x="{card_x + 28}" y="{y + 42 + line_height * 2}" font-size="22" fill="#4a5270"><tspan font-weight="700">Total rows:</tspan> {escape(row.get("total_rows", "0"))}</text>',
                f'<text x="{card_x + 500}" y="{y + 42 + line_height}" font-size="22" fill="#4a5270"><tspan font-weight="700">Browsers:</tspan> {escape(row.get("browsers_seen", "unknown"))}</text>',
                f'<text x="{card_x + 500}" y="{y + 42 + line_height * 2}" font-size="22" fill="#4a5270"><tspan font-weight="700">Flaky rate:</tspan> {escape(row.get("flaky_rate", "0.000"))}</text>',
            ]))
        return "".join(parts)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="Layer 3 browser chart dashboard" style="font-family: Helvetica, Arial, sans-serif;">
  <defs>
    <linearGradient id="bg" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%" stop-color="#f0f4ff"/>
      <stop offset="100%" stop-color="#e6eeff"/>
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" fill="url(#bg)"/>
  <text x="{page_margin}" y="88" font-size="48" font-weight="700" fill="#1a1f3a">Layer 3 Browser Charts</text>
  <text x="{page_margin}" y="126" font-size="22" fill="#4a5270">Auto-generated from layer3_summary.csv and layer3_browser_summary.csv.</text>

  {bug_bars()}
  {browser_bars()}
  {stat_cards()}
</svg>'''


def build_html(summary_rows, browser_rows):
    cards = []
    for row in summary_rows:
        cards.append("".join([
            '<div class="card">',
            f'<h3>{escape(row.get("bug_id", "unknown"))}</h3>',
            f'<p><strong>Detected:</strong> {escape(row.get("detected", "no"))}</p>',
            f'<p><strong>Total rows:</strong> {escape(row.get("total_rows", "0"))}</p>',
            f'<p><strong>Browsers:</strong> {escape(row.get("browsers_seen", "unknown"))}</p>',
            f'<p><strong>Flaky rate:</strong> {escape(row.get("flaky_rate", "0.000"))}</p>',
            '</div>',
        ]))

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Layer 3 Charts</title>
    <style>
      :root {{
        color-scheme: light;
        --ink: #1a1f3a;
        --muted: #4a5270;
        --paper: #edf0fc;
        --panel: #f8faff;
        --line: #c8d0e8;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: Helvetica, Arial, sans-serif;
        color: var(--ink);
        background: linear-gradient(180deg, #f0f4ff 0%, #e6eeff 100%);
      }}
      main {{
        max-width: 980px;
        margin: 0 auto;
        padding: 32px 20px 48px;
      }}
      h1 {{ margin: 0 0 10px; font-size: 40px; line-height: 1.05; }}
      p.lead {{ margin: 0 0 24px; color: var(--muted); font-size: 18px; }}
      section {{ margin-top: 24px; }}
      .panel {{
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 22px;
        padding: 18px;
        box-shadow: 0 14px 30px rgba(30, 40, 100, 0.08);
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
      <h1>Layer 3 Browser Charts</h1>
      <p class="lead">Auto-generated from layer3_summary.csv and layer3_browser_summary.csv.</p>
      <section class="cards">{''.join(cards)}</section>
    </main>
  </body>
</html>
"""


def main():
    summary_rows = read_csv(SUMMARY_CSV)
    browser_rows = read_csv(BROWSER_SUMMARY_CSV)
    relationship_rows = read_csv(RELATIONSHIP_MATRIX_CSV)

    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(build_html(summary_rows, browser_rows), encoding="utf-8")
    OUT_SVG.write_text(render_dashboard_svg(summary_rows, browser_rows), encoding="utf-8")
    OUT_MATRIX_SVG.write_text(render_relationship_matrix_svg(relationship_rows), encoding="utf-8")
    print(f"[Layer3 Chart] wrote {OUT_HTML}")
    print(f"[Layer3 Chart] wrote {OUT_SVG}")
    print(f"[Layer3 Chart] wrote {OUT_MATRIX_SVG}")


if __name__ == "__main__":
    main()
