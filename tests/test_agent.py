"""
Tests for command interpretation (LangChain agent).
Run with: pytest tests/test_agent.py -v
"""
import asyncio
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("AGENT_SECRET", "test-secret")


def _mock_agent_result(output: dict):
    """Return a coroutine that yields a fake AgentExecutor result."""
    async def _fake_invoke(_input):
        return {"output": output}
    return _fake_invoke


@pytest.mark.parametrize("transcript,expected_action", [
    ("open Spotify",      "open_app"),
    ("take a screenshot", "screenshot"),
    ("press control C",   "hotkey"),
    ("scroll down",       "scroll"),
])
def test_interpret_known_commands(transcript, expected_action):
    with patch("backend.agent.AgentExecutor") as MockExec:
        instance = MagicMock()
        instance.ainvoke = _mock_agent_result({"action": expected_action})
        MockExec.return_value = instance

        from backend.agent import interpret_command
        result = asyncio.run(interpret_command(transcript))
        assert result.get("action") == expected_action


def test_interpret_returns_clarify_for_ambiguous():
    with patch("backend.agent.AgentExecutor") as MockExec:
        instance = MagicMock()
        instance.ainvoke = _mock_agent_result(
            {"action": "clarify", "question": "Which app do you mean?"}
        )
        MockExec.return_value = instance

        from backend.agent import interpret_command
        result = asyncio.run(interpret_command("open the thing"))
        assert result["action"] == "clarify"
        assert "question" in result
