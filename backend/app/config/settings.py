"""Single place all configuration is loaded from.

Sources:
- `backend/.env` / environment variables -> `Settings` (secrets, URLs, numbers).
- `config/models.yaml` -> `ModelsConfig` (every model Syncra uses).
- `config/prompts/<name>.yaml` -> `Prompt` (versioned LLM prompts; models.yaml picks one per role).

Environment variables always win over `.env`. Required settings that are missing
raise `ConfigError` with a message naming each missing field.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = BACKEND_DIR / "config"


class ConfigError(RuntimeError):
    """Raised at startup when configuration is missing or invalid."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_ignore_empty=True, extra="ignore"
    )

    # --- required ---
    database_url: str

    # --- services ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout_seconds: float = 120.0
    hf_token: str | None = None  # only needed for gated Hugging Face models
    device: str = "auto"  # auto | cpu | mps | cuda — where Hugging Face models run
    trained_models_dir: Path = BACKEND_DIR / "trained_models"  # classifiers we train (SetFit)

    # --- data sources (each optional until that connector is used) ---
    github_token: str | None = None
    github_api_url: str = "https://api.github.com"
    jira_base_url: str | None = None  # e.g. https://acme.atlassian.net
    jira_email: str | None = None
    jira_api_token: str | None = None
    slack_bot_token: str | None = None
    slack_workspace_url: str | None = None  # e.g. https://acme.slack.com (for message links)
    slack_api_url: str = "https://slack.com/api"
    slack_thread_lookback_days: int = 7  # re-scan this far back for new replies on old threads

    # --- key numbers (description.md §9) ---
    sync_interval_minutes: int = 15
    chat_memory_turns: int = 10
    top_k_evidence: int = 8
    embedding_dim: int = 1024

    # --- chunker, in characters (~4 per token, well inside the embedder's window) ---
    chunk_size: int = 1500
    chunk_overlap: int = 200

    # --- decision reader, in characters: shorter conversations are skipped, longer ones cut in
    #     the middle (Ollama runs qwen3:8b with 4096 tokens of context; the prompt takes ~720) ---
    decision_min_chars: int = 60
    decision_max_chars: int = 6000

    # --- login: a bearer token stops working this many hours after it was handed out ---
    token_ttl_hours: int = 12

    # --- misc ---
    log_level: str = "INFO"
    api_docs: bool = False  # /docs, /redoc, /openapi.json; off unless set (local dev turns it on)


class ModelSpec(BaseModel):
    runtime: Literal["ollama", "huggingface", "spacy"]
    name: str  # Ollama: "qwen3:8b" (tag = version). Hugging Face: repo id.
    revision: str | None = None  # Hugging Face git revision; None = main
    gated: bool = False  # needs HF_TOKEN + accepted licence
    files: list[str] | None = None  # Hugging Face: download only these (glob patterns)
    labels: list[str] = []  # GLiNER: entity types to look for
    threshold: float = 0.5  # GLiNER: drop hits scoring lower; entity_linker: merge names this alike
    prompt: str | None = None  # Ollama: config/prompts/<prompt>.yaml, versioned by name (".v1")


class ModelsConfig(BaseModel):
    models: dict[str, ModelSpec]

    def __getitem__(self, role: str) -> ModelSpec:
        try:
            return self.models[role]
        except KeyError as exc:
            raise ConfigError(f"No model configured for role '{role}' in models.yaml") from exc


class Prompt(BaseModel):
    system: str  # the system prompt
    prompt: str  # string.Template; the step fills its $placeholders


def _format_validation_error(exc: ValidationError) -> str:
    lines = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err["loc"]).upper()
        lines.append(f"  - {field}: {err['msg']}")
    return "\n".join(lines)


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        raise ConfigError(
            "Syncra cannot start: missing or invalid settings "
            f"(set them in {BACKEND_DIR / '.env'} or the environment):\n"
            f"{_format_validation_error(exc)}"
        ) from exc


@lru_cache
def get_models_config(path: Path = CONFIG_DIR / "models.yaml") -> ModelsConfig:
    try:
        data = yaml.safe_load(path.read_text()) or {}
        return ModelsConfig.model_validate(data)
    except FileNotFoundError as exc:
        raise ConfigError(f"Models config not found: {path}") from exc
    except ValidationError as exc:
        raise ConfigError(
            f"Invalid models config {path}:\n{_format_validation_error(exc)}"
        ) from exc


@lru_cache
def get_prompt(role: str) -> Prompt:
    """The prompt file the role's `prompt` names in models.yaml: config/prompts/<prompt>.yaml."""
    name = get_models_config()[role].prompt
    if not name:
        raise ConfigError(f"No prompt configured for role '{role}' in models.yaml")
    path = CONFIG_DIR / "prompts" / f"{name}.yaml"
    try:
        return Prompt.model_validate(yaml.safe_load(path.read_text()))
    except FileNotFoundError as exc:
        raise ConfigError(f"Prompt file not found: {path}") from exc
    except ValidationError as exc:
        raise ConfigError(f"Invalid prompt file {path}:\n{_format_validation_error(exc)}") from exc
