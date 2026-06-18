"""The real wall-clock, kept out of the domain behind the Clock Protocol."""

from __future__ import annotations

from datetime import datetime, timezone


class SystemClock:
    """A Clock backed by the real system time, in UTC ISO-8601 form."""

    def timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()
