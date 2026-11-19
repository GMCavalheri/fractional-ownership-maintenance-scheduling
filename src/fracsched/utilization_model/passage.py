"""How many calendar weeks a flight-hour interval lasts: a first-passage time.

A task due every ``L`` FH falls due in the first week ``t`` at whose end the cumulative hours
reach ``L``. At mean utilization this is ``L / ū`` weeks. Under uncertain utilization it is a
random variable, and its spread is what makes FH-based maintenance hard to plan in weeks.
"""

from __future__ import annotations

import numpy as np

from fracsched.utilization_model.model import FloatArray, IntArray


def weeks_to_reach(u: FloatArray, limit: float, initial: float = 0.0) -> IntArray:
    """For each path in ``u`` (``(..., T)``), the 0-based week in which hours reach ``limit``.

    The task is due in week ``t`` when ``initial + u[0] + … + u[t] >= limit``. Paths that never
    reach it within ``T`` weeks return ``T`` (censored).
    """
    cum = initial + np.cumsum(u, axis=-1)
    reached = cum >= limit
    first = np.argmax(reached, axis=-1)
    return np.where(reached.any(axis=-1), first, u.shape[-1]).astype(np.int64)


def hours_to_weeks_quantiles(
    u: FloatArray, limit: float, quantiles: tuple[float, ...] = (0.1, 0.5, 0.9)
) -> tuple[float, ...]:
    """Quantiles of the number of weeks a ``limit``-FH interval lasts (``weeks_to_reach + 1``)."""
    weeks = weeks_to_reach(u, limit).ravel() + 1
    return tuple(float(q) for q in np.quantile(weeks, quantiles, method="inverted_cdf"))
