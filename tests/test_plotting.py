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
