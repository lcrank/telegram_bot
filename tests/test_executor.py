"""
Tests for the laptop agent command dispatcher.
Run with: pytest tests/test_executor.py -v
"""
import asyncio
import pytest
from unittest.mock import patch, MagicMock


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def mock_pyautogui():
    with patch("laptop_agent.actions.keyboard.pyautogui") as m, \
         patch("laptop_agent.actions.mouse.pyautogui") as m2, \
         patch("laptop_agent.actions.screen.pyautogui") as m3:
        m3.screenshot.return_value = MagicMock(
            width=1920, height=1080,
            save=MagicMock()
        )
        yield


def test_dispatch_open_app():
    with patch("laptop_agent.actions.apps.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        from laptop_agent.executor import dispatch
        result = _run(dispatch({"action": "open_app", "target": "Spotify",
                                "_request_id": "1", "_wa_id": "+1"}))
        assert result["status"] == "ok"


def test_dispatch_unknown_action():
    from laptop_agent.executor import dispatch
    result = _run(dispatch({"action": "self_destruct", "_request_id": "2", "_wa_id": "+1"}))
    assert result["status"] == "error"
    assert "Unknown action" in result["message"]


def test_dispatch_shell_blocked():
    from laptop_agent.executor import dispatch
    result = _run(dispatch({"action": "shell", "command": "rm -rf /",
                             "_request_id": "3", "_wa_id": "+1"}))
    assert result["status"] == "error"
    assert "Not permitted" in result["message"]


def test_dispatch_shell_allowed():
    from laptop_agent.executor import dispatch
    result = _run(dispatch({"action": "shell", "command": "date",
                             "_request_id": "4", "_wa_id": "+1"}))
    assert result["status"] == "ok"


def test_dispatch_hotkey():
    with patch("laptop_agent.actions.keyboard.pyautogui") as m:
        from laptop_agent.executor import dispatch
        result = _run(dispatch({"action": "hotkey", "keys": "ctrl+c",
                                "_request_id": "5", "_wa_id": "+1"}))
        assert result["status"] == "ok"
