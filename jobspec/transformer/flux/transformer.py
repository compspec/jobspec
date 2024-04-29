import uuid

import jobspec.core as js
import jobspec.core.resources as rcore
from jobspec.runner import TransformerBase

from .steps import batch, stage, submit
from .workload import FluxWorkload

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

    def parse(self, jobspec):
        """
        Parse the jobspec into tasks for flux.
        """
        # The transformer needs to share state between tasks and groups, so we create
        # a shared class to do that. A "flux workload" is some number of tasks / batches
        # It replaces the step abstractions to be run. Anoher workload manager that does
        # not have the tight dependencies would not need to do this.
        workload = FluxWorkload(jobspec)
        workload.parse()

        # Return the workload to run
        return [workload]


# A transformer can register shared steps, or custom steps
Transformer.register_step(batch)
Transformer.register_step(submit)
Transformer.register_step(stage)
