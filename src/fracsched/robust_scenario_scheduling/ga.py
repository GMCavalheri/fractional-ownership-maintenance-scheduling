"""A genetic algorithm whose fitness is a plan's cost across sampled utilization scenarios.

This is AVR-04's GA with a different evaluation. Reused from ``pmo`` unchanged: the encoding
(desired task weeks per component), the decoder that repairs a genotype into a calendar- and
capacity-feasible plan (Lamarckian write-back), block crossover, the mutation operators, the
fixed-interval seeding and the DEAP individual. New here:

* **fitness**: the plan's per-scenario costs from a segment cost table (sample-average
  approximation, SAA), reduced to the expected cost, ``CVaR_α`` or the worst case, plus
  AVR-04's penalty per unit of constraint violation. It is rounded to cents so that a 1-ulp
  difference between CPUs cannot change a tournament;
* **scenario best response**: an extra move, the shortest path of one component against the
  scenario-averaged costs (``best_response``);
* **warm start**: plans passed in ``seeds`` (e.g. the plan for the average) join the initial
  population, so the search can only improve on them in sample (elitism keeps the best).

Note that pmo's own ``reoptimize`` move still runs inside ``pmo.ga.mutate``; on the calendar
instance it is a mean-utilization best response, a reasonable proposal the fitness then
judges.
"""

from __future__ import annotations

import random
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
from deap import algorithms, base, creator, tools
from pmo.decoder import decode
from pmo.ga import Encoding, cx_blocks, initial_population, mutate  # registers the DEAP types
from pmo.instance import Schedule

from fracsched.problem import FleetProblem
from fracsched.risk_measures import cvar
from fracsched.robust_scenario_scheduling.best_response import best_response
from fracsched.scenarios import PENALTY, planned_part, scenario_costs
from fracsched.utilization_model.model import FloatArray

Objective = Literal["mean", "cvar", "worst"]


@dataclass(frozen=True)
class RobustConfig:
    objective: Objective = "mean"
    alpha: float = 0.9  # CVaR level
    pop_size: int = 100
    generations: int = 400
    cx_prob: float = 0.8
    mut_prob: float = 0.6
    tournament: int = 3
    elite: int = 2
    seed_fraction: float = 0.1
    scenario_br_prob: float = 0.5  # share of mutations that are a scenario best response
    penalty: float = PENALTY
    seed: int = 0


@dataclass
class RobustResult:
    schedule: Schedule
    objective: float  # in-sample objective value (no penalty when feasible)
    feasible: bool
    history: list[float] = field(default_factory=list)  # best fitness after each generation
    evaluations: int = 0
    runtime: float = 0.0


def reduce_costs(costs: FloatArray, objective: Objective, alpha: float = 0.9) -> float:
    """The scalar a plan is judged by: expected cost, ``CVaR_α`` or worst case."""
    if objective == "mean":
        return float(np.mean(costs))
    if objective == "cvar":
        return cvar(costs, alpha)
    if objective == "worst":
        return float(np.max(costs))
    raise ValueError(f"unknown objective {objective!r}")


def plan_objective(
    problem: FleetProblem, cost_table: FloatArray, schedule: Schedule, config: RobustConfig
) -> tuple[float, float]:
    """(objective, violation) of a plan, as the GA scores it (before rounding)."""
    planned, _, _, violation = planned_part(problem, schedule)
    costs = scenario_costs(cost_table, planned, schedule)
    return reduce_costs(costs, config.objective, config.alpha), violation


def run_robust_ga(
    problem: FleetProblem,
    cost_table: FloatArray,
    config: RobustConfig | None = None,
    seeds: Sequence[Schedule] = (),
) -> RobustResult:
    """Search for the plan minimising ``config.objective`` over the scenarios of ``cost_table``.

    ``cost_table`` is ``scenarios.cost_table(problem, u)`` for the in-sample scenarios ``u``.
    """
    cfg = config or RobustConfig()
    random.seed(cfg.seed)
    start = time.perf_counter()
    inst = problem.base
    enc = Encoding(inst)
    mean_costs = cost_table.mean(axis=-1)

    best: tuple[float, Schedule, float, float] | None = None  # fitness, plan, objective, viol
    n_evals = 0

    def evaluate_all(individuals: Sequence[Any]) -> None:
        nonlocal best, n_evals
        for ind in individuals:
            if ind.fitness.valid:
                continue
            schedule = decode(inst, enc.split(ind))
            objective, violation = plan_objective(problem, cost_table, schedule, cfg)
            fitness = round(objective + cfg.penalty * violation, 2)
            ind[:] = enc.encode(schedule)
            ind.fitness.values = (fitness,)
            n_evals += 1
            if best is None or fitness < best[0]:
                best = (fitness, schedule, objective, violation)

    def vary(ind: Any) -> tuple[Any]:
        if random.random() < cfg.scenario_br_prob:
            c = random.randrange(len(enc.lengths))
            events = best_response(problem, mean_costs, enc.split(ind), c)
            sl = enc.block(c)
            n = sl.stop - sl.start
            events = events[:n]
            ind[sl] = events + [-1] * (n - len(events))
            return (ind,)
        return mutate(ind, enc)  # type: ignore[no-any-return]

    toolbox = base.Toolbox()
    toolbox.register("mate", cx_blocks, enc=enc)
    toolbox.register("mutate", vary)
    toolbox.register("select", tools.selTournament, tournsize=cfg.tournament)

    pop = initial_population(inst, enc, cfg.pop_size, cfg.seed_fraction, creator.Individual)
    for i, plan in enumerate(seeds):
        pop[len(pop) - 1 - i] = creator.Individual(enc.encode([list(e) for e in plan]))
    evaluate_all(pop)
    assert best is not None
    history = [best[0]]
    for _ in range(cfg.generations):
        elites = [toolbox.clone(ind) for ind in tools.selBest(pop, cfg.elite)]
        offspring = toolbox.select(pop, len(pop) - cfg.elite)
        offspring = algorithms.varAnd(offspring, toolbox, cfg.cx_prob, cfg.mut_prob)
        evaluate_all(offspring)
        pop = elites + offspring
        history.append(best[0])

    _, schedule, objective, violation = best
    return RobustResult(
        schedule=schedule,
        objective=objective,
        feasible=violation <= 1e-9,
        history=history,
        evaluations=n_evals,
        runtime=time.perf_counter() - start,
    )


def run_job(job: tuple[FleetProblem, FloatArray, RobustConfig, Sequence[Schedule]]) -> RobustResult:
    """Build the cost table from scenarios ``u`` and run the GA (for process pools)."""
    from fracsched.scenarios import cost_table

    problem, u, cfg, seeds = job
    return run_robust_ga(problem, cost_table(problem, u), cfg, seeds)


def run_many(
    jobs: Sequence[tuple[FleetProblem, FloatArray, RobustConfig, Sequence[Schedule]]],
    workers: int = 1,
) -> list[RobustResult]:
    """Independent GA runs, in parallel processes when ``workers > 1``; order is kept."""
    if workers <= 1:
        return [run_job(job) for job in jobs]
    from concurrent.futures import ProcessPoolExecutor

    with ProcessPoolExecutor(min(workers, len(jobs) or 1)) as ex:
        return list(ex.map(run_job, jobs))
