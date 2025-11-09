"""Example usage of power_outage_remainder package.

This demonstrates how to use the Telegram scraper and Google Calendar integration.
"""

import asyncio
import os
from dotenv import load_dotenv


async def main():
    """Example: fetch outages from Telegram and print them."""
    load_dotenv()

    # Import scraper functions
    from power_outage_remainder.scraper import fetch_and_parse_outages

    # Get credentials from environment
    api_id = int(os.getenv("TELEGRAM_API_ID", "0"))
    api_hash = os.getenv("TELEGRAM_API_HASH", "")
    phone = os.getenv("TELEGRAM_PHONE", "")
    channel = os.getenv("TELEGRAM_CHANNEL", "")

    if not all([api_id, api_hash, phone, channel]):
        print("Please set Telegram credentials in .env file")
        print(
            "Required: TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE, TELEGRAM_CHANNEL"
        )
        return

    print(f"Fetching messages from {channel}...")

    # Fetch and parse outages
    outages_by_date = await fetch_and_parse_outages(
        api_id, api_hash, phone, channel, limit=50
    )

    # Display results
    if not outages_by_date:
        print("No outage schedules found")
        return

    print(f"\nFound outages for {len(outages_by_date)} date(s):\n")

    for date_key in sorted(outages_by_date.keys()):
        outages = outages_by_date[date_key]
        print(f"📅 {date_key}")
        for outage in outages:
            print(f"  ⚡ {outage['location']}")
            print(f"     Start: {outage['start']}")
            print(f"     End:   {outage['end']}")
            if outage.get("group"):
                print(f"     Group: {outage['group']}")
        print()


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
