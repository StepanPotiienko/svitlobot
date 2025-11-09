"""Telegram channel scraper for DTEK outage schedules.

This module fetches messages from a Telegram channel, detects outage schedule information,
and structures it into a dictionary format suitable for Google Calendar events.
"""

import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional, cast


async def fetch_channel_messages(
    api_id: int, api_hash: str, phone: str, channel: str, limit: int = 50
) -> List[Dict]:
    """Fetch recent messages from a Telegram channel.

    Args:
        api_id: Telegram API ID (from my.telegram.org)
        api_hash: Telegram API hash
        phone: Phone number for authentication
        channel: Channel username (e.g., '@dtek_kyiv' or channel URL)
        limit: Maximum number of messages to fetch

    Returns:
        List of message dictionaries with 'id', 'date', 'text' fields
    """
    try:
        from telethon import TelegramClient
    except ImportError as e:
        raise RuntimeError("Telethon is required. Install from requirements.txt") from e

    client = TelegramClient("session_name", api_id, api_hash)

    messages = []
    try:
        await client.start(phone=phone)  # type: ignore

        # Fetch messages from channel
        async for message in client.iter_messages(channel, limit=limit):
            if message.text:
                messages.append(
                    {"id": message.id, "date": message.date, "text": message.text}
                )
    finally:
        await client.disconnect()  # type: ignore

    return messages


def is_outage_message(text: str) -> bool:
    """Check if a message contains outage schedule information.

    Looks for keywords like:
    - "відключення" (outages)
    - "графік" (schedule)
    - "вимкнення" (switching off)
    - "електропостачання" (power supply)
    - time patterns (e.g., "08:00-12:00")
    """
    if not text:
        return False

    text_lower = text.lower()

    # Keywords that indicate outage information
    keywords = [
        "відключення",
        "вимкнення",
        "графік",
        "електропостачання",
        "електроенергі",
        "світло",
        "без світла",
    ]

    has_keyword = any(keyword in text_lower for keyword in keywords)

    # Check for time patterns (HH:MM format)
    has_time = bool(re.search(r"\d{1,2}[:.-]\d{2}", text))

    return has_keyword and has_time


def extract_outage_info(text: str, message_date: datetime) -> List[Dict[str, Any]]:
    """Extract structured outage information from message text.

    Args:
        text: Message text containing outage information
        message_date: Date when the message was posted

    Returns:
        List of dictionaries with keys: 'start', 'end', 'location', 'description', 'group'.
        The list contains one entry per time range found in the message. Returns an
        empty list if parsing fails or no time ranges are found.
    """
    if not text:
        return []

    # Extract time ranges (e.g., "08:00-12:00", "08:00 - 12:00", "з 08:00 до 18:00")
    time_patterns = [
        r"(\d{1,2})[:.](\d{2})\s*[-–—]\s*(\d{1,2})[:.](\d{2})",  # 08:00-12:00
        r"з\s+(\d{1,2})[:.](\d{2})\s+до\s+(\d{1,2})[:.](\d{2})",  # з 08:00 до 18:00
    ]

    times = []
    for pattern in time_patterns:
        matches = re.findall(pattern, text)
        if matches:
            for match in matches:
                if len(match) == 4:
                    start_h, start_m, end_h, end_m = match
                    times.append(
                        {
                            "start": (int(start_h), int(start_m)),
                            "end": (int(end_h), int(end_m)),
                        }
                    )

    # Extract date if mentioned (e.g., "10.11", "10 листопада", "10 ноября")
    # Match either DD.MM format or "DD month_name" but avoid matching group numbers like "2.1"
    date_patterns = [
        r"\b(\d{1,2})\s+(листопада|ноября|грудня|січня|лютого|февраля|березня|марта|квітня|апреля|травня|мая|червня|июня|липня|июля|серпня|августа|вересня|сентября|жовтня|октября|декабря)\b",  # "10 листопада"
        r"\b(\d{1,2})\.(\d{2})\b",  # "10.11" (two-digit month only to avoid "2.1")
    ]

    target_date = message_date.date()
    date_match = None
    for pattern in date_patterns:
        date_match = re.search(pattern, text)
        if date_match:
            break

    if date_match:
        day_str = date_match.group(1)
        month_part = date_match.group(2)

        # Try to parse the month
        month_map = {
            "січня": 1,
            "января": 1,
            "лютого": 2,
            "февраля": 2,
            "березня": 3,
            "марта": 3,
            "квітня": 4,
            "апреля": 4,
            "травня": 5,
            "мая": 5,
            "червня": 6,
            "июня": 6,
            "липня": 7,
            "июля": 7,
            "серпня": 8,
            "августа": 8,
            "вересня": 9,
            "сентября": 9,
            "жовтня": 10,
            "октября": 10,
            "листопада": 11,
            "ноября": 11,
            "грудня": 12,
            "декабря": 12,
        }

        month = month_map.get(month_part.lower())
        if not month:
            try:
                month = int(month_part)
            except ValueError:
                month = message_date.month

        day = int(day_str)
        year = message_date.year

        # Handle year transition
        if month < message_date.month and message_date.month == 12:
            year += 1

        try:
            target_date = datetime(year, month, day).date()
        except ValueError:
            target_date = message_date.date()

    # Extract location/address/group info
    location = ""
    group_match = re.search(r"[Гг]руп[аи]?\s*[:-]?\s*(\d+[.\d]*)", text)
    if group_match:
        location = f"Група {group_match.group(1)}"

    # Extract address patterns
    address_patterns = [
        r"вул\.\s+([^\n,;]+)",
        r"вулиця\s+([^\n,;]+)",
        r"район[іи]?\s+([^\n,;]+)",
        r"черга\s+(\d+)",
    ]

    for pattern in address_patterns:
        addr_match = re.search(pattern, text, re.IGNORECASE)
        if addr_match:
            if location:
                location += f", {addr_match.group(1).strip()}"
            else:
                location = addr_match.group(1).strip()
            break

    if not location:
        location = "Не вказано"

    # Build result dictionaries for each time range found
    results: List[Dict[str, Any]] = []
    for time_info in times:
        start_h, start_m = time_info["start"]
        end_h, end_m = time_info["end"]

        # Make datetimes timezone-aware using DEFAULT_TIMEZONE (fallback to Europe/Kyiv)
        tz_name = os.getenv("DEFAULT_TIMEZONE", "Europe/Kyiv")
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("Europe/Kyiv")

        start_dt = datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            start_h,
            start_m,
            tzinfo=tz,
        )
        end_dt = datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            end_h,
            end_m,
            tzinfo=tz,
        )

        # Handle overnight outages (e.g., 23:00-02:00)
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)

        results.append(
            {
                # isoformat() will include the offset (e.g. +02:00) which is accepted by
                # Google Calendar API and removes the need to pass a separate timeZone.
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "location": location,
                "description": text[:500],  # Limit description length
                "group": group_match.group(1) if group_match else None,
            }
        )

    # Return all found time ranges so callers can create one calendar event per
    # time window. Older code expected a single dict; the parser below handles
    # both list and dict results for backward compatibility.
    return results


def parse_messages_to_dict(messages: List[Dict]) -> Dict[str, List[Dict]]:
    """Parse Telegram messages and organize outages by date.

    Args:
        messages: List of message dicts from fetch_channel_messages

    Returns:
        Dictionary mapping date strings (YYYY-MM-DD) to lists of outage info dicts
    """
    outages_by_date = {}

    for msg in messages:
        text = msg.get("text", "")
        msg_date = msg.get("date")

        if not is_outage_message(text):
            continue

        outage_info = extract_outage_info(text, msg_date)  # type: ignore
        if not outage_info:
            continue

        # extract_outage_info now returns a list of outage dicts (one per time
        # range). For backward compatibility accept a single dict as well.
        candidates: List[Dict[str, Any]] = []
        if isinstance(outage_info, dict):
            candidates = [cast(Dict[str, Any], outage_info)]
        elif isinstance(outage_info, list):
            candidates = cast(List[Dict[str, Any]], outage_info)
        else:
            # skip unexpected types (defensive programming)
            continue

        for outage_dict in candidates:
            # Safely retrieve the ISO start string and validate it before parsing
            start_iso = (
                outage_dict.get("start") if isinstance(outage_dict, dict) else None
            )
            if not isinstance(start_iso, str):
                # skip entries without a valid start datetime string
                continue

            # Parse the start datetime to get the date key
            try:
                start_dt = datetime.fromisoformat(start_iso)
            except (ValueError, TypeError):
                # skip invalid datetime formats
                continue

            date_key = start_dt.strftime("%Y-%m-%d")

            if date_key not in outages_by_date:
                outages_by_date[date_key] = []

            outages_by_date[date_key].append(outage_dict)

    return outages_by_date


async def fetch_and_parse_outages(
    api_id: int, api_hash: str, phone: str, channel: str, limit: int = 50
) -> Dict[str, List[Dict]]:
    """Main function to fetch from Telegram and parse outages.

    Args:
        api_id: Telegram API ID
        api_hash: Telegram API hash
        phone: Phone number for auth
        channel: Channel username or URL
        limit: Max messages to fetch

    Returns:
        Dictionary mapping dates to lists of outage info
    """
    messages = await fetch_channel_messages(api_id, api_hash, phone, channel, limit)
    return parse_messages_to_dict(messages)
