import itertools
import json
import os
import subprocess
import sys
import tempfile
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
        time.sleep(5)
        for name, uri in self.uris.items():
            self.handles[name] = flux.Flux(uri)
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
        Submits a list of jobs asynchronously across all leaf brokers.
        """
        # Create a JobspecV1 object for each unique command
        jobspecs = [flux.job.JobspecV1.from_command(cmd) for cmd in commands]
        self.pprint(f"Submitting {len(jobspecs)} unique jobs across {len(self.handles)} workers...")
        runner = AsyncJobRunner(list(self.handles.values()))
        return runner.run(jobspecs)

    def throughput(self, command, count=100):
        """
        A specialized function to test throughput by submitting one command many times.
        """
        print(f"Preparing throughput test for command: {' '.join(command)}")
        commands_list = [command for _ in range(count)]
        return self.submit_jobs(commands_list)


class AsyncJobRunner:
    """
    Manage asynchronous bulk submission of a list of jobspecs.

    I based this on src/tests/throughput.py from Flux. Note
    that likely in the future when a handle has a unique shape
    (that we want to understand to submit to) we will store them
    as a lookup, with a hash for the shape. For now, list!
    """

    def __init__(self, handles):
        self.handles = handles
        self.jobs = {}

    def event_cb(self, future, jobid):
        """Callback for job events (start, finish, clean, etc.)."""
        event = future.get_event()
        if event:
            self.jobs[jobid][event.name] = event

    def submit_cb(self, future, handle):
        """
        First callback after submit_async. Its only job is to get the
        job ID from the future and call the next handler. This correctly
        matches the C function signature that .then() expects.
        """
        try:
            # future.handle contains the specific handle used for this submission
            self.handle_submit(future.get_id(), handle)
        except Exception as exc:
            print(f"Submission failed: {exc}", file=sys.stderr)

    def handle_submit(self, jobid, handle):
        """
        Second part of the submission chain: sets up the event watcher.
        """
        self.jobs[jobid] = {"t_submit": time.time()}
        fut = flux.job.event_watch_async(handle, jobid)
        fut.then(self.event_cb, jobid)

    def run(self, jobspecs):
        """
        Run one or more jobspecs, cycling through handles (Flux URI)
        """
        handle_cycler = itertools.cycle(self.handles)

        for spec in jobspecs:
            handle = next(handle_cycler)
            spec_string = spec.dumps()
            flux.job.submit_async(handle, spec_string).then(self.submit_cb, handle)

        if self.handles:
            self.handles[0].reactor_run()
        return self.jobs


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
