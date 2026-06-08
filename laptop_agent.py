"""
FRIDAY Laptop Agent
Run this script on your laptop to connect it to the FRIDAY Telegram bot.
"""

import asyncio
import json
import os
import sys
import platform
import subprocess
import base64
import io
import logging
import websockets

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

CONFIG = {
    "server_url": os.environ.get("AGENT_SERVER_URL", "ws://localhost:8080"),
    "auth_token": os.environ.get("AGENT_AUTH_TOKEN", "friday-secret-key"),
    "reconnect_delay": 5,
}


def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "agent_config.json")
    if os.path.exists(config_path):
        with open(config_path) as f:
            cfg = json.load(f)
            CONFIG.update(cfg)


async def handle_shell(command):
    if not command.strip():
        return {"success": False, "error": "Empty command"}
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
        )
        stdout, stderr = await proc.communicate()
        out = stdout.decode(errors="replace")[:100000]
        err = stderr.decode(errors="replace")[:100000]
        result = {"success": proc.returncode == 0}
        if out:
            result["data"] = out
        if err:
            result["error"] = err
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_file_list(path):
    import os
    try:
        items = os.listdir(path)
        files = []
        for item in sorted(items):
            fp = os.path.join(path, item)
            try:
                st = os.stat(fp)
                files.append({
                    "name": item,
                    "type": "dir" if os.path.isdir(fp) else "file",
                    "size": st.st_size,
                })
            except OSError:
                files.append({"name": item, "type": "unknown"})
        return {"success": True, "data": files}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_file_read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return {"success": True, "data": content[:500000]}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_file_write(path, content):
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "data": f"Written {len(content)} bytes to {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_system_info():
    import psutil
    info = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "hostname": platform.node(),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "cpu_count": psutil.cpu_count(),
        "memory": dict(psutil.virtual_memory()._asdict()),
        "disk": {},
        "processes": [],
    }
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            info["disk"][part.mountpoint] = {
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
            }
        except Exception:
            pass
    for proc in sorted(
        psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]),
        key=lambda p: p.info.get("cpu_percent", 0) or 0,
        reverse=True,
    )[:20]:
        info["processes"].append(proc.info)
    return {"success": True, "data": info}


async def handle_screenshot():
    try:
        from mss import mss
        from PIL import Image
        with mss() as sct:
            monitor = sct.monitors[1]
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            b64 = base64.b64encode(buf.read()).decode()
            return {"success": True, "data": b64}
    except ImportError:
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            b64 = base64.b64encode(buf.read()).decode()
            return {"success": True, "data": b64}
        except Exception as e:
            return {"success": False, "error": f"Screenshot failed: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


ACTION_HANDLERS = {
    "shell": handle_shell,
    "file_list": lambda p: handle_file_list(p.get("path", ".")),
    "file_read": lambda p: handle_file_read(p.get("path", "")),
    "file_write": lambda p: handle_file_write(p.get("path", ""), p.get("content", "")),
    "system_info": lambda p: handle_system_info(),
    "screenshot": lambda p: handle_screenshot(),
}


async def execute_action(action, params):
    handler = ACTION_HANDLERS.get(action)
    if not handler:
        return {"success": False, "error": f"Unknown action: {action}"}
    try:
        if asyncio.iscoroutinefunction(handler):
            return await handler(params)
        return handler(params)
    except Exception as e:
        return {"success": False, "error": str(e)}


async def agent_main():
    uri = CONFIG["server_url"]
    token = CONFIG["auth_token"]

    while True:
        try:
            async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as ws:
                await ws.send(json.dumps({"type": "auth", "token": token}))
                resp = json.loads(await ws.recv())
                if resp.get("type") != "auth_ok":
                    logger.error(f"Auth failed: {resp.get('error')}")
                    await asyncio.sleep(CONFIG["reconnect_delay"])
                    continue

                logger.info("Connected and authenticated to FRIDAY server")

                async for message in ws:
                    data = json.loads(message)
                    if data.get("type") == "cmd":
                        result = await execute_action(
                            data["action"], data.get("params", {})
                        )
                        await ws.send(json.dumps({
                            "type": "result",
                            "id": data["id"],
                            **result,
                        }))
                    elif data.get("type") == "ping":
                        await ws.send(json.dumps({"type": "pong"}))

        except Exception as e:
            logger.warning(f"Connection error: {e}. Reconnecting in {CONFIG['reconnect_delay']}s...")
            await asyncio.sleep(CONFIG["reconnect_delay"])


if __name__ == "__main__":
    load_config()
    logger.info(f"FRIDAY Laptop Agent starting... Server: {CONFIG['server_url']}")
    asyncio.run(agent_main())
