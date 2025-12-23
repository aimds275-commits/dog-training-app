import json
import datetime

# Load database
with open('db.json', encoding='utf-8') as f:
    db = json.load(f)

print("=" * 60)
print("DATABASE EVENT ANALYSIS")
print("=" * 60)

# Current time
now = datetime.datetime.now()
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

print(f"\nCurrent server time: {now}")
print(f"Today start: {today_start}")
print(f"Today timestamp: {int(today_start.timestamp())}")

# Show recent events
events = sorted(db['events'], key=lambda e: e['timestamp'], reverse=True)[:20]

print(f"\n20 Most Recent Events:")
print("-" * 60)

for ev in events:
    dt = datetime.datetime.fromtimestamp(ev['timestamp'])
    date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
    is_today = dt.date() == now.date()
    today_marker = " <-- TODAY" if is_today else ""
    print(f"{date_str} - {ev['type']:15} by userId {ev['userId'][:8]}... {today_marker}")

# Count today's events
today_events = [e for e in db['events'] if datetime.datetime.fromtimestamp(e['timestamp']).date() == now.date()]
print(f"\nTotal events today: {len(today_events)}")

# Group by type
from collections import Counter
today_types = Counter(e['type'] for e in today_events)
print("\nToday's events by type:")
for event_type, count in today_types.most_common():
    print(f"  {event_type}: {count}")
