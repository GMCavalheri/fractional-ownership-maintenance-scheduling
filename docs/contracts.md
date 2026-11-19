# `contracts`: owners' shares and the cap on their hours

**Lesson:** [6 · Who owns the hours](lessons/06-who-owns-the-hours.md) ·
**Code:** [`src/fracsched/contracts/`](../src/fracsched/contracts/)

## Model

Owners hold shares (1/16 to 1/4) with 800 hours a year per whole aircraft. Each owner-year
draws an intensity (Gamma, mean 1); requested fleet hours are split by share times intensity;
an owner is served until allocation times (1 + borrowing), then refused. Every aircraft's week
shrinks by the fleet's served/requested ratio (pooled dispatch).

## API

| function | purpose |
|---|---|
| `default_programme(borrowing)` | 76 owners, 10 aircraft ([`contract_parameters.csv`](../src/fracsched/data/contract_parameters.csv)) |
| `apply_contracts(u, programme, rng)` | flown hours, served ratio, owner hours, who was capped |

## Verification

A hand-computed cap; no cap leaves hours unchanged; caps hold, hours are conserved and more
borrowing never flies fewer hours (Hypothesis)
([`tests/test_contracts.py`](../tests/test_contracts.py)).
