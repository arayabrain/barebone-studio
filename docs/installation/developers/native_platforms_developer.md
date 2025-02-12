(native_platforms_developer)=
Native Platforms (Developer)
=================

```{contents}
:depth: 4
```

## Installation

We introduce how to install optinist for developer.
We have developed optinist python(backend) and typescript(frontend), so you need to make both environment.
Please follow instructions below.

## 1. Make backend environment

### Install Tools

Follow the steps in the `Install Tools` section for each platform below.

- Unix-like platforms
  - Linux
    - [Install Tools](../users/linux.md#install-tools)
  - Mac
    - [Install Tools](../users/mac.md#install-tools)
  - Windows WSL
    - [Install Tools](../users/windows_native.md#install-tools)
- Other platforms
  - Windows Native
    - [Install Tools](../users/windows_native.md#install-tools)

#### Install Node.js

- [Node.js Official](https://nodejs.org)
  - Get node with v20
- You can also install node via [nvm](https://github.com/nvm-sh/nvm). 
  - *Recommended for unix-like platforms.*

After install node, install yarn.
```bash
npm install -g yarn
```

### Create Conda Environment

```bash
conda create -n optinist_dev python=3.8 poetry
conda activate optinist_dev
```

### Clone Repository

```bash
git clone https://github.com/oist/optinist.git
cd ./optinist
```

- copy config files
  ```
  cp studio/config/.env.example studio/config/.env
  cp frontend/.env.example frontend/.env
  ```

### Install Requirements

```bash
poetry install --no-root --with dev
```

### Set Saving Directory

Optinist default saving directory is `/tmp/studio`. If you reboot your PC, this repogitory content is deleted. And setting the saving directory in environment path.

```bash
export OPTINIST_DIR="your_saving_dir"
```

## 2. Run Backend

```bash
python main.py
```
- `python main.py` log is as blow:
```bash
$ run_optinist
INFO:     Will watch for changes in these directories: ['/home/oist/optinist']
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxx] using statreload
INFO:     Started server process [xxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

- If you won't develop the frontend code, launch browser and go to http://localhost:8000

## 3. Run Frontend

Open new terminal window, and go to `frontend` directory.

```bash
# from optinist root directory
cd frontend
```

Then install packages and run.
```bash
yarn install
yarn start
```

- Launch browser, and go to `http://localhost:3000`

Done!

```{eval-rst}
.. note::
    * By default, frontend in development environment uses port ``3000``, while production optinist uses ``8000``.
    * See: :ref:`_optinist_startup_options`
    * If you will make PRs, please see the :ref:`for_developers` section.
```
