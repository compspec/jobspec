# JobSpec the Next Generation

## Example

Let's start with a simple example. This is a **tasks a la carte** pattern, which means submitting isolated tasks, but they depend on one another
(which is not required for the pattern). We aren't doing anything fancy with flux hierarchies.
For this set of tasks, we want to write a JobSpec to build and run the package "ior" with spack. That might look like this:

```yaml
version: 1

resources:
  spack-build:
    count: 1
    type: node

    # The node requires this architecture
    requires:
    - name: system
      field: cpu.target
      match: amd64

    # We just want one node with 4 cores
    with:
     - count: 4
       type: core


  # I want one node with 4 gpu
  ior-run:
    count: 1
    type: node
    with:
      count: 4
      type: gpu
      requires:
      - name: hardware
        field: gpu.vendor
        match: nvidia

tasks:
- name: build
  command: ["spack", "install", "ior"]
  resources: spack-build

- name: ior
  depends_on: ["build"]
  resources: ior-run
  command:
    - bash
    - -c
    - |
      spack load ior
      ior -b 10g -O summaryFormat=json
```

The top level resources define the schedule-able units of work, which are referenced by underlying tasks and groups. The grouping in this manner makes it easier to read, and resources combined with requirements "requires" makes it easier to implement. We are also going to add a dummy field "schedule" to indicate that a resource is at the top level and should be asked for (to the scheduler) to schedule separately. This is for special cases where (for some reason) you are passing in a resource spec and don't want all to be asked for to schedule. If "schedule" is not present anywhere, all top level resource groups are expected to be wanted to be scheduled. The above also assumes a cluster with a shared filesystem, where a spack install is already on the user's default path. Now let's walk through specific sections of the above, and then we will move into advanced patterns.

## Tasks

The basic unit of work is the task. Each task MUST define a command. The command can be a list of strings, or a single string. The example above shows how to put custom script logic into a command by way of "bash -c" followed by a pipe and larger block.

- **name** under each task is only required if there is some reference to the task (e.g.,) `depends_on` would say that the task in question depends on another named task).

Here is another simple example of having two tasks, the first which writes a script and makes it executable, and the second which waits for it and then runs it. Let's say (for whatever reason) we want to write our main submission file on the fly. We might do the following.

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

This above assumes a shared filesystem. In addition to steps and the obvious command or depends on, tasks can have references to [resources](#resources), [requires](#requires), and [groups](#groups), discussed below.


### Steps

**Not thought through yet**

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
  command:
    - /bin/bash
    - -c
    - flux archive create -n kubeconfig -C ./home/dinosaur kubeconfig
    - flux -r all -x 0 flux exec flux archive get -n kubeconfig -C ./home/dinosaur
```

Instead of doing the above, we use the abstraction, and the underlying transformer does the translation. This means that different cluster transformers would parse the jobspec, and convert that into whatever their filemap/archive command is. We would likely have similar, abstract workload manager steps.

## Requires

The "requires" section (on the top level) includes user-level subsystem requirements for the JobSpec, which might include (but are not limited to) software, network, or I/O. This metadata will be discovered typically in the user home as separate JGF files (one per user subsystem) under `~/.compspec/subsystems`. The requires section, akin to resources, includes named groups of subsystem requirements that can be referenced in tasks. For example:

```yaml
requires:
  spack-software:
    - name: spack      # subsystem name
      field: type      # field in metadata
      match: package   # this is a spack package node
      attribute: name  # These would be new - for the "attributes" section of the JGF
      value: lammps

  module-software:
    - name: environment-modules
      field: type
      match: module
      attribute: software
      value: lammps

tasks:
- name: build
  command: ["spack", "install", "ior"]
  resources: spack-build
  requires: spack-software|module-software
```

The above is referencing a [spack user subsystem](https://gist.github.com/vsoch/af1c57b558a476d1bb67fd78b284677e#file-spack-subsystem-json-L35-L43) and an [environment module](https://gist.github.com/vsoch/adba1cd620fb8280006e1533a3ab9928) user subsystem that are only accessible to the user that submits or owns the JobSpec. The library here, JobSpec Next Generation, will do a small satisfy check against the JobSpec and the user subsystems to inform the final selection.

## Groups

Different workload managers can represent the concept of a logical grouping of tasks. While they might vary in the nesting of the groups (for example, Flux can nest up the smallest granularity or unit of resource possible) most have the idea of a top level batch script running smaller commands. So let's start with that.

- A **group** is a logical set of tasks that are run under shared resources.

For this example, let's look at the "Mini Mummi" workflow, which requires:

1. Creating a group at the top level that will have shared resources for CPU and GPU.
2. Within the top level batch, starting a task queue service
3. Within the top level batch, submitting jobs to run machine learning tasks
4. Within the top level batch, submitting other jobs to run training
5. And doing the same for testing.

While we could imagine another level of nesting (for example, the machine learning tasks each being a group with a subset of tasks) let's start with this design for now. It might look like this. Note that the requires (and other) sections are removed for brevity:

```yaml
version: 1

# Resources can be used with tasks or task groups
# They are named so can be referenced in multiple places,
# and used with AND and OR
resources:
  mini-mummi:
    count: 8
    type: node
    with:
    - type: gpu
      count: 2
    - type: cores
      count: 4

  # This is a subset of the parent resources above for the GPU portion
  mummi-gpu:
    count: 2
    type: node
    with:
    - type: gpu
      count: 1

  # Same, but for CPU
  mummi-cpu:
    count: 2
    type: node
    with:
    - type: cores
      count: 4

# A group is a "flux batch"
groups:
- name: mini-mummi

  # This shows a reference to resources above
  resources: mini-mummi

  # Tasks are run (or submit) in the order provided
  tasks:

  # "local" means it isn't a flux submit, it's just run in the batch script
  # In this case we start the task queue service
  - local: true
    command: ["kubectl", "apply", "-f", "./task-queue.yaml"]

  # A reference to the group "train" defined below,
  # This will be a flux batch in the top level flux batch
  - group: train

  # flux submit to run test jobs, also run from top level batch
  - name: test
    replicas: 20

    # This says "give me gpu first, then cpu"
    # This is not implemented or supported yet
    resources: mummi-gpu|mummi-cpu
    depends_on: [train]
    command:
      - bash
      - -c
      - ml-test -o ./test.json --host http://localhost:8080

   # And stop the service
   - local: true
     command: ["kubectl", "delete", "-f", "./task-queue.yaml"]

# flux batch from mini-mummi group
- name: train
  resources: mummi-gpu
  tasks:
    # If a task doesn't have resources, it inherits parent group (uses all)
  - name: train
    command:
     - bash
     - -c
     - |
      ml-train ... -o train.json
      compspec save-artifact ./train.json --host http://localhost:8080
```

In the above, we are creating a hierarchy like the following:

 - flux batch ./level-1.sh
   - start kubernetes service
   - flux batch ./train.sh
     - flux submit training job (entire resources of the batch allocaation)
   - flux submit testing jobs (when training is done) 20x
   - stop kubernetes service

The "local" alongside a task command indicates that it isn't a submit or batch, but just a one-off command run in the allocation. Also note that within a JobSpec, groups can be defined alongside tasks, and tasks can reference groups. In both cases, a group is going to create the equivalent of a batch, and a task is akin to a single job. Groups (batches) can have one off commands (not run as a job, but as a line in the batch script) that are under "commands."

## Resources

Now let's talk about resources. Resources are all required to be in named groups at the top section. If you don't put `schedule: true` in any group, they are all assumed to be wanted for a separate scheduling request. If you only want to ask for a subset of the resources (or some are nested) then set `scheduled: true` to those.
While it is not enforced (assuming you know what you are doing, or something like grow/autoscale is possible) it is typically suggested that child resources are a subset of parent resources. Some special cases included:

- If a task does not have resources defined, it inherits the same resources as the parent group.
- A standalone task or group without resources is not allowed.

Here is an example using shared resources, and running one task five times ("replicas" is 5) each of which is a separate `flux submit` under the same allocation of 4 nodes. In this first example, we are asking explicitly for 4 cores, each of which is on one node.

```yaml
version: 1

resources:
  hello-world:
    count: 4
    type: node
    with:
    - count: 4
      type: core

tasks:
- command: ["echo", "hello", "world"]

  # Run this task 4 times
  replicas: 4
  resources: hello-world
```


Here is the same, but asking instead for any number of nodes, and "just give me those 4 cores anywhere!" The only change is switching count to replicas. The node is left as an abstraction in case we want to add resource requirements.

```yaml
version: 1
resources:
  hello-world:
    type: node
    replicas: 4
    with:
    - count: 4
      type: core

tasks:
- command: ["echo", "hello", "world"]

  # Run this task 4 times for each set of 4 cores
  replicas: 4
  resources: hello-world
```


A "name" field is not needed for the task if it is not referenced anywhere. The above can have any dependency relationship. The reason resources are at the top level is to make sharing across tasks easy. For example, start with this jobspec:

```yaml
version: 1
resources:
  spack:
    count: 4
    type: node

tasks:
- command: ["spack", "install", "sqlite"]
  resources: spack
```

The above would be a `flux submit` to one node. The "name" is not technically required. Given the above, you could do something as simple as:

```yaml
version: 1
resources:
  spack:
    count: 1
    type: node

tasks:
- command: ["spack", "install", "singularity"]
  resources: spack
- command: ["spack", "install", "mpich"]
  resources: spack
- command: ["spack", "install", "go"]
  resources: spack
```

### Requires

The "requires" section (on the level of a resource) includes compatibility metadata or key value pairs that are provided to a scheduler or image selection process to inform resource needs. Since we need to know the level of the graph to look (for example, a node attribute is different from a GPU one) we place them on the level of the resource definition. Any specification of "requires" is OPTIONAL. Requires are also implemented as a list of key value pairs (all strings) to make it easy for serialization into an interface, and parsing by custom match algorithm interfaces. Here is an example of adding requires to the spack job above.


```yaml
version: 1
resources:
  spack:
    count: 4
    type: node
    requires:
    - name: system
      field: platform
      match: amd64

tasks:
- command: ["spack", "install", "sqlite"]
  resources: spack
```

### Attributes

Attributes are also defined on the level of resources - the reason being that attributes are scoped to schedulable units. They can also be defined at lower levels (tasks and groups) that are used to submit jobs in nested instances, but won't be asked for on the top level.
It is up to the user to make sure these declarations make sense (for example, you can't ask for a duration for a child job to be longer than the top level resource request duration).

- [Duration](#duration)
- [Environment](#environment)
- [Current working directory](#current-working-directory)
- [Additional Flags](#additional-flags)

#### Duration

The duration is the maximum runtime for your batch job or set of individual tasks. The following applies:

- Setting duration on any level is OPTIONAL. If no duration is set, it defaults to the resource manager default.
- When defined at the group level, the duration sets the upper limit for the group.
- Thus, child tasks must be <= the global duration.
- When defined at the task level without a global duration, each task (`flux submit`) is not constrained to an upper limit.

Here is an example of the spack jobspec above with duration defined for the resource set:

```yaml
version: 1
resources:
  spack:
    count: 1
    type: node
    attributes:
      duration: 300s

tasks:
- command: ["spack", "install", "singularity"]
  resources: spack
```

Arguably, a group duration is best used when there is complex logic in the script that deems the total runtime of the individual tasks unknown, and a group duration is more sane to set.

#### Environment

Environment is a set of key value pairs that are also under attributes.

```yaml
version: 1
resources:
  spack:
    count: 1
    type: node
    environment:
      pasta: labasta

tasks:
- command: ["spack", "install", "singularity"]
  resources: spack
```

Environment variables are always exported at the onset of the task or batch job.

#### Current Working Directory

The current working directory is where you expect the job to run. It defaults to your home on the cluster, or in the context of a container environment, where you would expect the WORKDIR to be.
Here is an example of a set of flat tasks (no groups) with a current working directory set:

```yaml
version: 1
resources:
  spack:
    count: 1
    type: node
    attributes:
      cwd: /opt/pennant/test/

tasks:
- command: ["spack", "install", "singularity"]
  resources: spack
```

#### Additional Flags

Additional flags are attributes that may or may not be supported by different job managers. Here is an example to add `--watch` (or similar) to say you want to submit and stream the output (and block further submits):

```yaml
version: 1
resources:
  spack:
    count: 1
    type: node
    attributes:
      watch: true

tasks:
- command: ["spack", "install", "singularity"]
  resources: spack
```

## Support for Services

A service can be:

- Run as a part of a task, meaning it is started and stopped within the context of an application run.
- Run as part of a group (somewhere in an allocation) with a command at the top level of the allocation run to start it, and a command run toward the end to clean up.

In the second case, it is assumed that services that are not cleaned up will be terminated with the end of the allocation. The JobSpec below shows this example:

```yaml
version: 1

resources:
  ml-group:
    type: node
    count: 1
    with:
    - count: 4
      type: core

  single-node:
    count: 1
    type: node

groups:
 - name: ml-work
   resources: ml-group
   tasks:

   # Local indicates we run the command verbatim with no flux submit
   - name: start
     local: true
     command: kubectl apply -f ./database.yaml

   - name: train
     depends_on: ["start"]
     replicas: 100
     resources: single-node
     command:
      - bash
      - -c
      - |
        ml-train ... -o train.json
        compspec save-artifact ./train.json --host http://localhost:8080

   - name: test
     depends_on: ["train"]
     replicas: 10
     resources: single-node
     command:
      - bash
      - -c
      - ml-test -o ./test.json --host http://localhost:8080

  - name: delete
    depends_on: ["test"]
    local: true
    command: kubectl delete -f ./database.yaml
```

The above is a faux machine learning job that starts a model endpoint (database) to receive training data and to generate test predictions. The local specificaation, tasks, and "depends_on" dictate the relationship between tasks in the hierarchy.

```
flux batch >
  database start
    flux submit train (depends on database start)
    flux submit test (depends on train)
  database stop (depends on test)
```

## Nested Hierarchy

From the example above, we can better talk about the nested hierarchy. A nested hierarchy is not exposed in just a setup with tasks, but requires a group.
In the example below:

1. Each entry under "groups" is a flux batch. The associated resource indicate the entire thing running under a batch job with 4 nodes.
2. The database is started with kubectl (assuming Usernetes is available) when the batch job starts in a new allocation. The "local" parameter specifies this.

Each child resource, if defined, must be a subset of the parent resources.
The example below shows more than 2 levels of tasks, and that the third (level 3) is launched by a batch in level 2 (a group defined at that level):

```yaml
resources:
  machine-learning:
    count: 4
    type: node
    with:
    - count: 4
      type: core

  single-node:
    count: 1
    type: node

  generate-data:
    count: 3
    type: node

groups:
  - name: machine-learning
    resources: machine-learning
    tasks:

      # Local means run at the instance level, no flux submit
      # If the task blocks, it will block the remaining tasks
    - local: true
      command: kubectl apply -f ./database.yaml

    - name: sleep
      resources: single-node
      command: ["sleep", "infinity"]

      # flux batch to launch the generate-data level
      # TODO we need logic here to say "wait until this finishes"
      # same for submits
    - group: generate-data

      # This is cleanup before the job exists
    - local: true
      command: kubectl delete -f ./database.yaml

    # this is another flux batch, launched before the end,
  - name: generate-data
    resources: generate-data
    tasks:
      - command: ["machine", "learn", "things"]
        resources: single-node
      - name: eat-data
        command: ["munch", "munch", "munch"]
        resources: single-node
```

### Not Accounted for Yet

Additional properties and attributes we might want to consider

- Next step - PR to add support for dependency.name to flux-core. I see where this needs to be added (and the logic) and would learn a lot from a hackathon (where I can lead and write the code)
  - Would like to get it supported in flux core first, but if not possible need to consider using jobids here (not ideal)
- Environment still needs to be added to the implementation, along with using requires and attributes meaningfully.
- for groups in groups (batches) along with submit we need logic to wait for completion before the instance cleans up.
- user: variables specific to the user
- parameters: task parameters or state that inform resource selection
- ability to add `--watch` or generally stream logs.
- easy way to write scripts / config files? Just via a task?
- how to represent an OR for resources (not thought about this yet)
- depends_on cannot be supported yet because of [this](https://github.com/flux-framework/flux-core/issues/5917) and I don't like the design of needing to carry around a lookup of job submit IDs to task names.
