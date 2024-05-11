import shlex


def new_simple_jobspec(command, nodes=1, name=None, tasks=1, jobspec_version=1):
    """
    Generate a new simple jobspec from basic parameters.
    """
    if isinstance(command, str):
        command = shlex.split(command)

    if not command:
        raise ValueError("A command must be provided.")

    # If we don't have a name, derive one
    if name is None:
        name = command[0]

    if nodes < 1 or tasks < 1:
        raise ValueError("Nodes and tasks for the job must be >= 1")

    # Replicas identifies the slot
    rack_resource = {
        "type": "rack",
        "replicas": 1,
        "with": [
            {
                "type": "node",
                "count": nodes,
                "with": [
                    {
                        "type": "core",
                        "count": tasks,
                    }
                ],
            }
        ],
    }

    tasks_resources = [
        {
            "command": command,
            "resources": name,
        }
    ]
    return {
        "version": jobspec_version,
        "resources": {name: rack_resource},
        "tasks": tasks_resources,
    }
