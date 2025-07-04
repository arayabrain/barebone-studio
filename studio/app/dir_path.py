import os
import platform
from enum import Enum
from types import SimpleNamespace

from dotenv import load_dotenv

_TMP_DIR = (
    os.environ.get("TEMP", os.environ.get("TMP", "C:\\temp"))
    if platform.system() == "Windows"
    else "/tmp"
)
_DEFAULT_DIR = f"{_TMP_DIR}/studio"
_ENV_DIR = os.environ.get("OPTINIST_DIR")


class DIRPATH:
    DATA_DIR = _DEFAULT_DIR if _ENV_DIR is None else _ENV_DIR

    INPUT_DIR = f"{DATA_DIR}/input"
    OUTPUT_DIR = f"{DATA_DIR}/output"

    os.makedirs(INPUT_DIR, exist_ok=True)
    assert os.path.exists(INPUT_DIR)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    assert os.path.exists(OUTPUT_DIR)

    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    STUDIO_DIR = os.path.dirname(os.path.dirname(__file__))
    APP_DIR = os.path.dirname(__file__)
    CONFIG_DIR = f"{STUDIO_DIR}/config"
    if os.path.isfile(f"{CONFIG_DIR}/.env"):
        load_dotenv(f"{CONFIG_DIR}/.env")

    FRONTEND_DIR = f"{ROOT_DIR}/frontend"
    FRONTEND_DIRS = SimpleNamespace(
        PUBLIC=f"{FRONTEND_DIR}/public",
        BUILD=f"{FRONTEND_DIR}/build",
    )

    LOCKFILE_DIR = f"{_DEFAULT_DIR}/locks"
    os.makedirs(LOCKFILE_DIR, exist_ok=True)
    assert os.path.exists(LOCKFILE_DIR)

    CONDAENV_DIR = (
        f"{os.path.dirname(os.path.dirname(os.path.dirname(__file__)))}/conda"
    )
    SNAKEMAKE_CONDA_ENV_DIR = f"{ROOT_DIR}/.snakemake/conda"

    SNAKEMAKE_FILEPATH = f"{APP_DIR}/Snakefile"
    EXPERIMENT_YML = "experiment.yaml"
    SNAKEMAKE_CONFIG_YML = "snakemake.yaml"
    WORKFLOW_YML = "workflow.yaml"

    FIREBASE_PRIVATE_PATH = f"{CONFIG_DIR}/auth/firebase_private.json"
    FIREBASE_CONFIG_PATH = f"{CONFIG_DIR}/auth/firebase_config.json"

    MICROSCOPE_LIB_DIR = f"{APP_DIR}/optinist/microscopes/libs"
    MICROSCOPE_LIB_ZIP = f"{APP_DIR}/optinist/microscopes/libs.zip"

    LOG_FILE_PATH = f"{DATA_DIR}/logs/studio.log"


class CORE_PARAM_PATH(Enum):
    nwb = f"{DIRPATH.APP_DIR}/optinist/core/nwb/nwb.yaml"
    snakemake = f"{DIRPATH.APP_DIR}/common/core/snakemake/snakemake.yaml"
