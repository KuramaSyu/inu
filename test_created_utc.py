from datetime import datetime

# Simulate submission with created_utc as Unix timestamp (float)
class MockSubmission:
    created_utc = 1752364800.0  # 2025-07-13 00:00:00 UTC
    title = "Top 10 Anime of the Week #7 - Summer 2026 (Anime Corner)"

sub = MockSubmission()
print(f"created_utc type: {type(sub.created_utc)}")
print(f"created_utc value: {sub.created_utc}")
try:
    ranking_date: datetime = sub.created_utc or datetime.now()
    print(f"ranking_date after first line: {ranking_date!r}, type: {type(ranking_date)}")
    ranking_date = datetime(ranking_date.year, ranking_date.month, ranking_date.day)
    print(f"ranking_date after second line: {ranking_date}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")