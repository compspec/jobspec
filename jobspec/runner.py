# This imports the latest version
import jobspec.core as js
import jobspec.steps.runner as step_runner


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

    def parse(self, jobspec):
        """
        parse validates logic and returns a series of steps, which
        will depend on the underlying transformer. It might be:

        - a batch that includes logic to write a script and then run it
        - one or more submit commands
        """
        raise NotImplementedError

    def announce(self):
        pass

    def flatten(self, filename):
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
        self.announce()

        # Run each step to submit the job, and that's it.
        for step in steps:
            step_runner.run(self.name, step)

    def load_jobspec(self, filename):
        """
        Load and transform a jobspec.

        This function should be able to load it in some raw format
        and convert into correct directives given the transformer.
        """
        return js.Jobspec(filename)
