"""Phase 2: plan for the average with AVR-04's GA, then score the plan under uncertainty."""

from fracsched.deterministic_baseline.baseline import (
    average_plan,
    constant_scenario,
    fixed_interval_plans,
)

__all__ = ["average_plan", "constant_scenario", "fixed_interval_plans"]
