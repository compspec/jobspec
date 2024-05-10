import copy


def find_resources(flat, resource, slot, last_one=False):
    """
    Unwrap a nested resource
    """
    # We found a dominant subsystem resource
    # TODO convert flux submit into a jobspec too?
    if "type" in resource and resource["type"] != "slot":
        if "count" not in resource and "replicas" not in resource:
            raise ValueError("A resource must have a count (non-slot) or replicas (slot)")
        flat[resource["type"]] = resource.get("count") or resource.get("replicas")

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


def to_jobspec(resource, js=None, slot_name=None, has_slot=False):
    """
    Recursive function to help convert to jobspec

    There could be more than one slot in the future, but in
    practice now most flux jobspecs just support one.
    """
    slot_name = slot_name or "default"

    # If we don't have flat yet, make it the entire thing
    if not js:
        js = copy.deepcopy(resource)
    else:
        if "with" not in js:
            js["with"] = []

    # We found a place to insert a slot
    if "replicas" in resource:
        has_slot = True
        if "replicas" not in resource:
            raise ValueError("A resource must have a count (non-slot) or replicas (slot)")

        # If we have a slot, expand out into one
        count = resource["replicas"]
        with_list = resource.get("with") or []
        slot = {"type": "slot", "count": count, "label": slot_name}
        if with_list:
            slot["with"] = with_list
            resource["with"] = [slot]

    # If count not in resources, assume 1
    if "count" not in resource:
        resource["count"] = 1

    # Delete requires, it isn't understood
    if "requires" in resource:
        del resource["requires"]
    if "replicas" in resource:
        del resource["replicas"]

    # More traversing...
    if "with" in resource:
        for r in resource["with"]:
            has_slot = to_jobspec(r, js, slot_name, has_slot)
    return has_slot


def parse_resource_subset(named_resources, resources):
    """
    Parse and validate the resource subset.

    Note that right now we rely on the user to ask for sensical values.
    For example, a task in a group (batch) that asks for more GPU than
    the batch has won't be satisfied. But if this is a grow/autoscale
    setup, maybe it eventually could be, so we allow it.
    """
    # If we are given a Resources object, unwrap the data
    if hasattr(resources, "data"):
        resources = resources.data
    if hasattr(named_resources, "data"):
        named_resources = named_resources.data

    # Case 1: we have resources as a string and it's a member of named
    if isinstance(resources, str):
        if "|" in resources:
            raise ValueError("Asking for an OR in resources is not supported yet.")
        if "," in resources:
            raise ValueError("Asking for an AND in resources is not supported yet.")
        if resources not in named_resources:
            raise ValueError(f"Asked for resources '{resources}' that are not known")
        return named_resources[resources]

    # Case 2: It's just it's own thing
    return resources
