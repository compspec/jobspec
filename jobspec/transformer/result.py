from jobspec.logger import logger


class Result:
    """
    Helper class to encompass a result
    """

    def __init__(self, out=None, prefix="   ", has_depends_on=False):
        self.out = out or ""
        self.lines = []
        self.prefix = prefix
        self.has_depends_on = has_depends_on

    def add_debug_line(self, line):
        self.lines.append(line)

    def print_extra(self):
        for line in self.lines:
            logger.debug(self.prefix + line)
