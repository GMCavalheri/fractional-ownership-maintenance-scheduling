"""The stochastic-programming measures of what uncertainty costs and what a model recovers.

For a minimisation with plan ``x`` and random future ``ω`` (Birge & Louveaux, ch. 4):

* **EV**  = ``min_x c(x, E[ω])``: the value the deterministic planner *promises*;
* **EEV** = ``E[c(x_EV, ω)]``: what the plan for the average *actually* costs;
* **RP**  = ``min_x E[c(x, ω)]``: the recourse problem, the best a single plan can do;
* **WS**  = ``E[min_x c(x, ω)]``: wait-and-see, the cost with perfect foresight of each future.

Always ``WS ≤ RP ≤ EEV``. Their differences are the **expected value of perfect information**,
``EVPI = RP - WS``, and the **value of the stochastic solution**, ``VSS = EEV - RP``. On a common
sample of scenarios these inequalities hold exactly; the tests check them.

``mmw_gap`` is Mak, Morton & Wood's (1999) statistical bound on a candidate plan's optimality
gap: the mean of ``M`` independent SAA optimal values is a biased-low estimate of RP, the
candidate's held-out mean an unbiased estimate of its true cost, and their difference, with a
one-sided confidence term, bounds the candidate's gap.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import stats

from fracsched.utilization_model.model import FloatArray


@dataclass(frozen=True)
class Ladder:
    ev: float
    eev: float
    rp: float
    ws: float

    @property
    def vss(self) -> float:
        return self.eev - self.rp

    @property
    def evpi(self) -> float:
        return self.rp - self.ws

    @property
    def overrun(self) -> float:
        """What the deterministic plan costs beyond its promise: ``EEV - EV``."""
        return self.eev - self.ev


def ladder_on_sample(costs: FloatArray, ev_plan: int, ev_value: float) -> Ladder:
    """The measures on one sample, from a matrix of plan costs.

    ``costs[p, s]`` is the cost of candidate plan ``p`` in scenario ``s``, where the candidates
    include the EV plan (row ``ev_plan``), and for every scenario the plan optimal in it (so the
    row-wise minimum per scenario is the wait-and-see value). RP is the best row's mean.
    """
    return Ladder(
        ev=ev_value,
        eev=float(costs[ev_plan].mean()),
        rp=float(np.min(costs.mean(axis=1))),
        ws=float(np.min(costs, axis=0).mean()),
    )


@dataclass(frozen=True)
class GapBound:
    lower: float  # mean of the M SAA optimal values (estimates RP from below)
    lower_se: float
    upper: float  # candidate's mean on held-out scenarios
    upper_se: float
    gap: float  # upper - lower
    bound: float  # one-sided (1 - alpha) upper confidence bound on the gap

    @property
    def relative_bound(self) -> float:
        return self.bound / self.upper


def mmw_gap(saa_values: FloatArray, held_out_costs: FloatArray, alpha: float = 0.05) -> GapBound:
    """Mak-Morton-Wood optimality-gap bound for a candidate plan.

    ``saa_values`` are the optimal values of ``M`` independent SAA problems (t-interval);
    ``held_out_costs`` are the candidate's costs on independent held-out scenarios (normal).
    """
    M = saa_values.size
    lower = float(saa_values.mean())
    lower_se = float(saa_values.std(ddof=1)) / math.sqrt(M)
    upper = float(held_out_costs.mean())
    upper_se = float(held_out_costs.std(ddof=1)) / math.sqrt(held_out_costs.size)
    t = float(stats.t.ppf(1 - alpha, M - 1))
    z = float(stats.norm.ppf(1 - alpha))
    bound = upper - lower + z * upper_se + t * lower_se
    return GapBound(lower, lower_se, upper, upper_se, upper - lower, bound)


def paired_difference(a: FloatArray, b: FloatArray) -> tuple[float, float]:
    """Mean and standard error of ``a - b`` on common scenarios."""
    d = np.asarray(a) - np.asarray(b)
    return float(d.mean()), float(d.std(ddof=1)) / math.sqrt(d.size)
