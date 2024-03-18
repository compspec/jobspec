#!/usr/bin/env python

import json

import jobspec.utils as utils


def main(args, extra):
    """
    Run an extraction. This can be converted to a proper function
    if needed.
    """
    from jobspec.plugin import get_transformer_registry

    registry = get_transformer_registry()

    # This raises an error if not found
    # This would be what we put in a Python script
    # that is in a cronjob, for loop receiver, etc.
    # We can add additional options to the init here
    plugin = registry.get_plugin(args.transform)()

    # Run the plugin with the jobspec
    plugin.run(args.jobspec)
