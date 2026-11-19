# `problem` and `scenarios`: the FH-clock problem and its evaluator

**Lesson:** [2 · Planning for the average](lessons/02-planning-for-the-average.md) ·
**Code:** [`src/fracsched/problem.py`](../src/fracsched/problem.py),
[`src/fracsched/scenarios.py`](../src/fracsched/scenarios.py)

## Model

`FleetProblem` keeps AVR-04's `pmo.Instance` (fleet, capacities, costs, calendar windows) and
adds Weibull scales and limits in FH. A segment between consecutive renewals costs its
expected failures, the cumulative hazard at its end age minus that at its start age, plus
forced tasks: a task is forced in the week an FH limit would be passed before the planned
week, at the task cost plus an unscheduled premium. Both depend only on the segment's end
points and the scenario, so a plan's cost is a sum of table look-ups.

## API

| function | purpose |
|---|---|
| `main_problem`, `small_problem`, `from_pmo` | AVR-04's instances on the FH clock |
| `FleetProblem.at_mean()` | AVR-04's week-clock instance at the design utilization |
| `FleetProblem.subproblem(...)` | the remaining problem from an observed state (Lesson 5) |
| `segment_tables`, `cost_table` | `(component, start, end, scenario)` failures, forced tasks, costs |
| `evaluate`, `evaluate_in_chunks`, `scenario_costs` | a plan's per-scenario costs |

## Failure modes

A week's hours reaching an FH limit (the recourse is undefined), wrong shapes, components past
their limits at week 0 and calendar limits shorter than FH limits raise `ValueError`.

## Verification

At constant utilization: `at_mean()` equals AVR-04's instance field for field, and the
evaluator equals `pmo.evaluate` and AVR-04's published costs to $10^{-12}$; a week-by-week
simulator agrees with every table entry under random utilization; forced tasks by hand
([`tests/test_scenarios.py`](../tests/test_scenarios.py)).
