import os

from dotenv import load_dotenv

from studio.app.dir_path import DIRPATH


class EXPDB_DIRPATH:
    load_dotenv(f"{DIRPATH.CONFIG_DIR}/.env")

    EXPDB_DIR = os.environ.get("EXPDB_DIR")
    assert EXPDB_DIR is not None, "EXPDB_DIR must be set"
    assert os.path.exists(EXPDB_DIR), f"{EXPDB_DIR} does not exist"

    PUBLIC_EXPDB_DIR = os.environ.get("PUBLIC_EXPDB_DIR")
    assert PUBLIC_EXPDB_DIR is not None, "PUBLIC_EXPDB_DIR must be set"
    assert os.path.exists(PUBLIC_EXPDB_DIR), f"{PUBLIC_EXPDB_DIR} does not exist"

    assert (
        EXPDB_DIR != PUBLIC_EXPDB_DIR
    ), "EXPDB_DIR and PUBLIC_EXPDB_DIR must be different"

    GRAPH_HOST = os.environ.get("GRAPH_HOST")
    assert GRAPH_HOST is not None, "GRAPH_HOST must be set"

    SELFHOST_GRAPH = os.environ.get("SELFHOST_GRAPH", True)
