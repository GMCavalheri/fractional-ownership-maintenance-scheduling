"""Extra: owners' contracts and their hour caps."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fracsched.contracts import Programme, apply_contracts, default_programme
from fracsched.utilization_model import default_model


def test_default_programme_sells_ten_aircraft_in_legal_shares() -> None:
    p = default_programme()
    assert p.aircraft == pytest.approx(10.0)
    assert p.shares.min() == 1 / 16  # 14 CFR 91.1001(b)(10): at least 1/16 of an aircraft
    assert p.allocation.min() == pytest.approx(50.0)  # 1/16 of 800 hours
    assert p.cap.min() == pytest.approx(55.0)  # 10 % borrowing


def test_capping_by_hand() -> None:
    # Two equal owners, no intensity spread, 10 FH a week requested by one aircraft: each
    # owner asks 5 FH a week. With an allocation of 0.5 x 40 = 20 FH and no borrowing each
    # is served for 4 weeks, then refused: the aircraft flies 10, 10, 10, 10, 0, 0.
    p = Programme(np.array([0.5, 0.5]), hours_per_aircraft=40, borrowing=0.0, intensity_cv=0.0)
    u = np.full((1, 1, 6), 10.0)
    out = apply_contracts(u, p, np.random.default_rng(0))
    np.testing.assert_allclose(out.u[0, 0], [10, 10, 10, 10, 0, 0])
    np.testing.assert_allclose(out.owner_hours, [[20, 20]])
    assert out.capped.all()


def test_no_cap_leaves_hours_unchanged() -> None:
    u, _ = default_model().sample(np.random.default_rng(1), 20, 10, 52)
    out = apply_contracts(u, default_programme(borrowing=np.inf), np.random.default_rng(2))
    # The served/requested ratio is 1 up to rounding in the owners' weights.
    np.testing.assert_allclose(out.u, u, rtol=1e-12)
    assert not out.capped.any()


@settings(max_examples=30, deadline=None)
@given(seed=st.integers(0, 10_000), low=st.floats(0.0, 0.5), extra=st.floats(0.0, 0.5))
def test_caps_hold_conserve_hours_and_loosen_with_borrowing(
    seed: int, low: float, extra: float
) -> None:
    u, _ = default_model().sample(np.random.default_rng(seed), 4, 10, 52)
    tight = apply_contracts(u, default_programme(low), np.random.default_rng(seed + 1))
    loose = apply_contracts(u, default_programme(low + extra), np.random.default_rng(seed + 1))
    p = default_programme(low)
    assert np.all(tight.owner_hours <= p.cap + 1e-9)
    assert np.all(tight.u <= u + 1e-12) and np.all(tight.u >= 0)
    assert np.all((tight.served_ratio >= 0) & (tight.served_ratio <= 1 + 1e-12))
    # Hours flown by the aircraft = hours served to owners.
    np.testing.assert_allclose(tight.u.sum(axis=(1, 2)), tight.owner_hours.sum(axis=1), rtol=1e-9)
    # Same owners, more borrowing: never fewer hours.
    assert np.all(loose.owner_hours >= tight.owner_hours - 1e-9)


def test_invalid_programmes_are_rejected() -> None:
    with pytest.raises(ValueError):
        Programme(np.array([0.0, 1.0]))
    with pytest.raises(ValueError):
        Programme(np.array([1.0]), borrowing=-0.1)
