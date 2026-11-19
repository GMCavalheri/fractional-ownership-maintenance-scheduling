"""Phase 4: the rolling-horizon simulation, its state tracking and its sub-problems."""

import random

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pmo.decoder import decode
from pmo.ga import random_desired

from fracsched.deterministic_baseline import average_plan, constant_scenario
from fracsched.dynamic_rescheduling import (
    RollingConfig,
    component_state,
    deterministic_policy,
    robust_policy,
    sample_actual,
    simulate,
    static_policy,
)
from fracsched.problem import small_problem
from fracsched.scenarios import evaluate, segment_tables
from fracsched.utilization_model import default_model

SMALL = small_problem()
MODEL = default_model()


def random_plan(seed: int):
    random.seed(seed)
    inst = SMALL.base
    return decode(inst, [random_desired(inst, c) for c in range(inst.n_components)])


def test_static_policy_executes_the_plan_and_scores_it_like_the_evaluator() -> None:
    rng = np.random.default_rng(1)
    actual = sample_actual(MODEL, rng, SMALL.base.n_aircraft, SMALL.horizon)
    plan = random_plan(1)
    out = simulate(SMALL, plan, actual, static_policy, RollingConfig(period=3), rng)
    assert out.executed == plan
    assert out.replans == (SMALL.horizon - 1) // 3
    direct = evaluate(SMALL, segment_tables(SMALL, actual.u[None]), plan)
    assert out.evaluation.total[0] == direct.total[0]


@settings(max_examples=25, deadline=None)
@given(seed=st.integers(0, 10_000), week=st.integers(1, 25), scale=st.floats(0.5, 2.0))
def test_component_state_agrees_with_the_evaluator(seed: int, week: int, scale: float) -> None:
    # Oracle: the evaluator's forced tasks on the same plan and path. Forced weeks before
    # `week` found by the state tracker must be exactly the evaluator's count up to then,
    # and the FH age must be the hours flown since the last renewal.
    rng = np.random.default_rng(seed)
    u, _ = default_model(annual_mean_fh=800 * scale).sample(rng, 1, 3, SMALL.horizon)
    plan = random_plan(seed)
    truncated = tuple(tuple(t for t in events if t < week) for events in plan)
    prefix = np.zeros_like(u)
    prefix[..., :week] = u[..., :week]
    ev = evaluate(SMALL, segment_tables(SMALL, prefix), truncated)
    forced = 0
    for c, comp in enumerate(SMALL.base.components):
        state = component_state(SMALL, c, truncated[c], u[0], week)
        forced += len(state.forced_weeks)
        renewals = sorted([*truncated[c], *state.forced_weeks])
        last = renewals[-1] if renewals else None
        if last is None:
            expected = SMALL.initial_fh[c] + u[0, comp.aircraft, :week].sum()
            assert state.weeks_since_task == week + comp.initial_age
        else:
            expected = u[0, comp.aircraft, last:week].sum()
            assert state.weeks_since_task == week - last
        assert state.fh_since_task == pytest.approx(expected, rel=1e-12, abs=1e-9)
    assert forced == ev.forced_tasks[0]


def test_subproblem_carries_state_and_remaining_capacity() -> None:
    inst = SMALL.base
    weeks = [3] * inst.n_components
    fh = [40.0] * inst.n_components
    used = [1] * len(inst.types)
    sub = SMALL.subproblem(10, weeks, fh, used)
    assert sub.horizon == inst.horizon - 10
    assert [c.initial_age for c in sub.base.components] == weeks
    assert sub.initial_fh == tuple(fh)
    np.testing.assert_array_equal(sub.base.bays, inst.bays[10:])
    np.testing.assert_array_equal(
        sub.base.initial_stock, inst.initial_stock + inst.deliveries[:, :10].sum(axis=1) - 1
    )
    # Parts available at the sub-problem's week t = those of week start + t, minus the used.
    np.testing.assert_array_equal(sub.base.part_availability, inst.part_availability[:, 10:] - 1)
    with pytest.raises(ValueError):
        SMALL.subproblem(0, weeks, fh, used)


def test_failures_split_additively_at_a_replan() -> None:
    # The expected failures of a whole year equal those before week k (a plan cut at k) plus
    # those of the sub-problem from the observed state: H is additive along a segment.
    rng = np.random.default_rng(3)
    u, _ = MODEL.sample(rng, 1, 3, SMALL.horizon)
    plan = random_plan(3)
    k = 12
    full = evaluate(SMALL, segment_tables(SMALL, u), plan)
    before_plan = tuple(tuple(t for t in e if t < k) for e in plan)
    head = np.zeros_like(u)
    head[..., :k] = u[..., :k]
    before = evaluate(SMALL, segment_tables(SMALL, head), before_plan)
    states = [component_state(SMALL, c, before_plan[c], u[0], k) for c in range(9)]
    parts = [0] * len(SMALL.base.types)
    sub = SMALL.subproblem(
        k, [s.weeks_since_task for s in states], [s.fh_since_task for s in states], parts
    )
    rest = tuple(tuple(t - k for t in e if t >= k) for e in plan)
    after = evaluate(sub, segment_tables(sub, u[..., k:]), rest)
    assert full.expected_failures[0] == pytest.approx(
        before.expected_failures[0] + after.expected_failures[0], rel=1e-10
    )
    assert full.forced_tasks[0] == before.forced_tasks[0] + after.forced_tasks[0]


@pytest.mark.slow
def test_replanning_policies_keep_the_past_and_stay_feasible() -> None:
    rng = np.random.default_rng(5)
    actual = sample_actual(MODEL, rng, SMALL.base.n_aircraft, SMALL.horizon)
    plan = average_plan(SMALL).schedule
    cfg = RollingConfig(period=6, n_scenarios=10, pop_size=12, generations=5)
    for policy in (deterministic_policy(cfg), robust_policy(MODEL, cfg)):
        out = simulate(SMALL, plan, actual, policy, cfg, np.random.default_rng(0))
        assert out.evaluation.feasible
        # Weeks before the first re-plan are executed exactly as first planned.
        for done, first in zip(out.executed, plan, strict=True):
            assert [t for t in done if t < 6] == [t for t in first if t < 6]


def test_constant_future_gives_the_at_mean_cost_with_a_static_plan() -> None:
    actual_u = constant_scenario(SMALL)[0]
    from fracsched.dynamic_rescheduling import Actual

    state = MODEL.stationary_state(np.random.default_rng(0), 1, 3)
    actual = Actual(actual_u, tuple(state for _ in range(SMALL.horizon + 1)))
    plan = average_plan(SMALL).schedule
    out = simulate(SMALL, plan, actual, static_policy, RollingConfig(), np.random.default_rng(0))
    at_mean = evaluate(SMALL, segment_tables(SMALL, constant_scenario(SMALL)), plan)
    assert out.evaluation.total[0] == pytest.approx(at_mean.total[0], rel=1e-12)
    assert out.evaluation.forced_tasks[0] == 0
