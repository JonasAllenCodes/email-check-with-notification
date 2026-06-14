# Email Checker

A lightweight Docker container that checks an IMAP mailbox for emails matching configurable criteria and sends a notification via [ntfy.sh](https://ntfy.sh) when found or not found.

Designed to run on a schedule (e.g., via Coolify's built-in cron), exits after each run, and uses zero resources between executions.

## Features

- **Provider-agnostic**: Works with any IMAP server (Zoho, Gmail, Outlook, self-hosted, etc.)
- **Configurable search**: Match by sender, subject, or both with AND/OR logic
- **Time-windowed search**: Only checks emails within a configurable lookback period
- **ntfy.sh notifications**: Free, no-account-required push notifications to your phone
- **Zero dependencies**: Uses only Python standard library
- **Minimal Docker image**: ~50MB Alpine-based

## Quick Start

### 1. Set up ntfy.sh

1. Install the [ntfy app](https://ntfy.sh) on your phone (iOS/Android)
2. Choose a private topic name (e.g., `my-secret-topic-123`)
3. Subscribe to that topic in the app

### 2. Generate an IMAP App Password

For your email provider, generate an app-specific password:
- **Zoho Mail**: Settings → Security → App Passwords → Generate
- **Gmail**: Google Account → Security → App Passwords
- **Outlook**: Microsoft Account → Security → App Passwords

### 3. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `IMAP_HOST` | Yes | - | IMAP server hostname |
| `IMAP_PORT` | No | `993` | IMAP server port |
| `IMAP_EMAIL` | Yes | - | Your email address for IMAP login |
| `IMAP_PASSWORD` | Yes | - | App password for IMAP login |
| `EMAIL_FOLDER` | No | `INBOX` | Mailbox folder to search |
| `EMAIL_SENDER` | No* | - | Sender email to match |
| `EMAIL_SUBJECT` | No* | - | Subject text to match |
| `EMAIL_MATCH_RULE` | No | `and` | `and` or `or` - how to combine sender/subject |
| `SEARCH_LOOKBACK_HOURS` | No | `24` | How many hours back to search |
| `NTFY_URL` | Yes | - | Full ntfy.sh topic URL |
| `NTFY_TITLE` | No | `Email Check` | Title for the notification |
| `NOTIFY_ON_FOUND` | No | `true` | Send notification when emails are found |
| `NOTIFY_ON_NOT_FOUND` | No | `true` | Send notification when no emails are found |

*At least one of `EMAIL_SENDER` or `EMAIL_SUBJECT` must be set.

### 4. Run Locally

```bash
docker compose up --build
```

### 5. Deploy to Coolify

1. Push this repository to your Git hosting (GitHub, GitLab, etc.)
2. In Coolify, create a new resource → **Docker Compose**
3. Connect your repository
4. Go to the **Environment Variables** tab and add all variables from `.env.example`
5. Go to the **Scheduler** tab and add a cron schedule:

   ```
   0 14 * * 4
   ```

   This runs every Thursday at 14:00 UTC, which is:
   - **6:00 AM PST** (Pacific Standard Time)
   - **7:00 AM PDT** (Pacific Daylight Time)

   Adjust the cron expression for your timezone.

6. Deploy

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│  Coolify Cron (0 14 * * 4)                                  │
│  └─ Starts container                                        │
│     └─ Connects to IMAP server (SSL, port 993)              │
│        └─ Searches folder for matching emails               │
│           └─ Filters by time window (lookback hours)        │
│              ├─ Emails found → ntfy: "Found X email(s)"     │
│              └─ No emails → ntfy: "No matching emails found"│
│     └─ Container exits                                      │
└─────────────────────────────────────────────────────────────┘
```

### Search Logic

1. The script connects to your IMAP server and searches the specified folder
2. It uses IMAP's `SINCE` criterion to narrow results to the lookback date range
3. For each matching email, it fetches the header and parses the `Date` field
4. It filters out emails older than the precise `SEARCH_LOOKBACK_HOURS` window
5. Results are logged and a notification is sent via ntfy.sh

### Match Rules

- **`and`**: Both sender AND subject must match (if both are set)
- **`or`**: Either sender OR subject must match

## Security Notes

- Never commit your `.env` file - it's in `.gitignore`
- Use app-specific passwords, not your main email password
- Choose a unique, unpredictable ntfy.sh topic name for privacy
- All IMAP connections use SSL/TLS
