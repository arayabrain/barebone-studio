Docker (Developer)
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

- Install [Docker](https://www.docker.com/products/docker-desktop/)

### Clone repository

```bash
git clone https://github.com/oist/optinist.git
```

#### setup application config files

```bash
cd ./optinist
cp studio/config/.env.example studio/config/.env
cp frontend/.env.example frontend/.env
```

### Start Docker Container

```bash
docker compose -f docker-compose.dev.yml up -d
```

## 2. Access to Backend

- Launch browser, and go to `http://localhost:3000`
- Your local code change will be applied on save.

Done!

```{eval-rst}
.. note::
    * By default, dev container uses port ``3000``, while production docker image uses ``8000``.
    * See: :ref:`_optinist_startup_options` and ``docker-compose.yml``
    * If you will make PRs, please see the :ref:`for_developers` section.
```
