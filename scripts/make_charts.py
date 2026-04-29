#!/usr/bin/env python3
import os, re
import pandas as pd
import matplotlib.pyplot as plt

CSV_IN = "results/run_results.csv"
OUT_DIR = "results/charts"
os.makedirs(OUT_DIR, exist_ok=True)

df = pd.read_csv(CSV_IN)
df["failure_kind"] = df["failure_kind"].fillna("")
df["details"] = df["details"].fillna("")

def extract_int(pattern, s):
    m = re.search(pattern, s or "")
    return int(m.group(1)) if m else None

df["input_len"] = df.apply(
    lambda r: extract_int(r"input_len=(\d+)", r["details"]) if r["layer"] == "layer2_wasmtime" else None,
    axis=1
)

# 1) total by layer
plt.figure()
df["layer"].value_counts().sort_index().plot(kind="bar")
plt.title("Total test cases by layer")
plt.xlabel("Layer"); plt.ylabel("Count")
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "01_total_by_layer.png"), dpi=200)

# 2) outcomes by layer
plt.figure()
pivot = df.pivot_table(index="layer", columns="outcome", aggfunc="size", fill_value=0).reindex(sorted(df["layer"].unique()))
pivot.plot(kind="bar")
plt.title("Outcome distribution by layer")
plt.xlabel("Layer"); plt.ylabel("Count")
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "02_outcome_by_layer.png"), dpi=200)

# 3) layer3 outcomes by browser
plt.figure()
l3 = df[df["layer"] == "layer3_browser"]
pivot_l3 = l3.pivot_table(index="runtime", columns="outcome", aggfunc="size", fill_value=0).reindex(sorted(l3["runtime"].unique()))
pivot_l3.plot(kind="bar")
plt.title("Layer 3 outcomes by browser runtime")
plt.xlabel("Browser runtime"); plt.ylabel("Count")
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "03_layer3_by_browser.png"), dpi=200)

# 4) totals by runtime
plt.figure()
df["runtime"].value_counts().reindex(sorted(df["runtime"].unique())).plot(kind="bar")
plt.title("Total test cases by runtime")
plt.xlabel("Runtime"); plt.ylabel("Count")
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "04_total_by_runtime.png"), dpi=200)

# 5) layer2 input_len histogram
plt.figure()
l2 = df[df["layer"] == "layer2_wasmtime"]
vals = l2["input_len"].dropna()
plt.hist(vals, bins=20)
plt.title("Layer 2: input_len distribution (bytes)")
plt.xlabel("input_len"); plt.ylabel("Number of cases")
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "05_layer2_input_len_hist.png"), dpi=200)

# 6) boundary_len trend
plt.figure()
boundary = l2[l2["test_name"].astype(str).str.startswith("boundary_len_")].copy()
if not boundary.empty:
    boundary["n"] = boundary["test_name"].str.replace("boundary_len_", "", regex=False).astype(int)
    boundary = boundary.sort_values("n")
    plt.plot(boundary["n"], boundary["input_len"], marker="o")
    plt.title("Layer 2: boundary_len cases (input_len)")
    plt.xlabel("boundary_len_n (bytes)"); plt.ylabel("input_len (bytes)")
else:
    plt.text(0.5, 0.5, "No boundary_len cases found", ha="center", va="center")
    plt.axis("off")

plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "06_layer2_boundary_len.png"), dpi=200)

print(f"Saved charts to {OUT_DIR}/")