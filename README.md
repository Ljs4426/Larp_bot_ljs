# 327th Star Corps Discord Bot

A Discord bot for managing Engagement Points (EP), event logging, inactivity tracking, discharge requests, and Roblox account verification for a Roblox military unit.

---

## Quick Install (Linux)

Runs the install script which handles Python, Tesseract-OCR, and all dependencies automatically:

```bash
bash <(curl -sSL https://raw.githubusercontent.com/Ljs4426/Larp_bot_ljs/main/install.sh)
```

Then set up your config and start the bot:

```bash
cd Larp_bot_ljs/discord-bot
cp .env.example .env
nano .env          # fill in your tokens and IDs
python3 main.py
```

---

## Full Setup Guide

### Step 1 — Create a Discord Bot

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications) and click **New Application**
2. Give it a name, then go to the **Bot** tab
3. Under **Privileged Gateway Intents** enable:
   - Server Members Intent
   - Message Content Intent
4. Click **Reset Token** and copy the token — this goes into `DISCORD_TOKEN`
5. Go to **OAuth2 → URL Generator**, select scopes: `bot`, `applications.commands`
6. Under Bot Permissions select: Send Messages, Embed Links, Attach Files, Read Message History, Add Reactions, Manage Roles, Kick Members
7. Copy the generated URL, open it in a browser, and invite the bot to your server

### Step 2 — Find Your Server and Channel IDs

Enable Developer Mode in Discord: **User Settings → Advanced → Developer Mode**

Then right-click any server, channel, or role and click **Copy ID**.

You'll need IDs for:
- Your server (guild)
- Log channel (`LOG_CHANNEL_ID`)
- Aid request channel (`AID_REQUEST_CHANNEL_ID`)
- Inactivity channel (`INACTIVITY_CHANNEL_ID`)
- Discharge request channel (`DISCHARGE_REQUEST_CHANNEL_ID`)
- Discharge log channel (`DISCHARGE_LOG_CHANNEL_ID`)
- Event log channel (`EVENT_LOG_CHANNEL_ID`) — optional, where event embeds post
- Report channel (`REPORT_CHANNEL_ID`) — optional, for weekly report drops

### Step 3 — Find Your Roblox Group ID

Your group URL looks like `roblox.com/groups/12345678/GroupName`. The number is your group ID.

To get the bot owner's Roblox user ID, go to your profile — the number in the URL is your ID.

### Step 4 — Fill in .env

Copy `.env.example` and fill in everything:

```env
# Discord
DISCORD_TOKEN=your_bot_token_here

# Roblox
ROBLOX_USER_ID=123456789       # bot owner's roblox user ID (used for group icon etc)
ROBLOX_GROUP_ID=12345678       # your group ID

# Channels (right-click → Copy ID)
LOG_CHANNEL_ID=111111111111111111
AID_REQUEST_CHANNEL_ID=222222222222222222
INACTIVITY_CHANNEL_ID=333333333333333333
DISCHARGE_REQUEST_CHANNEL_ID=444444444444444444
DISCHARGE_LOG_CHANNEL_ID=555555555555555555
EVENT_LOG_CHANNEL_ID=666666666666666666    # optional
REPORT_CHANNEL_ID=777777777777777777       # optional

# Roles (right-click role → Copy ID)
INACTIVITY_ROLE_ID=888888888888888888
INACTIVITY_COOLDOWN_ROLE_ID=999999999999999999
DISCHARGE_PING_ROLE_ID=111111111111111112
DISCHARGE_LOG_PING_ROLE_ID=111111111111111113
EP_MANAGER_ROLE_ID=111111111111111114      # who can run /ep edit and /log
LOG_ROLE_ID=111111111111111115             # optional, separate role for /log only

# API (optional but recommended)
API_KEY=some_secret_key_here   # required to use the REST API, leave blank to disable auth
API_HOST=0.0.0.0
API_PORT=8080

# AI features (optional)
ANTHROPIC_API_KEY=sk-ant-...   # needed for OCR fallback and weekly report summaries
CLAUDE_MODEL=claude-sonnet-4-6
CLAUDE_VISION_ENABLED=true     # set false to stop screenshots being sent to Anthropic

# Database encryption (optional but recommended)
# generate a key: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
DB_ENCRYPTION_KEY=

# Logging mode for /log command
# flexible (default) — screenshot optional, no screenshot opens manual text entry
# screenshot_required — screenshot always required
# manual_only         — always uses manual text entry, screenshot ignored
LOG_MODE=flexible

# Report settings
REPORT_UNIT_NAME=327th Star Corps
REPORT_TOP_EP_COUNT=10
REPORT_COLOR_PRIMARY=1B2A4A
REPORT_COLOR_ACCENT=C9A84C

# Google Sheets (optional)
ENABLE_SHEETS=false
GOOGLE_SHEETS_CREDS_FILE=credentials.json
GOOGLE_SHEET_ID=your_spreadsheet_id_here
GOOGLE_EVENT_LOG_TAB=Event Log    # name of the event log tab in the spreadsheet

# Feature toggles (set false to disable a command)
ENABLE_EP=true
ENABLE_LOG=true
ENABLE_REPORT=true
ENABLE_API=true
ENABLE_BACKUP=true
ENABLE_REQUEST_AID=true
ENABLE_INACTIVITY=true
ENABLE_DISCHARGE=true
ENABLE_VERIFY=true

# How often to sync EP records from Roblox group (hours)
EP_SYNC_INTERVAL_HOURS=6
```

### Step 5 — Configure Events

Events are defined in `discord-bot/events_config.json`. Edit this to add or change event types:

```json
[
  { "name": "Training",  "ep": 2, "type": "standard" },
  { "name": "Patrol",    "ep": 1, "type": "standard" },
  { "name": "Tryout",    "ep": 3, "type": "tryout"   },
  { "name": "Joint Op",  "ep": 4, "type": "standard" }
]
```

- `type: "tryout"` — enables the passed/failed split UI when logging
- `ep` — how much EP each attendee gets for this event type

### Step 6 — Google Sheets (optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com) and create a project
2. Enable the **Google Sheets API**
3. Go to **IAM & Admin → Service Accounts**, create a service account
4. Download the JSON key file and put it somewhere safe on your server
5. Set `GOOGLE_SHEETS_CREDS_FILE` to the path of that JSON file
6. Create a Google Sheets spreadsheet and copy its ID from the URL
7. Share the spreadsheet with the service account's email address (give Editor access)
8. Set `GOOGLE_SHEET_ID` to the spreadsheet ID
9. Set `ENABLE_SHEETS=true`

The bot will write two tabs:
- **Sheet1** — EP leaderboard, sorted highest to lowest, updated on the sync interval
- **Event Log** tab — every logged event with date, type, host, attendees, and EP totals

### Step 7 — Database Encryption (optional but recommended)

Generate a Fernet encryption key:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Paste the output into `DB_ENCRYPTION_KEY` in your `.env`. The bot will encrypt `bot_data.json` on the next save. If you add the key after the bot has already been running, it will migrate the existing plaintext file on the next write.

---

## Commands

### Member Commands

| Command | Description |
|---------|-------------|
| `/profile` | View your EP total and basic stats |
| `/verify username:<roblox_username>` | Link your Roblox account to Discord. Generates a unique code to put in your Roblox profile About section. |
| `/inactivity-notice` | File an absence notice with start/end dates and a reason |
| `/discharge` | Submit a discharge (leave) request |
| `/request-aid` | Submit a military aid request to leadership |

### Staff Commands

| Command | Description |
|---------|-------------|
| `/ep edit roblox_username:<name> ep_value:<number>` | Add or subtract EP from a member. Use a negative number to subtract. |
| `/log event_type:<type>` | Log an event. Attach a screenshot for OCR extraction, or leave it blank to type names manually. |
| `/gen-report` | Generate the weekly activity report as a Word document. Limited to 2 uses per week. |

### /log details

**With a screenshot:**
The bot runs OCR on the image to detect Roblox usernames, shows you the list, and lets you confirm, edit, or cancel before EP is awarded.

**Without a screenshot (manual mode):**
A text box pops up. Type one Roblox username per line. You can also paste Discord @mentions — the bot will look up their linked Roblox account if they've run `/verify`. Unresolvable mentions are shown as a warning.

**LOG_MODE options (set in .env):**
- `flexible` — screenshot optional (default)
- `screenshot_required` — screenshot always required, manual entry disabled
- `manual_only` — always uses manual text entry, screenshot is ignored

### /verify details

Members run `/verify username:TheirRobloxName`, get a 4-word code (e.g. `amber-falcon-storm-cedar`), paste it into their Roblox profile's About section, then click **Done**. The bot checks the live profile and links the accounts. The code expires after 15 minutes and is single-use.

Once verified, Discord @mentions in `/log` manual mode will automatically resolve to that member's Roblox username.

---

## EP Audit Log

Every `/ep edit` call is recorded in the database with:
- Who ran the command (Discord ID and username)
- Which Roblox account was affected
- Old EP value, new EP value, and the change amount
- Timestamp

This is stored in `bot_data.json` under `ep_audit_log` and is visible in the Discord log channel embed for each edit.

---

## REST API

Runs on port `8080` by default. Set `API_KEY` in your `.env` to require authentication — requests must include the header `X-API-Key: your_key`. Full interactive docs at `http://your-server:8080/docs`.

### EP endpoints

```
GET /user/{roblox_user_id}/ep          — EP record by Roblox user ID
GET /user/username/{username}/ep       — EP record by Roblox username
GET /users?page=1&per_page=50          — all EP records, sorted by EP
GET /users/leaderboard?limit=10        — top N members by EP
```

### Event endpoints

```
GET /events/week                        — all events logged this week
GET /events/week/summary               — totals for the current week (event count, EP, active members)
GET /events?page=1&per_page=50         — all events, newest first
GET /events?since=2026-03-01T00:00:00  — filter by date range (ISO 8601)
GET /events?until=2026-03-08T19:00:00
```

Week boundaries follow the same Sunday 19:00 UTC cutoff that the weekly report uses.

### Health

```
GET /health    — bot status, no auth required
```

---

## Running with systemd (keep it running after SSH disconnect)

Create `/etc/systemd/system/larp-bot.service`:

```ini
[Unit]
Description=327th Star Corps Discord Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/Larp_bot_ljs/discord-bot
ExecStart=/usr/bin/python3 main.py
Restart=on-failure
RestartSec=10
EnvironmentFile=/home/your_username/Larp_bot_ljs/discord-bot/.env

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable larp-bot
sudo systemctl start larp-bot
sudo systemctl status larp-bot   # check it's running
journalctl -u larp-bot -f        # live logs
```

---

## Recommended Server Specs

These are rough guidelines based on real usage. The bot is lightweight — most of the load is Discord API calls and occasional Roblox API lookups, not raw compute.

### By member count

| Guild size | RAM | CPU | Storage | Notes |
|------------|-----|-----|---------|-------|
| Under 100 members | 256 MB | 1 vCPU | 1 GB | Any cheap VPS works. Even a Raspberry Pi 4. |
| 100–500 members | 512 MB | 1 vCPU | 2 GB | Still very light. Most $4–6/mo VPS tiers are fine. |
| 500–2,000 members | 1 GB | 1–2 vCPU | 5 GB | Roblox group sync will take longer. EP sync interval can be stretched to 12h. |
| 2,000+ members | 2 GB | 2 vCPU | 10 GB | At this scale you might want to consider swapping `bot_data.json` for a real database. |

### What actually uses resources

- **RAM** — the JSON database is loaded entirely into memory. A 500-member group with full EP history and event logs is typically under 5 MB. Not a concern until you're storing thousands of records.
- **CPU** — nearly idle most of the time. Spikes slightly during OCR (pytesseract), Word doc generation (`/gen-report`), or Google Sheets sync. None of these are CPU-intensive enough to matter on any modern VPS.
- **Storage** — the database file, rate limit files, and generated reports are all small. The only thing that grows over time is the event log. Even a very active unit logging 20 events/week will only accumulate a few MB per year.
- **Network** — the bot makes outbound calls to Discord, Roblox, and optionally Google/Anthropic APIs. Inbound is just Discord gateway traffic (WebSocket) plus whatever hits your REST API port. Nothing unusual.
- **Anthropic API** — only used for OCR fallback (when pytesseract fails on a screenshot) and weekly report summaries. If you set `CLAUDE_VISION_ENABLED=false` and don't use `/gen-report`, no Claude API calls are made at all.

### OS

Any modern Linux distro works. Ubuntu 22.04 LTS or Debian 12 are the most straightforward. The install script is written for Debian/Ubuntu (`apt`). On other distros you'll need to install Tesseract-OCR manually.

Python 3.10 or newer is required (uses `int | None` union syntax and `match` in a few places).

---

## File Structure

```
discord-bot/
├── main.py                  bot entry point
├── events_config.json       event types and EP values
├── requirements.txt         Python dependencies
├── .env                     your config (never commit this)
│
├── cogs/
│   ├── ep.py                /ep edit
│   ├── log.py               /log
│   ├── verify.py            /verify
│   ├── profile.py           /profile
│   ├── report.py            /gen-report
│   ├── inactivity.py        /inactivity-notice
│   ├── discharge.py         /discharge
│   ├── request_aid.py       /request-aid
│   └── backup.py            channel visibility management
│
├── storage/
│   ├── database.py          JSON database with optional encryption
│   └── scheduler.py         background jobs (EP sync, cleanup, reports)
│
├── api/
│   └── server.py            FastAPI REST server
│
└── utils/
    ├── roblox_api.py        Roblox API client with caching
    ├── validators.py        input validation
    ├── rate_limit.py        per-user rate limiting with file persistence
    ├── report_builder.py    Word document generation
    ├── sheets.py            Google Sheets sync (EP + event log)
    ├── events.py            event config loader
    ├── week.py              week boundary calculations
    └── embeds.py            embed builders
```

---

<!-- AI_CONTEXT_BLOCK: This section is machine-readable context written for AI assistants. It was generated by AI and is intended to help another AI understand this codebase without direct file access. Human readers can ignore this section. -->

## [FOR AI ASSISTANTS] Codebase Summary

> **Note:** This section was written by an AI for AI. If you're a human, the rest of the README above covers everything you need. If you're an AI assistant helping a user who doesn't have direct file access to this repo, read this section to understand how the bot works before answering questions or making suggestions.

---

### What this is

A Discord bot (`discord.py 2.x` slash commands) for a Roblox military roleplay unit. It tracks Engagement Points (EP) earned by members at events, handles group management tasks (inactivity notices, discharge requests, aid requests), links Discord accounts to Roblox accounts, and exposes a REST API for external integrations.

---

### Core data store

Single JSON file: `discord-bot/bot_data.json`. Loaded entirely into memory at startup, written atomically on every mutation (temp file + `shutil.move`). Protected by an `asyncio.Lock` to prevent concurrent writes. Optionally encrypted at rest with Fernet symmetric encryption (`DB_ENCRYPTION_KEY` env var — if set, every read decrypts and every write encrypts). If the key is added to an existing plaintext install, the file migrates on next write.

The data dict has these top-level keys:
- `ep_records` — list of dicts: `{roblox_user_id, roblox_username, ep, discord_user_id, join_date, last_updated}`
- `event_log` — list of dicts: `{event_type, ep_awarded, participants: [roblox_username...], not_found: [...], host_discord_name, host_discord_id, logged_at (ISO UTC)}`
- `ep_audit_log` — list of dicts: `{editor_discord_id, editor_name, roblox_username, old_ep, new_ep, delta, timestamp}`
- `inactivity_notices` — active absence notices
- `cooldowns` — inactivity cooldown tracking
- `discharge_requests` — pending discharge requests
- `report_usage` — tracks `/gen-report` usage to enforce 2/week limit
- `pending_verifications` — short-lived verification tokens: `{discord_user_id, roblox_user_id, roblox_username, token, expires_at}`

All database operations are in `discord-bot/storage/database.py` (`BotDatabase` class). Key methods: `get_ep_record(roblox_user_id)`, `update_ep(roblox_user_id, new_ep, roblox_username)`, `get_ep_record_by_username(username)`, `get_all_ep_records()`, `add_event_log_entry(...)`, `get_all_event_log_entries()`, `get_events_in_range(start_dt, end_dt)`, `add_ep_audit_entry(...)`, `add_pending_verification(...)`, `get_pending_verification(discord_user_id)`, `remove_pending_verification(discord_user_id)`, `cleanup_expired_verifications()`, `link_discord_to_roblox(discord_user_id, roblox_user_id, roblox_username)`.

---

### Bot entry point

`discord-bot/main.py` — creates the bot with `commands.Bot`, attaches `database` and `roblox_api` as bot attributes, loads cogs based on feature-toggle env vars (`ENABLE_EP`, `ENABLE_LOG`, etc.), starts the REST API as an asyncio background task if `ENABLE_API=true`, starts the scheduler.

---

### Cogs (slash commands)

Each cog lives in `discord-bot/cogs/`. All use `@app_commands.command` for slash commands.

- **`ep.py`** — `/ep edit roblox_username ep_value`. Requires `EP_MANAGER_ROLE_ID`. Updates EP, writes audit entry, posts embed to `LOG_CHANNEL_ID`. Per-user rate limited (5 uses/60s, persisted to `rate_limits_ep.json`).
- **`log.py`** — `/log event_type [screenshot]`. Requires `EP_MANAGER_ROLE_ID` or `LOG_ROLE_ID`. Three modes controlled by `LOG_MODE` env var:
  - `flexible` (default) — screenshot optional; no screenshot triggers a Discord Modal for manual username entry
  - `screenshot_required` — screenshot always required
  - `manual_only` — always opens the Modal, screenshot ignored
  With a screenshot: downloads it, runs pytesseract OCR to extract Roblox usernames, shows a confirmation View. The Modal (`ManualUsernamesModal`) accepts one Roblox username or Discord `@mention` per line; mentions are resolved to Roblox usernames via the `discord_user_id` field in `ep_records`. Both paths end at `ConfirmLogView` for staff to confirm/edit before EP is awarded. Per-user rate limited (3 uses/300s, persisted to `rate_limits_log.json`).
- **`verify.py`** — `/verify username`. Generates a 4-word token from a 150-word pool using `secrets.choice` (~500M combinations). Stores it in `pending_verifications` with 15-min expiry. Shows a View with Done/Cancel buttons. Done: fetches live Roblox profile description via `get_user_description` (never cached), does case-insensitive token search, links accounts if found, posts staff log embed. Cancel: removes pending token.
- **`profile.py`** — `/profile`. Shows the calling user's EP record (requires linked Roblox account via `/verify`).
- **`report.py`** — `/gen-report`. Generates a `.docx` weekly activity report using `python-docx`. Optionally adds an AI-written summary via Anthropic API (only top-5 EP values sent, not usernames). Limited to 2 uses/week per the Sunday 19:00 UTC boundary.
- **`inactivity.py`** — `/inactivity-notice`. Files absence notice, assigns `INACTIVITY_ROLE_ID`, posts to `INACTIVITY_CHANNEL_ID`.
- **`discharge.py`** — `/discharge`. Posts discharge request embed to `DISCHARGE_REQUEST_CHANNEL_ID`, pings `DISCHARGE_PING_ROLE_ID`.
- **`request_aid.py`** — `/request-aid`. Posts aid request embed to `AID_REQUEST_CHANNEL_ID`.
- **`backup.py`** — channel visibility management utilities (not a user-facing slash command).

---

### Background scheduler

`discord-bot/storage/scheduler.py` — APScheduler `AsyncIOScheduler`. Jobs:
- **EP sync** — every `EP_SYNC_INTERVAL_HOURS` hours. Fetches all members from the Roblox group via `get_group_members()` (paginated), upserts EP records (new members get 0 EP), then syncs to Google Sheets (`sync_ep_to_sheet`).
- **Google Sheets event sync** — runs alongside EP sync. Calls `sync_events_to_sheet` with all event log entries, writes to a second tab named `GOOGLE_EVENT_LOG_TAB` (default: "Event Log").
- **Verification cleanup** — every 15 minutes. Calls `cleanup_expired_verifications()` to remove tokens past their `expires_at`.
- **Weekly report** — optional auto-post of the weekly report to `REPORT_CHANNEL_ID` on Sunday at 19:00 UTC.

---

### REST API

`discord-bot/api/server.py` — FastAPI app running in the same event loop via `uvicorn.Server`. Shares the `BotDatabase` instance via `app.state.database`. Authentication: `X-API-Key` header checked against `API_KEY` env var (if unset, all requests pass with a startup warning). The `/health` and `/` endpoints skip auth.

Endpoints:
- `GET /user/{roblox_user_id}/ep` — EP record by Roblox numeric ID
- `GET /user/username/{roblox_username}/ep` — EP record by Roblox username
- `GET /users?page=1&per_page=50` — all EP records sorted by EP desc, paginated (max 100/page)
- `GET /users/leaderboard?limit=10` — top N members by EP with rank field
- `GET /events/week` — all events in the current week (Sunday 19:00 UTC boundary), newest first
- `GET /events/week/summary` — total events, total EP, unique members, and events-by-type breakdown for the week
- `GET /events?page=1&per_page=50&since=<ISO>&until=<ISO>` — all events, newest first, with optional ISO 8601 date range filtering, paginated
- `GET /health` — bot status, record count, no auth required

---

### Roblox API client

`discord-bot/utils/roblox_api.py` — `RobloxAPICache` class. Uses `aiohttp` for all requests. Caches avatars, group icons, and user ID lookups for 1 hour (in-memory dict). Profile descriptions are never cached (needed fresh for `/verify`). Retry logic: 3 attempts with 1/2/4s delays on 429 or timeout.

Key methods: `get_user_avatar(user_id)`, `get_group_icon(group_id)`, `get_group_members(group_id)` (paginated, 0.5s sleep between pages), `get_user_id_by_username(username)`, `get_username_by_id(user_id)`, `get_user_description(user_id)`.

---

### Google Sheets sync

`discord-bot/utils/sheets.py` — uses `gspread` + `google.oauth2.service_account`. Sync functions are async wrappers that run blocking gspread calls in `loop.run_in_executor`. Two functions: `sync_ep_to_sheet(ep_records)` writes to Sheet1 (Rank, Username, ID, EP, Discord ID, Last Updated), `sync_events_to_sheet(events)` writes to a configurable second tab (Date, Event Type, Host, Attendee count, EP Each, Total EP, Participant Names). Tab is created automatically if it doesn't exist.

---

### Rate limiting

`discord-bot/utils/rate_limit.py` — `RateLimiter` class. Sliding window per Discord user ID. Optional `persist_path` saves the usage history to a JSON file on every check so limits survive bot restarts. Each cog instantiates its own limiter with its own file.

---

### Configuration summary (env vars)

All config via `.env` file. Key vars:
- `DISCORD_TOKEN` — required
- `ROBLOX_USER_ID`, `ROBLOX_GROUP_ID` — required for group sync
- `*_CHANNEL_ID`, `*_ROLE_ID` — Discord IDs for all channels and roles
- `API_KEY` — REST API authentication key (leave blank to disable auth, not recommended)
- `API_HOST`, `API_PORT` — defaults `0.0.0.0:8080`
- `ANTHROPIC_API_KEY`, `CLAUDE_MODEL`, `CLAUDE_VISION_ENABLED` — for OCR fallback and report summaries
- `DB_ENCRYPTION_KEY` — Fernet key for at-rest DB encryption
- `LOG_MODE` — `flexible` | `screenshot_required` | `manual_only`
- `EP_SYNC_INTERVAL_HOURS` — how often to sync from Roblox group (default 6)
- `ENABLE_SHEETS`, `GOOGLE_SHEETS_CREDS_FILE`, `GOOGLE_SHEET_ID`, `GOOGLE_EVENT_LOG_TAB` — Google Sheets integration
- `ENABLE_EP`, `ENABLE_LOG`, `ENABLE_REPORT`, `ENABLE_API`, `ENABLE_BACKUP`, `ENABLE_REQUEST_AID`, `ENABLE_INACTIVITY`, `ENABLE_DISCHARGE`, `ENABLE_VERIFY` — feature toggles
- `REPORT_UNIT_NAME`, `REPORT_TOP_EP_COUNT`, `REPORT_COLOR_PRIMARY`, `REPORT_COLOR_ACCENT` — report branding

<!-- END AI_CONTEXT_BLOCK -->
