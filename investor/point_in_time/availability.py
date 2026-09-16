from datetime import datetime, timezone
from typing import Optional

class AvailabilityPolicy:
    """Central no-lookahead policy.

    A datum may be used only when its real-world availability timestamp is
    <= the simulated decision timestamp. Period end alone is never sufficient
    for company fundamentals.
    """
    @staticmethod
    def _dt(x: Optional[str]):
        if not x: return None
        s=str(x).replace("Z","+00:00")
        d=datetime.fromisoformat(s)
        if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)

    def usable(self, available_at: Optional[str], as_of: str) -> bool:
        a=self._dt(available_at); t=self._dt(as_of)
        return bool(a and t and a <= t)

    def assert_usable(self, available_at: Optional[str], as_of: str, name="evidence"):
        if not self.usable(available_at,as_of):
            raise ValueError(f"LOOKAHEAD_BLOCKED: {name} available_at={available_at} as_of={as_of}")
