
import subprocess
import time
import csv
import os
from datetime import datetime

CONTAINERS = [
    "workload-cpu",
    "workload-io",
    "workload-mixed",
]

DURATION = 10
OUTPUT_DIR = "data/results/benchmark"


def snapshot():
    result = {}

    for container in CONTAINERS:
        pid = subprocess.check_output(
            [
                "sudo", "docker", "inspect",
                "-f", "{{.State.Pid}}", container
            ],
            text=True,
        ).strip()

        pid = int(pid)

        with open(f"/proc/{pid}/schedstat") as f:
            values = tuple(map(int, f.read().split()))

        result[container] = (pid, values)

    return result


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Taking initial snapshot...")
    start_time = time.monotonic()
    first = snapshot()

    time.sleep(DURATION)

    second = snapshot()
    end_time = time.monotonic()
    elapsed = end_time - start_time

    timestamp = datetime.now().isoformat(timespec="seconds")

    rows = []

    print(f"\nElapsed: {elapsed:.3f} seconds\n")

    for container in CONTAINERS:
        pid1, before = first[container]
        pid2, after = second[container]

        if pid1 != pid2:
            print(f"{container}: PID changed; skipping sample")
            continue

        cpu_delta = after[0] - before[0]
        wait_delta = after[1] - before[1]
        slices_delta = after[2] - before[2]

        if min(cpu_delta, wait_delta, slices_delta) < 0:
            print(f"{container}: counter reset; skipping sample")
            continue

        cpu_seconds_per_second = cpu_delta / elapsed / 1e9
        wait_ms_per_second = wait_delta / elapsed / 1e6
        slices_per_second = slices_delta / elapsed

        row = {
            "timestamp": timestamp,
            "condition": os.environ.get("BENCHMARK_CONDITION", "unspecified"),
            "container": container,
            "pid": pid1,
            "elapsed_seconds": elapsed,
            "cpu_seconds_per_second": cpu_seconds_per_second,
            "runqueue_wait_ms_per_second": wait_ms_per_second,
            "timeslices_per_second": slices_per_second,
        }

        rows.append(row)

        print(container)
        print(f"  CPU runtime/s: {cpu_seconds_per_second:.3f}")
        print(f"  Runqueue wait ms/s: {wait_ms_per_second:.3f}")
        print(f"  Timeslices/s: {slices_per_second:.2f}")

    if rows:
        filename = os.path.join(
            OUTPUT_DIR,
            f"{os.environ.get('BENCHMARK_CONDITION', 'unspecified')}_snapshot.csv",
        )

        write_header = not os.path.exists(filename)

        with open(filename, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())

            if write_header:
                writer.writeheader()

            writer.writerows(rows)

        print(f"\nSaved results to {filename}")


if __name__ == "__main__":
    main()
