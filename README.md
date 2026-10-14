# DynamOS - ML-Assisted CPU Scheduling in Operating Systems

A Linux-based project that generates different workload types and collects process-level scheduling telemetry as a foundation for an ML-assisted CPU scheduling system.

## Current Features

- **CPU workload:** Continuous computation.
- **I/O workload:** File operations with short sleeps.
- **Mixed workload:** Computation combined with file operations and sleeps.
- **Docker isolation:** Runs the three workloads in separate containers sharing the Debian VM's Linux kernel.
- **Telemetry collection:** Reads process metrics from `/proc` and stores them in a CSV file.

### Collected Metrics

- CPU time (clock ticks)
- Voluntary and involuntary context switches
- Run-queue wait time
- Number of timeslices
- Minor and major page faults

## Tech Stack

- Debian Linux
- Docker Engine
- Python 3
- Linux `/proc` filesystem
- CSV

## Project Structure

```text
ml-cpu-scheduler/
├── Dockerfile
├── workload.py
├── telemetry.py
└── data/
    └── results/
        └── telemetry.csv
```

## Prerequisites

- Debian Linux VM
- Docker Engine installed and running
- Python 3 installed

## How to Run

### 1. Build the Docker image

From the project directory:

```bash
sudo docker build -t cpu-workload .
```

### 2. Start the workloads

```bash
sudo docker run -d --name workload-cpu cpu-workload cpu
sudo docker run -d --name workload-io cpu-workload io
sudo docker run -d --name workload-mixed cpu-workload mixed
```

### 3. Verify the containers

```bash
sudo docker ps
sudo docker stats --no-stream
```

### 4. Start telemetry collection

In a separate terminal, navigate to the project directory and run:

```bash
sudo python3 telemetry.py
```

The collector samples each workload approximately once per second and writes the measurements to:

```text
data/results/telemetry.csv
```

Press `Ctrl+C` to stop collection.

### 5. Inspect the collected data

```bash
head -n 5 data/results/telemetry.csv
```

## Restarting the Workloads

To remove existing containers and recreate them:

```bash
sudo docker rm -f workload-cpu workload-io workload-mixed
```

Then repeat the commands in Step 2.

## Current Status

**Implemented:** Docker-based workload generation and process-level telemetry collection.

**Planned:** Feature extraction, ML model training, workload classification, a runtime scheduling controller, and performance evaluation against the default Linux scheduler.

The telemetry currently contains cumulative counters. Feature extraction must calculate changes between consecutive samples before using the metrics for ML training.
