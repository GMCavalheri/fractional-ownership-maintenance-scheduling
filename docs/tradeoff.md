# `tradeoff`: what uncertainty costs and what each model recovers

**Lesson:** [8 · The price of planning for the average](lessons/08-the-price-of-planning-for-the-average.md) ·
**Code:** [`src/fracsched/tradeoff/`](../src/fracsched/tradeoff/)

## Model

EV (the deterministic optimum), EEV (its plan's expected cost), RP (the best single plan),
WS (perfect foresight), with $\text{WS} \le \text{RP} \le \text{EEV}$, VSS = EEV − RP and
EVPI = RP − WS. Mak-Morton-Wood: the mean of $M$ SAA optima estimates RP from below, a
candidate's held-out mean its cost; their difference plus confidence terms bounds the gap.

## API

| function | purpose |
|---|---|
| `ladder_on_sample(costs, ev_plan, ev_value)` | the measures from a plan-by-scenario cost matrix |
| `Ladder` | `vss`, `evpi`, `overrun` |
| `mmw_gap(saa_values, held_out_costs, alpha)` | the optimality-gap bound |
| `paired_difference(a, b)` | mean and se of a paired difference |

## Verification

$\text{WS} \le \text{RP} \le \text{EEV}$ on any cost matrix (Hypothesis); on a tiny instance the
exact SAA model reproduces RP and every wait-and-see term found by brute force
([`tests/test_tradeoff.py`](../tests/test_tradeoff.py)).
