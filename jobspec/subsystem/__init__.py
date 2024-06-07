import os

from .subsystem import SubsystemRegistry


def get_subsystem_registry(path=None):
    """
    If a path is not defined, we look in the user home at:

    ~/.compspec/subsystems
    """
    if path is None:
        path = os.path.join(os.path.expanduser("~"), ".compspec", "subsystems")

    if not os.path.exists(path):
        raise ValueError(f"User subsystem directory {path} does not exist")

    # Generate the subsystem registry
    return SubsystemRegistry(path)
