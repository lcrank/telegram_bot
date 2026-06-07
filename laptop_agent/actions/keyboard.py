"""
Keyboard control via PyAutoGUI.
"""
import pyautogui

pyautogui.FAILSAFE = True   # Move mouse to top-left corner to abort

# Map friendly key names to PyAutoGUI key names
KEY_ALIASES = {
    "cmd": "command",
    "win": "winleft",
    "return": "enter",
    "del": "delete",
    "esc": "escape",
}


def type_text(text: str, interval: float = 0.03) -> str:
    """Type text at the current cursor position."""
    pyautogui.write(text, interval=interval)
    return f"Typed {len(text)} characters"


def press_hotkey(keys: str) -> str:
    """
    Press a hotkey combination.
    keys: plus-separated string e.g. "ctrl+c", "cmd+space", "alt+tab"
    """
    parts = [KEY_ALIASES.get(k.strip().lower(), k.strip().lower()) for k in keys.split("+")]
    pyautogui.hotkey(*parts)
    return f"Pressed {keys}"


def press_key(key: str) -> str:
    """Press a single key."""
    key = KEY_ALIASES.get(key.lower(), key.lower())
    pyautogui.press(key)
    return f"Pressed {key}"
