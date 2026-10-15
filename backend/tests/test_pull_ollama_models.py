import os
import subprocess
import sys
from pathlib import Path

from app.config.settings import BACKEND_DIR, get_models_config


def test_pull_script_pulls_every_ollama_model_in_config(tmp_path: Path) -> None:
    # A fake `ollama` on PATH records its arguments instead of downloading anything.
    log = tmp_path / "calls.log"
    fake = tmp_path / "ollama"
    fake.write_text('#!/bin/sh\necho "$@" >> "$OLLAMA_FAKE_LOG"\n')
    fake.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "OLLAMA_FAKE_LOG": str(log),
    }

    subprocess.run(
        [sys.executable, "scripts/pull_ollama_models.py"], cwd=BACKEND_DIR, env=env, check=True
    )

    expected = {m.name for m in get_models_config().models.values() if m.runtime == "ollama"}
    assert expected == {"qwen3:4b", "qwen3:8b"}
    assert {line.removeprefix("pull ") for line in log.read_text().splitlines()} == expected
