# Windows (Native)

```{contents}
:depth: 4
```

## Installation

We introduce how to install optinist.
Please follow instructions below.

## 1. Make Backend Environment

### Install Tools

(windows-install-visual-studio-build-tools)=

#### Install Visual Studio Build Tools

- For installing CaImAn, you need to install Visual Studio Build Tools.
- Download `Build Tools for Visual Studio 2022` from [visualstudio.microsoft.com](https://visualstudio.microsoft.com/ja/downloads/) .
- In insteraller, select `Desktop Application for C++`

(windows-install-conda)=

#### Install Conda Tool

- Install Miniforge for Windows
  - [https://github.com/conda-forge/miniforge/releases](https://github.com/conda-forge/miniforge/releases)
    - `Miniforge3-Windows-x86_64.exe`
      - _The latest version is fine._

##### setting configs

On the Terminal (Miniforge Prompt, etc)

- For _Miniforge_
  ```bash
  conda config --set channel_priority flexible
  ```
- For _Anaconda, Miniconda_
  ```bash
  conda config --set channel_priority strict
  ```

### Create Conda Environment

On the Terminal

```bash
conda create -n optinist python=3.8
conda activate optinist
```

### Install Library

On the Terminal

```bash
pip install optinist
```

### Set Saving Directory

Optinist default saving directory is `C:\tmp\optinist`. If you reboot your PC, this repository content is deleted. And setting the saving directory in environment path.

- For Command Prompt
  ```batch
  SET OPTINIST_DIR={your_saving_dir}
  ```
- For PowerShell
  ```powershell
  $ENV:OPTINIST_DIR="{your_saving_dir}"
  ```

## 2. Run Backend

On the Terminal

```bash
run_optinist
```

- `run_optinist` log is as below:

```batch
(optinist) PS C:\optinist> run_optinist
INFO:     Will watch for changes in these directories: ['C:\\optinist']
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process xxxxx using statreload
INFO:     Started server process xxxxx
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

- Launch browser, and go to `http://localhost:8000`

Done!
