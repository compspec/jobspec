import os
from jobspec.plugin import get_transformer_registry

here = os.path.abspath(os.path.dirname(__file__))
jobspec_file = os.path.join(here, "jobspec.yaml")

def main():
     
    # Get the registry
    registry = get_transformer_registry()

    # The cool thing about transformers is that you can have
    # one tiny server that acts an an interface to several cloud (or other)
    # APIs. A transformer doesn't have to be for cluster batch, it could
    # be for an API to an emphemeral resource
    plugin = registry.get_plugin("flux")()

    # Run the plugin with the jobspec
    plugin.run(jobspec_file)

if __name__ == "__main__":
    main()
