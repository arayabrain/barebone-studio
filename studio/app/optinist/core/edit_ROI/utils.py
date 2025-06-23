import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Tuple

import numpy as np
import yaml

from studio.app.common.core.logger import AppLogger
from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.common.core.utils.filepath_finder import find_condaenv_filepath
from studio.app.dir_path import DIRPATH
from studio.app.optinist.core.edit_ROI.wrappers import edit_roi_wrapper_dict
from studio.app.optinist.schemas.roi import RoiPos

logger = AppLogger.get_logger()


class EditRoiUtils:
    @classmethod
    def conda(cls, config):
        algo = config["algo"]
        if "conda_name" in edit_roi_wrapper_dict[algo]:
            conda_name = edit_roi_wrapper_dict[algo]["conda_name"]
            return find_condaenv_filepath(conda_name) if conda_name else None
        return None

    @classmethod
    def get_algo(cls, filepath):
        algo_list = edit_roi_wrapper_dict.keys()
        algo = next((algo for algo in algo_list if algo in filepath), None)
        if not algo:
            from fastapi import HTTPException, status

            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
        return algo

    @classmethod
    def execute(cls, filepath: str):
        result = False
        with ProcessPoolExecutor(max_workers=1) as executor:
            logger.info("start snakemake edit_roi process.")
            future = executor.submit(cls._execute_process, filepath)
            result = future.result()
            logger.info("finish snakemake edit_roi process. result: %s", result)

        if not result:
            logger.error("edit_ROI snakemake run failed.")
            from fastapi import HTTPException, status

            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @classmethod
    def _execute_process(cls, filepath: str) -> bool:
        # Lazy import snakemake modules to avoid Python version conflicts
        snakemake_modules = _get_snakemake_modules()
        SnakemakeApi = snakemake_modules["SnakemakeApi"]
        OutputSettings = snakemake_modules["OutputSettings"]
        StorageSettings = snakemake_modules["StorageSettings"]
        ResourceSettings = snakemake_modules["ResourceSettings"]
        DeploymentSettings = snakemake_modules["DeploymentSettings"]
        DeploymentMethod = snakemake_modules["DeploymentMethod"]

        # Create isolated temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_workdir = Path(temp_dir)

            # Create edit_ROI specific config file
            config_data = {
                "type": "EDIT_ROI",
                "algo": cls.get_algo(filepath),
                "file_path": filepath,
            }

            config_file = join_filepath(temp_workdir, "snakemake.yaml")
            with open(config_file, "w") as f:
                yaml.dump(config_data, f)

            # Use new SnakemakeApi pattern with isolated workdir
            with SnakemakeApi(
                OutputSettings(
                    verbose=True,
                    show_failed_logs=True,
                ),
            ) as snakemake_api:
                workflow_api = snakemake_api.workflow(
                    snakefile=Path(DIRPATH.SNAKEMAKE_FILEPATH),
                    workdir=temp_workdir,
                    storage_settings=StorageSettings(),
                    resource_settings=ResourceSettings(cores=2),
                    deployment_settings=DeploymentSettings(
                        deployment_method=[DeploymentMethod.CONDA],
                        conda_frontend="conda",
                        conda_prefix=DIRPATH.SNAKEMAKE_CONDA_ENV_DIR,
                    ),
                )

                dag_api = workflow_api.dag()

                try:
                    dag_api.execute_workflow()
                    result = True
                except Exception as e:
                    logger.error(f"edit_ROI snakemake execution failed: {e}")
                    result = False

        return result


def _get_snakemake_modules():
    """Lazy import snakemake modules to avoid Python version conflicts in conda envs."""
    from snakemake.api import (
        DeploymentMethod,
        DeploymentSettings,
        OutputSettings,
        ResourceSettings,
        SnakemakeApi,
        StorageSettings,
    )

    return {
        "DeploymentMethod": DeploymentMethod,
        "DeploymentSettings": DeploymentSettings,
        "OutputSettings": OutputSettings,
        "ResourceSettings": ResourceSettings,
        "SnakemakeApi": SnakemakeApi,
        "StorageSettings": StorageSettings,
    }


def create_ellipse_mask(shape: Tuple[int, int], roi_pos: RoiPos):
    x, y, width, height = (
        round(roi_pos.posx),
        round(roi_pos.posy),
        round(roi_pos.sizex),
        round(roi_pos.sizey),
    )

    x_coords = np.arange(0, shape[0])
    y_coords = np.arange(0, shape[1])
    xx, yy = np.meshgrid(x_coords, y_coords)

    # Calculate the distance of each pixel from the center of the ellipse
    a = width / 2
    b = height / 2
    distance = ((xx - x) / a) ** 2 + ((yy - y) / b) ** 2

    # Set the pixels within the ellipse to 1 and the pixels outside to NaN
    ellipse = np.empty(shape)
    ellipse[:] = np.nan
    ellipse[distance <= 1] = 1

    return ellipse
