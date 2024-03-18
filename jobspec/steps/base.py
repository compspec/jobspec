class StepBase:
    """
    A base step describes the design of a step.
    """

    required = []

    def __init__(self, js, options):
        """
        A step takes a task definition and custom options
        """
        self.jobspec = js
        self.options = options
        if not hasattr(self, "name"):
            raise ValueError(f"Step {self} is missing a name")

        # Shared validation
        self._validate()

        # Custom validation
        self.validate()

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
        pass

    @property
    def scripts(self):
        """
        Return a lookup of scripts

        Many steps will have need for this.
        """
        if hasattr(self, "_scripts") and self._scripts is not None:
            return self._scripts

        # Task scripts must have a name and content
        task = self.jobspec.get("task")
        scripts = {}
        if task:
            for script in task.get("scripts"):
                if "name" not in script:
                    raise ValueError(f"Script {script} is missing a name.")
                if "content" not in script:
                    raise ValueError(f"Script {script} is missing content.")
                scripts[script["name"]] = script
        self._scripts = scripts
        return scripts

    def run(self, stage, *args, **kwargs):
        """
        Run a step.

        This is the argument structure that should be used.
        """
        raise NotImplementedError
