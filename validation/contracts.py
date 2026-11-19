"""Extra: owners' contracts cap the fleet's hours. What does that do to the maintenance plan?

    uv run python validation/contracts.py

Needs the plans of ``deterministic.py`` and ``robust.py``. Writes
``validation/results/contracts.md`` and ``docs/figures/contracts_hours.png``.
About three minutes on four cores.
"""

from __future__ import annotations

import os
from dataclasses import replace

import numpy as np

from fracsched import plotting
from fracsched.contracts import apply_contracts, default_programme
from fracsched.problem import main_problem
from fracsched.risk_measures import quantile, summarize
from fracsched.robust_scenario_scheduling import RobustConfig, run_many
from fracsched.scenarios import evaluate_in_chunks

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
BORROWING = (0.0, 0.1, 0.25, np.inf)
GA_SEEDS = (0, 1, 2)


def capped(u: np.ndarray, borrowing: float, seed: int) -> np.ndarray:
    """The same requested hours under contracts; owner intensities from their own stream."""
    rng = np.random.default_rng(np.random.SeedSequence([seed, 6]))
    return apply_contracts(u, default_programme(borrowing), rng).u


def m(x: float) -> str:
    return f"{x / 1e6:.3f}"


def main() -> None:
    problem = main_problem()
    average, robust = load_plan("average_ga"), load_plan("robust_mean")
    u_in = scenarios(N_IN_SAMPLE, IN_SAMPLE_SEED)
    u_out = scenarios(N_HELD_OUT, HELD_OUT_SEED)
    programme = default_programme()

    # 1. What the caps do to the hours
    rows = []
    for b in BORROWING:
        rng = np.random.default_rng(np.random.SeedSequence([HELD_OUT_SEED, 6]))
        out = apply_contracts(u_out, default_programme(b), rng)
        years = out.u.sum(axis=-1).ravel()
        fleet = out.u.sum(axis=(1, 2))
        rows.append(
            [
                "no cap" if np.isinf(b) else f"{b:.0%}",
                f"{out.capped.mean():.3f}",
                f"{1 - out.u.sum() / u_out.sum():.4f}",
                f"{years.mean():.1f}",
                f"{quantile(years, 0.9):.0f}",
                f"{quantile(years, 0.99):.0f}",
                f"{fleet.std(ddof=1) / fleet.mean():.4f}",
                f"{years.std(ddof=1) / years.mean():.4f}",
            ]
        )
    hours_table = table(
        [
            "borrowing",
            "owner-years at the cap",
            "hours refused",
            "mean FH / aircraft-year",
            "P90",
            "P99",
            "fleet CV",
            "aircraft CV",
        ],
        rows,
    )

    # 2. Plans under the default contracts (10 % borrowing)
    u_in_c = capped(u_in, programme.borrowing, IN_SAMPLE_SEED)
    u_out_c = capped(u_out, programme.borrowing, HELD_OUT_SEED)
    jobs = [(problem, u_in_c, replace(RobustConfig(), seed=s), (robust,)) for s in GA_SEEDS]
    results = run_many(jobs, workers=min(len(GA_SEEDS), os.cpu_count() or 1))
    contract_plan = min(results, key=lambda r: r.objective).schedule
    save_plan("robust_contracts", contract_plan, borrowing=programme.borrowing)
    plans = {
        "plan for the average": average,
        "robust plan (no contracts)": robust,
        "robust plan (contract scenarios)": contract_plan,
    }
    evs = dict(
        zip(plans, evaluate_in_chunks(problem, u_out_c, list(plans.values()), 100), strict=True)
    )
    base = evs["plan for the average"].total
    plan_rows = []
    for name, ev in evs.items():
        s = summarize(ev.total)
        d = summarize(ev.total - base)
        plan_rows.append(
            [
                name,
                f"{m(s.mean)} ± {m(s.se)}",
                m(s.cvar90),
                f"{ev.forced_tasks.mean():.2f}",
                "—" if name == "plan for the average" else f"{m(d.mean)} ± {m(d.se)}",
            ]
        )
    plans_table = table(
        ["plan", "mean ($M) ± se", "CVaR 90 %", "forced tasks", "change vs average ($M)"],
        plan_rows,
    )

    # 3. How the value of planning for the futures moves with the cap
    rows = []
    for b in BORROWING:
        u_b = capped(u_out, b, HELD_OUT_SEED)
        ev_avg, ev_rob = evaluate_in_chunks(problem, u_b, [average, robust], 100)
        d = summarize(ev_rob.total - ev_avg.total)
        rows.append(
            [
                "no cap" if np.isinf(b) else f"{b:.0%}",
                m(float(ev_avg.total.mean())),
                f"{ev_avg.forced_tasks.mean():.2f}",
                m(float(ev_rob.total.mean())),
                f"{m(d.mean)} ± {m(d.se)}",
                f"{100 * d.mean / ev_avg.total.mean():+.2f} %",
            ]
        )
    value_table = table(
        [
            "borrowing",
            "plan for the average ($M)",
            "its forced tasks",
            "robust plan ($M)",
            "difference ($M) ± se",
            "difference",
        ],
        rows,
    )

    write_result(
        "contracts",
        "Extra: owners' contracts and their hour caps",
        [
            (
                "Programme",
                f"{programme.n_owners} owners: 20 quarter, 24 eighth and 32 sixteenth shares, "
                "10 aircraft sold as 800 hours each. Each owner-year draws an intensity (Gamma, "
                "mean 1, CV 0.25); requested fleet hours are split by share x intensity; an owner "
                "past allocation x (1 + borrowing) is refused. Held-out futures "
                f"({N_HELD_OUT}, seed {HELD_OUT_SEED}).\n\n" + hours_table,
            ),
            (
                "Plans under the default contracts (10 % borrowing), held out",
                "The contract plan is the phase 3 GA (3 seeds, best in sample) on "
                f"{N_IN_SAMPLE} contract-capped in-sample scenarios, warm-started with the "
                "robust plan.\n\n" + plans_table,
            ),
            ("Value of the robust plan as the cap tightens (paired, held out)", value_table),
        ],
    )
    uncapped_years = u_out.sum(axis=-1).ravel()
    capped_years = u_out_c.sum(axis=-1).ravel()
    plotting.cost_distributions(
        {"no contracts": uncapped_years, "contracts, 10 % borrowing": capped_years},
        unit=1.0,
        xlabel="FH flown by one aircraft in a year",
    ).savefig(FIGURES / "contracts_hours.png", dpi=150)


if __name__ == "__main__":
    main()
