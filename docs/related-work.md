# Related work, and what is (and isn't) new

This note places the project in the literature. It was written from a targeted search (late
2026) of the operations-research and aviation-maintenance literature, not from a systematic
review; every claim below was checked against the source's published abstract or record. The
last section states, narrowly, what the repository adds, and how the search should be
extended before claiming more.

## 1. The methods: established

* **Stochastic programming and recourse.** Planning before uncertainty resolves, paying for
  corrections afterwards, and the measures EV, EEV, RP, WS, VSS and EVPI are textbook
  material (Birge & Louveaux, 2011, ch. 4).
* **Sample-average approximation.** Replacing an expectation by a sample mean, its
  convergence and its optimism bias (Kleywegt, Shapiro & Homem-de-Mello, 2002), and
  statistical bounds on a candidate's optimality gap (Mak, Morton & Wood, 1999).
* **Risk measures.** CVaR as a coherent risk measure (Artzner et al., 1999) and its linear
  programming form (Rockafellar & Uryasev, 2000).
* **Rolling horizons.** Re-planning on a moving window (Sethi & Sorger, 1991; Chand, Hsu & Sethi,
  2002); deterministic and stochastic look-ahead policies (Powell, 2022).
* **Minimal repair and Weibull wear.** Barlow & Proschan (1965); the power-law process and its
  Bayesian analysis (Rigdon & Basu, 2000). The conjugate Gamma-Poisson model is the one EJD-01
  uses (Atwood et al., 2003).
* **Genetic algorithms and CP-SAT for maintenance scheduling.** This project reuses AVR-04's
  GA and exact model unchanged.

None of these is new, and none is claimed.

## 2. Closest work: maintenance checks under uncertain utilization

A line of work from TU Delft schedules airline *maintenance checks* (A-checks and C-checks)
over several years for a fleet whose daily utilization and check durations are uncertain:

* **Deng, Santos & Curran (2020)** schedule A- and C-checks for a heterogeneous fleet by
  dynamic programming, minimising the unused interval between checks, with complete
  information.
* **Deng & Santos (2022)** extend this to uncertain daily utilization and check durations
  with a look-ahead approximate dynamic programming policy that combines deterministic and
  stochastic forecasts.
* **van der Weide, Deng & Santos (2022)** use a *genetic algorithm* for robust long-term heavy
  check schedules under uncertain check durations and daily utilization (a min-max
  robustness objective), tested by Monte Carlo simulation on an airline fleet of 45 aircraft.

This is the work closest to Phases 3 and 4 here. A robust GA evaluated over sampled
utilization futures, and a look-ahead policy, are **not** new to aircraft maintenance
scheduling. The differences are in the object and the measurement:

| | Deng & Santos; van der Weide et al. | this project |
|---|---|---|
| operator | airline, scheduled flying | fractional-ownership business jets, owner-driven flying |
| what is scheduled | heavy checks (A, C) against FH/FC/calendar limits | component preventive tasks with wear-out failure risk, under hangar, labour and spare-part capacity |
| cost of a late plan | constraint violations, extra slots | forced tasks at an unscheduled premium, plus expected failures (minimal repair) |
| optimality | heuristic (GA, ADP) | GA checked against proven-optimal SAA solutions (CP-SAT) |
| measurement | utilization and check counts | EV, EEV, RP, WS, VSS, EVPI, CVaR, held-out and paired |

## 3. Fractional ownership in operations research

Fractional programmes have a substantial operations-research literature, almost all of it
about *flying* the demand:

* **Keskinocak & Tayur (1998)**, the first study, schedule time-shared jet aircraft of one
  type.
* **Martin, Jones & Keskinocak (2003)** describe the optimisation of on-demand schedules
  (reservations, dispatch, maintenance and crews) at a fractional operator.
* **Hicks et al. (2005)** report an optimisation system for aircraft, crews and facilities at
  a fractional programme.
* **Yang, Karaesmen, Keskinocak & Tayur (2008)** study aircraft and crew scheduling over
  multi-day horizons.
* **Keysan, Nemhauser & Savelsbergh (2010)** plan scheduled maintenance for per-seat,
  on-demand air transportation, linking tactical capacity to daily flight scheduling.
* **Munari & Alvarez (2019)** route on-demand aircraft with maintenance events.
* **Barreto & Abrahão (2021)** route fractional fleets using fault prognostics, noting the
  dynamic nature of fractional demand.

In this literature maintenance enters as events in routing and dispatch, or as capacity for
scheduled checks. The search did not find work that plans a fractional fleet's
*preventive maintenance* against the uncertainty of its owners' flying. That question is the
one this project studies.

## 4. Usage-rate uncertainty in reliability

Reliability and warranty analysis has long treated the *usage rate* as random across
users, as in two-dimensional (age and usage) warranty models (Blischke & Murthy, 1994). This
project's utilization model is a richer, time-varying version of the same idea, calibrated to
a fractional programme's design utilization.

## 5. What is (and isn't) new

**Not new:** every method (SAA, CVaR, GA, CP-SAT, rolling horizons, conjugate Bayes), and
the idea of scheduling aircraft maintenance robustly against uncertain utilization with a GA
or a look-ahead policy (Deng & Santos, 2022; van der Weide et al., 2022).

**What this repository adds, as far as this search found:**

1. **A measurement for fractional-ownership business jets.** On a synthetic fleet with stated
   assumptions, the plan for the average breaks its promise by about 20 %, and the
   stochastic-programming ladder splits that overrun into the cost of variability itself,
   the value of perfect information, and the value of the stochastic solution, with every
   term proven exactly on small instances.
2. **An exactness check on the GA under uncertainty.** AVR-04's DAG model stays exactly linear
   for the sample-average problem, so the GA's gap is measured against proven optima, not
   assumed.
3. **Re-planning against planning once, on the same futures.** Re-planning every four weeks
   recovers about four times what a single robust plan does.
4. **Two negative results.** Owner contracts cap the fleet's hours but barely the aircraft's
   variability, and uncertain wear (EJD-01) barely changes an expected-cost plan, while a
   plug-in of the mean scale biases its cost by 2 %.
5. **An open, reproducible implementation** built by reusing AVR-04 and EJD-01 unchanged,
   with a lesson per phase.

These are measurements on illustrative parameters, not field results. Before claiming more,
the search should be extended systematically: Scopus and Web of Science for "fractional"
or "on-demand" with "maintenance" and "stochastic" or "robust"; the TU Delft line's citing
papers; *Transportation Science*, *EJOR*, *Computers & Operations Research*, *Reliability
Engineering & System Safety* and the *Journal of Air Transport Management* since 2015; and
the business-aviation maintenance trade literature.

## References

* P. Artzner, F. Delbaen, J.-M. Eber and D. Heath, "Coherent measures of risk", *Mathematical
  Finance* 9(3), 1999, pp. 203–228.
* C. L. Atwood et al., *Handbook of Parameter Estimation for Probabilistic Risk Assessment*,
  NUREG/CR-6823, U.S. Nuclear Regulatory Commission, 2003.
* R. E. Barlow and F. Proschan, *Mathematical Theory of Reliability*, Wiley, 1965.
* Barreto and Abrahão, "Aircraft routing problem model for fractional fleets
  using fault prognostics", *Journal of Quality in Maintenance Engineering*, 2021,
  doi:10.1108/JQME-06-2020-0053.
* J. R. Birge and F. Louveaux, *Introduction to Stochastic Programming*, 2nd ed., Springer,
  2011.
* W. R. Blischke and D. N. P. Murthy, *Warranty Cost Analysis*, Marcel Dekker, 1994.
* S. Chand, V. N. Hsu and S. Sethi, "Forecast, solution, and rolling horizons in operations
  management problems: a classified bibliography", *Manufacturing & Service Operations
  Management* 4(1), 2002, pp. 25–43.
* Q. Deng, B. F. Santos and R. Curran, "A practical dynamic programming based methodology for
  aircraft maintenance check scheduling optimization", *European Journal of Operational
  Research* 281(2), 2020, pp. 256–273.
* Q. Deng and B. F. Santos, "Lookahead approximate dynamic programming for stochastic aircraft
  maintenance check scheduling optimization", *European Journal of Operational Research*
  299(3), 2022, pp. 814–833.
* R. Hicks, R. Madrid, C. Milligan, R. Pruneau, M. Kanaley, Y. Dumas, B. Lacroix,
  J. Desrosiers and F. Soumis, "Bombardier Flexjet significantly improves its fractional
  aircraft ownership operations", *Interfaces* 35(1), 2005, pp. 49–60.
* P. Keskinocak and S. Tayur, "Scheduling of time-shared jet aircraft", *Transportation
  Science* 32(3), 1998, pp. 277–294.
* G. Keysan, G. L. Nemhauser and M. W. P. Savelsbergh, "Tactical and operational planning of
  scheduled maintenance for per-seat, on-demand air transportation", *Transportation
  Science* 44(3), 2010, pp. 291–306.
* A. J. Kleywegt, A. Shapiro and T. Homem-de-Mello, "The sample average approximation method
  for stochastic discrete optimization", *SIAM Journal on Optimization* 12(2), 2002,
  pp. 479–502.
* W. K. Mak, D. P. Morton and R. K. Wood, "Monte Carlo bounding techniques for determining
  solution quality in stochastic programs", *Operations Research Letters* 24(1–2), 1999,
  pp. 47–56.
* C. Martin, D. Jones and P. Keskinocak, "Optimizing on-demand aircraft schedules for
  fractional aircraft operators", *Interfaces* 33(5), 2003, pp. 22–35.
* P. Munari and A. Alvarez, "Aircraft routing for on-demand air transportation with service
  upgrade and maintenance events: compact model and case study", *Journal of Air Transport
  Management* 75, 2019, pp. 75–84.
* W. B. Powell, *Reinforcement Learning and Stochastic Optimization*, Wiley, 2022.
* S. E. Rigdon and A. P. Basu, *Statistical Methods for the Reliability of Repairable
  Systems*, Wiley, 2000.
* R. T. Rockafellar and S. Uryasev, "Optimization of conditional value-at-risk", *Journal of
  Risk* 2(3), 2000, pp. 21–41.
* S. Sethi and G. Sorger, "A theory of rolling horizon decision making", *Annals of Operations
  Research* 29, 1991, pp. 387–415.
* T. van der Weide, Q. Deng and B. F. Santos, "Robust long-term aircraft heavy maintenance
  check scheduling optimization under uncertainty", *Computers & Operations Research* 141,
  2022, 105667.
* L. Yang, I. Karaesmen, P. Keskinocak and S. Tayur, "Aircraft and crew scheduling for
  fractional ownership programs", *Annals of Operations Research* 159(1), 2008, pp. 415–431.
