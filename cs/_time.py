"""Market-local time helpers (DST-correct via zoneinfo).

The campaign follow-up windows are market-local ("reminder after the
reminder hour", "SMS from the evening hour"). Compute them from the
clone's configured timezone (manifest [knobs].timezone → settings),
NEVER a hardcoded UTC offset: an offset that is right in summer silently
shifts every window by an hour after the DST switch. This module is the
single source of "what time is it in the operator's market" for the
campaign verbs; a non-default-market clone changes the manifest knob,
not this file.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

_ZONES: dict[str, ZoneInfo] = {}


def _zone(tz_name: str) -> ZoneInfo:
    z = _ZONES.get(tz_name)
    if z is None:
        z = _ZONES[tz_name] = ZoneInfo(tz_name)
    return z


def now_utc() -> datetime:
    """Timezone-aware current instant in UTC."""
    return datetime.now(timezone.utc)


def to_local(dt: datetime, tz_name: str) -> datetime:
    """`dt` as a tz-aware datetime in the operator's market timezone.
    Naive input is read as UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_zone(tz_name))


def local_hour(dt: datetime, tz_name: str) -> int:
    """Hour-of-day (0–23) in the market timezone at instant `dt`."""
    return to_local(dt, tz_name).hour


def local_date(dt: datetime, tz_name: str) -> str:
    """Market-local calendar date 'YYYY-MM-DD' — the unit for per-day guards.

    Using the market's calendar day (not UTC) keeps "once per day" aligned
    with the operator's business day across the hours where the two dates
    differ.
    """
    return to_local(dt, tz_name).strftime("%Y-%m-%d")


def past_local_noon(dt: datetime, tz_name: str) -> bool:
    """True once it is >= 12:00 in the market timezone at instant `dt`."""
    return local_hour(dt, tz_name) >= 12


def parse_moment(text: str, tz_name: str) -> datetime:
    """An operator-typed ISO instant -> tz-aware UTC. Raises ValueError.

    A bare 'YYYY-MM-DD' means the END of that market-local day. Someone
    back-dating "I called him on the 18th" cannot be asked at what hour, and
    reading it as midnight would leave that same day's earlier mail looking
    open — precisely the false alarm the caller is trying to stop. A naive
    datetime is read in the market timezone (the clock the operator is looking
    at, not UTC); an aware one is taken as given.
    """
    t = (text or "").strip()
    if not t:
        raise ValueError("empty timestamp")
    try:  # date-only first: fromisoformat() would accept it as midnight
        d = date.fromisoformat(t)
    except ValueError:
        pass
    else:
        return datetime.combine(
            d, time(23, 59, 59), tzinfo=_zone(tz_name)
        ).astimezone(timezone.utc)
    try:
        dt = datetime.fromisoformat(t)
    except ValueError:
        raise ValueError(
            f"{text!r} is not an ISO date/time (expected YYYY-MM-DD or "
            "YYYY-MM-DDTHH:MM)"
        ) from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_zone(tz_name))
    return dt.astimezone(timezone.utc)
