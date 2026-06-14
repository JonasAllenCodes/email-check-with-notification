#!/usr/bin/env python3
"""
Checks an IMAP mailbox for emails matching configurable criteria
and sends a notification via ntfy.sh if found or not found.
"""

import imaplib
import email
from email.header import decode_header
import os
import sys
import socket
from datetime import datetime, timedelta, timezone
import http.client
import urllib.parse

socket.setdefaulttimeout(30)


def get_env(name, default=None, required=False):
    """Get environment variable with optional default and required check."""
    value = os.environ.get(name, default)
    if required and not value:
        print(f"Error: Required environment variable '{name}' is not set.")
        sys.exit(1)
    return value


def parse_imap_date(date_str):
    """
    Parse an email Date header string into a datetime object.
    Email dates can be in various formats, this handles common ones.
    """
    date_str = date_str.strip()
    for fmt in [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S",
    ]:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


def decode_mime_header(header_value):
    """Decode a MIME-encoded header (handles non-ASCII characters)."""
    if not header_value:
        return ""
    decoded_parts = decode_header(header_value)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def build_imap_search_query(sender, subject, match_rule):
    """
    Build an IMAP search query string.

    IMAP search syntax:
    - FROM "sender" matches emails from that sender
    - SUBJECT "subject" matches emails containing that subject
    - Multiple criteria are ANDed by default in IMAP
    - OR requires explicit OR prefix: OR FROM "x" SUBJECT "y"
    """
    sender_part = f'FROM "{sender}"' if sender else ""
    subject_part = f'SUBJECT "{subject}"' if subject else ""

    if not sender_part and not subject_part:
        print("Error: At least one of EMAIL_SENDER or EMAIL_SUBJECT must be set.")
        sys.exit(1)

    if match_rule == "or":
        if sender_part and subject_part:
            return f'OR {sender_part} {subject_part}'
        return sender_part or subject_part
    else:
        if sender_part and subject_part:
            return f'{sender_part} {subject_part}'
        return sender_part or subject_part


def send_ntfy(url, title, message):
    """
    Send a notification via ntfy.sh using HTTP POST.

    ntfy expects:
    - POST to the topic URL
    - Title in the 'Title' header
    - Message in the request body
    """
    try:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        host = parsed.netloc

        conn = http.client.HTTPSConnection(host) if parsed.scheme == "https" else http.client.HTTPConnection(host)
        conn.request(
            "POST",
            path,
            body=message.encode("utf-8"),
            headers={"Title": title},
        )
        response = conn.getresponse()
        if response.status in (200, 201):
            print(f"Notification sent successfully: {message}")
        else:
            print(f"Failed to send notification: {response.status} {response.read().decode()}")
        conn.close()
    except Exception as e:
        print(f"Error sending notification: {e}")


def main():
    # Load configuration
    imap_host = get_env("IMAP_HOST", required=True)
    imap_port = int(get_env("IMAP_PORT", "993"))
    imap_email = get_env("IMAP_EMAIL", required=True)
    imap_password = get_env("IMAP_PASSWORD", required=True)

    email_folder = get_env("EMAIL_FOLDER", "INBOX")
    email_sender = get_env("EMAIL_SENDER", "")
    email_subject = get_env("EMAIL_SUBJECT", "")
    match_rule = get_env("EMAIL_MATCH_RULE", "and").lower()
    lookback_hours = int(get_env("SEARCH_LOOKBACK_HOURS", "24"))

    ntfy_url = get_env("NTFY_URL", required=True)
    ntfy_title = get_env("NTFY_TITLE", "Email Check")
    notify_on_found = get_env("NOTIFY_ON_FOUND", "true").lower() == "true"
    notify_on_not_found = get_env("NOTIFY_ON_NOT_FOUND", "true").lower() == "true"

    # Connect to IMAP server
    print(f"Connecting to {imap_host}:{imap_port}...")
    try:
        mail = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=30)
        mail.login(imap_email, imap_password)
        print("Login successful.")
    except imaplib.IMAP4.error as e:
        print(f"IMAP login failed: {e}")
        sys.exit(1)
    except OSError as e:
        print(f"IMAP connection failed: {e}")
        sys.exit(1)
    except TimeoutError as e:
        print(f"IMAP connection timed out: {e}")
        sys.exit(1)

    # Select mailbox folder
    status, _ = mail.select(email_folder, readonly=True)
    if status != "OK":
        print(f"Failed to select folder '{email_folder}': {status}")
        sys.exit(1)
    print(f"Selected folder: {email_folder}")

    # Build and execute search
    search_query = build_imap_search_query(email_sender, email_subject, match_rule)
    print(f"Search query: {search_query}")

    # IMAP SINCE uses date only (no time), so we search from the start of the lookback date
    cutoff_date = (datetime.now() - timedelta(hours=lookback_hours)).strftime("%d-%b-%Y")
    full_query = f'(SINCE {cutoff_date} {search_query})'
    print(f"Full query: {full_query}")

    status, messages = mail.search(None, full_query)
    if status != "OK":
        print(f"Search failed: {status}")
        sys.exit(1)

    email_ids = messages[0].split()
    print(f"Found {len(email_ids)} matching email(s).")

    # Filter by precise time (IMAP SINCE is date-only)
    cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    recent_emails = []

    for eid in email_ids:
        status, msg_data = mail.fetch(eid, "(RFC822.HEADER)")
        if status != "OK":
            continue
        raw_header = msg_data[0][1]
        msg = email.message_from_bytes(raw_header)
        date_str = msg.get("Date", "")
        msg_date = parse_imap_date(date_str)
        if msg_date and msg_date >= cutoff_dt:
            subject = decode_mime_header(msg.get("Subject", ""))
            sender = decode_mime_header(msg.get("From", ""))
            recent_emails.append({"from": sender, "subject": subject, "date": date_str})
            print(f"  - From: {sender} | Subject: {subject} | Date: {date_str}")

    mail.logout()

    # Send notification
    if recent_emails:
        count = len(recent_emails)
        message = f"Found {count} matching email(s) in the last {lookback_hours} hours."
        print(f"RESULT: Email(s) found. {message}")
        if notify_on_found:
            send_ntfy(ntfy_url, ntfy_title, message)
    else:
        message = f"No matching emails found in the last {lookback_hours} hours."
        print(f"RESULT: No emails found. {message}")
        if notify_on_not_found:
            send_ntfy(ntfy_url, ntfy_title, message)


if __name__ == "__main__":
    main()
