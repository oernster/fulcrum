"""Tests for the system clock adapter."""

from fulcrum.infrastructure.system_clock import SystemClock


def test_timestamp_is_human_readable_utc():
    stamp = SystemClock().timestamp()
    assert isinstance(stamp, str)
    assert stamp.endswith(" UTC")
