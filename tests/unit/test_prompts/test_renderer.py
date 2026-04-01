import pytest

from llmops.core.prompts.renderer import PromptRenderer


def test_render_simple():
    result = PromptRenderer.render("Hello {{ name }}!", {"name": "World"})
    assert result == "Hello World!"


def test_render_multiple_variables():
    template = "Summarize the {{ topic }} for a {{ audience }} audience."
    result = PromptRenderer.render(template, {"topic": "AI safety", "audience": "technical"})
    assert result == "Summarize the AI safety for a technical audience."


def test_render_no_variables():
    result = PromptRenderer.render("No variables here.")
    assert result == "No variables here."


def test_render_missing_variable_raises():
    with pytest.raises(ValueError, match="Template rendering failed"):
        PromptRenderer.render("Hello {{ name }}!", {})


def test_render_preserves_newlines():
    template = "Line 1\nLine 2\n{{ var }}\n"
    result = PromptRenderer.render(template, {"var": "Line 3"})
    assert result == "Line 1\nLine 2\nLine 3\n"


def test_render_with_conditionals():
    template = "{% if formal %}Dear Sir/Madam{% else %}Hey{% endif %}, {{ name }}"
    assert PromptRenderer.render(template, {"formal": True, "name": "Bob"}) == "Dear Sir/Madam, Bob"
    assert PromptRenderer.render(template, {"formal": False, "name": "Bob"}) == "Hey, Bob"


def test_extract_variables():
    template = "Hello {{ name }}, your {{ item }} is ready."
    vars = PromptRenderer.extract_variables(template)
    assert vars == ["item", "name"]


def test_extract_variables_empty():
    assert PromptRenderer.extract_variables("No variables") == []


def test_extract_variables_with_conditionals():
    template = "{% if show %}{{ greeting }} {{ name }}{% endif %}"
    vars = PromptRenderer.extract_variables(template)
    assert "greeting" in vars
    assert "name" in vars
    assert "show" in vars
