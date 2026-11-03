"""Horário de funcionamento (manual §2) e situação da loja em um dado momento."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import holidays

WEEKDAY_HOURS = (time(9), time(18))
SATURDAY_HOURS = (time(9), time(13))
SATURDAY = 5
SUNDAY = 6
MAX_LOOKAHEAD_DAYS = 14


def _holiday_name(day: date) -> str | None:
    # Feriados nacionais e de MS. Feriados municipais de Campo Grande não estão cobertos.
    return holidays.country_holidays("BR", subdiv="MS", years=day.year).get(day)


def hours_on(day: date) -> tuple[time, time] | None:
    if _holiday_name(day) or day.weekday() == SUNDAY:
        return None
    return SATURDAY_HOURS if day.weekday() == SATURDAY else WEEKDAY_HOURS


@dataclass(frozen=True)
class StoreStatus:
    is_open: bool
    closes_at: datetime | None
    next_opening: datetime | None
    holiday: str | None


def store_status(moment: datetime) -> StoreStatus:
    today_hours = hours_on(moment.date())
    if today_hours and today_hours[0] <= moment.time() < today_hours[1]:
        closes_at = datetime.combine(moment.date(), today_hours[1], tzinfo=moment.tzinfo)
        return StoreStatus(True, closes_at, None, None)
    return StoreStatus(False, None, _next_opening(moment), _holiday_name(moment.date()))


def _next_opening(moment: datetime) -> datetime | None:
    for offset in range(MAX_LOOKAHEAD_DAYS):
        day = moment.date() + timedelta(days=offset)
        day_hours = hours_on(day)
        if not day_hours:
            continue
        opening = datetime.combine(day, day_hours[0], tzinfo=moment.tzinfo)
        if opening > moment:
            return opening
    return None
