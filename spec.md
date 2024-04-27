# JobSpec the Next Generation

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
  - count: 4
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
  - count: 4
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

The above assumes a cluster with a shared filesystem, where a spack install is already on the user's default path. A few notes:

- **tasks** are the main unit that we care about
- **order** It's human readable. You can read from top to bottom and see what happens.
- **requires**: Requirements for a job are a reference to compatibility metadata. This could be on the global level (applied to all tasks) or for a specific task. Specific task definitions override the global level.
- **resources** Can be defined on the level of a task, or at the global level (to indicate batch work). If defined at the global level, the subset of resources under tasks must be <= the superset.
- **name** under each task is only required if there is a depends_on specification (or for a human readable thing). Label is removed
- **slot** is kept for now because it has utility, but it needs to be clearly defined what it means.


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
- count: 4
  type: node
  with:
   - count: 1
     type: slot
       with:
       - count: 4
         type: core

tasks:
- command: ["echo", "hello", "world"]
  replicas: 4
  resources:
  - count: 1
    type: node
```

A "name" field is not needed for the task if it is not referenced anywhere. In the above, although we don't define a second "slot" for the task, because it's under the allocation, it's assumed to be exclusive to the work.

Both of the above can have any dependency relationship. Here is an example of running one task eight times, each of which is a separate `flux submit` under the same allocation of 4 nodes. This means 4 jobs will be running at once, with 4 waiting to run after the first 4 are finished.

**Questions**
 - Do we have a default resources? E.g., one node.

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

## Duration

The duration is the maximum runtime for your batch job or set of individual tasks. The following applies:

- Setting duration on any level is OPTIONAL. If no duration is set, it defaults to one hour.
- When defined at the global level, child tasks must be <= the global duration.
- When defined at the task level without a global duration, each task (`flux submit`) is not constrained to an upper limit.

Here is an example of running one task with a duration of 5 minutes (300 seconds).

```yaml
version: 1
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
  duration: 900s
- name: build
  command: ["spack", "install", "zlib"]
  duration: 300s
```

And finally, the same two tasks, but put under a global duration.

```yaml
version: 1
duration: 2000s

tasks:
- command: ["spack", "install", "singularity"]
  duration: 900s
- name: build
  command: ["spack", "install", "zlib"]
  duration: 300s
```

Note that a global duration set in absence of task-level durations will not influence the task level durations unless it is under the default. Arguably, a global duration is best used when there is complex logic in the script that deems the total runtime of the individual tasks unknown, and a global duration is more sane to set.


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
- count: 4
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
  - count: 1
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

## Workload Manager Tasks

Different workload managers have functionality for staging files, or similar tasks. We will try to define these as abstractions called "steps" where common needs (e.g., paths) are defined as variables, and each workload manager has a transformer that takes the variables and writes to the correct logic. A good example with flux is `flux archive`, which previously was called `flux filemap`. We might generalize this to the idea of staging files:

```yaml
- name: root
  level: 1
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
