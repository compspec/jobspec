import tempfile  # Add to your imports
import subprocess  # Add to your imports
import shlex  # Add to your imports
import multiprocessing
import threading
import itertools
import os
import json
import os
import re
import subprocess
import sys
import tempfile
import multiprocessing
import time

import jobspec.utils as utils
from jobspec.logger import LogColors

try:
    import flux
    import flux.job
except ImportError:
    flux = None


class FluxHierarchy:
    """
    A FluxHierarchy allows for immediate or dynamic submisison of
    jobs to a hierarchy of Flux instances. To start, we calculate
    instance sizes based on the resources given at the top level.

    # TODO: should be able to read in directory of active sockets.
    """

    def __init__(self, config_path, outdir=None):
        """
        Create an output directory for jobspecs and submit files.
        """
        # We will store a lookup of uris
        self.config = utils.read_yaml(config_path)

        # You can't handle me right now.
        self.uris = {}
        self.handles = {}

        self.outdir = outdir or tempfile.mkdtemp(prefix="flux-hierarchy-")
        self.socket_dir = os.path.join(self.outdir, "sockets")
        os.makedirs(self.socket_dir, exist_ok=True)
        self.groups = {g["name"]: g for g in self.config["groups"]}

        # Still thinking about this one. I think it should be possible
        # to define an entire tree, but then only create a subgraph of it
        # This is the entrypoint.
        self.entrypoint = self.config["entrypoint"]

    @property
    def resources(self):
        return self.config["resources"]

    def pprint(self, message):
        """
        Print a pretty section!
        """
        print(f"=> {LogColors.OKCYAN}{message}{LogColors.ENDC}", end="")

    def check(self):
        """
        Check to make sure we have imported flux.
        """
        if not flux:
            raise ValueError("Cannot import flux, which is needed here.")

    def start(self, interactive=True):
        """
        Start a flux hierarchy of a specific size. Currently, let's not submit
        commands entire the entire thing is created, and we will call this a
        startup cost.
        """
        self.check()

        # Provide the first instance level (0)
        self.pprint(f"🌲 Generating Flux Hierarchy...\n")
        filepath = self.generate(self.entrypoint, "0")

        # This launches our entrypoint to create nested hierarchy
        self.pprint(f"\n🚗 Starting...")
        cmd = ["flux", "job", "submit", "--flags=waitable", filepath]
        utils.run_command(cmd, check_output=True)

        self.pprint(f"\n🌿 Leaf Broker Workers...")
        print(json.dumps(self.uris, indent=2))
        self.print_tree()

        # Give the user an interactive mode
        self.connect()
        if interactive:
            self.interactive()

        # Assume we want to return URIs to interact with
        return self.uris

    def connect(self):
        """
        Connect to all leaf broker URIs and store the handles.
        """
        if not self.uris:
            return
        # IMPORTANT: if you do this immediately it will fail - the sockets need a setup delay
        self.pprint(f"\nWaiting for {len(self.uris)} leaf brokers...\n")
        time.sleep(10)
        for name, uri in self.uris.items():
            self.handles[name] = flux.Flux(uri)
            self.handles[name].uri = uri
        self.pprint(f"Connected!\n")

    def interactive(self):
        """
        Interactive mode to submit.
        """
        print(f"\n{LogColors.BOLD}Dropping into an interactive IPython shell.{LogColors.ENDC}")
        print("The 'self' object is the FluxHierarchy instance.")
        print(
            f"Throughput test: {LogColors.OKCYAN}results = self.throughput(['sleep', '1'], 16){LogColors.ENDC}"
        )
        print(
            f"    Submit jobs: {LogColors.OKCYAN}results = self.submit_jobs([['hostname'], ['date']]){LogColors.ENDC}"
        )
        import IPython

        IPython.embed()

    def generate(self, group_name, instance_path):
        """
        Recursively generate and save a self-contained jobspec for a group.
        """
        print(f"- Generating: {group_name} (instance: {instance_path})")
        group = self.groups[group_name]

        # A group is a leaf if it does NOT have a launch section.
        is_leaf_group = "launch" not in group

        # The resources label points to resources for the group
        label = group["resources"]
        jobspec_filename = os.path.abspath(
            os.path.join(self.outdir, f"jobspec-{group_name}-{instance_path}.json")
        )

        # A leaf broker runs a broker that we can submit to
        if is_leaf_group:
            socket_path = os.path.abspath(
                os.path.join(self.socket_dir, f"broker-{instance_path}.sock")
            )
            uri_string = f"local://{socket_path}"
            self.uris[instance_path] = uri_string

            command = ["flux", "broker", "-S", f"local-uri={uri_string}", "sleep", "infinity"]
            jobspec = get_jobspec_from_dry_run(command, self.resources[label])

        # If we get here, we are generating an intermediate node.
        else:
            # Recursively generate all child files and collect their paths
            child_paths = []
            for task in group["launch"]:
                name = task["group"]
                count = task.get("count") or 1

                for _ in range(count):
                    task_path = f"{instance_path}-{len(child_paths)}"
                    child_path = self.generate(name, task_path)
                    child_paths.append(child_path)

            # Use flux trick to generate inner file for broker to execute
            script_path = os.path.abspath(
                os.path.join(self.outdir, f"inner-script-{group_name}-{instance_path}.sh")
            )
            script = self.generate_script(child_paths)
            utils.write_file(script, script_path, executable=True)

            # 3. Get the jobspec for this intermediate broker
            command = ["flux", "broker", script_path]
            jobspec = get_jobspec_from_dry_run(command, self.resources[label])

        # Save the jobspec for the leaf or intermediate node.
        utils.write_json(jobspec, jobspec_filename)
        return jobspec_filename

    def generate_script(self, child_paths):
        """
        Generate an intermediate worker script.

        Jinja2 would be better here, but don't want to add dependency.
        """
        script = "#!/bin/bash\n"
        script += "set -euo pipefail\n\n"
        for child_path in child_paths:
            script += f"flux job submit --flags=waitable {child_path}\n"
        script += "\nflux job wait --all\n"
        return script

    def print_tree(self):
        """
        Print a pretty ASCII tree of the hierarchy defined in the config.
        THERE IS NO OTHER WAY.
        """
        self._print_tree_recursive(self.entrypoint)

    def _print_tree_recursive(self, group_name, prefix="", is_last=True):
        """
        A recursive helper function to print the hierarchy tree.
        """
        group = self.groups[group_name]
        resource_key = group["resources"]
        resource_def = self.resources[resource_key]

        # Make a resource string to show structure
        parts = []
        if "nodes" in resource_def:
            parts.append(f"Nodes: {resource_def['nodes']}")
        if "cores" in resource_def:
            parts.append(f"Cores: {resource_def['cores']}")
        if "count" in resource_def:
            parts.append(f"Tasks: {resource_def['count']}")
        result = f"[{', '.join(parts)}]"

        # Determine the branch character and color for leaf/intermediate nodes
        is_leaf = "launch" not in group
        branch_char = "└── " if is_last else "├── "

        # Make the leaves green!
        name_color = LogColors.OKGREEN if is_leaf else LogColors.OKBLUE

        # The root node has no prefix
        if prefix == "":
            print(f"{name_color}{LogColors.BOLD}{group_name}{LogColors.ENDC} {result}")
        else:
            print(f"{prefix}{branch_char}{name_color}{group_name}{LogColors.ENDC} {result}")

        # If it's an intermediate node, recurse
        if not is_leaf:

            # Create a flat list of all children to launch
            children_to_launch = []
            for task in group.get("launch", []):
                count = task.get("count", 1)
                children_to_launch.extend([task["group"]] * count)

            # Recurse, adjusting the prefix for the next level
            num_children = len(children_to_launch)
            for i, child_name in enumerate(children_to_launch):
                is_child_last = i == num_children - 1
                new_prefix = prefix + ("    " if is_last else "│   ")
                self._print_tree_recursive(child_name, new_prefix, is_child_last)

    def submit_jobs(self, commands):
        """
        Submits a list of jobs using a multiprocessing pool where each
        worker executes `flux bulksubmit`.
        """
        self.pprint(f"Starting submission of {len(commands)} jobs...")

        # Instantiate and use the MultiprocessBulkRunner
        runner = MultiprocessBulkRunner(list(self.handles.values()))
        results = runner.run(commands)

        self.pprint("Submission process complete.\n")
        return results

    def throughput(self, command, count=100):
        """
        A specialized function to test throughput by submitting one command many times.
        """
        print(f"Preparing throughput test for command: {' '.join(command)}")
        commands_list = [command for _ in range(count)]
        return self.submit_jobs(commands_list)

    def throughput(self, command, count=100):
        """
        A specialized function to test throughput by submitting one command many times.
        """
        print(f"Preparing throughput test for command: {' '.join(command)}")
        commands_list = [command for _ in range(count)]
        return self.submit_jobs(commands_list)

    def throughput(self, command, count=100):
        """
        A specialized function to test throughput by submitting one command many times.
        """
        print(f"Preparing throughput test for command: {' '.join(command)}")
        commands_list = [command for _ in range(count)]
        return self.submit_jobs(commands_list)


def get_jobspec_from_dry_run(command, resources):
    """
    Use flux to generate a json jobspec with flux submit --dryrun
    """
    cores = resources.get("cores")
    nodes = resources.get("nodes")
    tasks = resources.get("count")

    cmd = ["flux", "submit", "--dry-run"]
    if nodes is not None:
        cmd += ["-N", str(nodes)]
    if tasks is not None:
        cmd += ["-n", str(tasks)]
    if cores is not None:
        cmd += ["--cores", str(cores)]
    cmd += command
    process = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(process.stdout)


class MultiprocessBulkRunner:
    """
    Uses a multiprocessing pool to perform parallel bulk submissions.

    Each worker process is assigned a chunk of commands and a single handle (URI).
    It writes its commands to a temporary file and executes `flux bulksubmit`
    via a subprocess, achieving high parallelism and throughput.
    """

    def __init__(self, handles):
        if not handles:
            raise ValueError("Runner requires at least one handle.")
        self.handles = handles
        self.jobs_to_complete = 0
        self.completion_event = None
        self.jobs = {}

    @staticmethod
    def _chunkify(data, num_chunks):
        if not data or num_chunks <= 0:
            return []
        chunks = [[] for _ in range(num_chunks)]
        for i, item in enumerate(data):
            chunks[i % num_chunks].append(item)
        return chunks

    @staticmethod
    def _cffi_submit_worker(command_chunk, uri_string):
        """
        A pickle-safe worker that connects its own handle and uses a tight
        loop of `submit_async` and `get_id` for submission.
        """
        pid = os.getpid()
        job_ids = []
        handle = None
        # 1. Create a fresh handle inside the worker process
        handle = flux.Flux(uri_string)

        start_time = time.monotonic()

        # 2. Loop and submit as fast as possible in memory
        for command in command_chunk:
            spec = flux.job.JobspecV1.from_command(command)
            future = flux.job.submit_async(handle, spec.dumps(), waitable=True)
            # get_id() blocks briefly but is necessary to confirm submission
            job_ids.append(future.get_id())

        end_time = time.monotonic()
        return (len(command_chunk), start_time, end_time, job_ids, uri_string)

    @staticmethod
    def _async_cffi_worker(command_chunk, uri_string):
        """
        A pickle-safe worker that uses a pipelined CFFI approach for submission.
        """
        pid = os.getpid()
        handle = None
        handle = flux.Flux(uri_string)
        futures = []
        job_ids = []
        start_time = time.monotonic()

        # Submit all jobs without waiting for individual ACKs.
        # This blasts the broker with requests, just like bulksubmit.
        for command in command_chunk:
            spec = flux.job.JobspecV1.from_command(command)
            # submit_async is non-blocking, it returns a future immediately
            futures.append(flux.job.submit_async(handle, spec.dumps(), waitable=True))

        # Now, loop through the futures and get the IDs. The requests are
        # already "in-flight" or queued on the broker side.
        for f in futures:
            job_ids.append(f.get_id())

        end_time = time.monotonic()
        duration = end_time - start_time
        print(
            f"  - True Async CFFI Worker [{pid}] submitted {len(job_ids)} jobs in {duration:.2f}s."
        )
        return (len(command_chunk), start_time, end_time, job_ids, uri_string)

    @staticmethod
    def _bulk_submit_worker(command_chunk, uri_string):
        """
        Worker that uses `flux proxy` to correctly target a leaf broker and
        pipes commands to `flux bulksubmit` via stdin for maximum performance.
        """
        pid = os.getpid()

        input_string = "\n".join(shlex.join(command) for command in command_chunk)

        with tempfile.TemporaryFile(mode="w+") as stdout_pipe, tempfile.TemporaryFile(
            mode="w+"
        ) as stderr_pipe:
            cmd = ["flux", "proxy", uri_string, "flux", "bulksubmit"]

            start_time = time.monotonic()
            subprocess.run(
                cmd,
                input=input_string,
                stdout=stdout_pipe,
                stderr=stderr_pipe,
                text=True,
                check=True,
            )
            end_time = time.monotonic()

            stdout_pipe.seek(0)
            job_ids = [line.strip() for line in stdout_pipe if line.strip()]

            duration = end_time - start_time
            print(
                f"  - Worker [{pid}] submitted {len(job_ids)} jobs in {duration:.2f}s to {uri_string}."
            )

            # length of command chunk is job count
            return (len(command_chunk), start_time, end_time, job_ids, uri_string)

    def run(self, commands):
        """
        Distributes commands to a multiprocessing pool for parallel bulk submission.
        """
        if not commands:
            print("No commands to submit.")
            return {"total_submitted": 0}

        num_handles = len(self.handles)
        print(
            f"\n=> Preparing parallel bulk submission for {len(commands)} jobs across {num_handles} handles..."
        )

        # 1. Chunk commands and pair with URIs for the workers.
        command_chunks = self._chunkify(commands, num_handles)
        handle_uris = [h.uri for h in self.handles]
        tasks = [(c, u) for c, u in zip(command_chunks, handle_uris) if c]

        if not tasks:
            print("No tasks could be created for submission.")
            return {"total_submitted": 0}

        n_workers = min(os.cpu_count(), len(tasks))
        print(f"=> Creating a pool of {n_workers} worker processes...")
        results = []

        # 2. Run workers to perform parallel bulk submissions.
        with multiprocessing.Pool(processes=n_workers) as pool:
            worker_args = [(chunk, uri) for chunk, uri in tasks]

            # starmap blocks until all workers are complete.
            results += pool.starmap(self._async_cffi_worker, worker_args)
            print(f"=> All worker processes finished.")

        total_submitted = sum([x[0] for x in results])

        print(f"\n=> Summary:")
        print(f"  - Approximate submissions per worker: {results[0][0]}")
        print(f"  - Total jobs submitted: {total_submitted} / {len(commands)}")

        # Measure Time to Final Completion
        print(f"\nWaiting for {total_submitted} jobs to complete...")
        self.jobs.clear()
        self.jobs_to_complete = total_submitted
        self.completion_event = threading.Event()

        for task_result in results:
            job_ids = task_result[3]
            uri_string = task_result[4]
            handle = flux.Flux(uri_string)

            for i, jobid in enumerate(job_ids):
                jobid = flux.job.JobID(jobid)
                # Create a future that resolves when the job is clean.
                fut = flux.job.wait_async(handle, jobid)
                # When it resolves, call our callback, passing it the jobid AND the handle
                # so it can fetch the final job info.
                fut.then(self._job_complete_cb, jobid, handle)
                # self.job_complete_cb(jobid, handle)
                # print(f'{i} of {len(job_ids)}', end="\r")
            handle.reactor_run()

        self.completion_event.wait()
        print("=> All jobs complete. Finalizing results...")

        # Now, build the final data structures from the collected info
        start_times = []
        end_times = []

        # The job_info_dict is now fully populated...
        for info in self.jobs.values():
            start_times.append(info["t_submit"])
            end_times.append(info["t_cleanup"])

        # Reconstruct the exact return signature you had
        return {
            "total_submitted": total_submitted,
            "results_per_worker": results,
            "start_times": start_times,
            "end_times": end_times,
            "submit_times": [res[1] for res in results],
            "submit_end_times": [res[2] for res in results],
        }

    def job_complete_cb(self, jobid, handle):
        """
        Callback executed when a job is complete. It fetches the job's
        final info and stores it in the shared dictionary.
        """
        try:
            self.jobs[jobid] = flux.job.get_job(handle, int(jobid))
        except Exception as e:
            print(f"There was an issue with job completion callback: {e}")
        finally:
            self.jobs_to_complete -= 1
            if self.jobs_to_complete <= 0:
                self.completion_event.set()

    def _job_complete_cb(self, future, jobid, handle):
        """
        Callback executed when a job is complete. It fetches the job's
        final info and stores it in the shared dictionary.
        """
        try:
            self.jobs[jobid] = flux.job.get_job(handle, int(jobid))
        except Exception as e:
            print(f"There was an issue with job completion callback: {e}")
        finally:
            self.jobs_to_complete -= 1
            if self.jobs_to_complete <= 0:
                self.completion_event.set()
