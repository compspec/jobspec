import os
import sys

# This imports the latest version
import jobspec.core as js
import jobspec.defaults as defaults
import jobspec.logger as logger
from jobspec.logger import LogColors


class TransformerBase:
    """
    A Transformer base is the core of a JobSpec

    It loads a Jobspec and transforms for a particular environment
    (which typically means a workload manager or similar). This is most
    relevant for submit and batch commands, along with custom steps.
    """

    steps = {}

    def __init__(self, **options):
        """
        Create a new transformer backend, accepting any options type.

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
        if "name" not in step or "value" not in step:
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
        parse validates logic and returns a series of steps, which
        will depend on the underlying transformer. It might be:

        - a batch that includes logic to write a script and then run it
        - one or more submit commands
        """
        raise NotImplementedError

    def run(self, filename):
        """
        Run the transformer
        """
        # Load the jobspec
        jobspec = self.load_jobspec(filename)

        # Get validated transformation steps
        # These will depend on the transformer logic
        steps = self.parse(jobspec)

        # Run each step to submit the job, and that's it.
        for step in steps:
            self.run_step(step)

    def run_step(self, step):
        """
        Run a single step. Make it pretty.
        """
        prefix = f"{self.name} {step.name}".ljust(15)
        print(f"=> {LogColors.OKCYAN}{prefix}{LogColors.ENDC}", end="")
        try:
            result = step.run()
            print(
                f"{LogColors.OKBLUE}{result.out}{LogColors.ENDC} {LogColors.OKGREEN}OK{LogColors.ENDC}"
            )
            result.print_extra()
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
        return js.Jobspec(filename)
