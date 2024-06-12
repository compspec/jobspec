# JobSpec Nextgen with Depends On

We are going to use jobspec nextgen to run a small workflow with depends on. Note that this requires:

 - The [frobnicator plugin](https://github.com/flux-framework/flux-core/pull/5982) to set a dependency name. This comes with the Developer Environment VSCode container.
 - You will need to get the hostname of the container and update the [broker.toml](broker.toml) here. Also generate a curve certificate and R lite file:

## 1. Setup

First, install a developer version of jobspec (from the root):

```bash
pip install -e .
```

Next, update [broker.toml](broker.toml) to have the hostname of your container (this is in `examples/depends_on` relative to the root). Then:

```bash
flux R encode --local > /tmp/R
flux keygen /tmp/curve.cert
```

You should then be able to start your sub-instance:

```bash
flux start -o --config=./broker.toml 
```
```console
vscode@c970303f1b79:/workspaces/iflux/jobspec$ flux resource list
     STATE NNODES   NCORES    NGPUS NODELIST
      free      1       10        0 c970303f1b79
 allocated      0        0        0 
      down      0        0        0 
```

Check that the frobnicator plugin is installed.

```bash
$ flux job-frobnicator --list-plugins
```
```console
Available plugins:
constraints           Apply constraints to incoming jobspec based on broker config.
defaults              Apply defaults to incoming jobspec based on broker config.
dependency            Translate dependency.name into a job id for dependency.afterok
```

Try submitting a job - it should work.

```bash
flux run hostname
```

## 2. Test Depends On

We can now submit a simple jobspec that has depends_on, which is included in [jobspec.yaml](jobspec.yaml).

```bash
jobspec run ./jobspec.yaml
```

The second task (task-2) depends on task-1, and the first task will sleep for a minute, so at first you'll see:

```bash
$ flux jobs -a
       JOBID USER     NAME       ST NTASKS NNODES     TIME INFO
   ƒ3sL5KeV5 vscode   task-2      D      4      1        - depends:after-success=6329825492992
   ƒ3sGt1CFy vscode   task-1      R      4      1   13.91s 747b0768eb45
```

And then after a minute:

```bash
$ flux jobs -a
       JOBID USER     NAME       ST NTASKS NNODES     TIME INFO
   ƒ3sL5KeV5 vscode   task-2     CD      4      1   3.035s 747b0768eb45
   ƒ3sGt1CFy vscode   task-1     CD      4      1   1.001m 747b0768eb45
```

Tada! And that's it. You can obviously do more complex things, but this is a great start! 
Note that we also keep the plugin [dependency.py](dependency.py) here in case the pull request branch
is lost. You basically need to start a broker that has it enabled, and then put it in the Python flux install 
at `flux/job/frobnicator/plugins`.
