"""CLI entry and runner that ties Telegram scraper -> calendar integration.

Fetches messages from Telegram channel, extracts outage schedules, and creates calendar events.
"""

import argparse
import asyncio
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

try:
    from googleapiclient.errors import HttpError  # type: ignore
except ImportError:
    # Keep a local placeholder if google client not available in test env
    class HttpError(Exception):
        """Exception raised for HTTP-related errors.

        This is a lightweight, general-purpose exception intended to signal
        problems encountered while performing HTTP requests or processing HTTP
        responses. It subclasses the built-in Exception class and does not add
        extra behavior or attributes by default; it relies on the standard
        Exception interface (e.g., .args) for carrying message and context.

        Usage:
          raise HttpError("Request failed with status 502")
          # or with chaining:
          raise HttpError("Failed to fetch resource") from original_exception

        Notes:
          - If additional structured information (status code, response body,
            headers, etc.) is needed, create a subclass that captures those
            details or attach attributes to the instance at the call site.
          - This class exists to provide a semantic, named exception type for
            HTTP-related failures so callers can catch HttpError specifically.
        """


def build_event_from_outage(outage: dict) -> dict:
    """Map an outage dict to a Google Calendar event body.

    Args:
        outage: Dict with keys: start, end, location, description, group

    Returns:
        Google Calendar event body dict
    """
    summary = f"⚡ Відключення світла: {outage.get('location', 'Не вказано')}"
    if outage.get("group"):
        summary += f" (Група {outage['group']})"

    body = {
        "summary": summary,
        "description": outage.get("description", ""),
        # The scraper now produces timezone-aware ISO datetimes (with offset),
        # so include only the dateTime. Google Calendar accepts the offset in
        # the string and a separate timeZone property is not required.
        "start": {"dateTime": outage["start"]},
        "end": {"dateTime": outage["end"]},
        "colorId": "11",  # Red color for outages
    }

    return body


async def main_async(argv=None):
    """Async main function."""
    parser = argparse.ArgumentParser(
        description="Fetch DTEK outage schedules from Telegram and create Google Calendar reminders"
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Parse and print events without creating them",
    )
    parser.add_argument(
        "--channel",
        dest="channel",
        help="Telegram channel username (overrides env TELEGRAM_CHANNEL)",
    )
    parser.add_argument(
        "--limit",
        dest="limit",
        type=int,
        default=None,
        help="Max messages to fetch (overrides env MAX_MESSAGES)",
    )
    parser.add_argument(
        "--group",
        dest="group",
        default=None,
        help="Only create events for this group (e.g. '1.2').",
    )
    parser.add_argument(
        "--cleanup",
        dest="cleanup",
        action="store_true",
        help="Remove existing outage events from the calendar that are not for today/tomorrow.",
    )
    parser.add_argument(
        "--yes",
        dest="yes",
        action="store_true",
        help="Auto-confirm destructive actions like deletion (use with care).",
    )
    args = parser.parse_args(argv)

    load_dotenv()

    # Load Telegram credentials
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    phone = os.getenv("TELEGRAM_PHONE")
    channel = args.channel or os.getenv("TELEGRAM_CHANNEL")
    limit = args.limit or int(os.getenv("MAX_MESSAGES", "50"))

    if not all([api_id, api_hash, phone, channel]):
        parser.error(
            "Telegram credentials required: TELEGRAM_API_ID, \
              TELEGRAM_API_HASH, TELEGRAM_PHONE, TELEGRAM_CHANNEL"
        )

    # Import scraper
    from power_outage_remainder.scraper import fetch_and_parse_outages

    print(f"Fetching up to {limit} messages from {channel}...")
    outages_by_date = await fetch_and_parse_outages(
        int(api_id), api_hash, phone, channel, limit  # type: ignore
    )

    # Prune older remainders: keep only events for today and tomorrow in the
    # configured timezone. This prevents creating events for past dates.
    tz_name = os.getenv("DEFAULT_TIMEZONE", "Europe/Kyiv")
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("Europe/Kyiv")

    today = datetime.now(tz).date()
    tomorrow = today + timedelta(days=1)
    allowed = {today.isoformat(), tomorrow.isoformat()}

    # Filter the outages_by_date mapping in-place
    pruned = {k: v for k, v in outages_by_date.items() if k in allowed}
    removed = len(outages_by_date) - len(pruned)
    if removed > 0:
        print(
            f"Pruned {removed} past date(s); keeping only today and tomorrow: {sorted(allowed)}"
        )

    outages_by_date = pruned

    if not outages_by_date:
        print("No outage schedules found in recent messages")
        return

    # If cleanup mode requested, connect to Google Calendar and remove old events
    if args.cleanup:
        creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH")
        token_path = os.getenv("GOOGLE_TOKEN_PATH", "token.json")
        calendar_id = os.getenv("DEFAULT_CALENDAR_ID", "primary")

        if not creds_path:
            print("GOOGLE_CREDENTIALS_PATH not set; cannot perform cleanup.")
            return

        from power_outage_remainder.calendar_integration import (
            delete_event,
            get_service,
            list_events,
        )

        service = get_service(creds_path, token_path)

        # Build allowed date set (today and tomorrow in tz)
        allowed = {today.isoformat(), tomorrow.isoformat()}

        # Define list window: from 30 days ago to 30 days ahead to find recent events
        window_min = (datetime.now(tz) - timedelta(days=30)).isoformat()
        window_max = (datetime.now(tz) + timedelta(days=30)).isoformat()

        candidates = []
        for ev in list_events(
            service, calendar_id, time_min=window_min, time_max=window_max
        ):
            summary = ev.get("summary", "")
            # Only consider events that look like our outage reminders
            if not summary.startswith("⚡ Відключення світла"):
                continue

            # Prefer dateTime start; skip all-day 'date' events
            start = ev.get("start", {}).get("dateTime")
            if not start:
                continue

            try:
                ev_date = datetime.fromisoformat(start).date()
            except ValueError:
                continue

            if ev_date.isoformat() not in allowed:
                candidates.append(ev)

        if not candidates:
            print("No old outage events found to remove.")
            return

        print(
            f"Found {len(candidates)} outage event(s) outside today/tomorrow to remove:"
        )
        for ev in candidates:
            print(" -", ev.get("summary"), ev.get("htmlLink"))

        if not args.yes:
            ans = input("Delete these events? Type 'yes' to confirm: ")
            if ans.strip().lower() != "yes":
                print("Aborting cleanup.")
                return

        deleted = 0
        for ev in candidates:
            try:
                delete_event(service, calendar_id, ev["id"])
                deleted += 1
            except HttpError as e:
                print(f"Failed to delete {ev.get('id')}: {e}")

        print(f"Deleted {deleted} event(s)")
        return

    print(f"\nFound outages for {len(outages_by_date)} date(s):")
    for date_key, outages in sorted(outages_by_date.items()):
        print(f"\n{date_key}: {len(outages)} outage(s)")
        for outage in outages:
            # If a group filter is provided, skip outages that don't match
            if args.group and (outage.get("group") != args.group):
                continue

            event = build_event_from_outage(outage)
            if args.dry_run:
                print(f"  - {event['summary']}")
                print(f"    Start: {event['start']['dateTime']}")
                print(f"    End: {event['end']['dateTime']}")
            else:
                print(f"  - Event ready: {event['summary']}")

    if not args.dry_run:
        # Load Google Calendar credentials
        creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH")
        token_path = os.getenv("GOOGLE_TOKEN_PATH", "token.json")
        calendar_id = os.getenv("DEFAULT_CALENDAR_ID", "primary")

        if not creds_path:
            print(
                "\nNote: GOOGLE_CREDENTIALS_PATH not set. Events prepared but not created."
            )
            print("Set credentials and run without --dry-run to create events.")
            return

        from power_outage_remainder.calendar_integration import (
            create_event,
            get_service,
            list_events,
        )

        service = get_service(creds_path, token_path)
        print(f"\nChecking for existing events in calendar: {calendar_id}")

        # Fetch existing outage events within the time window (today and tomorrow)
        window_min = (
            datetime.combine(today, datetime.min.time()).replace(tzinfo=tz).isoformat()
        )
        window_max = (
            datetime.combine(tomorrow, datetime.max.time())
            .replace(tzinfo=tz)
            .isoformat()
        )

        existing_events = []
        for ev in list_events(
            service, calendar_id, time_min=window_min, time_max=window_max
        ):
            summary = ev.get("summary", "")
            # Only consider events that look like our outage reminders
            if summary.startswith("⚡ Відключення світла"):
                existing_events.append(
                    {
                        "summary": summary,
                        "start": ev.get("start", {}).get("dateTime"),
                        "end": ev.get("end", {}).get("dateTime"),
                    }
                )

        print(f"Found {len(existing_events)} existing outage event(s)")

        def event_exists(new_event):
            """Check if an event with the same summary, start, and end already exists."""
            for existing in existing_events:
                if (
                    existing["summary"] == new_event["summary"]
                    and existing["start"] == new_event["start"]["dateTime"]
                    and existing["end"] == new_event["end"]["dateTime"]
                ):
                    return True
            return False

        created_count = 0
        skipped_count = 0
        for date_key, outages in sorted(outages_by_date.items()):
            for outage in outages:
                # Apply same group filter before creating events
                if args.group and (outage.get("group") != args.group):
                    continue

                event = build_event_from_outage(outage)

                # Check if this event already exists
                if event_exists(event):
                    print(f"  ⊘ Skipped (already exists): {event['summary']}")
                    skipped_count += 1
                    continue

                created = create_event(service, calendar_id, event)
                print(f"  ✓ Created: {created.get('htmlLink')}")
                created_count += 1

        print(
            f"\n✓ Successfully created {created_count} event(s), skipped {skipped_count} duplicate(s)"
        )


def main(argv=None):
    """Synchronous entry point."""
    asyncio.run(main_async(argv))


if __name__ == "__main__":
    main()
