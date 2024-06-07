#!/usr/bin/env python

import sys

from jobspec.subsystem import get_subsystem_registry


def main(args, _):
    """
    Determine if a jobspec can be satsified by local resources.
    This is a fairly simple (flat) check.
    """
    registry = get_subsystem_registry(args.sdir)
    is_satisfied = registry.satisfied(args.jobspec, ignore_missing=not args.require_all)
    sys.exit(0 if is_satisfied else -1)
