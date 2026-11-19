# `dynamic_rescheduling`: re-planning on a rolling horizon

**Lesson:** [5 · Re-planning as the hours come in](lessons/05-re-planning-as-the-hours-come-in.md) ·
**Code:** [`src/fracsched/dynamic_rescheduling/`](../src/fracsched/dynamic_rescheduling/)

## Model

Every `period` weeks: rebuild each component's state from the actual hours and executed tasks
(forced ones included), form the remaining problem, ask a policy for a plan of the rest of the
year, and commit the next `period` weeks. Policies: keep the plan; re-plan for the average
(one scenario at the design rate); re-plan on scenarios sampled conditionally on the observed
regimes and demand factor. The realised year is scored on the actual hours.

## API

| function | purpose |
|---|---|
| `sample_actual(model, rng, A, T)` | an actual year and the state observed each week |
| `simulate(problem, plan, actual, policy, config, rng)` | the rolling loop |
| `static_policy`, `deterministic_policy`, `robust_policy` | the policies |
| `component_state` | a component's ages and forced weeks at a given week |

## Verification

The state tracker against the evaluator's forced tasks; failures splitting additively at a
re-plan; the static policy reproducing the evaluator exactly; the past never rewritten
([`tests/test_rolling.py`](../tests/test_rolling.py)).
