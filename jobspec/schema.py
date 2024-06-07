jobspec_nextgen = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "http://github.com/flux-framework/rfc/tree/master/data/spec_24/schema.json",
    "title": "jobspec-01",
    "description": "JobSpec the Next Generation",
    "type": "object",
    # The only required thing is a version. Tasks and groups can be defined.
    # If neither is, we essentially do nothing.
    "required": ["version"],
    "properties": {
        # Name for the entire jobspec is optional
        "name": {"type": "string"},
        # This is not a flux JobSpec, and we start at v1
        "version": {
            "description": "the jobspec version",
            "type": "integer",
            "enum": [1],
        },
        "requires": {
            "type": "object",
            "patternProperties": {
                "^([a-z]|[|]|&|[0-9]+)+$": {
                    "type": "array",
                    "items": {"type": "object"},
                },
            },
        },
        "resources": {
            "type": "object",
            "patternProperties": {
                "^([a-z]|[|]|&|[0-9]+)+$": {"$ref": "#/definitions/resources"},
            },
        },
        # The top level jobspec has groups and tasks
        # Groups are "flux batch"
        "groups": {"type": "array", "items": {"$ref": "#/definitions/group"}},
        # Tasks are one or more named tasks
        # Tasks are "flux submit" on the level they are defined
        "tasks": {"$ref": "#/definitions/tasks"},
        # Attributes can eventually be given to the jobs
        "attributes": {"$ref": "#/definitions/attributes"},
        "additionalProperties": False,
    },
    "definitions": {
        "attributes": {
            "description": "system, parameter, and user attributes",
            "type": "object",
            "properties": {
                "duration": {"type": "number", "minimum": 0},
                "cwd": {"type": "string"},
                "environment": {"type": "object"},
            },
        },
        "resources": {
            "description": "requested resources",
            "type": "object",
            "required": ["type"],
            "properties": {
                "type": {"type": "string"},
                # Count is only required when below a slot
                "count": {"type": "integer", "minimum": 1},
                "requires": {
                    "type": "array",
                    "items": {"type": "object"},
                },
                "attributes": {"$ref": "#/definitions/attributes"},
                "schedule": {"type": "boolean"},
                "with": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"$ref": "#/definitions/resources"},
                },
            },
        },
        "steps": {
            "type": ["array"],
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "enum": ["stage"],
                    },
                },
                "required": ["name"],
            },
        },
        "tasks": {
            "description": "tasks configuration",
            "type": "array",
            # If no slot is defined, it's implied to be at the top level (the node)
            "items": {
                "type": "object",
                "properties": {
                    # These are task level items that over-ride global
                    # Resources in a task can be traditional OR a string reference
                    "resources": {"type": "string"},
                    # A task can reference another group (a flux batch)
                    "group": {"type": "string"},
                    # If the task is run locally on the level it is currently at.
                    "local": {"type": "boolean"},
                    # Requires is a reference to one or more requirement blocks
                    # For example, users space subsystems
                    "requires": {"type": "string"},
                    # Name only is needed to reference the task elsewhere
                    "name": {"type": "string"},
                    "depends_on": {"type": "array", "items": {"type": "string"}},
                    # How many of this task are to be run?
                    "replicas": {"type": "number", "minimum": 1, "default": 1},
                    # A command can be a string or a list of strings
                    "command": {
                        "type": ["string", "array"],
                        "minItems": 1,
                        "items": {"type": "string"},
                    },
                    # Custom logic for the transformer
                    "steps": {"$ref": "#/definitions/steps"},
                },
            },
        },
        "group": {
            "description": "group of tasks (batch)",
            "type": "object",
            # If no slot is defined, it's implied to be at the top level (the node)
            "properties": {
                # Name only is needed to reference the group elsewhere
                "name": {"type": "string"},
                "resources": {"type": "string"},
                "depends_on": {"type": "array", "items": {"type": "string"}},
                # Tasks for the group
                "tasks": {"$ref": "#/definitions/tasks"},
                "groups": {"type": "array", "items": {"$ref": "#/definitions/group"}},
            },
            "additionalProperties": False,
        },
    },
}
