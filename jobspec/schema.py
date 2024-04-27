# Note that this has experimental features added, they are flagged
jobspec_nextgen = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "http://github.com/flux-framework/rfc/tree/master/data/spec_24/schema.json",
    "title": "jobspec-01",
    "description": "JobSpec the Next Generation",
    "type": "object",
    "required": ["version", "tasks"],
    "properties": {
        # This is not a flux JobSpec, and we start at v1
        "version": {
            "description": "the jobspec version",
            "type": "integer",
            "enum": [1],
        },
        # These are optional global resources
        "requires": {"$ref": "#/definitions/requires"},
        "resources": {"$ref": "#/definitions/resources"},
        "attributes": {"$ref": "#/definitions/attributes"},
        # Tasks are one or more named tasks
        "tasks": {
            "description": "tasks configuration",
            "type": "array",
            # If no slot is defined, it's implied to be at the top level (the node)
            "properties": {
                # These are task level items that over-ride global
                "requires": {"$ref": "#/definitions/requires"},
                "resources": {"$ref": "#/definitions/resources"},
                "attributes": {"$ref": "#/definitions/attributes"},
                # Name only is needed to reference the task elsewhere
                "name": {"type": "string"},
                "depends_on": {"type": "array", "items": {"type": "string"}},
                "parent": {"type": "string"},
                # How many of this task are to be run?
                "replicas": {"type": "number", "minimum": 1, "default": 1},
                "level": {"type": "number", "minimum": 1, "default": 1},
                # A command can be a string or a list of strings
                "command": {
                    "type": ["string", "array"],
                    "minItems": 1,
                    "items": {"type": "string"},
                },
                # Custom logic for the transformer
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
                # RESOURCES AND SCRIPTS ARE EXPERIMENTAL
                "scripts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["name", "content"],
                        "properties": {
                            "name": {"type": "string"},
                            "content": {"type": "string"},
                        },
                    },
                },
            },
        },
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
            "type": "object",
            "oneOf": [
                {"$ref": "#/definitions/node_vertex"},
                {"$ref": "#/definitions/slot_vertex"},
            ],
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
            "required": ["type", "count", "with"],
            "properties": {
                "type": {"enum": ["node"]},
                "count": {"type": "integer", "minimum": 1},
                "unit": {"type": "string"},
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
