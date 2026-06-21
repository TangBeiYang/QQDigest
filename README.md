# QQDigest

Monitor QQ group messages via NapCat, automatically summarize them with DeepSeek API daily, and send the digest to a designated QQ account.

## Features

- WebSocket connection to NapCat to listen for group messages in real time
- Persist all messages to local SQLite database
- Scheduled daily summary (configurable time) via DeepSeek API
- Summary delivered as private message through NapCat HTTP API
- Automatic reconnection on WebSocket disconnect
- Fully async (asyncio)

## Architecture

```
main.py          — Entrypoint: wires modules, starts collector & scheduler
collector.py     — WebSocket client: parses OneBot v11 JSON, stores to DB
db.py            — SQLite async wrapper: insert / query messages by time range
summarizer.py    — Calls DeepSeek Chat Completions API with formatted messages
sender.py        — Sends private message via NapCat HTTP API (send_private_msg)
config.yaml      — All configuration (group, target QQ, API key, schedule)
```

## Requirements

- Python 3.10+
- NapCat (running, with WebSocket on port 3001 and HTTP on port 3000)
- DeepSeek API key

## Setup

```bash
# 1. Clone / enter project
cd QQDigest

# 2. Install dependencies
pip install websockets aiohttp apscheduler pyyaml

# 3. Create config from example
cp config.example.yaml config.yaml
# Edit config.yaml — fill in api_key, group_id, target_qq

# 4. Make sure NapCat is running

# 5. Run
python main.py
```

The program will start listening immediately and run a summary job once on startup, then daily at the configured time.

## Configuration

| Field | Description |
|---|---|
| `napcat.ws_url` | NapCat WebSocket address (message event stream) |
| `napcat.http_url` | NapCat HTTP API address (sending messages) |
| `group_id` | QQ group to monitor |
| `target_qq` | QQ to receive the daily digest |
| `deepseek.api_key` | DeepSeek API key |
| `deepseek.model` | Model name (default `deepseek-chat`) |
| `deepseek.base_url` | API base URL (default `https://api.deepseek.com`) |
| `schedule.time` | Daily summary time in HH:MM (24h) |
| `schedule.timezone` | Timezone (default `Asia/Shanghai`) |
| `database.path` | SQLite file path |

## Notes

- `config.yaml` is gitignored — it contains the API key. Use `config.example.yaml` as a template.
- The database file (`data/messages.db`) is also gitignored.
- On startup the program runs one summary for the past 24h. This is intentional for testing — remove the call in `main.py` if you only want the scheduled run.
- WebSocket auto-reconnects after 5 seconds on disconnect.

## Tests

```bash
pip install pytest pytest-asyncio aiosqlite
pytest
```