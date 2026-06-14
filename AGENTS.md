# AGENTS.md

## Project

Single Python script that checks IMAP mailboxes for matching emails and sends ntfy.sh notifications. Designed to run on a Coolify cron schedule, exit after each run, and consume zero resources between executions.

## Commands

- Syntax check: `python3 -m py_compile check-payment-email.py`
- Run locally: `docker compose up --build`
- No test suite, no lint, no typecheck, no pip dependencies (stdlib only)

## Architecture

- **Single file**: `check-payment-email.py` is the entire application
- **Dockerfile**: `python:3.12-alpine`, no `pip install` needed
- **docker-compose.yml**: `restart: "no"` is intentional — Coolify's scheduler starts the container on cron, it exits after completion. The `environment:` block defines all env vars with defaults so Coolify pre-fills them in the UI.
- **Local `.env` still works**: Docker Compose auto-loads `.env` and substitutes values via `${VAR:-default}` syntax.

## Conventions

- Commit format: `TYPE description` on first line, blank line, then bullet details (e.g., `INIT IMAP Email Check with Ntfy Notification`)
- `.env` is gitignored; always use `.env.example` as the template
- Never commit credentials or `.env` files

## Environment Variables

All config via env vars. See `.env.example` for full list. Required: `IMAP_HOST`, `IMAP_EMAIL`, `IMAP_PASSWORD`, `NTFY_URL`. At least one of `EMAIL_SENDER` or `EMAIL_SUBJECT` must be set.

Custom notification messages supported via `MESSAGE_ON_FOUND`, `MESSAGE_ON_NOT_FOUND`, `MESSAGE_EMAIL_DETAIL` with placeholder substitution (`{count}`, `{lookback_hours}`, `{sender}`, `{subject}`, `{date}`). Per-email details toggle via `NOTIFY_EMAIL_DETAILS` (default `true`).

## Key Design Notes

- IMAP `SINCE` is date-only, so the script fetches headers afterward and does precise time filtering in Python
- Uses `RFC822.HEADER` fetch (headers only, not full bodies) for speed
- `mail.select()` uses `readonly=True` — never modifies mailbox state
