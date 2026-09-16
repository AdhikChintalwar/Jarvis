from investor.primary_data import CrossSourceValidator

v = CrossSourceValidator()

tests = [
    ("revenue", 100_000_000_000, 99_400_000_000, "FY2025", "FY2025"),
    ("revenue", 100_000_000_000, 83_000_000_000, "FY2025", "FY2025"),
    ("revenue", 100_000_000_000, 99_400_000_000, "FY2025", "TTM"),
    ("net_margin", 0.269, 0.265, "FY2025", "FY2025"),
]

for test in tests:
    result = v.validate(*test)
    print(result.metric, result.status, result.confidence, result.selected_source)
