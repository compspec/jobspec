import copy
import os
import sys

# This imports the latest version
import jobspec.core as js
import jobspec.defaults as defaults
import jobspec.utils as utils
from jobspec.logger import LogColors


class TransformerBase:
    """
    A Jobspec Transformer can load a Jobspec and transform for a particular environment.
    """

    steps = {}

    def __init__(self, **options):
        """
        Create a new graph backend, accepting any options type.

        Validation of transformers is done by the registry
        """
        # Set options as attributes
        for key, value in options.items():
            setattr(self, key, value)

    @classmethod
    def register_step(cls, step, name=None):
        """
        Register a step class to the transformer
        """
        # Allow registering an empty step if needed
        # An empty step does nothing, an explicit declaration
        # by the transformer developer it's not needed, etc.
        name = name or step.name
        cls.steps[name] = step

    def update_settings(self, settings, typ, step):
        """
        Update settings, either set or unset
        """
        if "key" not in step or "value" not in step:
            return
        if not step["key"]:
            return
        # This is important for typos, etc.
        if step["key"] not in defaults.valid_settings:
            raise ValueError(f"{step['key']} is not a known setting.")
        if typ == "set":
            settings[step["key"]] = step["value"]
        elif typ == "unset" and step["key"] in settings:
            del settings[step["key"]]

    def parse(self, jobspec):
        """
        parse validates transform logic and returns steps.

        We also look for global variables for steps.
        """
        # We will return a listing of steps to complete
        # Each step is provided all settings that are provided
        # before it
        steps = []

        # Each filename directive must have a matching script
        # It could be the case it exists (and we might mark that)
        # but not for the time being
        task = jobspec.jobspec.get("task")

        # Global set settings
        settings = {"sharedfs": defaults.sharedfs}

        # Validate each step
        for i, step in enumerate(task.get("transform")):
            # The step must be known to the transformer
            name = step.get("step")
            if not name:
                raise ValueError(f"Step in index {i} is missing a name")

            # If it's a set or unset, add to settings
            if name == "set" or name == "unset":
                self.update_settings(settings, name, step)
                continue

            if name not in self.steps:
                raise ValueError(f"Step {name} is not known to transformer {self.name}")

            # This ensures we get the exact state of settings at this level
            step["settings"] = copy.deepcopy(settings)

            # Instantiate the new step (does extra validation), provided entire jobspec
            new_step = self.steps[name](jobspec.jobspec, step)
            steps.append(new_step)
        return steps

    def run(self, filename):
        """
        Run the transformer
        """
        # Load the jobspec
        jobspec = self.load_jobspec(filename)

        # Get validated transformation steps
        steps = self.parse(jobspec)

        # Create a temporary staging directory
        stage = utils.get_tmpdir(prefix="jobspec-")

        # Run each step to submit the job, and that's it.
        for step in steps:
            step_stage = stage or step["settings"].get("stage")
            self.run_step(step, step_stage)

    def run_step(self, step, stage):
        """
        Run a single step. Make it pretty.
        """
        prefix = f"step {step.name}".ljust(15)
        print(f"=> {LogColors.OKCYAN}{prefix}{LogColors.ENDC}", end="")
        try:
            out = (step.run(stage) or "").ljust(25)
            print(f"{LogColors.OKBLUE}{out}{LogColors.ENDC} {LogColors.OKGREEN}OK{LogColors.ENDC}")
        except Exception as e:
            print(f"\n{LogColors.RED}{str(e)}{LogColors.ENDC}")
            sys.exit()

    def load_jobspec(self, filename):
        """
        Load and transform a jobspec.

        This function should be able to load it in some raw format
        and convert into correct directives given the transformer.
        """
        filename = os.path.abspath(filename)
        jobspec = js.Jobspec(filename)
        return jobspec
