"""Planning for the average: AVR-04's methods, unchanged, on the mean-utilization instance.

``FleetProblem.at_mean()`` is AVR-04's week-clock instance at the design utilization. On it,
AVR-04's genetic algorithm and fixed-interval rules produce plans exactly as AVR-04 does.
Those plans are then scored on the FH clock across utilization scenarios
(``fracsched.scenarios``). That is the deterministic baseline of the PLAN: optimise for one
assumed profile, live with all the others.
"""

from __future__ import annotations

import numpy as np
from pmo.baseline import BASELINES, fixed_interval_schedule
from pmo.ga import GAConfig, GAResult, run_ga
from pmo.instance import Schedule

from fracsched.problem import FleetProblem
from fracsched.utilization_model.model import FloatArray


def average_plan(problem: FleetProblem, config: GAConfig | None = None) -> GAResult:
    """AVR-04's GA (``pmo.ga.run_ga``) on the mean-utilization instance."""
    return run_ga(problem.at_mean(), config or GAConfig())


def fixed_interval_plans(problem: FleetProblem) -> dict[str, Schedule]:
    """AVR-04's two fixed-interval baselines on the mean-utilization instance."""
    inst = problem.at_mean()
    return {name: fixed_interval_schedule(inst, **kw) for name, kw in BASELINES.items()}


def constant_scenario(problem: FleetProblem, n_scenarios: int = 1) -> FloatArray:
    """Every aircraft flies exactly ``ū`` FH every week: the world the average plan assumes."""
    shape = (n_scenarios, problem.base.n_aircraft, problem.horizon)
    return np.full(shape, problem.mean_fh)
