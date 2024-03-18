import os

import jobspec.core.v1 as js


class TransformerBase:
    """
    A Jobspec Transformer can load a Jobspec and transform for a particular environment.
    """

    def __init__(self, **options):
        """
        Create a new graph backend, accepting any options type.
        """
        # Set options as attributes
        for key, value in options.items():
            setattr(self, key, value)

        # Ever transformer must have a class name
        # TODO more validation stuff

    def load_jobspec(self, filename):
        """
        Load and transform a jobspec.

        This function should be able to load it in some raw format
        and convert into correct directives given the transformer.
        """
        filename = os.path.abspath(filename)
        jobspec = js.Jobspec(filename)
        return jobspec
