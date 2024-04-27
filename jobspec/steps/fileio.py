import os
import stat

import jobspec.utils as utils

from .base import StepBase


class WriterStep(StepBase):
    """
    A writer step has support for writing files

    This step also provides a base for other writing steps.
    """

    name = "write"
    required = ["filename"]

    def validate(self):
        """
        A write step requires a filename, and matching file in scripts
        """
        filename = self.options.get("filename")

        # This validates unique names
        names = list(self.scripts.keys())

        # 1. All filename directives must be defined in scripts
        if filename and filename not in names:
            raise ValueError(
                f"Filename {filename} is defined for a {self.name} step but not in task scripts"
            )

    def run(self, *args, **kwargs):
        """
        write some content to a filename.

        This is currently not used, as we can represent the same logic in a task.

        step: write
        filename: install.sh
        executable: true
        """
        filename = self.options.get("filename")
        stage = self.options.get("stage")
        fullpath = os.path.join(stage, filename)
        utils.write_file(self.scripts[filename]["content"], fullpath)

        executable = self.options.get("executable") is True
        # Execute / search permissions for the user and others
        if executable:
            st = os.stat(fullpath)
            os.chmod(fullpath, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
