import importlib
import pkgutil

from jobspec.transformer import plugins as in_tree


class TransformerRegistry:
    """
    A registry of transformers - jobspec steps to workload manager setup.
    """

    plugin_class = "Transformer"
    module_prefix = "jobspec_"

    def __init__(self):
        self.discover()

    def get_plugin_names(self):
        return list(self.plugins)

    def is_installed(self, name):
        return name in self.plugins

    def get_plugin(self, name):
        plugin = self.plugins.get(name)
        if plugin is None:
            raise ValueError(f"Plugin {name} is not known.")
        return plugin

    def add_arguments(self, subparser):
        """
        Add subparser and arguments for each plugin
        """
        for _, plugin in self.plugins.items():
            plugin.add_arguments(subparser)

    def discover(self):
        """
        Discover and register plugins with name jobspec-<name>
        """
        self.plugins = {}
        for moduleinfo in pkgutil.iter_modules():
            if not moduleinfo.ispkg or not moduleinfo.name.startswith(self.module_prefix):
                continue
            module = importlib.import_module(moduleinfo.name)
            self.register(moduleinfo.name, module)

        # These are internally provided
        for module in in_tree:
            self.register_in_tree(module)

    def register_in_tree(self, plugin):
        """
        Register a new in tree plugin.

        The main difference here is that in tree plugins
        are already loaded.
        """
        if not hasattr(plugin, "name"):
            raise ValueError(f"Plugin {plugin} is missing a name")
        name = plugin.name
        if name in self.plugins:
            return
        self._validate_plugin(plugin, name)
        self.plugins[name] = plugin

    def register(self, name, plugin):
        """
        Register a new plugin.
        """
        if name in self.plugins:
            return
        self.validate_plugin(name, plugin)

        # Python modules use "_" instead of "-"
        name = name.removeprefix(self.module_prefix).replace("_", "-")
        self.plugins[name] = self.load_plugin(name, plugin)

    def load_plugin(self, name, module):
        """
        Load a plugin
        """
        cls = getattr(module, self.plugin_class)
        return cls(name)

    def validate_plugin(self, name, module):
        """
        Validate a plugin.
        """
        invalid = f"Plugin {name} is not valid"

        # Plugin must be defined!
        if not hasattr(module, self.plugin_class):
            raise ValueError(f"{invalid}, missing {self.plugin_class} to import")

        # Defaults must also be defined
        if not hasattr(module, "defaults"):
            raise ValueError(f"{invalid}, missing 'defaults' submodule.")

        cls = getattr(module, self.plugin_class)
        self._validate_plugin(cls, name)

    def _validate_plugin(self, cls, name):
        """
        Shared validation steps.
        """
        invalid = f"Plugin {name} is not valid"

        # Class attributes
        for attr in ["description", "name"]:
            if not hasattr(cls, attr):
                raise ValueError(f"{invalid}, missing '{attr}' attribute")
            if not getattr(cls, attr, None):
                raise ValueError(f"{invalid},'{attr}' attribute is not defined")
