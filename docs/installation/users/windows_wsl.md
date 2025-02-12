# Windows (WSL2)

```{contents}
:depth: 4
```

## About WSL

WSL (Windows Subsystem for Linux) lets you run a Linux environment directly on Windows 10 and newer versions, without the need for a traditional virtual machine.

- To install WSL:
  1. Open PowerShell or Windows Command Prompt as Administrator
  2. Run: `wsl --install`
  3. Open a new terminal and run: `wsl`

- Important note:
  - Development tools like Conda environments, Git, and other packages must be installed within your WSL environment, not in Windows.

## Installation

We introduce how to install optinist.
Please follow instructions below.

<br />

```{eval-rst}
.. caution::
   For WSL2, We have tested OptiNiSt on Ubuntu 20.04/22.04.
```

## 1. Make Backend Environment

### Install Tools

#### Install gcc, g++

- For installing CaImAn, you need to install gcc and g++.

```bash
sudo apt update
sudo apt install gcc g++
```

#### Install Conda Tool

- Install [Miniforge](https://github.com/conda-forge/miniforge)

```bash
# install (*latest version is fine)
curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
bash Miniforge3-$(uname)-$(uname -m).sh

# initial setting (re-login required)
$HOME/miniforge3/bin/conda init
logout

# setting configs
conda config --set channel_priority flexible
```

### Create Conda Environment

```bash
conda create -n optinist python=3.8
conda activate optinist
```

### Install Library

```bash
pip install optinist
```

### Set Saving Directory

Optinist default saving directory is `/tmp/studio`. If you reboot your PC, this repository content is deleted. And setting the saving directory in environment path.

```bash
export OPTINIST_DIR="your_saving_dir"
```

## 2. Run Backend

```bash
run_optinist
```

- `run_optinist` log is as below:

```bash
$ run_optinist
INFO:     Will watch for changes in these directories: ['/home/oist/optinist']
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxx] using statreload
INFO:     Started server process [xxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

- Launch browser, and go to `http://localhost:8000`

Done!
