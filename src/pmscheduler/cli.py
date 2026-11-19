"""Command line entry: python -m pmscheduler tasks.csv --start 2027-01-01 --months 3"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

from .ics import write_ics
from .schedule import add_months, build_schedule, load_tasks, monthly_hours


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    parser = argparse.ArgumentParser(prog="pmscheduler", description="Generate a PM calendar")
    parser.add_argument("csv", help="PM task CSV")
    parser.add_argument("--start", type=date.fromisoformat, default=date.today(), help="first day, YYYY-MM-DD")
    parser.add_argument("--months", type=int, default=3, help="months to cover")
    parser.add_argument("--shift-weekends", action="store_true", help="move weekend dates to Monday")
    parser.add_argument("--ics", help="write an .ics calendar file")
    args = parser.parse_args(argv)
    if args.months < 1:
        print("error: --months must be at least 1", file=sys.stderr)
        return 1
    try:
        tasks = load_tasks(args.csv)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    end = add_months(args.start, args.months) - timedelta(days=1)
    schedule = build_schedule(tasks, args.start, end, args.shift_weekends)
    print(f"{len(tasks)} tasks, {len(schedule)} visits from {args.start} to {end}")
    for month, hours in monthly_hours(schedule).items():
        count = sum(1 for s in schedule if s.due.strftime("%Y-%m") == month)
        print(f"{month}: {count:>3} visits, {hours:>5.1f} hours")
    print("\nFirst 8 visits")
    for item in schedule[:8]:
        print(f"{item.due} {item.due:%a}  {item.task.building:<10} {item.task.asset} - {item.task.task}")
    if args.ics:
        print(f"\nwrote {write_ics(args.ics, schedule)} events to {args.ics}")
    return 0
