# `deterministic_baseline`: planning for the average

**Lesson:** [2 · Planning for the average](lessons/02-planning-for-the-average.md) ·
**Code:** [`src/fracsched/deterministic_baseline/`](../src/fracsched/deterministic_baseline/)

## Model

AVR-04's genetic algorithm and fixed-interval rules, imported from `pmo` v1.0.0 and run
unchanged on `FleetProblem.at_mean()`, the problem in which every aircraft flies exactly the
design utilization. The resulting plans are then judged on the FH clock under uncertainty.

## API

| function | purpose |
|---|---|
| `average_plan(problem, config)` | `pmo.ga.run_ga` on the mean-utilization instance |
| `fixed_interval_plans(problem)` | AVR-04's two fixed-interval baselines |
| `constant_scenario(problem, n)` | the world the average plan assumes |

## Verification

With the same seed the wrapper returns exactly AVR-04's GA plan, and AVR-04's published
per-seed costs are reproduced to $10^{-12}$
([`tests/test_scenarios.py`](../tests/test_scenarios.py),
[`validation/results/deterministic.md`](../validation/results/deterministic.md)).
