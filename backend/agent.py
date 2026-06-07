"""
LangChain agent that maps natural language transcripts to structured
laptop commands.  Each tool returns a dict that the laptop agent executes.
"""
import json
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import create_tool_calling_agent, AgentExecutor
from .config import settings

if settings.OPENROUTER_API_KEY:
    llm = ChatOpenAI(
        model=settings.OPENROUTER_MODEL,
        temperature=0,
        api_key=settings.OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "https://github.com/voice-laptop-agent",
            "X-Title": "Telegram Laptop Agent",
        },
    )
else:
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=settings.OPENAI_API_KEY,
    )

# ── Tool definitions ───────────────────────────────────────────────────────────

@tool
def open_application(name: str) -> dict:
    """Open a named application on the laptop (e.g. 'Chrome', 'Terminal', 'Spotify')."""
    return {"action": "open_app", "target": name}


@tool
def close_application(name: str) -> dict:
    """Close / quit a running application by name."""
    return {"action": "close_app", "target": name}


@tool
def take_screenshot() -> dict:
    """Capture a screenshot of the entire screen and return it."""
    return {"action": "screenshot"}


@tool
def type_text(text: str) -> dict:
    """Type the given text at the current cursor position."""
    return {"action": "type", "text": text}


@tool
def press_hotkey(keys: str) -> dict:
    """
    Press a keyboard shortcut.  Pass keys as a plus-separated string,
    e.g. 'ctrl+c', 'cmd+space', 'alt+tab', 'ctrl+shift+esc'.
    """
    return {"action": "hotkey", "keys": keys}


@tool
def move_and_click(x: int, y: int, button: str = "left") -> dict:
    """Move the mouse to screen coordinates (x, y) and click."""
    return {"action": "click", "x": x, "y": y, "button": button}


@tool
def scroll(direction: str, amount: int = 3) -> dict:
    """Scroll the mouse wheel.  direction: 'up' or 'down'.  amount: number of ticks."""
    return {"action": "scroll", "direction": direction, "amount": amount}


@tool
def run_shell_command(command: str) -> dict:
    """
    Run a whitelisted shell command on the laptop.
    Only pre-approved safe commands are permitted (ls, date, open, etc.).
    """
    return {"action": "shell", "command": command}


@tool
def open_url(url: str) -> dict:
    """Open a URL in the default browser."""
    return {"action": "open_url", "url": url}


@tool
def get_clipboard() -> dict:
    """Read the current clipboard contents."""
    return {"action": "clipboard_read"}


@tool
def set_volume(level: int) -> dict:
    """Set system volume.  level: 0–100."""
    return {"action": "set_volume", "level": max(0, min(100, level))}


@tool
def ambiguous_command(question: str) -> dict:
    """
    Use this when the user's intent is unclear.
    Return a clarifying question to ask back via WhatsApp.
    """
    return {"action": "clarify", "question": question}


TOOLS = [
    open_application, close_application, take_screenshot,
    type_text, press_hotkey, move_and_click, scroll,
    run_shell_command, open_url, get_clipboard, set_volume,
    ambiguous_command,
]

# ── Prompt ─────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a laptop control assistant. The user sends voice or text commands via Telegram.
Your job is to interpret the command and call exactly ONE tool that best represents the action.

Rules:
- Always call a tool — never respond with plain text.
- Prefer specific tools over shell commands.
- If the command is unsafe, illegal, or destructive (rm -rf, format, delete system files), call ambiguous_command with a refusal message.
- If the intent is unclear, call ambiguous_command with a short clarifying question.
- For application names, use the exact macOS/Windows app name (e.g. 'Google Chrome', not 'chrome').
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),
])

# ── Public interface ───────────────────────────────────────────────────────────

async def interpret_command(transcript: str) -> dict:
    """
    Convert a transcript string into a structured command dict.
    Returns e.g. {"action": "open_app", "target": "Spotify"}
    """
    agent = create_tool_calling_agent(llm, TOOLS, prompt)
    executor = AgentExecutor(agent=agent, tools=TOOLS, max_iterations=3, verbose=False)

    try:
        result = await executor.ainvoke({"input": transcript})
        output = result.get("output", {})
        # The tool returns a dict; if it came back as a string, parse it
        if isinstance(output, str):
            try:
                output = json.loads(output)
            except json.JSONDecodeError:
                output = {"action": "clarify", "question": f"I didn't understand: {transcript}"}
        return output
    except Exception as e:
        return {"action": "error", "message": str(e)}
