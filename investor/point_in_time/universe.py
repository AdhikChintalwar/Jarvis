from dataclasses import dataclass
from typing import Dict, Iterable, Optional

@dataclass
class UniverseMembership:
    symbol: str
    start: str
    end: Optional[str] = None
    reason: str = "observed_membership"

class PointInTimeUniverse:
    """Membership ledger; prevents today's survivors from masquerading as history."""
    def __init__(self, memberships: Iterable[UniverseMembership]=()):
        self.memberships=list(memberships)

    def active(self, as_of: str):
        return sorted({m.symbol.upper() for m in self.memberships
                       if m.start <= as_of and (m.end is None or as_of <= m.end)})

    def contains(self,symbol,as_of):
        return symbol.upper() in self.active(as_of)
