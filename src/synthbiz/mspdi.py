"""MSPDI writer."""

import re
import xml.etree.ElementTree as ET
from datetime import date

from .io import NOTICE
from .project import DAY_MINUTES, WEEKDAYS, Link, ProjectDataset, Task
from .schema import DISCLAIMER

NAMESPACE = "http://schemas.microsoft.com/project"
LINK_TYPES = {"FF": 0, "FS": 1, "SF": 2, "SS": 3}
# days
FORMAT_DAYS = 7
DAILY_EXCEPTION = 1
CALENDAR_UID = 1
# Sunday=1
WORKING_DAY_TYPES = range(2, 2 + WEEKDAYS)
WORKING_TIMES = [("08:00:00", "12:00:00"), ("13:00:00", "17:00:00")]

COPYRIGHT = f"Copyright (c) 2026 Mehmet Tuzunkan. {NOTICE}"
COMMENT = f"<!-- {DISCLAIMER} {COPYRIGHT} -->"
# non-XML
INVALID = re.compile("[^\t\n\r\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]")


def _add(parent: ET.Element, tag: str, value: object = None) -> ET.Element:
    child = ET.SubElement(parent, tag)
    if value is not None:
        text = str(value)
        if INVALID.search(text):
            raise ValueError(f"{tag} holds a character that XML does not allow")
        child.text = text
    return child


def _calendar(root: ET.Element, holidays: list[tuple[date, str]]) -> None:
    calendar = _add(_add(root, "Calendars"), "Calendar")
    _add(calendar, "UID", CALENDAR_UID)
    _add(calendar, "Name", "Standard")
    _add(calendar, "IsBaseCalendar", 1)
    _add(calendar, "BaseCalendarUID", -1)
    week = _add(calendar, "WeekDays")
    for day_type in range(1, 8):
        day = _add(week, "WeekDay")
        _add(day, "DayType", day_type)
        working = day_type in WORKING_DAY_TYPES
        _add(day, "DayWorking", int(working))
        if working:
            times = _add(day, "WorkingTimes")
            for start, end in WORKING_TIMES:
                time = _add(times, "WorkingTime")
                _add(time, "FromTime", start)
                _add(time, "ToTime", end)
    exceptions = _add(calendar, "Exceptions")
    for when, name in holidays:
        item = _add(exceptions, "Exception")
        _add(item, "EnteredByOccurrences", 0)
        period = _add(item, "TimePeriod")
        _add(period, "FromDate", f"{when.isoformat()}T00:00:00")
        _add(period, "ToDate", f"{when.isoformat()}T23:59:00")
        _add(item, "Occurrences", 1)
        _add(item, "Name", name)
        _add(item, "Type", DAILY_EXCEPTION)
        _add(item, "DayWorking", 0)


def _task(tasks: ET.Element, task: Task, links: list[Link]) -> None:
    element = _add(tasks, "Task")
    _add(element, "UID", task.uid)
    _add(element, "ID", task.uid)
    _add(element, "Name", task.name)
    _add(element, "WBS", task.wbs)
    _add(element, "OutlineNumber", task.wbs)
    _add(element, "OutlineLevel", task.level)
    if not task.summary:
        hours, minutes = divmod(task.duration_minutes, 60)
        _add(element, "Duration", f"PT{hours}H{minutes}M0S")
        _add(element, "DurationFormat", FORMAT_DAYS)
    _add(element, "Milestone", int(task.milestone))
    _add(element, "Summary", int(task.summary))
    # hundredths
    _add(element, "FixedCost", task.fixed_cost_cents)
    _add(element, "Cost", task.cost_cents)
    for link in links:
        item = _add(element, "PredecessorLink")
        _add(item, "PredecessorUID", link.pred_uid)
        _add(item, "Type", LINK_TYPES[link.kind])
        # tenths
        _add(item, "LinkLag", link.lag_minutes * 10)
        _add(item, "LagFormat", FORMAT_DAYS)


def project_xml(ds: ProjectDataset) -> bytes:
    root = ET.Element("Project", xmlns=NAMESPACE)
    _add(root, "SaveVersion", 12)
    _add(root, "Name", "project.xml")
    _add(root, "Title", "Synthetic project plan (synthetic data)")
    _add(root, "ScheduleFromStart", 1)
    _add(root, "StartDate", f"{ds.start.isoformat()}T{WORKING_TIMES[0][0]}")
    _add(root, "CurrencyDigits", 2)
    _add(root, "CurrencyCode", "USD")
    _add(root, "CalendarUID", CALENDAR_UID)
    _add(root, "DefaultStartTime", WORKING_TIMES[0][0])
    _add(root, "DefaultFinishTime", WORKING_TIMES[-1][1])
    _add(root, "MinutesPerDay", DAY_MINUTES)
    _add(root, "MinutesPerWeek", DAY_MINUTES * WEEKDAYS)
    _add(root, "DaysPerMonth", 20)
    _calendar(root, ds.holidays)
    into: dict[int, list[Link]] = {}
    for link in ds.links:
        into.setdefault(link.succ_uid, []).append(link)
    tasks = _add(root, "Tasks")
    for task in ds.tasks:
        _task(tasks, task, into.get(task.uid, []))
    ET.indent(root)
    head = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    body = ET.tostring(root, encoding="unicode")
    return f"{head}\n{COMMENT}\n{body}\n".encode()
