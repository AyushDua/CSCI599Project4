#!/usr/bin/env python3
"""ML Bug Detectability Classifier.

Reads results/run_results.csv, engineers features, trains a Decision Tree and
Random Forest to predict bug_id from test-run characteristics, and produces:

  results/ml_detection_probability.csv   — per (bug_id, layer) fail rate
  results/ml_bug_report.md               — Markdown summary with insights
  results/ml_feature_importance_dt.svg   — Decision Tree feature importances
  results/ml_feature_importance_rf.svg   — Random Forest feature importances
"""

import argparse
import csv
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

LAYERS = ["layer1_native", "layer2_wasmtime", "layer3_browser"]


# ── Feature engineering ───────────────────────────────────────────────────────

def _extract_int(text: str, key: str, default: int) -> int:
    m = re.search(rf"{key}=(\d+)", text or "")
    return int(m.group(1)) if m else default


def engineer_features(rows: list) -> tuple:
    """Return (X_list, y_list, feature_names, label_map) where X_list is a
    list of dicts and y_list is a list of bug_id strings."""
    layer_ord   = {"layer1_native": 0, "layer2_wasmtime": 1, "layer3_browser": 2}
    runtime_set = sorted({r.get("runtime","") for r in rows})
    fkind_set   = sorted({r.get("failure_kind","") or "none" for r in rows})
    prefix_set  = sorted({r.get("test_name","").split(".")[0].split("_")[0] for r in rows})

    runtime_map = {v: i for i, v in enumerate(runtime_set)}
    fkind_map   = {v: i for i, v in enumerate(fkind_set)}
    prefix_map  = {v: i for i, v in enumerate(prefix_set)}

    X_list, y_list = [], []

    for row in rows:
        bug_id  = row.get("bug_id", "").strip()
        layer   = row.get("layer",  "").strip()
        runtime = row.get("runtime","").strip()
        fkind   = (row.get("failure_kind","") or "none").strip()
        outcome = row.get("outcome","").strip()
        details = row.get("details","") or ""
        tname   = row.get("test_name","") or ""

        if not bug_id or not layer:
            continue

        outcome_enc = {"pass": 0, "fail": 1}.get(outcome, -1)
        inp_len     = _extract_int(details, "input_len",    0)
        exp_len     = _extract_int(details, "expected_len", 0)
        act_len     = _extract_int(details, "actual_len",  -1)
        len_delta   = abs(exp_len - act_len) if act_len >= 0 else 0
        prefix      = tname.split(".")[0].split("_")[0]

        feat = {
            "layer_enc":          layer_ord.get(layer, -1),
            "runtime_enc":        runtime_map.get(runtime, -1),
            "failure_kind_enc":   fkind_map.get(fkind, -1),
            "outcome_enc":        outcome_enc,
            "input_len":          inp_len,
            "expected_len":       exp_len,
            "actual_len":         act_len,
            "len_delta":          len_delta,
            "is_random_test":     int(tname.startswith("random_seed_")),
            "is_boundary_test":   int(tname.startswith("boundary_len_")),
            "is_invoke_test":     int(tname.startswith("invoke_")),
            "test_name_prefix_enc": prefix_map.get(prefix, -1),
        }
        X_list.append(feat)
        y_list.append(bug_id)

    feature_names = list(X_list[0].keys()) if X_list else []
    return X_list, y_list, feature_names


def to_numpy(X_list: list, feature_names: list):
    """Convert list-of-dicts to a 2D list-of-lists (avoids numpy dependency)."""
    return [[row[f] for f in feature_names] for row in X_list]


# ── Detection probability (no ML required) ───────────────────────────────────

def compute_detection_probability(rows: list) -> list:
    counts = defaultdict(lambda: {"total": 0, "fail": 0, "pass": 0})
    for row in rows:
        bug_id  = row.get("bug_id","").strip()
        layer   = row.get("layer", "").strip()
        outcome = row.get("outcome","").strip()
        if not bug_id or not layer:
            continue
        key = (bug_id, layer)
        counts[key]["total"] += 1
        if outcome == "fail":
            counts[key]["fail"] += 1
        elif outcome == "pass":
            counts[key]["pass"] += 1

    results = []
    for (bug_id, layer), c in sorted(counts.items()):
        total = c["total"] or 1
        prob  = round(c["fail"] / total, 4)
        verdict = ("HIGH"   if prob > 0.8 else
                   "MEDIUM" if prob > 0.2 else
                   "LOW"    if prob > 0   else "NONE")
        results.append({
            "bug_id": bug_id, "layer": layer,
            "total_rows": c["total"], "fail_rows": c["fail"], "pass_rows": c["pass"],
            "detection_probability": prob, "verdict": verdict,
        })
    return results


def write_detection_csv(det_rows: list, out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fieldnames = ["bug_id","layer","total_rows","fail_rows","pass_rows",
                  "detection_probability","verdict"]
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(det_rows)
    print(f"[ml_classifier] wrote {out_path}")


# ── SVG feature importance chart ─────────────────────────────────────────────

def render_importance_svg(importances: dict, model_name: str, out_path: str) -> None:
    sorted_items = sorted(importances.items(), key=lambda x: x[1], reverse=True)
    max_val = max(v for _, v in sorted_items) if sorted_items else 1.0

    BAR_MAX_W = 420
    ROW_H     = 36
    LEFT_PAD  = 220
    TOP_PAD   = 70

    width  = LEFT_PAD + BAR_MAX_W + 100
    height = TOP_PAD + len(sorted_items) * ROW_H + 30

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#f8f9fa"/>',
        f'<text x="{width//2}" y="36" text-anchor="middle" font-size="15" '
        f'font-weight="bold" font-family="sans-serif" fill="#222">'
        f'Feature Importances — {model_name}</text>',
    ]

    for i, (feat, imp) in enumerate(sorted_items):
        y    = TOP_PAD + i * ROW_H
        bar_w = int((imp / max_val) * BAR_MAX_W) if max_val > 0 else 0
        lines.append(
            f'<text x="{LEFT_PAD - 8}" y="{y + 22}" text-anchor="end" '
            f'font-size="12" font-family="monospace" fill="#333">{feat}</text>'
        )
        lines.append(
            f'<rect x="{LEFT_PAD}" y="{y + 6}" width="{bar_w}" height="20" '
            f'rx="4" fill="#4472C4" opacity="0.85"/>'
        )
        lines.append(
            f'<text x="{LEFT_PAD + bar_w + 6}" y="{y + 21}" font-size="11" '
            f'font-family="monospace" fill="#444">{imp:.4f}</text>'
        )

    lines.append("</svg>")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"[ml_classifier] wrote {out_path}")


# ── ML training (requires scikit-learn) ──────────────────────────────────────

def run_ml(X_list: list, y_list: list, feature_names: list, seed: int,
           dt_depth: int, rf_estimators: int) -> dict:
    try:
        from sklearn.tree import DecisionTreeClassifier
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import classification_report
        from sklearn.preprocessing import LabelEncoder
    except ImportError:
        return {"error": "scikit-learn not installed — pip install scikit-learn"}

    le = LabelEncoder()
    y_enc = le.fit_transform(y_list)
    X = to_numpy(X_list, feature_names)

    bug_counts = Counter(y_list)
    if len(bug_counts) < 2:
        return {"error": f"Only {len(bug_counts)} bug variant(s) present — need ≥2 for classification"}

    # Use stratified split only if every class has ≥2 samples
    min_count = min(bug_counts.values())
    stratify  = y_enc if min_count >= 2 else None

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_enc, test_size=0.2, random_state=seed, stratify=stratify
    )

    dt = DecisionTreeClassifier(max_depth=dt_depth, class_weight="balanced",
                                 random_state=seed)
    dt.fit(X_train, y_train)

    rf = RandomForestClassifier(n_estimators=rf_estimators, max_depth=dt_depth + 1,
                                 class_weight="balanced", random_state=seed)
    rf.fit(X_train, y_train)

    dt_pred = dt.predict(X_test)
    rf_pred = rf.predict(X_test)

    target_names = list(le.classes_)

    return {
        "dt_accuracy":    round(sum(dt_pred == y_test) / len(y_test), 4),
        "rf_accuracy":    round(sum(rf_pred == y_test) / len(y_test), 4),
        "dt_report":      classification_report(y_test, dt_pred, target_names=target_names,
                                                zero_division=0),
        "rf_report":      classification_report(y_test, rf_pred, target_names=target_names,
                                                zero_division=0),
        "dt_importances": dict(zip(feature_names, dt.feature_importances_)),
        "rf_importances": dict(zip(feature_names, rf.feature_importances_)),
        "label_classes":  target_names,
    }


# ── Markdown report ───────────────────────────────────────────────────────────

def write_report(det_rows: list, ml_results: dict,
                 dt_svg: str, rf_svg: str, out_path: str, csv_path: str) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_dir = os.path.dirname(out_path)
    rel = lambda p: os.path.relpath(p, out_dir)

    lines = [
        "# ML Bug Detectability Report",
        "",
        f"Generated: {now}  |  Source: `{csv_path}`",
        "",
        "## Detection Probability by Bug and Layer",
        "",
        "| Bug ID | Layer | fail/total | Detection Probability | Verdict |",
        "|--------|-------|------------|----------------------|---------|",
    ]

    for r in det_rows:
        lines.append(
            f"| {r['bug_id']} | {r['layer']} | "
            f"{r['fail_rows']}/{r['total_rows']} | "
            f"{r['detection_probability']:.2%} | **{r['verdict']}** |"
        )

    lines += [""]

    if "error" in ml_results:
        lines += [
            "## Classifier",
            "",
            f"> ⚠ {ml_results['error']}",
            "",
            "The detection probability table above does not require ML and is always produced.",
            "",
        ]
    else:
        lines += [
            "## Classifier Accuracy",
            "",
            f"- Decision Tree (max_depth=auto): **{ml_results['dt_accuracy']:.2%}**",
            f"- Random Forest (n_estimators=auto): **{ml_results['rf_accuracy']:.2%}**",
            "",
            "### Decision Tree Classification Report",
            "```",
            ml_results["dt_report"],
            "```",
            "",
            "### Random Forest Classification Report",
            "```",
            ml_results["rf_report"],
            "```",
            "",
            "## Feature Importances",
            "",
            "Sorted by Random Forest importance (descending):",
            "",
        ]
        rf_imp = ml_results["rf_importances"]
        for feat, imp in sorted(rf_imp.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- `{feat}`: {imp:.4f}")

        lines += [
            "",
            f"![Decision Tree importances]({rel(dt_svg)})",
            f"![Random Forest importances]({rel(rf_svg)})",
            "",
            "## Key Insights for Security Testing",
            "",
        ]

        # Auto-generate insights from data
        layer_best = defaultdict(list)
        for r in det_rows:
            if r["detection_probability"] > 0 and not r["bug_id"].startswith("CLEAN"):
                layer_best[r["layer"]].append((r["bug_id"], r["detection_probability"]))

        for layer, bugs in sorted(layer_best.items()):
            bug_strs = [f"`{b}` ({p:.0%})" for b, p in sorted(bugs, key=lambda x: -x[1])]
            label = layer.replace("layer1_native","Layer 1 (native)") \
                         .replace("layer2_wasmtime","Layer 2 (Wasmtime)") \
                         .replace("layer3_browser","Layer 3 (Browser)")
            lines.append(f"- **{label}** detects: {', '.join(bug_strs)}")

        top_feat = sorted(rf_imp.items(), key=lambda x: x[1], reverse=True)[0]
        lines += [
            "",
            f"The most predictive feature is `{top_feat[0]}` (importance {top_feat[1]:.4f}), "
            f"indicating that the {top_feat[0].replace('_', ' ')} is the strongest signal "
            f"for distinguishing bug types across layers.",
        ]

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"[ml_classifier] wrote {out_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="ML bug detectability classifier")
    p.add_argument("--csv",            default="results/run_results.csv")
    p.add_argument("--out-dir",        default="results/")
    p.add_argument("--seed",           type=int, default=42)
    p.add_argument("--dt-max-depth",   type=int, default=5)
    p.add_argument("--rf-estimators",  type=int, default=100)
    p.add_argument("--no-svg",         action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)

    if not os.path.exists(args.csv):
        print(f"[ml_classifier] CSV not found: {args.csv} — skipping")
        return 0

    with open(args.csv, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    det_rows = compute_detection_probability(rows)
    det_csv  = str(out_dir / "ml_detection_probability.csv")
    write_detection_csv(det_rows, det_csv)

    # Attempt ML
    X_list, y_list, feature_names = engineer_features(rows)
    bug_variants = len(set(y_list))
    if bug_variants < 4:
        print(f"[ml_classifier] Only {bug_variants} bug variant(s) in CSV — "
              "skipping classifier (need ≥4 for meaningful classification)")
        ml_results = {"error": f"Only {bug_variants} bug variant(s) present — need ≥4"}
    else:
        print(f"[ml_classifier] Training on {len(X_list)} rows, "
              f"{bug_variants} bug variants, {len(feature_names)} features …")
        ml_results = run_ml(X_list, y_list, feature_names,
                            args.seed, args.dt_max_depth, args.rf_estimators)
        if "error" not in ml_results:
            print(f"[ml_classifier] DT accuracy={ml_results['dt_accuracy']:.2%}  "
                  f"RF accuracy={ml_results['rf_accuracy']:.2%}")

    dt_svg = str(out_dir / "ml_feature_importance_dt.svg")
    rf_svg = str(out_dir / "ml_feature_importance_rf.svg")

    if not args.no_svg and "dt_importances" in ml_results:
        render_importance_svg(ml_results["dt_importances"], "Decision Tree", dt_svg)
        render_importance_svg(ml_results["rf_importances"], "Random Forest", rf_svg)

    report_md = str(out_dir / "ml_bug_report.md")
    write_report(det_rows, ml_results, dt_svg, rf_svg, report_md, args.csv)

    return 0


if __name__ == "__main__":
    sys.exit(main())
