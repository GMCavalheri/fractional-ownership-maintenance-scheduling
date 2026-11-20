# CLAUDE.md

Maintenance scheduling under uncertain utilization. A business jet's future flight hours are
uncertain, most of all in a fractional-ownership fleet. Components wear with flight hours, so a
plan built for average utilization can be wrong for any one aircraft. This project models
utilization as a stochastic process, evaluates maintenance plans across Monte Carlo scenarios
(expected cost, CVaR, worst case), searches with the genetic algorithm of AVR-04 and checks it
against an exact sample-average model, re-plans on a rolling horizon, and measures out of
sample what planning for the average costs.
Plan: `EJD-02-fractional-ownership-maintenance-scheduling-PLAN.md` (tick the phase checkboxes
as phases land).

## Reused code (pinned by git tag in `pyproject.toml`)
- `pmo` = AVR-04 (`GMCavalheri/Preventive-Maintenance-Optimization-with-Genetic-Algorithms`,
  tag v1.0.0; its pyproject says 0.1.0). Reused unchanged: `Instance`, `decode`, `Encoding`,
  `cx_blocks`, `mutate`, `run_ga`, `evaluate` (for constraint violations), `solve_exact`
  (cross-check only). Never copy its code here; import it.
- `smallfleet` = EJD-01 (`GMCavalheri/bayesian-small-fleet-reliability`, tag v1.0.0): the
  Gamma-Poisson conjugate update.

## Commands
- `uv sync` — install (Python ≥ 3.11; CI runs 3.11, 3.12 and 3.13)
- `uv run pytest --cov` — tests with the 90 % coverage gate (`-m "not slow"` skips GA/CP-SAT runs)
- `uv run ruff check .` and `uv run ruff format --check .` — lint/format. Ruff also formats
  the ```python blocks inside Markdown, so run it after editing docs too
- `uv run mypy` — strict type check of `src/`
- `uv run python validation/<script>.py` — regenerate one phase's tables
  (`validation/results/`) and figures (`docs/figures/`); `validation/run_all.py` runs them all
  in order (about an hour on 12 cores; later scripts read the plans earlier ones save in
  `validation/results/plans/`). `exact.py --main` also writes `exact_main.md`, the one
  time-limited, machine-dependent result, excluded from the byte comparison
- `uv run python notebooks/build_notebooks.py` — regenerate and execute the notebooks
- CI: `ci.yml` (lint, tests 3.11–3.13, security) on every push; `reproduce.yml` (run_all +
  `git diff --exit-code validation/results` + notebooks) when code, results or dependencies
  change, weekly, and on demand

## Layout
- `src/fracsched/` — single package; subpackages mirror the plan.
- `src/fracsched/data/` — parameter tables (CSV); every value is labelled an assumption or
  carries its source.
- `tests/` — pytest + Hypothesis. `validation/` — one script per phase, `results/` tables.
- `docs/` — theory note per module, `scope.md`, `related-work.md`, `report.md`;
  `docs/lessons/` is the course (keep its numbers in sync with `validation/results/`).
  `notebooks/` — one executed demo per lesson.

## Conventions
- The time grid is the week (t = 0…T−1, as in AVR-04). A task in week t renews the component
  at the start of week t. Component wear clocks are flight hours (FH); calendar limits are
  weeks. Utilization `u[s, a, t]` is the FH aircraft a flies in week t of scenario s.
- Planned schedules respect calendar limits and capacity (pmo's decoder). FH limits are
  enforced per scenario by recourse: a task is forced in the week the FH limit would be
  passed, at an unscheduled premium. Failures follow minimal repair with a Weibull cumulative
  hazard in FH, H(x) = (x/η)^β.
- The deterministic baseline is AVR-04 at mean utilization ū: η_weeks = η_FH/ū. With one
  constant scenario the scenario evaluator must equal `pmo.evaluate` (a test).
- Simulations take a seeded `numpy.random.Generator`; DEAP uses Python's `random`, seeded via
  the GA config. CP-SAT runs with `num_workers=1` and a fixed `random_seed`.
- Exact results (closed forms, enumeration, proven-optimal CP-SAT) are compared with
  tolerance 1e-9 or better; Monte Carlo against its own standard error (state the multiple).
- Only deterministic numbers go into `validation/results/`; anything that depends on a time
  limit or on floating-point summation order at rounding level is reported rounded or as a
  bound (`validation/common.bounded`).

## Scope (public repo)
- Synthetic utilization, fleets and costs only; every parameter is an illustrative,
  labelled assumption or cites a public source. No operator data. See `docs/scope.md`.
- Fractional programmes are described generically, from public sources. Fleets are generic
  ("midsize business jet").
- Never mention the author's employer, day job or a target employer in any file, commit
  message or doc; check for it before every push.

## Docs (GitHub-rendered math)
- Display equations go in ```` ```math ```` fences (no Markdown processing inside).
- Inline `$...$` is processed as Markdown first: no `\,` or `\;`, no `\\` row breaks, and no
  `_` right after `}` `)` `]`. `tests/test_docs.py` guards this.

## Testing rules
- Every test asserts against a closed-form result, an independent oracle (brute-force
  enumeration, numerical integration, Monte Carlo, `pmo`'s own evaluator or CP-SAT) or a cited
  published value; name the source in a comment.
- Never loosen a tolerance to make a failing test pass without explaining why.
- Properties that must hold for every input (CVaR between mean and max, hours ≥ 0, VSS ≥ 0)
  are Hypothesis tests.

## Workflow
- Commit small logical changes directly to `main`; push after ruff, mypy and pytest pass,
  each run as its own command (no pipes: a pipe hides the exit code). Stage explicit paths.
- No `Co-Authored-By` or other Claude attribution in commit messages.
- Each phase lands as code + tests, then validation results, then its lesson in
  `docs/lessons/` as a separate commit. Confirm CI is green after each push.
