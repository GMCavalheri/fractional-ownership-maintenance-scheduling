"""The scheduling problem on a flight-hour clock, built on AVR-04's instance.

AVR-04 (``pmo``) schedules preventive tasks in weeks for a fleet whose flying is known, so a
component's age is counted in weeks. Here age is counted in flight hours (FH), and the hours
are uncertain. A :class:`FleetProblem` holds:

* ``base``: a ``pmo.Instance`` on the calendar. It carries the fleet, the capacities (hangar
  bays, labour, spare parts), the costs and the *calendar* interval limits. pmo's decoder and
  its constraint check run on it unchanged.
* the FH side: per component type a Weibull scale ``eta_fh`` and an FH limit; per component
  the FH flown since its last task.

``at_mean()`` maps the problem back to a pmo instance at the design utilization ``ū``:
``eta_weeks = eta_fh / ū`` and ``max_interval = min(calendar limit, ⌊FH limit / ū⌋)``. When
the parameters come from AVR-04 (``from_pmo``) that instance *is* AVR-04's.
"""

from __future__ import annotations

import csv
import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from importlib import resources

import numpy as np
from pmo.instance import ComponentType, Instance, default_instance, small_instance

from fracsched.utilization_model.model import FloatArray, load_parameters


def load_scheduling_parameters() -> dict[str, float]:
    path = resources.files("fracsched") / "data" / "scheduling_parameters.csv"
    with path.open() as f:
        return {row["parameter"]: float(row["value"]) for row in csv.DictReader(f)}


def design_fh_per_week() -> float:
    """``ū``: the design utilization, 800 FH a year over 52 weeks."""
    p = load_parameters()
    return p["annual_mean_fh"] / p["weeks_per_year"]


@dataclass(frozen=True, eq=False)
class FleetProblem:
    base: Instance  # calendar instance: capacities, costs, calendar max intervals
    mean_fh: float  # ū, FH per aircraft-week the FH parameters were converted at
    beta: tuple[float, ...]  # Weibull shape per type
    eta_fh: tuple[float, ...]  # Weibull scale per type, FH
    fh_limit: tuple[float, ...]  # FH limit per type
    initial_fh: tuple[float, ...]  # FH since the last task, per component, at week 0
    unscheduled_visit_cost: float  # $ per forced (out-of-plan) task, on top of the task cost
    limit_tolerance: float = 1e-9

    def __post_init__(self) -> None:
        K, C = len(self.base.types), self.base.n_components
        if not len(self.beta) == len(self.eta_fh) == len(self.fh_limit) == K:
            raise ValueError("beta, eta_fh and fh_limit need one value per component type")
        if len(self.initial_fh) != C:
            raise ValueError("initial_fh needs one value per component")
        if self.mean_fh <= 0 or self.unscheduled_visit_cost < 0:
            raise ValueError("mean_fh must be > 0 and unscheduled_visit_cost >= 0")
        for c, h in zip(self.base.components, self.initial_fh, strict=True):
            if not 0 <= h <= self.fh_limit[c.type]:
                raise ValueError("a component starts beyond its FH limit")

    @property
    def horizon(self) -> int:
        return int(self.base.horizon)

    @property
    def n_components(self) -> int:
        return int(self.base.n_components)

    def failure_cost(self, k: int) -> float:
        """Cost of one failure of type ``k``: repair plus aircraft downtime (AVR-04's)."""
        return float(self.base.failure_cost(k))

    def forced_task_cost(self, k: int) -> float:
        return float(self.base.types[k].cost_pm) + self.unscheduled_visit_cost

    def cumulative_hazard(self, k: int, fh: FloatArray) -> FloatArray:
        """Expected failures (minimal repair) while a type-``k`` component ages to ``fh`` FH."""
        return np.asarray((fh / self.eta_fh[k]) ** self.beta[k], dtype=np.float64)

    def at_mean(self) -> Instance:
        """The deterministic equivalent: AVR-04's week-clock instance at utilization ``ū``."""
        types = []
        for k, ct in enumerate(self.base.types):
            weeks = math.floor(self.fh_limit[k] / self.mean_fh * (1 + self.limit_tolerance))
            types.append(
                replace(
                    ct,
                    eta=self.eta_fh[k] / self.mean_fh,
                    max_interval=min(ct.max_interval, weeks),
                )
            )
        # The week-clock planner sees each component's FH age as ``h / ū`` weeks.
        components = tuple(
            replace(
                comp,
                initial_age=min(
                    round(self.initial_fh[c] / self.mean_fh), types[comp.type].max_interval
                ),
            )
            for c, comp in enumerate(self.base.components)
        )
        return replace(
            self.base,
            name=f"{self.base.name}-at-mean",
            types=tuple(types),
            components=components,
        )

    def subproblem(
        self,
        start: int,
        weeks_since_task: Sequence[int],
        fh_since_task: Sequence[float],
        parts_used: Sequence[int],
    ) -> FleetProblem:
        """The problem that remains at the start of week ``start``.

        Its week 0 is week ``start`` here. Each component starts from its observed state:
        ``weeks_since_task`` (calendar age) and ``fh_since_task``. Capacities are the remaining
        weeks'; spare parts on hand are the initial stock plus deliveries before ``start`` minus
        ``parts_used`` (per type) by tasks already done.
        """
        inst = self.base
        if not 0 < start < inst.horizon:
            raise ValueError("start must be inside the horizon")
        components = tuple(
            replace(comp, initial_age=int(w))
            for comp, w in zip(inst.components, weeks_since_task, strict=True)
        )
        stock = inst.initial_stock + inst.deliveries[:, :start].sum(axis=1) - np.asarray(parts_used)
        base = replace(
            inst,
            name=f"{inst.name}-from{start}",
            horizon=inst.horizon - start,
            components=components,
            bays=inst.bays[start:].copy(),
            labor=inst.labor[start:].copy(),
            initial_stock=np.maximum(stock, 0).astype(inst.initial_stock.dtype),
            deliveries=inst.deliveries[:, start:].copy(),
        )
        return replace(self, base=base, initial_fh=tuple(float(h) for h in fh_since_task))


def from_pmo(
    inst: Instance,
    mean_fh: float | None = None,
    calendar_limit_factor: float | None = None,
    unscheduled_visit_cost: float | None = None,
) -> FleetProblem:
    """Lift an AVR-04 instance onto the FH clock.

    Scales and maximum intervals in weeks become FH at ``ū``; initial ages likewise. The
    calendar limit is ``calendar_limit_factor`` times the old maximum interval, so at mean use
    the FH limit binds first and ``at_mean()`` gives back ``inst``.
    """
    p = load_scheduling_parameters()
    u = design_fh_per_week() if mean_fh is None else mean_fh
    factor = p["calendar_limit_factor"] if calendar_limit_factor is None else calendar_limit_factor
    cost = p["unscheduled_visit_cost"] if unscheduled_visit_cost is None else unscheduled_visit_cost
    if factor < 1:
        raise ValueError("the calendar limit must not be shorter than the FH limit at mean use")
    types: list[ComponentType] = [
        replace(ct, max_interval=math.ceil(factor * ct.max_interval)) for ct in inst.types
    ]
    base = replace(inst, types=tuple(types))
    return FleetProblem(
        base=base,
        mean_fh=u,
        beta=tuple(float(ct.beta) for ct in inst.types),
        eta_fh=tuple(float(ct.eta) * u for ct in inst.types),
        fh_limit=tuple(float(ct.max_interval) * u for ct in inst.types),
        initial_fh=tuple(float(c.initial_age) * u for c in inst.components),
        unscheduled_visit_cost=cost,
        limit_tolerance=p["limit_tolerance"],
    )


def main_problem(seed: int = 0) -> FleetProblem:
    """AVR-04's main case study (10 aircraft x 4 types x 52 weeks) on the FH clock."""
    return from_pmo(default_instance(seed))


def small_problem(seed: int = 0) -> FleetProblem:
    """AVR-04's small instance (3 aircraft x 3 types x 26 weeks), small enough for CP-SAT."""
    return from_pmo(small_instance(seed))
