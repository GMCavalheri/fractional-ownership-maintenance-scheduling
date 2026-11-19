"""A stochastic model of weekly flight hours for a fractional-ownership fleet.

Aircraft ``a`` flies ``u[a, t] = m[t] * D[t] * X[a, t]`` flight hours (FH) in week ``t``:

* ``m[t]`` is a deterministic seasonal multiplier with mean 1 over the year;
* ``D[t] = exp(Z[t] - s²/2)`` is a fleet-wide demand factor, a lognormal AR(1): ``Z[t] = φ Z[t-1]
  + σ ε[t]`` with stationary variance ``s² = σ²/(1 - φ²)``, so ``E[D] = 1``. It is shared by every
  aircraft and makes their hours correlated;
* ``X[a, t]`` is the aircraft's own demand: a Markov regime ``R[a, t]`` (idle, normal, spike) with
  transition matrix ``P`` and, given the regime, Gamma hours with mean ``μ_r`` and shape ``k_r``.
  The regimes of different aircraft are independent.

Everything is a labelled assumption (``data/utilization_parameters.csv``) except the mean annual
hours, which are calibrated to the 800 FH a year that fractional programmes sell per aircraft.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from importlib import resources

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]

REGIMES = ("idle", "normal", "spike")
WEEKS_PER_YEAR = 52


def load_parameters() -> dict[str, float]:
    """The parameter table, ``parameter -> value`` (the basis column is documentation)."""
    path = resources.files("fracsched") / "data" / "utilization_parameters.csv"
    with path.open() as f:
        return {row["parameter"]: float(row["value"]) for row in csv.DictReader(f)}


def stationary_distribution(P: FloatArray) -> FloatArray:
    """The left eigenvector of ``P`` for eigenvalue 1, normalised to sum to one."""
    n = P.shape[0]
    # Solve π (P - I) = 0 with Σ π = 1 as a least-squares system (exact for an ergodic chain).
    A = np.vstack([(P - np.eye(n)).T, np.ones(n)])
    b = np.zeros(n + 1)
    b[-1] = 1.0
    pi, *_ = np.linalg.lstsq(A, b, rcond=None)
    return np.asarray(pi, dtype=np.float64)


def seasonality(amplitude: float, peak_week: int, holiday_uplift: float) -> FloatArray:
    """Weekly multipliers ``m[0..51]`` with mean exactly 1.

    A cosine cycle peaking at 0-based week ``peak_week - 1``, times ``1 + holiday_uplift`` in the
    Thanksgiving week and the two year-end weeks (1-based weeks 47, 51, 52), then rescaled.
    """
    t = np.arange(WEEKS_PER_YEAR)
    m = 1.0 + amplitude * np.cos(2 * np.pi * (t - (peak_week - 1)) / WEEKS_PER_YEAR)
    m[[46, 50, 51]] *= 1.0 + holiday_uplift
    return np.asarray(m / m.mean(), dtype=np.float64)


@dataclass(frozen=True)
class UtilizationState:
    """What the operator knows at the end of a week: each aircraft's regime and the log demand."""

    regimes: IntArray  # (S, A)
    log_demand: FloatArray  # (S,), Z of the last simulated week


@dataclass(frozen=True)
class UtilizationModel:
    P: FloatArray  # (3, 3) regime transition matrix, rows sum to 1
    means: FloatArray  # (3,) mean weekly FH given the regime
    shapes: FloatArray  # (3,) Gamma shape given the regime
    demand_ar: float  # φ
    demand_sigma: float  # σ
    season: FloatArray  # (52,) multipliers, mean 1
    max_weekly_fh: float = float("inf")  # physical cap on one aircraft's week; inf = uncapped

    def __post_init__(self) -> None:
        if self.P.shape != (3, 3) or not np.allclose(self.P.sum(axis=1), 1.0):
            raise ValueError("P must be a 3 x 3 stochastic matrix")
        if np.any(self.P < 0) or np.any(self.means <= 0) or np.any(self.shapes <= 0):
            raise ValueError("probabilities must be >= 0, means and shapes > 0")
        if self.max_weekly_fh <= 0:
            raise ValueError("max_weekly_fh must be > 0")
        if not 0 <= self.demand_ar < 1 or self.demand_sigma < 0:
            raise ValueError("need 0 <= demand_ar < 1 and demand_sigma >= 0")
        if self.season.shape != (WEEKS_PER_YEAR,) or not np.isclose(self.season.mean(), 1.0):
            raise ValueError("season must hold 52 multipliers with mean 1")

    @property
    def pi(self) -> FloatArray:
        return stationary_distribution(self.P)

    @property
    def mean_weekly_fh(self) -> float:
        """Stationary mean of ``X``, which is also the mean of ``u`` over a year."""
        return float(self.pi @ self.means)

    @property
    def demand_log_var(self) -> float:
        """``s² = σ²/(1 - φ²)``, the stationary variance of ``Z``."""
        return self.demand_sigma**2 / (1 - self.demand_ar**2)

    def season_at(self, start_week: int, horizon: int) -> FloatArray:
        weeks = (start_week + np.arange(horizon)) % WEEKS_PER_YEAR
        return np.asarray(self.season[weeks], dtype=np.float64)

    def stationary_state(
        self, rng: np.random.Generator, n_scenarios: int, n_aircraft: int
    ) -> UtilizationState:
        """A state drawn from the stationary distribution (the default start)."""
        regimes = rng.choice(3, size=(n_scenarios, n_aircraft), p=self.pi).astype(np.int64)
        z = rng.normal(0.0, np.sqrt(self.demand_log_var), size=n_scenarios)
        return UtilizationState(regimes, z)

    def sample(
        self,
        rng: np.random.Generator,
        n_scenarios: int,
        n_aircraft: int,
        horizon: int,
        *,
        start_week: int = 0,
        state: UtilizationState | None = None,
    ) -> tuple[FloatArray, UtilizationState]:
        """Weekly hours ``u`` of shape ``(S, A, horizon)`` and the state after the last week.

        Without ``state`` the chain starts from a stationary draw for the week before
        ``start_week``. With ``state`` (shapes ``(S, A)`` and ``(S,)``, or ``(1, A)`` and ``(1,)``
        broadcast to every scenario) the sample is conditional on it: this is how the rolling
        horizon draws futures given what has been observed. Hours are capped at
        ``max_weekly_fh``; the closed forms in ``moments`` describe the uncapped model.
        """
        if state is None:
            state = self.stationary_state(rng, n_scenarios, n_aircraft)
        regimes = np.broadcast_to(state.regimes, (n_scenarios, n_aircraft)).copy()
        z = np.broadcast_to(state.log_demand, (n_scenarios,)).copy()
        cum = np.cumsum(self.P, axis=1)
        cum[:, -1] = 1.0  # guard against a row sum of 1 - 1e-16 sending a draw to state 3
        season = self.season_at(start_week, horizon)
        half_var = self.demand_log_var / 2
        u = np.empty((n_scenarios, n_aircraft, horizon))
        for t in range(horizon):
            draw = rng.random((n_scenarios, n_aircraft))
            regimes = (draw[..., None] > cum[regimes]).sum(axis=-1).astype(np.int64)
            z = self.demand_ar * z + self.demand_sigma * rng.standard_normal(n_scenarios)
            k = self.shapes[regimes]
            x = rng.gamma(k, self.means[regimes] / k)
            u[:, :, t] = season[t] * np.exp(z - half_var)[:, None] * x
        np.minimum(u, self.max_weekly_fh, out=u)
        return u, UtilizationState(regimes, z)


def default_model(annual_mean_fh: float | None = None, *, capped: bool = True) -> UtilizationModel:
    """The model of ``data/utilization_parameters.csv``, scaled to the annual mean hours.

    ``capped=False`` drops the weekly cap, giving the model the closed forms describe exactly.
    """
    p = load_parameters()
    P = np.array(
        [
            [p["p_idle_idle"], p["p_idle_normal"], 0.0],
            [p["p_normal_idle"], p["p_normal_normal"], p["p_normal_spike"]],
            [0.0, p["p_spike_normal"], p["p_spike_spike"]],
        ]
    )
    relative = np.array(
        [p["idle_relative_mean"], p["normal_relative_mean"], p["spike_relative_mean"]]
    )
    target = (annual_mean_fh if annual_mean_fh is not None else p["annual_mean_fh"]) / p[
        "weeks_per_year"
    ]
    means = relative * target / float(stationary_distribution(P) @ relative)
    return UtilizationModel(
        P=P,
        means=means,
        shapes=np.array([p["idle_shape"], p["normal_shape"], p["spike_shape"]]),
        demand_ar=p["demand_ar"],
        demand_sigma=p["demand_sigma"],
        season=seasonality(p["season_amplitude"], int(p["season_peak_week"]), p["holiday_uplift"]),
        max_weekly_fh=p["max_weekly_fh"] if capped else float("inf"),
    )
