from datetime import date
from pathlib import Path

import pytest
from icalendar import Calendar

from pmscheduler import PMTask, add_months, build_schedule, load_tasks, monthly_hours, occurrences, write_ics
from pmscheduler.cli import main
from pmscheduler.schedule import next_weekday

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "pm_tasks.csv"


def task(freq, first, hours=1.0):
    return PMTask("Unit 1", "Building A", "Check", freq, first, hours)


def days(task_, start, end, **kw):
    return [o.due for o in occurrences(task_, start, end, **kw)]


def test_add_months_clamps_short_month():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2028, 1, 31), 1) == date(2028, 2, 29)


def test_add_months_year_rollover():
    assert add_months(date(2026, 11, 15), 3) == date(2027, 2, 15)


def test_monthly_returns_to_31st_after_short_month():
    result = days(task("monthly", date(2026, 1, 31)), date(2026, 1, 1), date(2026, 4, 30))
    assert result == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]


def test_weekly_and_biweekly():
    assert len(days(task("weekly", date(2026, 1, 5)), date(2026, 1, 1), date(2026, 1, 31))) == 4
    assert days(task("biweekly", date(2026, 1, 5)), date(2026, 1, 1), date(2026, 1, 31)) == [
        date(2026, 1, 5), date(2026, 1, 19)]


def test_quarterly_semiannual_annual():
    start, end = date(2026, 1, 1), date(2027, 12, 31)
    assert len(days(task("quarterly", date(2026, 2, 15)), start, end)) == 8
    assert len(days(task("semiannual", date(2026, 3, 1)), start, end)) == 4
    assert days(task("annual", date(2026, 4, 10)), start, end) == [date(2026, 4, 10), date(2027, 4, 10)]


def test_dates_before_start_skipped_and_end_inclusive():
    result = days(task("weekly", date(2026, 1, 5)), date(2026, 1, 12), date(2026, 1, 19))
    assert result == [date(2026, 1, 12), date(2026, 1, 19)]


def test_task_starting_after_window_has_none():
    assert days(task("monthly", date(2027, 6, 1)), date(2026, 1, 1), date(2026, 12, 31)) == []


def test_end_before_start_rejected():
    with pytest.raises(ValueError):
        occurrences(task("weekly", date(2026, 1, 5)), date(2026, 2, 1), date(2026, 1, 1))


def test_weekend_shift():
    assert next_weekday(date(2026, 2, 28)) == date(2026, 3, 2)  # Saturday
    assert next_weekday(date(2026, 3, 1)) == date(2026, 3, 2)  # Sunday
    assert next_weekday(date(2026, 3, 3)) == date(2026, 3, 3)
    shifted = days(task("monthly", date(2026, 1, 31)), date(2026, 1, 1), date(2026, 2, 28), shift_weekends=True)
    assert shifted == [date(2026, 2, 2)]  # Jan 31 is a Saturday and Feb 28 moves out of the window


def test_schedule_sorted_and_hours():
    tasks = [task("weekly", date(2026, 1, 12), 2.0), PMTask("A", "B", "C", "monthly", date(2026, 1, 5), 3.0)]
    schedule = build_schedule(tasks, date(2026, 1, 1), date(2026, 1, 31))
    assert [s.due for s in schedule] == sorted(s.due for s in schedule)
    assert monthly_hours(schedule) == {"2026-01": 3 * 2.0 + 3.0}


def test_uid_is_stable_and_unique():
    schedule = build_schedule([task("weekly", date(2026, 1, 5))], date(2026, 1, 1), date(2026, 1, 31))
    uids = [s.uid for s in schedule]
    assert len(set(uids)) == len(uids)
    assert uids == [s.uid for s in build_schedule([task("weekly", date(2026, 1, 5))], date(2026, 1, 1), date(2026, 1, 31))]


def test_ics_round_trip(tmp_path):
    schedule = build_schedule(load_tasks(SAMPLE), date(2026, 1, 1), date(2026, 1, 31))
    out = tmp_path / "pm.ics"
    assert write_ics(out, schedule) == len(schedule)
    cal = Calendar.from_ical(out.read_bytes())
    events = [c for c in cal.walk() if c.name == "VEVENT"]
    assert len(events) == len(schedule)
    assert events[0]["SUMMARY"].startswith("PM: ")
    assert events[0]["DTSTART"].dt == schedule[0].due


def test_load_tasks_errors(tmp_path):
    path = tmp_path / "t.csv"
    path.write_text("asset,building\nA,B\n")
    with pytest.raises(ValueError, match="missing columns"):
        load_tasks(path)
    head = "asset,building,task,frequency,first_due,hours\n"
    path.write_text(head + "A,B,C,daily,2026-01-01,1\n")
    with pytest.raises(ValueError, match="unknown frequency"):
        load_tasks(path)
    path.write_text(head + "A,B,C,weekly,01/01/2026,1\n")
    with pytest.raises(ValueError, match="bad first_due"):
        load_tasks(path)
    path.write_text(head + "A,B,C,weekly,2026-01-01,-2\n")
    with pytest.raises(ValueError, match="negative"):
        load_tasks(path)


def test_cli(tmp_path, capsys):
    ics = tmp_path / "out.ics"
    assert main([str(SAMPLE), "--start", "2027-01-01", "--months", "2", "--ics", str(ics)]) == 0
    assert "wrote" in capsys.readouterr().out and ics.exists()
    assert main([str(SAMPLE), "--months", "0"]) == 1
    assert main([str(tmp_path / "none.csv")]) == 1
