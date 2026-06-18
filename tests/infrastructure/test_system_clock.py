"""Tests for the system clock adapter."""

from fulcrum.infrastructure.system_clock import SystemClock


def test_timestamp_is_iso_string():
    stamp = SystemClock().timestamp()
    assert isinstance(stamp, str)
    assert "T" in stamp
