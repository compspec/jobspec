import uuid

import jobspec.core as js
import jobspec.utils as utils
from jobspec.runner import TransformerBase
from jobspec.steps.base import StepBase
from jobspec.transformer.result import Result
import jobspec.core.resources as rcore

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
        # Return series of steps
        steps = []

        # Save lookup of named group (batch) steps
        # Some of these will be nested, and some at the top level to submit
        groups = {}

        # Start with global named resources, attributes, and requires
        resources = jobspec.get("resources", {})
        requires = jobspec.get("requires", {})
        tasks = jobspec.get("tasks", [])
        groups = jobspec.get("groups", [])

        # We will return a listing of steps to complete
        # Parse a-la-carte tasks for the top level - flux submit each
        if tasks:
            steps += self.parse_tasks(jobspec, tasks, resources, requires=requires)

        # Now add on groups. Each group can have a-la-carte tasks,
        # and commands to run in the group (script)
        if groups:
            steps += self.parse_groups(jobspec, groups, resources, requires=requires)
        return steps

    def parse_groups(self, jobspec, groups, resources=None, requires=None):
        """
        Parse groups and return a list of steps. If tasks are within a group,
        they are written to the script of the group.

        This might be tricky to figure out for the very nested version.
        """
        # We first need to find

        print("PARSE GROUPS")
        import IPython
        IPython.embed()
        sys.exit()
        resources = resources or {}
        attributes = attributes or {}

        steps = []
        for i, task in enumerate(tasks):
            task_resources = task.get("resources", {})

            # Create a name based on the index or the task name
            name = task.get("name") or f"task-{i}"

            # The slot is optional and drives where the match is targeting
            slot = task.get("slot")

            # If the task has resources, must be:
            #  A named section in the global resources
            #  A subset of parent resources
            task_resources = js.Resources(
                rcore.parse_resource_subset(resources, task_resources), slot=slot
            )

            # Derive and update task attributes, if provided
            task_attributes = js.Attributes(attributes)
            task_attributes.update(task.get("attributes"))

            # Same for requires. This might eventually include retrieval of
            # artifact metadata first.
            task_requires = js.Requires(attributes)
            task_requires.update(task.get("requires"))

            new_step = self.steps["submit"](
                jobspec,
                name=name,
                resources=task_resources,
                attributes=task_attributes,
                requires=task_requires,
                task=task,
            )
            steps.append(new_step)

        return steps

    
    def parse_tasks(self, jobspec, tasks, resources=None, attributes=None, requires=None):
        """
        Parse a jobspec (or group) tasks and return a list of steps.

        If the task is defined in a group, the attributes provided will be inherited 
        from the group. Otherwise they will likely be empty.
        """
        resources = resources or {}
        attributes = attributes or {}
        requires = requires or {}

        steps = []
        for i, task in enumerate(tasks):
            task_resources = task.get("resources", {})

            # Create a name based on the index or the task name
            name = task.get("name") or f"task-{i}"

            # The slot is optional and drives where the match is targeting
            slot = task.get("slot")

            # If the task has resources, must be:
            #  A named section in the global resources
            #  A subset of parent resources
            task_resources = js.Resources(
                rcore.parse_resource_subset(resources, task_resources), slot=slot
            )

            # Derive and update task attributes, if provided
            task_attributes = js.Attributes(attributes)
            task_attributes.update(task.get("attributes"))

            # Same for requires. This might eventually include retrieval of
            # artifact metadata first.
            task_requires = js.Requires(requires)
            task_requires.update(task.get("requires"))

            new_step = self.steps["submit"](
                jobspec,
                name=name,
                resources=task_resources,
                attributes=task_attributes,
                requires=task_requires,
                task=task,
            )
            steps.append(new_step)

        return steps


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


class JobBase(StepBase):
    """
    base with shared logic for submit or batch
    """

    def prepare(self):
        """
        Return the command, without flux submit|batch
        """
        cmd = []

        # We can get the resources from options
        resources = self.options.get("resources")

        # These aren't used yet - they need to go into flux
        attributes = self.options.get("attributes") or {}
        task = self.options.get("task") or {}

        # This flattens to be what we ask flux for
        slot = resources.flatten_slot()
        nodes = slot.get("node")
        tasks = slot.get("core")

        # Get name, jobspec, depends, etc
        name = self.options.get("name")
        duration = attributes.get("duration")
        cwd = attributes.get("cwd")
        watch = attributes.get("watch")

        # We can't support this yet because it needs the jobid
        # That design to require to get it seems fragile
        # for depends_on in task.get("depends_on") or []:
        #    cmd += [f"--dependency={depends_on}"]

        if cwd is not None:
            cmd += ["--cwd", cwd]
        if name is not None:
            cmd += ["--job-name", name]
        if duration is not None:
            cmd += ["--time-limit", str(duration)]
        if watch is True:
            cmd += ["--watch"]

        if nodes:
            cmd += ["-N", str(nodes)]
        if tasks:
            cmd += ["-n", str(tasks)]

        # Right now assume command is required
        command = task["command"]
        if isinstance(command, str):
            command = [command]
        cmd += command
        return cmd


class batch(JobBase):
    name = "batch"

    def run(self, *args, **kwargs):
        """
        Run the batch step
        """
        cmd = self.prepare()
        cmd = ["flux", "batch"] + cmd

        # Are we watching?
        attributes = self.options.get("attributes") or {}
        watch = attributes.get("watch")
        res = utils.run_command(cmd, check_output=True, stream=watch)

        # Prepare a result to return
        result = Result()

        # Are we watching?
        attributes = self.options.get("attributes") or {}
        watch = attributes.get("watch")

        # Return results to print
        if not watch:
            result.out = res["message"].strip()
        result.add_debug_line(" ".join(cmd))
        return result


class submit(JobBase):
    name = "submit"

    def run(self, *args, **kwargs):
        """
        Run the submit step.

        The python bindings are giving me weird errors.
        """
        cmd = self.prepare()
        cmd = ["flux", "submit"] + cmd

        # Are we watching?
        attributes = self.options.get("attributes") or {}
        watch = attributes.get("watch")
        res = utils.run_command(cmd, check_output=True, stream=watch)

        # Prepare a result to return
        result = Result()

        # Return results to print
        if not watch:
            result.out = res["message"].strip()
        result.add_debug_line(" ".join(cmd))
        return result


# A transformer can register shared steps, or custom steps
Transformer.register_step(batch)
Transformer.register_step(submit)
Transformer.register_step(stage)