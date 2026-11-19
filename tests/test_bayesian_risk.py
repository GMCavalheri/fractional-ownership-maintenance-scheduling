"""Extra: the Bayesian wear multiplier, against numerical integration and the evaluator."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from scipy import integrate, stats
from smallfleet.bayesian_point_estimation import GammaRate

from fracsched.bayesian_risk import (
    load_wear_priors,
    mean_eta_factor,
    plug_in_multiplier,
    posterior,
    reference_failures_per_year,
    sample_multipliers,
    scale_failures,
)
from fracsched.deterministic_baseline import fixed_interval_plans
from fracsched.problem import main_problem
from fracsched.scenarios import evaluate, segment_tables
from fracsched.utilization_model import default_model

MAIN = main_problem()


def test_priors_cover_the_four_component_types() -> None:
    priors = load_wear_priors()
    assert [p.component for p in priors] == [t.name for t in MAIN.base.types]
    assert priors[2].prior.mean() == pytest.approx(1.3)
    assert priors[2].prior.sd() / priors[2].prior.mean() == pytest.approx(0.5)


@pytest.mark.parametrize(("n", "exposure"), [(0, 0.7), (3, 2.5), (12, 9.0)])
def test_posterior_is_likelihood_times_prior(n: int, exposure: float) -> None:
    # Oracle: numerical integration of Poisson(n; λE) x Gamma prior, normalised.
    prior = GammaRate(4.0, 4.0)
    post = posterior(prior, n, exposure)
    assert (post.alpha, post.beta) == pytest.approx((4.0 + n, 4.0 + exposure))

    def unnorm(lam: float) -> float:
        return stats.poisson.pmf(n, lam * exposure) * stats.gamma.pdf(lam, 4.0, scale=0.25)

    z = integrate.quad(unnorm, 0, np.inf)[0]
    mean = integrate.quad(lambda x: x * unnorm(x), 0, np.inf)[0] / z
    second = integrate.quad(lambda x: x * x * unnorm(x), 0, np.inf)[0] / z
    assert post.mean() == pytest.approx(mean, rel=1e-8)
    assert post.var() == pytest.approx(second - mean**2, rel=1e-6)


def test_posterior_mean_of_eta_by_quadrature() -> None:
    # Oracle: E[λ^(-1/β)] by numerical integration of the Gamma density.
    dist, beta = GammaRate(6.0, 5.0), 2.5
    value = integrate.quad(
        lambda x: x ** (-1 / beta) * stats.gamma.pdf(x, 6.0, scale=0.2), 0, np.inf
    )[0]
    assert mean_eta_factor(dist, beta) == pytest.approx(value, rel=1e-9)
    with pytest.raises(ValueError):
        mean_eta_factor(GammaRate(0.2, 1.0), 2.5)


@settings(max_examples=100, deadline=None)
@given(alpha=st.floats(1.0, 50.0), rate=st.floats(0.1, 50.0), beta=st.floats(1.2, 4.0))
def test_plugging_in_the_mean_scale_understates_wear(
    alpha: float, rate: float, beta: float
) -> None:
    # Jensen: x^(-1/β) is convex, so E[λ^(-1/β)]^(-β) <= E[λ].
    dist = GammaRate(alpha, rate)
    assert plug_in_multiplier(dist, beta) <= dist.mean() * (1 + 1e-12)


def test_multipliers_scale_failures_and_leave_forced_tasks() -> None:
    u, _ = default_model().sample(np.random.default_rng(2), 6, 10, 52)
    tables = segment_tables(MAIN, u)
    lam = np.array([[1.0] * 6, [2.0] * 6, [0.5] * 6, [3.0] * 6])
    scaled = scale_failures(MAIN, tables, lam)
    plan = fixed_interval_plans(MAIN)["Fixed interval (cost-optimal)"]
    base = evaluate(MAIN, tables, plan)
    ev = evaluate(MAIN, scaled, plan)
    np.testing.assert_array_equal(ev.forced_tasks, base.forced_tasks)
    # Failures per type, from the per-component tables, scale by that type's multiplier.
    per_c = tables.failures[:, 0, 52, 0]  # no-task segments of scenario 0
    by_type = reference_failures_per_year(MAIN, per_c)
    by_type_scaled = reference_failures_per_year(MAIN, scaled.failures[:, 0, 52, 0])
    np.testing.assert_allclose(by_type_scaled, by_type * lam[:, 0], rtol=1e-12)
    assert ev.failure_cost.sum() > base.failure_cost.sum()


def test_sampled_multipliers_follow_the_posterior() -> None:
    dists = [GammaRate(9.0, 9.0), GammaRate(25.0, 20.0)]
    lam = sample_multipliers(dists, 40_000, np.random.default_rng(0))
    for d, row in zip(dists, lam, strict=True):
        assert abs(row.mean() - d.mean()) < 4 * d.sd() / np.sqrt(row.size)
