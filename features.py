import csv
import os
from collections import defaultdict
from datetime import datetime

INPUT = "data/results/telemetry.csv"
OUTPUT = "data/results/features.csv"

COUNTERS = [
    "cpu_ticks",
    "voluntary_context_switches",
    "involuntary_context_switches",
    "runqueue_wait_ns",
    "timeslices",
    "minor_page_faults",
    "major_page_faults",
]

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

previous = {}
rows = []

with open(INPUT, "r", newline="") as f:
    reader = csv.DictReader(f)

    for row in reader:
        container = row["container"]
        timestamp = datetime.fromisoformat(row["timestamp"])

        current = {key: int(row[key]) for key in COUNTERS}

        if container in previous:
            prev_time, prev_values = previous[container]
            elapsed = (timestamp - prev_time).total_seconds()

            if elapsed > 0:
                features = {
                    "timestamp": row["timestamp"],
                    "container": container,
                    "host_pid": row["host_pid"],
                    "interval_seconds": elapsed,
                }

                valid = True

                for key in COUNTERS:
                    delta = current[key] - prev_values[key]

                    # Ignore counter resets or process restarts.
                    if delta < 0:
                        valid = False
                        break

                    features[key + "_delta"] = delta
                    features[key + "_per_second"] = delta / elapsed

                if valid:
                    rows.append(features)

        previous[container] = (timestamp, current)

if not rows:
    print("No feature rows generated. Collect more telemetry first.")
    raise SystemExit(1)

with open(OUTPUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated {len(rows)} feature rows.")
print(f"Output: {OUTPUT}")
