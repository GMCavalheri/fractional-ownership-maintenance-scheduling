"""Phase 1: the utilization model against closed forms and independent oracles."""

import itertools

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from scipy import stats

from fracsched.utilization_model import (
    UtilizationModel,
    UtilizationState,
    annual_mean,
    annual_sd,
    autocorrelation,
    cross_correlation,
    d_second_moment,
    default_model,
    fleet_annual_sd,
    hours_to_weeks_quantiles,
    load_parameters,
    seasonality,
    stationary_distribution,
    weekly_covariance,
    weekly_mean,
    weeks_to_reach,
    x_second_moment,
)

MODEL = default_model(capped=False)


def test_stationary_distribution_is_the_limit_of_the_chain() -> None:
    # Oracle: rows of P^n converge to π for an ergodic chain (here n = 2000 is far past mixing).
    limit = np.linalg.matrix_power(MODEL.P, 2000)
    np.testing.assert_allclose(MODEL.pi, limit[0], atol=1e-12)
    np.testing.assert_allclose(MODEL.pi @ MODEL.P, MODEL.pi, atol=1e-14)


def test_mean_annual_hours_are_calibrated_to_the_programme_design() -> None:
    # 800 FH a year per aircraft (1/16 share = 50 h); the scaling makes it exact.
    assert annual_mean(MODEL) == pytest.approx(load_parameters()["annual_mean_fh"], rel=1e-12)
    assert MODEL.mean_weekly_fh == pytest.approx(800 / 52, rel=1e-12)


def test_seasonality_has_mean_one_and_holiday_uplift() -> None:
    m = seasonality(0.15, 28, 0.3)
    assert m.mean() == pytest.approx(1.0, abs=1e-14)
    plain = seasonality(0.15, 28, 0.0)
    np.testing.assert_allclose(m[46] / plain[46], m[0] / plain[0] * 1.3, rtol=1e-12)
    assert int(np.argmax(plain)) == 27  # the 1-based peak week 28


def test_gamma_second_moment_given_regime() -> None:
    # Oracle: scipy's Gamma raw moment, mixed over the stationary regimes.
    expected = sum(
        p * stats.gamma(k, scale=mu / k).moment(2)
        for p, k, mu in zip(MODEL.pi, MODEL.shapes, MODEL.means, strict=True)
    )
    assert x_second_moment(MODEL, 0) == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize("lag", [1, 2, 3, 5])
def test_lagged_moment_by_enumerating_regime_paths(lag: int) -> None:
    # Oracle: brute-force sum over every regime path of length lag + 1 (3^(lag+1) paths).
    total = 0.0
    for path in itertools.product(range(3), repeat=lag + 1):
        prob = MODEL.pi[path[0]]
        for a, b in itertools.pairwise(path):
            prob *= MODEL.P[a, b]
        total += prob * MODEL.means[path[0]] * MODEL.means[path[-1]]
    assert x_second_moment(MODEL, lag) == pytest.approx(total, rel=1e-12)


@pytest.mark.parametrize("lag", [0, 1, 4])
def test_demand_factor_moment_by_quadrature(lag: int) -> None:
    # Oracle: 2-D Gauss-Hermite quadrature of E[exp(Z1 + Z2 - s²)] over the bivariate normal.
    s2 = MODEL.demand_log_var
    rho = MODEL.demand_ar**lag
    x, w = np.polynomial.hermite_e.hermegauss(60)
    w = w / w.sum()
    z1 = np.sqrt(s2) * x[:, None]
    z2 = np.sqrt(s2) * (rho * x[:, None] + np.sqrt(max(1 - rho**2, 0.0)) * x[None, :])
    value = float((w[:, None] * w[None, :] * np.exp(z1 + z2 - s2)).sum())
    assert d_second_moment(MODEL, lag) == pytest.approx(value, rel=1e-10)


def test_weekly_and_annual_moments_by_monte_carlo() -> None:
    # Oracle: simulation of the uncapped model; each check within 4 Monte Carlo SE.
    n = 20_000
    u, _ = MODEL.sample(np.random.default_rng(11), n, 1, 52)
    u = u[:, 0, :]
    se_mean = u.std(axis=0, ddof=1) / np.sqrt(n)
    assert np.all(np.abs(u.mean(axis=0) - weekly_mean(MODEL)) < 4 * se_mean)

    y = u.sum(axis=1)
    assert abs(y.mean() - annual_mean(MODEL)) < 4 * y.std(ddof=1) / np.sqrt(n)
    # SE of a sample variance: sqrt((m4 - s^4) / n) with the sample fourth central moment.
    centred = y - y.mean()
    se_var = np.sqrt(((centred**4).mean() - centred.var() ** 2) / n)
    assert abs(y.var(ddof=1) - annual_sd(MODEL) ** 2) < 4 * se_var

    cov = weekly_covariance(MODEL)
    for t, h in [(5, 1), (20, 3), (40, 8)]:
        prod = (u[:, t] - weekly_mean(MODEL)[t]) * (u[:, t + h] - weekly_mean(MODEL)[t + h])
        assert abs(prod.mean() - cov[t, t + h]) < 4 * prod.std(ddof=1) / np.sqrt(n)


def test_cross_aircraft_correlation_and_fleet_total_by_monte_carlo() -> None:
    n = 20_000
    u, _ = MODEL.sample(np.random.default_rng(12), n, 4, 52)
    deseason = u / MODEL.season[None, None, :]
    a, b = deseason[:, 0, :].ravel(), deseason[:, 1, :].ravel()
    # Weeks within a path are dependent, so use whole-path blocks for the SE.
    prod = (a - a.mean()) * (b - b.mean())
    var = deseason[:, 0, :].var()
    block_means = prod.reshape(n, 52).mean(axis=1)
    se = block_means.std(ddof=1) / np.sqrt(n) / var
    assert abs(prod.mean() / var - cross_correlation(MODEL)) < 4 * se

    fleet = u.sum(axis=(1, 2))
    centred = fleet - fleet.mean()
    se_var = np.sqrt(((centred**4).mean() - centred.var() ** 2) / n)
    assert abs(fleet.var(ddof=1) - fleet_annual_sd(MODEL, 4) ** 2) < 4 * se_var


def test_autocorrelation_decays_and_matches_the_covariance_matrix() -> None:
    cov = weekly_covariance(MODEL)
    sd = np.sqrt(np.diag(cov))
    for h in (1, 2, 6):
        # With the season factored out the correlation is exactly autocorrelation(h).
        assert cov[10, 10 + h] / (sd[10] * sd[10 + h]) == pytest.approx(
            autocorrelation(MODEL, h), rel=1e-12
        )
    acf = [autocorrelation(MODEL, h) for h in range(1, 30)]
    assert all(x > y for x, y in itertools.pairwise(acf))
    assert autocorrelation(MODEL, 0) == pytest.approx(1.0, rel=1e-14)


def test_cap_binds_rarely_and_lowers_the_mean_slightly() -> None:
    capped = default_model()
    u, _ = capped.sample(np.random.default_rng(3), 5000, 10, 52)
    assert u.max() <= capped.max_weekly_fh
    assert (u >= capped.max_weekly_fh).mean() < 0.01
    assert 0.99 * annual_mean(MODEL) < u.sum(axis=-1).mean() < annual_mean(MODEL)


def test_conditional_first_week_regimes_follow_the_transition_row() -> None:
    # Given every aircraft idle, next week's regime is a draw from row 0 of P: check the
    # frequencies within 4 binomial SE.
    n_s, n_a = 4000, 10
    state = UtilizationState(np.zeros((1, n_a), dtype=np.int64), np.zeros(1))
    _, after = MODEL.sample(np.random.default_rng(5), n_s, n_a, 1, state=state)
    freq = np.bincount(after.regimes.ravel(), minlength=3) / (n_s * n_a)
    se = np.sqrt(MODEL.P[0] * (1 - MODEL.P[0]) / (n_s * n_a))
    assert np.all(np.abs(freq - MODEL.P[0]) <= 4 * se + 1e-12)


@settings(max_examples=40, deadline=None)
@given(
    seed=st.integers(0, 2**32 - 1),
    regime=st.integers(0, 2),
    z=st.floats(-1.0, 1.0),
    start=st.integers(0, 51),
    cap=st.floats(5.0, 100.0),
)
def test_hours_are_bounded_and_absorbing_regimes_stay_put(
    seed: int, regime: int, z: float, start: int, cap: float
) -> None:
    model = UtilizationModel(
        P=np.eye(3),
        means=MODEL.means,
        shapes=MODEL.shapes,
        demand_ar=0.5,
        demand_sigma=0.1,
        season=MODEL.season,
        max_weekly_fh=cap,
    )
    state = UtilizationState(np.full((1, 3), regime, dtype=np.int64), np.array([z]))
    u, after = model.sample(np.random.default_rng(seed), 7, 3, 9, start_week=start, state=state)
    assert u.shape == (7, 3, 9)
    assert np.all(u >= 0) and np.all(u <= cap)
    assert np.all(after.regimes == regime)  # P = I: the history's regime persists


def test_seeded_sampling_is_reproducible() -> None:
    a, _ = MODEL.sample(np.random.default_rng(9), 3, 2, 5)
    b, _ = MODEL.sample(np.random.default_rng(9), 3, 2, 5)
    np.testing.assert_array_equal(a, b)


def test_weeks_to_reach_by_hand() -> None:
    u = np.array([[10.0, 10.0, 10.0, 10.0], [1.0, 1.0, 1.0, 1.0]])
    # 10 + 10 + 10 reaches 25 in week index 2; the second path never does (censored at 4).
    np.testing.assert_array_equal(weeks_to_reach(u, 25.0), [2, 4])
    np.testing.assert_array_equal(weeks_to_reach(u, 25.0, initial=20.0), [0, 4])
    assert hours_to_weeks_quantiles(np.full((5, 40), 15.0), 600.0) == (40.0, 40.0, 40.0)


def test_invalid_models_are_rejected() -> None:
    good = {
        "P": MODEL.P,
        "means": MODEL.means,
        "shapes": MODEL.shapes,
        "demand_ar": 0.5,
        "demand_sigma": 0.1,
        "season": MODEL.season,
    }
    bad = [
        {"P": np.ones((3, 3))},
        {"means": -MODEL.means},
        {"demand_ar": 1.0},
        {"season": np.ones(10)},
        {"max_weekly_fh": 0.0},
    ]
    for change in bad:
        with pytest.raises(ValueError):
            UtilizationModel(**{**good, **change})


def test_stationary_distribution_of_a_two_state_chain() -> None:
    # Closed form for a two-state chain: π = (q, p) / (p + q).
    p, q = 0.2, 0.05
    pi = stationary_distribution(np.array([[1 - p, p], [q, 1 - q]]))
    np.testing.assert_allclose(pi, [q / (p + q), p / (p + q)], atol=1e-14)
