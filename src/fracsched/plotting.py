"""Figures for the validation scripts and the lessons (matplotlib only, no global state)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
from matplotlib.figure import Figure

from fracsched.utilization_model.model import FloatArray

COLORS = ("#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#8c564b")


def utilization_paths(u: FloatArray, mean: FloatArray, *, n_paths: int = 3) -> Figure:
    """Weekly hours of a few aircraft against the mean (the seasonal curve)."""
    fig = Figure(figsize=(8, 3.6), layout="constrained")
    ax = fig.add_subplot()
    weeks = np.arange(1, u.shape[-1] + 1)
    for i in range(n_paths):
        ax.plot(weeks, u[i], lw=1.2, color=COLORS[i], label=f"aircraft {i + 1}")
    ax.plot(weeks, mean, "k--", lw=1.5, label="mean")
    ax.set(xlabel="week", ylabel="flight hours in the week", xlim=(1, weeks[-1]))
    ax.legend(ncols=4, fontsize=8, loc="upper left")
    return fig


def annual_hours_histogram(hours: FloatArray, design: float) -> Figure:
    fig = Figure(figsize=(6, 3.6), layout="constrained")
    ax = fig.add_subplot()
    ax.hist(hours, bins=60, color=COLORS[0], alpha=0.8)
    ax.axvline(design, color="k", ls="--", label=f"design {design:.0f} FH")
    ax.set(xlabel="flight hours in a year (one aircraft)", ylabel="aircraft-years")
    ax.legend(fontsize=8)
    return fig


def weeks_to_limit(weeks: Mapping[str, FloatArray], deterministic: Mapping[str, float]) -> Figure:
    """Distribution of the calendar length of FH intervals, with the at-mean value marked."""
    fig = Figure(figsize=(7, 3.6), layout="constrained")
    ax = fig.add_subplot()
    for i, (label, w) in enumerate(weeks.items()):
        bins = np.arange(float(np.min(w)) - 0.5, float(np.max(w)) + 1.5).tolist()
        ax.hist(w, bins=bins, color=COLORS[i], alpha=0.55, label=label, density=True)
        ax.axvline(deterministic[label], color=COLORS[i], ls="--")
    ax.set(xlabel="weeks until the interval is flown", ylabel="share of aircraft")
    ax.legend(fontsize=8)
    return fig


def cost_distributions(
    costs: Mapping[str, FloatArray], *, unit: float = 1e6, xlabel: str = "cost ($M)"
) -> Figure:
    """Overlaid histograms of per-scenario costs for several plans, means marked."""
    fig = Figure(figsize=(7, 3.8), layout="constrained")
    ax = fig.add_subplot()
    values = np.concatenate([np.asarray(c) for c in costs.values()]) / unit
    bins = np.linspace(float(np.min(values)), float(np.max(values)), 60).tolist()
    for i, (label, c) in enumerate(costs.items()):
        c = np.asarray(c) / unit
        ax.hist(c, bins=bins, alpha=0.5, color=COLORS[i], label=label, density=True)
        ax.axvline(c.mean(), color=COLORS[i], ls="--", lw=1.2)
    ax.set(xlabel=xlabel, ylabel="density")
    ax.legend(fontsize=8)
    return fig


def lines(
    x: Sequence[float],
    series: Mapping[str, Sequence[float]],
    *,
    xlabel: str,
    ylabel: str,
    logx: bool = False,
) -> Figure:
    fig = Figure(figsize=(6.5, 3.8), layout="constrained")
    ax = fig.add_subplot()
    for i, (label, y) in enumerate(series.items()):
        ax.plot(x, y, "o-", color=COLORS[i % len(COLORS)], label=label, ms=4)
    if logx:
        ax.set_xscale("log")
    ax.set(xlabel=xlabel, ylabel=ylabel)
    ax.legend(fontsize=8)
    return fig


def bars(
    labels: Sequence[str], values: Sequence[float], errors: Sequence[float], *, ylabel: str
) -> Figure:
    """One bar per label with a ±error whisker."""
    fig = Figure(figsize=(7, 3.8), layout="constrained")
    ax = fig.add_subplot()
    x = np.arange(len(labels))
    ax.bar(
        x,
        values,
        yerr=errors,
        color=[COLORS[i % len(COLORS)] for i in range(len(labels))],
        capsize=4,
        alpha=0.85,
    )
    ax.set_xticks(x, labels, fontsize=8)
    ax.set_ylabel(ylabel)
    lo = min(v - e for v, e in zip(values, errors, strict=True))
    hi = max(v + e for v, e in zip(values, errors, strict=True))
    ax.set_ylim(lo - 0.15 * (hi - lo), hi + 0.15 * (hi - lo))
    return fig


def replans(
    plans: Sequence[Sequence[int]],
    epochs: Sequence[int],
    executed: Sequence[int],
    forced: Sequence[int],
    hours: FloatArray,
    mean_rate: float,
) -> Figure:
    """How one component's plan moves as the year unfolds.

    Top: the aircraft's cumulative hours. Bottom: one row per re-plan epoch with the task weeks
    planned at that epoch (dots); executed tasks (squares) and forced tasks (crosses) below.
    """
    fig = Figure(figsize=(8, 5), layout="constrained")
    top, bottom = fig.subplots(2, 1, sharex=True, height_ratios=(1, 2))
    weeks = np.arange(hours.size + 1)
    top.plot(weeks, np.concatenate([[0.0], np.cumsum(hours)]), color=COLORS[0])
    top.plot(weeks, weeks * mean_rate, "k--", lw=1, label="at the design rate")
    top.legend(fontsize=7)
    top.set_ylabel("cumulative FH")
    for row, (epoch, plan) in enumerate(zip(epochs, plans, strict=True)):
        future = [t for t in plan if t >= epoch]
        bottom.scatter(future, [row] * len(future), color=COLORS[1], s=18)
        bottom.plot([epoch, epoch], [row - 0.4, row + 0.4], color="k", lw=0.8)
    base = len(epochs) + 0.5
    bottom.scatter(executed, [base] * len(executed), marker="s", color=COLORS[2], label="executed")
    bottom.scatter(forced, [base + 1] * len(forced), marker="x", color="k", label="forced")
    bottom.set_yticks(
        [*range(len(epochs)), base, base + 1],
        [*(f"plan at week {e}" for e in epochs), "executed", "forced"],
        fontsize=7,
    )
    bottom.set_xlabel("week")
    return fig


def gantt_scenarios(
    groups: Sequence[str],
    planned: Sequence[Sequence[int]],
    forced: Mapping[str, Sequence[Sequence[int]]],
    horizon: int,
) -> Figure:
    """One panel per future: planned tasks (bars, identical in every panel) and that future's
    forced tasks (crosses), one row per component; ``groups[r]`` names row ``r``'s aircraft."""
    n = len(forced)
    fig = Figure(figsize=(9, 1.0 + 0.055 * len(groups) * n), layout="constrained")
    axes = np.atleast_1d(fig.subplots(n, 1, sharex=True))
    rows = np.arange(len(groups))
    names = list(dict.fromkeys(groups))
    idx = range(len(groups))
    centres = [float(np.mean([r for r in idx if groups[r] == g])) for g in names]
    edges = [r - 0.5 for r in idx[1:] if groups[r] != groups[r - 1]]
    for ax, (title, weeks) in zip(axes, forced.items(), strict=True):
        for r, events in zip(rows, planned, strict=True):
            ax.scatter(events, [r] * len(events), marker="|", s=30, color=COLORS[0])
        for r, events in zip(rows, weeks, strict=True):
            ax.scatter(events, [r] * len(events), marker="x", s=20, color=COLORS[1])
        for e in edges:
            ax.axhline(e, color="0.85", lw=0.6)
        ax.set_yticks(centres, names, fontsize=6)
        ax.set_title(title, fontsize=9, loc="left")
        ax.set_xlim(-1, horizon)
        ax.set_ylim(len(groups) - 0.5, -0.5)
    axes[-1].set_xlabel("week (bars: planned tasks; crosses: tasks forced in this future)")
    return fig


def gantt_html(
    labels: Sequence[str],
    planned: Sequence[Sequence[int]],
    forced: Mapping[str, Sequence[Sequence[int]]],
) -> str:
    """The same chart as ``gantt_scenarios``, interactive (Plotly, library from its CDN)."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(
        rows=len(forced),
        cols=1,
        shared_xaxes=True,
        subplot_titles=list(forced),
        vertical_spacing=0.05,
    )
    for i, weeks in enumerate(forced.values(), start=1):
        xs = [t for events in planned for t in events]
        ys = [labels[r] for r, events in enumerate(planned) for _ in events]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="markers",
                marker={"symbol": "line-ns-open", "size": 10},
                name="planned",
                showlegend=i == 1,
                marker_color=COLORS[0],
            ),
            row=i,
            col=1,
        )
        xs = [t for events in weeks for t in events]
        ys = [labels[r] for r, events in enumerate(weeks) for _ in events]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="markers",
                marker={"symbol": "x", "size": 8},
                name="forced",
                showlegend=i == 1,
                marker_color=COLORS[1],
            ),
            row=i,
            col=1,
        )
    fig.update_layout(height=320 * len(forced), template="plotly_white")
    return str(fig.to_html(include_plotlyjs="cdn", full_html=True))
