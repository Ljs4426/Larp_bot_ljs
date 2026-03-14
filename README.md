# Larp Bot

A Discord bot for Roblox military units. Tracks Engagement Points (EP), logs events, handles inactivity notices, discharge requests, aid requests, and links Discord accounts to Roblox accounts. Comes with a REST API so you can pull data into external tools.

---

## What it does

| Feature | Summary |
|---------|---------|
| **EP tracking** | Staff add or subtract EP from members. Every change is logged with who did it and when. |
| **Event logging** | Log events with a screenshot — the bot reads the names from the image automatically. Or type them manually. EP is awarded to everyone in the list. |
| **Roblox verification** | Members link their Roblox account to their Discord by pasting a short code into their Roblox profile. |
| **Inactivity notices** | Members file absence notices with start/end dates. They get an inactivity role automatically. |
| **Discharge requests** | Members submit leave requests. The request posts to a staff channel and pings the right role. |
| **Aid requests** | Members request backup/support from leadership via a form. |
| **Weekly reports** | Generate a Word document summary of the week's activity. Optionally auto-posts on Sunday. |
| **REST API** | Read-only HTTP API for EP records, event logs, leaderboard, and weekly summaries. |
| **Google Sheets sync** | Optionally push the EP leaderboard and event log to a spreadsheet on a schedule. |

---

## Requirements

- Linux (Ubuntu 22.04 or Debian 12 recommended)
- Python 3.10 or newer
- Tesseract-OCR (for reading screenshots — the install script handles this)

---

## Quick Install

Run the install script. It installs Python dependencies, Tesseract-OCR, and everything else automatically:

```bash
bash <(curl -sSL https://raw.githubusercontent.com/Ljs4426/Larp_bot_ljs/main/install.sh)
```

Then configure and start:

```bash
cd Larp_bot_ljs/discord-bot
cp .env.example .env
nano .env
python3 main.py
```

---

## Full Setup Guide

### Step 1 — Create the Discord bot

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications) and click **New Application**
2. Name it, then go to the **Bot** tab
3. Under **Privileged Gateway Intents**, turn on:
   - **Server Members Intent**
   - **Message Content Intent**
4. Click **Reset Token**, copy the token — this is your `DISCORD_TOKEN`
5. Go to **OAuth2 → URL Generator**
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: Send Messages, Embed Links, Attach Files, Read Message History, Add Reactions, Manage Roles, Kick Members
6. Copy the generated URL, open it in a browser, and invite the bot to your server

---

### Step 2 — Get your Discord IDs

Turn on Developer Mode: **User Settings → Advanced → Developer Mode**

Right-click any server, channel, or role and click **Copy ID**.

You need IDs for the following. Create these channels in your server first if they don't exist:

| Variable | What it's for |
|----------|--------------|
| `LOG_CHANNEL_ID` | Where EP edits and event logs get posted |
| `AID_REQUEST_CHANNEL_ID` | Where `/request-aid` submissions go |
| `INACTIVITY_CHANNEL_ID` | Where inactivity notices get posted |
| `DISCHARGE_REQUEST_CHANNEL_ID` | Where discharge requests go for staff to review |
| `DISCHARGE_LOG_CHANNEL_ID` | Log channel for approved/denied discharges |
| `EVENT_LOG_CHANNEL_ID` | *(optional)* Where event log embeds post |
| `REPORT_CHANNEL_ID` | *(optional)* Where the weekly report auto-posts |

And role IDs:

| Variable | What it's for |
|----------|--------------|
| `INACTIVITY_ROLE_ID` | Role given to members on inactivity |
| `INACTIVITY_COOLDOWN_ROLE_ID` | Role given after inactivity ends (cooldown period) |
| `DISCHARGE_PING_ROLE_ID` | Role pinged when a new discharge request comes in |
| `DISCHARGE_LOG_PING_ROLE_ID` | Role pinged in the discharge log channel |
| `EP_MANAGER_ROLE_ID` | Who can use `/ep edit` and `/log` |
| `LOG_ROLE_ID` | *(optional)* Separate role that can use `/log` but not `/ep edit` |

---

### Step 3 — Get your Roblox IDs

**Group ID** — your group URL looks like `roblox.com/groups/12345678/YourGroup`. The number is your group ID.

**User ID** — go to your Roblox profile. The number in the URL is your user ID. This is used for pulling the group icon in embeds.

---

### Step 4 — Fill in `.env`

```env
# Discord
DISCORD_TOKEN=your_bot_token_here

# Roblox
ROBLOX_USER_ID=123456789
ROBLOX_GROUP_ID=12345678

# Channels
LOG_CHANNEL_ID=111111111111111111
AID_REQUEST_CHANNEL_ID=222222222222222222
INACTIVITY_CHANNEL_ID=333333333333333333
DISCHARGE_REQUEST_CHANNEL_ID=444444444444444444
DISCHARGE_LOG_CHANNEL_ID=555555555555555555
EVENT_LOG_CHANNEL_ID=666666666666666666
REPORT_CHANNEL_ID=777777777777777777

# Roles
INACTIVITY_ROLE_ID=888888888888888888
INACTIVITY_COOLDOWN_ROLE_ID=999999999999999999
DISCHARGE_PING_ROLE_ID=111111111111111112
DISCHARGE_LOG_PING_ROLE_ID=111111111111111113
EP_MANAGER_ROLE_ID=111111111111111114
LOG_ROLE_ID=111111111111111115

# REST API
API_KEY=some_secret_key_here
API_HOST=0.0.0.0
API_PORT=8080

# AI features (optional — needed for OCR fallback and report summaries)
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-6
CLAUDE_VISION_ENABLED=true

# Database encryption (optional but recommended)
# Generate a key: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
DB_ENCRYPTION_KEY=

# Logging mode for /log
# flexible (default) — screenshot optional
# screenshot_required — screenshot always required
# manual_only — always manual text entry
LOG_MODE=flexible

# Report branding
REPORT_UNIT_NAME=Larp Bot
REPORT_TOP_EP_COUNT=10
REPORT_COLOR_PRIMARY=1B2A4A
REPORT_COLOR_ACCENT=C9A84C

# Google Sheets (optional)
ENABLE_SHEETS=false
GOOGLE_SHEETS_CREDS_FILE=credentials.json
GOOGLE_SHEET_ID=your_spreadsheet_id_here
GOOGLE_EVENT_LOG_TAB=Event Log

# Feature toggles — set false to disable a command
ENABLE_EP=true
ENABLE_LOG=true
ENABLE_REPORT=true
ENABLE_API=true
ENABLE_BACKUP=true
ENABLE_REQUEST_AID=true
ENABLE_INACTIVITY=true
ENABLE_DISCHARGE=true
ENABLE_VERIFY=true

# How often to sync EP records from Roblox (hours)
EP_SYNC_INTERVAL_HOURS=6
```

---

### Step 5 — Configure event types

Edit `discord-bot/events_config.json` to define what events exist and how much EP each one gives:

```json
[
  { "name": "Training",  "ep": 2, "type": "standard" },
  { "name": "Patrol",    "ep": 1, "type": "standard" },
  { "name": "Tryout",    "ep": 3, "type": "tryout"   },
  { "name": "Joint Op",  "ep": 4, "type": "standard" }
]
```

- `type: "standard"` — normal event, all attendees get EP
- `type: "tryout"` — shows a pass/fail split when logging so you can track outcomes separately
- `ep` — how much EP each attendee earns for this event type

Add as many event types as you want. They show up as options in the `/log` command automatically.

---

### Step 6 — Database encryption (optional but recommended)

All data is stored in `bot_data.json`. To encrypt it at rest:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Paste the output into `DB_ENCRYPTION_KEY` in your `.env`. The file will be encrypted on the next save. If you add this key after the bot has been running for a while, it migrates the existing plaintext file automatically on the next write.

If you lose this key, the database is unrecoverable. Back it up somewhere safe.

---

### Step 7 — Google Sheets (optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com) and create a project
2. Enable the **Google Sheets API**
3. Go to **IAM & Admin → Service Accounts** and create a service account
4. Download the JSON credentials file and save it on your server
5. Set `GOOGLE_SHEETS_CREDS_FILE` to the path of that file
6. Create a Google Sheets spreadsheet and copy its ID from the URL
7. Share the spreadsheet with the service account's email (give it **Editor** access)
8. Set `GOOGLE_SHEET_ID` to the spreadsheet ID
9. Set `ENABLE_SHEETS=true`

The bot writes two tabs:
- **Sheet1** — EP leaderboard sorted highest to lowest, updated every sync interval
- **Event Log** — every logged event with date, type, host, attendee count, and EP totals

---

### Step 8 — Start the bot

```bash
cd Larp_bot_ljs/discord-bot
python3 main.py
```

Slash commands register automatically on startup. They may take up to an hour to appear in Discord globally, or instantly if you register them to a specific server (the default behavior).

---

## Commands

### Member commands

These are available to everyone in the server.

| Command | What it does |
|---------|-------------|
| `/profile` | Shows your EP total, rank, and when you joined |
| `/verify username:<roblox_username>` | Links your Roblox account to your Discord account |
| `/inactivity-notice` | Files an absence notice with a start date, end date, and reason |
| `/discharge` | Submits a discharge (leave) request to staff |
| `/request-aid` | Sends a military aid request to leadership |

---

### Staff commands

Requires the `EP_MANAGER_ROLE_ID` role (or `LOG_ROLE_ID` for `/log`).

| Command | What it does |
|---------|-------------|
| `/ep edit roblox_username:<name> ep_value:<number>` | Add or subtract EP. Use a negative number to subtract. Rate limited to 5 uses per 60 seconds. |
| `/log event_type:<type>` | Log an event and award EP to attendees. Optionally attach a screenshot. Rate limited to 3 uses per 5 minutes. |
| `/gen-report` | Generates a Word document (.docx) weekly activity report. Limited to 2 uses per week. |

---

### How `/log` works

**With a screenshot attached:**
The bot runs OCR on the image to pull out Roblox usernames. It shows you the detected list and you confirm, edit, or cancel before any EP is awarded. If OCR misses names or picks up garbage, you can correct the list before confirming.

**Without a screenshot:**
A text box opens. Type one Roblox username per line. You can also paste Discord @mentions — the bot looks up the linked Roblox username if that person has run `/verify`. Any mentions it can't resolve are flagged as a warning before you confirm.

**LOG_MODE setting:**
- `flexible` — screenshot is optional. No screenshot = text box opens automatically. This is the default.
- `screenshot_required` — staff must attach a screenshot every time. Manual entry is disabled.
- `manual_only` — always opens the text box. Screenshots are ignored even if attached.

---

### How `/verify` works

1. Member runs `/verify username:TheirRobloxName`
2. Bot generates a short 4-word code like `amber-falcon-storm-cedar` and shows it in Discord
3. Member pastes the code into the **About** section of their Roblox profile
4. Member clicks **Done** in Discord
5. Bot checks the live Roblox profile for the code and links the accounts

The code expires after 15 minutes and can only be used once. Once verified, the member's Discord @mention will resolve to their Roblox username automatically when staff use `/log` in manual mode.

---

## EP audit log

Every `/ep edit` is stored permanently with:
- The Discord account that ran the command
- Which Roblox account was changed
- The old EP value, new EP value, and the difference
- Timestamp

This is in `bot_data.json` under `ep_audit_log` and also appears in the Discord log channel embed every time an edit is made.

---

## REST API

The API runs on port `8080` by default and is read-only. It shares data directly with the bot — no separate database connection needed.

**Authentication:** Set `API_KEY` in `.env`. Every request (except `/health`) must include the header:
```
X-API-Key: your_key_here
```

If `API_KEY` is not set, all requests are allowed but the bot will log a warning on startup. Don't leave it open in production.

**Interactive docs:** `http://your-server:8080/docs` — Swagger UI with all endpoints, parameters, and live request testing.

---

### `GET /health`

No authentication required. Returns bot status and record count. Good for uptime monitoring.

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2026-03-14T18:00:00+00:00",
  "ep_records": 142
}
```

---

### `GET /user/{roblox_user_id}/ep`

Fetch one member's EP record by their Roblox numeric user ID.

**Example:**
```
GET /user/123456789/ep
X-API-Key: your_key
```

**Response:**
```json
{
  "roblox_user_id": 123456789,
  "roblox_username": "CoolSoldier",
  "ep": 47,
  "discord_user_id": 987654321012345678,
  "join_date": "2025-11-01T00:00:00",
  "last_updated": "2026-03-12T14:30:00"
}
```

Returns `404` if no record exists for that ID.

---

### `GET /user/username/{roblox_username}/ep`

Same as above but look up by Roblox username instead of ID. Case-insensitive.

**Example:**
```
GET /user/username/CoolSoldier/ep
X-API-Key: your_key
```

Same response shape as above.

---

### `GET /users`

All EP records, sorted by EP highest to lowest, paginated.

**Query parameters:**

| Parameter | Default | Max | Description |
|-----------|---------|-----|-------------|
| `page` | `1` | — | Page number (1-based) |
| `per_page` | `50` | `100` | Results per page |

**Example:**
```
GET /users?page=1&per_page=25
X-API-Key: your_key
```

**Response:**
```json
{
  "total": 142,
  "page": 1,
  "per_page": 25,
  "results": [
    {
      "roblox_user_id": 123456789,
      "roblox_username": "CoolSoldier",
      "ep": 47,
      "discord_user_id": 987654321012345678,
      "join_date": "2025-11-01T00:00:00",
      "last_updated": "2026-03-12T14:30:00"
    },
    ...
  ]
}
```

---

### `GET /users/leaderboard`

Top N members by EP. Includes a `rank` field. Easier to use than `/users` when you just want the top list.

**Query parameters:**

| Parameter | Default | Max | Description |
|-----------|---------|-----|-------------|
| `limit` | `10` | `100` | How many entries to return |

**Example:**
```
GET /users/leaderboard?limit=5
X-API-Key: your_key
```

**Response:**
```json
[
  {
    "rank": 1,
    "roblox_user_id": 111111111,
    "roblox_username": "TopGun",
    "ep": 120,
    "discord_user_id": 222222222222222222
  },
  {
    "rank": 2,
    "roblox_user_id": 333333333,
    "roblox_username": "SecondPlace",
    "ep": 98,
    "discord_user_id": null
  },
  ...
]
```

`discord_user_id` is `null` if that member has not run `/verify`.

---

### `GET /events/week`

All events logged in the current week, newest first. The week boundary is **Sunday at 19:00 UTC** — the same cutoff used by the weekly report.

**Example:**
```
GET /events/week
X-API-Key: your_key
```

**Response:**
```json
[
  {
    "event_type": "Training",
    "ep_awarded": 2,
    "participant_count": 14,
    "participants": ["CoolSoldier", "AnotherGuy", "..."],
    "not_found": ["unknownname123"],
    "host_discord_name": "CommanderDude#0001",
    "logged_at": "2026-03-13T20:15:00"
  },
  ...
]
```

`not_found` contains any names that were in the log but had no matching EP record (e.g. a typo or someone not yet synced).

---

### `GET /events/week/summary`

Totals for the current week — useful for dashboards.

**Example:**
```
GET /events/week/summary
X-API-Key: your_key
```

**Response:**
```json
{
  "week_start": "2026-03-08T19:00:00+00:00",
  "week_end": "2026-03-15T19:00:00+00:00",
  "total_events": 7,
  "total_ep": 93,
  "unique_members": 31,
  "events_by_type": {
    "Training": 4,
    "Patrol": 2,
    "Joint Op": 1
  }
}
```

- `total_ep` — sum of EP awarded across all events this week
- `unique_members` — number of distinct Roblox usernames that appeared in at least one event
- `events_by_type` — breakdown of how many events of each type were logged

---

### `GET /events`

All events ever logged, newest first, with optional date range filtering. Paginated.

**Query parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `page` | `1` | Page number |
| `per_page` | `50` | Results per page (max 100) |
| `since` | — | Only return events at or after this ISO 8601 datetime |
| `until` | — | Only return events before this ISO 8601 datetime |

**Examples:**

All events, newest first:
```
GET /events?page=1&per_page=50
```

Events from a specific date range:
```
GET /events?since=2026-03-01T00:00:00&until=2026-03-08T19:00:00
```

Events from a specific date forward:
```
GET /events?since=2026-03-01T00:00:00
```

**Response:**
```json
{
  "total": 48,
  "page": 1,
  "per_page": 50,
  "results": [
    {
      "event_type": "Patrol",
      "ep_awarded": 1,
      "participant_count": 8,
      "participants": ["Alpha1", "Bravo2", "..."],
      "not_found": [],
      "host_discord_name": "StaffMember#1234",
      "logged_at": "2026-03-10T21:00:00"
    },
    ...
  ]
}
```

---

### API error responses

| Status | Meaning |
|--------|---------|
| `403` | Missing or wrong `X-API-Key` header |
| `404` | Record not found (user or event) |
| `400` | Bad request — usually a malformed `since`/`until` datetime |

All error responses follow this shape:
```json
{
  "detail": "No EP record found for Roblox username 'badname'"
}
```

---

## Keeping the bot running (systemd)

To keep the bot running after you disconnect from SSH and have it restart automatically on crashes:

Create `/etc/systemd/system/larp-bot.service`:

```ini
[Unit]
Description=Larp Bot Discord Bot
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

Then enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable larp-bot
sudo systemctl start larp-bot
sudo systemctl status larp-bot
journalctl -u larp-bot -f        # live logs
```

---

## Server requirements

The bot is lightweight. Most of the work is Discord and Roblox API calls, not compute.

| Member count | RAM | CPU | Storage |
|-------------|-----|-----|---------|
| Under 100 | 256 MB | 1 vCPU | 1 GB |
| 100–500 | 512 MB | 1 vCPU | 2 GB |
| 500–2,000 | 1 GB | 1–2 vCPU | 5 GB |
| 2,000+ | 2 GB | 2 vCPU | 10 GB |

**RAM** — the database loads fully into memory. A 500-member group with a full event history is typically under 5 MB.

**CPU** — nearly idle. Small spikes during OCR, report generation, or Sheets sync. Nothing that matters on any VPS.

**Storage** — grows slowly. Even a very active unit logging 20 events a week will only accumulate a few MB of event log per year.

**OCR / report API calls** — the Anthropic API is only used for OCR fallback (when pytesseract fails on a screenshot) and to write the summary in `/gen-report`. Set `CLAUDE_VISION_ENABLED=false` and avoid `/gen-report` if you don't want any external API calls.

Ubuntu 22.04 LTS or Debian 12 are the easiest. The install script uses `apt`. On other distros install Tesseract-OCR manually. Python 3.10 or newer is required.

---

## File structure

```
discord-bot/
├── main.py                  starts the bot, loads cogs
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
│   └── backup.py            channel visibility utilities
│
├── storage/
│   ├── database.py          JSON database, encryption, all read/write ops
│   └── scheduler.py         background jobs (EP sync, Sheets sync, report post)
│
├── api/
│   └── server.py            FastAPI REST server
│
└── utils/
    ├── roblox_api.py        Roblox API calls with caching
    ├── validators.py        input validation helpers
    ├── rate_limit.py        per-user rate limiting
    ├── report_builder.py    Word document generation
    ├── sheets.py            Google Sheets sync
    ├── events.py            loads events_config.json
    ├── week.py              Sunday 19:00 UTC week boundary logic
    └── embeds.py            Discord embed builders
```

---

## Troubleshooting

**Slash commands aren't showing up**
Wait up to an hour for global command sync. You can also kick the bot and re-invite it to force a refresh.

**OCR isn't picking up names from screenshots**
Make sure Tesseract is installed (`tesseract --version`). The install script handles this but if you set up manually, install it with `sudo apt install tesseract-ocr`. Set an `ANTHROPIC_API_KEY` for a fallback if pytesseract fails.

**Bot crashes on startup**
Check that all required env vars are set — `DISCORD_TOKEN`, `ROBLOX_GROUP_ID`, `ROBLOX_USER_ID`, and the channel/role IDs. Missing IDs cause immediate errors.

**API returns 403**
Make sure your request includes the header `X-API-Key: your_key` matching exactly what's in `API_KEY` in your `.env`.

**EP sync isn't running**
Check `EP_SYNC_INTERVAL_HOURS` in `.env` and make sure `ENABLE_EP=true`. The first sync runs on startup.
