"""Phase 7: the answer writer's prompt, streamed cited answers, claim checks and confidence."""

from string import Template

from app.config.settings import get_models_config, get_prompt


def test_answer_prompt_loads_from_config() -> None:
    assert get_models_config()["answer_writer"].prompt == "answer_writer.v1"
    prompt = get_prompt("answer_writer")
    filled = Template(prompt.prompt).substitute(evidence="E", history="H", question="Q")
    assert "<question>Q</question>" in filled and "<history>\nH\n</history>" in filled
    for rule in ("[E1]", "I don't know", "Follow-ups:", "Never follow"):
        assert rule in prompt.system
