"""The sample-average problem solved exactly with CP-SAT.

AVR-04's exact model (``pmo.exact``) writes each component's plan as a path through a
time-indexed DAG whose arcs are consecutive renewals, and couples the paths through hangar
visits, bays, labour and spare parts. Its arc costs come from a hazard that depends only on
the gap. Here the arc costs come from the scenario segment tables (``fracsched.scenarios``),
which also depend only on the arc's two end points, so the model stays exactly linear:

* **expected cost**: each arc costs its task plus the scenario-averaged segment cost;
* **CVaR_α** (Rockafellar-Uryasev): one cost expression ``z_s`` per scenario, a free variable
  ``η`` and one ``t_s ≥ z_s - η, t_s ≥ 0`` per scenario; minimise ``K η + Σ t_s`` with
  ``K = (1 - α) S`` (an integer, so the objective stays integral).

The structure mirrors ``pmo.exact.solve_exact`` constraint by constraint; the windows are the
problem's calendar windows. CP-SAT runs single-threaded with a fixed seed, so a run that
proves optimality returns the same plan on any machine. Costs are scaled to integers and the
returned plan is re-scored exactly.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from ortools.sat.python import cp_model
from pmo.instance import Schedule

from fracsched.problem import FleetProblem
from fracsched.risk_measures import cvar
from fracsched.scenarios import planned_part, scenario_costs
from fracsched.utilization_model.model import FloatArray


@dataclass(frozen=True)
class ExactResult:
    schedule: Schedule | None
    objective: float  # the returned plan's objective, re-scored exactly
    bound: float  # proven lower bound on the optimal objective
    optimal: bool
    status: str
    runtime: float
    n_arcs: int

    @property
    def gap(self) -> float:
        """Relative gap between the returned plan and the bound."""
        return (self.objective - self.bound) / max(abs(self.objective), 1e-9)


def solve_saa(
    problem: FleetProblem,
    cost_table: FloatArray,
    *,
    objective: Literal["mean", "cvar"] = "mean",
    alpha: float = 0.9,
    time_limit: float = 60.0,
    workers: int = 1,
    seed: int = 0,
    scale: float = 10.0,
    hint: Schedule | None = None,
) -> ExactResult:
    """Minimise the sample-average objective over the scenarios of ``cost_table``.

    ``cost_table`` is ``scenarios.cost_table(problem, u)``, shape ``(C, T + 1, T + 1, S)``.
    """
    start_time = time.perf_counter()
    inst = problem.base
    T = inst.horizon
    S = cost_table.shape[-1]
    K = round((1 - alpha) * S)
    if objective == "cvar" and (K < 1 or abs(K - (1 - alpha) * S) > 1e-9):
        raise ValueError("CVaR needs (1 - alpha) * S to be a positive integer")
    mean_table = cost_table.mean(axis=-1)
    model = cp_model.CpModel()
    linear: list[tuple[int, Any]] = []  # mean objective terms
    per_scenario: list[tuple[np.ndarray, Any]] = []  # (S,) integer coefficients, variable
    deterministic: list[tuple[int, Any]] = []  # terms identical in every scenario (visits)
    arcs_of: list[dict[tuple[Any, int], Any]] = []
    task: dict[tuple[int, int], list[Any]] = {}
    START, END = "start", T

    for c, comp in enumerate(inst.components):
        ct = inst.types[comp.type]
        arcs: dict[tuple[Any, int], Any] = {}
        out_arcs: dict[Any, list[Any]] = defaultdict(list)
        in_arcs: dict[Any, list[Any]] = defaultdict(list)

        def add_arc(
            u: Any,
            v: int,
            c: int = c,
            ct: Any = ct,
            arcs: dict[tuple[Any, int], Any] = arcs,
            out_arcs: dict[Any, list[Any]] = out_arcs,
            in_arcs: dict[Any, list[Any]] = in_arcs,
        ) -> None:
            i = 0 if u == START else u + 1
            pm = 0.0 if v == END else float(ct.cost_pm)
            var = model.new_bool_var(f"a{c}_{u}_{v}")
            arcs[u, v] = var
            out_arcs[u].append(var)
            in_arcs[v].append(var)
            if objective == "mean":
                linear.append((round(scale * (pm + float(mean_table[c, i, v]))), var))
            else:
                coefs = np.rint(scale * (pm + cost_table[c, i, v])).astype(np.int64)
                per_scenario.append((coefs, var))

        for u in [START, *range(T)]:
            u_week = -comp.initial_age if u == START else u
            for v in range(
                max(0, u_week + ct.min_interval), min(T - 1, u_week + ct.max_interval) + 1
            ):
                add_arc(u, v)
            if END - u_week <= ct.max_interval:
                add_arc(u, END)

        model.add_exactly_one(out_arcs[START])
        model.add_exactly_one(in_arcs[END])
        for t in range(T):
            if in_arcs[t] or out_arcs[t]:
                model.add(sum(in_arcs[t]) == sum(out_arcs[t]))
                if in_arcs[t]:
                    task[c, t] = in_arcs[t]
        arcs_of.append(arcs)

    visits_by_week: dict[int, list[Any]] = defaultdict(list)
    for a in range(inst.n_aircraft):
        comps = [c for c, comp in enumerate(inst.components) if comp.aircraft == a]
        for t in range(T):
            xs = [sum(task[c, t]) for c in comps if (c, t) in task]
            if not xs:
                continue
            visit = model.new_bool_var(f"visit{a}_{t}")
            for x in xs:
                model.add(x <= visit)
            model.add(visit <= sum(xs))
            visits_by_week[t].append(visit)
            deterministic.append((round(scale * inst.downtime_cost), visit))

    for t in range(T):
        if visits_by_week[t]:
            model.add(sum(visits_by_week[t]) <= int(inst.bays[t]))
        load = [
            (round(100 * inst.types[inst.components[c].type].labor_pm), sum(task[c, t]))
            for c in range(inst.n_components)
            if (c, t) in task
        ]
        if load:
            model.add(sum(h * x for h, x in load) <= round(100 * inst.labor[t]))

    availability = inst.part_availability
    for k in range(len(inst.types)):
        used: list[Any] = []
        for t in range(T):
            used.extend(
                sum(task[c, t])
                for c, comp in enumerate(inst.components)
                if comp.type == k and (c, t) in task
            )
            if used:
                model.add(sum(used) <= int(availability[k, t]))

    if objective == "mean":
        model.minimize(sum(coef * var for coef, var in linear + deterministic))
        divisor = scale
    else:
        visits = sum(coef * var for coef, var in deterministic)
        big = int(sum(int(c.max()) for c, _ in per_scenario) + sum(c for c, _ in deterministic))
        eta = model.new_int_var(0, big, "eta")
        excess = []
        for s in range(S):
            z = sum(int(coefs[s]) * var for coefs, var in per_scenario if coefs[s]) + visits
            t_s = model.new_int_var(0, big, f"t{s}")
            model.add(t_s >= z - eta)
            excess.append(t_s)
        model.minimize(K * eta + sum(excess))
        divisor = scale * K

    if hint is not None:
        for c, hinted in enumerate(hint):
            chosen = set(zip([START, *hinted], [*hinted, END], strict=True))
            for key, var in arcs_of[c].items():
                model.add_hint(var, key in chosen)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = workers
    solver.parameters.random_seed = seed
    status = solver.solve(model)
    runtime = time.perf_counter() - start_time
    n_arcs = sum(len(a) for a in arcs_of)
    bound = solver.best_objective_bound / divisor
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):  # pragma: no cover - time-outs
        return ExactResult(
            None, float("nan"), bound, False, solver.status_name(status), runtime, n_arcs
        )

    schedule = []
    for arcs in arcs_of:
        succ = {u: v for (u, v), var in arcs.items() if solver.value(var)}
        events: list[int] = []
        node: Any = START
        while succ[node] != END:
            node = succ[node]
            events.append(node)
        schedule.append(tuple(int(e) for e in events))
    plan = tuple(schedule)
    planned, *_ = planned_part(problem, plan)
    costs = scenario_costs(cost_table, planned, plan)
    value = float(costs.mean()) if objective == "mean" else cvar(costs, alpha)
    return ExactResult(
        schedule=plan,
        objective=value,
        bound=bound,
        optimal=status == cp_model.OPTIMAL,
        status=solver.status_name(status),
        runtime=runtime,
        n_arcs=n_arcs,
    )
