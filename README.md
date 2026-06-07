# Telegram Laptop Agent (JARVIS-like)

Control your laptop remotely by sending **voice messages or text** to a Telegram bot. The bot responds with **voice (TTS)** like Iron Man's JARVIS.

```
Voice message → Whisper STT → GPT-4o-mini → WebSocket → PyAutoGUI
                                        ↕
                              OpenAI TTS voice response
```

---

## Prerequisites

| What | Where to get it |
|---|---|
| **Telegram Bot Token** | Chat with [@BotFather](https://t.me/BotFather) on Telegram |
| **Your Telegram User ID** | Chat with [@userinfobot](https://t.me/userinfobot) on Telegram |
| **OpenAI API key** | platform.openai.com (required for STT + TTS) |
| **OpenRouter API key** (optional) | openrouter.ai/keys (alternative LLM provider — use Claude, Llama, Gemini, etc.) |
| Python 3.11+ | python.org |
| Public HTTPS server (backend) | Hetzner / DigitalOcean / any VPS |
| Domain + TLS cert | Let's Encrypt (`certbot`) |

---

## Project structure

```
voice-laptop-agent/
├── backend/                  ← runs on your VPS
│   ├── main.py               FastAPI app + Telegram webhook + WebSocket
│   ├── telegram_bot.py       Telegram bot handlers (voice + text)
│   ├── tts.py                OpenAI TTS (text-to-speech)
│   ├── stt.py                Whisper transcription
│   ├── agent.py              LangChain command interpreter (GPT-4o-mini)
│   ├── ws_manager.py         WebSocket connection manager
│   ├── config.py             Environment settings
│   ├── models.py             Pydantic schemas
│   ├── Dockerfile
│   └── .env.example
├── laptop_agent/             ← runs on your laptop
│   ├── agent.py              Main loop + WebSocket client
│   ├── executor.py           Command dispatcher
│   ├── config.py
│   ├── .env.example
│   └── actions/
│       ├── apps.py           open / close applications
│       ├── keyboard.py       type text, hotkeys
│       ├── mouse.py          click, scroll
│       ├── screen.py         screenshot, clipboard
│       └── shell.py          sandboxed shell + volume + URL
├── tests/
├── Dockerfile                ← Railway deployment
├── .dockerignore
├── docker-compose.yml
├── requirements-backend.txt
└── requirements-laptop.txt
```

---

## Quick start — Railway deploy (recommended)

Deploy the backend on [Railway](https://railway.app) for free (no credit card needed for starter tier).

### Step 1 — Create your Telegram bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather).
2. Send `/newbot` and follow the prompts to create a bot.
3. Note the **bot token** (looks like `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`).
4. Find your user ID by messaging [@userinfobot](https://t.me/userinfobot) — it will reply with your numeric ID.

### Step 2 — Deploy on Railway

**A. Push the repo to GitHub**
```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git push -u origin main
```

**B. Deploy on Railway**

1. Go to [railway.app](https://railway.app) and log in with GitHub.
2. Click **New Project** → **Deploy from GitHub repo**.
3. Select your repo. Railway auto-detects the `Dockerfile` at the root and starts building.
4. Go to the **Variables** tab and add these environment variables:

| Variable | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Your bot token from @BotFather |
| `OPENAI_API_KEY` | `sk-...` from platform.openai.com |
| `AGENT_SECRET` | Run `python -c "import secrets; print(secrets.token_hex(32))"` and paste the output |
| `TELEGRAM_ALLOWED_USER_IDS` | `[123456789]` (your Telegram user ID from @userinfobot) |
| `WEBHOOK_URL` | Your Railway URL (from Settings → Domains, e.g. `https://voice-agent.up.railway.app`) |
| `TTS_VOICE` | `nova` (or alloy/echo/fable/onyx/shimmer) |

5. Wait for the build to finish. Railway shows **Deployments** → logs.
6. Go to **Settings → Domains** and generate a `*.railway.app` domain (or add your own).
7. Visit `https://your-app.railway.app` — you should see `{"detail":"Not Found"}` (that means it's running).

### Step 3 — Set the Telegram webhook

Run this once (replace TOKEN and URL):
```bash
curl -F "url=https://your-app.railway.app/webhook" \
     https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook
```

Verify it worked:
```bash
curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo
```

### Step 4 — Start the laptop agent

```bash
# On your laptop
pip install -r requirements-laptop.txt

cp laptop_agent/.env.example laptop_agent/.env
# Edit laptop_agent/.env:
#   WS_URL=wss://your-app.railway.app
#   AGENT_SECRET=<same value as you set on Railway>

python -m laptop_agent.agent
# You should see: ✅  Connected — waiting for commands
```

### Step 5 — Test it

Open Telegram, find your bot, and send a voice message or text:

- *"Open Spotify"*
- *"Take a screenshot"*
- *"Press Control C"*
- *"Set volume to 50"*
- *"Open youtube.com"*

The bot will reply with both **text** and a **voice message** (TTS).

---

## Alternative: Deploy on your own VPS / Docker

```bash
git clone <your-repo> && cd voice-laptop-agent

# Create .env
cp backend/.env.example backend/.env
# Edit backend/.env — fill in all values

# Start with Docker Compose
docker compose up -d

# Then set webhook
curl -F "url=https://your-domain.com/webhook" \
     https://api.telegram.org/bot<TOKEN>/setWebhook
```

Make sure port 8000 is accessible over HTTPS (reverse-proxy with nginx + certbot).

---

## Features

| Feature | Description |
|---|---|
| **Voice commands** | Send a voice message → transcribed with Whisper → executed |
| **Text commands** | Type any command directly |
| **Voice responses** | Bot speaks back via OpenAI TTS (like JARVIS) |
| **Screenshots** | "Take a screenshot" sends the image inline |
| **App control** | Open / close any application |
| **Keyboard** | Type text, press any hotkey combination |
| **Mouse control** | Click at coordinates, scroll |
| **Clipboard** | Read clipboard contents |
| **Volume** | Set system volume |
| **Shell** | Run whitelisted commands (ls, date, etc.) |

## Supported commands

| Voice/text command (examples) | Action |
|---|---|
| "Open Chrome / Spotify / Terminal" | Opens the application |
| "Close Slack" | Quits the application |
| "Take a screenshot" | Captures screen, sends image back |
| "Press Control C" / "Press Command Space" | Keyboard shortcut |
| "Type hello world" | Types text at cursor |
| "Scroll down / up" | Mouse scroll |
| "Click at 500 300" | Mouse click at coordinates |
| "Open github.com" | Opens URL in browser |
| "What's in my clipboard" | Returns clipboard contents |
| "Set volume to 70" | Sets system volume |
| "Show files on desktop" / "Show date" | Whitelisted shell commands |

---

## Security

- **User whitelist** — set `TELEGRAM_ALLOWED_USER_IDS` to restrict commands to your Telegram account only.
- **Command allowlist** — shell commands must match the hardcoded allowlist in `actions/shell.py`. Never blindly pass LLM output to subprocess.
- **WebSocket auth** — the laptop agent authenticates with a shared secret token.
- **PyAutoGUI failsafe** — move your mouse to the top-left corner of the screen to abort any running PyAutoGUI action.
- **Timeouts** — all subprocess calls have a 10-second timeout; WebSocket commands time out after 30 seconds.

---

## Extending the allowlist

To allow additional shell commands, edit `laptop_agent/actions/shell.py`:

```python
ALLOWED_EXACT: set[str] = {
    "date", "whoami", ...
    "your-new-command",
}

ALLOWED_PREFIXES: tuple[str, ...] = (
    "open ",
    "ls ~/",
    "your-prefix ",
)
```

---

## Running tests

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

---

## Environment variables reference

### Backend (`backend/.env`)

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token from @BotFather |
| `OPENAI_API_KEY` | OpenAI API key (required for Whisper STT + TTS voice) |
| `OPENROUTER_API_KEY` | OpenRouter API key (optional — overrides OpenAI for the LLM agent) |
| `OPENROUTER_MODEL` | Model to use via OpenRouter (default: `openai/gpt-4o-mini`) |
| `AGENT_SECRET` | Shared secret between backend and laptop agent |
| `TELEGRAM_ALLOWED_USER_IDS` | JSON array of allowed Telegram user IDs (optional) |
| `WEBHOOK_URL` | Your public HTTPS URL for webhook auto-registration |
| `TTS_VOICE` | OpenAI TTS voice: `alloy`, `echo`, `fable`, `nova`, `onyx`, `shimmer` |
| `REDIS_URL` | Redis connection URL |
| `RATE_LIMIT` | slowapi rate limit string (default: `30/minute`) |

### Laptop agent (`laptop_agent/.env`)

| Variable | Description |
|---|---|
| `WS_URL` | WebSocket URL of the backend (`wss://your-domain.com`) |
| `AGENT_SECRET` | Must match backend value |
| `RECONNECT_DELAY` | Seconds to wait before reconnecting (default: `5`) |

---

## Troubleshooting

**"Laptop agent is offline" reply**
- Run `python -m laptop_agent.agent` on your laptop.
- Check `WS_URL` uses `wss://` (not `ws://`) in production.

**Bot not responding**
- Check the webhook is set: `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo`
- Verify your server is reachable over HTTPS.

**PyAutoGUI PermissionError on macOS**
- Go to System Settings → Privacy & Security → Accessibility and add your Terminal / Python.

**Command not executing as expected**
- Check backend logs (`docker compose logs backend`) for the raw transcript.
- The GPT agent may have misinterpreted the command — try rephrasing.

**Voice response not playing**
- TTS uses OpenAI's API — ensure your OpenAI key has access and credit.
