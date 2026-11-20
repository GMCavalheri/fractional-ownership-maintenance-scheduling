"""Rerun every validation script, in phase order, and report the time each took.

    uv run python validation/run_all.py

Every result is exact, proven optimal, or computed from seeded generators with fitness rounded
to cents, and rounding-level quantities are reported as bounds, so a rerun reproduces the
tables in ``validation/results/`` byte for byte; CI checks that with ``git diff``. The one
exception is ``exact_main.md``: a time-limited, multi-threaded CP-SAT search on the main
instance, whose best plan and bound depend on the machine (``exact.py --main``). Figures go to
``docs/figures/``; their pixels can differ between platforms' font setups, so CI does not
compare them.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = [
    (["utilization.py"], "Phase 1: utilization model"),
    (["deterministic.py"], "Phase 2: planning for the average (reproduces AVR-04)"),
    (["robust.py"], "Phase 3: scenario-based robust scheduling"),
    (["exact.py", *(["--main"] if "--main" in sys.argv else [])], "Extra: exact SAA oracle"),
    (["rolling.py"], "Phase 4: rolling-horizon re-planning"),
    (["contracts.py"], "Extra: owners' contracts"),
    (["bayesian.py"], "Extra: uncertain wear (EJD-01's conjugate model)"),
    (["tradeoff.py"], "Phase 5: trade-off analysis"),
]


def main() -> int:
    for args, title in SCRIPTS:
        print(f"== {title}", flush=True)
        t0 = time.perf_counter()
        done = subprocess.run([sys.executable, str(HERE / args[0]), *args[1:]], cwd=HERE.parent)
        if done.returncode:
            print(f"   {args[0]} failed (exit {done.returncode})", flush=True)
            return done.returncode
        print(f"   done in {time.perf_counter() - t0:.1f} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
