"""Train a SetFit classifier on its examples in config/<role>.yaml and report its accuracy.

Usage (from backend/):
  make train-triage          noise filter, config/triage.yaml
  make train-intent-router   intent router, config/intent_router.yaml
About 20 s each on a laptop GPU, a few minutes on CPU.
"""

import logging
import sys

from app.ml.gateway import train_setfit_held_out

ROLES = ("triage", "intent_router")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    role = sys.argv[1]
    if role not in ROLES:
        sys.exit(f"Unknown classifier {role!r}: one of {', '.join(ROLES)}.")
    accuracy = train_setfit_held_out(role)
    print(f"Held-out accuracy: {accuracy:.1%}")
    if accuracy < 0.9:
        sys.exit(f"Below 90%: add or fix examples in config/{role}.yaml and train again.")
