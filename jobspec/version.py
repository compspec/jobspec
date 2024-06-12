__version__ = "0.1.14"
AUTHOR = "Vanessa Sochat"
AUTHOR_EMAIL = "vsoch@users.noreply.github.com"
NAME = "jobspec"
PACKAGE_URL = "https://github.com/compspec/jobspec"
KEYWORDS = "cluster, orchestration, transformer, jobspec, flux"
DESCRIPTION = "Jobspec specification and translation layer for cluster work"
LICENSE = "LICENSE"


################################################################################
# Global requirements

INSTALL_REQUIRES = (("jsonschema", {"min_version": None}),)

TESTS_REQUIRES = (("pytest", {"min_version": "4.6.2"}),)
INSTALL_REQUIRES_ALL = INSTALL_REQUIRES + TESTS_REQUIRES
