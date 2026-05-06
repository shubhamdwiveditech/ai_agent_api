"""
Chart generation service using Matplotlib.
Supports: bar, line, pie, doughnut, radar, scatter, area, histogram, horizontal_bar
Returns base64 encoded PNG.

Fixes & improvements:
  1. Pie / Doughnut: small slices no longer overlay labels — always uses a
     clean side legend keyed by color. Percentage labels are moved to wedge
     center only when the slice is large enough to contain them.
  2. Bar / Horizontal-bar: value labels are never clipped — they are drawn
     inside long bars when the bar is tall/wide enough, or suppressed for very
     dense charts; the axis limit is expanded to guarantee labels have room.
  3. General: figure size auto-scaling, robust NaN/empty-data guards, sane
     legend placement across all chart types.
"""

import io
import base64
import math
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import numpy as np
from typing import Literal, Optional

CHART_TYPES = Literal[
    "bar", "horizontal_bar", "line", "area", "pie", "doughnut", "radar"
]

# Clean default color palette
COLORS = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52",
    "#8172B3", "#937860", "#DA8BC3", "#8C8C8C",
    "#CCB974", "#64B5CD",
]

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fig_to_base64(fig: plt.Figure, *, dpi: int = 150) -> dict:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=dpi)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return {
        "data_url": f"data:image/png;base64,{b64}",
        "format": "png",
    }


def _apply_common_style(ax, title: Optional[str] = None):
    ax.set_facecolor("#f9f9f9")
    ax.figure.patch.set_facecolor("#ffffff")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if title:
        ax.set_title(title, fontsize=14, fontweight="bold", pad=12)


def _apply_category_label_layout(ax, *, labels: list, category_axis: str) -> None:
    """Reduce overlap for category labels in dense charts."""
    label_count = len(labels or [])
    if label_count <= 0:
        return

    if category_axis == "x":
        ax.tick_params(axis="x", labelrotation=45)
        for tick in ax.get_xticklabels():
            tick.set_ha("right")
            tick.set_va("top")
        if ax.figure.subplotpars.bottom < 0.25:
            ax.figure.subplots_adjust(bottom=0.25)
        if label_count > 15:
            for tick in ax.get_xticklabels():
                tick.set_fontsize(9)
    elif category_axis == "y":
        if label_count > 15:
            for tick in ax.get_yticklabels():
                tick.set_fontsize(9)


def _maybe_move_legend_outside(ax, *, label_count: int, dataset_count: int) -> None:
    if dataset_count <= 1:
        return
    if label_count <= 10 and dataset_count <= 3:
        ax.legend()
        return
    ax.legend(
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        borderaxespad=0.0,
        frameon=False,
    )
    ax.figure.subplots_adjust(right=0.78)


def _auto_figure_size(
    *,
    labels: list,
    datasets: list,
    chart_type: str,
    width: int,
    height: int,
) -> tuple:
    label_count = len(labels or [])
    dataset_count = len(datasets or [])

    if chart_type in ("bar", "line", "area"):
        if label_count > 10:
            width = max(width, min(24, int(0.55 * label_count + 4)))
            height = max(height, 7)
        if dataset_count > 3:
            width = max(width, 14)

    if chart_type == "horizontal_bar":
        if label_count > 10:
            height = max(height, min(22, int(0.35 * label_count + 3)))
        if dataset_count > 3:
            height = max(height, 8)

    return width, height


def _cap_figure_size_to_max_px(
    *, width: float, height: float, dpi: int, max_px: int
) -> tuple:
    if not max_px or max_px <= 0:
        return float(width), float(height)
    if not dpi or dpi <= 0:
        dpi = 150
    max_dim_px = max(width, height) * dpi
    if max_dim_px <= max_px:
        return float(width), float(height)
    scale = max_px / float(max_dim_px)
    return float(width) * scale, float(height) * scale


def _safe_data(data) -> list:
    """Replace None / NaN with 0 so Matplotlib never chokes."""
    out = []
    for v in (data or []):
        try:
            f = float(v)
            out.append(0.0 if math.isnan(f) or math.isinf(f) else f)
        except (TypeError, ValueError):
            out.append(0.0)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def generate_chart(
    chart_type: str,
    labels: list,
    datasets: list,
    title: Optional[str] = None,
    width: int = 10,
    height: int = 6,
    *,
    dpi: int = 150,
    max_px: Optional[int] = None,
) -> dict:
    """
    Main entry point. Dispatches to the correct chart generator.

    Args:
        chart_type : One of the supported chart types.
        labels     : X-axis / category labels (or pie slice labels).
        datasets   : List of {"label": str, "data": list[float]} dicts.
        title      : Optional chart title.
        width/height: Figure size in inches.

    Returns:
        {"data_url": str, "format": "png"}
    """
    chart_type = chart_type.lower().replace(" ", "_")
    width, height = _auto_figure_size(
        labels=labels,
        datasets=datasets,
        chart_type=chart_type,
        width=width,
        height=height,
    )
    width, height = _cap_figure_size_to_max_px(
        width=width, height=height, dpi=dpi, max_px=max_px or 0
    )
    generators = {
        "bar":            _bar_chart,
        "horizontal_bar": _horizontal_bar_chart,
        "line":           _line_chart,
        "area":           _area_chart,
        "pie":            _pie_chart,
        "doughnut":       _doughnut_chart,
        "radar":          _radar_chart,
    }
    if chart_type not in generators:
        raise ValueError(
            f"Unsupported chart type '{chart_type}'. "
            f"Choose from: {', '.join(generators)}"
        )
    # Sanitise all dataset data vectors
    for ds in datasets:
        ds["data"] = _safe_data(ds.get("data", []))
    return generators[chart_type](labels, datasets, title, width, height, dpi)


# ─────────────────────────────────────────────────────────────────────────────
# FIX 1 & 2 – Pie / Doughnut: robust label & legend handling
# ─────────────────────────────────────────────────────────────────────────────

# Minimum wedge percentage (of full circle) to print the % text inside the wedge.
_PCT_LABEL_MIN_PCT = 4.0   # smaller than this → label is suppressed on wedge


def _circular_chart(
    labels: list,
    datasets: list,
    title: Optional[str],
    width: float,
    height: float,
    dpi: int,
    *,
    is_doughnut: bool = False,
) -> dict:
    """
    Shared renderer for pie and doughnut.

    Strategy
    ────────
    • ALWAYS use a side legend (color swatch + label + value%).
      This eliminates all wedge-label clutter regardless of slice count or size.
    • Percentage text is drawn inside the wedge ONLY when the slice is large
      enough (≥ _PCT_LABEL_MIN_PCT %) to avoid overlapping the arc.
    • For tiny slices the % is omitted from the wedge entirely — the legend
      already carries the number.
    """
    data = datasets[0]["data"]
    n = len(data)
    colors = COLORS[:n]

    total = sum(data) or 1  # guard against all-zero data
    pcts  = [v / total * 100 for v in data]

    fig, ax = plt.subplots(figsize=(width, height))

    wedge_props = {"edgecolor": "white", "linewidth": 1.5}
    if is_doughnut:
        wedge_props["width"] = 0.5

    # ── Draw wedges without any automatic labels ──────────────────────────────
    wedges, _ = ax.pie(
        data,
        labels=None,          # We handle all labelling ourselves
        colors=colors,
        startangle=140,
        wedgeprops=wedge_props,
        autopct=None,         # We draw pct text manually below
    )
    ax.axis("equal")

    # ── Manually place % text inside large-enough wedges ─────────────────────
    # Matplotlib stores each wedge's start/end angles in degrees (theta1, theta2).
    for wedge, pct in zip(wedges, pcts):
        if pct < _PCT_LABEL_MIN_PCT:
            continue  # too small — skip to avoid clutter
        # Mid-angle of the wedge in radians
        theta = math.radians((wedge.theta1 + wedge.theta2) / 2)
        # Radial position: halfway into the wedge (or slightly inner for doughnut)
        r = 0.60 if not is_doughnut else 0.72
        x = r * math.cos(theta)
        y = r * math.sin(theta)
        ax.text(
            x, y,
            f"{pct:.1f}%",
            ha="center", va="center",
            fontsize=9, fontweight="bold",
            color="white",
        )

    # ── Side legend: color patch + label + percentage ─────────────────────────
    legend_handles = []
    for color, label, pct in zip(colors, labels, pcts):
        patch = mpatches.Patch(color=color, label=f"{label}  ({pct:.1f}%)")
        legend_handles.append(patch)

    ax.legend(
        handles=legend_handles,
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        frameon=False,
        fontsize=10,
    )
    fig.subplots_adjust(right=0.68)

    if title:
        ax.set_title(title, fontsize=14, fontweight="bold", pad=12)

    return _fig_to_base64(fig, dpi=dpi)


def _pie_chart(labels, datasets, title, width, height, dpi):
    return _circular_chart(
        labels, datasets, title, width, height, dpi, is_doughnut=False
    )


def _doughnut_chart(labels, datasets, title, width, height, dpi):
    return _circular_chart(
        labels, datasets, title, width, height, dpi, is_doughnut=True
    )


# ─────────────────────────────────────────────────────────────────────────────
# FIX 3 – Bar / Horizontal-bar: unclipped value labels
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_value(v: float) -> str:
    """Human-readable compact number format."""
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    if abs(v) >= 1_000:
        return f"{v/1_000:.1f}K"
    # Use integer display when value is whole, else up to 2 decimal places
    return f"{v:g}"


def _bar_chart(labels, datasets, title, width, height, dpi):
    fig, ax = plt.subplots(figsize=(width, height))
    x = np.arange(len(labels))
    n = len(datasets)
    bar_width = min(0.8 / n, 0.35)   # cap individual bar width for readability

    all_values = [v for ds in datasets for v in ds["data"]]
    y_max = max((v for v in all_values if v >= 0), default=0)
    y_min = min((v for v in all_values if v < 0), default=0)
    has_neg = y_min < 0

    containers = []
    for i, ds in enumerate(datasets):
        offset = (i - n / 2 + 0.5) * bar_width
        c = ax.bar(
            x + offset,
            ds["data"],
            width=bar_width,
            label=ds.get("label", f"Series {i+1}"),
            color=COLORS[i % len(COLORS)],
            alpha=0.88,
        )
        containers.append(c)

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    _apply_category_label_layout(ax, labels=labels, category_axis="x")

    # ── Expand y-axis so labels above bars are never clipped ─────────────────
    total_bars = len(labels) * max(1, n)
    show_labels = total_bars <= 80

    if show_labels:
        # Add ~10% padding above tallest bar and below deepest negative bar
        y_range = (y_max - y_min) or 1
        pad = y_range * 0.12
        ax.set_ylim(
            (y_min - pad) if has_neg else ax.get_ylim()[0],
            y_max + pad,
        )

        for container, ds in zip(containers, datasets):
            for rect, val in zip(container, ds["data"]):
                bar_h = rect.get_height()
                bar_w = rect.get_width()
                x_c = rect.get_x() + bar_w / 2
                label_txt = _fmt_value(val)

                # Decide placement: inside bar if bar is tall enough,
                # otherwise just above (positive) or below (negative) the bar.
                bar_px_h = abs(bar_h) / (y_max - y_min + 1e-9) * height * dpi
                place_inside = bar_px_h > 30 and abs(bar_h) > (y_range * 0.08)

                if val >= 0:
                    if place_inside:
                        y_pos = bar_h * 0.5
                        va = "center"
                        color = "white"
                        fw = "bold"
                    else:
                        y_pos = bar_h + y_range * 0.01
                        va = "bottom"
                        color = "#333333"
                        fw = "normal"
                else:
                    if place_inside:
                        y_pos = bar_h * 0.5
                        va = "center"
                        color = "white"
                        fw = "bold"
                    else:
                        y_pos = bar_h - y_range * 0.01
                        va = "top"
                        color = "#333333"
                        fw = "normal"

                ax.text(
                    x_c, y_pos, label_txt,
                    ha="center", va=va,
                    fontsize=8, color=color, fontweight=fw,
                    clip_on=False,   # ← prevents Matplotlib from clipping
                )

    _maybe_move_legend_outside(ax, label_count=len(labels), dataset_count=n)
    _apply_common_style(ax, title)
    return _fig_to_base64(fig, dpi=dpi)


def _horizontal_bar_chart(labels, datasets, title, width, height, dpi):
    fig, ax = plt.subplots(figsize=(width, height))
    y = np.arange(len(labels))
    n = len(datasets)
    bar_height = min(0.8 / n, 0.35)

    all_values = [v for ds in datasets for v in ds["data"]]
    x_max = max((v for v in all_values if v >= 0), default=0)
    x_min = min((v for v in all_values if v < 0), default=0)
    has_neg = x_min < 0

    containers = []
    for i, ds in enumerate(datasets):
        offset = (i - n / 2 + 0.5) * bar_height
        c = ax.barh(
            y + offset,
            ds["data"],
            height=bar_height,
            label=ds.get("label", f"Series {i+1}"),
            color=COLORS[i % len(COLORS)],
            alpha=0.88,
        )
        containers.append(c)

    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    _apply_category_label_layout(ax, labels=labels, category_axis="y")

    # ── Expand x-axis so labels beyond bars are never clipped ────────────────
    total_bars = len(labels) * max(1, n)
    show_labels = total_bars <= 80

    if show_labels:
        x_range = (x_max - x_min) or 1
        pad = x_range * 0.12
        ax.set_xlim(
            (x_min - pad) if has_neg else ax.get_xlim()[0],
            x_max + pad,
        )

        for container, ds in zip(containers, datasets):
            for rect, val in zip(container, ds["data"]):
                bar_w = rect.get_width()
                bar_h = rect.get_height()
                y_c = rect.get_y() + bar_h / 2
                label_txt = _fmt_value(val)

                bar_px_w = abs(bar_w) / (x_range + 1e-9) * width * dpi
                place_inside = bar_px_w > 40 and abs(bar_w) > x_range * 0.08

                if val >= 0:
                    if place_inside:
                        x_pos = bar_w * 0.5
                        ha = "center"
                        color = "white"
                        fw = "bold"
                    else:
                        x_pos = bar_w + x_range * 0.01
                        ha = "left"
                        color = "#333333"
                        fw = "normal"
                else:
                    if place_inside:
                        x_pos = bar_w * 0.5
                        ha = "center"
                        color = "white"
                        fw = "bold"
                    else:
                        x_pos = bar_w - x_range * 0.01
                        ha = "right"
                        color = "#333333"
                        fw = "normal"

                ax.text(
                    x_pos, y_c, label_txt,
                    ha=ha, va="center",
                    fontsize=8, color=color, fontweight=fw,
                    clip_on=False,
                )

    _maybe_move_legend_outside(ax, label_count=len(labels), dataset_count=n)
    _apply_common_style(ax, title)
    return _fig_to_base64(fig, dpi=dpi)


# ─────────────────────────────────────────────────────────────────────────────
# Line / Area / Radar – unchanged structure, guards added
# ─────────────────────────────────────────────────────────────────────────────

def _line_chart(labels, datasets, title, width, height, dpi):
    fig, ax = plt.subplots(figsize=(width, height))
    x = np.arange(len(labels))

    for i, ds in enumerate(datasets):
        ax.plot(
            x, ds["data"],
            marker="o", linewidth=2,
            label=ds.get("label", f"Series {i+1}"),
            color=COLORS[i % len(COLORS)],
        )

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    _apply_category_label_layout(ax, labels=labels, category_axis="x")
    _maybe_move_legend_outside(ax, label_count=len(labels), dataset_count=len(datasets))
    _apply_common_style(ax, title)
    return _fig_to_base64(fig, dpi=dpi)


def _area_chart(labels, datasets, title, width, height, dpi):
    fig, ax = plt.subplots(figsize=(width, height))
    x = np.arange(len(labels))

    for i, ds in enumerate(datasets):
        color = COLORS[i % len(COLORS)]
        ax.fill_between(x, ds["data"], alpha=0.35, color=color)
        ax.plot(
            x, ds["data"],
            marker="o", linewidth=2,
            label=ds.get("label", f"Series {i+1}"),
            color=color,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    _apply_category_label_layout(ax, labels=labels, category_axis="x")
    _maybe_move_legend_outside(ax, label_count=len(labels), dataset_count=len(datasets))
    _apply_common_style(ax, title)
    return _fig_to_base64(fig, dpi=dpi)


def _radar_chart(labels, datasets, title, width, height, dpi):
    N = len(labels)
    if N < 3:
        raise ValueError("Radar chart requires at least 3 labels.")
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(width, height), subplot_kw={"polar": True})

    for i, ds in enumerate(datasets):
        values = list(ds["data"]) + [ds["data"][0]]
        color = COLORS[i % len(COLORS)]
        ax.plot(angles, values, "o-", linewidth=2, color=color,
                label=ds.get("label", f"Series {i+1}"))
        ax.fill(angles, values, alpha=0.2, color=color)

    ax.set_thetagrids(np.degrees(angles[:-1]), labels)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))
    if title:
        ax.set_title(title, fontsize=14, fontweight="bold", pad=20)
    return _fig_to_base64(fig, dpi=dpi)

