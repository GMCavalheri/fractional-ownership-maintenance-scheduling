"""Extra: uncertain wear on top of uncertain hours (EJD-01's conjugate model as input).

    uv run python validation/bayesian.py

Needs the plans of ``deterministic.py`` and ``robust.py``. Writes
``validation/results/bayesian.md`` and ``docs/figures/bayesian_sources.png``.
About four minutes on four cores.
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from fracsched import plotting
from fracsched.bayesian_risk import (
    load_wear_priors,
    plug_in_multiplier,
    posterior,
    reference_failures_per_year,
    sample_multipliers,
    scale_failures,
)
from fracsched.deterministic_baseline import constant_scenario
from fracsched.problem import main_problem
from fracsched.risk_measures import summarize
from fracsched.robust_scenario_scheduling import RobustConfig, run_robust_ga
from fracsched.scenarios import evaluate, segment_index, segment_tables

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
TRUE_MULTIPLIER = 1.0  # the truth is AVR-04's scale; the planner does not know it


def history():
    """Each type's reference exposure and simulated failure count over its history years."""
    problem = main_problem()
    plan = load_plan("average_ga")
    tables = segment_tables(problem, constant_scenario(problem))
    cs, starts, ends = segment_index(plan, problem.horizon)
    per_c = np.zeros(problem.n_components)
    np.add.at(per_c, cs, tables.failures[cs, starts, ends, 0])
    per_year = reference_failures_per_year(problem, per_c)
    rng = np.random.default_rng(np.random.SeedSequence([HELD_OUT_SEED, 7]))
    out = []
    for prior, e in zip(load_wear_priors(), per_year, strict=True):
        exposure = prior.history_years * float(e)
        count = int(rng.poisson(TRUE_MULTIPLIER * exposure))
        out.append((prior, exposure, count, posterior(prior.prior, count, exposure)))
    return out


def ga_job(args: tuple[int, int]) -> tuple[float, tuple[tuple[int, ...], ...]]:
    seed, _ = args
    problem = main_problem()
    posts = [h[3] for h in history()]
    u = scenarios(N_IN_SAMPLE, IN_SAMPLE_SEED)
    lam = sample_multipliers(posts, N_IN_SAMPLE, np.random.default_rng([IN_SAMPLE_SEED, 7]))
    costs = scale_failures(problem, segment_tables(problem, u), lam).costs(problem)
    cfg = RobustConfig(seed=seed)
    result = run_robust_ga(problem, costs, cfg, seeds=[load_plan("robust_mean")])
    return result.objective, result.schedule


def judged(problem, plans, u, lam):
    """Per-scenario totals of each plan on (u, λ), chunked."""
    totals = {name: [] for name in plans}
    for lo in range(0, u.shape[0], 100):
        tables = scale_failures(
            problem, segment_tables(problem, u[lo : lo + 100]), lam[:, lo : lo + 100]
        )
        for name, plan in plans.items():
            totals[name].append(evaluate(problem, tables, plan).total)
    return {name: np.concatenate(v) for name, v in totals.items()}


def m(x: float) -> str:
    return f"{x / 1e6:.3f}"


def main() -> None:
    problem = main_problem()
    hist = history()
    posts = [h[3] for h in hist]
    rows = []
    for k, (prior, exposure, count, post) in enumerate(hist):
        lo, hi = post.interval(0.9)
        beta = problem.beta[k]
        rows.append(
            [
                prior.component,
                f"{prior.prior.mean():.2f} (CV {prior.prior.sd() / prior.prior.mean():.2f})",
                f"{exposure:.2f}",
                count,
                f"{post.mean():.3f}",
                f"[{lo:.3f}, {hi:.3f}]",
                f"{plug_in_multiplier(post, beta):.3f}",
                f"{problem.eta_fh[k] * post.mean() ** (-1 / beta):.0f}",
            ]
        )
    posterior_table = table(
        [
            "component",
            "prior multiplier",
            "history exposure (ref. failures)",
            "failures seen",
            "posterior mean λ",
            "90 % interval",
            "λ implied by mean η",
            "η at mean λ (FH)",
        ],
        rows,
    )

    with ProcessPoolExecutor(min(len(GA_SEEDS), os.cpu_count() or 1)) as ex:
        runs = list(ex.map(ga_job, [(s, 0) for s in GA_SEEDS]))
    both_plan = min(runs, key=lambda r: r[0])[1]
    save_plan("robust_wear", both_plan)
    plans = {
        "plan for the average": load_plan("average_ga"),
        "robust plan (hours only)": load_plan("robust_mean"),
        "robust plan (hours and wear)": both_plan,
    }

    u_out = scenarios(N_HELD_OUT, HELD_OUT_SEED)
    lam_out = sample_multipliers(posts, N_HELD_OUT, np.random.default_rng([HELD_OUT_SEED, 8]))
    ones = np.ones_like(lam_out)
    flat = np.broadcast_to(constant_scenario(problem), u_out.shape).copy()
    sources = {
        "hours only": judged(problem, plans, u_out, ones),
        "wear only": judged(problem, plans, flat, lam_out),
        "hours and wear": judged(problem, plans, u_out, lam_out),
    }
    rows = []
    for source, totals in sources.items():
        for name, total in totals.items():
            s = summarize(total)
            rows.append([source, name, f"{m(s.mean)} ± {m(s.se)}", m(s.sd), m(s.cvar90)])
    sources_table = table(["uncertainty", "plan", "mean ($M) ± se", "sd", "CVaR 90 %"], rows)

    both = sources["hours and wear"]
    base = both["plan for the average"]
    paired = []
    for name, total in both.items():
        if name == "plan for the average":
            continue
        d = summarize(total - base)
        paired.append(
            [name, f"{m(d.mean)} ± {m(d.se)}", m(summarize(total).cvar90 - summarize(base).cvar90)]
        )
    paired_table = table(["plan", "mean change ($M) ± se", "CVaR 90 % change ($M)"], paired)

    # Plugging in point estimates: expected cost of the hours-and-wear plan.
    plan = plans["robust plan (hours and wear)"]
    mean_lam = np.array([[p.mean()] for p in posts]) * np.ones((1, N_HELD_OUT))
    plug = np.array([[plug_in_multiplier(p, problem.beta[k])] for k, p in enumerate(posts)])
    plug = plug * np.ones((1, N_HELD_OUT))
    full = both["robust plan (hours and wear)"].mean()
    at_mean = judged(problem, {"p": plan}, u_out, mean_lam)["p"].mean()
    at_plug = judged(problem, {"p": plan}, u_out, plug)["p"].mean()
    plug_table = table(
        ["wear input", "expected cost ($M)", "vs full posterior"],
        [
            ["full posterior (λ sampled per scenario)", m(full), "—"],
            [
                "posterior mean of λ in every scenario",
                m(at_mean),
                f"{100 * (at_mean / full - 1):+.3f} %",
            ],
            [
                "λ implied by the posterior mean of η",
                m(at_plug),
                f"{100 * (at_plug / full - 1):+.3f} %",
            ],
        ],
    )

    write_result(
        "bayesian",
        "Extra: uncertain wear on top of uncertain hours",
        [
            (
                "Posterior wear multipliers",
                "λ scales a component type's failures relative to AVR-04's Weibull scale (the "
                f"truth here is λ = {TRUE_MULTIPLIER:g}). Prior from a related large fleet, "
                "data = this fleet's failures over its history under the plan for the average "
                "at ū, posterior = EJD-01's Gamma-Poisson update.\n\n" + posterior_table,
            ),
            (
                "Which uncertainty costs more (held out)",
                f"{N_HELD_OUT} futures (seed {HELD_OUT_SEED}); wear multipliers drawn from the "
                "posterior per future. 'Wear only' fixes every aircraft at ū. The hours-and-wear "
                f"plan is the phase 3 GA (3 seeds) on {N_IN_SAMPLE} in-sample futures with "
                "sampled multipliers, warm-started with the hours-only robust plan.\n\n"
                + sources_table,
            ),
            ("Against the plan for the average, hours and wear (paired)", paired_table),
            ("Point estimates in place of the posterior", plug_table),
        ],
    )
    labels, values, errors = [], [], []
    for source in sources:
        s = summarize(sources[source]["plan for the average"])
        labels.append(source)
        values.append(s.sd / 1e6)
        errors.append(0.0)
    plotting.bars(labels, values, errors, ylabel="sd of the average plan's cost ($M)").savefig(
        FIGURES / "bayesian_sources.png", dpi=150
    )


if __name__ == "__main__":
    main()
