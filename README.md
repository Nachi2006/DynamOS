# DynamOS — ML-Assisted CPU Scheduling in Operating Systems

DynamOS is a prototype that integrates machine learning with Linux process scheduling to explore workload-aware CPU resource allocation. It classifies running workloads using runtime telemetry and applies scheduling policies based on the predicted workload category.

The project evaluates three workload types — CPU-bound, I/O-bound, and mixed — using Docker containers on a Debian Linux virtual machine.

## 1. Objectives

- Collect runtime scheduling and process telemetry from Linux.
- Extract meaningful features from cumulative operating-system counters.
- Classify workloads using a trained Random Forest model.
- Apply workload-specific scheduling policies using Linux process priorities and Docker CPU shares.
- Compare the proposed scheduling policy against default scheduling using measured performance metrics.

## 2. System Architecture

The DynamOS pipeline consists of the following stages:

1. **Workload Generation:** Three Python workloads simulate CPU-intensive, I/O-intensive, and mixed activity.
2. **Telemetry Collection:** Linux `/proc` interfaces provide CPU runtime, runqueue wait, timeslices, context switches, and page-fault counters.
3. **Feature Engineering:** Cumulative counters are converted into per-second rates.
4. **ML Classification:** A trained Random Forest classifier predicts the workload category from seven runtime features.
5. **Adaptive Scheduling:** The controller maps predicted workload classes to scheduling policies.
6. **Benchmarking:** Baseline and DynamOS runs are compared using scheduler metrics.

### Technology Stack

- **Operating System:** Debian Linux
- **Virtualization:** Oracle VirtualBox
- **Containerization:** Docker
- **Programming Language:** Python
- **Machine Learning:** Scikit-learn Random Forest Classifier
- **Data Processing:** Pandas
- **Model Persistence:** Joblib
- **Telemetry:** Linux `/proc` filesystem
- **Scheduling Controls:** Linux `renice` and Docker CPU-share configuration

## 3. Workload Generation

DynamOS uses three Docker containers to represent different execution patterns.

| Container | Workload | Behavior |
|---|---|---|
| `workload-cpu` | CPU-bound | Continuously performs arithmetic computations |
| `workload-io` | I/O-bound | Performs temporary-file operations and sleeps between operations |
| `workload-mixed` | Mixed | Combines arithmetic computation, file operations, and short sleeps |

Each container runs the Python workload generator with a mode specifying its behavior.

### Build and Start Workloads

```bash
cd ~/ml-cpu-scheduler

sudo docker build -t cpu-workload .

sudo docker run -d --name workload-cpu cpu-workload cpu
sudo docker run -d --name workload-io cpu-workload io
sudo docker run -d --name workload-mixed cpu-workload mixed
```

Inspect the running containers:

```bash
sudo docker ps
sudo docker stats --no-stream
```

If the containers already exist and need to be recreated:

```bash
sudo docker rm -f workload-cpu workload-io workload-mixed
```

## 4. Telemetry Collection

The `telemetry.py` script runs on the Debian host and collects metrics for each container's main process. Host PIDs are obtained through Docker inspection.

The collected counters include:

- **CPU ticks:** CPU time consumed by the process, measured in clock ticks.
- **Voluntary context switches:** Switches associated with the process yielding or blocking.
- **Involuntary context switches:** Switches where the process is preempted.
- **Runqueue wait:** Time spent runnable but waiting for CPU scheduling.
- **Timeslices:** Scheduler timeslice counter reported by `/proc/PID/schedstat`.
- **Minor page faults:** Page faults resolved without reading a page from storage.
- **Major page faults:** Page faults requiring storage I/O.

Run the telemetry collector:

```bash
sudo python3 telemetry.py
```

Stop collection using `Ctrl+C`.

Raw telemetry is written to:

```text
data/results/telemetry.csv
```

The recorded counters are cumulative. Therefore, raw counter values should not be directly compared between runs without accounting for elapsed time and counter resets.

## 5. Feature Engineering and Dataset Preparation

The feature-processing pipeline converts raw telemetry into per-second rates.

### Feature Extraction

The `features.py` script calculates differences between successive samples and derives rates for CPU ticks, context switches, runqueue wait, timeslices, and page faults.

```bash
python3 features.py
```

Output:

```text
data/results/features.csv
```

### Dataset Preparation

The `prepare_dataset.py` script associates known workload types with labels for supervised learning.

The labels correspond to the workload categories:

- CPU-bound
- I/O-bound
- Mixed

The prepared dataset is used for model training and evaluation.

## 6. Machine Learning Model

DynamOS uses a trained Random Forest classifier to identify workload categories from runtime features.

The model artifacts are:

```text
dynamos_scheduler_rf.pkl
dynamos_label_encoder.pkl
```

Training and evaluation notebooks:

```text
dynamos_ml_training.ipynb
dynamos_ml_training_with_results.ipynb
```

### Runtime Features

The controller uses seven features:

1. `cpu_ticks_per_second`
2. `voluntary_context_switches_per_second`
3. `involuntary_context_switches_per_second`
4. `runqueue_wait_ns_per_second`
5. `timeslices_per_second`
6. `minor_page_faults_per_second`
7. `major_page_faults_per_second`

The classifier returns a predicted workload class and class probabilities. The label encoder maps class indices to workload labels.

**Important:** The model and controller must use the same feature names, order, units, and preprocessing as the training pipeline. Model artifacts should be loaded with a compatible scikit-learn version.

## 7. Runtime Scheduling Controller

The `controller.py` script loads the trained model, samples runtime telemetry, predicts workload categories, and applies the configured scheduling policy.

The policy uses two mechanisms:

- **Linux nice value:** Adjusts relative scheduling priority for normal Linux processes. A lower nice value generally gives a process a higher scheduling priority.
- **Docker CPU shares:** Sets a container's relative CPU weight when CPU resources are contended. CPU shares are not a fixed CPU percentage or a guaranteed allocation.

### Current Tuned Policy

The tuned configuration used in the latest benchmark is intended to prioritize the CPU-bound workload less aggressively while increasing the relative CPU weight of the mixed workload.

| Workload | Nice value | CPU shares |
|---|---:|---:|
| CPU-bound | +5 | 768 |
| I/O-bound | +2 | 1024 |
| Mixed | 0 | 1536 |

Confirm that these values match the active `controller.py` configuration before reproducing the benchmark. The controller must be restarted after policy changes.

Start the controller:

```bash
sudo .venv/bin/python controller.py
```

Stop it with `Ctrl+C`.

The controller requires permissions to inspect processes and apply scheduling changes. Linux remains responsible for the actual selection and execution of runnable processes.

## 8. Benchmarking and Evaluation

DynamOS is evaluated by comparing default scheduling against the tuned workload-aware policy.

### Reset to Baseline

Stop the controller before resetting scheduling parameters.

```bash
for c in workload-cpu workload-io workload-mixed; do
    pid=$(sudo docker inspect -f '{{.State.Pid}}' "$c")
    sudo renice -n 0 -p "$pid"
    sudo docker update --cpu-shares 1024 "$c"
done
```

### Capture Baseline Measurements

The `benchmark_snapshot.py` script takes two scheduler-counter snapshots separated by a 10-second sleep and calculates rates using the measured elapsed time.

```bash
BENCHMARK_CONDITION=baseline python3 benchmark_snapshot.py
```

Repeat the measurement for additional trials.

### Capture Tuned DynamOS Measurements

Start the controller and verify that the intended policy has been applied. In another terminal, run:

```bash
BENCHMARK_CONDITION=dynamos_tuned python3 benchmark_snapshot.py
```

Repeat the measurement for additional trials.

Results are saved under:

```text
data/results/benchmark/
```

The snapshot script records CPU runtime per second, runqueue-wait milliseconds per second, and timeslices per second.

### Compare Results

Run:

```bash
python3 compare_snapshots.py
```

The comparison script calculates average metrics for each workload and the relative percentage change between baseline and tuned DynamOS.

For runqueue wait:

- A negative percentage change indicates a reduction in measured waiting.
- A positive percentage change indicates an increase in measured waiting.

Lower runqueue wait is a useful scheduling indicator, but it does not by itself prove higher throughput or shorter task completion time.

## 9. Preliminary Benchmark Results

The latest comparison reports averages across three trials per condition.

| Workload | Metric | Baseline | Tuned DynamOS | Change |
|---|---|---:|---:|---:|
| CPU-bound | CPU runtime (s/s) | 0.9870 | 0.9851 | −0.19% |
| CPU-bound | Runqueue wait (ms/s) | 0.2100 | 0.1210 | −42.35% |
| CPU-bound | Timeslices/s | 9.5137 | 8.1157 | −14.69% |
| I/O-bound | CPU runtime (s/s) | 0.0090 | 0.0089 | −0.70% |
| I/O-bound | Runqueue wait (ms/s) | 2.4801 | 2.2761 | −8.23% |
| I/O-bound | Timeslices/s | 82.4489 | 85.6931 | +3.93% |
| Mixed | CPU runtime (s/s) | 0.3460 | 0.3345 | −3.32% |
| Mixed | Runqueue wait (ms/s) | 7.1440 | 5.3400 | −25.25% |
| Mixed | Timeslices/s | 130.3111 | 118.1912 | −9.30% |

### Preliminary Findings

- The CPU-bound workload showed a 42.35% reduction in average runqueue-wait rate.
- The I/O-bound workload showed an 8.23% reduction.
- The mixed workload showed a 25.25% reduction.
- CPU runtime remained nearly unchanged for the CPU-bound and I/O-bound workloads and decreased by 3.32% for the mixed workload.

These results suggest reduced runqueue waiting under the tuned policy. They do not yet establish a statistically significant or overall performance improvement. Further repeated trials and direct measurements of throughput or task completion time are needed.

## 10. Project Structure

```text
ml-cpu-scheduler/
├── data/
│   └── results/
│       ├── benchmark/
│       │   ├── baseline_telemetry.csv
│       │   ├── dynamos_telemetry.csv
│       │   ├── dynamos_tuned_telemetry.csv
│       │   ├── baseline_snapshot.csv
│       │   └── dynamos_tuned_snapshot.csv
│       ├── telemetry.csv
│       ├── features.csv
├── Dockerfile
├── workload.py
├── telemetry.py
├── features.py
├── prepare_dataset.py
├── controller.py
├── benchmark_snapshot.py
├── compare_snapshots.py
├── dynamos_scheduler_rf.pkl
├── dynamos_label_encoder.pkl
├── dynamos_ml_training.ipynb
├── dynamos_ml_training_with_results.ipynb
├── README.md
└── .venv/
```

The exact files present under `data/results/benchmark/` depend on which experiments have been run.

## 11. Limitations

- Telemetry currently focuses on each container's main process rather than aggregating every process and thread in a container.
- Runqueue wait measures runnable time waiting for CPU, not total latency or I/O wait.
- Docker CPU shares influence relative allocation under contention and do not guarantee CPU percentages.
- Workload-specific policies may improve one workload while affecting another.
- The current benchmark does not independently establish throughput or completion-time improvements.
- Results can be affected by VM background activity, measurement duration, workload variability, and scheduling conditions.
- Model serialization compatibility must be maintained between training and runtime environments.

## 12. Future Scope

- Add repeated benchmark automation and report trial-to-trial variability.
- Measure workload throughput and task completion time.
- Evaluate scheduling fairness and controller overhead.
- Expand telemetry to container-level process aggregation.
- Test more workload types and resource-contention scenarios.
- Explore dynamic policy tuning based on measured outcomes.
- Improve model validation and assess classification accuracy on unseen workload samples.

## 13. Summary

DynamOS demonstrates an end-to-end prototype for ML-assisted, workload-aware CPU scheduling. It combines Docker-based workload generation, Linux telemetry, feature engineering, Random Forest classification, runtime scheduling controls, and baseline-versus-tuned benchmarking.

The current measurements show lower average runqueue-wait rates for all three workload types under the tuned policy. Further controlled evaluation is required to determine whether these reductions translate into consistent improvements in useful application performance.
