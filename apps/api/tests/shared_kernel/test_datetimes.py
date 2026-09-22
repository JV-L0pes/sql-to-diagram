from datetime import UTC, datetime

from src.shared_kernel.datetimes import ensure_utc, utc_now


def test_utc_now_is_timezone_aware():
    assert utc_now().tzinfo is UTC


def test_ensure_utc_adds_utc_to_naive_values():
    naive = datetime(2026, 1, 1, 12, 0, 0)
    assert ensure_utc(naive).tzinfo is UTC


def test_ensure_utc_leaves_aware_values_unchanged():
    aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    assert ensure_utc(aware) is aware
