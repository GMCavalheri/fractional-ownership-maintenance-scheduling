# Course: maintenance scheduling under uncertain utilization

Nine lessons, in order. They take a reader from a stochastic model of a fractional fleet's
flight hours to plans that hedge against it, exact optima that check those plans, re-planning
as the hours come in, and the stochastic-programming measures that say what each step is
worth. Each lesson has:
- learning objectives;
- the theory with derivations;
- a code walkthrough and a worked example;
- exercises with solutions, and references;
- an executed notebook.

Every number comes from [`validation/results/`](../../validation/results/).

**Prerequisites:** basic probability (Markov chains, the Gamma and Poisson distributions,
expectation and variance) and Python. The scheduling problem is AVR-04's, recalled in
Lesson 2; its own course
([Preventive Maintenance Optimization with Genetic Algorithms](https://github.com/GMCavalheri/Preventive-Maintenance-Optimization-with-Genetic-Algorithms))
covers the GA and the exact model from scratch.

| # | lesson | key ideas | the finding | notebook |
|---|---|---|---|---|
| 1 | [Flying hours you can't predict](01-flying-hours-you-cant-predict.md) | fractional programmes, regime-switching hours, closed-form moments, first-passage weeks | a 600 FH interval lasts 29 to 57 weeks (P10 to P90); persistence doubles a year's spread | [01](../../notebooks/01_flying_hours_you_cant_predict.ipynb) |
| 2 | [Planning for the average](02-planning-for-the-average.md) | the FH clock, AVR-04 reproduced exactly, forced tasks as recourse, Jensen | AVR-04's plan costs 4.29 \$M, not the 3.58 it promises | [02](../../notebooks/02_planning_for_the_average.ipynb) |
| 3 | [Planning for many futures](03-planning-for-many-futures.md) | SAA, expected cost, CVaR, worst case, paired held-out tests, optimism | −2.1 % on average, −0.24 \$M in the tail; worst case overfits | [03](../../notebooks/03_planning_for_many_futures.ipynb) |
| 4 | [The exact answer for a sampled future](04-the-exact-answer-for-a-sampled-future.md) | the DAG integer program stays linear, CVaR linearised, bounds | the GA's best of three is within 0.24 % of the proven optimum | [04](../../notebooks/04_the_exact_answer_for_a_sampled_future.ipynb) |
| 5 | [Re-planning as the hours come in](05-re-planning-as-the-hours-come-in.md) | rolling horizons, state, deterministic and stochastic look-ahead | re-planning every 4 weeks saves 8 to 9 %, in every one of 48 years | [05](../../notebooks/05_re_planning_as_the_hours_come_in.ipynb) |
| 6 | [Who owns the hours](06-who-owns-the-hours.md) | shares, allocations, borrowing, owner-level caps | caps calm the fleet's hours, not the aircraft's | [06](../../notebooks/06_who_owns_the_hours.ipynb) |
| 7 | [Uncertain wear on top of uncertain hours](07-uncertain-wear-on-top-of-uncertain-hours.md) | Weibull as Poisson in a multiplier, EJD-01's update, Jensen again | hours, not wear, drive the plan; the mean scale biases cost by 2 % | [07](../../notebooks/07_uncertain_wear_on_top_of_uncertain_hours.ipynb) |
| 8 | [The price of planning for the average](08-the-price-of-planning-for-the-average.md) | EV, WS, RP, EEV, VSS, EVPI, Mak-Morton-Wood, SAA size | the overrun is the price of ignorance: WS ≈ EV | [08](../../notebooks/08_the_price_of_planning_for_the_average.ipynb) |
| 9 | [What is (and isn't) new](09-what-is-and-isnt-new.md) | method, application, measurement; closest work; a novelty statement | the methods are established; the claims are measurements, stated narrowly | [09](../../notebooks/09_what_is_and_isnt_new.ipynb) |

The report is [`docs/report.md`](../report.md); the boundaries of what is modelled are in
[`docs/scope.md`](../scope.md); each module has a theory note in [`docs/`](../).

## Suggested paths

* **Maintenance planner, short on time:** Lessons 1, 2 and 5, then the report.
* **Operations researcher:** Lessons 3, 4 and 8, then the related-work note.
* **Reliability engineer:** Lessons 1, 2 and 7.
