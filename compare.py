
import pandas as pd

base_path = "data/results/benchmark/baseline_telemetry.csv"
dyn_path = "data/results/benchmark/dynamos_telemetry.csv"

base = pd.read_csv(base_path)
dyn = pd.read_csv(dyn_path)

metrics = [
    "cpu_ticks",
    "runqueue_wait_ns",
    "voluntary_context_switches",
    "involuntary_context_switches",
    "timeslices",
]

def summarize(df):
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values(["container", "timestamp"])

    # Convert cumulative counters into per-second rates.
    for col in metrics:
        delta = df.groupby("container")[col].diff()
        dt = df.groupby("container")["timestamp"].diff().dt.total_seconds()
        df[col + "_rate"] = (delta / dt).where((dt > 0) & (delta >= 0))

    rate_cols = [m + "_rate" for m in metrics]
    return df.groupby("container")[rate_cols].mean()

base_avg = summarize(base)
dyn_avg = summarize(dyn)

print("\nBASELINE: mean per-second rates")
print(base_avg.round(2))

print("\nDYNAMOS: mean per-second rates")
print(dyn_avg.round(2))

print("\nRelative change (%) — negative means the metric decreased")
change = (dyn_avg - base_avg) / base_avg.replace(0, float("nan")) * 100
print(change.round(2))
