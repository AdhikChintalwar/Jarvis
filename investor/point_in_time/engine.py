from typing import Dict, Iterable, Optional
from .availability import AvailabilityPolicy
from .models import EvidenceItem, ResearchSnapshot
from .snapshot_store import PointInTimeSnapshotStore

class PointInTimeResearchEngine:
    """Builds an immutable research snapshot from evidence known at `as_of`.

    This intentionally does NOT reconstruct historical fundamentals from today's
    latest statements. Historical evidence must carry a real available_at/filing
    timestamp or it is excluded.
    """
    def __init__(self,store=None,policy=None):
        self.store=store or PointInTimeSnapshotStore()
        self.policy=policy or AvailabilityPolicy()

    def build_snapshot(self,symbol,as_of,universe_as_of,market_data_as_of,
                       evidence:Iterable[EvidenceItem],eligible=True,
                       exclusion_reasons=None,provenance=None):
        accepted={}
        blocked=[]
        for e in evidence:
            if self.policy.usable(e.available_at,as_of):
                accepted[e.name]=e
            else:
                blocked.append({"name":e.name,"available_at":e.available_at})
        snap=ResearchSnapshot(
            symbol=symbol.upper(),as_of=as_of,universe_as_of=universe_as_of,
            market_data_as_of=market_data_as_of,evidence=accepted,eligible=eligible,
            exclusion_reasons=list(exclusion_reasons or []),
            provenance={**(provenance or {}),"blocked_future_evidence":blocked,
                        "schema_version":"5.0"}
        )
        self.store.save(snap)
        return snap
