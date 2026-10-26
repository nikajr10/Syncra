"""Download every Hugging Face model in config/models.yaml.

Usage (from backend/):  .venv/bin/python scripts/download_hf_models.py   or   make download-models
"""

import logging

from app.ml.download import download_all

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    done, skipped = download_all()
    print("Downloaded:", ", ".join(done) or "nothing")
    if skipped:
        print("Skipped (gated, set HF_TOKEN):", ", ".join(skipped))
