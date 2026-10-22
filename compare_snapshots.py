
import pandas as pd

base_path = "data/results/benchmark/baseline_snapshot.csv"
dyn_path = "data/results/benchmark/dynamos_tuned_snapshot.csv"

base = pd.read_csv(base_path)
dyn = pd.read_csv(dyn_path)

metrics = [
    "cpu_seconds_per_second",
    "runqueue_wait_ms_per_second",
    "timeslices_per_second",
]

for df in (base, dyn):
    for metric in metrics:
        df[metric] = pd.to_numeric(df[metric], errors="coerce")

base_avg = base.groupby("container")[metrics].mean()
dyn_avg = dyn.groupby("container")[metrics].mean()

print("\n=== BASELINE AVERAGES ===")
print(base_avg.round(4))

print("\n=== TUNED DYNAMOS AVERAGES ===")
print(dyn_avg.round(4))

print("\n=== RELATIVE CHANGE (%) ===")
change = (
    (dyn_avg - base_avg)
    / base_avg.replace(0, float("nan"))
    * 100
)
print(change.round(2))
