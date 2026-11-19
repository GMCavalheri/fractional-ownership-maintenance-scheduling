"""Extra: the GA against the exact sample-average optimum.

    uv run python validation/exact.py          # small instances (byte-reproducible)
    uv run python validation/exact.py --main   # also the main instance (time-limited)

Small instances (AVR-04's 3 aircraft x 3 types x 26 weeks, five seeds): CP-SAT proves the
optimum single-threaded, so ``validation/results/exact.md`` reproduces exactly. The main
instance cannot be proven within a time limit; ``exact_main.md`` reports the best plan and
bound found in ``MAIN_TIME`` seconds with eight threads, which depend on the machine. It is the
one result CI does not byte-compare (see ``run_all.py``).
"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace

from pmo.ga import GAConfig

from fracsched.deterministic_baseline import average_plan
from fracsched.exact_saa import solve_saa
from fracsched.problem import main_problem, small_problem
from fracsched.robust_scenario_scheduling import RobustConfig, plan_objective, run_robust_ga
from fracsched.scenarios import cost_table, evaluate_in_chunks

from common import (
    HELD_OUT_SEED,
    IN_SAMPLE_SEED,
    load_plan,
    scenarios,
    table,
    write_result,
)

INSTANCES = (0, 1, 2, 3, 4)
GA_SEEDS = (0, 1, 2)
N_MEAN = 100  # in-sample scenarios for the expected-cost problem
N_CVAR = 30  # CVaR is much harder exactly: (1 - 0.9) x 30 = 3 tail scenarios
N_HELD_OUT = 2000
TIME_SMALL = 3600.0  # a generous limit: every small solve must prove optimality to reproduce
MAIN_TIME = 300.0


def small_case(i: int) -> dict[str, object]:
    problem = small_problem(i)
    shape = {"n_aircraft": 3, "horizon": 26}
    out: dict[str, object] = {"instance": i}
    average = average_plan(problem, GAConfig(seed=0)).schedule
    for objective, n in (("mean", N_MEAN), ("cvar", N_CVAR)):
        u = scenarios(n, IN_SAMPLE_SEED, replicate=1 + i, **shape)
        table_in = cost_table(problem, u)
        exact = solve_saa(problem, table_in, objective=objective, time_limit=TIME_SMALL)  # type: ignore[arg-type]
        cfg = RobustConfig(objective=objective, generations=400)  # type: ignore[arg-type]
        ga = [
            run_robust_ga(problem, table_in, replace(cfg, seed=s), seeds=[average]).objective
            for s in GA_SEEDS
        ]
        avg_value, _ = plan_objective(problem, table_in, average, cfg)
        out[objective] = {
            "optimal": exact.optimal,
            "exact": exact.objective,
            "ga": ga,
            "average": avg_value,
            "schedule": exact.schedule,
        }
    # Held-out judgement of the exact expected-cost plan and the average plan.
    u_out = scenarios(N_HELD_OUT, HELD_OUT_SEED, replicate=1 + i, **shape)
    mean_plan = out["mean"]["schedule"]  # type: ignore[index]
    ev_exact, ev_avg = evaluate_in_chunks(problem, u_out, [mean_plan, average], chunk=500)
    out["held_out"] = (float(ev_avg.total.mean()), float(ev_exact.total.mean()))
    return out


def pct(a: float, b: float) -> str:
    return f"{100 * (a / b - 1):+.2f} %"


def small() -> None:
    with ProcessPoolExecutor(min(len(INSTANCES), os.cpu_count() or 1)) as ex:
        cases = list(ex.map(small_case, INSTANCES))
    sections = []
    for objective, title, n in (
        ("mean", "Expected cost", N_MEAN),
        ("cvar", "CVaR 90 %", N_CVAR),
    ):
        rows = []
        for case in cases:
            d = case[objective]  # type: ignore[index]
            ga = d["ga"]
            rows.append(
                [
                    case["instance"],
                    "yes" if d["optimal"] else "no",
                    f"{d['exact']:,.0f}",
                    pct(d["average"], d["exact"]),
                    pct(min(ga), d["exact"]),
                    pct(sorted(ga)[1], d["exact"]),
                    pct(max(ga), d["exact"]),
                ]
            )
        sections.append(
            (
                f"{title}: GA gap to the proven optimum ({n} in-sample scenarios)",
                table(
                    [
                        "instance",
                        "proven",
                        "optimum ($)",
                        "plan for the average",
                        "GA best of 3",
                        "GA median",
                        "GA worst",
                    ],
                    rows,
                ),
            )
        )
    rows = []
    for case in cases:
        avg, exact = case["held_out"]  # type: ignore[misc]
        rows.append([case["instance"], f"{avg:,.0f}", f"{exact:,.0f}", pct(exact, avg)])
    sections.append(
        (
            f"Held out ({N_HELD_OUT} scenarios): the exact expected-cost plan against the plan "
            "for the average",
            table(["instance", "plan for the average ($)", "exact SAA plan ($)", "change"], rows),
        )
    )
    write_result(
        "exact",
        "Extra: the GA against the exact sample-average optimum",
        [
            (
                "Setup",
                "AVR-04's small instances (3 aircraft x 3 types x 26 weeks, seeds 0-4) on the "
                "FH clock. CP-SAT (one thread, seed 0) solves the sample-average problem; "
                "'proven' means it proved optimality (arc costs rounded to 10 cents, so the "
                "optimum is exact to within a few dollars). The GA is phase 3's (100 x 400, "
                "warm-started with the plan for the average). Gaps are relative to the "
                "optimum, in sample.",
            ),
            *sections,
        ],
        script="exact",
    )


def main_instance() -> None:
    problem = main_problem()
    table_in = cost_table(problem, scenarios(N_MEAN, IN_SAMPLE_SEED))
    ga_plan = load_plan("robust_mean")
    ga_value, _ = plan_objective(problem, table_in, ga_plan, RobustConfig())
    avg_value, _ = plan_objective(problem, table_in, load_plan("average_ga"), RobustConfig())
    exact = solve_saa(problem, table_in, time_limit=MAIN_TIME, workers=8, hint=ga_plan)
    rows = [
        ["plan for the average", f"{avg_value / 1e6:.3f}", pct(avg_value, exact.bound)],
        ["phase 3 GA (expected cost)", f"{ga_value / 1e6:.3f}", pct(ga_value, exact.bound)],
        ["CP-SAT best plan", f"{exact.objective / 1e6:.3f}", pct(exact.objective, exact.bound)],
        ["CP-SAT lower bound", f"{exact.bound / 1e6:.3f}", "—"],
    ]
    write_result(
        "exact_main",
        "Extra: the main instance against CP-SAT (time-limited, machine-dependent)",
        [
            (
                "Expected cost on the 100 in-sample scenarios",
                f"CP-SAT, {MAIN_TIME:.0f} s, 8 threads, hinted with the GA plan; status "
                f"{exact.status}. Rounded to $1000; the bound and the best plan depend on the "
                "machine and are not byte-compared by CI.\n\n"
                + table(["plan", "expected cost ($M)", "above the bound"], rows),
            )
        ],
        script="exact",
    )


if __name__ == "__main__":
    small()
    if "--main" in sys.argv:
        main_instance()
