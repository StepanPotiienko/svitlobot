import asyncio


async def _fake_fetch(*args, **kwargs):
    # Return two outages on the same date with different groups
    return {
        "2025-11-10": [
            {
                "start": "2025-11-10T08:00:00+02:00",
                "end": "2025-11-10T12:00:00+02:00",
                "location": "Test Addr 1",
                "description": "Desc 1",
                "group": "1.2",
            },
            {
                "start": "2025-11-10T14:00:00+02:00",
                "end": "2025-11-10T17:00:00+02:00",
                "location": "Test Addr 2",
                "description": "Desc 2",
                "group": "2.1",
            },
        ]
    }


def run_main_and_capture(monkeypatch, argv):
    """Helper to run main_async with monkeypatch in place and capture printed output."""
    # Ensure required env vars are present
    monkeypatch.setenv("TELEGRAM_API_ID", "1")
    monkeypatch.setenv("TELEGRAM_API_HASH", "x")
    monkeypatch.setenv("TELEGRAM_PHONE", "p")
    monkeypatch.setenv("TELEGRAM_CHANNEL", "chan")

    # Patch scraper.fetch_and_parse_outages to our fake
    import power_outage_remainder.scraper as scraper_mod

    monkeypatch.setattr(scraper_mod, "fetch_and_parse_outages", _fake_fetch)

    # Run the CLI main_async and capture stdout
    from power_outage_remainder.cli import main_async

    return asyncio.run(main_async(argv))


def test_cli_group_filter_dry_run(monkeypatch, capsys):
    """When --group=1.2 is passed in dry-run, only events for group 1.2 are printed."""
    # Run and capture (main_async prints to stdout)
    run_main_and_capture(monkeypatch, ["--dry-run", "--group", "1.2"])
    captured = capsys.readouterr()
    out = captured.out

    assert "Група 1.2" in out or "(Група 1.2)" in out
    assert "Група 2.1" not in out and "(Група 2.1)" not in out


def test_cli_no_group_shows_all(monkeypatch, capsys):
    """Without --group both outages should be printed in dry-run."""
    run_main_and_capture(monkeypatch, ["--dry-run"])
    captured = capsys.readouterr()
    out = captured.out

    assert ("Група 1.2" in out) or ("(Група 1.2)" in out)
    assert ("Група 2.1" in out) or ("(Група 2.1)" in out)
