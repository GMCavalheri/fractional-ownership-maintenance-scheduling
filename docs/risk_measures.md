# `risk_measures`: summarising a cost distribution

**Lessons:** [3 · Planning for many futures](lessons/03-planning-for-many-futures.md) ·
**Code:** [`src/fracsched/risk_measures.py`](../src/fracsched/risk_measures.py)

## Model

For $S$ equally likely outcomes, the CVaR at level $lpha$ averages the worst $(1-lpha)S$, the
boundary one counted fractionally; this equals the Rockafellar-Uryasev minimum over $\eta$.
Quantiles use the inverted CDF (an observed value), which is stable across platforms.

## API

| function | purpose |
|---|---|
| `cvar(x, alpha)` | conditional value at risk |
| `quantile(x, q)` | observed-value quantile |
| `summarize(x)` | mean, Monte Carlo se, sd, P10, P50, P90, P99, CVaR 90 %, max |

## Verification

CVaR by hand, against brute-force minimisation of the Rockafellar-Uryasev objective, and
(Hypothesis) between the mean and the maximum and rising with $\alpha$
([`tests/test_risk_measures.py`](../tests/test_risk_measures.py)).
