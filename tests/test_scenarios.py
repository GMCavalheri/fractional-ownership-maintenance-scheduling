"""Phase 2: the FH-clock problem and the scenario evaluator against AVR-04 and a naive simulator."""

import math
import random
from dataclasses import replace

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pmo.decoder import decode
from pmo.evaluate import evaluate as pmo_evaluate
from pmo.ga import random_desired
from pmo.instance import FLEET_TYPES, default_instance, generate_instance, small_instance

from fracsched.deterministic_baseline import constant_scenario, fixed_interval_plans
from fracsched.problem import (
    FleetProblem,
    design_fh_per_week,
    from_pmo,
    main_problem,
    small_problem,
)
from fracsched.scenarios import (
    cost_table,
    cumulative_hours,
    evaluate,
    evaluate_in_chunks,
    planned_part,
    scenario_costs,
    segment_tables,
)
from fracsched.utilization_model import default_model

MAIN = main_problem()
SMALL = small_problem()


def simulate(problem: FleetProblem, schedule, u_path):
    """Naive oracle: step every component week by week through one scenario.

    ``u_path`` is ``(A, T)``. Returns (expected failures, forced tasks) summed over components.
    """
    T = problem.horizon
    failures = forced = 0.0
    for c, comp in enumerate(problem.base.components):
        k = comp.type
        limit = problem.fh_limit[k] * (1 + problem.limit_tolerance)
        H = lambda x, k=k: float(problem.cumulative_hazard(k, np.array(x)))  # noqa: E731
        age = base = problem.initial_fh[c]
        planned = set(schedule[c])
        for t in range(T):
            if t in planned:
                failures += H(age) - H(base)
                age = base = 0.0
            if age + u_path[comp.aircraft, t] > limit:
                failures += H(age) - H(base)
                age = base = 0.0
                forced += 1
            age += u_path[comp.aircraft, t]
        failures += H(age) - H(base)
    return failures, forced


def test_at_mean_is_avr04_main_instance() -> None:
    # The deterministic baseline must be AVR-04's own instance, field for field.
    ours, avr04 = MAIN.at_mean(), default_instance(0)
    assert ours.types == avr04.types
    assert ours.components == avr04.components
    for field in ("bays", "labor", "initial_stock", "deliveries"):
        np.testing.assert_array_equal(getattr(ours, field), getattr(avr04, field))
    assert SMALL.at_mean().types == small_instance(0).types


def test_fh_parameters_are_avr04_weeks_at_design_utilization() -> None:
    u = design_fh_per_week()
    assert u == pytest.approx(800 / 52, rel=1e-15)
    avr04 = default_instance(0)
    for k, ct in enumerate(avr04.types):
        assert MAIN.eta_fh[k] == pytest.approx(ct.eta * u, rel=1e-15)
        assert MAIN.fh_limit[k] == pytest.approx(ct.max_interval * u, rel=1e-15)
        # calendar limit 1.5x the old maximum (scheduling_parameters.csv)
        assert MAIN.base.types[k].max_interval == math.ceil(1.5 * ct.max_interval)


def test_constant_utilization_reproduces_avr04_evaluator_on_its_baselines() -> None:
    # With every aircraft at exactly ū, the FH clock is AVR-04's week clock times ū: the
    # scenario evaluator must give pmo.evaluate's numbers and never force a task.
    tables = segment_tables(MAIN, constant_scenario(MAIN))
    avr04 = default_instance(0)
    published = {  # AVR-04 results/summary.md (pmo v1.0.0)
        "Fixed interval (80% of max)": 4_838_191.388283321,
        "Fixed interval (cost-optimal)": 4_772_492.913684425,
    }
    for name, schedule in fixed_interval_plans(MAIN).items():
        ev = evaluate(MAIN, tables, schedule)
        ref = pmo_evaluate(avr04, schedule)
        assert ev.forced_tasks[0] == 0
        assert ev.expected_failures[0] == pytest.approx(ref.expected_failures, rel=1e-12)
        assert ev.total[0] == pytest.approx(ref.total_cost, rel=1e-12)
        assert ev.total[0] == pytest.approx(published[name], rel=1e-12)


@settings(max_examples=25, deadline=None)
@given(seed=st.integers(0, 10_000))
def test_constant_utilization_matches_avr04_on_random_plans(seed: int) -> None:
    random.seed(seed)
    inst = SMALL.at_mean()
    schedule = decode(inst, [random_desired(inst, c) for c in range(inst.n_components)])
    ev = evaluate(SMALL, segment_tables(SMALL, constant_scenario(SMALL)), schedule)
    ref = pmo_evaluate(inst, schedule)
    assert ev.forced_tasks[0] == 0
    assert ev.failure_cost[0] == pytest.approx(ref.failure_cost, rel=1e-12, abs=1e-6)


@settings(max_examples=30, deadline=None)
@given(seed=st.integers(0, 10_000), scale=st.floats(0.3, 2.5))
def test_tables_match_a_week_by_week_simulation(seed: int, scale: float) -> None:
    # Oracle: the naive simulator above, on random plans and random (scaled) utilization,
    # which makes forced tasks common at high scale.
    rng = np.random.default_rng(seed)
    random.seed(seed)
    model = default_model(annual_mean_fh=800 * scale)
    u, _ = model.sample(rng, 3, SMALL.base.n_aircraft, SMALL.horizon)
    inst = SMALL.base
    schedule = decode(inst, [random_desired(inst, c) for c in range(inst.n_components)])
    ev = evaluate(SMALL, segment_tables(SMALL, u), schedule)
    for s in range(3):
        failures, forced = simulate(SMALL, schedule, u[s])
        assert ev.expected_failures[s] == pytest.approx(failures, rel=1e-10, abs=1e-12)
        assert ev.forced_tasks[s] == forced


def test_forced_tasks_by_hand() -> None:
    # One aircraft, one brake (AVR-04: max 20 weeks -> FH limit 20ū), new at week 0, no plan,
    # flown at 2ū: the limit is reached after 10 weeks. Forced in week t when
    # 2ū (t + 1) > 20ū, i.e. t = 10, then again at t = 20 and 30 on a 40-week horizon.
    inst = generate_instance(
        n_aircraft=1, types=(FLEET_TYPES[3],), horizon=40, blackouts=(), age_fraction=0.0
    )
    problem = from_pmo(inst)
    u = np.full((1, 1, 40), 2 * problem.mean_fh)
    ev = evaluate(problem, segment_tables(problem, u), ((),))
    assert ev.forced_tasks[0] == 3
    # Four segments of 10 weeks (20ū FH each) from age 0: 4 H(20ū) expected failures.
    one = float(problem.cumulative_hazard(0, np.array(20 * problem.mean_fh)))
    assert ev.expected_failures[0] == pytest.approx(4 * one, rel=1e-12)
    cost = 3 * problem.forced_task_cost(0) + 4 * one * problem.failure_cost(0)
    assert ev.total[0] == pytest.approx(cost, rel=1e-12)
    # A planned task in week 8 restarts the clock: forced at 18, 28, 38.
    ev = evaluate(problem, segment_tables(problem, u), ((8,),))
    assert ev.forced_tasks[0] == 3


def test_fast_paths_agree_with_the_full_evaluator() -> None:
    u, _ = default_model().sample(np.random.default_rng(4), 30, 10, 52)
    tables = segment_tables(MAIN, u)
    costs = cost_table(MAIN, u)
    np.testing.assert_array_equal(costs, tables.costs(MAIN))
    for schedule in fixed_interval_plans(MAIN).values():
        ev = evaluate(MAIN, tables, schedule)
        planned, *_ = planned_part(MAIN, schedule)
        np.testing.assert_allclose(scenario_costs(costs, planned, schedule), ev.total, rtol=1e-12)
    plans = list(fixed_interval_plans(MAIN).values())
    chunked = evaluate_in_chunks(MAIN, u, plans, chunk=7)
    for schedule, ev in zip(plans, chunked, strict=True):
        np.testing.assert_allclose(ev.total, evaluate(MAIN, tables, schedule).total, rtol=1e-12)
        assert ev.feasible


def test_cumulative_hours() -> None:
    u = np.arange(6, dtype=float).reshape(1, 2, 3)
    np.testing.assert_array_equal(cumulative_hours(u)[0], [[0, 0, 1, 3], [0, 3, 7, 12]])


def test_invalid_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        segment_tables(SMALL, np.zeros((1, 2, SMALL.horizon)))
    with pytest.raises(ValueError):
        segment_tables(SMALL, np.full((1, 3, SMALL.horizon), 1e6))
    with pytest.raises(ValueError):
        from_pmo(small_instance(0), calendar_limit_factor=0.5)
    with pytest.raises(ValueError):
        replace(SMALL, beta=(2.0,))
    with pytest.raises(ValueError):
        replace(SMALL, initial_fh=(0.0,))
    with pytest.raises(ValueError):
        replace(SMALL, mean_fh=0.0)
    with pytest.raises(ValueError):
        replace(SMALL, initial_fh=tuple(1e9 for _ in SMALL.initial_fh))


@pytest.mark.slow
def test_average_plan_is_avr04_ga() -> None:
    # Same instance, same seed: AVR-04's GA must return the same plan through our wrapper.
    from pmo.ga import GAConfig, run_ga

    from fracsched.deterministic_baseline import average_plan

    cfg = GAConfig(pop_size=20, generations=8, seed=3)
    ours = average_plan(SMALL, cfg)
    theirs = run_ga(small_instance(0), cfg)
    assert ours.schedule == theirs.schedule
    assert ours.objective == theirs.objective
