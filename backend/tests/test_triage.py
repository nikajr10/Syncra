"""Task 2.1: triage training data."""

import yaml

from app.config.settings import CONFIG_DIR


def test_triage_data_has_both_labels_well_represented() -> None:
    data = yaml.safe_load((CONFIG_DIR / "triage.yaml").read_text())
    assert set(data) == {"useful", "noise"}
    texts = [text for examples in data.values() for text in examples]
    assert 100 <= len(texts) <= 300
    assert all(isinstance(t, str) and t.strip() for t in texts)  # unquoted "a: b" is a dict
    assert len(set(texts)) == len(texts)  # no duplicates, so no text carries both labels
    assert min(len(examples) for examples in data.values()) >= 0.4 * len(texts)
