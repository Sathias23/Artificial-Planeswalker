"""Unit tests for tool_steps module."""

from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)

from src.ui.tool_steps import extract_tool_calls, format_tool_params, format_tool_result_summary


class TestExtractToolCalls:
    """Test extract_tool_calls function."""

    def test_single_turn_with_one_tool_call(self) -> None:
        """Test extraction from single turn with one tool call."""
        tool_call_part = ToolCallPart(
            tool_name="lookup_card_by_name",
            args={"card_name": "Lightning Bolt"},
            tool_call_id="call_123",
        )
        model_response = ModelResponse(parts=[tool_call_part], timestamp=None)
        messages: list[ModelMessage] = [model_response]

        result = extract_tool_calls(messages)

        assert len(result) == 1
        assert result[0]["tool_name"] == "lookup_card_by_name"
        assert result[0]["tool_call_id"] == "call_123"
        assert result[0]["args"] == {"card_name": "Lightning Bolt"}

    def test_single_turn_with_multiple_tool_calls(self) -> None:
        """Test extraction from single turn with multiple parallel tool calls."""
        tool_call_1 = ToolCallPart(
            tool_name="lookup_card_by_name",
            args={"card_name": "Lightning Bolt"},
            tool_call_id="call_1",
        )
        tool_call_2 = ToolCallPart(
            tool_name="search_cards_advanced",
            args={"colors": ["R"], "limit": 10},
            tool_call_id="call_2",
        )
        model_response = ModelResponse(parts=[tool_call_1, tool_call_2], timestamp=None)
        messages: list[ModelMessage] = [model_response]

        result = extract_tool_calls(messages)

        assert len(result) == 2
        assert result[0]["tool_name"] == "lookup_card_by_name"
        assert result[1]["tool_name"] == "search_cards_advanced"

    def test_multiple_model_responses_in_turn(self) -> None:
        """Test extraction when turn has multiple ModelResponse messages.

        In PydanticAI, a single turn may have:
        - ModelResponse with ToolCallParts (agent calling tools)
        - ModelResponse with TextPart (agent giving final answer)
        """
        tool_call = ToolCallPart(
            tool_name="lookup_card_by_name",
            args={"card_name": "Lightning Bolt"},
            tool_call_id="call_1",
        )
        tool_response = ModelResponse(parts=[tool_call], timestamp=None)
        text_response = ModelResponse(parts=[TextPart(content="Result")], timestamp=None)

        messages: list[ModelMessage] = [tool_response, text_response]
        result = extract_tool_calls(messages)

        # Should extract tool call from first ModelResponse
        assert len(result) == 1
        assert result[0]["tool_name"] == "lookup_card_by_name"

    def test_text_only_response(self) -> None:
        """Test extraction when turn has only text response (no tool calls)."""
        text_part = TextPart(content="I understand your question.")
        model_response = ModelResponse(parts=[text_part], timestamp=None)
        messages: list[ModelMessage] = [model_response]

        result = extract_tool_calls(messages)

        assert len(result) == 0

    def test_empty_message_list(self) -> None:
        """Test extraction with empty message list."""
        messages: list[ModelMessage] = []
        result = extract_tool_calls(messages)
        assert len(result) == 0

    def test_no_model_response_in_messages(self) -> None:
        """Test extraction when messages contain no ModelResponse."""
        messages: list[ModelMessage] = [
            UserPromptPart(content="Show me Lightning Bolt"),
            SystemPromptPart(content="You are a helpful assistant"),
        ]
        result = extract_tool_calls(messages)
        assert len(result) == 0

    def test_mixed_parts_in_response(self) -> None:
        """Test extraction when response has both text and tool calls."""
        text_part = TextPart(content="Let me search for that card.")
        tool_call_part = ToolCallPart(
            tool_name="lookup_card_by_name",
            args={"card_name": "Counterspell"},
            tool_call_id="call_mixed",
        )
        model_response = ModelResponse(parts=[text_part, tool_call_part], timestamp=None)
        messages: list[ModelMessage] = [model_response]

        result = extract_tool_calls(messages)

        assert len(result) == 1
        assert result[0]["tool_name"] == "lookup_card_by_name"


class TestFormatToolParams:
    """Test format_tool_params function."""

    def test_format_simple_string_param(self) -> None:
        result = format_tool_params("lookup_card_by_name", {"card_name": "Lightning Bolt"})
        assert result == 'card_name="Lightning Bolt"'

    def test_format_multiple_params(self) -> None:
        result = format_tool_params(
            "search_cards_advanced",
            {"colors": ["R"], "limit": 10, "types": ["Creature"]},
        )
        assert "colors=" in result
        assert "limit=10" in result
        assert "types=" in result

    def test_format_none_params(self) -> None:
        result = format_tool_params("set_format_filter", None)
        assert result == "No parameters"


class TestFormatToolResultSummary:
    """Test format_tool_result_summary function."""

    def test_single_card_result(self) -> None:
        result = format_tool_result_summary(
            "lookup_card_by_name",
            "**Lightning Bolt**\nMana Cost: {R}\nType: Instant",
        )
        assert result == "Found: Lightning Bolt"

    def test_multiple_cards_result(self) -> None:
        result = format_tool_result_summary(
            "search_cards_advanced",
            "I found 15 cards matching your search criteria.",
        )
        assert "Found" in result
        assert "15" in result or "cards" in result

    def test_no_results_found(self) -> None:
        result = format_tool_result_summary(
            "lookup_card_by_name",
            "I couldn't find a card matching that name.",
        )
        assert result == "No results found"
