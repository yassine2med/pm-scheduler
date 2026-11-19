"""Write a schedule as an iCalendar file."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from icalendar import Calendar, Event

from .schedule import Occurrence


def build_calendar(schedule: list[Occurrence], name: str = "Preventive maintenance") -> Calendar:
    """Return a Calendar with one all-day event per occurrence."""
    cal = Calendar()
    cal.add("prodid", "-//pm-scheduler//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", name)
    for item in schedule:
        event = Event()
        event.add("uid", item.uid)
        event.add("summary", f"PM: {item.task.task} - {item.task.asset}")
        event.add("dtstart", item.due)
        event.add("dtend", item.due + timedelta(days=1))
        event.add("location", item.task.building)
        event.add("description", f"Asset: {item.task.asset}\nFrequency: {item.task.frequency}\nPlanned hours: {item.task.hours:g}")
        cal.add_component(event)
    return cal


def write_ics(path: str | Path, schedule: list[Occurrence]) -> int:
    """Write the file and return the number of events."""
    Path(path).write_bytes(build_calendar(schedule).to_ical())
    return len(schedule)
