"""Phase 4: re-planning every four weeks as the actual hours are revealed.

    uv run python validation/rolling.py

Needs the plans of ``deterministic.py`` and ``robust.py``. Simulates ``N_FUTURES`` actual
years and four policies on each. Writes ``validation/results/rolling.md`` and two figures.
About eight minutes on four cores.
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from fracsched import plotting
from fracsched.dynamic_rescheduling import (
    RollingConfig,
    deterministic_policy,
    robust_policy,
    sample_actual,
    simulate,
    static_policy,
)
from fracsched.problem import main_problem
from fracsched.risk_measures import summarize
from fracsched.utilization_model import default_model

from common import FIGURES, HELD_OUT_SEED, load_plan, table, write_result

N_FUTURES = 48
CONFIG = RollingConfig()  # re-plan every 4 weeks; 30 conditional scenarios; GA 40 x 50
POLICIES = (
    "keep the plan for the average",
    "keep the robust plan",
    "re-plan for the average",
    "re-plan on conditional scenarios",
)


def future(i: int) -> dict[str, object]:
    problem = main_problem()
    model = default_model()
    average, robust = load_plan("average_ga"), load_plan("robust_mean")
    seq = np.random.SeedSequence([HELD_OUT_SEED, 4, i])
    actual = sample_actual(model, np.random.default_rng(seq.spawn(1)[0]), 10, 52)
    runs = {
        POLICIES[0]: (average, static_policy),
        POLICIES[1]: (robust, static_policy),
        POLICIES[2]: (average, deterministic_policy(CONFIG)),
        POLICIES[3]: (robust, robust_policy(model, CONFIG)),
    }
    out: dict[str, object] = {"actual": actual}
    for name, (plan, policy) in runs.items():
        rng = np.random.default_rng(np.random.SeedSequence([HELD_OUT_SEED, 5, i]))
        outcome = simulate(problem, plan, actual, policy, CONFIG, rng)
        ev = outcome.evaluation
        out[name] = {
            "total": float(ev.total[0]),
            "forced": float(ev.forced_tasks[0]),
            "failures": float(ev.expected_failures[0]),
            "tasks": ev.n_tasks,
            "visits": ev.n_visits,
            "outcome": outcome,
        }
    return out


def m(x: float) -> str:
    return f"{x / 1e6:.3f}"


def main() -> None:
    with ProcessPoolExecutor(os.cpu_count() or 1) as ex:
        results = list(ex.map(future, range(N_FUTURES)))
    totals = {p: np.array([r[p]["total"] for r in results]) for p in POLICIES}  # type: ignore[index]
    base = totals[POLICIES[0]]
    rows, paired = [], []
    for p in POLICIES:
        s = summarize(totals[p])
        mean = lambda key, p=p: np.mean([r[p][key] for r in results])  # type: ignore[index]  # noqa: E731
        rows.append(
            [
                p,
                f"{m(s.mean)} ± {m(s.se)}",
                m(s.p90),
                f"{mean('tasks'):.1f}",
                f"{mean('visits'):.1f}",
                f"{mean('forced'):.2f}",
                f"{mean('failures'):.2f}",
            ]
        )
        if p != POLICIES[0]:
            d = summarize(totals[p] - base)
            paired.append(
                [
                    p,
                    f"{m(d.mean)} ± {m(d.se)}",
                    f"{100 * d.mean / base.mean():+.2f} %",
                    f"{(totals[p] < base).mean():.3f}",
                ]
            )
    policy_table = table(
        [
            "policy",
            "realised cost ($M) ± se",
            "P90",
            "tasks",
            "visits",
            "forced tasks",
            "expected failures",
        ],
        rows,
    )
    paired_table = table(["policy", "change ($M) ± se", "change", "share of years cheaper"], paired)
    # The value of re-planning itself, holding the plan type fixed.
    d_avg = summarize(totals[POLICIES[2]] - totals[POLICIES[0]])
    d_rob = summarize(totals[POLICIES[3]] - totals[POLICIES[1]])
    d_scen = summarize(totals[POLICIES[3]] - totals[POLICIES[2]])
    split = table(
        ["comparison", "change ($M) ± se"],
        [
            [
                "re-planning, starting from the plan for the average",
                f"{m(d_avg.mean)} ± {m(d_avg.se)}",
            ],
            ["re-planning, starting from the robust plan", f"{m(d_rob.mean)} ± {m(d_rob.se)}"],
            [
                "re-plan on conditional scenarios instead of for the average",
                f"{m(d_scen.mean)} ± {m(d_scen.se)}",
            ],
        ],
    )

    write_result(
        "rolling",
        "Phase 4: rolling-horizon re-planning",
        [
            (
                "Setup",
                f"{N_FUTURES} actual years drawn week by week from the utilization model "
                f"(seed {HELD_OUT_SEED}, stream 4). Re-plan every {CONFIG.period} weeks; tasks "
                "decided at an epoch are committed until the next. Re-planning runs the phase 3 "
                f"GA ({CONFIG.pop_size} x {CONFIG.generations}, warm-started with the current "
                "plan) on one scenario at the design rate, or on "
                f"{CONFIG.n_scenarios} scenarios sampled conditionally on the observed regimes "
                "and demand factor. Realised cost = planned tasks and visits + forced tasks + "
                "expected failures given the realised ages.",
            ),
            ("Realised cost by policy", policy_table),
            ("Against keeping the plan for the average, year by year", paired_table),
            ("Where the gain comes from (paired)", split),
        ],
    )
    labels = ["keep average", "keep robust", "re-plan average", "re-plan scenarios"]
    plotting.bars(
        labels,
        [totals[p].mean() / 1e6 for p in POLICIES],
        [summarize(totals[p]).se / 1e6 for p in POLICIES],
        ylabel="realised cost ($M), mean ± se",
    ).savefig(FIGURES / "rolling_policies.png", dpi=150)

    # Adaptation over time: the component whose plan moved most in the first future.
    first = results[0]
    outcome = first[POLICIES[3]]["outcome"]  # type: ignore[index]
    problem = main_problem()
    moved = [len({tuple(p[c]) for p in outcome.plans}) for c in range(problem.n_components)]
    c = int(np.argmax(moved))
    comp = problem.base.components[c]
    from fracsched.dynamic_rescheduling import component_state

    state = component_state(problem, c, outcome.executed[c], first["actual"].u, 52)  # type: ignore[attr-defined]
    epochs = list(range(0, 52, CONFIG.period))
    plotting.replans(
        [p[c] for p in outcome.plans],
        epochs,
        list(outcome.executed[c]),
        list(state.forced_weeks),
        first["actual"].u[comp.aircraft],  # type: ignore[attr-defined]
        problem.mean_fh,
    ).savefig(FIGURES / "rolling_adaptation.png", dpi=150)


if __name__ == "__main__":
    main()
