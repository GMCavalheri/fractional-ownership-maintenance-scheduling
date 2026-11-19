"""Scenario best response: one component's optimal plan against the scenario-averaged costs.

With every other component held fixed, the expected cost of one component's plan is a sum of
arc costs on a time-indexed DAG (the AVR-04 structure): an arc from renewal ``u`` to renewal
``v`` costs the scenario-averaged segment cost (failures and forced tasks) plus the task at
``v``, which is cheaper when the aircraft is already in the hangar that week for another
component. The shortest path is the component's optimal plan for the expected-cost objective.

Unlike AVR-04's ``best_response``, the hangar, labour and parts capacities are not checked
here: the GA's decoder (``pmo.decoder.decode``) repairs them, as it does for every other move.
For CVaR or worst-case objectives the move is a heuristic, scored like any other.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from fracsched.problem import FleetProblem
from fracsched.utilization_model.model import FloatArray


def best_response(
    problem: FleetProblem,
    mean_costs: FloatArray,
    plan: Sequence[Sequence[int]],
    c: int,
) -> list[int]:
    """Optimal task weeks of component ``c`` given ``plan`` for the others.

    ``mean_costs`` is the scenario-averaged cost table of shape ``(C, T + 1, T + 1)``.
    The calendar windows are the problem's (``base`` instance) min and max intervals.
    """
    inst = problem.base
    T = inst.horizon
    comp = inst.components[c]
    ct = inst.types[comp.type]
    in_hangar = [False] * T
    for other, events in enumerate(plan):
        if other != c and inst.components[other].aircraft == comp.aircraft:
            for t in events:
                if 0 <= t < T:
                    in_hangar[t] = True
    task = [ct.cost_pm + (0.0 if in_hangar[t] else inst.downtime_cost) for t in range(T)]
    table = mean_costs[c]

    # Nodes: 0 = START (week -initial_age), 1..T = a task in week 0..T-1, T + 1 = END (week T).
    week = [-comp.initial_age, *range(T), T]
    dist = [math.inf] * (T + 2)
    parent = [-1] * (T + 2)
    dist[0] = 0.0
    for node in range(T + 1):
        if dist[node] == math.inf:
            continue
        w = week[node]
        for v in range(max(0, w + ct.min_interval), min(T - 1, w + ct.max_interval) + 1):
            d = dist[node] + float(table[node, v]) + task[v]
            if d < dist[v + 1]:
                dist[v + 1], parent[v + 1] = d, node
        if T - w <= ct.max_interval:
            d = dist[node] + float(table[node, T])
            if d < dist[T + 1]:
                dist[T + 1], parent[T + 1] = d, node
    if dist[T + 1] == math.inf:  # pragma: no cover - the calendar windows always reach END
        raise ValueError("no plan respects the calendar windows")
    events, node = [], parent[T + 1]
    while node > 0:
        events.append(week[node])
        node = parent[node]
    return events[::-1]
