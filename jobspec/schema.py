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
        # These are optional global resources
        "requires": {"$ref": "#/definitions/requires"},
        # Resources at the top level are key (identifier) and value (resource) pairs
        "resources": {
            "type": "object",
            "patternProperties": {
                "^([a-z]|[|]|&|[0-9]+)+$": {"$ref": "#/definitions/resources"},
            },
        },
        "attributes": {"$ref": "#/definitions/attributes"},
        # The top level jobspec has groups and tasks
        # Groups are "flux batch"
        "groups": {"type": "array", "items": {"$ref": "#/definitions/group"}},
        # Tasks are one or more named tasks
        # Tasks are "flux submit" on the level they are defined
        "tasks": {"$ref": "#/definitions/tasks"},
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
        "requires": {
            "description": "compatibility requirements",
            "type": "object",
        },
        "resources": {
            "description": "requested resources",
            "oneOf": [
                {"$ref": "#/definitions/node_vertex"},
                {"$ref": "#/definitions/slot_vertex"},
            ],
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
                    "requires": {"$ref": "#/definitions/requires"},
                    # Resources in a task can be traditional OR a string reference
                    "resources": {"type": "string"},
                    "attributes": {"$ref": "#/definitions/attributes"},
                    # A task can reference another group (a flux batch)
                    "group": {"type": "string"},
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
                    "steps": {"$ref": "#definitions/steps"},
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
                # These are task level items that over-ride global
                "requires": {"$ref": "#/definitions/requires"},
                # Resources in a task can be traditional OR a string reference
                "resources": {"type": "string"},
                "attributes": {"$ref": "#/definitions/attributes"},
                "depends_on": {"type": "array", "items": {"type": "string"}},
                # Tasks for the group
                "tasks": {"$ref": "#definitions/tasks"},
            },
            "additionalProperties": False,
        },
        "intranode_resource_vertex": {
            "description": "schema for resource vertices within a node, cannot have child vertices",
            "type": "object",
            "required": ["type", "count"],
            "properties": {
                "type": {"enum": ["core", "gpu"]},
                "count": {"type": "integer", "minimum": 1},
                "unit": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "node_vertex": {
            "description": "schema for the node resource vertex",
            "type": "object",
            "required": ["type", "count"],
            "properties": {
                "type": {"enum": ["node"]},
                "count": {"type": "integer", "minimum": 1},
                "unit": {"type": "string"},
                "schedule": {"type": "boolean"},
                "with": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 1,
                    "items": {
                        "oneOf": [
                            {"$ref": "#/definitions/slot_vertex"},
                            {"$ref": "#/definitions/intranode_resource_vertex"},
                        ]
                    },
                },
            },
            "additionalProperties": False,
        },
        "slot_vertex": {
            "description": "special slot resource type - label assigns to task slot",
            "type": "object",
            "required": ["type", "count", "with", "label"],
            "properties": {
                "type": {"enum": ["slot"]},
                "count": {"type": "integer", "minimum": 1},
                "unit": {"type": "string"},
                "label": {"type": "string"},
                "schedule": {"type": "boolean"},
                "exclusive": {"type": "boolean"},
                "with": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 2,
                    "items": {"oneOf": [{"$ref": "#/definitions/intranode_resource_vertex"}]},
                },
            },
            "additionalProperties": False,
        },
    },
}
