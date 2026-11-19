# Scope and modelling boundaries

This repository is an **operations research methodology and software** project. It asks one
question: how should preventive maintenance be scheduled when an aircraft's future flight
hours are uncertain, and what does it cost to plan for the average instead? Everything in it
is meant to be safe to publish, and these rules keep it that way.

## What is modelled

* **Synthetic utilization.** Weekly flight hours of a fleet of generic midsize business jets
  under a fractional-ownership programme (never a named type or operator). The model and its
  parameters are in
  [`utilization_parameters.csv`](../src/fracsched/data/utilization_parameters.csv). One value
  is calibrated to public figures: the 800 hours a year that programmes sell per aircraft.
  Every other value is an **illustrative assumption**, labelled as such and chosen to be of a
  plausible order of magnitude.
* **Synthetic fleets, components and costs.** These are reused and extended from AVR-04's
  instances. Component lives, task intervals, costs and capacities are illustrative. None is
  field data of any operator, manufacturer or programme, and none should be read as one.
* **Public methodology.** Stochastic programming and sample-average approximation, risk
  measures (CVaR), genetic algorithms and constraint programming, all from the public
  literature (the related-work note gives the sources). Programme structures (share sizes and
  hours) come from public programme descriptions and are used generically.

## What is not modelled

* No real operator's utilization, maintenance programme, task intervals or costs.
* No airworthiness judgement. A schedule here is an optimisation result on illustrative
  numbers, not a maintenance programme. Real task intervals come from approved maintenance
  data and are never exceeded.
* No claim about any manufacturer's products, or about any fractional programme's operations
  beyond its public description.

## Why this is the right boundary

The question (how much the uncertainty in flight hours costs a maintenance plan, and how much
a scenario-based plan recovers) depends on the shape of that uncertainty and on the cost
structure. It does not depend on whose aircraft the numbers come from. Synthetic scenarios
with known distributions answer it better than one operator's history could. They can be
sampled as often as needed, and a plan can be tested on futures it was not optimised on.
