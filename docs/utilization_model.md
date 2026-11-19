# `utilization_model`: weekly flight hours of a fractional fleet

**Lesson:** [1 · Flying hours you can't predict](lessons/01-flying-hours-you-cant-predict.md) ·
**Code:** [`src/fracsched/utilization_model/`](../src/fracsched/utilization_model/)

## Model

$u_{a,t} = m_t D_t X_{a,t}$, capped at 70 FH: a seasonal multiplier (mean 1), a fleet-wide
lognormal AR(1) demand factor ($E[D] = 1$), and each aircraft's Markov-modulated Gamma hours
(regimes idle, normal, spike). The regime means are scaled so the stationary mean is 800 FH a
year (the hours a fractional programme sells per aircraft). Parameters and their basis are in
[`utilization_parameters.csv`](../src/fracsched/data/utilization_parameters.csv).

## API

| function | purpose |
|---|---|
| `default_model(annual_mean_fh, capped)` | the model of the parameter table |
| `UtilizationModel.sample(rng, S, A, T, start_week, state)` | paths `(S, A, T)` and the final state; conditional on `state` if given |
| `stationary_distribution`, `seasonality` | building blocks |
| `x_second_moment`, `d_second_moment`, `weekly_covariance`, `annual_sd`, `fleet_annual_sd`, `autocorrelation`, `cross_correlation` | closed-form moments (uncapped model) |
| `weeks_to_reach`, `hours_to_weeks_quantiles` | first-passage weeks to an FH limit |

## Failure modes

Invalid transition matrices, non-positive means or shapes, $|\phi| \ge 1$ and a non-unit
season mean raise `ValueError`. The closed forms describe the uncapped model; the cap binds
in about 0.3 % of aircraft-weeks.

## Verification

The stationary distribution against $P^{2000}$; lagged moments against enumeration of every
regime path; the demand factor against Gauss-Hermite quadrature; weekly, annual,
cross-aircraft and fleet moments against Monte Carlo within 4 standard errors; Hypothesis
properties of conditional sampling
([`tests/test_utilization_model.py`](../tests/test_utilization_model.py)).
