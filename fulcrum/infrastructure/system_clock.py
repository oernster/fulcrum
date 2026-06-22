"""The real wall-clock, kept out of the domain behind the Clock Protocol."""

from __future__ import annotations

from datetime import datetime, timezone

_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


class SystemClock:
    """A Clock backed by the real system time, as a human-readable UTC string."""

    def timestamp(self) -> str:
        # Human-friendly UTC for report headers and saved games, to the second
        # (no sub-second noise): e.g. "22 June 2026, 14:30:45 UTC". A fixed
        # month list keeps it English regardless of the system locale.
        now = datetime.now(timezone.utc)
        return f"{now.day} {_MONTHS[now.month - 1]} {now.year}, {now:%H:%M:%S} UTC"
