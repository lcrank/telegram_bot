import json
import logging
import httpx
from .config import AI_API_KEY, AI_BASE_URL, AI_MODEL, AI_PROVIDER, SITE_URL, SITE_NAME

logger = logging.getLogger(__name__)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_shell",
            "description": "Run a shell command on the laptop. Use for running programs, scripts, navigating file system, and system commands.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file (creates directories if needed, overwrites existing file)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write to"},
                    "content": {"type": "string", "description": "Content to write to the file"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "Get detailed system information: OS, CPU, memory, disk usage, running processes",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Take a screenshot of the laptop screen",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "press_key",
            "description": "Press a keyboard key or key combination. Examples: 'win+r', 'ctrl+c', 'alt+tab', 'enter', 'escape'",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {"type": "string", "description": "Key or key combination separated by + (e.g. 'ctrl+c', 'win+r', 'alt+tab')"}
                },
                "required": ["keys"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text on the laptop keyboard",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to type"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mouse_click",
            "description": "Click the mouse at specified coordinates or current position",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate (optional, uses current position if omitted)"},
                    "y": {"type": "integer", "description": "Y coordinate (optional)"},
                    "button": {"type": "string", "description": "Mouse button: 'left', 'right', or 'middle' (default: left)", "enum": ["left", "right", "middle"]},
                    "clicks": {"type": "integer", "description": "Number of clicks (default: 1, use 2 for double-click)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mouse_move",
            "description": "Move the mouse cursor to specified coordinates",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate to move to"},
                    "y": {"type": "integer", "description": "Y coordinate to move to"}
                },
                "required": ["x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "launch_app",
            "description": "Launch an application by path or name (e.g. 'notepad.exe', 'calc.exe', 'chrome')",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Application path, executable name, or Windows URI (e.g. 'notepad.exe', 'C:\\Program Files\\...')"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "clipboard_read",
            "description": "Read the current text content from the clipboard",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "clipboard_write",
            "description": "Write text to the clipboard",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to copy to clipboard"}
                },
                "required": ["text"]
            }
        }
    }
]

SYSTEM_PROMPT = (
    "You are FRIDAY, an advanced AI assistant like JARVIS from Iron Man. "
    "You are integrated with the user's laptop and can control it completely:\n"
    "- Execute shell commands\n"
    "- Manage files (list, read, write)\n"
    "- Take screenshots and describe what you see\n"
    "- Monitor system resources (CPU, memory, disk, processes)\n"
    "- Control keyboard and mouse (press keys, type text, click, move cursor)\n"
    "- Launch applications\n"
    "- Read and write clipboard\n\n"
    "Rules:\n"
    "- Be concise, helpful, and proactive like JARVIS\n"
    "- NEVER run destructive commands without explicit confirmation (delete, format, rm -rf)\n"
    "- When asked to control the laptop, just do it rather than explaining you can't\n"
    "- For screenshots, comment on what you see like JARVIS would\n"
    "- The user's OS is Windows unless otherwise specified\n"
    "- Use the mouse/keyboard/clipboard tools for GUI interaction instead of shell when appropriate"
)

async def chat_with_ai(messages):
    if not AI_API_KEY:
        logger.error(f"AI API key not configured for provider '{AI_PROVIDER}'")
        return None

    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json",
    }

    if AI_PROVIDER == "openrouter":
        headers["HTTP-Referer"] = SITE_URL
        headers["X-Title"] = SITE_NAME

    body = {
        "model": AI_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 4096,
        "tools": TOOLS,
        "tool_choice": "auto",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(
                f"{AI_BASE_URL}/chat/completions",
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            detail = e.response.text[:500]
            logger.error(f"AI API error ({AI_PROVIDER}): {status} - {detail}")
            if status == 401:
                logger.error("API key rejected - check that your API key is valid and has not expired")
            elif status == 402:
                logger.error("API key has insufficient credits - top up your account")
            elif status == 429:
                logger.error("Rate limited - too many requests, slowing down")
            return None
        except httpx.TimeoutException:
            logger.error(f"AI API timeout ({AI_PROVIDER})")
            return None
        except Exception as e:
            logger.exception(f"AI API error ({AI_PROVIDER}): {e}")
            return None
