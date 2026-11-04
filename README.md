<div align="center">
  <img src="assets/banner.svg" alt="Yadara — bilingual Telegram reminder bot" width="100%">

  # Yadara | یادآرا

  **English** · [فارسی](README.fa.md)

  **Personal reminders, one Telegram message away.**

  **Simple to use. Free to self-host. Built for two languages.**

  [Features](#features) · [Quick start](#quick-start) · [Commands](#commands) · [Development](#development)
</div>

---

Yadara is an open-source Telegram reminder bot with Persian and English interfaces. Create reminders using supported natural-language patterns or a guided conversation. It uses rule-based parsing, not a paid AI service.

> **Status:** Initial working version. Automated tests and simulated bot conversations pass, but a live Telegram connection has not yet been verified. Do not rely on the bot alone for medication or other critical reminders.

## See it in action

Illustrative conversation (the date depends on the current day and time zone):

```text
You:     remind me to take medicine tomorrow at 3 pm
Yadara:  How often should this reminder repeat?
You:     Once
Yadara:  Title: take medicine
         Time: 2026-11-05 15:00 (Asia/Tehran)
         Repeat: Once
         Confirm?
You:     ✅ Confirm
Yadara:  Saved ✅ ID: 1
```

## Features

| | Feature | What it does |
| --- | --- | --- |
| 🌍 | **Two languages** | Persian and English interfaces, selected independently by each user. |
| 💬 | **Natural input** | Type a supported phrase or follow the guided conversation. |
| 🔁 | **Flexible schedules** | Set a one-time, daily or weekly reminder. |
| 🕒 | **Local time** | Choose your own IANA time zone and review the date before saving. |
| 🗂️ | **Stay organized** | List, edit and delete reminders; retry failed deliveries. |
| 💾 | **Self-hosted** | Store reminders in SQLite with no paid AI API required. |

## Quick start

### 1. Get ready

Requirements: Python 3.10+, network access to Telegram, and a bot token from [BotFather](https://t.me/BotFather).

### 2. Install and configure

```bash
git clone <your-repository-url>
cd yadara-telegram-reminder
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env
# Edit .env and set BOT_TOKEN
python -m yadara
```

### 3. Say hello

Open your bot and send `/start`, then `/language en`. The default time zone is `Asia/Tehran`; set your own using `/timezone Europe/London`. On Windows, install `tzdata` if system time-zone data is unavailable. Never commit your token.

### Docker

Create `.env` from `.env.example`, set the token, then run:

```bash
docker compose up -d --build
docker compose logs -f
```

Data is stored in a Docker volume. Run **only one instance** of the bot per database. Keep `DATABASE_PATH` under `/app/data` in Docker for persistence.

## Commands

| Command | Description |
| --- | --- |
| `/start`, `/help` | Start or show help |
| `/language en`, `/language fa` | Change your interface language |
| `/list`, `/list 2` | List active reminders, page by page |
| `/edit 123`, `/delete 123` | Edit title/time or delete a reminder |
| `/timezone Europe/London` | Set your IANA time zone |
| `/failed`, `/retry 123` | View the latest 50 failed deliveries or retry one |
| `/cancel` | Cancel the current flow |

Language and time zone are independent. Existing one-time reminders retain their actual time when the time zone changes; recurring reminders retain their saved time zone. Lists display dates in the user's current time zone.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `BOT_TOKEN` | required | Telegram bot token |
| `DATABASE_PATH` | `data/yadara.db` | SQLite database location |
| `DEFAULT_TIMEZONE` | `Asia/Tehran` | Default IANA time zone |
| `POLL_INTERVAL_SECONDS` | `15` | Due-reminder polling interval |

## Supported input and limitations

English mode supports `today`, `tomorrow`, or ISO dates such as `2027-05-16`, plus a numeric time: `tomorrow at 3 pm`, `today at 15:30`. Specify am/pm for hours 1–12. Persian mode accepts today, tomorrow, the day after tomorrow and numeric Jalali dates. Natural-language support is rule-based and deliberately limited; weekdays, month names and relative durations such as “in two hours” are not supported.

The server must be online and connected. After downtime, overdue one-time reminders are sent; missed occurrences of a recurring reminder result in one delivery before scheduling the next future occurrence. Temporary failures are retried up to 10 times; permanent failures are listed under `/failed`. Exactly-once delivery, timeliness and message visibility cannot be guaranteed; a crash after sending but before recording success can cause duplicates. A concurrent delete may not stop an already in-flight message.

Ambiguous or nonexistent initial local times are rejected. Recurrences use the first occurrence of an ambiguous time; nonexistent times move forward to a valid local time, while preserving the original wall-clock time for later occurrences. Unfinished conversations are lost on restart; confirmed reminders are stored in SQLite. Hosting may incur costs.

Reminders and user IDs are stored in the database. Restrict access to it and to backups. Use SQLite's backup API when WAL is enabled instead of copying only the live database file:

```bash
python -c "import sqlite3; a=sqlite3.connect('data/yadara.db'); b=sqlite3.connect('backup.db'); a.backup(b); b.close(); a.close()"
```

Test restoration before relying on backups.

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

`yadara/` contains the bot, parsers and storage layer; `tests/` contains automated tests; `.github/workflows/` contains CI; and `docs/` contains the Persian product and architecture notes. Tests include simulated conversations, not live Telegram integration.

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [MIT license](LICENSE).
