import argparse
import copy
import json
import logging
import os
import shlex
import subprocess
import time
import uuid

import yaml

import jobspec.steps as steps
import jobspec.utils as utils
from jobspec.steps.base import StepBase
from jobspec.transform import TransformerBase

logger = logging.getLogger("jobspec-flux")

# handle for steps to use
handle = None


class Transformer(TransformerBase):
    """
    The flux transformer
    """

    # These metadata fields are required (and checked for)
    name = "flux"
    description = "Flux Framework transformer"

    def __init__(self, *args, **kwargs):
        # Ensure we have a flux handle
        global handle
        import flux

        handle = flux.Flux()
        super().__init__(*args, **kwargs)


# Custom Flux steps - just write and register!


class stage(StepBase):
    """
    A stage step uses flux filemap to stage across nodes
    """

    name = "stage"

    def run(self, stage, *args, **kwargs):
        """
        Run the stage step = fall back to filename for now
        """
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


class batch(StepBase):
    name = "batch"

    def run(self, stage, *args, **kwargs):
        """
        Run the batch step
        """
        slot = self.flatten_slot()
        nodes = slot.get("node")
        tasks = slot.get("core")

        # I'm pretty sure we need one of these
        if not nodes and not tasks:
            raise ValueError("slot is missing node or core, cannot direct to batch.")

        # I don't think batch has python bindings?
        filename = self.options.get("filename")
        cmd = ["flux", "batch"]
        if nodes:
            cmd += ["-N", str(nodes)]
        if tasks:
            cmd += ["-n", str(tasks)]
        cmd.append(filename)

        # Would be nice if this was exposed as "from jobspec"
        # https://github.com/flux-framework/flux-core/blob/master/src/bindings/python/flux/cli/batch.py#L109-L120
        with utils.workdir(stage):
            res = utils.run_command(cmd, check_output=True)

        # 👀️ 👀️ 👀️
        jobid = res["message"].strip()
        wait = self.options.get("wait") is True
        if wait:
            watch_job(handle, jobid)
        return jobid


def watch_job(handle, jobid):
    """
    Shared function to watch a job
    """
    import flux.job

    if isinstance(jobid, str):
        jobid = flux.job.JobID(jobid)

    print()
    watcher = flux.job.watcher.JobWatcher(
        handle,
        progress=False,
        jps=False,  # show throughput with progress
        log_events=False,
        log_status=True,
        labelio=False,
        wait=True,
        watch=True,
    )
    watcher.start()
    watcher.add_jobid(jobid)
    handle.reactor_run()


class submit(StepBase):
    name = "submit"

    def validate(self):
        """
        Validate a submit step.

        This largely is done with the schema.json
        """
        assert "resources" in self.jobspec

    def run(self, stage, *args, **kwargs):
        """
        Run the submit step
        """
        import flux.job

        # Parse jobspec into yaml stream, because it doesn't have support for json stream
        # Also remove "experimental" feature lol
        js = copy.deepcopy(self.jobspec)
        for key in ["scripts", "transform", "resources"]:
            if key in js.get("task"):
                del js["task"][key]

        # Task -> tasks
        if "task" in js:
            task = js.get("task")
            del js["task"]
            js["tasks"] = [task]

        # It requires attributes, even if it's empty...
        if "attributes" not in js:
            js["attributes"] = {"system": {"duration": 3600, "cwd": stage}}

        # Are we watching?
        wait = self.options.get("wait") is True
        flux_jobspec = flux.job.JobspecV1.from_yaml_stream(yaml.dump(js))
        jobid = flux.job.submit(handle, flux_jobspec, waitable=True)

        # 👀️ 👀️ 👀️
        if wait:
            watch_job(handle, jobid)
        return jobid.f58plain


# A transformer can register shared steps, or custom steps
Transformer.register_step(steps.WriterStep)
Transformer.register_step(batch)
Transformer.register_step(submit)
Transformer.register_step(stage)
