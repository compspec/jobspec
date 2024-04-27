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
            find_resources(flat, r, slot, last_one)
    return flat
