from studio.app.common.core.snakemake.smk_utils import SmkInternalUtils
from studio.app.dir_path import DIRPATH

conda_name = "suite2p"


def test_SmkInternalUtils():
    conda_env_rootpath = f"{DIRPATH.DATA_DIR}/conda_envs/{conda_name}"
    conda_env_filepath = f"{DIRPATH.DATA_DIR}/conda_envs/{conda_name}/{conda_name}.yaml"

    conda_env_exists = SmkInternalUtils.verify_conda_env_exists(
        conda_name, conda_env_rootpath, conda_env_filepath
    )

    assert conda_env_exists, f"Invalid verify_conda_env_exists result: {conda_name}"
