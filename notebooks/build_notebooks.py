"""Generate and execute the demo notebooks, one per lesson, from the cell sources below.

    uv run python notebooks/build_notebooks.py           # write and execute all notebooks
    uv run python notebooks/build_notebooks.py --check   # execute in memory only (CI)

Keeping the sources here, instead of hand-editing .ipynb JSON, makes the notebooks reviewable
in diffs. Every demo runs on AVR-04's small instance (3 aircraft x 3 types x 26 weeks) with
small, seeded budgets, so each takes seconds; the headline numbers live in
``validation/results/``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

HERE = Path(__file__).resolve().parent

SETUP = """\
import matplotlib.pyplot as plt
import numpy as np

from fracsched.problem import small_problem
from fracsched.utilization_model import default_model

rng = np.random.default_rng(1)
problem = small_problem(0)  # AVR-04's small instance on the flight-hour clock
model = default_model()"""

Cell = tuple[str, str]


def intro(n: int, title: str, lesson: str, text: str) -> Cell:
    return ("md", f"# {n} · {title}\n\n{text} See [Lesson {n}](../docs/lessons/{lesson}).")


NOTEBOOKS: dict[str, list[Cell]] = {
    "01_flying_hours_you_cant_predict.ipynb": [
        intro(
            1,
            "Flying hours you can't predict",
            "01-flying-hours-you-cant-predict.md",
            "Sample a year of weekly flight hours, compare the closed-form spread with simulation, "
            "and see how long a 600 FH interval lasts.",
        ),
        ("code", SETUP),
        (
            "code",
            """\
from fracsched.utilization_model import annual_mean, annual_sd, weekly_mean, weeks_to_reach

u, state = model.sample(rng, 4000, 10, 52)
years = u.sum(axis=-1).ravel()
exact = default_model(capped=False)
print(f"closed form: mean {annual_mean(exact):.0f} FH, sd {annual_sd(exact):.0f} FH")
print(f"simulated (capped): mean {years.mean():.0f} FH, sd {years.std():.0f} FH")
fig, ax = plt.subplots(figsize=(7, 3))
for a in range(3):
    ax.plot(u[0, a], lw=1)
ax.plot(weekly_mean(model), "k--", label="mean")
ax.set_xlabel("week")
ax.set_ylabel("FH in the week")
ax.legend();""",
        ),
        (
            "code",
            """\
long, _ = model.sample(rng, 2000, 10, 104)
weeks = weeks_to_reach(long, 600.0).ravel() + 1
print("weeks at mean use:", 600 / model.mean_weekly_fh)
print("P10, median, P90:", np.quantile(weeks, [0.1, 0.5, 0.9]))""",
        ),
    ],
    "02_planning_for_the_average.ipynb": [
        intro(
            2,
            "Planning for the average",
            "02-planning-for-the-average.md",
            "Run AVR-04's GA at the design utilization, check that the FH clock reproduces "
            "AVR-04's evaluator, then judge the plan on futures it did not expect.",
        ),
        ("code", SETUP),
        (
            "code",
            """\
from pmo.evaluate import evaluate as pmo_evaluate
from pmo.ga import GAConfig

from fracsched.deterministic_baseline import average_plan, constant_scenario
from fracsched.scenarios import evaluate, evaluate_in_chunks, segment_tables

plan = average_plan(problem, GAConfig(pop_size=40, generations=60, seed=0)).schedule
at_mean = evaluate(problem, segment_tables(problem, constant_scenario(problem)), plan)
print("this project at ū:", round(at_mean.total[0], 2))
print("AVR-04's evaluator:", round(pmo_evaluate(problem.at_mean(), plan).total_cost, 2))

u, _ = model.sample(rng, 1000, 3, 26)
(ev,) = evaluate_in_chunks(problem, u, [plan])
print(f"expected cost {ev.total.mean():,.0f} vs promised {at_mean.total[0]:,.0f}")
print("mean forced tasks:", ev.forced_tasks.mean())""",
        ),
        (
            "code",
            """\
fig, ax = plt.subplots(figsize=(6, 3))
ax.hist(ev.total / 1e3, bins=40)
ax.axvline(at_mean.total[0] / 1e3, color="k", ls="--", label="promised")
ax.set_xlabel("cost over 26 weeks ($k)")
ax.legend();""",
        ),
    ],
    "03_planning_for_many_futures.ipynb": [
        intro(
            3,
            "Planning for many futures",
            "03-planning-for-many-futures.md",
            "Optimise a plan on 50 sampled futures (expected cost and CVaR) and judge it on "
            "1000 others, paired against the plan for the average.",
        ),
        ("code", SETUP),
        (
            "code",
            """\
from pmo.ga import GAConfig

from fracsched.deterministic_baseline import average_plan
from fracsched.robust_scenario_scheduling import RobustConfig, run_robust_ga
from fracsched.scenarios import cost_table, evaluate_in_chunks

average = average_plan(problem, GAConfig(pop_size=40, generations=60, seed=0)).schedule
u_in, _ = model.sample(rng, 50, 3, 26)
table = cost_table(problem, u_in)
plans = {"average": average}
for objective in ("mean", "cvar"):
    cfg = RobustConfig(objective=objective, pop_size=40, generations=60, seed=0)
    plans[objective] = run_robust_ga(problem, table, cfg, seeds=[average]).schedule
u_out, _ = model.sample(rng, 1000, 3, 26)
evs = dict(zip(plans, evaluate_in_chunks(problem, u_out, list(plans.values()))))
for name, ev in evs.items():
    d = ev.total - evs["average"].total
    print(f"{name:8s} mean {ev.total.mean():9,.0f}  paired change {d.mean():8,.0f} ± {d.std() / np.sqrt(d.size):,.0f}")""",
        ),
    ],
    "04_the_exact_answer_for_a_sampled_future.ipynb": [
        intro(
            4,
            "The exact answer for a sampled future",
            "04-the-exact-answer-for-a-sampled-future.md",
            "Solve the sample-average problem exactly with CP-SAT and measure the GA's gap.",
        ),
        ("code", SETUP),
        (
            "code",
            """\
from fracsched.exact_saa import solve_saa
from fracsched.robust_scenario_scheduling import RobustConfig, run_robust_ga
from fracsched.scenarios import cost_table

u, _ = model.sample(rng, 100, 3, 26)
table = cost_table(problem, u)
exact = solve_saa(problem, table, time_limit=120)
print(exact.status, f"optimum {exact.objective:,.0f}, bound {exact.bound:,.0f}")
for seed in range(3):
    ga = run_robust_ga(problem, table, RobustConfig(pop_size=40, generations=80, seed=seed))
    print(f"GA seed {seed}: {100 * (ga.objective / exact.objective - 1):.2f} % above the optimum")""",
        ),
    ],
    "05_re_planning_as_the_hours_come_in.ipynb": [
        intro(
            5,
            "Re-planning as the hours come in",
            "05-re-planning-as-the-hours-come-in.md",
            "Simulate one actual year, then keep the plan or re-plan every four weeks.",
        ),
        ("code", SETUP),
        (
            "code",
            """\
from pmo.ga import GAConfig

from fracsched.deterministic_baseline import average_plan
from fracsched.dynamic_rescheduling import (
    RollingConfig,
    deterministic_policy,
    robust_policy,
    sample_actual,
    simulate,
    static_policy,
)

plan = average_plan(problem, GAConfig(pop_size=40, generations=60, seed=0)).schedule
cfg = RollingConfig(period=4, n_scenarios=15, pop_size=20, generations=15)
for year in range(3):
    actual = sample_actual(model, np.random.default_rng(100 + year), 3, 26)
    costs = {}
    for name, policy in [("keep", static_policy), ("re-plan avg", deterministic_policy(cfg)),
                         ("re-plan scenarios", robust_policy(model, cfg))]:
        out = simulate(problem, plan, actual, policy, cfg, np.random.default_rng(0))
        costs[name] = (round(out.evaluation.total[0]), int(out.evaluation.forced_tasks[0]))
    print(f"year {year}:", costs)""",
        ),
    ],
    "06_who_owns_the_hours.ipynb": [
        intro(
            6,
            "Who owns the hours",
            "06-who-owns-the-hours.md",
            "Apply owners' contracts to the fleet's hours and compare the fleet's spread with "
            "an aircraft's.",
        ),
        ("code", SETUP),
        (
            "code",
            """\
from fracsched.contracts import apply_contracts, default_programme

u, _ = model.sample(rng, 2000, 10, 52)
for borrowing in (0.0, 0.1, np.inf):
    out = apply_contracts(u, default_programme(borrowing), np.random.default_rng(6))
    fleet = out.u.sum(axis=(1, 2))
    tail = out.u.sum(axis=-1).ravel()
    print(f"borrowing {borrowing}: capped owner-years {out.capped.mean():.2f}, "
          f"fleet CV {fleet.std() / fleet.mean():.3f}, aircraft CV {tail.std() / tail.mean():.3f}")""",
        ),
    ],
    "07_uncertain_wear_on_top_of_uncertain_hours.ipynb": [
        intro(
            7,
            "Uncertain wear on top of uncertain hours",
            "07-uncertain-wear-on-top-of-uncertain-hours.md",
            "Update a wear multiplier with EJD-01's conjugate model and see why the mean scale "
            "is the wrong point estimate.",
        ),
        ("code", SETUP),
        (
            "code",
            """\
from smallfleet.bayesian_point_estimation import gamma_from_mean_cv

from fracsched.bayesian_risk import plug_in_multiplier, posterior

prior = gamma_from_mean_cv(1.3, 0.5)  # a pessimistic prior from a related fleet
post = posterior(prior, 16, 21.10)  # 16 failures where the reference expects 21.1
print(f"posterior mean {post.mean():.3f}, 90 % interval {post.interval(0.9)}")
print(f"multiplier implied by the mean scale: {plug_in_multiplier(post, 1.8):.3f}")
x = np.linspace(0.01, 2.5, 300)
fig, ax = plt.subplots(figsize=(6, 3))
ax.plot(x, [prior.pdf(v) for v in x], label="prior")
ax.plot(x, [post.pdf(v) for v in x], label="posterior")
ax.axvline(1.0, color="k", ls=":", label="truth")
ax.set_xlabel("wear multiplier λ")
ax.legend();""",
        ),
    ],
    "08_the_price_of_planning_for_the_average.ipynb": [
        intro(
            8,
            "The price of planning for the average",
            "08-the-price-of-planning-for-the-average.md",
            "Compute EV, EEV, RP and WS exactly on the small instance, and the value of the "
            "stochastic solution and of perfect information.",
        ),
        ("code", SETUP),
        (
            "code",
            """\
from fracsched.deterministic_baseline import constant_scenario
from fracsched.exact_saa import solve_saa
from fracsched.scenarios import cost_table, planned_part, scenario_costs

u, _ = model.sample(rng, 40, 3, 26)
table = cost_table(problem, u)
ev = solve_saa(problem, cost_table(problem, constant_scenario(problem)))
rp = solve_saa(problem, table)
eev = scenario_costs(table, planned_part(problem, ev.schedule)[0], ev.schedule).mean()
ws = np.mean([solve_saa(problem, table[..., s : s + 1]).objective for s in range(40)])
print(f"EV {ev.objective:,.0f}  WS {ws:,.0f}  RP {rp.objective:,.0f}  EEV {eev:,.0f}")
print(f"VSS = EEV - RP = {eev - rp.objective:,.0f};  EVPI = RP - WS = {rp.objective - ws:,.0f}")""",
        ),
    ],
    "09_what_is_and_isnt_new.ipynb": [
        intro(
            9,
            "What is (and isn't) new",
            "09-what-is-and-isnt-new.md",
            "The headline measurements this project adds, read from the committed results.",
        ),
        (
            "code",
            """\
from pathlib import Path

results = Path("..") / "validation" / "results"
for name in ("deterministic", "robust", "rolling", "tradeoff"):
    text = (results / f"{name}.md").read_text()
    print(text.split("## ")[2][:900], "\\n...")""",
        ),
    ],
}


def build(name: str, cells: list[Cell]) -> nbformat.NotebookNode:
    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {
        "name": "python3",
        "display_name": "Python 3",
        "language": "python",
    }
    nb.cells = [
        nbformat.v4.new_markdown_cell(src) if kind == "md" else nbformat.v4.new_code_cell(src)
        for kind, src in cells
    ]
    for i, cell in enumerate(nb.cells):
        cell["id"] = f"{Path(name).stem}-{i}"
    NotebookClient(
        nb,
        timeout=900,
        kernel_name="python3",
        record_timing=False,  # no timestamps: rebuilds are byte-identical
        resources={"metadata": {"path": str(HERE)}},
    ).execute()
    return nb


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="execute without writing")
    ap.add_argument("names", nargs="*", help="notebooks to build (default: all)")
    args = ap.parse_args()
    for name in args.names or list(NOTEBOOKS):
        print(f"== {name}", flush=True)
        nb = build(name, NOTEBOOKS[name])
        if not args.check:
            nbformat.write(nb, HERE / name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
