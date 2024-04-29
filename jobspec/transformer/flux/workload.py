import jobspec.core as js
import jobspec.core.resources as rcore
import jobspec.steps.runner as step_runner
from jobspec.transformer.result import Result

from .steps import batch, submit


class FluxWorkload:
    """
    The flux workload (batch and submit) holder
    """

    name = "workload"

    def __init__(self, jobspec):
        """
        Add the jobspec and set globals (resources, tasks, requires)
        """
        self.js = jobspec
        self.group_lookup = {}

        # Top level, a-la-carte tasks (steps)
        # TODO - we might need to decide on order for top level tasks vs. groups
        self.tasks = []

    @property
    def resources(self):
        """
        This returns a global resource lookup
        """
        return self.js.get("resources", {})

    @property
    def requires(self):
        return self.js.get("requires", {})

    def run(self, *args, **kwargs):
        """
        Run the steps of the workload, some number of submit/batch.
        """
        print()
        # This will be a combination of submit and batch
        for step in self.tasks:
            step_runner.run("flux", step)

    def parse(self):
        """
        Parse the jobspec into tasks for flux.
        """
        # Parse top level groups into a lookup. Those that don't have a name
        # are given a name based on order, and assumed not to be linked to anything
        for i, group in enumerate(self.js.get("groups") or []):
            name = group.get("name") or f"batch-{i}"
            self.group_lookup[name] = group

        # We will return a listing of steps to complete - flux submit each
        # A group referenced within a task group is parsed there
        tasks = self.js.get("tasks") or []
        if tasks:
            self.tasks = self.parse_tasks(tasks, self.resources, requires=self.requires)

        # Now parse remaining groups "a la carte" that aren't linked to top level tasks
        for name, group in self.group_lookup.items():
            self.tasks.prepend(
                self.parse_group(group, name, self.resources, requires=self.requires)
            )

    def parse_group(self, group, name, resources=None, requires=None, attributes=None):
        """
        Parse a group and return a step. If tasks are within a group,
        they are written to the script of the group.

        This might be tricky to figure out for the very nested version.
        """
        resources = resources or {}
        requires = requires or {}
        attributes = attributes or {}

        group_resources = group.get("resources", {})
        group_attributes = group.get("attributes", {})

        # Group requires gets updated from globa (and passed to task)
        group_requires = js.Requires(requires)
        group_requires.update(group.get("requires"))

        # Group resources don't have a slot
        group_resources = js.Resources(rcore.parse_resource_subset(resources, group_resources))

        # Parse the task steps for the group
        tasks = group.get("tasks") or []
        steps = []
        if tasks:
            name_prefix = f"{name}-"
            steps = self.parse_tasks(
                tasks,
                resources=group_resources,
                requires=group_requires.data,
                attributes=group_attributes,
                name_prefix=name_prefix,
            )

        # Prepare a batch (group) step
        new_step = batch(
            self.js,
            name=name,
            resources=group_resources,
            attributes=group_attributes,
            requires=group_requires,
            tasks=tasks,
        )
        new_step.tasks = steps
        return new_step

    def parse_task(self, task, name, resources=None, requires=None, attributes=None):
        """
        Parse a task and return a step.
        """
        task_resources = task.get("resources", {})

        # The slot is optional and drives where the match is targeting
        slot = task.get("slot")

        # If the task has resources, must be:
        #  A named section in the global resources
        #  A subset of parent resources
        task_resources = js.Resources(
            rcore.parse_resource_subset(resources, task_resources), slot=slot
        )

        # Derive and update task attributes, if provided
        task_attributes = js.Attributes(attributes).update(task.get("attributes"))

        # Same for requires. This might eventually include retrieval of
        # artifact metadata first.
        task_requires = js.Requires(requires).update(task.get("requires"))

        # Prepare a submit step
        return submit(
            self.js,
            name=name,
            resources=task_resources,
            attributes=task_attributes,
            requires=task_requires,
            task=task,
        )

    def parse_tasks(self, tasks, resources=None, attributes=None, requires=None, name_prefix=None):
        """
        Parse a jobspec (or group) tasks and return a list of steps.

        If the task is defined in a group, the attributes provided will be inherited
        from the group. Otherwise they will likely be empty.
        """
        # A name prefix helps with defaults to scope to a group
        name_prefix = name_prefix or ""
        resources = resources or {}
        attributes = attributes or {}
        requires = requires or {}

        steps = []
        for i, task in enumerate(tasks):
            # Create a name based on the index or the task name
            name = task.get("name") or f"task-{i}"

            # Case 1: We found a group! Parse here and add to steps
            group_name = task.get("group")
            if group_name is not None:
                group = self.group_lookup.get(group_name)
                if not group:
                    raise ValueError(
                        f"Task {name} is looking for group {group_name} that is not defined."
                    )

                # We assume a group is used once
                del self.group_lookup[group_name]
                new_step = self.parse_group(
                    group, group_name, resources, requires=requires, attributes=attributes
                )

            # Case 2: we have a regular task to flux submit
            else:
                new_step = self.parse_task(
                    task, name, resources, requires=requires, attributes=attributes
                )

            steps.append(new_step)

        return steps
