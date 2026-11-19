"""The exact sample-average model against joint brute force and AVR-04's own exact model."""

import itertools

import numpy as np
import pytest
from pmo.exact import solve_exact
from pmo.instance import FLEET_TYPES, generate_instance, small_instance

from fracsched.deterministic_baseline import constant_scenario
from fracsched.exact_saa import solve_saa
from fracsched.problem import from_pmo
from fracsched.risk_measures import cvar
from fracsched.scenarios import cost_table, planned_part, scenario_costs
from fracsched.utilization_model import default_model

# Arc costs are scaled by 10 and rounded: each arc is off by at most 5 cents.
ROUNDING = 1.0  # $, far above (number of arcs in a plan) x 0.05


def component_plans(problem, c):
    inst = problem.base
    comp = inst.components[c]
    ct = inst.types[comp.type]
    T = inst.horizon
    for r in range(0, T + 1):
        for events in itertools.combinations(range(T), r):
            prev, ok = -comp.initial_age, True
            for t in events:
                ok &= ct.min_interval <= t - prev <= ct.max_interval
                prev = t
            if ok and T - prev <= ct.max_interval:
                yield events


def brute_force(problem, table, reduce):
    """Oracle: every joint plan that is calendar- and capacity-feasible, scored exactly."""
    per_component = [list(component_plans(problem, c)) for c in range(problem.n_components)]
    best = np.inf
    for plan in itertools.product(*per_component):
        planned, _, _, violation = planned_part(problem, plan)
        if violation > 1e-9:
            continue
        best = min(best, reduce(scenario_costs(table, planned, plan)))
    return best


def tiny(n_aircraft, types, horizon, bays, seed):
    inst = generate_instance(
        n_aircraft=n_aircraft, types=types, horizon=horizon, bays=bays, blackouts=(), seed=seed
    )
    problem = from_pmo(inst)
    u, _ = default_model(annual_mean_fh=1000).sample(
        np.random.default_rng(seed), 10, n_aircraft, horizon
    )
    return problem, cost_table(problem, u)


CASES = [
    # one aircraft, two components sharing visits
    (1, (FLEET_TYPES[2], FLEET_TYPES[3]), 12, 1, 3),
    # two aircraft, one component each, one hangar bay
    (2, (FLEET_TYPES[3],), 14, 1, 4),
]


@pytest.mark.slow
@pytest.mark.parametrize("case", CASES)
def test_expected_cost_optimum_matches_brute_force(case) -> None:
    problem, table = tiny(*case)
    result = solve_saa(problem, table, objective="mean")
    assert result.optimal
    best = brute_force(problem, table, np.mean)
    assert result.objective == pytest.approx(best, abs=ROUNDING)
    assert result.bound <= best + ROUNDING
    hinted = solve_saa(problem, table, objective="mean", hint=result.schedule)
    assert hinted.objective == pytest.approx(result.objective, abs=ROUNDING)
    assert abs(hinted.gap) < 1e-5


@pytest.mark.slow
@pytest.mark.parametrize("case", CASES)
def test_cvar_optimum_matches_brute_force(case) -> None:
    problem, table = tiny(*case)
    result = solve_saa(problem, table, objective="cvar", alpha=0.8)
    assert result.optimal
    best = brute_force(problem, table, lambda x: cvar(x, 0.8))
    assert result.objective == pytest.approx(best, abs=ROUNDING)


@pytest.mark.slow
def test_constant_utilization_matches_avr04_exact_model() -> None:
    # With calendar limits equal to AVR-04's (factor 1) and every aircraft at ū, the SAA
    # problem is AVR-04's problem; both exact models must prove the same optimum.
    inst = small_instance(0)
    problem = from_pmo(inst, calendar_limit_factor=1.0)
    table = cost_table(problem, constant_scenario(problem))
    ours = solve_saa(problem, table, time_limit=120)
    theirs = solve_exact(inst, time_limit=120, workers=1)
    assert ours.optimal and theirs.optimal
    assert ours.objective == pytest.approx(theirs.objective, abs=ROUNDING)


def test_cvar_needs_an_integer_tail() -> None:
    problem, table = tiny(*CASES[0])
    with pytest.raises(ValueError):
        solve_saa(problem, table, objective="cvar", alpha=0.95)  # (1 - 0.95) x 10 = 0.5
