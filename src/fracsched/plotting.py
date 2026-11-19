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
