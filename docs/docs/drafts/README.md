# JobSpec the Next Generation

> Prototype v1 (not implemented)

## Example

A basic JobSpec to build the package "ior" with spack and then run it looks like this:

```yaml
version: 1
requires:
  io.archspec:
    cpu.target: amd64

tasks:
- name: build
  command: ["spack", "install", "ior"]
  resources:
    count: 4
    type: node
    with:
     - count: 1
       type: slot
       with:
       - count: 4
         type: core

- name: ior
  depends_on: ["build"]
  resources:
    count: 4
    type: node
    with:
    - count: 1
      type: slot
      with:
      - count: 4
        type: core

    # This is an example of a custom "task-level' requires
    requires:
      hardware.gpu.available: "yes"

    command:
      - bash
      - -c
      - |
        spack load ior
        ior -b 10g -O summaryFormat=json
```

The above assumes a cluster with a shared filesystem, where a spack install is already on the user's default path. Note that the order (and ability to read from top to bottom without needing to jump around) is intentional.

## Name

If you want to provide a name for your entire job, which might be appropriate for a batch job, you can define that at the top level:

```yaml
version: 1
name: ml-workload
```

While this is not required, it's recommended for general good practice.

## Tasks

The basic unit of work is the task. Each task MUST define a command. The command can be a list of strings, or a single string. The example above shows how to put custom script logic into a command by way of "bash -c" followed by a pipe and larger block.

- **name** under each task is only required if there is some reference to the task (e.g.,) `depends_on` would say that the task in question depends on another named task).
- **slot** indicates the level of resources in the main cluster (or containment) graph where we are doing an assessment for matching.

Here is another simple example of having two tasks, the first which writes a script and makes it executable, and the second which waits for it and then runs it.
Let's say (for whatever reason) we want to write our main submission file on the fly. We might do the following.

```yaml
tasks:
- name: setup
  command:
    - bash
    - -c
    - |
      cat << EOF > job.sh
      #!/bin/bash
      echo hello from my job
      EOF
      chmod +x ./job.sh

- depends_on: ["setup"]
  command: ["/bin/bash", "job.sh"]
```

This above assumes a shared filesystem.

### Steps

Different workload managers have functionality for staging files, or similar tasks. We will try to define these as abstractions called "steps" where common needs (e.g., paths) are defined as variables, and each workload manager has a transformer that takes the variables and writes to the correct logic. A good example with flux is `flux archive`, which previously was called `flux filemap`. We might generalize this to the idea of staging files. We currently support the following steps:

| Name   | Description |
|--------|-------------|
| stage  | stage files or directories |

We hope to add these minimally, and only choosing ones that might be supported across environments or workload managers.

#### Stage

By default, the JobSpec doesn't know anything about having a shared filesystem or not. In the case of not, you might need to stage files, or ensure they are present across nodes before running any task. Here is what a staging task for a directory might look like:

```yaml
tasks:
- name: setup
  steps:
    - name: stage
      path: /tmp/path-for-workflow
```

or a file:

```yaml
- name: setup
  steps:
    - name: stage
      path: /home/dinosaur/kubeconfig
```


If we were to write this out with a task (with flux commands) it might look like this:

```yaml
- name: root
  level: 1
  command:
    - /bin/bash
    - -c
    - flux archive create -n kubeconfig -C ./home/dinosaur kubeconfig
    - flux -r all -x 0 flux exec flux archive get -n kubeconfig -C ./home/dinosaur
```

Instead of doing the above, we use the abstraction, and the underlying transformer does the translation. This means that different cluster transformers would parse the jobspec, and convert that into whatever their filemap/archive command is. We would likely have similar, abstract workload manager steps.

## Resources

- One of the following is REQUIRED:
  - A top level "resources" section to indicate the entire set are run under `flux batch`. In this case, resources on the level of the task are OPTIONAL and must be a subset of the superset. This setup assumes the entire set is a batch job, with levels of job hierarchies submit below it.
  - One or more task-level "resources" sections, either with or without global resources. If global resources are not provided, each task MUST have resources defined. This setup assumes that each task is a separate submission.

Both of the above can have any dependency relationship. Here is an example of running one task four times ("replicas" is 4) each of which is a separate `flux submit` under the same allocation of 4 nodes.

```yaml
version: 1
requires:
  io.archspec:
    cpu.target: amd64

resources:
  count: 4
  type: node
  with:
   - count: 1
     type: slot
      with:
      - count: 4
        type: core

tasks:
- command: ["echo", "hello", "world"]

  # Run this task 4 times
  replicas: 4
  resources:
    count: 1
    type: node
```

A "name" field is not needed for the task if it is not referenced anywhere. In the above, although we don't define a second "slot" for the task, because it's under the allocation, it's assumed to be exclusive to the work.

Both of the above can have any dependency relationship. Here is an example of running one task eight times, each of which is a separate `flux submit` under the same allocation of 4 nodes. This means 4 jobs will be running at once, with 4 waiting to run after the first 4 are finished.

**Questions**
 - Do we have a default resources? E.g., one node.

Note that I've made resources an object instead of list, which I'm doing until there is good reason to not do that. The list adds additional complexity right now that I'm not sure makes sense, because a task within a batch job would get its own section, regardless of the level it is on.

```yaml
version: 1

tasks:
- name: example-with-default-resources
  command: ["spack", "install", "sqlite"]
```

The above would be a `flux submit` to one node. The "name" is not technically required. Given the above, you could do something as simple as:

```yaml
version: 1

tasks:
- command: ["spack", "install", "singularity"]
- command: ["spack", "install", "mpich"]
- command: ["spack", "install", "go"]
```

## Attributes

Attributes work the same way as resources. They can be defined either on the global (top) level to be applied to all tasks, or on the level of an individual task to over-ride any equivalent global setting.
Attributes currently include:

- [Duration](#duration)
- [Environment](#environment)
- [Current working directory](#current-working-directory)
- [Additional Flags](#additional-flags)

### Duration

The duration is the maximum runtime for your batch job or set of individual tasks. The following applies:

- Setting duration on any level is OPTIONAL. If no duration is set, it defaults to one hour.
- When defined at the global level, child tasks must be <= the global duration.
- When defined at the task level without a global duration, each task (`flux submit`) is not constrained to an upper limit.

Here is an example of running one task with a duration of 5 minutes (300 seconds).

```yaml
version: 1
attributes:
  duration: 300s

tasks:
- name: build
  command: ["spack", "install", "sqlite"]
```

Here is an example of multiple tasks, where each has a separate duration.

```yaml
version: 1

tasks:
- command: ["spack", "install", "singularity"]
  attributes:
    duration: 900s
- name: build
  command: ["spack", "install", "zlib"]
  attributes:
    duration: 300s
```

And finally, the same two tasks, but put under a global duration.

```yaml
version: 1
duration:
  duration: 2000s

tasks:
- command: ["spack", "install", "singularity"]
  attributes:
    duration: 900s
- name: build
  command: ["spack", "install", "zlib"]
  attributes:
    duration: 300s
```

Arguably, a global duration is best used when there is complex logic in the script that deems the total runtime of the individual tasks unknown, and a global duration is more sane to set.

### Environment

Environment is a set of key value pairs that are also under attributes. The same rules apply with respect to global (top) level and within-task definitions. This example shows a global environment variable that is over-ridden by a task-level definition.


```yaml
version: 1
attributes:
  environment:
    LD_LIBRARY_PATH: /usr/local/lib:/usr/local/lib64
tasks:
- name: build
  command: ["spack", "install", "pennant"]
- command: ["pennant", "/opt/pennant/test/params.pnt"]
  depends_on: ["build"]
  attributes:
    envirionment:
      LD_LIBRARY_PATH: /usr/local/cuda/lib
```

Environment variables are always exported at the onset of the task or batch job.

**Question**: should these be blocks of stings at the choice of the user for definition / export?

### Current Working Directory

The current working directory is where you expect the job to run. It defaults to your home on the cluster, or in the context of a container environment, where you would expect the WORKDIR to be.

```yaml
version: 1
tasks:
- name: build
  command: ["spack", "install", "pennant"]
- command: ["pennant", "params.pnt"]
  depends_on: ["build"]
  attributes:
    cwd: /opt/pennant/test/
```

The job above shows the same running logic with pennant, but we are sitting in the directory with the parameter script instead. The same rules apply for the global and task-level definitions under "attributes."

### Additional Flags

Additional flags are attributes that may or may not be supported by different job managers. Here is an example to add `--watch` (or similar) to say you want to submit and stream the output (and block further submits):

```yaml
version: 1

tasks:
- command: ["spack", "install", "sqlite"]
  attributes:
    watch: true
```

## Requires

The "requires" section includes compatibility metadata or key value pairs that are provided to a scheduler or image selection process to inform resource needs. The following applies:

- Any specification of "requires" is OPTIONAL.
- A global "requires" is applied to all tasks in the set.
- Any task-level "requires" over-rides global variables that with the same keys.

The example at the top shows global requires paired with task-level requires.


## Support for Services

A service can be:

- Run as a part of a task, meaning it is started and stopped within the context of an application run.
- Run as a task in an allocation, with a command at the top level of the allocation run to start it, and a command run toward the end to clean up.

In the second case, it is assumed that services that are not cleaned up will be terminated with the end of the allocation. The JobSpec below shows this example:

```yaml
version: 1

resources:
  count: 4
  type: node
  with:
   - count: 1
     type: slot
     with:
     - count: 4
       type: core

tasks:
- name: start
  level: 1
  command: kubectl apply -f ./database.yaml

- name: train
  level: 2
  depends_on: ["start"]
  replicas: 100
  resources:
  - count: 1
    type: node
    command:
      - bash
      - -c
      - |
        ml-train ... -o train.json
        compspec save-artifact ./train.json --host http://localhost:8080

- name: test
  level: 2
  depends_on: ["train"]
  replicas: 10
  resources:
    count: 1
    type: node
    command:
      - bash
      - -c
      - ml-test -o ./test.json --host http://localhost:8080

- name: delete
  depends_on: ["test"]
  level: 1
  command: kubectl delete -f ./database.yaml
```
The above is a faux machine learning job that starts a model endpoint (database) to receive training data and to generate test predictions. The levels and "depends_on" dictate the relationship between tasks in the hierarchy:

```
flux batch >
  database start
    flux submit train (depends on database start)
    flux submit test (depends on train)
  database stop (depends on test)
```

## Nested Hierarchy

From the example above, we can better talk about the nested hierarchy.

1. The top level "resources" indicates the entire thing running under a batch job with 4 nodes.
2. The database is started with kubectl (assuming Usernetes is available) when the batch job starts in a new allocation.
3. The levels indicate where each task is run.
 - level 1 is at the root, which might not have a number of nodes assigned (no flux submit)
 - level 2 is a `flux submit` from the root
 - level 3+ must have a parent defined

Each child resource, if defined, must be a subset of the parent resources.

**Question**: what determines if a command within a batch allocation is done with flux submit or not? How do we know when something isn't a flux submit but something else? If a user wants to intelligently launch multiple levels (beyond two) how do they do that? How do we take what they want to do and map it to something easy here. The example below shows more than 2 levels of tasks, and that the third is required to have a parent:

```yaml
tasks:
- name: root
  level: 1
  command: kubectl apply -f ./database.yaml

- name: sleep
  level: 2
  command: ["sleep", "infinity"]
  ...

- name: generate-data
  level: 2
  command: ["machine", "learn", "things"]
  ...

- name: eat-data
  level: 3
  parent: generate-data
  command: ["munch", "munch", "munch']
```

### Not Accounted for Yet

Additional properties and attributes we might want to consider (only when needed)

- user: variables specific to the user
- parameters: task parameters or state that inform resource selection
- ability to add `--watch` or generally stream logs.
- easy way to write scripts / config files? Just via a task?
- how to represent an OR for resources (not thought about this yet)
- depends_on cannot be supported yet because of [this](https://github.com/flux-framework/flux-core/issues/5917) and I don't like the design of needing to carry around a lookup of job submit IDs to task names.
