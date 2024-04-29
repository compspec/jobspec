import os
import stat

import jobspec.utils as utils

from .base import StepBase


class EmptyStep(StepBase):
    """
    An empty step is used to declare that a step should be skipped
    """

    def run(self, *args, **kwargs):
        """
        do nothing.
        """
        pass
