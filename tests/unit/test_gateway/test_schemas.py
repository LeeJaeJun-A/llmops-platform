from llmops.core.gateway.schemas import (
    ChatRequest,
    ChatResponse,
    Choice,
    Message,
    Role,
    Usage,
)


def test_chat_request_defaults():
    req = ChatRequest(
        model="claude-sonnet-4-20250514",
        messages=[Message(role=Role.USER, content="Hello")],
    )
    assert req.temperature == 0.7
    assert req.max_tokens == 1024
    assert req.stream is False


def test_chat_response_content():
    resp = ChatResponse(
        id="test-123",
        model="claude-sonnet-4-20250514",
        choices=[
            Choice(
                index=0,
                message=Message(role=Role.ASSISTANT, content="Hi there!"),
                finish_reason="stop",
            )
        ],
        usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15),
    )
    assert resp.content == "Hi there!"
    assert resp.usage.total_tokens == 15


def test_chat_response_empty_choices():
    resp = ChatResponse(
        id="test-123",
        model="test",
        choices=[],
        usage=Usage(),
    )
    assert resp.content == ""
