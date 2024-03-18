import json
import os
import tempfile

import yaml


def read_json(filename):
    """
    Read json from file
    """
    return json.loads(read_file(filename))


def read_file(filename):
    """
    Read in a file content
    """
    with open(filename, "r") as fd:
        content = fd.read()
    return content


def get_tmpdir(tmpdir=None, prefix="", create=True):
    """
    Get a temporary directory for an operation.
    """
    tmpdir = tmpdir or tempfile.gettempdir()
    prefix = prefix or "shpc-tmp"
    prefix = "%s.%s" % (prefix, next(tempfile._get_candidate_names()))
    tmpdir = os.path.join(tmpdir, prefix)

    if not os.path.exists(tmpdir) and create is True:
        os.mkdir(tmpdir)

    return tmpdir


def read_yaml(filename):
    """
    Read yaml from file
    """
    with open(filename, "r") as fd:
        content = yaml.safe_load(fd)
    return content


def write_file(content, filename):
    """
    Write content to file
    """
    with open(filename, "w") as fd:
        fd.write(content)


def write_yaml(obj, filename):
    """
    Read yaml to file
    """
    with open(filename, "w") as fd:
        yaml.dump(obj, fd)
