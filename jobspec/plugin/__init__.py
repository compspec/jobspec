from .registry import TransformerRegistry

# Only do this once
registry = None


def get_transformer_registry():
    global registry
    if registry is None:
        registry = TransformerRegistry()
        registry.discover()
    return registry
