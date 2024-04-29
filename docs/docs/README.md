# JobSpec

> Next Generation

This is an abstract job specification that takes a description of work, including requirements, services, and resources, and transforms it into the correct submission commands for a specific workload manager or cloud API. It is intended to be used with the <a href="https://converged-computing.github.io/rainbow" target="_blank">Rainbow Scheduler</a> but Rainbow is not required. We are starting with <a href="https://flux-framework.readthedocs.io" target="_blank">Flux Framework</a> and will be extending to Kubernetes and other workload managers and APIs soon.</p>

## Specifications

For our current specification, see [the spec](spec.md). For a first draft (that wasn't used) see [here](drafts/).

## Frequently Asked Questions

### Is this a Flux jobspec?

Despite the shared name, this is not a Flux jobspec. Type `man bash` to see that the term "jobspec" predates flux. If we lived in a universe of just Flux, sure we wouldn't need this. But the world is more than Flux, and we want to extend our Jobspec to that - providing an abstraction that works with Flux, but also works with other workload managers and compute environments and application programming interfaces.

### What are steps?

A step is a custom setup or staging command that might be allowed for a specific environment. For example, workload managers that know how to map or stage files can use the "stage" step. General steps to write scripts can arguably used anywhere with some form of filesystem, shared or not. The steps that are allowed for a task are shown in the [spec](spec.md). At the onset we will make an effort to only add steps that can be supported across transformer types.

### Where are the different transformers defined?

We currently have our primary (core) transformers here in [jobspec/transformer](jobspec/transformer), however a registry that discovers jobspec-* named Python modules can allow an out of tree install and use of a transfomrmer. This use case is anticipating clusters with some custom or private logic that cannot be shared in a public GitHub repository.

#### Means of Interaction

There are several likely means of interacting with this library:

- As a service that runs at some frequency to receive jobs (written as a loop in Python in some context)
- As a cron job that does the same (an entry to crontab to run "jobspec" at some frequency)
- As a one off run with `jobspec run ...`

For the example usage here, and since the project I am working on is concerned with Flux, we will start with the simplest case - a client that is running inside a flux instance (meaning it can import flux) that reads in a jobspec with a section that defines a set of transforms, and then issues the commands to stage the setup and use flux to run the work defined by the jobspec.

## Commands

Read more about the commands and getting started [here](commands.md#commands).

## Development

Read our [developer guide](#developer.md)
