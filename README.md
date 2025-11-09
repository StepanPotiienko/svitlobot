# Power Outage Reminder (ДТЕК Telegram → Google Calendar)

This project fetches "Графіки відключення світла" from ДТЕК's Telegram channel and automatically creates reminders in Google Calendar.

## What you get

- Python package `power_outage_remainder` with:
  - `scraper` — Telegram channel scraper that detects and parses outage schedules
  - `calendar_integration` — Google Calendar helper (OAuth flow + event creation, plus listing/deleting helpers)
  - `cli` and `scripts/run.py` — runner/CLI
- Tests (pytest) for the parser and calendar
- `requirements.txt`, `.env.example`, `Makefile`

## Key behaviour changes (recent)

- The scraper now produces timezone-aware ISO datetimes (e.g. `2025-11-10T08:00:00+02:00`).
- The CLI uses a today/tomorrow pruning window: only events scheduled for today or tomorrow (in the configured timezone) are kept and created. This avoids creating reminders for past dates.
- You can filter by group with `--group` (e.g. `--group 1.2`).
- A safe calendar cleanup mode was added: `--cleanup` lists candidate outage events outside the today/tomorrow window and optionally deletes them; pass `--yes` to skip confirmation.

## Prerequisites

### 1. Telegram API Credentials

You need Telegram API credentials to access channel messages:

1. Go to https://my.telegram.org
2. Log in with your phone number
3. Click "API development tools"
4. Create an app and get your `api_id` and `api_hash`

### 2. Google Calendar API Credentials

You need OAuth 2.0 credentials to create calendar events:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the Google Calendar API
4. Create OAuth 2.0 credentials (Desktop app type)
5. Download the credentials JSON file

## Setup

### 1. Create and activate a virtualenv (macOS / zsh):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Copy `.env.example` to `.env` and fill values:

```bash
cp .env.example .env
```

Edit `.env` with your credentials and optional settings:

- `TELEGRAM_API_ID` — your Telegram API ID (from my.telegram.org)
- `TELEGRAM_API_HASH` — your Telegram API hash
- `TELEGRAM_PHONE` — your phone number (e.g., +380123456789)
- `TELEGRAM_CHANNEL` — DTEK channel username (e.g., @dtek_kyiv or @yasno_kiev)
- `GOOGLE_CREDENTIALS_PATH` — path to OAuth client secrets JSON (e.g., `./credentials.json`)
- `GOOGLE_TOKEN_PATH` — token file path to store OAuth tokens (e.g., `token.json`)
- `DEFAULT_CALENDAR_ID` — calendar ID to insert events to (or `primary` for default)
- `DEFAULT_TIMEZONE` — timezone used for parsing/deciding "today" (default: `Europe/Kyiv`)
- `MAX_MESSAGES` — max messages to fetch from channel (default: 50)

> Note: The tool now produces timezone-aware datetimes. If you need to change the timezone used to decide "today/tomorrow" (for pruning and cleanup), set `DEFAULT_TIMEZONE` to a valid IANA timezone string (e.g. `UTC`, `Europe/Kyiv`).

### 3. Run the scraper (dry-run first to test):

```bash
python -m power_outage_remainder --dry-run
# or
python scripts/run.py --dry-run
```

On the first run:

- Telegram will send you a verification code — enter it when prompted
- Google will open a browser for OAuth authentication

### 4. Run for real (create calendar events):

```bash
python -m power_outage_remainder
# or
python scripts/run.py
```

## CLI options (use `python -m power_outage_remainder --help` for full list)

- `--dry-run` — parse and print events without creating them
- `--group <GROUP>` — only create events for the specified group (e.g. `1.2`)
- `--cleanup` — list outage events in the calendar outside the today/tomorrow window and allow deleting them
- `--yes` — when used with `--cleanup` skip the confirmation prompt and delete immediately (use with care)
- `--limit N` — number of Telegram messages to fetch (overrides `MAX_MESSAGES`)

## How it works

1. **Fetch messages**: Connects to Telegram using Telethon and fetches recent messages from the specified channel
2. **Detect outages**: Filters messages that contain outage-related keywords (відключення, графік, etc.) and time patterns
3. **Parse details**: Extracts:
   - Start/end times (handles formats like "08:00-12:00", "з 14:00 до 18:00") and produces timezone-aware ISO datetimes
   - Dates (handles formats like "10.11", "10 листопада")
   - Locations/groups (Група 1, Група 2.1, etc.)
   - Descriptions (full message text)
4. **Prune**: The CLI keeps only outages for today and tomorrow (in the `DEFAULT_TIMEZONE`) to avoid creating reminders for past dates
5. **Create events**: Uses Google Calendar API to create calendar events with red color for visibility

## Cleanup mode (safe deletion)

- `--cleanup` searches calendar events in a ±30 day window and filters events whose summary starts with the outage prefix (`⚡ Відключення світла`).
- It prints candidate events outside today/tomorrow and asks for confirmation before deletion. Use `--yes` to skip confirmation.
- This is a best-effort safety measure — please review the list before confirming deletion.

## Common Telegram Channels

- **Kyiv DTEK**: `@dtek_kyiv`
- **YASNO (Kyiv region)**: `@yasno_kiev`
- **Odesa DTEK**: `@dtek_odessa`

Check the official DTEK or YASNO websites for their Telegram channels.

## Testing

Run tests:

```bash
pytest -v
# or
make test
```

## Notes

- The scraper uses pattern matching and keywords to detect outage messages — DTEK's message format may vary
- The first Telegram auth creates a session file (`session_name.session`) which is reused for subsequent runs
- Calendar events are color-coded red (colorId: 11) for easy visibility
- Overnight outages (e.g., 23:00-02:00) are handled correctly

## Troubleshooting

**"No module named 'telethon'"**: Run `pip install -r requirements.txt`

**Telegram auth fails**: Make sure your phone number is in international format (+380...)

**"No outage schedules found"**: Try increasing `MAX_MESSAGES` or check the channel name

**Google auth fails**: Ensure the credentials JSON is valid and Calendar API is enabled in Google Cloud Console

## Issues / Contributions

Open an issue or send a patch. This project is MIT licensed.
