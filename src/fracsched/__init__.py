"""Maintenance scheduling under uncertain utilization.

A business jet's future flight hours are uncertain, most of all in a fractional-ownership
fleet, where an owner's use can spike or vanish with little notice. Components wear with flight
hours, so a maintenance plan built for the average utilization can be wrong for every
individual aircraft. ``fracsched`` models utilization as a stochastic process, evaluates each
candidate plan across Monte Carlo scenarios (expected cost, CVaR and worst case), searches with
the genetic algorithm of ``pmo`` and checks it against an exact sample-average model,
re-plans on a rolling horizon as hours are observed, and measures out of sample what planning
for the average costs.
"""

from importlib.metadata import version

__version__ = version("fracsched")
