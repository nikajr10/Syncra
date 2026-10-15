"""Download every Hugging Face model in config/models.yaml ahead of time."""

from __future__ import annotations

import logging
from collections.abc import Callable

from app.config.settings import ModelSpec, get_models_config, get_settings

log = logging.getLogger("syncra.models")


def hf_models() -> dict[str, ModelSpec]:
    return {r: m for r, m in get_models_config().models.items() if m.runtime == "huggingface"}


def download_all(download: Callable[..., str] | None = None) -> tuple[list[str], list[str]]:
    """Download each HF model once (same repo id twice = one download).

    Returns (downloaded repo ids, skipped repo ids). Gated models are skipped without HF_TOKEN.
    """
    if download is None:
        from huggingface_hub import snapshot_download

        download = snapshot_download
    token = get_settings().hf_token
    done: list[str] = []
    skipped: list[str] = []
    for role, spec in hf_models().items():
        if spec.name in done or spec.name in skipped:
            continue
        if spec.gated and not token:
            log.warning("skipping gated model %s (%s): set HF_TOKEN", spec.name, role)
            skipped.append(spec.name)
            continue
        log.info("downloading %s (%s)", spec.name, role)
        download(repo_id=spec.name, revision=spec.revision, token=token, allow_patterns=spec.files)
        done.append(spec.name)
    return done, skipped
