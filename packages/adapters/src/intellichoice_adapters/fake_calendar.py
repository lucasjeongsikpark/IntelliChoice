from uuid import uuid4

from intellichoice_shared.calendar import CalendarEvent


class FakeCalendarTransport:
    """Dev/test `CalendarTransport` (SPEC §5.23.3) - appends to an in-memory list
    instead of calling Google Calendar, mirrors `FakeEmailTransport` exactly. A real
    client (per-user OAuth, SPEC §5.23.3/§5.24.3) is selected by env config once real
    Google credentials exist (D-002).
    """

    def __init__(self) -> None:
        self.created: list[CalendarEvent] = []

    async def create_event(self, event: CalendarEvent) -> str:
        self.created.append(event)
        return f"fake-event-{uuid4()}"
