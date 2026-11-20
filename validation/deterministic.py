"""Phase 2: plan for the average with AVR-04's methods, then judge the plans under uncertainty.

    uv run python validation/deterministic.py          # byte-reproducible results
    uv run python validation/deterministic.py --main   # also rerun AVR-04's GA (machine-dependent)

Writes ``validation/results/deterministic.md``, the fixed-interval plans in
``validation/results/plans/`` and ``docs/figures/deterministic_costs.png``.

The plan for the average is AVR-04's GA plan, kept as data in ``plans/average_ga.json``. AVR-04's
GA compares unrounded floating-point costs, so on a different CPU a seed can take a different
search path (it happened on CI for seed 1). Rerunning it is therefore the ``--main`` step,
which writes ``deterministic_ga.md`` (not byte-compared) and re-selects the plan; the default
run only evaluates the committed plan, whose cost at ū is checked against AVR-04's published
value exactly.
"""

from __future__ import annotations

import os
import sys
from dataclasses import replace

import numpy as np
from pmo.evaluate import evaluate as pmo_evaluate
from pmo.ga import GAConfig, run_ga_many

from fracsched import plotting
from fracsched.deterministic_baseline import constant_scenario, fixed_interval_plans
from fracsched.problem import FleetProblem, main_problem
from fracsched.risk_measures import summarize
from fracsched.scenarios import evaluate, evaluate_in_chunks, segment_index, segment_tables

from common import (
    FIGURES,
    HELD_OUT_SEED,
    bounded,
    load_plan,
    save_plan,
    scenarios,
    table,
    write_result,
)

GA_SEEDS = (0, 1, 2)
N_HELD_OUT = 2000
# AVR-04 results/baseline_vs_ga.csv (pmo v1.0.0, GAConfig defaults: 100 x 500 generations)
AVR04_PUBLISHED = {
    "Fixed interval (80% of max)": 4838191.388283321,
    "Fixed interval (cost-optimal)": 4772492.913684425,
    "GA seed 0": 3594965.646085215,
    "GA seed 1": 3587504.3102065343,
    "GA seed 2": 3581598.259084967,
}


AVERAGE_SOURCE = "GA seed 2 (the plan for the average)"
AVR04_PUBLISHED[AVERAGE_SOURCE] = AVR04_PUBLISHED["GA seed 2"]


def rerun_ga(problem: FleetProblem) -> None:
    """Rerun AVR-04's GA (machine-dependent) and keep the seed cheapest at ū as the plan."""
    inst = problem.at_mean()
    workers = min(len(GA_SEEDS), os.cpu_count() or 1)
    runs = run_ga_many([(inst, replace(GAConfig(), seed=s)) for s in GA_SEEDS], workers)
    mean_tables = segment_tables(problem, constant_scenario(problem))
    rows = []
    for s, run in zip(GA_SEEDS, runs, strict=True):
        ours = float(evaluate(problem, mean_tables, run.schedule).total[0])
        theirs = AVR04_PUBLISHED[f"GA seed {s}"]
        rows.append([s, f"{theirs:,.2f}", f"{ours:,.2f}", f"{abs(ours / theirs - 1):.1e}"])
    best = min(range(len(runs)), key=lambda i: pmo_evaluate(inst, runs[i].schedule).total_cost)
    save_plan(
        "average_ga",
        runs[best].schedule,
        source=f"pmo GA seed {GA_SEEDS[best]} on the mean instance",
    )
    write_result(
        "deterministic_ga",
        "Phase 2: AVR-04's GA rerun (machine-dependent)",
        [
            (
                "AVR-04's GA, rerun through `average_plan` (pmo v1.0.0, defaults)",
                "AVR-04's GA compares unrounded floating-point costs, so a seed reproduces its "
                "published plan on the machine that produced it but can take another path on a "
                "different CPU. This file is therefore not byte-compared by CI. The plan for the "
                f"average is the seed cheapest at ū (seed {GA_SEEDS[best]}), saved as data.\n\n"
                + table(["seed", "AVR-04 published ($)", "rerun at ū ($)", "rel. diff"], rows),
            )
        ],
        script="deterministic",
    )


def main() -> None:
    problem = main_problem()
    inst = problem.at_mean()

    # 1. Reproduce AVR-04 on its own terms (the PLAN's consistency check)
    plans = dict(fixed_interval_plans(problem))
    if "--main" in sys.argv:
        rerun_ga(problem)
    plans[AVERAGE_SOURCE] = load_plan("average_ga")
    mean_tables = segment_tables(problem, constant_scenario(problem))
    rows = []
    for name, schedule in plans.items():
        ours = float(evaluate(problem, mean_tables, schedule).total[0])
        theirs = AVR04_PUBLISHED[name]
        rows.append(
            [name, f"{theirs:,.2f}", f"{ours:,.2f}", bounded(abs(ours / theirs - 1), floor=1e-12)]
        )
    reproduce = table(["plan", "AVR-04 published ($)", "this project at ū ($)", "rel. diff"], rows)

    average = plans[AVERAGE_SOURCE]
    judged = {
        "Fixed interval (cost-optimal)": plans["Fixed interval (cost-optimal)"],
        "Fixed interval (80% of max)": plans["Fixed interval (80% of max)"],
        "GA plan for the average": average,
    }
    for name, schedule in judged.items():
        if name.startswith("Fixed"):
            save_plan("fixed_" + ("optimal" if "optimal" in name else "80pct"), schedule)

    # 2. The same plans under uncertain utilization (held-out scenarios)
    u = scenarios(N_HELD_OUT, HELD_OUT_SEED)
    evs = evaluate_in_chunks(problem, u, list(judged.values()), chunk=100)
    rows, breakdown, costs = [], [], {}
    for (name, schedule), ev in zip(judged.items(), evs, strict=True):
        at_mean = evaluate(problem, mean_tables, schedule)
        s = summarize(ev.total)
        costs[name] = ev.total
        rows.append(
            [
                name,
                f"{at_mean.total[0] / 1e6:.3f}",
                f"{s.mean / 1e6:.3f} ± {s.se / 1e6:.3f}",
                f"{s.p10 / 1e6:.3f}",
                f"{s.p90 / 1e6:.3f}",
                f"{s.cvar90 / 1e6:.3f}",
                f"{100 * (s.mean / at_mean.total[0] - 1):.1f} %",
            ]
        )
        breakdown.append(
            [
                name,
                ev.n_tasks,
                ev.n_visits,
                f"{at_mean.expected_failures[0]:.2f}",
                f"{ev.expected_failures.mean():.2f}",
                f"{ev.forced_tasks.mean():.2f}",
                f"{(ev.forced_tasks > 0).mean():.3f}",
                f"{ev.failure_cost.mean() / 1e6 - at_mean.failure_cost[0] / 1e6:+.3f}",
                f"{ev.forced_cost.mean() / 1e6:.3f}",
            ]
        )
    judged_table = table(
        [
            "plan",
            "cost at ū ($M)",
            "expected cost ($M) ± se",
            "P10",
            "P90",
            "CVaR 90 %",
            "expected vs at ū",
        ],
        rows,
    )
    breakdown_table = table(
        [
            "plan",
            "tasks",
            "visits",
            "failures at ū",
            "expected failures",
            "forced tasks",
            "P(any forced)",
            "Δ failure cost ($M)",
            "forced-task cost ($M)",
        ],
        breakdown,
    )

    # 3. Which segments of the GA plan are forced: by the share of the FH limit they use at ū
    cs, starts, ends = segment_index(average, problem.horizon)
    forced_sum = np.zeros(len(cs))
    for lo in range(0, N_HELD_OUT, 100):
        forced_sum += segment_tables(problem, u[lo : lo + 100]).forced[cs, starts, ends].sum(axis=1)
    forced_mean = forced_sum / N_HELD_OUT
    use = []
    for c, a, b in zip(cs, starts, ends, strict=True):
        comp = problem.base.components[c]
        start = a - 1 if a > 0 else -comp.initial_age
        use.append((b - start) / inst.types[comp.type].max_interval)
    use_arr = np.array(use)
    bands = [(0.0, 0.5), (0.5, 0.75), (0.75, 0.9), (0.9, 1.0 + 1e-9)]
    band_rows = []
    for lo, hi in bands:
        m = (use_arr >= lo) & (use_arr < hi)
        band_rows.append(
            [
                f"{lo:.0%} to {min(hi, 1.0):.0%}",
                int(m.sum()),
                f"{forced_mean[m].sum():.2f}",
                f"{forced_mean[m].sum() / max(int(m.sum()), 1):.3f}",
            ]
        )
    segments_table = table(
        ["share of the FH limit used at ū", "segments", "forced tasks a year", "per segment"],
        band_rows,
    )

    write_result(
        "deterministic",
        "Phase 2: planning for the average",
        [
            (
                "Reproducing AVR-04 at the design utilization",
                "At constant utilization ū = 800/52 FH a week the FH problem is AVR-04's "
                "main instance. Its plans, re-scored by this project's scenario evaluator, "
                "must give AVR-04's published costs. The plan for the average is AVR-04's GA "
                "plan for seed 2 (pmo v1.0.0, defaults), kept as data in "
                "`plans/average_ga.json`; rerunning the GA is machine-dependent and reported in "
                "`deterministic_ga.md`.\n\n" + reproduce,
            ),
            (
                "The average plans under uncertain utilization",
                f"{N_HELD_OUT} held-out utilization scenarios (seed {HELD_OUT_SEED}). The "
                "planner's GA plan is AVR-04's seed 2, the lowest cost at ū. Costs in $M "
                "over the 52-week horizon; ± is one Monte Carlo standard error.\n\n" + judged_table,
            ),
            ("Where the extra cost comes from (means over scenarios)", breakdown_table),
            (
                "Which segments of the GA plan are forced",
                "A segment runs from one renewal to the next (or to the horizon). Its use is "
                "its length in weeks over the maximum interval at ū, i.e. the share of the FH "
                "limit it flies in an average future.\n\n" + segments_table,
            ),
        ],
    )
    plotting.cost_distributions(costs).savefig(FIGURES / "deterministic_costs.png", dpi=150)
    print(np.round([c.mean() for c in costs.values()], 0))


if __name__ == "__main__":
    main()
