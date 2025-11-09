def test_create_event_called():
    """Create a fake service with events().insert().execute()"""
    executed = {}

    class FakeInsert:
        def __init__(self, body):
            self._body = body

        def execute(self):
            executed["body"] = self._body
            return {"id": "fake123", "htmlLink": "http://example.com/event"}

    class FakeEvents:
        def insert(self, calendarId, body):
            assert calendarId == "testcal"
            return FakeInsert(body)

    class FakeService:
        def events(self):
            return FakeEvents()

    fake_service = FakeService()

    # Import the create_event function lazily to avoid requiring google libs
    from power_outage_remainder.calendar_integration import create_event

    body = {
        "summary": "Test",
        "start": {"dateTime": "2025-11-10T08:00:00"},
        "end": {"dateTime": "2025-11-10T09:00:00"},
    }
    res = create_event(fake_service, "testcal", body)
    assert res["id"] == "fake123"
    assert executed["body"] == body
