# Commands

## Usage

A JobSpec consists of one or more tasks that have dependencies. This level of dependency is what can be represented in a scheduler.
The JobSpec library here reads in the JobSpec and can map that into specific cluster submit commands.
Here is an example that assumes receiving a Jobspec on a flux cluster.

### Satisfy

We are prototyping user-space subsystems, for which we do a satisfy request of a contender jobspec against a directory of user space subsystem files, which each should
be JGF (json graph format) graphs. While this can be paired with run (to determine if the run should proceed) we provide a separate "satisfy" command to test and prototype the tool.
We also provide a set of example user subsystems in `examples/subsystems` for each of environment modules and spack. This means we can do satisfy requests of jobspecs against the subsystem directory as follows. Here is an example that is satisfied:

```bash
$ jobspec satisfy ./examples/subsystems/jobspec-spack-subystem-satisfied.yaml --subsystem-dir ./examples/subsystems
```
```console
SELECT name from subsystems WHERE name = 'spack';
SELECT label from nodes WHERE subsystem = 'spack' AND type = 'package';
hairy-peanut-butter-6064 OK
```

And here is one not satisfied:

```bash
$ jobspec satisfy ./examples/subsystems/jobspec-spack-subystem-unsatisfied.yaml --subsystem-dir ./examples/subsystems
```
```console
SELECT name from subsystems WHERE name = 'spack';
SELECT label from nodes WHERE subsystem = 'spack' AND type = 'package';
SELECT * from attributes WHERE name = 'name' AND value = 'lammps' and node IN ('package1','package2023','package2028','package2031','package2043','pac...
loopy-car-9711 NOT OK
```

If run from python, the function "satisfied" would return False and the broker could respond appropriately. If you don't provide the `--subsystem-dir` it will default to `~/.compspec/subsystems`, which likely doesn't exist (and you'll get an error). Also note that the subsystem metadata
is expected to be in JSON and our jobspec files are in yaml, so we can throw them into the same examples directory without issue.


### Run

#### 1. Start Flux

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

#### 2. Command Line Examples

We are going to run the [examples/hello-world-jobspec.yaml](examples/hello-world-jobspec.yaml). This setup is way overly
complex for this because we don't actually need to do any staging or special work, but it's an example, so intended to be so.
Also note that the design of this file is subject to change. For example, we don't have to include the transform directly in the
jobspec - it can be a file that the jobspec writes, and then the command is issued. I like it better as a piece of it, so am putting
it there for the time being, mostly because it looks nicer. I'm sure someone will disagree with me about that.

```bash
# Submit a basic set of jobs with dependencies
jobspec run ./examples/hello-world-jobspec.yaml
```
```console
=> flux workload
=> flux submit    ƒDjkLvNF9                 OK
=> flux submit    ƒDjzAyfhh                 OK
```

Add debug to see commands submit

```bash
jobspec --debug run ./examples/hello-world-jobspec.yaml
```
```console
=> flux workload
=> flux submit    ƒ2i6n8XHSP OK
   flux submit --job-name task-1 -N 1 bash -c echo Starting task 1; sleep 3; echo Finishing task 1
=> flux submit    ƒ2i6qafcUw OK
   flux submit --job-name task-2 -N 1 bash -c echo Starting task 2; sleep 3; echo Finishing task 2
```

Note that the default transformer is flux, so the above are equivalent to:

```bash
jobspec run -t flux ./examples/hello-world-jobspec.yaml
jobspec run --transformer flux ./examples/hello-world-jobspec.yaml
```

#### 3. Nested Examples

Try running some advanced examples. Here is a group within a task.

```bash
jobspec --debug run ./examples/task-with-group.yaml
```
```console
=> flux workload
=> flux submit    ƒ2iiMFBqxT OK
   flux submit --job-name task-1 -N 1 bash -c echo Starting task 1; sleep 3; echo Finishing task 1
=> flux batch     ƒ2iiQpk7Qj OK
   #!/bin/bash
   flux submit --job-name task-2-task-0 --flags=waitable bash -c echo Starting task 2; sleep 3; echo Finishing task 2
   flux job wait --all
   flux job submit /tmp/jobspec-.bvu1v7vk/jobspec-5y9n9u0y
```

That's pretty intuitive, because we see that there is a flux submit first, followed by a batch that has a single task run. The last line "flux submit" shows how we are submitting the script that was just shown.
What about a group within a group?

```bash
$ jobspec --debug run ./examples/group-with-group.yaml
```
```console
=> flux workload
=> flux batch     ƒ2jEE7NPXM OK
   #!/bin/bash
   flux submit --job-name group-1-task-0 --flags=waitable bash -c echo Starting task 1 in group 1; sleep 3; echo Finishing task 1 in group 1
   flux job submit --flags=waitable /tmp/jobspec-.ljjiywaa/jobspec-kb5y5lsl
   # rm -rf /tmp/jobspec-.ljjiywaa/jobspec-kb5y5lsl
   flux job wait --all
   flux job submit /tmp/jobspec-.45jezez5/jobspec-8dr1udhx
```

The UI here needs some work, but here is what we see above.

```console
# This is the start of the workload - the entire next gen jobspec always produces one workload
=> flux workload

# This is the top level group that has the other group within - it's the top level "flux batch" that we submit
=> flux batch     ƒ2e7Ay6jvo OK

   # This is showing the first script that is written
   #!/bin/bash

   # Here is the first job submit, now namespaced to group-1 (if the user, me, didn't give it a name)
   flux submit --job-name group-1-task-0 --flags=waitable bash -c echo Starting task 1 in group 1; sleep 3; echo Finishing task 1 in group 1

   # This is submitting group-2 - the jobspec is written in advance
   flux job submit --flags=waitable /tmp/jobspec-.ljjiywaa/jobspec-kb5y5lsl

   # And this will be how we clean it up as we go - always after it's submit. I'm commenting it out for now because rm -rf makes me nervous!
   # rm -rf /tmp/jobspec-.ljjiywaa/jobspec-kb5y5lsl

   # This is the actual end of the batch script
   flux job wait --all

   # This is showing submitting the batch script above, kind of confusing because it looks like it's within it (it's not, just a bad UI for now)
   flux job submit /tmp/jobspec-.45jezez5/jobspec-8dr1udhx
```

And because I didn't clean it up, here is the contents of the batch in the batch for group-2

```bash
#!/bin/bash
flux submit --job-name group-2-task-0 --flags=waitable bash -c echo Starting task 1 in group 2; sleep 3; echo Finishing task 1 in group 2
flux job wait --all
```

#### 4. Python Examples

It could also be the case that you want something running inside a lead broker instance to receive Jobspecs incrementally and then
run them. This Python example can help with that by showing how to accomplish the same, but from within Python.

```bash
python3 ./examples/flux/receive-job.py
```
```console
=> flux workload
=> flux submit    ƒKCJG2ESB OK
=> flux submit    ƒKCa5iZsd OK
```

Just for fun (posterity) I briefly tried having emoji here:

![assets/img/emoji.png](assets/img/emoji.png)


#### 4. Depends On

We have support for depends on, but it requires a custom frobnicator plugin to create a dependency based on job name. You
can see the small tutorial [here](https://github.com/compspec/jobspec/tree/main/examples/depends_on) where you can run the entire thing in the VSCode developer environment.


[home](/README.md#jobspec)
