"""Phase 5: the stochastic-programming measures, against brute force on tiny instances."""

import itertools

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pmo.instance import FLEET_TYPES, generate_instance

from fracsched.deterministic_baseline import constant_scenario
from fracsched.exact_saa import solve_saa
from fracsched.problem import from_pmo
from fracsched.scenarios import cost_table, planned_part, scenario_costs
from fracsched.tradeoff import Ladder, ladder_on_sample, mmw_gap, paired_difference
from fracsched.utilization_model import default_model

matrices = st.integers(2, 6).flatmap(
    lambda p: st.integers(2, 8).flatmap(
        lambda s: st.lists(
            st.lists(st.floats(0, 1e6, allow_nan=False), min_size=s, max_size=s),
            min_size=p,
            max_size=p,
        )
    )
)


@settings(max_examples=200, deadline=None)
@given(rows=matrices, which=st.integers(0, 5))
def test_ws_rp_eev_are_ordered_on_any_sample(rows: list[list[float]], which: int) -> None:
    # Wait-and-see picks the best plan per scenario, RP the best single plan, EEV one plan:
    # so WS <= RP <= EEV, i.e. EVPI >= 0 and VSS >= 0, on every sample.
    costs = np.array(rows)
    ladder = ladder_on_sample(costs, which % costs.shape[0], 0.0)
    assert ladder.ws <= ladder.rp + 1e-9
    assert ladder.rp <= ladder.eev + 1e-9
    assert ladder.vss >= -1e-9 and ladder.evpi >= -1e-9


def test_ladder_by_hand() -> None:
    costs = np.array([[1.0, 5.0], [3.0, 2.0]])  # plan 0 is the EV plan
    ladder = ladder_on_sample(costs, 0, 1.5)
    assert (ladder.ev, ladder.eev, ladder.rp, ladder.ws) == (1.5, 3.0, 2.5, 1.5)
    assert (ladder.vss, ladder.evpi, ladder.overrun) == (0.5, 1.0, 1.5)
    assert Ladder(1, 4, 3, 2).vss == 1


@pytest.mark.slow
def test_exact_measures_on_a_tiny_instance() -> None:
    # Oracle: brute force over every feasible plan of a tiny instance gives the exact WS, RP
    # and EEV on a sample; the exact SAA model must reproduce RP and each WS term.
    inst = generate_instance(
        n_aircraft=1,
        types=(FLEET_TYPES[2], FLEET_TYPES[3]),
        horizon=12,
        bays=1,
        blackouts=(),
        seed=3,
    )
    problem = from_pmo(inst)
    u, _ = default_model(annual_mean_fh=1000).sample(np.random.default_rng(3), 6, 1, 12)
    table = cost_table(problem, u)

    def plans(c):
        comp, T = problem.base.components[c], problem.horizon
        ct = problem.base.types[comp.type]
        for r in range(T + 1):
            for ev in itertools.combinations(range(T), r):
                prev, ok = -comp.initial_age, True
                for t in ev:
                    ok &= ct.min_interval <= t - prev <= ct.max_interval
                    prev = t
                if ok and T - prev <= ct.max_interval:
                    yield ev

    feasible = []
    for plan in itertools.product(*(list(plans(c)) for c in range(problem.n_components))):
        planned, _, _, violation = planned_part(problem, plan)
        if violation <= 1e-9:
            feasible.append(scenario_costs(table, planned, plan))
    costs = np.array(feasible)
    ev = solve_saa(problem, cost_table(problem, constant_scenario(problem)))
    planned, *_ = planned_part(problem, ev.schedule)
    ev_costs = scenario_costs(table, planned, ev.schedule)
    ladder = ladder_on_sample(np.vstack([ev_costs, costs]), 0, ev.objective)
    rp = solve_saa(problem, table)
    assert rp.objective == pytest.approx(ladder.rp, abs=1.0)
    ws = [solve_saa(problem, table[..., s : s + 1]).objective for s in range(6)]
    assert np.mean(ws) == pytest.approx(ladder.ws, abs=1.0)
    assert ladder.eev == pytest.approx(ev_costs.mean())


def test_mmw_bound_and_paired_difference() -> None:
    rng = np.random.default_rng(0)
    saa = rng.normal(100.0, 2.0, size=10)
    held = rng.normal(103.0, 10.0, size=4000)
    g = mmw_gap(saa, held, alpha=0.05)
    assert g.gap == pytest.approx(held.mean() - saa.mean())
    assert g.bound > g.gap  # the confidence terms are positive
    assert g.relative_bound == pytest.approx(g.bound / held.mean())
    mean, se = paired_difference(np.array([3.0, 5.0, 7.0]), np.array([1.0, 2.0, 3.0]))
    assert mean == 3.0
    assert se == pytest.approx(np.std([2.0, 3.0, 4.0], ddof=1) / np.sqrt(3))
