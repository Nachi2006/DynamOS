import os
import sys
import time
import tempfile
mode=sys.argv[1] if len(sys.argv)>1 else "cpu"

if mode not in ("cpu","io","mixed"):
	print("Usage: workload.py [cpu|io|mixed]")
	sys.exit(1)

print(f"Starting {mode} workload; PID={os.getpid()}", flush=True)
with tempfile.TemporaryFile() as f:
	while True:
		if mode=="cpu":
			total=0
			for i in range(100000):
				total+=i*i
		elif mode=="io":
			f.seek(0)
			f.write(b"x"*4096)
			f.flush()
			f.seek(0)
			f.read(4096)
			time.sleep(0.01)
		else:
			total=0
			for i in range(50000):
				total+=i*i

			f.seek(0)
			f.write(b"x"*4096)
			f.flush()
			f.seek(0)
			f.read(4096)
			time.sleep(0.005)

