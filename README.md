# QQDigest

[English](README.md) | [中文](README_ch.md)

Monitor QQ group messages via NapCat, automatically extract valuable information with DeepSeek API every hour (09:00-23:00), and send the digest to a designated QQ account.

## Features

- WebSocket connection to NapCat to listen for group messages in real time
- Persist all messages to local SQLite database
- Hourly extraction 09:00-23:00 via DeepSeek API — filters noise, surfaces study/career/technical signals; midnight catch-up at 00:00 covers 23:00-00:00; nightly catch-up at 09:00 covers 00:00-09:00
- Digest delivered as private message through NapCat HTTP API
- Automatic reconnection on WebSocket disconnect
- Fully async (asyncio)

## Architecture

```
main.py          — Entrypoint: wires modules, starts collector & scheduler
collector.py     — WebSocket client: parses OneBot v11 JSON, stores to DB
db.py            — SQLite async wrapper: insert / query messages by time range
summarizer.py    — Calls DeepSeek Chat Completions API: extracts high-value info (learning, career, tech) from raw messages
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

The program starts listening immediately and runs an extraction job once on startup for the past 1 hour, then follows the regular schedule.

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
| `schedule.minute` | Minute of each hour to run (0-59). Jobs: 09:00-23:00 hourly (past 1h), 00:00 (23-24h catch-up), 09:00 (00:00-09:00 night catch-up, past 9h) |
| `schedule.timezone` | Timezone (default `Asia/Shanghai`) |
| `database.path` | SQLite file path |

## Notes

- `config.yaml` is gitignored — it contains the API key. Use `config.example.yaml` as a template.
- The database file (`data/messages.db`) is also gitignored.
- Schedule: 09:00-23:00 runs every hour (past 1h of messages); 00:00 covers 23:00-00:00; 09:00 runs a night catch-up covering 00:00-09:00 (past 9h).
- On startup the program runs one extraction for the past 1 hour. This can be removed in `main.py` if undesired.
- WebSocket auto-reconnects after 5 seconds on disconnect.

## Tests

```bash
pip install pytest pytest-asyncio aiosqlite
pytest
```