"""CVaR and the summary statistics, against brute force and the Rockafellar-Uryasev form."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fracsched.risk_measures import cvar, quantile, summarize

costs = st.lists(st.floats(-1e6, 1e6, allow_nan=False), min_size=1, max_size=40)


def rockafellar_uryasev(x: np.ndarray, alpha: float) -> float:
    # Oracle: the objective is piecewise linear and convex in eta, so its minimum is at one of
    # the data points; evaluate it at every one (brute force).
    return min(eta + np.maximum(x - eta, 0).sum() / ((1 - alpha) * x.size) for eta in x)


def test_cvar_by_hand() -> None:
    x = np.array([1.0, 2.0, 3.0, 4.0, 10.0])
    assert cvar(x, 0.0) == pytest.approx(4.0)  # the mean
    assert cvar(x, 0.6) == pytest.approx(7.0)  # mean of the worst two
    assert cvar(x, 0.7) == pytest.approx((10 + 0.5 * 4) / 1.5)  # fractional boundary
    with pytest.raises(ValueError):
        cvar(x, 1.0)


@settings(max_examples=200, deadline=None)
@given(x=costs, alpha=st.floats(0.0, 0.99))
def test_cvar_is_the_rockafellar_uryasev_minimum(x: list[float], alpha: float) -> None:
    a = np.array(x)
    assert cvar(a, alpha) == pytest.approx(rockafellar_uryasev(a, alpha), rel=1e-9, abs=1e-6)


@settings(max_examples=200, deadline=None)
@given(x=costs, a1=st.floats(0.0, 0.99), a2=st.floats(0.0, 0.99))
def test_cvar_lies_between_mean_and_max_and_rises_with_alpha(
    x: list[float], a1: float, a2: float
) -> None:
    a = np.array(x)
    lo, hi = sorted((a1, a2))
    tol = 1e-9 * (1 + np.abs(a).max())
    assert a.mean() - tol <= cvar(a, lo) <= cvar(a, hi) + tol
    assert cvar(a, hi) <= a.max() + tol


def test_summary() -> None:
    x = np.arange(1.0, 101.0)
    s = summarize(x)
    assert s.mean == 50.5
    assert s.se == pytest.approx(x.std(ddof=1) / 10)
    assert (s.p10, s.p50, s.p90, s.p99, s.max) == (10.0, 50.0, 90.0, 99.0, 100.0)
    assert s.cvar90 == pytest.approx(95.5)  # mean of 91..100
    assert quantile(x, 0.25) == 25.0
    assert summarize(np.array([3.0])).sd == 0.0
