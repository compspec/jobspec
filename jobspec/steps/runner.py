import sys

from jobspec.logger import LogColors


def run(name, step):
    """
    Run a single step. Make it pretty.
    """
    prefix = f"{name} {step.name}".ljust(15)
    print(f"=> {LogColors.OKCYAN}{prefix}{LogColors.ENDC}", end="")
    try:
        result = step.run()
        if not result:
            return
        print(
            f"{LogColors.OKBLUE}{result.out}{LogColors.ENDC} {LogColors.OKGREEN}OK{LogColors.ENDC}"
        )
        result.print_extra()
    except Exception as e:
        print(f"\n{LogColors.RED}{str(e)}{LogColors.ENDC}")
        sys.exit()
