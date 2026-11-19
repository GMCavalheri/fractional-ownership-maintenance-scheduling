"""Scoring a maintenance plan across utilization scenarios.

A plan fixes the weeks of every preventive task. Each scenario fixes how many FH every
aircraft flies each week. Between two consecutive renewals of a component (its *segment*),
the scenario decides two things:

* **expected failures**: minimal repair with a Weibull hazard in FH, ``H(age_end) - H(age_start)``;
* **forced tasks (recourse)**: if the component's FH age would pass its limit during week
  ``t`` before the planned task, a task is forced at the start of week ``t``. It renews the
  component and costs the task plus an unscheduled visit. The planned task still happens.

Both depend only on the segment's two end points and the scenario, never on other segments.
So, as in AVR-04, a plan's cost is a sum of *segment costs*, and one table of them per
component (start node x end node x scenario) serves the evaluator, the best-response move and
the exact model alike.

Node convention (shared with AVR-04's DAG): start index ``0`` is START, the component's state
at week 0 (``initial_fh`` FH since its last task); start index ``i ≥ 1`` is a task in week
``i - 1``. End index ``j < T`` is a planned task in week ``j``; ``j = T`` is END, the horizon.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

import numpy as np
from pmo.evaluate import evaluate as pmo_evaluate
from pmo.instance import Schedule

from fracsched.problem import FleetProblem
from fracsched.utilization_model.model import FloatArray

PENALTY = 1e6  # $ per unit of constraint violation, as AVR-04's GA


def cumulative_hours(u: FloatArray) -> FloatArray:
    """``F[s, a, t]``: FH flown before the start of week ``t = 0..T``, from ``u[s, a, t]``."""
    S, A, T = u.shape
    F = np.zeros((S, A, T + 1))
    np.cumsum(u, axis=2, out=F[:, :, 1:])
    return F


@dataclass(frozen=True)
class SegmentTables:
    """Per component: expected failures and forced tasks for every (start, end, scenario).

    Arrays have shape ``(C, T + 1, T + 1, S)``; entries with ``end`` before ``start`` are 0
    and are never read for a valid plan.
    """

    failures: FloatArray
    forced: FloatArray

    @property
    def n_scenarios(self) -> int:
        return int(self.failures.shape[-1])

    def costs(self, problem: FleetProblem) -> FloatArray:
        """Segment cost table: failures x failure cost + forced tasks x forced-task cost."""
        k = [c.type for c in problem.base.components]
        cf = np.array([problem.failure_cost(t) for t in k])[:, None, None, None]
        cr = np.array([problem.forced_task_cost(t) for t in k])[:, None, None, None]
        return np.asarray(cf * self.failures + cr * self.forced, dtype=np.float64)


def _segments_from(
    problem: FleetProblem, k: int, F: FloatArray, start_week: int, start_age: FloatArray, first: int
) -> tuple[FloatArray, FloatArray]:
    """Failures and forced counts from one start, for every end index (``(S, T + 1)`` each).

    ``F`` is the aircraft's cumulative hours ``(S, T + 1)``. ``first`` is the first end index
    the start can reach (``start_week`` for START, ``start_week + 1`` for a task).
    """
    S, T1 = F.shape
    T = T1 - 1
    limit = problem.fh_limit[k] * (1 + problem.limit_tolerance)
    rows = np.arange(S)
    weeks = np.arange(T)
    ends = np.arange(T1)
    epoch = np.full(S, start_week)
    age0 = start_age.astype(np.float64).copy()
    acc = np.zeros(S)
    count = np.zeros(S)
    done = np.full(S, first - 1)  # end indices <= done are filled
    failures = np.zeros((S, T1))
    forced = np.zeros((S, T1))
    active = np.ones(S, dtype=bool)
    while active.any():
        base = F[rows, epoch]
        h0 = problem.cumulative_hazard(k, age0)
        # forced in week t if the age at the end of week t would pass the limit
        end_age = age0[:, None] + F[:, 1:] - base[:, None]
        over = (weeks[None, :] >= epoch[:, None]) & (end_age > limit)
        f = np.where(over.any(axis=1), np.argmax(over, axis=1), T)
        f = np.where(active, f, T)
        fill = active[:, None] & (ends[None, :] > done[:, None]) & (ends[None, :] <= f[:, None])
        age_at = np.maximum(age0[:, None] + F - base[:, None], 0.0)
        value = acc[:, None] + problem.cumulative_hazard(k, age_at) - h0[:, None]
        failures = np.where(fill, value, failures)
        forced = np.where(fill, count[:, None], forced)
        renew = active & (f < T)
        f_safe = np.minimum(f, T)
        acc = np.where(
            renew,
            acc + problem.cumulative_hazard(k, age0 + F[rows, f_safe] - base) - h0,
            acc,
        )
        epoch = np.where(renew, f, epoch)
        age0 = np.where(renew, 0.0, age0)
        count = count + renew
        done = np.where(renew, f, done)
        active = renew
    return failures, forced


def _component_tables(
    problem: FleetProblem, u: FloatArray
) -> Iterator[tuple[int, FloatArray, FloatArray]]:
    """For each component: its failures and forced tables, ``(T + 1, T + 1, S)`` each."""
    S, A, T = u.shape
    if problem.horizon != T or problem.base.n_aircraft != A:
        raise ValueError("u must have shape (scenarios, aircraft, horizon)")
    max_week = float(np.max(u)) if u.size else 0.0
    if max_week >= min(problem.fh_limit):
        raise ValueError("a single week's hours reach an FH limit; the recourse is undefined")
    F = cumulative_hours(u)
    for c, comp in enumerate(problem.base.components):
        Fa = F[:, comp.aircraft, :]
        k = comp.type
        failures = np.zeros((T + 1, T + 1, S))
        forced = np.zeros((T + 1, T + 1, S))
        fl, fo = _segments_from(problem, k, Fa, 0, np.full(S, problem.initial_fh[c]), 0)
        failures[0], forced[0] = fl.T, fo.T
        for w in range(T):
            fl, fo = _segments_from(problem, k, Fa, w, np.zeros(S), w + 1)
            failures[w + 1], forced[w + 1] = fl.T, fo.T
        yield c, failures, forced


def segment_tables(problem: FleetProblem, u: FloatArray) -> SegmentTables:
    """Tables for every component of ``problem`` under the scenarios ``u`` (``(S, A, T)``)."""
    S, _, T = u.shape
    C = problem.n_components
    failures = np.zeros((C, T + 1, T + 1, S))
    forced = np.zeros((C, T + 1, T + 1, S))
    for c, fl, fo in _component_tables(problem, u):
        failures[c], forced[c] = fl, fo
    return SegmentTables(failures, forced)


def cost_table(problem: FleetProblem, u: FloatArray) -> FloatArray:
    """The segment cost table alone, ``(C, T + 1, T + 1, S)``, at a third of the memory.

    Equal to ``segment_tables(problem, u).costs(problem)``; this is what the search uses.
    """
    S, _, T = u.shape
    out = np.zeros((problem.n_components, T + 1, T + 1, S))
    for c, fl, fo in _component_tables(problem, u):
        k = problem.base.components[c].type
        out[c] = problem.failure_cost(k) * fl + problem.forced_task_cost(k) * fo
    return out


def segment_index(schedule: Schedule, horizon: int) -> tuple[list[int], list[int], list[int]]:
    """(component, start index, end index) of every segment of ``schedule``."""
    cs, starts, ends = [], [], []
    for c, events in enumerate(schedule):
        prev = 0
        for t in events:
            cs.append(c)
            starts.append(prev)
            ends.append(int(t))
            prev = int(t) + 1
        cs.append(c)
        starts.append(prev)
        ends.append(horizon)
    return cs, starts, ends


@dataclass(frozen=True)
class ScenarioEvaluation:
    """A plan scored in every scenario. All per-scenario arrays have shape ``(S,)``."""

    planned_cost: float  # preventive tasks + planned hangar visits (the same in every scenario)
    failure_cost: FloatArray
    forced_cost: FloatArray
    expected_failures: FloatArray
    forced_tasks: FloatArray
    n_tasks: int
    n_visits: int
    violation: float  # calendar-interval and capacity violations, AVR-04's units

    @property
    def total(self) -> FloatArray:
        return np.asarray(self.planned_cost + self.failure_cost + self.forced_cost)

    @property
    def feasible(self) -> bool:
        return self.violation <= 1e-9


def planned_part(problem: FleetProblem, schedule: Schedule) -> tuple[float, int, int, float]:
    """Planned cost, tasks, visits and violations, from AVR-04's evaluator on the calendar."""
    ev = pmo_evaluate(problem.base, schedule)
    return float(ev.pm_cost + ev.visit_cost), int(ev.n_events), int(ev.n_visits), ev.total_violation


def evaluate(
    problem: FleetProblem, tables: SegmentTables, schedule: Schedule
) -> ScenarioEvaluation:
    """Score ``schedule`` in every scenario of ``tables``."""
    planned, n_tasks, n_visits, violation = planned_part(problem, schedule)
    cs, starts, ends = segment_index(schedule, problem.horizon)
    fl = tables.failures[cs, starts, ends]  # (n_segments, S)
    fo = tables.forced[cs, starts, ends]
    types = [problem.base.components[c].type for c in cs]
    cf = np.array([problem.failure_cost(k) for k in types])[:, None]
    cr = np.array([problem.forced_task_cost(k) for k in types])[:, None]
    return ScenarioEvaluation(
        planned_cost=planned,
        failure_cost=(cf * fl).sum(axis=0),
        forced_cost=(cr * fo).sum(axis=0),
        expected_failures=fl.sum(axis=0),
        forced_tasks=fo.sum(axis=0),
        n_tasks=n_tasks,
        n_visits=n_visits,
        violation=violation,
    )


def scenario_costs(cost_table: FloatArray, planned: float, schedule: Schedule) -> FloatArray:
    """Fast path for search: per-scenario totals from a precomputed cost table."""
    cs, starts, ends = segment_index(schedule, cost_table.shape[1] - 1)
    return np.asarray(planned + cost_table[cs, starts, ends].sum(axis=0), dtype=np.float64)


def evaluate_in_chunks(
    problem: FleetProblem, u: FloatArray, schedules: Sequence[Schedule], chunk: int = 500
) -> list[ScenarioEvaluation]:
    """Score several plans on many scenarios, building the tables ``chunk`` scenarios at a time."""
    parts: list[list[ScenarioEvaluation]] = [[] for _ in schedules]
    for lo in range(0, u.shape[0], chunk):
        tables = segment_tables(problem, u[lo : lo + chunk])
        for i, schedule in enumerate(schedules):
            parts[i].append(evaluate(problem, tables, schedule))
    out = []
    for evs in parts:
        first = evs[0]
        out.append(
            ScenarioEvaluation(
                planned_cost=first.planned_cost,
                failure_cost=np.concatenate([e.failure_cost for e in evs]),
                forced_cost=np.concatenate([e.forced_cost for e in evs]),
                expected_failures=np.concatenate([e.expected_failures for e in evs]),
                forced_tasks=np.concatenate([e.forced_tasks for e in evs]),
                n_tasks=first.n_tasks,
                n_visits=first.n_visits,
                violation=first.violation,
            )
        )
    return out
