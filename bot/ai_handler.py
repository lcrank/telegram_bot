import json
import logging
import httpx
from .config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL, SITE_URL, SITE_NAME

logger = logging.getLogger(__name__)

FUNCTIONS = [
    {
        "name": "execute_shell",
        "description": "Run a shell command on the laptop. Use for running programs, scripts, navigating file system, and system commands.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to execute"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "list_files",
        "description": "List files and directories at a given path",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path to list"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read"}
            },
            "required": ["path"]
        }
    },
    {
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
    },
    {
        "name": "get_system_info",
        "description": "Get detailed system information: OS, CPU, memory, disk usage, running processes",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "take_screenshot",
        "description": "Take a screenshot of the laptop screen",
        "parameters": {"type": "object", "properties": {}}
    }
]

SYSTEM_PROMPT = (
    "You are FRIDAY, an advanced AI assistant integrated with the user's laptop. "
    "You can execute shell commands, manage files, take screenshots, monitor system resources, "
    "and answer questions conversationally.\n\n"
    "Rules:\n"
    "- Be concise, helpful, and proactive\n"
    "- NEVER run destructive commands without explicit confirmation (delete, format, rm -rf)\n"
    "- Respect privacy only access what the user asks about\n"
    "- When displaying file listings or data, format it clearly\n"
    "- For screenshots, you can comment on what you see\n"
    "- The user's OS is Windows unless otherwise specified"
)

async def chat_with_ai(messages):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": SITE_URL,
        "X-Title": SITE_NAME,
    }

    body = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 4096,
        "functions": FUNCTIONS,
        "function_call": "auto",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenRouter API error: {e.response.status_code} - {e.response.text[:500]}")
            return None
        except httpx.TimeoutException:
            logger.error("OpenRouter API timeout")
            return None
        except Exception as e:
            logger.exception(f"OpenRouter error: {e}")
            return None
