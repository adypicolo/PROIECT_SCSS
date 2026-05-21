import io
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.figure import Figure
import numpy as np

_DARK_BG = "#1A0A0E"
_CARD_BG = "#2D1218"
_GRID = "#3A171D55"
_TEXT = "#F7ECE4"
_ACCENT_PINK = "#B65B62"
_ACCENT_GOLD = "#C9A15A"
_ACCENT_TEAL = "#4AA6A0"
_ACCENT_RED = "#E05555"
_ACCENT_GREEN = "#2E8B57"

_PALETTE = ["#4AA6A0", "#C9A15A", "#B65B62", "#7B8CDE", "#E0A35E", "#6BC9A8", "#D47B93"]

def _apply_dark_theme(ax: plt.Axes, fig: Figure):

    fig.patch.set_facecolor(_DARK_BG)
    ax.set_facecolor(_CARD_BG)
    ax.tick_params(colors=_TEXT, which="both")
    ax.xaxis.label.set_color(_TEXT)
    ax.yaxis.label.set_color(_TEXT)
    ax.title.set_color(_TEXT)
    for spine in ax.spines.values():
        spine.set_color("#3A171D")
        spine.set_linewidth(0.5)
    ax.grid(True, color=_GRID, linestyle="--", linewidth=0.4, alpha=0.5)

def generate_cost_evolution_chart(states: list[dict[str, Any]], dpi: int = 150) -> Figure:
    iterations = []
    costs = []
    for st in states:
        iterations.append(st["iteratie"])

        cost_total = 0.0
        orig_m = st["original_m"]
        orig_n = st["original_n"]
        for (i, j), qty in st["alocari"].items():
            if i < orig_m and j < orig_n:
                cost_total += qty.real * st["cost"][i][j]
        costs.append(cost_total)

    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=dpi)
    _apply_dark_theme(ax, fig)

    min_cost = min(costs)
    max_cost = max(costs)
    cost_span = max(max_cost - min_cost, max(max_cost, 1.0) * 0.08)
    baseline = max(0.0, min_cost - cost_span * 0.2)

    ax.plot(iterations, costs, color=_ACCENT_TEAL, linewidth=2.5, marker="o",
            markersize=8, markerfacecolor=_ACCENT_GOLD, markeredgecolor=_ACCENT_GOLD,
            markeredgewidth=1.5, zorder=5, label="Cost transport")

    ax.fill_between(iterations, costs, baseline, color=_ACCENT_TEAL, alpha=0.10)

    ax.plot(iterations[-1], costs[-1], "o", color=_ACCENT_GREEN, markersize=14,
            markeredgecolor="#ffffff", markeredgewidth=2, zorder=6)
    ax.annotate(f"Optim: {costs[-1]:g} UM",
                xy=(iterations[-1], costs[-1]),
                xytext=(iterations[-1] - 0.45, costs[-1] + cost_span * 0.2),
                fontsize=11, color=_ACCENT_GREEN, fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=_ACCENT_GREEN, lw=1.5))

    ax.annotate(f"NW: {costs[0]:g} UM",
                xy=(iterations[0], costs[0]),
                xytext=(iterations[0] + 0.28, costs[0] + cost_span * 0.08),
                fontsize=10, color=_ACCENT_PINK, fontweight="bold")

    for iteration, cost in zip(iterations, costs):
        ax.text(iteration, cost + cost_span * 0.035, f"{cost:.0f}",
                fontsize=9, fontweight="bold", color=_TEXT, ha="center", va="bottom")

    ax.set_xlabel("Iterația", fontsize=12, fontweight="bold")
    ax.set_ylabel("Cost total (UM)", fontsize=12, fontweight="bold")
    ax.set_title("Evoluția costului total", fontsize=16, fontweight="bold", pad=15)
    ax.set_xticks(iterations)
    ax.set_ylim(baseline, max_cost + cost_span * 0.3)

    if len(costs) > 1 and costs[0] != 0:
        economy = (costs[0] - costs[-1]) / costs[0] * 100
        ax.text(0.98, 0.95, f"Economie: {economy:.1f}%",
                transform=ax.transAxes, fontsize=12, fontweight="bold",
                color=_ACCENT_GREEN, ha="right", va="top",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="#2E8B5722", edgecolor=_ACCENT_GREEN, linewidth=1.5))

    fig.tight_layout(pad=1.5)
    return fig

def generate_flow_distribution_chart(
    final_state: dict[str, Any],
    destination_labels: list[str],
    demand: list[float],
    dpi: int = 150,
) -> Figure:
    orig_m = final_state["original_m"]
    orig_n = final_state["original_n"]

    flow_per_dest = [0.0] * orig_n
    for (i, j), qty in final_state["alocari"].items():
        if i < orig_m and j < orig_n:
            flow_per_dest[j] += qty.real

    labels = destination_labels[:orig_n]
    needs = demand[:orig_n]

    lowered = [l.lower() for l in labels]
    tumor_idx = next(
        (i for i, l in enumerate(lowered) if any(t in l for t in ("tumor", "tumora", "neoplasm", "cancer"))),
        None,
    )

    colors = []
    for i in range(len(labels)):
        if i == tumor_idx:
            colors.append(_ACCENT_RED)
        else:
            colors.append(_PALETTE[i % len(_PALETTE)])

    fig, ax = plt.subplots(figsize=(10, 5.4), dpi=dpi)
    _apply_dark_theme(ax, fig)

    y_pos = np.arange(len(labels))
    bar_height = 0.34

    bars1 = ax.barh(y_pos - bar_height / 2, flow_per_dest, bar_height,
                    color=colors, alpha=0.85, label="Flux alocat", edgecolor="none",
                    zorder=3)

    bars2 = ax.barh(y_pos + bar_height / 2, needs, bar_height,
                    color="#ffffff15", edgecolor="#ffffff30", linewidth=0.8,
                    label="Necesar", zorder=2)

    for bar, val in zip(bars1, flow_per_dest):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                f"{val:g}", va="center", ha="left", fontsize=10, color=_TEXT, fontweight="bold")

    for bar, need in zip(bars2, needs):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                f"nec. {need:g}", va="center", ha="left", fontsize=9, color="#d8c6bb")

    max_axis = max(max(flow_per_dest, default=0.0), max(needs, default=0.0), 1.0)
    ax.set_xlim(0, max_axis * 1.25)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=11, fontweight="bold")
    ax.set_xlabel("Cantitate", fontsize=12, fontweight="bold")
    ax.set_title("Acoperirea destinațiilor", fontsize=16, fontweight="bold", pad=15)
    ax.invert_yaxis()
    ax.legend(loc="lower right", fontsize=10, facecolor=_CARD_BG, edgecolor="#3A171D",
              labelcolor=_TEXT)

    deficits = [max(need - flow, 0.0) for flow, need in zip(flow_per_dest, needs)]
    if any(deficits):
        max_deficit = max(deficits)
        deficit_label = labels[deficits.index(max_deficit)]
        ax.text(0.98, 0.95, f"Deficit maxim: {deficit_label} ({max_deficit:g})",
                transform=ax.transAxes, fontsize=11, fontweight="bold",
                color=_ACCENT_GOLD, ha="right", va="top",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="#C9A15A22", edgecolor=_ACCENT_GOLD, linewidth=1.2))
    else:
        ax.text(0.98, 0.95, "Toate destinațiile sunt acoperite",
                transform=ax.transAxes, fontsize=11, fontweight="bold",
                color=_ACCENT_GREEN, ha="right", va="top",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="#2E8B5722", edgecolor=_ACCENT_GREEN, linewidth=1.2))

    if tumor_idx is not None:
        ax.text(0.98, 0.05, f"Tumora: {flow_per_dest[tumor_idx]:g} unități",
                transform=ax.transAxes, fontsize=11, fontweight="bold",
                color=_ACCENT_RED, ha="right", va="bottom",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="#E0555522", edgecolor=_ACCENT_RED, linewidth=1.5))

    fig.tight_layout(pad=1.5)
    return fig

def generate_network_flow_chart(
    final_state: dict[str, Any],
    source_labels: list[str],
    destination_labels: list[str],
    dpi: int = 150,
) -> Figure:
    orig_m = final_state["original_m"]
    orig_n = final_state["original_n"]

    src_labels = source_labels[:orig_m]
    dst_labels = destination_labels[:orig_n]

    fig, ax = plt.subplots(figsize=(11.4, 6.9), dpi=dpi)
    _apply_dark_theme(ax, fig)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, max(orig_m, orig_n) + 1.8)
    ax.axis("off")
    fig.patch.set_facecolor(_DARK_BG)
    ax.set_facecolor(_DARK_BG)

    src_x = 2.1
    dst_x = 7.9
    top_y = max(orig_m, orig_n) + 0.7
    src_ys = np.linspace(max(orig_m, orig_n) + 0.15, 0.85, orig_m)
    dst_ys = np.linspace(max(orig_m, orig_n) + 0.15, 0.85, orig_n)

    left_panel = mpatches.FancyBboxPatch(
        (0.45, 0.35), 2.6, top_y - 0.15,
        boxstyle="round,pad=0.12,rounding_size=0.18",
        facecolor="#FFF2DF10", edgecolor="#F4C9BC22", linewidth=1.0, zorder=0
    )
    right_panel = mpatches.FancyBboxPatch(
        (6.95, 0.35), 2.6, top_y - 0.15,
        boxstyle="round,pad=0.12,rounding_size=0.18",
        facecolor="#FFF2DF10", edgecolor="#F4C9BC22", linewidth=1.0, zorder=0
    )
    ax.add_patch(left_panel)
    ax.add_patch(right_panel)
    ax.text(1.75, top_y + 0.08, "Surse", color=_ACCENT_GOLD, fontsize=12, fontweight="bold", ha="center")
    ax.text(8.25, top_y + 0.08, "Destinatii", color=_ACCENT_GOLD, fontsize=12, fontweight="bold", ha="center")

    lowered = [l.lower() for l in dst_labels]
    tumor_idx = next(
        (i for i, l in enumerate(lowered) if any(t in l for t in ("tumor", "tumora", "neoplasm", "cancer"))),
        None,
    )

    max_flow = 0.0
    flows = {}
    for (i, j), qty in final_state["alocari"].items():
        if i < orig_m and j < orig_n and qty.real > 0:
            flows[(i, j)] = qty.real
            max_flow = max(max_flow, qty.real)

    if max_flow == 0:
        max_flow = 1.0

    for (i, j), flow in flows.items():
        lw = 1.8 + (flow / max_flow) * 6.6
        color = _ACCENT_RED if j == tumor_idx else _ACCENT_TEAL
        alpha = 0.4 + (flow / max_flow) * 0.5

        ax.annotate("",
                     xy=(dst_x - 0.85, dst_ys[j]),
                     xytext=(src_x + 0.85, src_ys[i]),
                     arrowprops=dict(
                         arrowstyle="-|>",
                         color=color,
                         lw=lw,
                         alpha=alpha,
                         connectionstyle="arc3,rad=0.08",
                         mutation_scale=12,
                     ))

        mid_x = (src_x + dst_x) / 2
        mid_y = (src_ys[i] + dst_ys[j]) / 2
        ax.text(mid_x, mid_y, f"{flow:g}",
                fontsize=9, fontweight="bold", color=_TEXT, alpha=0.9,
                ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.15", facecolor=_DARK_BG, edgecolor="none", alpha=0.7))

    for i, label in enumerate(src_labels):
        card = mpatches.FancyBboxPatch(
            (0.72, src_ys[i] - 0.28), 2.05, 0.56,
            boxstyle="round,pad=0.06,rounding_size=0.14",
            facecolor="#F0C78E14", edgecolor="#F0C78E44", linewidth=1.2, zorder=5
        )
        ax.add_patch(card)
        ax.text(1.75, src_ys[i] + 0.07, label, ha="center", va="center",
                fontsize=9.5, fontweight="bold", color=_TEXT, zorder=6)

    for j, label in enumerate(dst_labels):
        color = _ACCENT_RED if j == tumor_idx else _ACCENT_TEAL
        rect = mpatches.FancyBboxPatch(
            (7.22, dst_ys[j] - 0.28), 2.05, 0.56,
            boxstyle="round,pad=0.06,rounding_size=0.14",
            facecolor=f"{color}22", edgecolor=f"{color}", linewidth=1.2, zorder=5
        )
        ax.add_patch(rect)
        display_label = label if len(label) <= 18 else label[:17] + "…"
        ax.text(8.25, dst_ys[j] + 0.07, display_label, ha="center", va="center",
                fontsize=9, fontweight="bold", color=_TEXT, zorder=6)

    ax.set_title("Harta rutelor active", fontsize=16, fontweight="bold",
                 color=_TEXT, pad=20)

    active_routes = len(flows)
    total_flow = sum(flows.values())
    ax.text(0.02, 0.96, f"Rute active: {active_routes} | Flux total: {total_flow:g}",
            transform=ax.transAxes, fontsize=11, fontweight="bold",
            color=_TEXT, ha="left", va="top",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#ffffff10", edgecolor="#ffffff22", linewidth=1.0))

    legend_elements = [
        mpatches.Patch(facecolor=_ACCENT_GOLD, label="Surse"),
        mpatches.Patch(facecolor=_ACCENT_TEAL, label="Destinatii sanatoase"),
    ]
    if tumor_idx is not None:
        legend_elements.append(mpatches.Patch(facecolor=_ACCENT_RED, label="Punct de consum parazit"))
    ax.legend(handles=legend_elements, loc="lower center", fontsize=9,
              facecolor=_CARD_BG, edgecolor="#3A171D", labelcolor=_TEXT, ncol=3)

    fig.tight_layout(pad=1.5)
    return fig

def save_figure_to_bytes(fig: Figure, fmt: str = "png") -> bytes:

    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, facecolor=fig.get_facecolor(), edgecolor="none",
                bbox_inches="tight", pad_inches=0.15)
    buf.seek(0)
    data = buf.read()
    buf.close()
    plt.close(fig)
    return data
