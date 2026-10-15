"""Train the triage classifier on config/triage.yaml and report its held-out accuracy.

Usage (from backend/):  make train-triage      (~20 s on a laptop GPU, a few minutes on CPU)
"""

import logging
import sys

from app.learning.triage import train

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    accuracy = train()
    print(f"Held-out accuracy: {accuracy:.1%}")
    if accuracy < 0.9:
        sys.exit("Below 90%: add or fix examples in config/triage.yaml and train again.")
