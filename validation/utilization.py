"""Phase 1: the utilization model's statistics, closed form against simulation.

    uv run python validation/utilization.py

Writes ``validation/results/utilization.md`` and three figures in ``docs/figures/``.
"""

from __future__ import annotations

import numpy as np

from fracsched import plotting
from fracsched.utilization_model import (
    REGIMES,
    annual_mean,
    annual_sd,
    autocorrelation,
    cross_correlation,
    d_second_moment,
    default_model,
    fleet_annual_sd,
    weekly_mean,
    weeks_to_reach,
    x_second_moment,
)

from common import FIGURES, table, write_result

SEED = 20261119
N_PATHS = 20_000  # aircraft-years for the simulation checks
FLEET = 10
LIMITS = (150.0, 300.0, 600.0)


def main() -> None:
    rng = np.random.default_rng(SEED)
    exact = default_model(capped=False)
    capped = default_model()

    # 1. Parameters
    spell = 1 / (1 - np.diag(exact.P))
    params = table(
        ["regime", "stationary share", "mean FH / week", "Gamma shape", "mean spell (weeks)"],
        [
            [r, round(float(p), 4), round(float(m), 2), float(k), round(float(s), 2)]
            for r, p, m, k, s in zip(
                REGIMES, exact.pi, exact.means, exact.shapes, spell, strict=True
            )
        ],
    )

    # 2. Closed form against simulation (uncapped model, where the closed forms are exact)
    u, _ = exact.sample(rng, N_PATHS // FLEET, FLEET, 52)
    one = u.reshape(-1, 52)
    years = one.sum(axis=1)
    deseason = u / exact.season
    flat = deseason.reshape(-1, 52)

    def mc_acf(h: int) -> float:
        x = flat - flat.mean()
        return float((x[:, :-h] * x[:, h:]).mean() / x.var())

    a, b = deseason[:, 0, :].ravel(), deseason[:, 1, :].ravel()
    mc_cross = float(np.corrcoef(a, b)[0, 1])
    fleet_years = u.sum(axis=(1, 2))
    var_dx = d_second_moment(exact, 0) * x_second_moment(exact, 0) - exact.mean_weekly_fh**2
    weekly_sd_flat = float(np.sqrt(var_dx))
    # The same weekly variances with every covariance set to zero.
    independent_sd = float(np.sqrt(var_dx * (exact.season**2).sum()))
    checks = table(
        ["statistic", "closed form", "simulation"],
        [
            ["mean FH per aircraft-year", annual_mean(exact), float(years.mean())],
            ["sd of de-seasonalised weekly FH", weekly_sd_flat, float(flat.std(ddof=1))],
            ["sd of FH per aircraft-year if weeks were independent", independent_sd, "—"],
            ["sd of FH per aircraft-year", annual_sd(exact), float(years.std(ddof=1))],
            [
                "coefficient of variation",
                annual_sd(exact) / annual_mean(exact),
                float(years.std(ddof=1) / years.mean()),
            ],
            ["lag-1 week autocorrelation", autocorrelation(exact, 1), mc_acf(1)],
            ["lag-4 week autocorrelation", autocorrelation(exact, 4), mc_acf(4)],
            ["lag-13 week autocorrelation", autocorrelation(exact, 13), mc_acf(13)],
            ["correlation of two aircraft in one week", cross_correlation(exact), mc_cross],
            [
                f"sd of the {FLEET}-aircraft fleet's annual FH",
                fleet_annual_sd(exact, FLEET),
                float(fleet_years.std(ddof=1)),
            ],
            [
                f"fleet CV ({FLEET} aircraft)",
                fleet_annual_sd(exact, FLEET) / (FLEET * 800),
                float(fleet_years.std(ddof=1) / fleet_years.mean()),
            ],
        ],
    )

    # 3. The capped model the scheduler uses: plausible extremes
    uc, _ = capped.sample(rng, N_PATHS // FLEET, FLEET, 52)
    yc = uc.reshape(-1, 52).sum(axis=1)
    q = np.quantile(yc, [0.01, 0.1, 0.5, 0.9, 0.99], method="inverted_cdf")
    extremes = table(
        ["statistic", "value"],
        [
            ["mean FH per aircraft-year", float(yc.mean())],
            *[
                [f"P{p} FH per aircraft-year", float(v)]
                for p, v in zip((1, 10, 50, 90, 99), q, strict=True)
            ],
            ["P99 FH in one week", float(np.quantile(uc, 0.99, method="inverted_cdf"))],
            [
                "share of aircraft-weeks at the 70 FH cap",
                float((uc >= capped.max_weekly_fh).mean()),
            ],
            ["share of idle-quiet aircraft-years (< 400 FH)", float((yc < 400).mean())],
        ],
    )

    # 4. How long an FH interval lasts in weeks
    rows, weeks_by_limit, at_mean = [], {}, {}
    long_paths, _ = capped.sample(rng, N_PATHS // FLEET, FLEET, 104)
    for limit in LIMITS:
        w = weeks_to_reach(long_paths, limit).ravel() + 1
        p10, p50, p90 = np.quantile(w, [0.1, 0.5, 0.9], method="inverted_cdf")
        label = f"{limit:.0f} FH"
        weeks_by_limit[label] = w.astype(float)
        at_mean[label] = limit / capped.mean_weekly_fh
        rows.append([label, at_mean[label], int(p10), int(p50), int(p90), float((w > 104).mean())])
    passage = table(
        [
            "interval",
            "weeks at mean use",
            "P10 weeks",
            "median weeks",
            "P90 weeks",
            "share > 2 years",
        ],
        rows,
    )

    write_result(
        "utilization",
        "Phase 1: utilization model",
        [
            ("Regimes", params),
            (
                "Closed form against simulation",
                f"Uncapped model, {N_PATHS} aircraft-years (seed {SEED}). The closed forms are in "
                "`fracsched.utilization_model.moments`; tests hold them to path enumeration, "
                "quadrature and Monte Carlo.\n\n" + checks,
            ),
            ("Plausible extremes (capped model, used by the scheduler)", extremes),
            ("Calendar length of a flight-hour interval", passage),
        ],
    )

    mean = weekly_mean(capped)
    plotting.utilization_paths(uc[0], mean).savefig(FIGURES / "utilization_paths.png", dpi=150)
    plotting.annual_hours_histogram(yc, 800.0).savefig(FIGURES / "utilization_annual.png", dpi=150)
    plotting.weeks_to_limit(weeks_by_limit, at_mean).savefig(
        FIGURES / "utilization_weeks_to_limit.png", dpi=150
    )


if __name__ == "__main__":
    main()
