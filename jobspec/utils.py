import json
import os
import subprocess
import tempfile
from contextlib import contextmanager

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


@contextmanager
def workdir(dirname):
    """
    Provide context for a working directory, e.g.,

    with workdir(name):
       # do stuff
    """
    here = os.getcwd()
    os.chdir(dirname)
    try:
        yield
    finally:
        os.chdir(here)


def run_command(cmd, stream=False, check_output=False, return_code=0):
    """
    use subprocess to send a command to the terminal.

    If check_output is True, check against an expected return code.
    """
    stdout = subprocess.PIPE if not stream else None
    output = subprocess.Popen(cmd, stderr=subprocess.STDOUT, stdout=stdout)
    t = output.communicate()[0], output.returncode
    output = {"message": t[0], "return_code": t[1]}

    if isinstance(output["message"], bytes):
        output["message"] = output["message"].decode("utf-8")

    # Check the output and raise an error if not success
    if check_output and t[1] != return_code:
        raise ValueError(output["message"].strip())
    return output
