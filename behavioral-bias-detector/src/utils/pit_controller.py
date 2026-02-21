from datetime import datetime, timezone
from typing import Any, Callable


class PointInTimeController:
    """Validates that scenario context cannot include future knowledge."""

    def __init__(self, now_provider: Callable[[], datetime] | None = None):
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def now(self) -> datetime:
        return self._now_provider()

    def validate_context(self, context: dict[str, Any]) -> None:
        as_of = context.get("as_of")
        if not as_of:
            raise ValueError("historical_context.as_of is required")

        parsed = self._parse_as_of(as_of)
        if parsed > self.now():
            raise ValueError(f"Point-in-time violation: {parsed.isoformat()} is in the future")

    @staticmethod
    def _parse_as_of(value: str) -> datetime:
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(f"Invalid as_of timestamp: {value}") from exc

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
