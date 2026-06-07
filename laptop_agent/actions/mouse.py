"""
Mouse control via PyAutoGUI.
"""
import pyautogui


def move_and_click(x: int, y: int, button: str = "left") -> str:
    pyautogui.moveTo(x, y, duration=0.3)
    pyautogui.click(x, y, button=button)
    return f"Clicked ({x}, {y}) with {button} button"


def double_click(x: int, y: int) -> str:
    pyautogui.doubleClick(x, y)
    return f"Double-clicked ({x}, {y})"


def right_click(x: int, y: int) -> str:
    pyautogui.rightClick(x, y)
    return f"Right-clicked ({x}, {y})"


def scroll(direction: str, amount: int = 3) -> str:
    clicks = amount if direction == "up" else -amount
    pyautogui.scroll(clicks)
    return f"Scrolled {direction} {amount} ticks"


def get_screen_size() -> tuple[int, int]:
    return pyautogui.size()
