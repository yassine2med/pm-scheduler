"""Expand recurring PM tasks into dated occurrences."""
from __future__ import annotations

import calendar
import csv
import hashlib
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

REQUIRED = ("asset", "building", "task", "frequency", "first_due", "hours")
FREQUENCY_DAYS = {"weekly": 7, "biweekly": 14}
FREQUENCY_MONTHS = {"monthly": 1, "quarterly": 3, "semiannual": 6, "annual": 12}


@dataclass(frozen=True)
class PMTask:
    """A recurring preventive maintenance task."""

    asset: str
    building: str
    task: str
    frequency: str
    first_due: date
    hours: float


@dataclass(frozen=True)
class Occurrence:
    """One scheduled visit."""

    task: PMTask
    due: date

    @property
    def uid(self) -> str:
        """Stable id, so a re-imported calendar updates events instead of duplicating them."""
        key = f"{self.task.asset}|{self.task.task}|{self.task.first_due.isoformat()}|{self.due.isoformat()}"
        return hashlib.sha1(key.encode()).hexdigest()[:20] + "@pm-scheduler"


def load_tasks(path: str | Path) -> list[PMTask]:
    """Read tasks from CSV. Raises ValueError on missing columns, unknown frequency or bad values."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"missing columns: {', '.join(missing)}")
        tasks = []
        for line, row in enumerate(reader, start=2):
            frequency = row["frequency"].strip().lower()
            if frequency not in FREQUENCY_DAYS and frequency not in FREQUENCY_MONTHS:
                raise ValueError(f"line {line}: unknown frequency '{row['frequency']}'")
            try:
                first_due = date.fromisoformat(row["first_due"].strip())
                hours = float(row["hours"])
            except ValueError:
                raise ValueError(f"line {line}: bad first_due or hours") from None
            if hours < 0:
                raise ValueError(f"line {line}: hours cannot be negative")
            tasks.append(PMTask(row["asset"].strip(), row["building"].strip(), row["task"].strip(), frequency, first_due, hours))
    return tasks


def add_months(start: date, months: int) -> date:
    """Add months, clamping to the last day of a short month (Jan 31 plus 1 is Feb 28)."""
    index = start.month - 1 + months
    year, month = start.year + index // 12, index % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def next_weekday(day: date) -> date:
    """Move a Saturday or Sunday to the following Monday."""
    return day + timedelta(days=(7 - day.weekday()) % 7) if day.weekday() >= 5 else day


def occurrences(task: PMTask, start: date, end: date, shift_weekends: bool = False) -> list[Occurrence]:
    """Dates for one task between start and end, both inclusive.

    Each date is counted from first_due, not from the previous date, so a task due on the
    31st returns to the 31st after a short month.
    """
    if end < start:
        raise ValueError("end is before start")
    found = []
    step = 0
    while True:
        if task.frequency in FREQUENCY_DAYS:
            due = task.first_due + timedelta(days=FREQUENCY_DAYS[task.frequency] * step)
        else:
            due = add_months(task.first_due, FREQUENCY_MONTHS[task.frequency] * step)
        step += 1
        if shift_weekends:
            due = next_weekday(due)
        if due > end:
            break
        if due >= start:
            found.append(Occurrence(task, due))
    return found


def build_schedule(tasks: list[PMTask], start: date, end: date, shift_weekends: bool = False) -> list[Occurrence]:
    """All occurrences for all tasks, sorted by date then asset."""
    items = [o for t in tasks for o in occurrences(t, start, end, shift_weekends)]
    return sorted(items, key=lambda o: (o.due, o.task.asset, o.task.task))


def monthly_hours(schedule: list[Occurrence]) -> dict[str, float]:
    """Planned labour hours per month, keyed 'YYYY-MM'."""
    totals: dict[str, float] = {}
    for item in schedule:
        key = item.due.strftime("%Y-%m")
        totals[key] = round(totals.get(key, 0.0) + item.task.hours, 2)
    return dict(sorted(totals.items()))
