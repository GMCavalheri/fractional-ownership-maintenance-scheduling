"""Extra (PLAN extension 2): wear-rate uncertainty from EJD-01's conjugate model."""

from fracsched.bayesian_risk.wear import (
    WearPrior,
    load_wear_priors,
    mean_eta_factor,
    plug_in_multiplier,
    posterior,
    reference_failures_per_year,
    sample_multipliers,
    scale_failures,
)

__all__ = [
    "WearPrior",
    "load_wear_priors",
    "mean_eta_factor",
    "plug_in_multiplier",
    "posterior",
    "reference_failures_per_year",
    "sample_multipliers",
    "scale_failures",
]
