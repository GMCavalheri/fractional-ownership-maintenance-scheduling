# What planning for the average costs a fractional fleet

**A trade-off report: deterministic against robust and adaptive maintenance scheduling under
uncertain utilization.** Every number comes from
[`validation/results/`](../validation/results/), reproduced by `validation/run_all.py`.
Synthetic fleet, illustrative costs and stated assumptions throughout (see [scope](scope.md)).

## Summary

A fractional-ownership business jet flies when its owners decide to, and that is hard to
predict. In this model one aircraft's year ranges from 353 to 1219 flight hours (P1 to P99)
around the 800 a programme sells, and a task due every 600 FH falls due anywhere from week 29
to week 57 (P10 to P90).

1. **Planning for the average breaks its promise by a fifth.** AVR-04's genetic algorithm,
   reproduced exactly at the design utilization, plans a year that should cost \$3.58M. On
   10 000 held-out futures it costs \$4.29M on average. Most of the gap is tasks forced when
   components reach their flight-hour limits before their planned weeks.
2. **The overrun is the price of ignorance, not of variability.** With perfect foresight of
   each future, the best plans would cost about what was promised (wait-and-see \$3.62M,
   an upper estimate; on small instances, proven exactly, 2.6 to 4.7 % *below* the promise).
   The cost is not knowing which future comes.
3. **A single plan that looks at the futures recovers 13 % of the overrun.** A sample-average
   plan saves \$0.09M a year (2.2 %) and cuts the P99 year by \$0.23M. A genetic algorithm
   reaches the sample-average optimum to within 0.24 % (proven on small instances), and 100
   sampled futures are enough.
4. **Re-planning every four weeks recovers more than half.** Re-planning on the observed
   hours saves 8 to 9 % against keeping the plan for the average, in every one of 48 simulated
   years, by catching fast-wearing components before they are forced.
5. **Two expected remedies do little.** Owner contracts cap the fleet's hours but barely an
   aircraft's variability; uncertain wear rates (EJD-01's posteriors) barely change an
   expected-cost plan, though plugging in the mean scale understates cost by 2 %.

## 1. The question

The PLAN asks how a maintenance plan built for average utilization fares when utilization is
uncertain, and what explicitly planning for that uncertainty is worth. The answer is
measured on AVR-04's case study (10 aircraft × 4 component types × 52 weeks, with hangar,
labour and spare-part limits), moved from a week clock to a flight-hour clock:

* components wear with flight hours (Weibull, minimal repair);
* tasks have FH limits and calendar limits 50 % longer;
* a plan that falls behind the hours pays for forced tasks at an unscheduled premium.

## 2. The uncertainty

[Lesson 1](lessons/01-flying-hours-you-cant-predict.md). Weekly hours combine a season, a
fleet-wide demand factor and each aircraft's own regime (idle, normal, spike), calibrated
to 800 FH a year:

| | value |
|---|---:|
| one aircraft's year: sd, CV | 186 FH, 0.23 |
| the same if weeks were independent | 88 FH |
| a 10-aircraft fleet's CV | 0.106 |
| a 600 FH interval, P10 / median / P90 | 29 / 39 / 57 weeks |

Persistence (regimes lasting weeks) makes a year twice as uncertain as weekly noise would.
The fleet is much more predictable than any aircraft in it.

## 3. The deterministic baseline

[Lesson 2](lessons/02-planning-for-the-average.md). At constant utilization the FH problem is
AVR-04's, field for field. Its fixed-interval plans and three GA runs reproduce AVR-04's
published costs to a relative $10^{-12}$. Judged on 2000 held-out futures:

| plan | cost at the mean | expected cost | expected vs promised |
|---|---:|---:|---:|
| fixed interval, cost-optimal | 4.772 | 5.662 | +18.6 % |
| GA plan for the average | 3.582 | 4.291 | +19.8 % |

AVR-04's consolidation of tasks into shared visits survives uncertainty; the GA plan is still
the cheapest. The overrun comes from about nine forced tasks a year (\$0.51M) and Jensen's
inequality on convex wear (\$0.20M).

## 4. Robust plans

[Lessons 3](lessons/03-planning-for-many-futures.md) and
[4](lessons/04-the-exact-answer-for-a-sampled-future.md). AVR-04's GA with a sample-average
fitness over 100 futures, judged on 10 000 others
([trade-off results](../validation/results/tradeoff.md)):

| plan | mean | P90 | P99 | CVaR 90 % |
|---|---:|---:|---:|---:|
| plan for the average | 4.287 | 5.148 | 6.109 | 5.567 |
| robust, expected cost | 4.194 | 4.963 | 5.882 | 5.358 |
| robust, CVaR 90 % | 4.240 | 4.963 | 5.847 | 5.339 |

* The robust plans buy slack: 10 to 15 more tasks, a third fewer forced ones.
* A worst-case objective over 100 futures overfits: 12 % better in sample, 3.6 % out of sample.
* On small instances the exact optimum is proven by CP-SAT, and the GA's best of three runs
  is within 0.24 % (expected cost) and 0.87 % (CVaR) of it. On the main instance the GA is
  within 3.4 % of CP-SAT's bound.
* The SAA plan is within 2.7 to 4.0 % of the true optimum (95 % Mak-Morton-Wood bound, small
  instances); about 100 in-sample futures are enough.

## 5. Re-planning

[Lesson 5](lessons/05-re-planning-as-the-hours-come-in.md). 48 actual years, re-planned every
four weeks from the observed state:

| policy | realised cost | forced tasks | vs keeping the average plan |
|---|---:|---:|---:|
| keep the plan for the average | 4.310 | 8.98 | — |
| keep the robust plan | 4.231 | 6.21 | −1.84 % |
| re-plan for the average | 3.967 | 3.08 | −7.95 % |
| re-plan on conditional scenarios | 3.920 | 1.92 | −9.05 % |

## 6. The trade-off

[Lesson 8](lessons/08-the-price-of-planning-for-the-average.md). The overrun of the plan for
the average, \$0.705M on the main fleet, splits into:

| part | \$M | meaning |
|---|---:|---|
| WS − EV | 0.041 (within error of 0) | variability itself, with perfect foresight |
| RP − WS (EVPI) | 0.571 | not knowing the future |
| EEV − RP (VSS) | 0.093 | what a better single plan removes |

On the five small instances, where every term is exact, WS is 2.6 to 4.7 % below EV, EVPI is
13 to 17 % of EV and VSS 4.0 to 8.6 %.

**Recommendation, on these assumptions:** do not stop at a better plan. Re-plan often from the
observed hours, and sample the look-ahead futures conditionally on the present. A robust
plan is the right starting point for that loop, and the right answer only where re-planning
is impossible.

## 7. Extensions

* **Owner contracts** ([Lesson 6](lessons/06-who-owns-the-hours.md)). With 10 % borrowing a
  third of owner-years hit their cap; the fleet's CV falls from 0.103 to 0.066 but an
  aircraft's only from 0.232 to 0.221. Caps cut the mean hours, so the robust plan's edge
  falls from 2.1 % to 0.7 %; re-optimising on contract scenarios recovers 1.3 %.
* **Uncertain wear** ([Lesson 7](lessons/07-uncertain-wear-on-top-of-uncertain-hours.md)).
  EJD-01's Gamma-Poisson update gives each component a posterior wear multiplier. Uncertain
  hours give the average plan a cost sd of \$0.64M, uncertain wear \$0.22M; a plan optimised
  for both differs from the hours-only plan by \$2000. Plugging in the posterior mean scale
  understates expected cost by 2.0 %.

## 8. Limits

* **Synthetic.** Utilization regimes, costs, capacities and component lives are illustrative;
  only the 800 hours a year and the 1/16 minimum share come from public sources. The numbers
  are measurements of this model, not of any operator.
* **Recourse.** A forced task costs a fixed premium and does not consume planned capacity; the
  planned task still happens. Real operators may cancel or merge it.
* **Observability.** Re-planning assumes the demand regimes are observed (bookings). Filtering
  them from hours alone would lower its value somewhat.
* **Churn.** Re-planning moves tasks at no cost here; a real operator pays for re-booking.
* **Heuristic on the main fleet.** RP and WS on the main instance are GA upper estimates; only
  the small instances are exact. The main-instance CP-SAT result is time-limited and
  machine-dependent (`exact_main.md`, the one result CI does not byte-compare).
* **Novelty.** The methods are established, and robust and look-ahead scheduling of airline
  heavy checks under uncertain utilization exists (see [related work](related-work.md)). The
  contribution is the measurement for fractional fleets, stated narrowly.
