import jsonschema

import jobspec.schema as schema

from .base import ResourceBase
from .resources import find_resources


class Jobspec(ResourceBase):
    def __init__(self, filename, validate=True, schema=schema.jobspec_nextgen):
        """
        Load in and validate a Jobspec
        """
        # This should typically be loaded from jobspec.core
        if not hasattr(self, "schema") or not self.schema:
            self.schema = schema
        self.filename = filename
        self.data = None
        self.load(filename)
        if validate:
            self.validate()

    def validate(self):
        """
        Validate the jsonschema
        """
        jsonschema.validate(self.data, self.schema)

        # Require at least one of command or steps
        for task in self.data.get("tasks", []):
            if "command" not in task and "steps" not in task:
                raise ValueError("Jobspec is not valid, each task must have a command or steps")


class Resources(ResourceBase):
    def __init__(self, data, slot=None):
        """
        Interact with loaded resources.
        """
        self.data = data
        self.slot = slot

    def flatten_slot(self, slot=None):
        """
        Find the task slot, flatten it, and return
        """
        slot = slot or self.slot

        # Traverse each section. There is usually only one I guess
        for resource in self.data or []:
            flat = {}
            if find_resources(flat, resource, slot):
                break

        return flat


class Attributes(ResourceBase):
    """
    Job attributes, not formally defined yet.
    """

    pass


class Requires(ResourceBase):
    """
    Requires are nested groups
    """

    def update(self, requires):
        """
        Update specific groups. This is assumed
        at the level of the attribute, not the group.
        E.g., this at the global level:

        requires:
          io:
            fieldA: valueA
            fieldB: valueB

        Updated with this:
        requires:
          io:
            fieldB: valueC

        Results in this:
        requires:
          io:
            fieldA: valueA
            fieldB: valueC
        """
        if not requires:
            return
        for group, fields in requires.items():
            # If we don't have the group at all, we can add all and continue!
            if group not in self.data:
                self.data[group] = fields
                continue

            # If we have the group, update on the level of fields
            self.data[group].update(fields)
