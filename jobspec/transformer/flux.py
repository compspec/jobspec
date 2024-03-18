import argparse
import copy
import json
import logging
import os
import shlex
import subprocess
import time

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
        return jobid.f58plain


# A transformer can register shared steps, or custom steps
Transformer.register_step(steps.WriterStep)
Transformer.register_step(submit)
