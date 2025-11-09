"""Test scraper module functions"""

from datetime import datetime
from typing import cast, Dict, Any
from power_outage_remainder.scraper import (
    is_outage_message,
    extract_outage_info,
    parse_messages_to_dict,
)


def test_is_outage_message_positive():
    """Test that messages with outage keywords and times are detected."""
    text = "Графік відключення світла на 10.11: 08:00-12:00"
    assert is_outage_message(text) is True


def test_is_outage_message_negative():
    """Test that regular messages are not detected as outage messages."""
    text = "Доброго дня! Як справи?"
    assert is_outage_message(text) is False


def test_extract_outage_info_basic():
    """Test extraction of outage info from a simple message."""
    text = "Відключення світла: Група 1, 10.11.2025, 08:00-12:00"
    msg_date = datetime(2025, 11, 10, 10, 0, 0)

    result = extract_outage_info(text, msg_date)

    assert result is not None
    # function now returns a list of outage dicts (one per time range)
    assert isinstance(result, list)
    assert len(result) >= 1
    assert isinstance(result[0], dict)


def test_extract_outage_info_with_time_range():
    """Test extraction with different time formats."""
    text = "Планові роботи з 14:30 до 18:00, група 2.1"
    msg_date = datetime(2025, 11, 9, 12, 0, 0)
    result = extract_outage_info(text, msg_date)

    assert result is not None
    assert isinstance(result, list)
    assert len(result) >= 1
    result_dict = cast(Dict[str, Any], result[0])
    start = result_dict.get("start")
    end = result_dict.get("end")
    assert isinstance(start, str)
    assert isinstance(end, str)
    assert start.startswith("2025-11-09T14:30")
    assert end.startswith("2025-11-09T18:00")


def test_parse_messages_to_dict():
    """Test parsing multiple messages into organized dict."""
    messages = [
        {
            "id": 1,
            "date": datetime(2025, 11, 10, 9, 0, 0),
            "text": "Відключення світла 10.11: Група 1, 08:00-12:00",
        },
        {
            "id": 2,
            "date": datetime(2025, 11, 10, 10, 0, 0),
            "text": "Доброго ранку!",  # Not an outage message
        },
        {
            "id": 3,
            "date": datetime(2025, 11, 11, 9, 0, 0),
            "text": "Графік відключень 11.11: 14:00-17:00, Група 2",
        },
    ]

    result = parse_messages_to_dict(messages)

    assert isinstance(result, dict)
    assert "2025-11-10" in result
    assert "2025-11-11" in result
    assert len(result["2025-11-10"]) >= 1
    assert len(result["2025-11-11"]) >= 1
