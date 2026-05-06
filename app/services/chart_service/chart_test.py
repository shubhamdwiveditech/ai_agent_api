import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from chart_service import generate_chart
# ─────────────────────────────────────────────────────────────────────────────
# Quick smoke-test (run this file directly)
# ─────────────────────────────────────────────────────────────────────────────
import json, os

OUT = "tmp/chart_test"
os.makedirs(OUT, exist_ok=True)
# (.venv) drive run -  python app/services/chart_service/chart_test.py
# 
# all output will be in  C:\tmp\chart_test folder

def save(name, result):
    path = os.path.join(OUT, f"{name}.html")
    with open(path, "w") as f:
        f.write(f'<img src="{result["data_url"]}" style="max-width:100%">')
    print(f"  ✓ {name}.html")

print("\n=== Chart Smoke-Tests ===\n")

# ── Pie: many slices, several tiny ones ──────────────────────────────────
save("pie_tiny_slices", generate_chart(
    "pie",
    labels=["Alpha", "Beta", "Gamma", "Delta", "Epsilon",
            "Zeta", "Eta", "Theta", "Iota", "Kappa"],
    datasets=[{"label": "Share", "data": [30, 25, 15, 10, 7, 5, 3, 2, 2, 1]}],
    title="Pie – many slices, tiny remainder",
))

# ── Pie: very few slices ──────────────────────────────────────────────────
save("pie_few_slices", generate_chart(
    "pie",
    labels=["Product A", "Product B", "Product C"],
    datasets=[{"label": "Revenue", "data": [55, 30, 15]}],
    title="Pie – three slices",
))

# ── Doughnut: tiny slices ─────────────────────────────────────────────────
save("doughnut_tiny_slices", generate_chart(
    "doughnut",
    labels=["Q1", "Q2", "Q3", "Q4", "Other A", "Other B", "Other C"],
    datasets=[{"label": "Sales", "data": [40, 28, 16, 10, 3, 2, 1]}],
    title="Doughnut – small tail slices",
))

# ── Bar: positive values with value labels ────────────────────────────────
save("bar_positive", generate_chart(
    "bar",
    labels=["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
    datasets=[
        {"label": "2023", "data": [4200, 3800, 5100, 4700, 6200, 5800]},
        {"label": "2024", "data": [5100, 4600, 6300, 5500, 7400, 6900]},
    ],
    title="Bar – dual series with value labels",
))

# ── Bar: mixed positive/negative (waterfall-style) ────────────────────────
save("bar_mixed", generate_chart(
    "bar",
    labels=["Revenue", "COGS", "Gross Profit", "OpEx", "EBITDA", "D&A", "EBIT"],
    datasets=[{"label": "USD M", "data": [120, -45, 75, -30, 45, -5, 40]}],
    title="Bar – negative values",
))

# ── Bar: large values → compact formatting ────────────────────────────────
save("bar_large_values", generate_chart(
    "bar",
    labels=["NY", "LA", "Chicago", "Houston", "Phoenix"],
    datasets=[{"label": "Population", "data": [8336817, 3979576, 2693976, 2320268, 1608139]}],
    title="Bar – large value formatting (M/K)",
))

# ── Horizontal bar: many categories ──────────────────────────────────────
save("hbar_many", generate_chart(
    "horizontal_bar",
    labels=[f"Category {i}" for i in range(1, 16)],
    datasets=[{"label": "Score", "data": [90-i*3 for i in range(15)]}],
    title="Horizontal Bar – 15 categories",
))

# ── Horizontal bar: negative values ──────────────────────────────────────
save("hbar_negative", generate_chart(
    "horizontal_bar",
    labels=["Product A", "Product B", "Product C", "Product D"],
    datasets=[{"label": "Margin %", "data": [12.5, -3.2, 8.1, -7.6]}],
    title="Horizontal Bar – mixed margins",
))

# ── Line ──────────────────────────────────────────────────────────────────
save("line_multi", generate_chart(
    "line",
    labels=[str(y) for y in range(2015, 2025)],
    datasets=[
        {"label": "Series A", "data": [10, 15, 13, 18, 22, 21, 28, 32, 30, 35]},
        {"label": "Series B", "data": [5, 8, 9, 12, 14, 17, 19, 23, 25, 29]},
    ],
    title="Line – multi-series 10 years",
))

# ── Area ─────────────────────────────────────────────────────────────────
save("area_stacked", generate_chart(
    "area",
    labels=["Jan", "Feb", "Mar", "Apr", "May"],
    datasets=[
        {"label": "Mobile",  "data": [30, 35, 32, 40, 45]},
        {"label": "Desktop", "data": [50, 48, 55, 53, 60]},
    ],
    title="Area – dual series",
))

# ── Radar ─────────────────────────────────────────────────────────────────
save("radar_skills", generate_chart(
    "radar",
    labels=["Speed", "Strength", "Agility", "Stamina", "Intelligence"],
    datasets=[
        {"label": "Hero A", "data": [80, 70, 90, 65, 85]},
        {"label": "Hero B", "data": [60, 90, 55, 80, 70]},
    ],
    title="Radar – skill comparison",
))

# ── Edge: single data point ───────────────────────────────────────────────
save("bar_single_point", generate_chart(
    "bar",
    labels=["Only Category"],
    datasets=[{"label": "Value", "data": [42]}],
    title="Bar – single data point",
))

# ── Edge: all-zero data ───────────────────────────────────────────────────
save("bar_all_zeros", generate_chart(
    "bar",
    labels=["A", "B", "C"],
    datasets=[{"label": "Empty", "data": [0, 0, 0]}],
    title="Bar – all zeros",
))

print(f"\nAll charts saved to {OUT}/\n")