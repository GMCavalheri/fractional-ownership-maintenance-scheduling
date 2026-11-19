"""Phase 3: plans optimised across sampled futures, judged on futures they never saw.

    uv run python validation/robust.py

Needs ``validation/deterministic.py`` first (the plan for the average warm-starts the search).
Writes ``validation/results/robust.md``, plans in ``validation/results/plans/`` and two figures.
About five minutes on four cores.
"""

from __future__ import annotations

import os

import numpy as np

from fracsched import plotting
from fracsched.problem import main_problem
from fracsched.risk_measures import summarize
from fracsched.robust_scenario_scheduling import (
    RobustConfig,
    plan_objective,
    reduce_costs,
    run_many,
)
from fracsched.scenarios import cost_table, evaluate_in_chunks

from common import (
    FIGURES,
    HELD_OUT_SEED,
    IN_SAMPLE_SEED,
    load_plan,
    save_plan,
    scenarios,
    table,
    write_result,
)

N_IN_SAMPLE = 100
N_HELD_OUT = 2000
GA_SEEDS = (0, 1, 2)
OBJECTIVES = {
    "expected cost": RobustConfig(objective="mean"),
    "CVaR 90 %": RobustConfig(objective="cvar", alpha=0.9),
    "worst case": RobustConfig(objective="worst"),
}
KEYS = {"expected cost": "robust_mean", "CVaR 90 %": "robust_cvar", "worst case": "robust_worst"}


def m(x: float) -> str:
    return f"{x / 1e6:.3f}"


def main() -> None:
    problem = main_problem()
    average = load_plan("average_ga")
    u_in = scenarios(N_IN_SAMPLE, IN_SAMPLE_SEED)
    costs_in = cost_table(problem, u_in)

    jobs = [
        (problem, u_in, RobustConfig(**{**cfg.__dict__, "seed": s}), (average,))
        for cfg in OBJECTIVES.values()
        for s in GA_SEEDS
    ]
    results = run_many(jobs, workers=os.cpu_count() or 1)

    # The planner keeps, per objective, the run with the best in-sample value.
    runs_rows, plans, histories = [], {"plan for the average": average}, {}
    for i, (name, cfg) in enumerate(OBJECTIVES.items()):
        mine = results[i * len(GA_SEEDS) : (i + 1) * len(GA_SEEDS)]
        avg_value, _ = plan_objective(problem, costs_in, average, cfg)
        for s, r in zip(GA_SEEDS, mine, strict=True):
            runs_rows.append(
                [
                    name,
                    s,
                    m(avg_value),
                    m(r.objective),
                    f"{100 * (r.objective / avg_value - 1):.2f} %",
                ]
            )
        best = min(mine, key=lambda r: r.objective)
        plans[f"optimised for {name}"] = best.schedule
        histories[name] = [h / 1e6 for h in best.history]
        save_plan(KEYS[name], best.schedule, objective=cfg.objective, n_in_sample=N_IN_SAMPLE)
    runs_table = table(
        ["objective", "GA seed", "plan for the average ($M)", "GA plan ($M)", "change"], runs_rows
    )

    # Judge every plan on held-out futures (the same 2000 as phase 2).
    u_out = scenarios(N_HELD_OUT, HELD_OUT_SEED)
    evs = dict(
        zip(plans, evaluate_in_chunks(problem, u_out, list(plans.values()), 100), strict=True)
    )
    base_total = evs["plan for the average"].total
    rows, ops, paired = [], [], []
    for name, ev in evs.items():
        s = summarize(ev.total)
        rows.append([name, f"{m(s.mean)} ± {m(s.se)}", m(s.p50), m(s.p90), m(s.cvar90), m(s.max)])
        ops.append(
            [
                name,
                ev.n_tasks,
                ev.n_visits,
                m(ev.planned_cost),
                f"{ev.expected_failures.mean():.2f}",
                f"{ev.forced_tasks.mean():.2f}",
                m(float(ev.forced_cost.mean())),
            ]
        )
        if name != "plan for the average":
            d = ev.total - base_total
            sd = summarize(d)
            paired.append(
                [
                    name,
                    f"{m(sd.mean)} ± {m(sd.se)}",
                    f"{100 * sd.mean / base_total.mean():.2f} %",
                    m(s.cvar90 - summarize(base_total).cvar90),
                    f"{(d < 0).mean():.3f}",
                ]
            )
    held_table = table(["plan", "mean ($M) ± se", "median", "P90", "CVaR 90 %", "worst"], rows)
    ops_table = table(
        [
            "plan",
            "tasks",
            "visits",
            "planned cost ($M)",
            "expected failures",
            "forced tasks",
            "forced cost ($M)",
        ],
        ops,
    )
    paired_table = table(
        [
            "plan",
            "mean change ($M) ± se",
            "mean change",
            "CVaR 90 % change ($M)",
            "share of futures cheaper",
        ],
        paired,
    )

    # In-sample optimism. The in-sample set is itself a sample, so compare improvements over
    # the plan for the average, measured in sample and out of sample.
    optimism = []
    for name, cfg in OBJECTIVES.items():
        plan = plans[f"optimised for {name}"]
        avg_in, _ = plan_objective(problem, costs_in, average, cfg)
        plan_in, _ = plan_objective(problem, costs_in, plan, cfg)
        avg_out = reduce_costs(base_total, cfg.objective, cfg.alpha)
        plan_out = reduce_costs(evs[f"optimised for {name}"].total, cfg.objective, cfg.alpha)
        optimism.append(
            [
                name,
                m(avg_in),
                m(plan_in),
                f"{100 * (plan_in / avg_in - 1):+.2f} %",
                m(avg_out),
                m(plan_out),
                f"{100 * (plan_out / avg_out - 1):+.2f} %",
            ]
        )
    optimism_table = table(
        [
            "objective",
            "average plan, in sample",
            "GA plan, in sample",
            "improvement in sample",
            "average plan, held out",
            "GA plan, held out",
            "improvement held out",
        ],
        optimism,
    )

    write_result(
        "robust",
        "Phase 3: scenario-based robust scheduling",
        [
            (
                "Search",
                f"{N_IN_SAMPLE} in-sample utilization scenarios (seed {IN_SAMPLE_SEED}). The GA "
                "(pmo operators + scenario best response, 100 x 400 generations) is warm-started "
                "with the plan for the average; three seeds per objective, values in sample.\n\n"
                + runs_table,
            ),
            (
                "Held-out futures",
                f"{N_HELD_OUT} scenarios never used by any optimiser (seed {HELD_OUT_SEED}), "
                "$M over 52 weeks.\n\n" + held_table,
            ),
            (
                "Against the plan for the average, scenario by scenario",
                "Paired differences on the same held-out futures (negative = cheaper).\n\n"
                + paired_table,
            ),
            ("What the plans do differently (means over held-out futures)", ops_table),
            (
                "In-sample optimism",
                "Each plan's own objective, as a change from the plan for the average, measured "
                f"on the {N_IN_SAMPLE} scenarios it was optimised on and on the {N_HELD_OUT} "
                "held-out ones.\n\n" + optimism_table,
            ),
        ],
    )
    plotting.cost_distributions(
        {k: evs[k].total for k in ("plan for the average", "optimised for CVaR 90 %")}
    ).savefig(FIGURES / "robust_costs.png", dpi=150)
    gens = list(range(len(next(iter(histories.values())))))
    plotting.lines(
        gens, histories, xlabel="generation", ylabel="best in-sample objective ($M)"
    ).savefig(FIGURES / "robust_convergence.png", dpi=150)
    print(np.round([summarize(e.total).mean for e in evs.values()]))


if __name__ == "__main__":
    main()
