# Lesson 9 · What is (and isn't) new

> A portfolio project, like a paper, has to say what it adds. The honest answer usually has
> three layers: the methods (almost always established), the application (sometimes new),
> and the measurements (new by construction, but only as good as their assumptions). This
> lesson walks through the search behind [`related-work.md`](../related-work.md), finds the
> closest work, and writes the narrowest claim the evidence supports.

**Read:** [`docs/related-work.md`](../related-work.md) ·
**Previous:** [Lesson 8](08-the-price-of-planning-for-the-average.md)

## Learning objectives

By the end of this lesson you should be able to:

1. Separate a contribution into method, application and measurement.
2. Search for the closest work deliberately, and compare against it point by point.
3. Write a novelty statement that would survive a reviewer who knows the field.
4. Plan the search you have not yet done, instead of hiding it.

---

## 1. Three kinds of contribution

* **Method.** A new algorithm, model or proof. Nothing in this project is one. SAA, CVaR,
  rolling horizons, conjugate Bayes, genetic algorithms and CP-SAT are all textbook or
  standard tools, and the GA and the exact model are AVR-04's, reused unchanged.
* **Application.** An established method used on a problem where it had not been used, with
  something learned from the use. Here: preventive maintenance of fractional-ownership
  business jets against the uncertainty of their owners' flying.
* **Measurement.** Numbers that answer a question: how much does planning for the average
  cost, and how much does each model recover? New by construction, since nobody ran these
  instances before, but only as credible as the assumptions and the reproducibility behind
  them.

A claim at the wrong level is the commonest failure. "A new robust GA for aircraft
maintenance" would be false here; "a measurement, on stated assumptions, of what planning for
the average costs a fractional fleet" is true.

## 2. Finding the closest work

The search ran three ways:

1. **The method in the domain:** "aircraft maintenance scheduling", "uncertain utilization",
   "robust", "stochastic". It found the closest work. Deng & Santos (2022) schedule airline
   heavy checks under uncertain daily utilization with a look-ahead approximate dynamic
   programming policy. **van der Weide, Deng & Santos (2022) use a genetic algorithm for
   robust heavy-check schedules under uncertain utilization, tested by Monte Carlo.** That
   is close to Lesson 3.
2. **The domain's OR literature:** "fractional ownership" with "scheduling" or "optimization".
   It found a rich literature on flying the demand: scheduling (Keskinocak & Tayur, 1998),
   dispatch systems (Martin et al., 2003; Hicks et al., 2005), crews (Yang et al., 2008),
   maintenance as capacity or routing events (Keysan et al., 2010; Munari & Alvarez, 2019;
   Barreto & Abrahão, 2021). No paper planning preventive maintenance against owners'
   uncertain flying turned up.
3. **The idea elsewhere:** random usage rates in reliability and warranty (Blischke &
   Murthy, 1994), a much older form of the same uncertainty.

The first search changed the project's claim. Without it, Lesson 3 would read as the novelty.
With it, Lesson 3 is a reuse of a known approach, and the contribution moves to what the
known approach did not measure.

## 3. Point by point against the closest work

| | van der Weide, Deng & Santos (2022) | this project |
|---|---|---|
| operator, flying | airline, scheduled | fractional, owner-driven with regimes and a shared demand factor |
| decisions | heavy check dates | component tasks under bays, labour and spare parts |
| late-plan cost | constraint violation, extra slots | forced tasks at a premium, expected failures under wear-out |
| optimality | GA, heuristic | GA checked against proven SAA optima: best of 3 within 0.24 % |
| evaluation | Monte Carlo of the robust schedule | held-out, paired, with VSS, EVPI and CVaR, and a re-planning policy on the same futures |

Every row is a difference in object or measurement, not in method.

## 4. The novelty statement

> As far as a targeted search found, no published study plans a fractional-ownership fleet's
> preventive maintenance against the uncertainty of its owners' flying. On a synthetic
> fleet with stated assumptions, this project measures what planning for the average costs
> (about 20 % over its promise) and splits that overrun with the stochastic-programming
> measures, proven exactly on small instances. It shows that a sample-average plan
> recovers a few percent, a GA reaches it to within a quarter of a percent, and re-planning
> every four weeks recovers about four times as much. It adds two negative results: owner
> contracts tame the fleet's hours but not the aircraft's, and uncertain wear barely changes
> an expected-cost plan. The methods are established; robust GA and look-ahead scheduling
> of aircraft maintenance under uncertain utilization have been studied for airline heavy
> checks (Deng & Santos, 2022; van der Weide, Deng & Santos, 2022).

Note what it does *not* say: that the numbers hold for a real operator (the parameters are
illustrative), that the methods are new, or that the search was exhaustive.

## 5. The search not yet done

A targeted search can miss a paper. Before claiming more, for example in a paper, the plan is:

* **databases:** Scopus and Web of Science, with ("fractional" OR "on-demand" OR "business
  aviation") AND "maintenance" AND ("stochastic" OR "robust" OR "uncertain");
* **forward citations** of Deng & Santos (2022) and van der Weide et al. (2022);
* **journals since 2015:** *Transportation Science*, *EJOR*, *Computers & Operations Research*,
  *Reliability Engineering & System Safety*, *Journal of Air Transport Management*;
* **grey literature:** business-aviation maintenance trade press and fractional operators'
  published practice.

## 6. Worked example: grading three claims

| claim | level | verdict |
|---|---|---|
| "We propose a robust genetic algorithm for maintenance scheduling under uncertain utilization." | method | false: van der Weide et al. (2022) |
| "Re-planning every four weeks saves 9 % for any fractional operator." | measurement | over-generalised: one synthetic fleet, illustrative costs |
| "On a synthetic fractional fleet, re-planning every four weeks recovered about four times what a single robust plan did, on the same 48 futures." | measurement | supported: Lessons 3 and 5, paired, reproducible |

## Exercises

1. Which single result in this project would be most worth checking against real operator
   data, and what data would you need?
2. Rewrite the novelty statement for a reader who only cares about business aviation, in
   three sentences.
3. A reviewer says: "Lesson 4's exact model is AVR-04's model with a different cost table,
   so it is not a contribution." Agree or disagree?
4. Name a result in this project that would weaken the novelty claim if it changed sign
   under a different utilization model, and explain why.

### Solutions

1. Lesson 5's re-planning gain, because it drives the practical recommendation. You would
   need a fractional fleet's weekly hours per tail, its component task records (planned and
   unscheduled) and its re-planning rhythm, to calibrate the utilization model and the
   unscheduled premium.
2. For example: "A maintenance plan built for a fractional jet's average hours costs about a
   fifth more than it promises, because owners' flying is bursty. Planning against many
   possible years recovers a few percent; re-planning every month recovers several times
   more. Caps on owners' hours do not fix it, because they limit the fleet, not the tail."
3. Agree that it is not a methodological contribution. It is the observation that the model
   stays *exactly* linear under uncertainty, and the use of that to measure the GA's gap.
   That is a contribution to the measurement, not to the method.
4. The ranking of re-planning above a static robust plan (Lesson 5). If utilization were much
   less persistent (short regimes), a re-plan would learn little from the present, and the
   value of re-planning would shrink toward that of a static plan. The claim depends on
   owners' flying having memory, which is the model's central assumption.

## References

See [`docs/related-work.md`](../related-work.md) for the full list. The two papers that set the
boundary of the claim:

* Q. Deng and B. F. Santos, "Lookahead approximate dynamic programming for stochastic aircraft
  maintenance check scheduling optimization", *European Journal of Operational Research*
  299(3), 2022, pp. 814–833.
* T. van der Weide, Q. Deng and B. F. Santos, "Robust long-term aircraft heavy maintenance
  check scheduling optimization under uncertainty", *Computers & Operations Research* 141,
  2022, 105667.
