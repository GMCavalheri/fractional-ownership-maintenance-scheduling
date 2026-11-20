# Lesson 4 · The exact answer for a sampled future

> Lesson 3's plans came from a genetic algorithm, a heuristic. It found savings, but how much
> did it leave on the table? A heuristic cannot answer that about itself. This lesson builds
> an exact model of the same sample-average problem, solves it to proven optimality on small
> instances, and measures the GA against it. The model is AVR-04's, and it carries over
> unchanged because of one structural fact: under uncertainty, a segment's cost still depends
> only on where it starts and where it ends.

**Code:** [`src/fracsched/exact_saa/`](../../src/fracsched/exact_saa/) ·
**Tests:** [`tests/test_exact_saa.py`](../../tests/test_exact_saa.py) ·
**Results:** [`validation/results/exact.md`](../../validation/results/exact.md),
[`exact_main.md`](../../validation/results/exact_main.md) ·
**Previous:** [Lesson 3](03-planning-for-many-futures.md) ·
**Next:** [Lesson 5](05-re-planning-as-the-hours-come-in.md)

## Learning objectives

By the end of this lesson you should be able to:

1. Write the sample-average maintenance problem as an integer program on a time-indexed DAG.
2. Prove that its expected-cost objective is exactly linear, with no approximation.
3. Linearise CVaR with the Rockafellar-Uryasev variables, and explain why it is much harder.
4. Read a solver's bound and gap, and know which numbers are reproducible.
5. Decide when a heuristic is good enough, using an exact model as the yardstick.

---

## 1. The model

For each component $c$, build a graph whose nodes are its possible renewals: START (its state
at week 0), a task in week $t$ for $t = 0, \dots, T-1$, and END (the horizon). An arc $(i, j)$
means "renewed at $i$, next renewed at $j$". It exists only if the gap respects the
component's calendar window, $I_{\min} \le j - i \le I_{\max}$ (END checks only the maximum). A
plan for $c$ is a path from START to END. With a binary $x_{c,ij}$ per arc:

```math
\sum_{j} x_{c,\text{START} \to j} = 1, \qquad \sum_{i} x_{c,i \to \text{END}} = 1, \qquad \sum_i x_{c,i \to t} = \sum_j x_{c,t \to j} \quad \text{for every week } t .
```

The paths are coupled exactly as in AVR-04:
* a visit variable $v_{a,t} \in \{0,1\}$ for aircraft $a$ in week $t$, equal to 1 if any of
  its components is serviced that week;
* at most $B_t$ visits a week (hangar bays);
* labour hours per week;
* cumulative spare parts per type never above stock plus deliveries.

The objective for expected cost is

```math
\min \; \sum_{c} \sum_{(i,j)} \left( p_c \, [j \ne \text{END}] + \bar g_c(i, j) \right) x_{c,ij} + D \sum_{a,t} v_{a,t}, \qquad \bar g_c(i,j) = \frac{1}{S} \sum_{s=1}^{S} g_c(i, j, \omega_s),
```

where $p_c$ is the task cost, $D$ the cost of a planned aircraft-week, and $g_c(i, j, \omega)$
the segment cost of Lesson 2 (failures plus forced tasks) in scenario $\omega$. The table
$\bar g$ is the scenario average of `cost_table`.

## 2. Why this is exact

The cost of a plan in scenario $\omega$ is a sum over its segments of $g_c(i, j, \omega)$,
plus the planned costs. Lesson 2 showed that $g_c$ depends only on the segment's end points
and the scenario: the forced tasks inside a segment and the failures between renewals are
determined by the hours flown between $i$ and $j$. Averaging over scenarios commutes with
the sum:

```math
\frac{1}{S}\sum_s \sum_{\text{segments}} g_c(i,j,\omega_s) = \sum_{\text{segments}} \bar g_c(i,j) .
```

So the sample-average objective is a linear function of the arc variables, with constant
coefficients. There is no linearisation error: the integer program and the SAA problem are
the same problem. The only approximation is CP-SAT's need for integer coefficients. Costs are
multiplied by 10 and rounded, so each arc is off by at most 5 cents. The returned plan is
re-scored exactly.

## 3. CVaR: same constraints, a harder objective

CVaR is not a sum over segments, but Rockafellar & Uryasev make it linear with one variable
$\eta$ and one $t_s \ge 0$ per scenario:

```math
\min \; K\eta + \sum_{s=1}^{S} t_s \quad \text{s.t.} \quad t_s \ge z_s - \eta, \quad z_s = \sum_{c,(i,j)} \big(p_c [j \ne \text{END}] + g_c(i,j,\omega_s)\big) x_{c,ij} + D \sum_{a,t} v_{a,t},
```

with $K = (1-\alpha)S$, so the optimum divided by $K$ is the CVaR. Requiring $K$ to be an
integer keeps every coefficient integral. The model is still exact, but it now has one long
cost expression per scenario, and its linear relaxation is weak: the max-type constraints
$t_s \ge z_s - \eta$ let the relaxation spread the tail over fractional plans. In practice the
expected-cost model proves optimality on the small instances in seconds with 100
scenarios. The CVaR model needs 30 scenarios to do it in minutes.

## 4. How far is the GA from optimal?

AVR-04's small instances (3 aircraft × 3 types × 26 weeks, five seeds) on the FH clock. CP-SAT
on one thread proves every optimum; the plan for the average is the exact optimum at $\bar u$.
Gaps are in sample, relative to the optimum
([results](../../validation/results/exact.md)):

| instance | plan for the average | GA best of 3 | GA median | GA worst |
|---|---:|---:|---:|---:|
| expected cost, 0–4 | +3.5 to +9.7 % | 0.00 to 0.24 % | 0.00 to 1.60 % | 0.00 to 2.95 % |
| CVaR 90 %, 0–4 | +27 to +43 % | 0.00 to 0.87 % | 0.05 to 3.50 % | 0.55 to 3.50 % |

* **The GA is near-optimal when it is run more than once.** Its best of three seeds is within
  a quarter of a percent of the proven expected-cost optimum on every instance, and exact on
  two. A single run can be 3 % off; the planner should always run a few seeds.
* **The plan for the average is a poor answer to the tail question.** On CVaR it is 27 to 43 %
  above the optimum, because it plans every interval up to the limit at the mean and the
  fast tail punishes exactly that.
* **Out of sample the gain holds.** On 2000 held-out futures the exact expected-cost plan
  beats the plan for the average by 3.6 to 6.8 % on these instances.

### The main instance

On the full fleet (40 components, 52 weeks, 100 scenarios, about 41 000 arcs) CP-SAT does not
prove optimality in 300 seconds with 8 threads
([results](../../validation/results/exact_main.md)):

| plan | expected cost (\$M) | above the bound |
|---|---:|---:|
| plan for the average | 4.399 | +6.36 % |
| phase 3 GA | 4.277 | +3.41 % |
| CP-SAT best plan | 4.231 | +2.31 % |
| CP-SAT lower bound | 4.136 | — |

The GA plan is within 3.4 % of *any possible* plan, and CP-SAT's best is 1.1 % better than
the GA's. In sample, the most any plan could save over the plan for the average is
$(4.399 - 4.136)/4.399 = 6.0$ %; the GA captures 2.8 % of it and CP-SAT's plan 3.8 %. Lesson
3's held-out saving of 2.1 % on the main fleet is therefore a lower estimate of what planning
for the futures is worth. These numbers
depend on the machine: a time-limited, multi-threaded search finds different plans and bounds
on different hardware. They are the one result CI does not compare byte for byte.

## 5. Worked example

*One component, a horizon of 6 weeks, calendar window 2 to 4 weeks, initial age 1 week.* The
arcs from START (week −1) reach weeks 1, 2, 3 and END only if $6 - (-1) \le 4$, which is
false. Suppose the averaged segment costs (\$k) and the task cost (\$5k) give:

| path | segments | cost |
|---|---|---|
| START → 2 → END | $\bar g(\text{S},2) = 3$, $\bar g(2,\text{E}) = 6$ | 3 + 5 + 6 = 14 |
| START → 3 → END | $\bar g(\text{S},3) = 5$, $\bar g(3,\text{E}) = 3$ | 5 + 5 + 3 = 13 |
| START → 1 → 4 → END | 2, 3, 1 | 2 + 5 + 3 + 5 + 1 = 16 |

(START → 1 → END is not allowed: END is 5 weeks after week 1.) The optimum is one task in
week 3. In the integer program that is $x_{\text{S},3} = x_{3,\text{E}} = 1$, and flow
conservation at week 3 holds: one arc in, one arc out.

## 6. Code walkthrough

```python
from fracsched.exact_saa import solve_saa
from fracsched.problem import small_problem
from fracsched.scenarios import cost_table

problem = small_problem(0)
table = cost_table(problem, u)  # u: (100, 3, 26) in-sample scenarios
exact = solve_saa(problem, table, objective="mean", time_limit=600)  # one thread, seed 0
print(exact.optimal, exact.objective, exact.bound)

cvar = solve_saa(problem, cost_table(problem, u[:30]), objective="cvar", alpha=0.9)
```

The tests check the model three ways. On two tiny instances it is compared with brute
force over *every* calendar- and capacity-feasible joint plan, for expected cost and for
CVaR. At constant utilization, with calendar limits equal to AVR-04's, it must prove the
same optimum as AVR-04's own `solve_exact`.

## Exercises

1. Why does every arc out of START need its own variable, separate from the arc out of a
   task in week 0, even though both start "at week 0"?
2. Show that with a single scenario ($S = 1$) the expected-cost and CVaR models have the
   same optimum for any $\alpha$.
3. The CVaR model needs $(1-\alpha)S$ to be an integer. How would you handle $\alpha = 0.95$
   with $S = 30$ without changing $S$?
4. Lesson 3's GA was within 0.24 % on the small instances but 3.4 % above the bound on the
   main one. Give two reasons the second number overstates the GA's true gap.
5. AVR-04 concluded that an exact model is the strongest single method on its problem.
   Does that still hold here? When would you still choose the GA?

### Solutions

1. START carries the component's history (its initial calendar age and FH since its last
   task), so its segments have different costs and different windows from a segment that
   starts with a task in week 0 (age 0). Merging them would mix two different states.
2. With one scenario, the CVaR at any level $\alpha$ of a single outcome is that outcome: the
   worst $(1-\alpha)$ share of one value is the value itself. Both objectives are then the same
   linear function.
3. Scale the objective: minimise $(1-\alpha)S\eta + \sum t_s$ multiplied by 2, i.e.
   $3\eta + 2\sum_s t_s$ (since $(1 - 0.95) \cdot 30 = 1.5$). Any common multiplier that makes
   the coefficients integral works.
4. The bound is not tight: after 300 s CP-SAT's lower bound is still below the true optimum,
   and CP-SAT's own best plan is 2.3 % above it. Also, the GA's in-sample value is
   compared, and with 40 components a GA has far more to search than with 9. The true
   gap is at most 3.4 % and at least 1.1 % (the plan CP-SAT found).
5. On the small instances, yes: CP-SAT proves the optimum in seconds. On the main instance it
   cannot prove it in minutes, and the CVaR model is much harder still. The GA stays useful
   wherever the model stops being linear in the arcs. That includes the owner-contract costs
   of Lesson 6, which depend on how many aircraft are grounded in the same week.

## References

* L. Perron and F. Didier, *CP-SAT*, Google OR-Tools, v9.15,
  [developers.google.com/optimization](https://developers.google.com/optimization).
* R. T. Rockafellar and S. Uryasev, "Optimization of conditional value-at-risk", *Journal of
  Risk* 2(3), 2000, pp. 21–41.
* J. R. Birge and F. Louveaux, *Introduction to Stochastic Programming*, 2nd ed., Springer,
  2011, ch. 3 (extensive forms of stochastic integer programs).
* GMCavalheri, AVR-04, `pmo/exact.py` (the interval-DAG model this one extends).
