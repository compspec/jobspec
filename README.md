# jobspec (python)

> Translation layer for a jobspec specification to cluster execution

[![PyPI version](https://badge.fury.io/py/jobspec.svg)](https://badge.fury.io/py/jobspec)

![https://github.com/compspec/jobspec/blob/main/img/jobspec-bot.png?raw=true](https://github.com/compspec/jobspec/blob/main/img/jobspec-bot.png?raw=true)

This library includes a cluster agnostic language to setup a job (one unit of work in a jobspec).
It is a transformational layer, or a simple language that converts steps needed to prepare a job
for a specific clusters scheduler. If you think it looks too simple then I'd say it's a success,

## Usage

A transformer provides one or more steps for the jobpsec to be transformed and understood for a particular
execution environment. They include:

| Name   | Description |
|--------|-------------|
| write  | write a file in the staging directory |
| stage  | stage a file across nodes |
| submit | submit the job |
| batch  | submit the job with a batch command (more common in HPC) |
| auth   | authenticate with some service |

These are the basic steps that @vsoch needs now for scheduling experiments, and more can be added (or tweaked) if needed.

### Steps

### Example

Start up the development environment to find yourself in a container with flux. Start a test instance:

```bash
flux start --test-size=4
```

Note that we have 4 faux nodes and 40 faux cores.

```bash
flux resource list
```
```console
     STATE NNODES   NCORES    NGPUS NODELIST
      free      4       40        0 194c2b9f4f3c,194c2b9f4f3c,194c2b9f4f3c,194c2b9f4f3c
 allocated      0        0        0
      down      0        0        0
```

Ensure you have jobspec installed! Yes, we are vscode, installing to the container, so we use sudo. YOLO.

```bash
sudo pip install -e .
```

We are going to run the [examples/hello-world-jobspec.yaml](examples/hello-world-jobspec.yaml). This setup is way overly
complex for this because we don't actually need to do any staging or special work, but it's an example, so intended to be so.
Also note that the design of this file is subject to change. For example, we don't have to include the transform directly in the
jobspec - it can be a file that the jobspec writes, and then the command is issued. I like it better as a piece of it, so am putting
it there for the time being, mostly because it looks nicer. I'm sure someone will disagree with me about that.

```bash
# Example showing without watching (waiting) and showing output
jobspec run ./examples/hello-world-jobspec.yaml

# Example that shows waiting for output
jobspec run ./examples/hello-world-wait-jobspec.yaml

# Example with batch using flux
jobspec run ./examples/hello-world-batch.yaml
```

Note that the default transformer is flux, so the above are equivalent to:

```bash
jobspec run -t flux ./examples/hello-world-wait-jobspec.yaml
jobspec run --transformer flux ./examples/hello-world-wait-jobspec.yaml
```


### Details

As an example, although you *could* submit a job with a command ready to go - assuming your cluster has the
software needed and files, and you just want to run it, assuming submission to a cluster you haven't
setup on, you might need the following logic:

1. Write a script to file that is intended to install something.
2. Stage this file across nodes.
3. Submit the script to all nodes to do the install.
4. Write a script to file for your actual job.
5. Again, stage this file across nodes (assuming no share filesystem)
6. Submit the job, either as a submit or batch directive to a workload manager.

The way that you do this with every workload manager (or cluster, more generally) is going to vary
quite a bit. However, with a transformation - a mapping of abstract steps to a specific cluster
workload manager, you can write those steps out very simply:

```yaml
transform:

  - step: write
    filename: install.sh
    executable: true

  - step: stage
    filename: install.sh

  - step: submit
    filename: install.sh
    wait: true

  - step: write
    filename: job.sh
    executable: true

  - step: stage
    filename: job.sh

  - step: submit
    filename: job.sh
    wait: true
```

The above assumes we don't have a shared filesystem, and the receiving cluster has some cluster-specific method for staging or
file mapping. It could be ssh, or a filemap, or something else. For an ephemeral cluster API, it might be an interaction with
a storage provider, or just adding the file to an API call that will (in and of itself) do that creation, akin to a startup script for
an instance in Terraform. It really doesn't matter - the user can expect the file to be written and shared across nodes.
This is not intended to be a workflow or build tool - it simply is a transformational layer that a jobspec can provide
to setup a specific cluster environment. It works with a jobspec in that you define your filenames (scripts) in the tasks->scripts
directive. It also uses a plugin design, so a cluster or institution can write a custom transformer to install, and it will be discovered
by name. This is intended to work with the prototype [rainbow](https://github.com/converged-computing/rainbow) scheduler.
Jobspec is an entity of [flux-framework](https://flux-framework.org).

### Frequently Asked Questions

#### Why not rely on Flux internals?

If we lived in a universe of just flux, sure we wouldn't need this. But the world is more than Flux, and we want to extend our Jobspec to that world.
So we want a Jobspec to be able to handle a transformation of some logic (the above) into an execution that might not involve flux at all. It could be another workload manager (e.g., Slurm),
Kubernetes, or it could be a service that submits to some cloud batch API.

#### What are all the steps allowed?

They are currently shown in the example above, and better documentation will be written. Arguably, any transformation backend does not
need to support every kind of step, however if you provide a Jobspec to a transformer with a step not supported, you'll get an error.

#### Where are the different transformers defined?

We currently have our primary (core) transformers here in [jobspec/transformer](jobspec/transformer), however a registry that discovers jobspec-* named Python modules can allow an out of tree install and use of a transfomrmer. This use case is anticipating clusters with some custom or private logic that cannot be shared in a public GitHub repository.

#### How do you know this is a good idea?

I don't, or won't until I try it for experiments. I decided to try something like it after several days of preparing for experiments,and realizing that this transformation layer was entirely missing.

### Means of Interaction

There are several likely means of interacting with this library:

- As a service that runs at some frequency to receive jobs (written as a loop in Python in some context)
- As a cron job that does the same (an entry to crontab to run "jobspec" at some frequency)
- As a one off run (a single run of the above)

For the example usage here, and since the project I am working on is concerned with Flux, we will start with the simplest case - a client that is running inside a flux instance (meaning it can import flux) that reads in a jobspec with a section that defines a set of transforms, and then issues the commands to stage the setup and use flux to run the work defined by the jobspec.

## Developer

### Organization

While you can write an external transformer (as a plugin) a set of core transformers are provided here:

 - [jobspec/transformer](jobspec/transformer): core transformer classes that ship internally here.

### Writing a Transformer

For now, the easiest thing to do is add a single file (named by your transformer) to [jobspec/transformer](jobspec/transformer)
and copy the precedence in the file. A transformer minimally is a class with a name, description, and some number of steps.
You can then use provided steps in [jobspec/steps](jobstep/steps) or use the `StepBase` to write your own. At the end of
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

# This will not fail validation that the step is unknowb, but skip it
Transformer.register_step(steps.EmptyStep, name="stage")
```


## License

HPCIC DevTools is distributed under the terms of the MIT license.
All new contributions must be made under this license.

See [LICENSE](https://github.com/converged-computing/cloud-select/blob/main/LICENSE),
[COPYRIGHT](https://github.com/converged-computing/cloud-select/blob/main/COPYRIGHT), and
[NOTICE](https://github.com/converged-computing/cloud-select/blob/main/NOTICE) for details.

SPDX-License-Identifier: (MIT)

LLNL-CODE- 842614
