import os
import time
import subprocess
import joblib
import pandas as pd

MODEL_PATH = "dynamos_scheduler_rf.pkl"

ENCODER_PATH = "dynamos_label_encoder.pkl"
INTERVAL = 1.0

CONTAINERS = [
    "workload-cpu",
    "workload-io",
    "workload-mixed",
]

FEATURE_COLS = [
    "cpu_ticks_per_second",
    "voluntary_context_switches_per_second",
    "involuntary_context_switches_per_second",
    "runqueue_wait_ns_per_second",
    "timeslices_per_second",
    "minor_page_faults_per_second",
    "major_page_faults_per_second",
]


def get_host_pid(container):
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Pid}}", container],
        capture_output=True,
        text=True,
        check=True,
    )

    pid = int(result.stdout.strip())

    if pid <= 0:
        raise RuntimeError(f"{container} is not running")

    return pid


def read_metrics(pid):
    # Read /proc/PID/stat, handling spaces in the process name.
    with open(f"/proc/{pid}/stat") as f:
        stat_line = f.read()

    end = stat_line.rfind(")")
    if end == -1:
        raise ValueError(f"Invalid stat data for PID {pid}")

    fields = stat_line[end + 2:].split()

    cpu_ticks = int(fields[11]) + int(fields[12])
    minor_faults = int(fields[7])
    major_faults = int(fields[9])

    voluntary = 0
    involuntary = 0

    with open(f"/proc/{pid}/status") as f:
        for line in f:
            if line.startswith("voluntary_ctxt_switches:"):
                voluntary = int(line.split()[1])
            elif line.startswith("nonvoluntary_ctxt_switches:"):
                involuntary = int(line.split()[1])

    with open(f"/proc/{pid}/schedstat") as f:
        sched = f.read().split()

    return {
        "pid": pid,
        "cpu_ticks": cpu_ticks,
        "voluntary_context_switches": voluntary,
        "involuntary_context_switches": involuntary,
        "runqueue_wait_ns": int(sched[1]),
        "timeslices": int(sched[2]),
        "minor_page_faults": minor_faults,
        "major_page_faults": major_faults,
    }


def calculate_features(previous, current, elapsed):
    features = {}

    mapping = {
        "cpu_ticks": "cpu_ticks_per_second",
        "voluntary_context_switches":
            "voluntary_context_switches_per_second",
        "involuntary_context_switches":
            "involuntary_context_switches_per_second",
        "runqueue_wait_ns": "runqueue_wait_ns_per_second",
        "timeslices": "timeslices_per_second",
        "minor_page_faults": "minor_page_faults_per_second",
        "major_page_faults": "major_page_faults_per_second",
    }

    for counter, feature in mapping.items():
        delta = current[counter] - previous[counter]

        # A counter reset should not become a negative rate.
        if delta < 0:
            raise ValueError(f"{counter} counter reset")

        features[feature] = delta / elapsed

    return features


def apply_scheduling(container, pid, workload):
    policies = {
        "workload-cpu":   {"nice": 5,  "shares": 768},
        "workload-io":    {"nice": 0, "shares": 1536},
        "workload-mixed": {"nice": 0,  "shares": 1024},
    }

    policy = policies.get(workload)

    if policy is None:
        print(f"Unknown workload: {workload}")
        return False

    try:
        subprocess.run(
            ["renice", "-n", str(policy["nice"]), "-p", str(pid)],
            check=True,
            capture_output=True,
            text=True,
        )

        subprocess.run(
            [
                "docker", "update",
                "--cpu-shares", str(policy["shares"]),
                container,
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        print(
            f"  SCHEDULING APPLIED: {container} | "
            f"nice={policy['nice']} | "
            f"cpu-shares={policy['shares']}"
        )
        return True

    except subprocess.CalledProcessError as e:
        print(
            f"  SCHEDULING FAILED: {container} | "
            f"{e.stderr.strip()}"
        )
        return False


def main():
    model = joblib.load(MODEL_PATH)
    encoder = joblib.load(ENCODER_PATH)

    print("Model loaded:", type(model).__name__)
    print("Expected features:", getattr(model, "n_features_in_", None))
    print("Classes:", list(encoder.classes_))
    print("\nStarting prediction-only controller...")
    print("Press Ctrl+C to stop.\n")

    previous = {}
    last_applied = {}

    while True:
        cycle_start = time.monotonic()

        for container in CONTAINERS:
            try:
                pid = get_host_pid(container)
                current = read_metrics(pid)

                old = previous.get(container)

                # First sample establishes a baseline.
                # A changed PID means the container process restarted.
                if old is None or old["pid"] != pid:
                    previous[container]={**current,"sample_time": time.monotonic(),}
                    print(f"{container}: collecting baseline...")
                    continue

                elapsed = time.monotonic() - old["sample_time"]

                # Store current counters for the next iteration.
                previous[container] = {
                    **current,
                    "sample_time": time.monotonic(),
                }

                if elapsed <= 0:
                    continue

                features = calculate_features(old, current, elapsed)

                X = pd.DataFrame(
                    [[features[name] for name in FEATURE_COLS]],
                    columns=FEATURE_COLS,
                )

                probabilities = model.predict_proba(X)[0]
                predicted_index=probabilities.argmax()
                predicted_class=encoder.inverse_transform([predicted_index])[0]


                confidence = float(probabilities.max())

                print(
                    f"{container} | PID={pid} | "
                    f"Prediction={predicted_class} | "
                    f"Confidence={confidence:.2%}"
                )
                confidence_threshold=0.70
                if confidence<confidence_threshold:
                    print(f"Low Confidence: {container} | {confidence:.2%} | keeping current policy")
                else:
                    policy_key=(pid,predicted_class)
                    if last_applied.get(container)!=policy_key:
                        success=apply_scheduling(container,pid,predicted_class)
                        if success:
                            last_applied[container]=policy_key
            except (OSError, ValueError, RuntimeError,
                    subprocess.SubprocessError) as e:
                print(f"{container}: unable to collect/predict: {e}")

        elapsed_cycle = time.monotonic() - cycle_start
        time.sleep(max(0, INTERVAL - elapsed_cycle))


if __name__ == "__main__":
    main()
