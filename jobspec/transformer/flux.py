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
from jobspec.runner import TransformerBase
from jobspec.steps.base import StepBase

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

        filename = self.options.get("filename")
        cmd = ["flux", "batch", "--cwd", stage]
        if nodes:
            cmd += ["-N", str(nodes)]
        if tasks:
            cmd += ["-n", str(tasks)]
        cmd.append(filename)
        with utils.workdir(stage):
            res = utils.run_command(cmd, check_output=True)
        jobid = res["message"].strip()
        return jobid


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
        Run the submit step.

        The python bindings are giving me weird errors.
        """
        slot = self.flatten_slot()
        nodes = slot.get("node")
        tasks = slot.get("core")

        filename = self.options.get("filename")
        cmd = ["flux", "submit", "--cwd", stage]

        # TODO: add timeout from system section
        watch = self.options.get("watch") is True
        if watch:
            cmd.append("--watch")
        if nodes:
            cmd += ["-N", str(nodes)]
        if tasks:
            cmd += ["-n", str(tasks)]
        cmd += ["/bin/bash", filename]
        print("\n" + " ".join(cmd))

        with utils.workdir(stage):
            res = utils.run_command(cmd, check_output=True, stream=watch)

        if not watch:
            jobid = res["message"].strip()
            return jobid


# A transformer can register shared steps, or custom steps
Transformer.register_step(steps.WriterStep)
Transformer.register_step(batch)
Transformer.register_step(submit)
Transformer.register_step(stage)
