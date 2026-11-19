"""Phase 5: what planning for the average costs, and what each model recovers, out of sample.

    uv run python validation/tradeoff.py

Needs the plans of ``deterministic.py`` and ``robust.py``. Writes
``validation/results/tradeoff.md`` and figures in ``docs/figures/``.

* Small instances: the exact ladder EV ≤ … with every value proven by CP-SAT (one thread).
* Main instance: 10 000 held-out futures for the headline distributions; the GA for RP and
  for wait-and-see (an upper estimate of WS); the SAA sample size.
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace

import numpy as np

from fracsched import plotting
from fracsched.deterministic_baseline import constant_scenario
from fracsched.dynamic_rescheduling import component_state
from fracsched.exact_saa import solve_saa
from fracsched.problem import main_problem, small_problem
from fracsched.risk_measures import summarize
from fracsched.robust_scenario_scheduling import RobustConfig, run_robust_ga
from fracsched.scenarios import cost_table, evaluate_in_chunks, planned_part, scenario_costs
from fracsched.tradeoff import mmw_gap, paired_difference

from common import (
    FIGURES,
    HELD_OUT_SEED,
    IN_SAMPLE_SEED,
    load_plan,
    scenarios,
    table,
    write_result,
)

INSTANCES = (0, 1, 2, 3, 4)
N_SAA = 100  # scenarios per SAA problem
M_SAA = 10  # independent SAA replications for the Mak-Morton-Wood bound
N_WS_SMALL = 100  # futures solved with perfect foresight, small instances
N_EVAL_SMALL = 2000
N_HELD_OUT = 10_000
N_WS_MAIN = 48
SAA_SIZES = (10, 25, 50, 100, 200)
GA_SEEDS = (0, 1, 2)
SHAPE_SMALL = {"n_aircraft": 3, "horizon": 26}


def m(x: float) -> str:
    return f"{x / 1e6:.3f}"


def k(x: float) -> str:
    return f"{x / 1e3:.1f}"


# ------------------------------------------------------------------- small, exact


def small_ladder(i: int) -> dict[str, object]:
    problem = small_problem(i)
    ev = solve_saa(problem, cost_table(problem, constant_scenario(problem)), time_limit=3600)
    saa = []
    for r in range(M_SAA):
        u = scenarios(N_SAA, IN_SAMPLE_SEED, replicate=20 + 10 * i + r, **SHAPE_SMALL)
        saa.append(solve_saa(problem, cost_table(problem, u), time_limit=3600))
    u_eval = scenarios(N_EVAL_SMALL, HELD_OUT_SEED, replicate=1 + i, **SHAPE_SMALL)
    ev_eval, rp_eval = evaluate_in_chunks(problem, u_eval, [ev.schedule, saa[0].schedule], 500)
    ws_u = u_eval[:N_WS_SMALL]
    ws_table = cost_table(problem, ws_u)
    ws = [solve_saa(problem, ws_table[..., s : s + 1], time_limit=3600) for s in range(N_WS_SMALL)]
    ws_values = np.array([w.objective for w in ws])
    # RP plan on the same futures as WS, for a paired EVPI
    planned, *_ = planned_part(problem, saa[0].schedule)
    rp_on_ws = scenario_costs(ws_table, planned, saa[0].schedule)
    gap = mmw_gap(np.array([s.objective for s in saa]), rp_eval.total)
    return {
        "instance": i,
        "proven": all(x.optimal for x in [ev, *saa, *ws]),
        "ev": ev.objective,
        "eev": summarize(ev_eval.total),
        "rp": summarize(rp_eval.total),
        "vss": paired_difference(ev_eval.total, rp_eval.total),
        "ws": summarize(ws_values),
        "evpi": paired_difference(rp_on_ws, ws_values),
        "gap": gap,
    }


def small() -> list[tuple[str, str]]:
    with ProcessPoolExecutor(min(len(INSTANCES), os.cpu_count() or 1)) as ex:
        cases = list(ex.map(small_ladder, INSTANCES))
    ladder_rows, gap_rows = [], []
    for c in cases:
        ev, eev, rp, ws = c["ev"], c["eev"], c["rp"], c["ws"]
        vss, vss_se = c["vss"]
        evpi, evpi_se = c["evpi"]
        ladder_rows.append(
            [
                c["instance"],
                "yes" if c["proven"] else "no",
                k(ev),
                f"{k(ws.mean)} ± {k(ws.se)}",
                f"{k(rp.mean)} ± {k(rp.se)}",
                f"{k(eev.mean)} ± {k(eev.se)}",
                f"{k(vss)} ± {k(vss_se)}",
                f"{k(evpi)} ± {k(evpi_se)}",
                f"{100 * (eev.mean / ev - 1):.1f} %",
            ]
        )
        g = c["gap"]
        gap_rows.append(
            [
                c["instance"],
                f"{k(g.lower)} ± {k(g.lower_se)}",
                f"{k(g.upper)} ± {k(g.upper_se)}",
                k(g.gap),
                f"{k(g.bound)} ({100 * g.relative_bound:.2f} %)",
            ]
        )
    return [
        (
            "Small instances: the exact ladder",
            "AVR-04's small instances (3 aircraft x 3 types x 26 weeks) on the FH clock, $k. "
            f"EV: the deterministic optimum at ū. RP: the exact SAA plan ({N_SAA} scenarios) "
            f"judged on {N_EVAL_SMALL} held-out futures; EEV: the EV plan on the same futures. "
            f"WS: the exact optimum with perfect foresight of each of {N_WS_SMALL} of those "
            "futures. VSS = EEV - RP and EVPI = RP - WS are paired. Every solve proven optimal "
            "by CP-SAT on one thread.\n\n"
            + table(
                [
                    "instance",
                    "proven",
                    "EV",
                    "WS",
                    "RP",
                    "EEV",
                    "VSS",
                    "EVPI",
                    "overrun (EEV / EV)",
                ],
                ladder_rows,
            ),
        ),
        (
            "Small instances: how far is the SAA plan from the true optimum?",
            f"Mak-Morton-Wood: lower = mean optimal value of {M_SAA} independent SAA problems; "
            f"upper = the first SAA plan's mean on {N_EVAL_SMALL} held-out futures; 95 % "
            "one-sided bound on its optimality gap, $k.\n\n"
            + table(
                ["instance", "lower ± se", "upper ± se", "gap estimate", "95 % bound"], gap_rows
            ),
        ),
    ]


# ------------------------------------------------------------------- main, GA


def ws_job(args: tuple[np.ndarray, int]) -> float:
    u, seed = args
    problem = main_problem()
    seeds = [load_plan("average_ga"), load_plan("robust_mean")]
    cfg = replace(RobustConfig(), seed=seed)
    return run_robust_ga(problem, cost_table(problem, u[None]), cfg, seeds=seeds).objective


def saa_job(args: tuple[int, int]) -> tuple[int, float, tuple[tuple[int, ...], ...]]:
    n, seed = args
    problem = main_problem()
    u = scenarios(n, IN_SAMPLE_SEED, replicate=100 + n)
    cfg = replace(RobustConfig(), seed=seed)
    r = run_robust_ga(problem, cost_table(problem, u), cfg, seeds=[load_plan("average_ga")])
    return n, r.objective, r.schedule


def main_instance() -> list[tuple[str, str]]:
    problem = main_problem()
    plans = {
        "plan for the average": load_plan("average_ga"),
        "robust plan (expected cost)": load_plan("robust_mean"),
        "robust plan (CVaR 90 %)": load_plan("robust_cvar"),
    }
    u = scenarios(N_HELD_OUT, HELD_OUT_SEED, replicate=2)
    evs = dict(zip(plans, evaluate_in_chunks(problem, u, list(plans.values()), 100), strict=True))
    base = evs["plan for the average"].total
    rows = []
    for name, ev in evs.items():
        s = summarize(ev.total)
        d, d_se = paired_difference(ev.total, base)
        rows.append(
            [
                name,
                f"{m(s.mean)} ± {m(s.se)}",
                m(s.p50),
                m(s.p90),
                m(s.p99),
                m(s.cvar90),
                m(s.max),
                "—" if name == "plan for the average" else f"{m(d)} ± {m(d_se)}",
            ]
        )
    dist_table = table(
        ["plan", "mean ± se", "median", "P90", "P99", "CVaR 90 %", "worst", "paired change"], rows
    )

    workers = os.cpu_count() or 1
    with ProcessPoolExecutor(workers) as ex:
        ws_values = np.array(list(ex.map(ws_job, [(u[s], 0) for s in range(N_WS_MAIN)])))
        saa_runs = list(ex.map(saa_job, [(n, s) for n in SAA_SIZES for s in GA_SEEDS]))
    ev_value = float(
        scenario_costs(
            cost_table(problem, constant_scenario(problem)),
            planned_part(problem, plans["plan for the average"])[0],
            plans["plan for the average"],
        )[0]
    )
    eev = summarize(base)
    rp = summarize(evs["robust plan (expected cost)"].total)
    rp_ws = evs["robust plan (expected cost)"].total[:N_WS_MAIN]
    evpi, evpi_se = paired_difference(rp_ws, ws_values)
    ws = summarize(ws_values)
    vss, vss_se = paired_difference(base, evs["robust plan (expected cost)"].total)
    ladder = table(
        ["measure", "value ($M)", "how"],
        [
            ["EV (the promise)", m(ev_value), "AVR-04's GA plan at ū"],
            [
                "WS (perfect foresight)",
                f"{m(ws.mean)} ± {m(ws.se)}",
                f"GA per future on {N_WS_MAIN} futures: an upper estimate",
            ],
            [
                "RP (best single plan)",
                f"{m(rp.mean)} ± {m(rp.se)}",
                "phase 3 GA plan; an upper estimate",
            ],
            ["EEV (the plan for the average)", f"{m(eev.mean)} ± {m(eev.se)}", "held out"],
            ["VSS = EEV - RP", f"{m(vss)} ± {m(vss_se)}", "paired, a lower estimate"],
            ["EVPI = RP - WS", f"{m(evpi)} ± {m(evpi_se)}", f"paired on {N_WS_MAIN} futures"],
            ["overrun = EEV - EV", m(eev.mean - ev_value), "what the promise misses"],
        ],
    )

    # SAA sample size: the best of three GA seeds per size, judged held out (paired)
    best: dict[int, tuple[float, tuple[tuple[int, ...], ...]]] = {}
    for n, objective, schedule in saa_runs:
        if n not in best or objective < best[n][0]:
            best[n] = (objective, schedule)
    sized = evaluate_in_chunks(problem, u[:2000], [best[n][1] for n in SAA_SIZES], 100)
    base2k = base[:2000]
    size_rows, curve = [], []
    for n, ev in zip(SAA_SIZES, sized, strict=True):
        d, d_se = paired_difference(ev.total, base2k)
        size_rows.append(
            [
                n,
                m(best[n][0]),
                m(float(ev.total.mean())),
                f"{m(d)} ± {m(d_se)}",
                f"{100 * (best[n][0] / ev.total.mean() - 1):+.2f} %",
            ]
        )
        curve.append(100 * d / base2k.mean())
    size_table = table(
        [
            "in-sample scenarios",
            "in-sample value ($M)",
            "held-out mean ($M)",
            "change vs average plan ($M)",
            "in-sample optimism",
        ],
        size_rows,
    )
    plotting.lines(
        list(SAA_SIZES),
        {"robust plan vs plan for the average": curve},
        xlabel="in-sample scenarios",
        ylabel="held-out change in expected cost (%)",
        logx=True,
    ).savefig(FIGURES / "tradeoff_saa_size.png", dpi=150)
    plotting.cost_distributions({n: e.total for n, e in evs.items()}).savefig(
        FIGURES / "tradeoff_costs.png", dpi=150
    )
    plotting.bars(
        ["EV", "WS", "RP", "EEV"],
        [ev_value / 1e6, ws.mean / 1e6, rp.mean / 1e6, eev.mean / 1e6],
        [0.0, ws.se / 1e6, rp.se / 1e6, eev.se / 1e6],
        ylabel="expected cost over 52 weeks ($M)",
    ).savefig(FIGURES / "tradeoff_ladder.png", dpi=150)

    # Gantt: the robust plan in a slow, a median and a fast future
    plan = plans["robust plan (expected cost)"]
    totals = evs["robust plan (expected cost)"].total
    order = np.argsort(totals)
    picks = {
        "a cheap future (P10)": int(order[len(order) // 10]),
        "a median future": int(order[len(order) // 2]),
        "an expensive future (P90)": int(order[9 * len(order) // 10]),
    }
    names = [t.name for t in problem.base.types]
    labels = [f"aircraft {c.aircraft + 1} {names[c.type]}" for c in problem.base.components]
    forced = {
        title: [
            list(component_state(problem, c, plan[c], u[s], problem.horizon).forced_weeks)
            for c in range(problem.n_components)
        ]
        for title, s in picks.items()
    }
    groups = [f"aircraft {c.aircraft + 1}" for c in problem.base.components]
    plotting.gantt_scenarios(groups, plan, forced, problem.horizon).savefig(
        FIGURES / "tradeoff_gantt.png", dpi=150
    )
    (FIGURES / "tradeoff_gantt.html").write_text(plotting.gantt_html(labels, plan, forced))

    return [
        (
            "Main instance: the cost distribution of each plan",
            f"{N_HELD_OUT} held-out futures (seed {HELD_OUT_SEED}, stream 2), $M over 52 weeks; "
            "paired change against the plan for the average.\n\n" + dist_table,
        ),
        (
            "Main instance: the ladder",
            "The GA cannot prove optimality on the main instance, so RP and WS are upper "
            "estimates (a better optimiser could only lower them).\n\n" + ladder,
        ),
        (
            "Main instance: how many scenarios does the SAA need?",
            "GA on n in-sample futures (best of three seeds, warm-started with the plan for "
            "the average), judged on the first 2000 held-out futures.\n\n" + size_table,
        ),
    ]


def main() -> None:
    sections = small() + main_instance()
    write_result("tradeoff", "Phase 5: trade-off analysis", sections)


if __name__ == "__main__":
    main()
