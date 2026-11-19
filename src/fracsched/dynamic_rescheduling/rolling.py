"""Rolling-horizon re-planning as the actual flight hours are revealed.

A real operator does not keep a year's plan fixed. Every ``period`` weeks it looks at what
happened (which tasks were done, which were forced, how many hours each aircraft flew, which
demand regime each aircraft is in) and re-plans the rest of the year. Tasks decided at an
epoch are committed for the next ``period`` weeks (the planning freeze), then the cycle
repeats. The simulation:

1. starts from a full-year plan (the plan for the average, or a robust plan);
2. at each epoch ``k = period, 2 period, …`` rebuilds the state of every component from the
   actual hours and the tasks executed so far (``component_state``), forms the remaining
   problem (``FleetProblem.subproblem``) and asks a *policy* for a new plan of weeks ``k…T-1``;
3. executes each week's tasks from the plan in force that week;
4. scores the executed schedule on the actual future with the scenario evaluator.

Three policies: ``static`` (keep the plan), ``deterministic`` (re-plan for the average: one
scenario at ``ū``) and ``robust`` (re-plan on scenarios sampled *conditionally* on the
observed regimes and demand). Both re-planning policies run the phase 3 GA, warm-started with
the rest of the current plan.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from pmo.instance import Schedule

from fracsched.deterministic_baseline import constant_scenario
from fracsched.problem import FleetProblem
from fracsched.robust_scenario_scheduling import RobustConfig, run_robust_ga
from fracsched.scenarios import ScenarioEvaluation, cost_table, evaluate, segment_tables
from fracsched.utilization_model.model import FloatArray, UtilizationModel, UtilizationState

Policy = Callable[[FleetProblem, int, UtilizationState, Schedule, np.random.Generator], Schedule]


@dataclass(frozen=True)
class RollingConfig:
    period: int = 4  # weeks between re-plans; the tasks of those weeks are committed
    n_scenarios: int = 30  # conditional scenarios per robust re-plan
    pop_size: int = 40
    generations: int = 50
    seed: int = 0

    def ga(self) -> RobustConfig:
        return RobustConfig(
            objective="mean", pop_size=self.pop_size, generations=self.generations, seed=self.seed
        )


@dataclass(frozen=True)
class ComponentState:
    weeks_since_task: int
    fh_since_task: float
    forced_weeks: tuple[int, ...]


def component_state(
    problem: FleetProblem, c: int, planned: Sequence[int], u: FloatArray, week: int
) -> ComponentState:
    """State of component ``c`` at the start of ``week``, from week 0's state.

    ``planned`` are the planned tasks executed before ``week``; ``u`` is the actual
    ``(A, T)`` utilization. Forced tasks follow the evaluator's rule (``scenarios``).
    """
    comp = problem.base.components[c]
    limit = problem.fh_limit[comp.type] * (1 + problem.limit_tolerance)
    age = problem.initial_fh[c]
    last = -comp.initial_age
    done = set(planned)
    forced = []
    for t in range(week):
        if t in done:
            age, last = 0.0, t
        hours = float(u[comp.aircraft, t])
        if age + hours > limit:
            age, last = 0.0, t
            forced.append(t)
        age += hours
    return ComponentState(week - last, age, tuple(forced))


def static_policy(
    sub: FleetProblem, week: int, state: UtilizationState, rest: Schedule, rng: np.random.Generator
) -> Schedule:
    """Keep the plan."""
    return rest


def deterministic_policy(config: RollingConfig) -> Policy:
    """Re-plan the rest of the year for the average: one scenario where every aircraft flies ū."""

    def policy(
        sub: FleetProblem,
        week: int,
        state: UtilizationState,
        rest: Schedule,
        rng: np.random.Generator,
    ) -> Schedule:
        table = cost_table(sub, constant_scenario(sub))
        return run_robust_ga(sub, table, config.ga(), seeds=[rest]).schedule

    return policy


def robust_policy(model: UtilizationModel, config: RollingConfig) -> Policy:
    """Re-plan on futures sampled conditionally on the observed regimes and demand."""

    def policy(
        sub: FleetProblem,
        week: int,
        state: UtilizationState,
        rest: Schedule,
        rng: np.random.Generator,
    ) -> Schedule:
        u, _ = model.sample(
            rng,
            config.n_scenarios,
            sub.base.n_aircraft,
            sub.horizon,
            start_week=week,
            state=state,
        )
        table = cost_table(sub, u)
        return run_robust_ga(sub, table, config.ga(), seeds=[rest]).schedule

    return policy


@dataclass(frozen=True)
class Actual:
    """One actual future: weekly hours ``(A, T)`` and the model state at every week's start."""

    u: FloatArray
    states: tuple[UtilizationState, ...]  # states[k] = state observed at the start of week k


def sample_actual(
    model: UtilizationModel, rng: np.random.Generator, n_aircraft: int, horizon: int
) -> Actual:
    """Draw an actual future week by week, recording the state the operator observes."""
    state = model.stationary_state(rng, 1, n_aircraft)
    states, weeks = [state], []
    for t in range(horizon):
        u, state = model.sample(rng, 1, n_aircraft, 1, start_week=t, state=state)
        weeks.append(u[0, :, 0])
        states.append(state)
    return Actual(np.stack(weeks, axis=1), tuple(states))


@dataclass(frozen=True)
class RollingOutcome:
    executed: Schedule  # the planned tasks actually carried out
    evaluation: ScenarioEvaluation  # scored on the actual future (one scenario)
    replans: int


def simulate(
    problem: FleetProblem,
    initial_plan: Schedule,
    actual: Actual,
    policy: Policy,
    config: RollingConfig,
    rng: np.random.Generator,
) -> RollingOutcome:
    """Run one year: re-plan every ``config.period`` weeks with ``policy``, execute, score."""
    T, C = problem.horizon, problem.n_components
    plan = [tuple(e) for e in initial_plan]
    executed: list[list[int]] = [[] for _ in range(C)]
    replans = 0
    for k in range(0, T, config.period):
        if k > 0:
            states = [component_state(problem, c, executed[c], actual.u, k) for c in range(C)]
            parts = np.zeros(len(problem.base.types), dtype=np.int64)
            for c, comp in enumerate(problem.base.components):
                parts[comp.type] += len(executed[c])
            sub = problem.subproblem(
                k,
                [s.weeks_since_task for s in states],
                [s.fh_since_task for s in states],
                parts.tolist(),
            )
            rest = tuple(tuple(t - k for t in events if t >= k) for events in plan)
            new = policy(sub, k, actual.states[k], rest, rng)
            plan = [
                tuple(t for t in old if t < k) + tuple(t + k for t in events)
                for old, events in zip(plan, new, strict=True)
            ]
            replans += 1
        for c in range(C):
            executed[c].extend(t for t in plan[c] if k <= t < k + config.period)
    schedule = tuple(tuple(e) for e in executed)
    tables = segment_tables(problem, actual.u[None])
    return RollingOutcome(schedule, evaluate(problem, tables, schedule), replans)
