"""Pull every Ollama model listed in config/models.yaml.

Usage (from backend/):  .venv/bin/python scripts/pull_ollama_models.py   or   make pull-models
"""

import subprocess
import sys

from app.config.settings import get_models_config


def main() -> int:
    names = sorted({m.name for m in get_models_config().models.values() if m.runtime == "ollama"})
    for name in names:
        print(f"==> ollama pull {name}", flush=True)
        subprocess.run(["ollama", "pull", name], check=True)
    print("Pulled:", ", ".join(names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
