import csv
import os
import subprocess
import time
from datetime import datetime,timezone

CONTAINERS=["workload-cpu","workload-io","workload-mixed"]
OUTPUT="data/results/telemetry.csv"
INTERVAL=1.0

os.makedirs(os.path.dirname(OUTPUT),exist_ok=True)

def get_host_pid(container):
	result=subprocess.run(
	["docker","inspect","-f","{{.State.Pid}}",container],
	capture_output=True,
	text=True
	)
	if result.returncode!=0:
		return None

	try:
		pid=int(result.stdout.strip())
		return pid if pid>0 else None
	except ValueError:
		return None

def read_process_metrics(pid):
	with open(f"/proc/{pid}/stat") as f:
		stat=f.read()
	fields=stat[stat.rfind(")")+2:].split()
	cpu_ticks=int(fields[11])+int(fields[12])
	minor_faults=int(fields[7])
	major_faults=int(fields[9])
	with open(f"/proc/{pid}/status") as f:
		status=f.readlines()
	voluntary=0
	involuntary=0

	for line in status:
		if line.startswith("voluntary_ctxt_switches:"):
			voluntary=int(line.split()[1])
		elif line.startswith("nonvoluntary_ctxt_switches:"):
			involuntary=int(line.split()[1])
	with open(f"/proc/{pid}/schedstat") as f:
		sched=f.read().split()

	return {
		"cpu_ticks":cpu_ticks,
		"voluntary_context_switches":voluntary,
		"involuntary_context_switches":involuntary,
		"runqueue_wait_ns":int(sched[1]),
		"timeslices":int(sched[2]),
		"minor_page_faults":minor_faults,
		"major_page_faults":major_faults,
	}

def main():
	columns=[
		"timestamp",
		"container",
		"host_pid",
		"cpu_ticks",
		"voluntary_context_switches",
		"involuntary_context_switches",
		"runqueue_wait_ns",
		"timeslices",
		"minor_page_faults",
		"major_page_faults",
	]
	print(f"Collecting telemetry entry {INTERVAL} second(s).")
	print(f"Output: {OUTPUT}")
	print("Press Ctrl+C to stop. \n")
	with open(OUTPUT,"w",newline="") as f:
		writer=csv.DictWriter(f,fieldnames=columns)
		writer.writeheader()
		try:
			while True:
				for container in CONTAINERS:
					pid=get_host_pid(container)
					if pid is None:
						print(f"{container}: not running; skipping")
						continue
					try:
						metrics=read_process_metrics(pid)
						row={
						"timestamp":datetime.now(timezone.utc).isoformat(),
						"container":container,
						"host_pid":pid,
						**metrics,
						}
						writer.writerow(row)
						f.flush()

						print(
						f"{container:14} PID={pid:<6} "
						f"CPU_ticks={metrics['cpu_ticks']:<8} "
						f"voluntary_cs="
						f"{metrics['voluntary_context_switches']:<8} "
						f"runqueue_wait_ns="
						f"{metrics['runqueue_wait_ns']}"
						)
					except Exception as e:
						print(f"{container}: {type(e).__name__}:{e}",flush=True)
				time.sleep(INTERVAL)
		except KeyboardInterrupt:
			print("\nTelemetry collection stopped.")

if __name__=="__main__":
	main()
