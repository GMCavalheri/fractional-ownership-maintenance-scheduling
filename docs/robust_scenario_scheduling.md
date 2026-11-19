# `robust_scenario_scheduling`: a GA judged across sampled futures

**Lesson:** [3 · Planning for many futures](lessons/03-planning-for-many-futures.md) ·
**Code:** [`src/fracsched/robust_scenario_scheduling/`](../src/fracsched/robust_scenario_scheduling/)

## Model

AVR-04's GA (encoding, decoder, crossover, mutations, seeding) with a sample-average fitness:
the plan's per-scenario costs from a cost table, reduced to the expected cost, CVaR or the
worst case, plus AVR-04's penalty per unit of violation, rounded to cents. An extra move, the
scenario best response, re-plans one component as a shortest path on the scenario-averaged
segment costs (capacity left to the decoder). Plans passed as `seeds` warm-start the search.

## API

| function | purpose |
|---|---|
| `run_robust_ga(problem, cost_table, config, seeds)` | the search |
| `RobustConfig` | objective (`mean`, `cvar`, `worst`), α, population, generations, seed |
| `plan_objective`, `reduce_costs` | how a plan is scored |
| `best_response` | one component's optimal plan, others fixed |
| `run_many` | independent runs in parallel processes |

## Verification

The best response against enumeration of every calendar-feasible plan of a component; the
objective against the evaluator; elitism never losing a seed; reproducibility by seed; parallel
equal to serial ([`tests/test_robust.py`](../tests/test_robust.py)). Its gap to proven optima is
measured in [`exact.md`](../validation/results/exact.md).
