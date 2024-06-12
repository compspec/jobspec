import copy
import json
import os
import uuid

import jobspec.utils as utils
from jobspec.steps.base import StepBase
from jobspec.transformer.result import Result

script_prefix = ["#!/bin/bash"]

# Custom Flux steps - just write and register!


class stage(StepBase):
    """
    A copy step uses flux filemap to stage across nodes

    This assumes we don't have a shared filesystem. It is skipped if we do.
    """

    name = "stage"

    def run(self, stage, *args, **kwargs):
        """
        Run the stage step = fall back to filename for now
        """
        # If we have a sharedfs, return early, the write will have written it there
        sharedfs = self.options.get("settings", {}).get("sharedfs") is True
        if sharedfs:
            return

        # Sanity check staging directory exists across nodes
        cmd = ["flux", "exec", "-r", "all", "-x", "0", "mkdir", "-p", stage]
        utils.run_command(cmd, check_output=True)

        name = str(uuid.uuid4())
        filename = self.options["filename"]
        cmd = ["flux", "filemap", "map", "--tags", name, "--directory", stage, filename]
        utils.run_command(cmd, check_output=True)

        # Assume we send to all ranks besides where we've already written it
        # This will likely fail if the filesystem is shared
        cmd = [
            "flux",
            "exec",
            "--dir",
            stage,
            "-r",
            "all",
            "-x",
            "0",
            "flux",
            "filemap",
            "get",
            "--tags",
            name,
        ]
        utils.run_command(cmd, check_output=False)

        # Unmap to clear the memory map
        cmd = ["flux", "filemap", "unmap", "--tags", name]
        utils.run_command(cmd, check_output=True)


class JobBase(StepBase):
    """
    base with shared logic for submit or batch
    """

    def cleanup(self, filename):
        """
        Cleanup a filename if it still exists
        """
        if os.path.exists(filename):
            os.remove(filename)

    def prepare(self, command=None, waitable=False):
        """
        Return the command, without flux submit|batch
        """
        cmd = []

        # We can get the resources from options
        resources = self.options.get("resources")

        # These aren't used yet - they need to go into flux
        attributes = self.options.get("attributes") or {}
        task = self.options.get("task") or {}

        # This flattens to be what we ask flux for
        slot = resources.flatten_slot()
        nodes = slot.get("node")
        tasks = slot.get("core")
        gpus = slot.get("gpu")

        # Get name, jobspec, depends, etc
        name = self.options.get("name")
        duration = attributes.get("duration")
        cwd = attributes.get("cwd")
        watch = attributes.get("watch")

        # Note that you need to install our frobnicator plugin
        # for this to work. See the examples/depends_on directory
        for depends_on in task.get("depends_on") or []:
            cmd += [f"--setattr=dependency.name={depends_on}"]

        if cwd is not None:
            cmd += ["--cwd", cwd]
        if name is not None:
            cmd += ["--job-name", name]
        if duration is not None:
            cmd += ["--time-limit", str(duration)]
        if watch is True:
            cmd += ["--watch"]

        if nodes:
            cmd += ["-N", str(nodes)]
        if tasks:
            cmd += ["-n", str(tasks)]
        if gpus:
            cmd += ["-g", str(gpus)]

        # Replicas we do with cc
        replicas = task.get("replicas")
        if replicas:
            replicas -= 1
            cmd += ["--cc", f"0-{replicas}"]

        # Are we adding a waitable flag? This will prevent the batch
        # from exiting
        if waitable:
            cmd += ["--flags=waitable"]

        # Right now assume command is required
        if not command:
            command = task["command"]
        if isinstance(command, str):
            command = [command]
        cmd += command
        return cmd


class batch(JobBase):
    """
    flux batch is the flux implementation of a group.

    It starts an allocation to run commands and launch
    other tasks or groups.
    """

    name = "batch"

    def setup(self, **kwargs):
        """
        Custom setup

        A batch can hold one or more task steps, and these need to be written into
        a custom script (and not run as tasks)
        """
        self.tasks = []

    def write_tasks_script(self):
        """
        Generate the batch script.
        """
        data = copy.deepcopy(script_prefix)
        for task in self.tasks:
            if task.name == "batch":
                cmd, _ = task.generate_command(waitable=True)
                data.append(" ".join(cmd))
                # This is the jobspec
                data.append(f"# rm -rf {cmd[-1]}")
            else:
                data.append(" ".join(task.generate_command(waitable=True)))

        # Ensure all jobs are waited on
        data.append("flux job wait --all")
        script = "\n".join(data)
        return {"mode": 33216, "data": script, "encoding": "utf-8"}

    def generate_command(self, waitable=False):
        """
        Convenience function to generate the command.

        This is also intended for flux batch to use,
        and we expect the last argument to be the temporary file
        that needs to be cleaned up
        """
        # With batch, we are going to cheat and run a flux job submit --dry-run
        # with the command that would normally be derived for flux batch.
        command = ["flux", "broker", "{{tmpdir}}/batch-script"]
        cmd = self.prepare(command)

        # This returns a partial jobspec for the work that is needed...
        cmd = ["flux", "submit", "--dry-run"] + cmd
        res = utils.run_command(cmd, check_output=True)

        if res["return_code"] != 0:
            raise ValueError(f"Issue generating flux jobspec: {res['message']}")

        # Then we will add our (not written) batch script to the files section
        # Load the jobspec and add our "files" section to it with tasks (flux submit, etc)
        js = json.loads(res["message"])

        # Be careful about updating files - not sure if there are cases
        # when there might be other content there.
        files = js["attributes"]["system"].get("files") or {}
        files["batch-script"] = self.write_tasks_script()
        js["attributes"]["system"]["files"] = files

        # Write the jobspec to a temporary file, target for cleanup
        tmpfile = utils.get_tmpfile(prefix="jobspec-")
        utils.write_file(json.dumps(js), tmpfile)

        # Prepare a result, we can show the batch script if debug is on
        result = Result()
        for line in files["batch-script"]["data"].split("\n"):
            result.add_debug_line(line)

        # and submit with flux job submit <jobspec>
        # We can't really watch here, or do anything with attributes yet
        cmd = ["flux", "job", "submit"]
        if waitable:
            cmd += ["--flags=waitable"]
        cmd.append(tmpfile)
        return cmd, result

    def run(self, *args, **kwargs):
        """
        Run the batch step
        """
        cmd, result = self.generate_command()
        res = utils.run_command(cmd, check_output=True)

        # The temporary file to cleanup is the last in the list
        tmpfile = cmd[-1]

        # Prepare a result to return
        result.out = res["message"].strip()
        result.add_debug_line(" ".join(cmd))

        # Cleanup the files
        self.cleanup(tmpfile)
        return result


class submit(JobBase):
    name = "submit"

    def generate_command(self, waitable=False):
        """
        Convenience function to generate the command.

        This is intended for flux batch to use
        """
        cmd = self.prepare(waitable=waitable)
        return ["flux", "submit"] + cmd

    def run(self, *args, **kwargs):
        """
        Run the submit step.

        The python bindings are giving me weird errors.
        """
        cmd = self.generate_command()

        # Are we watching?
        attributes = self.options.get("attributes") or {}
        watch = attributes.get("watch")
        res = utils.run_command(cmd, check_output=True, stream=watch)

        # Prepare a result to return
        result = Result()

        # Return results to print
        if not watch:
            result.out = res["message"].strip()
        result.add_debug_line(" ".join(cmd))
        return result
