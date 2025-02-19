Appendix
=================

```{contents}
:depth: 4
```

## Application Configurations

(_optinist_startup_options)=

#### optinist startup options

- Options for `run_optinist`, `python main.py`
  - `--host` ... Request listen host (default: 127.0.0.1)
    - `127.0.0.1` ... Allow access from localhost only
    - `0.0.0.0` ... Allow access from all networks
  - `--port` ... Request listen port (default: 8000)

- Command Example
  ```bash
  run_optinist --host=0.0.0.0 --port=8000
  ```

### Allow access to optinist from another PC

By setting the optinist startup options, you can access optinist via a browser from a network other than your own PC.

#### Example of procedure

1. Start optinist on host PC
    * machine name: `optinist-demo-pc`
    * run optinist: `run_optinist --host=0.0.0.0 --port=8000`
2. Access to optinist from client PC
    * Access `http://optinist-demo-pc:8000` with a browser

```{eval-rst}
.. caution::
    On optinist host PC, access to the port specified by ``--port`` must also be allowed in the firewall settings for each Platforms(OS).
```

## Application Configurations (Developers)

### Allow access to optinist from another PC

By setting the optinist startup options and configs, you can access optinist via a browser from a network other than your own PC.

#### Example of procedure

1. Start optinist on host PC
    * machine name: `optinist-dev-pc`
    * run backend
      * run: `run_optinist --host=0.0.0.0 --port=8000`
    * run frontend
      * first, edit `frontend/.env`
        ```
        # REACT_APP_SERVER_HOST is OK to leave it empty. (use default: location.hostname)
        REACT_APP_SERVER_HOST=
        REACT_APP_SERVER_PORT=8000
        ```
      * run: `yarn start` or `yarn install && yarn start`
2. Access to optinist from client PC
    * Access `http://optinist-dev-pc:3000` with a browser

```{eval-rst}
.. caution::
    On optinist host PC, access to the port specified by ``--port`` must also be allowed in the firewall settings for each Platforms(OS).
```

