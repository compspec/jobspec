# Expose the latest version as core Jobspec
# If the user wants an earlier version (when we have them)
# they can import it
from .v1 import JobspecV1 as Jobspec
