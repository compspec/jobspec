#!/usr/bin/env python3

import time
import argparse

from jobspec.transformer.flux import FluxHierarchy
from jobspec.logger import LogColors

def parse_args():
    parser = argparse.ArgumentParser(description="Run job throughput test on a Flux Hierarchy")
    parser.add_argument("config", help="Path to the FluxHierarchy YAML configuration file")
    parser.add_argument("-n", "--njobs", type=int, metavar="N", help="Total number of jobs to run", default=100)
    parser.add_argument("-t", "--runtime", help="Simulated runtime of each job (default=1ms)", default="0.001s")
    parser.add_argument("-x", "--exec", help="Do not simulate, actually run jobs", action="store_true")
    parser.add_argument("-o", "--setopt", action="append", help="Set shell option OPT or OPT=VAL", metavar="OPT")
    parser.add_argument("--setattr", action="append", help="Set job attribute ATTR=VAL", metavar="ATTR=VAL")
    parser.add_argument("command", nargs=argparse.REMAINDER, default=["true"])
    return parser.parse_args()

def main():
    args = parse_args()

    # Instantiate, build, and connect to the Flux Hierarchy!
    hierarchy = FluxHierarchy(args.config)
    hierarchy.start(interactive=False)

    # Default to true if not set.
    if not args.command:
        args.command = ["true"]

    # Run the throughput test using the specialized 'throughput' method
    time0 = time.time()
    jobs = hierarchy.throughput(args.command, args.njobs)
    
    if not jobs:
        print(f"{LogColors.RED}No jobs were tracked. Cannot calculate throughput.{LogColors.ENDC}")
        return

    # 3. Analyze and print results (logic is unchanged)
    first = jobs[min(jobs.keys(), key=lambda x: jobs[x].get("submit", type("o", (), {"timestamp": float('inf')})()).timestamp)]
    last = jobs[max(jobs.keys(), key=lambda x: jobs[x].get("clean", type("o", (), {"timestamp": float('-inf')})()).timestamp)]
    lastsubmit = jobs[max(jobs.keys(), key=lambda x: jobs[x]["t_submit"])]
    
    submit_time = lastsubmit["t_submit"] - time0
    sjps = args.njobs / submit_time if submit_time > 0 else float('inf')    
    script_runtime = time.time() - time0

    job_runtime = last["clean"].timestamp - first["submit"].timestamp
    jps = args.njobs / job_runtime if job_runtime > 0 else float('inf')
    jpsb = args.njobs / script_runtime if script_runtime > 0 else float('inf')

    print(f"\n--- Throughput Results ---")
    print(f"number of jobs: {args.njobs} (on {len(hierarchy.handles)} workers)")
    print(f"   submit time: {submit_time:<6.3f}s ({sjps:5.1f} job/s)")
    print(f"script runtime: {script_runtime:<6.3f}s")
    print(f"   job runtime: {job_runtime:<6.3f}s")
    print(f"    throughput: {jps:<.1f} job/s (script: {jpsb:5.1f} job/s)")


if __name__ == "__main__":
    main()