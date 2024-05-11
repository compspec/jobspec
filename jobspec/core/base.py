import json
import os

import yaml

import jobspec.utils as utils


class ResourceBase:
    def __init__(self, data):
        """
        Interact with loaded resources.
        """
        self.data = data or {}

    def to_str(self):
        """
        Convert to string
        """
        return json.dumps(self.data)

    def to_yaml(self):
        """
        Dump to yaml string
        """
        return yaml.dump(self.data)

    def get(self, name, default=None):
        """
        Wrapper to the self.data
        """
        if not self.data:
            return default
        return self.data.get(name, default)

    def update(self, attrs):
        """
        Update with new key value pairs
        """
        if not attrs:
            return
        self.data.update(attrs)

    def load(self, filename):
        """
        Load the jobspec (from file or as string)
        """
        # Case 1: given a raw filename
        if isinstance(filename, str) and os.path.exists(filename):
            self.filename = os.path.abspath(filename)

            try:
                self.data = utils.read_json(self.filename)
            except:
                self.data = utils.read_yaml(self.filename)

        # Case 2: jobspec as dict (that we just want to validate)
        elif isinstance(filename, dict):
            self.data = filename
        # Case 3: jobspec as string for json or yaml
        else:
            try:
                self.data = json.loads(filename)
            except:
                self.data = yaml.load(filename, Loader=yaml.SafeLoader)

        # Case 4: wtf are you giving me? :X
        if not self.data:
            raise ValueError("Unrecognized input format for {self.__class__.__name__}.")
