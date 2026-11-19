# PLAN.md — EJD-02: Maintenance Scheduling Under Uncertain Utilization (Fractional Ownership)

## Overview
An extension of the Preventive Maintenance Optimization (genetic algorithms) reliability project, reformulated for the irregular, hard-to-predict utilization pattern typical of executive jets — especially under fractional ownership programs, where an aircraft's future flight hours are a matter of uncertain future demand rather than a fixed, predictable schedule.

## Objective
Build a maintenance scheduling optimizer that explicitly accounts for uncertainty in future aircraft utilization, producing schedules that are robust to demand variability rather than optimized for a single assumed usage profile.

## Why This Project
Commercial airline maintenance scheduling (as in the original Preventive Maintenance Optimization project) can assume a fairly predictable flight schedule. Executive jets — particularly under fractional ownership models — do not: an owner's usage can spike or vanish with little notice, so a maintenance plan optimized for average utilization can be badly wrong for any individual aircraft. This is a genuinely distinct optimization problem (stochastic, not deterministic) and a realistic reflection of how business aviation's fractional-ownership operators actually run their aircraft.

## Knowledge Covered
1. **Utilization Model**: model aircraft utilization as a stochastic process (e.g., a distribution of monthly flight hours per aircraft, informed by typical fractional-ownership usage patterns) rather than a fixed schedule.
2. **Deterministic Baseline (Reused)**: reuse the genetic algorithm scheduler from the Preventive Maintenance Optimization project as a baseline, run under a single assumed "average" utilization profile.
3. **Scenario-Based Robust Scheduling**: extend the genetic algorithm to evaluate each candidate schedule's fitness across multiple sampled utilization scenarios (Monte Carlo simulation of possible futures), instead of a single deterministic profile — optimizing for robustness (e.g., minimizing worst-case or expected cost across scenarios) rather than single-scenario optimality.
4. **Dynamic Rescheduling**: implement a rolling-horizon rescheduling capability — as actual utilization is observed and deviates from projections, the scheduler re-optimizes the remaining plan, reflecting how a real fractional-ownership operator would need to adapt in practice.
5. **Trade-off Analysis**: compare the deterministic and robust scheduling approaches under out-of-sample utilization scenarios, quantifying the cost of "planning for the average" vs. the benefit of explicitly planning for uncertainty.

## Prerequisites / Background
- The Preventive Maintenance Optimization (genetic algorithms) project — this project extends its formulation
- Basic probability (utilization as a stochastic process, not a fixed schedule)
- Genetic algorithms and, optionally, stochastic/robust optimization concepts

## Data / Dataset
- **Synthetic utilization scenarios**: monthly flight-hour distributions per aircraft representing fractional-ownership usage (seasonality, demand spikes, idle periods), sampled via Monte Carlo.
- **Synthetic problem instances**: fleet, components, maintenance windows, and intervals reused and extended from AVR-04.
- **Out-of-sample scenarios**: a separate set of generated utilization paths, held out for the trade-off evaluation.
- No real operator data is used.

## Tech Stack
- Python
- DEAP (reused from the Preventive Maintenance Optimization project) for the genetic algorithm core
- NumPy/SciPy for Monte Carlo scenario sampling
- Matplotlib/Plotly for Gantt charts under multiple scenarios, cost distribution comparisons

## Repository Structure
```
fractional-ownership-maintenance-scheduling/
  src/
    utilization_model/
    deterministic_baseline/          # reused/adapted from the GA optimization project
    robust_scenario_scheduling/
    dynamic_rescheduling/
  external/                          # imported GA core from Preventive Maintenance Optimization
  validation/
  notebooks/
  docs/
  tests/
```

## Execution Plan
- [ ] **Phase 1 — Utilization model**: build a stochastic model of aircraft utilization representative of fractional-ownership patterns, validate its statistical properties (mean, variance, plausible extremes).
- [ ] **Phase 2 — Deterministic baseline**: adapt the existing GA scheduler to run under a single average-utilization assumption, establish baseline performance.
- [ ] **Phase 3 — Robust scenario-based scheduling**: extend the GA fitness function to evaluate across multiple Monte Carlo utilization scenarios, implement worst-case and expected-cost objective variants.
- [ ] **Phase 4 — Dynamic rescheduling**: implement rolling-horizon re-optimization as simulated "actual" utilization is revealed over time.
- [ ] **Phase 5 — Trade-off analysis**: run out-of-sample evaluation comparing deterministic vs. robust schedules across many simulated utilization futures.
- [ ] **Phase 6 — Documentation and publishing**: written comparison of approaches, visualizations of schedule robustness and cost trade-offs.

## Validation Strategy
- Deterministic baseline validated for consistency against the original Preventive Maintenance Optimization project's results under equivalent assumptions.
- Robust scheduler evaluated out-of-sample: generate utilization scenarios not used during optimization, measure realized cost/downtime for both deterministic and robust schedules.
- Report the distribution (not just the mean) of outcomes across scenarios, since robustness is precisely about tail behavior.

## Deliverables
- Public repository with a documented stochastic maintenance scheduling optimizer
- A trade-off report quantifying the value of robust vs. deterministic scheduling under utilization uncertainty
- Visualizations: Gantt charts across multiple scenarios, cost distribution comparisons, rolling-horizon adaptation over simulated time

## Portfolio Differentiators
- Extends existing genetic-algorithm optimization expertise into stochastic/robust optimization — a more advanced and less commonly demonstrated skill than deterministic scheduling alone.
- Directly reflects a real operational reality of business aviation's fractional-ownership operators (fractional ownership, unpredictable utilization), making the project concretely relevant rather than generically technical.

## Possible Extensions
- Incorporate real-world fractional ownership program structures (e.g., guaranteed minimum/maximum hours per owner) as additional constraints
- Combine with the Bayesian Small-Fleet Reliability project's failure rate estimates as the risk input driving scheduling priority
