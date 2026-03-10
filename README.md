# GAR ARC Bot

Discord bot for the 327th Star Corps. Handles EP tracking, event logging, inactivity notices, discharge requests, weekly reports, and a REST API.

## Install

Run this on any Linux server and it handles everything — python, tesseract, all dependencies:

```bash
bash <(curl -sSL https://raw.githubusercontent.com/Ljs4426/GAR_ARC_BOT/main/install.sh)
```

Then fill in your config and start:

```bash
cd GAR_ARC_BOT/discord-bot
nano .env
python3 main.py
```

## Commands

| Command | Description |
|---|---|
| `/ep` | View or edit a member's EP |
| `/log` | Log an event and award EP to attendees |
| `/profile` | View your EP profile |
| `/request-aid` | Submit a military aid request |
| `/inactivity` | File an inactivity notice |
| `/discharge` | Submit a discharge request |
| `/gen-report` | Generate the weekly activity report |

## REST API

Runs on port `8080`. Full docs at `/docs`.

```
GET /user/username/{roblox_username}/ep
GET /user/{roblox_user_id}/ep
GET /users?page=1&per_page=50
GET /users/leaderboard?limit=10
GET /health
```

## Config

All settings live in `discord-bot/.env`. Copy `.env.example` to get started. Each feature can be toggled on/off:

```
ENABLE_EP=true
ENABLE_LOG=true
ENABLE_REPORT=true
ENABLE_API=true
ENABLE_BACKUP=true
ENABLE_REQUEST_AID=true
ENABLE_INACTIVITY=true
ENABLE_DISCHARGE=true
ENABLE_SHEETS=false
```

Google Sheets sync requires a service account JSON and `ENABLE_SHEETS=true`.
