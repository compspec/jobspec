# Expose the latest version as core Jobspec
# If the user wants an earlier version (when we have them)
# they can import it
import jobspec.schema as schemas

from .core import Attributes
from .core import Jobspec as JobspecBase
from .core import Requires, Resources


class Jobspec(JobspecBase):
    schema = schemas.jobspec_nextgen
