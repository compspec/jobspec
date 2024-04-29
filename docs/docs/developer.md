# Developer Guide

This is a short guide to help with development. It's recommended to develop with the included `.devcontainer` environment that includes Flux.

## Documentation

The main documentation for the repository is in the [docs](https://github.com/compspec/jobspec/tree/main/docs) directory, and the interface itself is static and generated from the markdown with
javascript. You can edit the markdown files there to update the documentation.

## Developer

### Organization

While you can write an external transformer (as a plugin) a set of core transformers are provided here:

 - [jobspec/transformer](https://github.com/compspec/jobspec/tree/main/jobspec/transformer): core transformer classes that ship internally here.
 - [jobspec/steps](https://github.com/compspec/jobspec/tree/main/jobspec/steps): shared steps used by transformers.
 - [jobspec/core](https://github.com/compspec/jobspec/tree/main/jobspec/core): core library for loading and interacting with JobSpec
 - [jobspec/schema.py](https://github.com/compspec/jobspec/tree/main/jobspec/schema.py): the jsonschema for a JobSpec
 - [jobspec/plugin](https://github.com/compspec/jobspec/tree/main/jobspec/plugin): plugin architecture that provides transformers from a registry (that can support external Python modules)
 - [jobspec/cli](https://github.com/compspec/jobspec/tree/main/jobspec/cli): client functions

### Writing a Transformer

For now, the easiest thing to do is add a single file or module directory (named by your transformer) to [jobspec/transformer](https://github.com/compspec/jobspec/tree/main/jobspec/transformer)
and copy the precedence in the file. A transformer minimally is a class with a name, description, and some number of steps.
You can then use provided steps in [jobspec/steps](https://github.com/compspec/jobspec/tree/main/jobspec/steps) or use the `StepBase` to write your own. At the end of
your transformer file you simply need to register the steps you want to use:

```python
# A transformer can register shared steps, or custom steps
Transformer.register_step(steps.WriterStep)
Transformer.register_step(batch)
Transformer.register_step(submit)
Transformer.register_step(stage)
```

If there is a skip you want the user to be able to define (but skip it for your transformer, for whatever reason you might have)
just register the empty step with the name you want to skip. As an example, let's say my transforer has no concept of a stage
(sharing a file across separate nodes) given that it has a shared filesystem. I might want to do:

```python
import jobspec.steps as steps

# This will not fail validation that the step is unknown, but skip it
Transformer.register_step(steps.EmptyStep, name="stage")
```

[home](/README.md#jobspec)
