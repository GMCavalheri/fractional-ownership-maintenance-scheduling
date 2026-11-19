# `exact_saa`: the sample-average problem, solved exactly

**Lesson:** [4 · The exact answer for a sampled future](lessons/04-the-exact-answer-for-a-sampled-future.md) ·
**Code:** [`src/fracsched/exact_saa/`](../src/fracsched/exact_saa/)

## Model

AVR-04's interval-DAG integer program (one path per component, visits, bays, labour,
cumulative spare parts) with arc costs from the scenario tables. Expected cost is exactly
linear in the arcs. CVaR uses the Rockafellar-Uryasev variables with $K = (1-\alpha)S$ an
integer. Costs are scaled by 10 and rounded; the returned plan is re-scored exactly.

## API

| function | purpose |
|---|---|
| `solve_saa(problem, cost_table, objective, alpha, time_limit, workers, seed, hint)` | CP-SAT |
| `ExactResult` | plan, exact objective, bound, optimality, gap |

## Failure modes

A non-integer $(1-\alpha)S$ raises `ValueError`. Time-limited runs return the best plan and a
bound; only proven optima with one worker are reproducible across machines.

## Verification

Joint brute force over every feasible plan on two tiny instances, for expected cost and CVaR;
agreement with AVR-04's own exact model at constant utilization
([`tests/test_exact_saa.py`](../tests/test_exact_saa.py)).
