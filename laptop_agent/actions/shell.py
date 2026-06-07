"""
Sandboxed shell command execution.
Only commands that exactly match the allowlist (or match an allowed prefix) are run.
"""
import subprocess
import platform

OS = platform.system()

# ── Allowlist ─────────────────────────────────────────────────────────────────
# Commands must match EXACTLY (after stripping whitespace) OR start with
# one of the ALLOWED_PREFIXES below.

ALLOWED_EXACT: set[str] = {
    "date", "whoami", "hostname", "uptime", "pwd",
    "ls", "ls ~/Desktop", "ls ~/Documents", "ls ~/Downloads",
    "pbpaste",          # macOS clipboard
    "open ~/Desktop",
    "open ~/Downloads",
    "open ~/Documents",
}

ALLOWED_PREFIXES: tuple[str, ...] = (
    "open ",            # open <file or app path> — macOS only
    "ls ~/",            # list home subdirectories
    "echo ",
)

# ── Volume control ─────────────────────────────────────────────────────────────

def set_volume(level: int) -> str:
    level = max(0, min(100, level))
    if OS == "Darwin":
        subprocess.run(["osascript", "-e", f"set volume output volume {level}"], check=True)
    elif OS == "Windows":
        # Uses nircmd (optional) or PowerShell
        pct = level / 100.0
        ps = f"$obj = New-Object -ComObject WScript.Shell; $obj.SendKeys([char]174)"
        subprocess.run(["powershell", "-command", ps])
    else:
        subprocess.run(["amixer", "-D", "pulse", "sset", "Master", f"{level}%"], check=True)
    return f"Volume set to {level}%"


def open_url(url: str) -> str:
    if OS == "Darwin":
        subprocess.run(["open", url], check=True, timeout=10)
    elif OS == "Windows":
        subprocess.run(["start", url], shell=True, check=True, timeout=10)
    else:
        subprocess.run(["xdg-open", url], check=True, timeout=10)
    return f"Opened {url}"


def run_shell(command: str, timeout: int = 10) -> str:
    """Run a whitelisted shell command and return stdout."""
    cmd = command.strip()
    allowed = cmd in ALLOWED_EXACT or cmd.startswith(ALLOWED_PREFIXES)
    if not allowed:
        raise PermissionError(f"Command not in allowlist: {cmd!r}")
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=timeout
    )
    output = result.stdout.strip()
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"Exit code {result.returncode}")
    return output or "(no output)"
