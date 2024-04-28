def find_resources(flat, resource, slot, last_one=False):
    """
    Unwrap a nested resource
    """
    # We found a dominant subsystem resource
    if "type" in resource and resource["type"] != "slot":
        flat[resource["type"]] = resource["count"]

    # The previous was the found slot, return
    if last_one:
        return True

    # We found the slot, this is where we stop
    if "type" in resource and resource["type"] == "slot":
        last_one = True

    # More traversing...
    if "with" in resource:
        for r in resource["with"]:
            print(r)
            find_resources(flat, r, slot, last_one)
    return flat


def parse_resource_subset(named_resources, resources):
    """
    Parse and validate the resource subset.

    Note that right now we rely on the user to ask for sensical values.
    For example, a task in a group (batch) that asks for more GPU than
    the batch has won't be satisfied. But if this is a grow/autoscale
    setup, maybe it eventually could be, so we allow it.
    """
    # Case 1: we have resources as a string and it's a member of named
    if isinstance(resources, str):
        if "|" in resources:
            raise ValueError("Asking for an OR in resources is not supported yet.")
        if "," in resources:
            raise ValueError("Asking for an AND in resources is not supported yet.")
        if resources not in named_resources:
            raise ValueError(f"Asked for resources '{resources}' that are not known")
        return named_resources["resources"]

    # Case 2: It's just it's own thing
    return resources
