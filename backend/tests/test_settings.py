from pathlib import Path

import pytest

from app.config.settings import (
    CONFIG_DIR,
    ConfigError,
    ModelsConfig,
    Settings,
    get_models_config,
    get_settings,
)

REQUIRED_ROLES = {
    "entity_finder",
    "decision_reader",
    "embedder",
    "entity_linker",
    "triage_base",
    "presidio_nlp",
    "question_rewriter",
    "prompt_guard",
    "intent_router_base",
    "reranker",
    "answer_writer",
    "claim_checker",
}


def test_defaults_match_key_numbers() -> None:
    s = get_settings()
    assert (s.sync_interval_minutes, s.chat_memory_turns, s.top_k_evidence, s.embedding_dim) == (
        15,
        10,
        8,
        1024,
    )


def test_env_overrides_change_behaviour(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOP_K_EVIDENCE", "3")
    monkeypatch.setenv("SYNC_INTERVAL_MINUTES", "1")
    s = Settings()  # fresh instance, bypassing the cache
    assert s.top_k_evidence == 3
    assert s.sync_interval_minutes == 1


def test_missing_required_setting_fails_with_clear_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    try:
        with pytest.raises(ConfigError) as exc_info:
            get_settings()
        assert "DATABASE_URL" in str(exc_info.value)
        assert "cannot start" in str(exc_info.value)
    finally:
        get_settings.cache_clear()


def test_models_yaml_lists_every_role() -> None:
    cfg = get_models_config()
    assert REQUIRED_ROLES <= set(cfg.models)
    assert cfg["answer_writer"].runtime == "ollama"
    assert cfg["embedder"].runtime == "huggingface"
    assert cfg["prompt_guard"].gated is True


def test_unknown_role_is_a_config_error() -> None:
    with pytest.raises(ConfigError):
        get_models_config()["no_such_role"]


def test_invalid_models_yaml_is_a_config_error(tmp_path: Path) -> None:
    bad = tmp_path / "models.yaml"
    bad.write_text("models:\n  x:\n    runtime: cloud\n    name: gpt\n")
    with pytest.raises(ConfigError):
        get_models_config(bad)
    assert (CONFIG_DIR / "models.yaml").exists()
    assert isinstance(ModelsConfig.model_validate({"models": {}}), ModelsConfig)
