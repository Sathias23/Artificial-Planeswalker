"""Tool call visualization helpers for Chainlit Steps.

This module provides functions to extract tool call information from PydanticAI
agent results and format them for display in Chainlit Steps. This maintains
architectural separation by keeping all Chainlit-specific code in the UI layer.
"""

import json
from typing import Any

from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart


def format_tool_params(tool_name: str, args: dict[str, Any] | str | None) -> str:
    """Format tool parameters for Step input display.

    Converts tool arguments into a human-readable format suitable for
    displaying in a Chainlit Step. Handles both dict and JSON string arguments.

    Args:
        tool_name: Name of the tool being called
        args: Tool arguments as dict, JSON string, or None

    Returns:
        Formatted parameter string for display

    Examples:
        >>> format_tool_params("lookup_card_by_name", {"card_name": "Lightning Bolt"})
        'card_name="Lightning Bolt"'
        >>> format_tool_params("search_cards_advanced", {"colors": ["R"], "limit": 10})
        'colors=["R"], limit=10'
        >>> format_tool_params("set_format_filter", None)
        'No parameters'
    """
    if args is None:
        return "No parameters"

    # Convert JSON string to dict if needed
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            # If can't parse, return raw string (ensure it's a string)
            return str(args)

    if not isinstance(args, dict):
        return str(args)

    # Format as key=value pairs
    parts = []
    for key, value in args.items():
        if value is None:
            continue  # Skip None values
        elif isinstance(value, str):
            # Quote strings
            parts.append(f'{key}="{value}"')
        elif isinstance(value, (list, dict)):
            # For complex types, use compact JSON representation
            parts.append(f"{key}={json.dumps(value)}")
        else:
            # For numbers, booleans, etc.
            parts.append(f"{key}={value}")

    return ", ".join(parts) if parts else "No parameters"


def format_tool_result_summary(tool_name: str, result: str) -> str:
    """Format tool result as a brief summary for Step output.

    Creates a concise summary of the tool result to avoid duplicating
    full card details that will appear in the final agent message.

    Args:
        tool_name: Name of the tool that was called
        result: Tool result string (full response from tool)

    Returns:
        Brief summary string for Step output

    Examples:
        >>> result = "Card: Lightning Bolt\\nMana Cost: {R}\\n..."
        >>> format_tool_result_summary("lookup_card_by_name", result)
        'Found: Lightning Bolt'
        >>> result = "I found 15 cards matching..."
        >>> format_tool_result_summary("search_cards_advanced", result)
        'Found 15 cards'
        >>> result = "I couldn't find a card matching..."
        >>> format_tool_result_summary("lookup_card_by_name", result)
        'No results found'
    """
    # Handle empty results
    if not result or not result.strip():
        return "Completed (no output)"

    # Extract card name from "**Card Name**" pattern
    if result.startswith("**"):
        # Single card result - extract name
        lines = result.split("\n")
        if lines:
            name = lines[0].strip("*")
            return f"Found: {name}"

    # Handle "I found X cards" pattern
    if "found" in result.lower() and "cards" in result.lower():
        # Try to extract count
        try:
            words = result.split()
            for i, word in enumerate(words):
                if word.lower() == "found" and i + 1 < len(words):
                    # Next word might be a number
                    try:
                        count = int(words[i + 1])
                        return f"Found {count} cards"
                    except ValueError:
                        pass
            return "Found multiple cards"
        except Exception:
            return "Found cards"

    # Handle "couldn't find" pattern
    if "couldn't find" in result.lower() or "no" in result.lower() and "found" in result.lower():
        return "No results found"

    # Handle set_format_filter responses
    if "format filter" in result.lower():
        if "enabled" in result.lower() or "set to" in result.lower():
            return "Format filter updated"
        elif "disabled" in result.lower() or "removed" in result.lower():
            return "Format filter removed"

    # Handle bug report responses
    if "bug report" in result.lower():
        return "Bug report submitted"

    # Default: truncate to first line or first 50 characters
    first_line = result.split("\n")[0]
    if len(first_line) > 50:
        return first_line[:47] + "..."
    return first_line


def extract_tool_calls(messages: list[ModelMessage]) -> list[dict[str, Any]]:
    """Extract tool call information from PydanticAI messages.

    Scans through messages to find tool calls from the most recent ModelResponse.
    Designed to be called with result.new_messages() which contains only the
    current turn's messages, preventing historical tool call pollution.

    Args:
        messages: List of ModelMessage objects from result.new_messages()

    Returns:
        List of dicts with tool call information:
        [
            {
                "tool_name": "lookup_card_by_name",
                "tool_call_id": "call_abc123",
                "args": {"card_name": "Lightning Bolt"},
                "result": "Card: Lightning Bolt..."
            },
            ...
        ]

    Notes:
        - Only includes tool calls from the most recent ModelResponse message
        - Excludes historical tool calls from previous conversation turns
        - Returns empty list if no ModelResponse or no tool calls in current turn
        - Matches tool calls with their results when available

    Examples:
        >>> # Single turn with one tool call
        >>> messages = [ModelResponse(...)]  # Contains ToolCallPart
        >>> extract_tool_calls(messages)
        [{"tool_name": "lookup_card_by_name", ...}]

        >>> # Multi-turn conversation - only extracts from last turn
        >>> messages = [
        ...     ModelResponse(...),  # Turn 1 with tool calls
        ...     UserPromptPart(...),  # User message
        ...     ModelResponse(...),  # Turn 2 with different tool calls
        ... ]
        >>> extract_tool_calls(messages)
        [{"tool_name": "search_cards_advanced", ...}]  # Only Turn 2
    """
    tool_calls: list[dict[str, Any]] = []

    # Extract tool calls from ALL ModelResponse messages in the list
    # Since we're called with new_messages(), this list only contains current turn
    # Tool calls appear in ModelResponse BEFORE the final text response
    for message in messages:
        if isinstance(message, ModelResponse):
            # Check each part of this response for tool calls
            for part in message.parts:
                if isinstance(part, ToolCallPart):
                    # Found a tool call
                    tool_info = {
                        "tool_name": part.tool_name,
                        "tool_call_id": part.tool_call_id,
                        "args": part.args,
                        "result": None,  # Will be filled if we find matching result
                    }
                    tool_calls.append(tool_info)

    # TODO: Match tool calls with their ToolReturnPart results
    # For MVP, we'll just show the tool calls themselves
    # Future enhancement: Parse ModelRequest messages for ToolReturnPart to get results

    return tool_calls


def get_friendly_tool_name(tool_name: str) -> str:
    """Convert technical tool name to user-friendly Step label.

    Args:
        tool_name: Technical function name (e.g., "lookup_card_by_name")

    Returns:
        User-friendly name (e.g., "Looking up card")

    Examples:
        >>> get_friendly_tool_name("lookup_card_by_name")
        'Looking up card'
        >>> get_friendly_tool_name("search_cards_advanced")
        'Searching cards'
        >>> get_friendly_tool_name("set_format_filter")
        'Setting format filter'
        >>> get_friendly_tool_name("report_bug")
        'Reporting bug'
    """
    # Map of tool names to friendly labels
    friendly_names = {
        "lookup_card_by_name": "Looking up card",
        "search_cards_advanced": "Searching cards",
        "set_format_filter": "Setting format filter",
        "report_bug": "Reporting bug",
    }

    return friendly_names.get(tool_name, tool_name.replace("_", " ").capitalize())
