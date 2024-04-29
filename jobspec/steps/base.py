class StepBase:
    """
    A base step describes the design of a step.
    """

    required = []

    def __init__(self, js, **kwargs):
        """
        A step takes a task definition and custom options

        Note that we aren't using options now, but could be.
        """
        self.jobspec = js
        if not hasattr(self, "name"):
            raise ValueError(f"Step {self} is missing a name")

        # Each step can take custom options (the keyword arguments)
        self.options = kwargs

        # Shared validation
        self._validate()

        # Custom validation and setup
        self.validate()
        self.setup(**kwargs)

    def _validate(self):
        """
        Shared validation functions
        """
        # Required fields are all... required.
        for field in self.required:
            if field not in self.options:
                raise ValueError(f"Step {self.name} is missing field {field}")
            if self.options[field] is None:
                raise ValueError(f"Step {self.name} has undefined field {field}")

    def validate(self):
        """
        Validate the step
        """
        pass

    def setup(self, **kwargs):
        """
        Custom setup

        Akin to overriding init, but easier to write.
        """
        pass

    def run(self, *args, **kwargs):
        """
        Run a step.

        This is the argument structure that should be used.
        """
        raise NotImplementedError
