#!/usr/bin/env python

import argparse
import os
import sys

import jobspec
from jobspec.logger import setup_logger


def get_parser():
    parser = argparse.ArgumentParser(
        description="Jobspec",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Global Variables
    parser.add_argument(
        "--debug",
        dest="debug",
        help="use verbose logging to debug.",
        default=False,
        action="store_true",
    )

    parser.add_argument(
        "--quiet",
        dest="quiet",
        help="suppress additional output.",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--version",
        dest="version",
        help="show software version.",
        default=False,
        action="store_true",
    )

    subparsers = parser.add_subparsers(
        help="actions",
        title="actions",
        description="actions",
        dest="command",
    )
    subparsers.add_parser("version", description="show software version")

    # Maybe this warrants a better name, but this seems to be what we'd want to do -
    # run a jobspec
    run = subparsers.add_parser(
        "run",
        formatter_class=argparse.RawTextHelpFormatter,
        description="receive and run a jobpsec",
    )

    # This will do the subsystem match before the run
    # run.add_argument("--subsystem-dir", help="directory with subsystem metadata to load")
    run.add_argument("-t", "--transform", help="transformer to use", default="flux")

    # This does just the user space subsystem match
    satisfy = subparsers.add_parser(
        "satisfy",
        formatter_class=argparse.RawTextHelpFormatter,
        description="determine if a jobspec is satisfied by the user subsystem",
    )
    satisfy.add_argument(
        "--subsystem-dir", dest="sdir", help="subsystem directory with JGF to load"
    )

    # If this is True, we do not allow a satisfy to occur if subsystem metadata is entirely missing
    # and the jobspec declares it needed
    satisfy.add_argument(
        "--require-all",
        dest="require_all",
        help="require all subsystems to be present and satisfied.",
        default=False,
        action="store_true",
    )

    for cmd in [run, satisfy]:
        cmd.add_argument("jobspec", help="jobspec yaml file", default="jobspec.yaml")

    return parser


def run_jobspec():
    """
    this is the main entrypoint.
    """
    parser = get_parser()

    def help(return_code=0):
        """print help, including the software version and active client
        and exit with return code.
        """
        version = jobspec.__version__

        print("\nJobspec v%s" % version)
        parser.print_help()
        sys.exit(return_code)

    # If the user didn't provide any arguments, show the full help
    if len(sys.argv) == 1:
        help()

    # If an error occurs while parsing the arguments, the interpreter will exit with value 2
    args, extra = parser.parse_known_args()

    if args.debug is True:
        os.environ["MESSAGELEVEL"] = "DEBUG"

    # Show the version and exit
    if args.command == "version" or args.version:
        print(jobspec.__version__)
        sys.exit(0)

    setup_logger(
        quiet=args.quiet,
        debug=args.debug,
    )

    # Here we can assume instantiated to get args
    if args.command == "run":
        from .run import main
    elif args.command == "satisfy":
        from .satisfy import main
    else:
        help(1)
    main(args, extra)


if __name__ == "__main__":
    run_jobspec()
