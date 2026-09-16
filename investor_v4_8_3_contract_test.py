import re
from types import SimpleNamespace as NS
import numpy as np
import pandas as pd

from investor.trade_plan_v46 import TradePlanAgent
import investor.trade_plan as legacy_module

# Discover the legacy dependencies dynamically. This prevents future regressions
# when TradePlanBuilder starts reading another technical attribute.
source = open(legacy_module.__file__, "r", encoding="utf-8").read()
required = sorted(set(re.findall(r"\btechnical\.([A-Za-z_][A-Za-z0-9_]*)", source)))

idx = pd.date_range("2025-01-01", periods=260, freq="B")
close = pd.Series(np.linspace(80, 120, 260), index=idx)
history = pd.DataFrame({
    "Open": close - .5, "High": close + 1, "Low": close - 1,
    "Close": close, "Volume": 1_000_000
})

# Deliberately incomplete packet.
minimal = NS(ema_20=118.0)
adapter = TradePlanAgent._legacy_technical_adapter(minimal, history, 2.0)

missing = [name for name in required if not hasattr(adapter, name)]
assert not missing, f"Legacy technical dependencies missing: {missing}"

for name in required:
    value = getattr(adapter, name)
    assert value is not None, f"Legacy technical dependency unresolved: {name}"

assert hasattr(adapter, "distance_from_ema20_pct")
assert isinstance(adapter.distance_from_ema20_pct, (int, float))

print("V4.8.3 complete legacy compatibility contract: PASS")
print("legacy dependencies:", required)
print("distance_from_ema20_pct:", adapter.distance_from_ema20_pct)
