import json
from types import SimpleNamespace

import pytest

from tarot.reader import draw_cards, extract_json, interpret, read_tarot
from tarot.server import handle_read, origin_allowed
from tarot.site import render

GOOD = {
    "question_analysis": {"category": "事業", "is_closed": True, "rewritten_question": "我如何看待轉職？"},
    "card_meanings": ["a", "b", "c"],
    "summary": "整體",
    "advice": "建議",
    "reflection_questions": ["q1", "q2"],
}


def fake_client(*contents):
    it = iter(contents)

    def create(**_):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=next(it)))])

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def test_draw_cards_is_reproducible_and_unique():
    a, b = draw_cards(3, seed=42), draw_cards(3, seed=42)
    assert a == b
    assert len({c["number"] for c in a}) == 3
    assert [c["position"] for c in a] == ["現況", "挑戰", "建議"]


def test_extract_json_strips_think_and_fences():
    text = '<think>想一想</think>```json\n{"x": 1}\n```'
    assert extract_json(text) == {"x": 1}


def test_interpret_retries_after_bad_output():
    client = fake_client("not json", json.dumps(GOOD))
    result = interpret(client, "m", "問題", draw_cards(3, 1))
    assert result.summary == "整體"


def test_interpret_fails_after_retries():
    client = fake_client("x", "y", "z")
    with pytest.raises(RuntimeError):
        interpret(client, "m", "問題", draw_cards(3, 1))


def test_read_tarot_and_render_escape_html():
    entry = read_tarot("<script>?", seed=7, client=fake_client(json.dumps(GOOD)), model="fake")
    html = render([entry], ["用了 Claude"])
    assert "<script>?" not in html
    assert "&lt;script&gt;?" in html
    assert "AI 使用說明" in html


def test_render_has_question_form():
    html = render([], [])
    assert 'id="ask"' in html and "/api/read" in html


def test_handle_read_validation_and_success():
    assert handle_read({})[0] == 400
    assert handle_read({"question": "   "})[0] == 400
    assert handle_read({"question": "x" * 201})[0] == 400
    code, body = handle_read({"question": "要不要運動？"}, client=fake_client(json.dumps(GOOD)), model="fake")
    assert code == 200 and body["reading"]["summary"] == "整體"


def test_handle_read_llm_failure_returns_502():
    code, body = handle_read({"question": "測試"}, client=fake_client("x", "y", "z"), model="fake")
    assert code == 502 and "error" in body


def test_origin_allowed():
    assert origin_allowed("http://127.0.0.1:8000")
    assert origin_allowed("https://someone.github.io")
    assert not origin_allowed("https://evil.example.com")
    assert not origin_allowed(None)
