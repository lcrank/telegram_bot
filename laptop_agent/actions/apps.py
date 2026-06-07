"""
Open and close applications cross-platform (macOS / Windows / Linux).
"""
import platform
import subprocess
import shutil

OS = platform.system()


def open_app(name: str) -> str:
    """Open an application by name."""
    name_lower = name.lower().strip()

    if OS == "Darwin":
        # Try `open -a "<Name>"` first
        try:
            subprocess.run(["open", "-a", name], check=True, timeout=10)
            return f"Opened {name}"
        except subprocess.CalledProcessError:
            pass
        # Fall back to Spotlight via osascript
        script = f'tell application "{name}" to activate'
        subprocess.run(["osascript", "-e", script], check=True, timeout=10)
        return f"Opened {name}"

    elif OS == "Windows":
        # Try the Start menu name mapping
        APP_MAP = {
            "chrome": "chrome",
            "google chrome": "chrome",
            "firefox": "firefox",
            "notepad": "notepad",
            "calculator": "calc",
            "explorer": "explorer",
            "terminal": "wt",   # Windows Terminal
            "word": "winword",
            "excel": "excel",
        }
        cmd = APP_MAP.get(name_lower, name_lower)
        subprocess.Popen(cmd, shell=True)
        return f"Opened {name}"

    else:  # Linux
        if shutil.which(name_lower):
            subprocess.Popen([name_lower])
            return f"Opened {name}"
        raise FileNotFoundError(f"Application not found: {name}")


def close_app(name: str) -> str:
    """Close an application by name."""
    if OS == "Darwin":
        script = f'tell application "{name}" to quit'
        subprocess.run(["osascript", "-e", script], timeout=10)
        return f"Closed {name}"
    elif OS == "Windows":
        subprocess.run(["taskkill", "/IM", f"{name}.exe", "/F"], timeout=10)
        return f"Closed {name}"
    else:
        subprocess.run(["pkill", "-f", name], timeout=10)
        return f"Closed {name}"
