"""Uncertain wear: a Bayesian failure-rate input from EJD-01's conjugate model.

Every lesson so far took each component's Weibull scale ``η`` as known. A small business-jet
fleet does not know it: it has a few failures in a few years. EJD-01 (``smallfleet``) answers
that with a Gamma-Poisson model. It applies here exactly, because for a *known* shape ``β``
the minimal-repair failure process is a Poisson process with a Gamma-conjugate rate:

* write ``η = η_ref λ^(-1/β)``, where ``η_ref`` is a reference scale (AVR-04's) and ``λ > 0`` a
  dimensionless *wear multiplier* (``λ = 1``: the reference; ``λ = 2``: twice the failures);
* expected failures while ageing from ``a`` to ``b`` FH are ``λ [H_ref(b) - H_ref(a)]``, so a
  history with ``n`` failures over a reference exposure ``E = Σ [H_ref(b) - H_ref(a)]`` has
  likelihood ``Poisson(n; λ E)``;
* a Gamma(α, β) prior on ``λ`` gives the posterior Gamma(α + n, β + E): EJD-01's update.

``smallfleet`` counts exposure in thousands of FH, so the reference exposure is passed as
``1000 E``. Because failures are linear in ``λ``, a scenario with multiplier ``λ_k`` for type
``k`` simply scales the failure tables of type-``k`` components; forced tasks do not change.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from importlib import resources

import numpy as np
from scipy import special
from smallfleet.bayesian_point_estimation import GammaRate, gamma_from_mean_cv

from fracsched.problem import FleetProblem
from fracsched.scenarios import SegmentTables
from fracsched.utilization_model.model import FloatArray

PER = 1000.0  # smallfleet's exposure unit


@dataclass(frozen=True)
class WearPrior:
    component: str
    prior: GammaRate
    history_years: float
    basis: str


def load_wear_priors() -> list[WearPrior]:
    path = resources.files("fracsched") / "data" / "wear_parameters.csv"
    with path.open() as f:
        return [
            WearPrior(
                row["component"],
                gamma_from_mean_cv(float(row["prior_mean"]), float(row["prior_cv"])),
                float(row["history_years"]),
                row["basis"],
            )
            for row in csv.DictReader(f)
        ]


def posterior(prior: GammaRate, failures: int, reference_exposure: float) -> GammaRate:
    """EJD-01's conjugate update of the wear multiplier (exposure in reference failures)."""
    return prior.update(failures, PER * reference_exposure)


def mean_eta_factor(dist: GammaRate, beta: float) -> float:
    """``E[λ^(-1/β)]`` under ``λ ~ Gamma(α, rate)``: the posterior mean of ``η / η_ref``.

    ``E[λ^p] = Γ(α + p) / (Γ(α) rate^p)`` for ``α + p > 0``.
    """
    p = -1.0 / beta
    if dist.alpha + p <= 0:
        raise ValueError("the posterior mean of eta is infinite for alpha <= 1/beta")
    log_ratio = float(special.gammaln(dist.alpha + p) - special.gammaln(dist.alpha))
    return float(np.exp(log_ratio) / float(dist.beta) ** p)


def plug_in_multiplier(dist: GammaRate, beta: float) -> float:
    """The multiplier implied by plugging in the posterior mean of ``η``: ``E[λ^(-1/β)]^(-β)``.

    By Jensen's inequality (``x^(-1/β)`` is convex) this is at most ``E[λ]``: plugging in the
    mean scale under-states the expected failures.
    """
    return float(mean_eta_factor(dist, beta) ** (-beta))


def sample_multipliers(dists: Sequence[GammaRate], n: int, rng: np.random.Generator) -> FloatArray:
    """``(K, n)`` independent draws of each type's wear multiplier."""
    return np.stack([rng.gamma(d.alpha, 1.0 / d.beta, size=n) for d in dists])


def scale_failures(
    problem: FleetProblem, tables: SegmentTables, multipliers: FloatArray
) -> SegmentTables:
    """Tables with each type-``k`` component's failures times ``multipliers[k, s]``."""
    types = np.array([c.type for c in problem.base.components])
    factor = multipliers[types]  # (C, S)
    return SegmentTables(tables.failures * factor[:, None, None, :], tables.forced)


def reference_failures_per_year(problem: FleetProblem, failures: FloatArray) -> FloatArray:
    """Sum per component type of a ``(C,)`` vector of expected failures."""
    out = np.zeros(len(problem.base.types))
    for c, comp in enumerate(problem.base.components):
        out[comp.type] += failures[c]
    return out
