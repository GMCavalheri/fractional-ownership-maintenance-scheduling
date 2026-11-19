"""Phase 2: plan for the average with AVR-04's methods, then judge the plans under uncertainty.

    uv run python validation/deterministic.py

Writes ``validation/results/deterministic.md``, the plans in ``validation/results/plans/`` and
``docs/figures/deterministic_costs.png``. About four minutes (three AVR-04 GA runs in parallel).
"""

from __future__ import annotations

import os
from dataclasses import replace

import numpy as np
from pmo.evaluate import evaluate as pmo_evaluate
from pmo.ga import GAConfig, run_ga_many

from fracsched import plotting
from fracsched.deterministic_baseline import constant_scenario, fixed_interval_plans
from fracsched.problem import main_problem
from fracsched.risk_measures import summarize
from fracsched.scenarios import evaluate, evaluate_in_chunks, segment_index, segment_tables

from common import (
    FIGURES,
    HELD_OUT_SEED,
    bounded,
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


def main() -> None:
    problem = main_problem()
    inst = problem.at_mean()

    # 1. Reproduce AVR-04 on its own terms (the PLAN's consistency check)
    plans = dict(fixed_interval_plans(problem))
    workers = min(len(GA_SEEDS), os.cpu_count() or 1)
    runs = run_ga_many([(inst, replace(GAConfig(), seed=s)) for s in GA_SEEDS], workers)
    for s, run in zip(GA_SEEDS, runs, strict=True):
        plans[f"GA seed {s}"] = run.schedule
    mean_tables = segment_tables(problem, constant_scenario(problem))
    rows = []
    for name, schedule in plans.items():
        ours = float(evaluate(problem, mean_tables, schedule).total[0])
        theirs = AVR04_PUBLISHED[name]
        rows.append(
            [name, f"{theirs:,.2f}", f"{ours:,.2f}", bounded(abs(ours / theirs - 1), floor=1e-12)]
        )
    reproduce = table(["plan", "AVR-04 published ($)", "this project at ū ($)", "rel. diff"], rows)

    # The planner's choice: the GA run with the lowest cost at mean utilization.
    best_seed = min(GA_SEEDS, key=lambda s: pmo_evaluate(inst, plans[f"GA seed {s}"]).total_cost)
    average = plans[f"GA seed {best_seed}"]
    save_plan("average_ga", average, source=f"pmo GA seed {best_seed} on the mean instance")
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
                "must give AVR-04's published costs; the GA rows rerun AVR-04's GA "
                f"(pmo v1.0.0, defaults, seeds {GA_SEEDS}) through `average_plan`.\n\n" + reproduce,
            ),
            (
                "The average plans under uncertain utilization",
                f"{N_HELD_OUT} held-out utilization scenarios (seed {HELD_OUT_SEED}). The "
                f"planner's GA plan is seed {best_seed}, the lowest cost at ū. Costs in $M "
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
