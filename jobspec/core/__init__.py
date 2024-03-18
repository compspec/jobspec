# Expose the latest version as core Jobspec
# If the user wants an earlier version (when we have them)
# they can import it
import jobspec.schema as schemas

from .core import Jobspec as JobspecBase


class Jobspec(JobspecBase):
    """
    Use experimental design as default
    """

    schema = schemas.jobspec_v2


class JobspecV1(JobspecBase):
    schema = schemas.jobspec_v1
