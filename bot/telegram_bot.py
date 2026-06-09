import json
import asyncio
import logging
import io
import base64
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from .config import TELEGRAM_BOT_TOKEN
from .ai_handler import chat_with_ai, SYSTEM_PROMPT
from .websocket_server import manager

logger = logging.getLogger(__name__)

conversations = {}
MAX_FUNCTION_CALLS = 5


def get_conv(user_id):
    if user_id not in conversations:
        conversations[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    return conversations[user_id]


def trim_conv(conv, max_tokens=96000):
    system = conv[0]
    recent = conv[1:]
    while recent and count_tokens([system] + recent) > max_tokens:
        recent.pop(0)
    return [system] + recent


def count_tokens(messages):
    total = 0
    for m in messages:
        content = m.get("content", "")
        total += len(content) // 4
        if m.get("role") == "system":
            total += 200
        if m.get("tool_calls"):
            for tc in m["tool_calls"]:
                total += len(json.dumps(tc)) // 4
    return total


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "FRIDAY Assistant Active\n\n"
        "I'm connected to your laptop. Just chat with me naturally.\n\n"
        "/status - Check laptop connection\n"
        "/clear - Reset conversation\n"
        "/help - This message",
        parse_mode="Markdown",
    )


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if manager.is_connected:
        s = manager._connected_at.strftime("%Y-%m-%d %H:%M:%S")
        await update.message.reply_text(
            f"Laptop Connected\nSince: {s}", parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "Laptop Not Connected\n\nRun laptop_agent.py on your computer.",
            parse_mode="Markdown",
        )


async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conversations.pop(user_id, None)
    await update.message.reply_text("Conversation reset.")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    text = update.message.text
    conv = get_conv(user_id)
    conv.append({"role": "user", "content": text})

    msg = await update.message.reply_text("...")

    for _ in range(MAX_FUNCTION_CALLS):
        response = await chat_with_ai(conv)
        if not response:
            logger.error(f"AI service failed for user {user_id}. Check logs for details.")
            await msg.edit_text(
                "AI service error.\n\n"
                "Check logs for details, or verify:\n"
                "1. Railway: set OPENROUTER_API_KEY or GEMINI_API_KEY in dashboard\n"
                "2. Your API key is valid and has credits\n"
                "3. The AI model name is correct"
            )
            return

        choice = response["choices"][0]
        reply_msg = choice["message"]

        if reply_msg.get("tool_calls"):
            conv.append(reply_msg)

            for tc in reply_msg["tool_calls"]:
                if tc["type"] != "function":
                    continue
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"].get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}

                await msg.edit_text(f"Executing: {name}...")

                action_map = {
                    "execute_shell": "shell",
                    "list_files": "file_list",
                    "read_file": "file_read",
                    "write_file": "file_write",
                    "get_system_info": "system_info",
                    "take_screenshot": "screenshot",
                }

                action = action_map.get(name)
                if not action:
                    conv.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": name,
                        "content": json.dumps({"success": False, "error": f"Unknown function: {name}"}),
                    })
                    continue

                result = await manager.send_command(action, args)

                if name == "take_screenshot" and result.get("success"):
                    try:
                        img_bytes = base64.b64decode(result["data"])
                        await update.message.reply_photo(photo=io.BytesIO(img_bytes))
                    except Exception as e:
                        logger.error(f"Screenshot send error: {e}")
                    conv.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": name,
                        "content": json.dumps({"success": True, "data": "[screenshot taken and sent to user]"}),
                    })
                else:
                    result_for_ai = dict(result)
                    if isinstance(result_for_ai.get("data"), str) and len(result_for_ai["data"]) > 1000:
                        result_for_ai["data"] = result_for_ai["data"][:1000] + "... [truncated]"
                    conv.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": name,
                        "content": json.dumps(result_for_ai),
                    })

            conv = trim_conv(conv)
            await msg.edit_text("Processing result...")
        else:
            reply = reply_msg.get("content", "")
            if reply:
                conv.append({"role": "assistant", "content": reply})
                conv = trim_conv(conv)
                await msg.edit_text(reply)
            return

    await msg.edit_text("Max processing depth reached. Please try again.")


async def run_bot():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    try:
        await asyncio.Future()
    finally:
        await app.stop()
