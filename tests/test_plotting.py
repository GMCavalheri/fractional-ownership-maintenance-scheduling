"""The figure helpers draw what they are given (one artist per series, labelled axes)."""

import numpy as np

from fracsched import plotting


def test_utilization_paths_and_histograms() -> None:
    rng = np.random.default_rng(0)
    u = rng.gamma(4.0, 4.0, size=(5, 52))
    fig = plotting.utilization_paths(u, u.mean(axis=0), n_paths=3)
    assert len(fig.axes[0].lines) == 4
    fig = plotting.annual_hours_histogram(u.sum(axis=1), 800.0)
    assert fig.axes[0].get_xlabel().startswith("flight hours")
    fig = plotting.weeks_to_limit({"a": np.array([3.0, 4.0, 5.0])}, {"a": 4.0})
    assert len(fig.axes[0].lines) == 1


def test_cost_distributions_and_lines() -> None:
    fig = plotting.cost_distributions({"x": np.array([1e6, 2e6]), "y": np.array([1.5e6, 3e6])})
    assert len(fig.axes[0].lines) == 2
    fig = plotting.lines([1, 10], {"a": [1, 2], "b": [2, 3]}, xlabel="x", ylabel="y", logx=True)
    assert fig.axes[0].get_xscale() == "log"


def test_bars_replans_and_gantt_figures() -> None:
    fig = plotting.bars(["x", "y"], [1.0, 2.0], [0.1, 0.2], ylabel="v")
    assert len(fig.axes[0].patches) == 2
    fig = plotting.replans(
        plans=[[3, 20], [3, 18]],
        epochs=[0, 4],
        executed=[3, 18],
        forced=[10],
        hours=np.full(26, 15.0),
        mean_rate=15.0,
    )
    assert len(fig.axes) == 2
    planned = [[3, 20], [10]]
    forced = {"slow": [[], []], "fast": [[15], [8, 30]]}
    fig = plotting.gantt_scenarios(["aircraft 1", "aircraft 1"], planned, forced, 52)
    assert len(fig.axes) == 2
    assert [t.get_text() for t in fig.axes[0].get_yticklabels()] == ["aircraft 1"]
    html = plotting.gantt_html(["a1 APU", "a1 brakes"], planned, forced)
    assert "<html>" in html and "forced" in html
