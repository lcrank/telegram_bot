"""
Screenshot capture and clipboard read/write.
"""
import base64
import io
import platform
import subprocess

import pyautogui
from PIL import Image

OS = platform.system()


def take_screenshot() -> str:
    """Capture full screen and return as base64-encoded PNG."""
    img: Image.Image = pyautogui.screenshot()
    # Resize to max 1280px wide to keep payload small
    max_w = 1280
    if img.width > max_w:
        ratio = max_w / img.width
        img = img.resize((max_w, int(img.height * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def read_clipboard() -> str:
    """Return the current clipboard contents as a string."""
    if OS == "Darwin":
        return subprocess.check_output(["pbpaste"], text=True)
    elif OS == "Windows":
        import subprocess
        result = subprocess.run(
            ["powershell", "-command", "Get-Clipboard"],
            capture_output=True, text=True
        )
        return result.stdout.strip()
    else:
        # xclip or xsel on Linux
        try:
            return subprocess.check_output(["xclip", "-selection", "clipboard", "-o"], text=True)
        except FileNotFoundError:
            return subprocess.check_output(["xsel", "--clipboard", "--output"], text=True)
