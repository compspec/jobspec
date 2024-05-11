import copy

import jsonschema

import jobspec.schema as schema
from jobspec.logger.generate import generate_name

from .base import ResourceBase
from .resources import find_resources, to_jobspec


class Jobspec(ResourceBase):
    def __init__(self, filename, validate=True, name=None, schema=schema.jobspec_nextgen):
        """
        Load in and validate a Jobspec
        """
        self.name = name or generate_name()

        # This should typically be loaded from jobspec.core
        if not hasattr(self, "schema") or not self.schema:
            self.schema = schema
        self.data = None
        self.load(filename)
        if validate:
            self.validate()

    def validate(self):
        """
        Validate the jsonschema
        """
        jsonschema.validate(self.data, self.schema)

        # Require at least one of command or steps, unless it is a group
        for task in self.data.get("tasks", []):
            if "group" not in task and ("command" not in task and "steps" not in task):
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
        flat = {}
        find_resources(flat, self.data, slot)
        return flat

    def to_jobspec(self, slot_name):
        """
        Turn the resource into a flux jobspec

        Note this is not currently used - it was too error prone
        """
        slot = self.slot or {}
        label = slot_name or (slot.get("label") or "default")

        # Hold onto the original data so it is not mangled
        js = copy.deepcopy(self.data)

        # Traverse each section and convert to flux jobspec
        has_slot = to_jobspec(js, slot_name=label)

        # If we don't have a slot, we have to make a fake one at the top
        if not has_slot:
            js = {"type": "slot", "count": 1, "label": label, "with": [js]}
        return js


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
        return self
