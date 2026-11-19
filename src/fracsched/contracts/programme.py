"""Owner contracts: whose hours the fleet flies, and the cap on them.

In a fractional programme an owner buys a share of an aircraft together with an annual
allocation of hours (1/16 = 50 hours), but flies whichever aircraft the operator dispatches
from the pooled fleet. Contracts therefore act on the *fleet's* hours, not on any one tail:

* every owner-year draws an intensity ``w_i`` (Gamma, mean 1): how much of the allocation that
  owner wants to fly this year;
* each week the fleet's requested hours ``Q_t`` (the utilization model's fleet total) are split
  among owners in proportion to ``share_i x w_i``;
* an owner who has flown the allocation plus the borrowing allowance is refused further hours
  this year (the hours are flown, if at all, by someone else's fleet);
* the hours served each week are spread over the aircraft in proportion to their own requested
  hours, so every aircraft's week shrinks by the same served/requested ratio.

The caps bind for heavy owners in busy years, so they trim the fleet's upper tail. They do not
touch an aircraft's own variability (idle spells, spikes), which is what drives its components'
due weeks. That contrast is the point of Lesson 6.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from importlib import resources

import numpy as np
from numpy.typing import NDArray

from fracsched.utilization_model.model import FloatArray


def load_contract_parameters() -> dict[str, float]:
    path = resources.files("fracsched") / "data" / "contract_parameters.csv"
    with path.open() as f:
        return {row["parameter"]: float(row["value"]) for row in csv.DictReader(f)}


@dataclass(frozen=True)
class Programme:
    shares: FloatArray  # (N,) each owner's share of one aircraft
    hours_per_aircraft: float = 800.0
    borrowing: float = 0.1  # extra fraction of the allocation an owner may fly (inf = no cap)
    intensity_cv: float = 0.25

    def __post_init__(self) -> None:
        if np.any(self.shares <= 0) or self.hours_per_aircraft <= 0:
            raise ValueError("shares and hours must be positive")
        if self.borrowing < 0 or self.intensity_cv < 0:
            raise ValueError("borrowing and intensity_cv must be >= 0")

    @property
    def n_owners(self) -> int:
        return int(self.shares.size)

    @property
    def aircraft(self) -> float:
        """Whole aircraft the shares add up to."""
        return float(self.shares.sum())

    @property
    def allocation(self) -> FloatArray:
        """Each owner's annual hours."""
        return np.asarray(self.shares * self.hours_per_aircraft, dtype=np.float64)

    @property
    def cap(self) -> FloatArray:
        """Each owner's maximum hours this year, borrowing included."""
        return np.asarray(self.allocation * (1 + self.borrowing), dtype=np.float64)


def default_programme(borrowing: float | None = None) -> Programme:
    p = load_contract_parameters()
    shares = np.concatenate(
        [
            np.full(int(p["owners_quarter_share"]), 1 / 4),
            np.full(int(p["owners_eighth_share"]), 1 / 8),
            np.full(int(p["owners_sixteenth_share"]), 1 / 16),
        ]
    )
    return Programme(
        shares=shares,
        hours_per_aircraft=p["hours_per_aircraft"],
        borrowing=p["borrowing"] if borrowing is None else borrowing,
        intensity_cv=p["intensity_cv"],
    )


@dataclass(frozen=True)
class CappedHours:
    u: FloatArray  # (S, A, T) hours actually flown by each aircraft
    served_ratio: FloatArray  # (S, T) served / requested fleet hours each week
    owner_hours: FloatArray  # (S, N) hours each owner flew this year
    capped: NDArray[np.bool_]  # (S, N) True where the owner reached the cap


def apply_contracts(u: FloatArray, programme: Programme, rng: np.random.Generator) -> CappedHours:
    """Cut the requested hours ``u`` (``(S, A, T)``) to what owners' contracts allow."""
    S = u.shape[0]
    Q = u.sum(axis=1)  # (S, T) requested fleet hours
    if programme.intensity_cv > 0:
        k = 1 / programme.intensity_cv**2
        w = rng.gamma(k, 1 / k, size=(S, programme.n_owners))
    else:
        w = np.ones((S, programme.n_owners))
    weights = programme.shares * w
    weights = weights / weights.sum(axis=1, keepdims=True)
    requested = Q[:, None, :] * weights[:, :, None]  # (S, N, T)
    # Weeks are served in order: an owner is served until its flown hours reach the cap.
    served = np.empty_like(requested)
    flown = np.zeros(requested.shape[:2])
    for t in range(requested.shape[2]):
        served[:, :, t] = np.minimum(requested[:, :, t], np.maximum(programme.cap - flown, 0.0))
        flown += served[:, :, t]
    total = served.sum(axis=1)
    ratio = np.divide(total, Q, out=np.ones_like(Q), where=Q > 0)
    return CappedHours(
        u=np.asarray(u * ratio[:, None, :], dtype=np.float64),
        served_ratio=np.asarray(ratio, dtype=np.float64),
        owner_hours=flown,
        capped=flown >= programme.cap * (1 - 1e-12),
    )
