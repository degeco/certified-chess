#!/usr/bin/env python3
"""Speed: entries/s of 03-checker (Python) and mcheck2 on the same files, by child CPU time
(user+sys, robust against other jobs sharing the machine) and by wall time."""
import subprocess, glob, time, resource, os
here = os.path.dirname(os.path.abspath(__file__))
PY = ["python3", os.path.join(here, "..", "03-checker", "mcheck.py")]
GO = [os.path.join(here, "mcheck2")]
def measure(cmd, files, env=None):
    r0 = resource.getrusage(resource.RUSAGE_CHILDREN); t0 = time.time(); n = 0
    for f in files:
        o = subprocess.run(cmd + ["verify", f], capture_output=True, text=True, env=env).stdout
        n += int([l for l in o.splitlines() if l.startswith("entries:")][0].split()[1])
    r1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (r1.ru_utime - r0.ru_utime) + (r1.ru_stime - r0.ru_stime)
    return n, cpu, time.time() - t0
sets = {
  "solver big (d3_b3, d3_c3_Rd2_b3, mini4x5_draw_w)": [os.path.join(here, "..", "05-solver", "certs", f + ".cert") for f in ("d3_b3", "d3_c3_Rd2_b3", "mini4x5_draw_w")],
  "300 small 5x5 tablebase certs": sorted(glob.glob(os.path.join(here, "..", "04-tablebase", "results", "certs_5x5", "*.cert")))[:300],
}
print(f"load average at start: {open('/proc/loadavg').read().split()[:3]}")
for name, fs in sets.items():
    print(name)
    for label, cmd, env in (("python", PY, None), ("go (4 threads)", GO, None), ("go (GOMAXPROCS=1)", GO, dict(os.environ, GOMAXPROCS="1"))):
        n, cpu, wall = measure(cmd, fs, env)
        print(f"  {label:18} {n:7d} entries  cpu {cpu:7.2f}s  wall {wall:7.2f}s  -> {n/cpu:10.0f} entries/cpu-s  {n/wall:10.0f} entries/wall-s")
