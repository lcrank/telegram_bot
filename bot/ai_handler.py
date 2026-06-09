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
