"""Phase 3: the scenario GA and its best-response move, against brute force."""

import itertools

import numpy as np
import pytest
from pmo.instance import FLEET_TYPES, generate_instance

from fracsched.deterministic_baseline import average_plan
from fracsched.problem import from_pmo, small_problem
from fracsched.risk_measures import cvar
from fracsched.robust_scenario_scheduling import (
    RobustConfig,
    best_response,
    plan_objective,
    reduce_costs,
    run_many,
    run_robust_ga,
)
from fracsched.scenarios import cost_table, evaluate, segment_tables
from fracsched.utilization_model import default_model

SMALL = small_problem()


def tiny():
    """Two aircraft, two component types, 14 weeks: small enough to enumerate every plan."""
    inst = generate_instance(
        n_aircraft=2, types=(FLEET_TYPES[2], FLEET_TYPES[3]), horizon=14, blackouts=(), seed=1
    )
    problem = from_pmo(inst)
    u, _ = default_model(annual_mean_fh=1100).sample(np.random.default_rng(2), 25, 2, 14)
    return problem, u


def all_plans(problem, c):
    """Every task-week set of component c that respects its calendar windows."""
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
                yield list(events)


def test_best_response_is_the_brute_force_optimum() -> None:
    # Oracle: enumerate every calendar-feasible plan of one component, others fixed, and
    # take the cheapest by expected segment costs plus task and (unshared) visit costs.
    problem, u = tiny()
    mean_costs = cost_table(problem, u).mean(axis=-1)
    inst = problem.base
    others = [[3, 9], [5], [], [7]]
    for c in range(inst.n_components):
        plan = [list(p) for p in others]
        comp = inst.components[c]
        ct = inst.types[comp.type]
        busy = {
            t
            for o, ev in enumerate(plan)
            if o != c and inst.components[o].aircraft == comp.aircraft
            for t in ev
        }

        def cost(events, c=c, ct=ct, busy=busy):
            total, start = 0.0, 0
            for t in events:
                total += mean_costs[c, start, t] + ct.cost_pm + (0 if t in busy else 20_000)
                start = t + 1
            return total + mean_costs[c, start, inst.horizon]

        best = min(cost(p) for p in all_plans(problem, c))
        found = best_response(problem, mean_costs, plan, c)
        assert cost(found) == pytest.approx(best, rel=1e-12)


def test_reduce_costs() -> None:
    x = np.array([3.0, 1.0, 7.0, 5.0])
    assert reduce_costs(x, "mean") == 4.0
    assert reduce_costs(x, "worst") == 7.0
    assert reduce_costs(x, "cvar", 0.5) == cvar(x, 0.5) == 6.0
    with pytest.raises(ValueError):
        reduce_costs(x, "median")  # type: ignore[arg-type]


def test_plan_objective_is_the_evaluator_reduced() -> None:
    problem, u = tiny()
    plan = ((3, 9), (5,), (), (7,))
    ev = evaluate(problem, segment_tables(problem, u), plan)
    costs = cost_table(problem, u)
    for objective, expected in [
        ("mean", ev.total.mean()),
        ("cvar", cvar(ev.total, 0.9)),
        ("worst", ev.total.max()),
    ]:
        value, violation = plan_objective(problem, costs, plan, RobustConfig(objective=objective))
        assert value == pytest.approx(expected, rel=1e-12)
        assert violation == ev.violation


@pytest.mark.slow
def test_ga_improves_on_its_seed_and_is_reproducible() -> None:
    u, _ = default_model().sample(np.random.default_rng(7), 30, 3, SMALL.horizon)
    costs = cost_table(SMALL, u)
    seed_plan = average_plan(SMALL).schedule
    for objective in ("mean", "cvar", "worst"):
        cfg = RobustConfig(objective=objective, pop_size=30, generations=25, seed=1)
        result = run_robust_ga(SMALL, costs, cfg, seeds=[seed_plan])
        start, _ = plan_objective(SMALL, costs, seed_plan, cfg)
        assert result.feasible
        assert result.objective <= start + 0.01  # elitism keeps the seed (fitness in cents)
        assert all(a >= b for a, b in itertools.pairwise(result.history))
        again = run_robust_ga(SMALL, costs, cfg, seeds=[seed_plan])
        assert again.schedule == result.schedule


@pytest.mark.slow
def test_parallel_runs_equal_serial_runs() -> None:
    u, _ = default_model().sample(np.random.default_rng(8), 10, 3, SMALL.horizon)
    jobs = [(SMALL, u, RobustConfig(pop_size=12, generations=4, seed=s), ()) for s in (0, 1)]
    serial = run_many(jobs, workers=1)
    parallel = run_many(jobs, workers=2)
    assert [r.schedule for r in serial] == [r.schedule for r in parallel]
