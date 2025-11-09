"""Runner script that fetches from Telegram and creates calendar events.

This script loads environment variables and uses async to fetch messages.
"""

from pathlib import Path
import sys
import os
import asyncio
from dotenv import load_dotenv

# Ensure the project root is on sys.path when running this script directly
# (so imports like `from power_outage_remainder.scraper ...` work).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


async def main():
    """Run scraper and create calendar events"""
    load_dotenv()

    # Load config from env
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    phone = os.getenv("TELEGRAM_PHONE")
    channel = os.getenv("TELEGRAM_CHANNEL")
    limit = int(os.getenv("MAX_MESSAGES", "50"))
    dry_run = os.getenv("DRY_RUN", "true").lower() in ("1", "true", "yes")

    if not all([api_id, api_hash, phone, channel]):
        raise SystemExit(
            "Telegram credentials required: TELEGRAM_API_ID, \
              TELEGRAM_API_HASH, TELEGRAM_PHONE, TELEGRAM_CHANNEL"
        )

    from power_outage_remainder.scraper import fetch_and_parse_outages
    from power_outage_remainder.cli import build_event_from_outage

    print(f"Fetching up to {limit} messages from {channel}...")
    outages_by_date = await fetch_and_parse_outages(
        int(api_id), api_hash, phone, channel, limit  # type: ignore
    )

    if not outages_by_date:
        print("No outage schedules found in recent messages")
        return

    print(f"\nFound outages for {len(outages_by_date)} date(s):")

    if dry_run:
        print("\n=== DRY RUN MODE ===")
        for date_key, outages in sorted(outages_by_date.items()):
            print(f"\n{date_key}: {len(outages)} outage(s)")
            for outage in outages:
                event = build_event_from_outage(outage)
                print(f"  - {event['summary']}")
                print(f"    {event['start']['dateTime']} → {event['end']['dateTime']}")
        return

    # Real mode: create calendar events
    creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH")
    token_path = os.getenv("GOOGLE_TOKEN_PATH", "token.json")
    calendar_id = os.getenv("DEFAULT_CALENDAR_ID", "primary")

    if not creds_path:
        print(
            "\nGOOGLE_CREDENTIALS_PATH not set. Set it and DRY_RUN=false to create events."
        )
        return

    from power_outage_remainder.calendar_integration import get_service, create_event

    service = get_service(creds_path, token_path)
    print(f"\nCreating events in calendar: {calendar_id}")

    created_count = 0
    for date_key, outages in sorted(outages_by_date.items()):
        for outage in outages:
            event = build_event_from_outage(outage)
            created = create_event(service, calendar_id, event)
            print(f"  ✓ {created.get('htmlLink')}")
            created_count += 1

    print(f"\n✓ Successfully created {created_count} event(s)")


if __name__ == "__main__":
    asyncio.run(main())
