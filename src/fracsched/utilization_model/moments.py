"""Closed-form moments of the utilization model, the oracle for its tests and its lesson.

``X`` (an aircraft's own demand) and ``D`` (the fleet factor) are independent, ``E[D] = 1`` and
``E[D_t D_{t+h}] = exp(s² φ^h)`` for a stationary lognormal AR(1). For the Markov-modulated Gamma
``X`` in its stationary regime distribution ``π``:

```
E[X]             = Σ_r π_r μ_r
E[X²]            = Σ_r π_r μ_r² (1 + 1/k_r)
E[X_t X_{t+h}]   = Σ_{r,r'} π_r (P^h)_{r r'} μ_r μ_{r'}            (h ≥ 1)
```

Weekly hours are ``u_t = m_t D_t X_t``, so every second moment of ``u`` (one aircraft across
weeks, two aircraft in one week, sums over a year) is a product of these.
"""

from __future__ import annotations

import numpy as np

from fracsched.utilization_model.model import FloatArray, UtilizationModel


def x_second_moment(model: UtilizationModel, lag: int) -> float:
    """``E[X_t X_{t+lag}]`` for one aircraft in the stationary regime distribution."""
    pi, mu = model.pi, model.means
    if lag == 0:
        return float(pi @ (mu**2 * (1 + 1 / model.shapes)))
    Ph = np.linalg.matrix_power(model.P, lag)
    return float((pi * mu) @ Ph @ mu)


def d_second_moment(model: UtilizationModel, lag: int) -> float:
    """``E[D_t D_{t+lag}] = exp(s² φ^lag)``."""
    return float(np.exp(model.demand_log_var * model.demand_ar ** abs(lag)))


def weekly_mean(model: UtilizationModel, start_week: int = 0, horizon: int = 52) -> FloatArray:
    """``E[u_t] = m_t E[X]`` for each week."""
    return model.season_at(start_week, horizon) * model.mean_weekly_fh


def weekly_covariance(
    model: UtilizationModel, start_week: int = 0, horizon: int = 52
) -> FloatArray:
    """``Cov(u_t, u_{t'})`` for one aircraft, a ``(horizon, horizon)`` matrix."""
    m = model.season_at(start_week, horizon)
    mx = model.mean_weekly_fh
    lags = np.abs(np.subtract.outer(np.arange(horizon), np.arange(horizon)))
    exx = np.array([x_second_moment(model, h) for h in range(horizon)])
    edd = np.array([d_second_moment(model, h) for h in range(horizon)])
    return np.asarray(np.outer(m, m) * (edd[lags] * exx[lags] - mx**2), dtype=np.float64)


def cross_aircraft_covariance(
    model: UtilizationModel, start_week: int = 0, horizon: int = 52
) -> FloatArray:
    """``Cov(u_{a,t}, u_{b,t'})`` for two different aircraft: only ``D`` is shared."""
    m = model.season_at(start_week, horizon)
    mx = model.mean_weekly_fh
    lags = np.abs(np.subtract.outer(np.arange(horizon), np.arange(horizon)))
    edd = np.array([d_second_moment(model, h) for h in range(horizon)])
    return np.asarray(np.outer(m, m) * mx**2 * (edd[lags] - 1), dtype=np.float64)


def weekly_sd(model: UtilizationModel, start_week: int = 0, horizon: int = 52) -> FloatArray:
    return np.sqrt(np.diag(weekly_covariance(model, start_week, horizon)))


def autocorrelation(model: UtilizationModel, lag: int) -> float:
    """Correlation of ``D_t X_t`` with ``D_{t+lag} X_{t+lag}`` (the season factor removed)."""
    mx = model.mean_weekly_fh
    var = d_second_moment(model, 0) * x_second_moment(model, 0) - mx**2
    cov = d_second_moment(model, lag) * x_second_moment(model, lag) - mx**2
    return cov / var


def cross_correlation(model: UtilizationModel) -> float:
    """Correlation of two aircraft's de-seasonalised hours in the same week."""
    mx = model.mean_weekly_fh
    var = d_second_moment(model, 0) * x_second_moment(model, 0) - mx**2
    return mx**2 * (d_second_moment(model, 0) - 1) / var


def annual_mean(model: UtilizationModel, start_week: int = 0, horizon: int = 52) -> float:
    return float(weekly_mean(model, start_week, horizon).sum())


def annual_sd(model: UtilizationModel, start_week: int = 0, horizon: int = 52) -> float:
    """Standard deviation of one aircraft's hours over ``horizon`` weeks."""
    return float(np.sqrt(weekly_covariance(model, start_week, horizon).sum()))


def fleet_annual_sd(
    model: UtilizationModel, n_aircraft: int, start_week: int = 0, horizon: int = 52
) -> float:
    """Standard deviation of the fleet's total hours: own variance plus shared covariance."""
    own = weekly_covariance(model, start_week, horizon).sum()
    shared = cross_aircraft_covariance(model, start_week, horizon).sum()
    return float(np.sqrt(n_aircraft * own + n_aircraft * (n_aircraft - 1) * shared))
