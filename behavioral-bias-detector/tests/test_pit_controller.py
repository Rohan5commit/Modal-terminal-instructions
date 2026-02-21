from datetime import datetime, timedelta, timezone

import pytest

from src.utils.pit_controller import PointInTimeController


def test_rejects_future_timestamp():
    now = datetime(2026, 2, 21, tzinfo=timezone.utc)
    controller = PointInTimeController(now_provider=lambda: now)
    future = (now + timedelta(days=1)).isoformat()

    with pytest.raises(ValueError):
        controller.validate_context({"as_of": future})


def test_accepts_past_timestamp():
    now = datetime(2026, 2, 21, tzinfo=timezone.utc)
    controller = PointInTimeController(now_provider=lambda: now)
    past = (now - timedelta(days=1)).isoformat()
    controller.validate_context({"as_of": past})

