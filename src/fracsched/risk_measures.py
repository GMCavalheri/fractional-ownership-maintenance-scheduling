"""Risk measures of a cost distribution over equally likely scenarios.

``CVaR_α`` (conditional value at risk) is the mean of the worst ``1 - α`` share of outcomes. For
``S`` equally likely scenarios it is the Rockafellar-Uryasev minimum

```
CVaR_α(x) = min_η  η + Σ_s max(x_s - η, 0) / ((1 - α) S),
```

which, with the costs sorted in decreasing order, averages the top ``(1 - α) S`` of them, the
boundary scenario counted fractionally. ``α = 0`` is the mean; ``α → 1`` is the maximum.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from fracsched.utilization_model.model import FloatArray


def cvar(x: FloatArray, alpha: float) -> float:
    """``CVaR_α`` of equally likely outcomes ``x`` (higher is worse)."""
    if not 0 <= alpha < 1:
        raise ValueError("alpha must be in [0, 1)")
    v = np.sort(np.asarray(x, dtype=np.float64))[::-1]
    tail = (1 - alpha) * v.size
    whole = min(math.floor(tail + 1e-12), v.size)
    total = float(v[:whole].sum())
    if whole < v.size:
        total += (tail - whole) * float(v[whole])
    return total / tail


def quantile(x: FloatArray, q: float) -> float:
    """The ``q`` quantile as an observed value (inverted CDF), stable across platforms."""
    return float(np.quantile(np.asarray(x), q, method="inverted_cdf"))


@dataclass(frozen=True)
class Summary:
    """A cost distribution in the numbers a planner asks for."""

    mean: float
    se: float  # Monte Carlo standard error of the mean
    sd: float
    p10: float
    p50: float
    p90: float
    p99: float
    cvar90: float
    max: float


def summarize(x: FloatArray) -> Summary:
    a = np.asarray(x, dtype=np.float64)
    sd = float(a.std(ddof=1)) if a.size > 1 else 0.0
    return Summary(
        mean=float(a.mean()),
        se=sd / math.sqrt(a.size),
        sd=sd,
        p10=quantile(a, 0.1),
        p50=quantile(a, 0.5),
        p90=quantile(a, 0.9),
        p99=quantile(a, 0.99),
        cvar90=cvar(a, 0.9),
        max=float(np.max(a)),
    )
