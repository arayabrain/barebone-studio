(cli-execution)=
CLI Usage
=================
This section describes how to run a workflow created in GUI on a cluster or in Command Line Interface (CLI).

- [CLI execution](#cli-execution)
  - [1. Config file settings](#1-config-file-settings)
  - [2. Set environment variables for save paths](#2-set-environment-variables-for-save-paths)
  - [3. Input File Settings](#3-input-file-settings)
  - [4. Execution](#4-execution)
  - [5.Output result](#5output-result)

## 1. Config File Settings
Config files can be downloaded from **Record** on the GUI.
Config files may be edited, such as duplicating and changing parameters.
Place the config file required by Snakemake in the desired location for running with the CLI.

## 2. Set Environment Variables for Save Paths
Change environment variables. Change the environment variable as follows, because the default setting refers to the directory under `/tmp/studio`.
```bash
export OPTINIST_DIR="your_saving_dir"
```

With environment variables set, input refers to `{OPTINIST_DIR}/input/` and results are output to `{OPTINIST_DIR}/output`.

## 3. Input File Settings
Input files are stored under `/{OPTINIST_DIR}/input/`.
For example, if there is `mouse_123.tiff`, it is stored as `/{OPTINIST_DIR}/input/mouse_123.tiff`.

## 4. Execution
It can be executed in CLI by running `run_cluster.py`.

The parameter arguments are as follows.
- **config** [string, required]: Path of config.yaml file set in step 1
- **cores** [int, optional, default: 2]: Specifies the number of CPU cores.
- **forceall** [bool, optional, default: false]: Whether to overwrite existing results or not.
- **use_conda** [bool, optional, default: true]: Whether to use the conda virtual environment or not. If not, it is necessary to have caiman, suite2p, etc. installed in the execution environment.

The command executes the following
```bash
python run_cluster.py --config="{snakemake.yaml file path}"
```

## 5.Output Result
The results are stored in `{OPTINIST_DIR}/output/{unique_id}`.
If you want to visualize the results, you can move this directory to local, and you can check the results in GUI.
