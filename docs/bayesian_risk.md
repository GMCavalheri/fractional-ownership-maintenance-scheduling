# `bayesian_risk`: a posterior wear multiplier from EJD-01

**Lesson:** [7 · Uncertain wear on top of uncertain hours](lessons/07-uncertain-wear-on-top-of-uncertain-hours.md) ·
**Code:** [`src/fracsched/bayesian_risk/`](../src/fracsched/bayesian_risk/)

## Model

With a known Weibull shape, $\eta = \eta_{\text{ref}}\lambda^{-1/\beta}$ and expected failures are
linear in $\lambda$, so a history's failures are Poisson in $\lambda E$ with $E$ the reference
exposure. A Gamma prior updates conjugately with EJD-01's `GammaRate.update` (exposure passed
in thousands, as EJD-01 counts FH). A future's multiplier scales its failure tables.

## API

| function | purpose |
|---|---|
| `load_wear_priors()` | priors from [`wear_parameters.csv`](../src/fracsched/data/wear_parameters.csv) |
| `posterior(prior, failures, exposure)` | EJD-01's update |
| `mean_eta_factor`, `plug_in_multiplier` | $E[\lambda^{-1/\beta}]$ and the multiplier implied by the mean scale |
| `sample_multipliers`, `scale_failures` | wear uncertainty in the tables |

## Verification

The posterior against numerical integration; $E[\eta]$ against quadrature; Jensen's bound
(Hypothesis); failures scaling per type with forced tasks unchanged
([`tests/test_bayesian_risk.py`](../tests/test_bayesian_risk.py)).
