import os
import shutil
from glob import glob

from studio.app.common.core.logger import AppLogger
from studio.app.common.core.storage.remote_storage_controller import (
    BaseRemoteStorageController,
)
from studio.app.common.core.utils.filepath_creater import (
    create_directory,
    join_filepath,
)
from studio.app.dir_path import DIRPATH

logger = AppLogger.get_logger()


class MockStorageController(BaseRemoteStorageController):
    """
    Mock Storage Controller (uses of development)
    """

    MOCK_STORAGE_DIR = (
        os.environ.get("MOCK_STORAGE_DIR")
        if "MOCK_STORAGE_DIR" in os.environ
        else "/tmp/studio/mock-storage"
    )
    MOCK_INPUT_DIR = f"{MOCK_STORAGE_DIR}/input"
    MOCK_OUTPUT_DIR = f"{MOCK_STORAGE_DIR}/output"

    def __init__(self):
        # initialization: create directories
        create_directory(__class__.MOCK_INPUT_DIR)
        create_directory(__class__.MOCK_OUTPUT_DIR)

    def _make_experiment_local_path(self, workspace_id: str, unique_id: str) -> str:
        experiment_local_path = join_filepath(
            [DIRPATH.OUTPUT_DIR, workspace_id, unique_id]
        )
        return experiment_local_path

    def _make_experiment_remote_path(self, workspace_id: str, unique_id: str) -> str:
        experiment_remote_path = join_filepath(
            [__class__.MOCK_OUTPUT_DIR, workspace_id, unique_id]
        )
        return experiment_remote_path

    @property
    def bucket_name(self) -> str:
        return None  # Fixed with None in MockStorage

    async def download_all_experiments_metas(self, workspace_ids: list = None) -> bool:
        # ----------------------------------------
        # make paths
        # ----------------------------------------

        if workspace_ids:  # search specified workspaces
            # Search per workspace
            experiment_yml_paths = []
            workflow_yml_paths = []
            for ws_id in workspace_ids:
                experiment_yml_search_path = (
                    f"{__class__.MOCK_OUTPUT_DIR}/{ws_id}/**/{DIRPATH.EXPERIMENT_YML}"
                )
                tmp_experiment_yml_paths = glob(
                    experiment_yml_search_path, recursive=True
                )
                experiment_yml_paths.extend(tmp_experiment_yml_paths)
                del tmp_experiment_yml_paths

                workflow_yml_search_path = (
                    f"{__class__.MOCK_OUTPUT_DIR}/{ws_id}/**/{DIRPATH.WORKFLOW_YML}"
                )
                tmp_workflow_yml_paths = glob(workflow_yml_search_path, recursive=True)
                workflow_yml_paths.extend(tmp_workflow_yml_paths)
                del tmp_workflow_yml_paths
        else:  # search all workspaces
            experiment_yml_search_path = (
                f"{__class__.MOCK_OUTPUT_DIR}/**/{DIRPATH.EXPERIMENT_YML}"
            )
            experiment_yml_paths = glob(experiment_yml_search_path, recursive=True)

            workflow_yml_search_path = (
                f"{__class__.MOCK_OUTPUT_DIR}/**/{DIRPATH.WORKFLOW_YML}"
            )
            workflow_yml_paths = glob(workflow_yml_search_path, recursive=True)

        target_files = sorted(experiment_yml_paths + workflow_yml_paths)

        logger.debug(
            "download all medata from remote storage (mock). [count: %d]",
            len(target_files),
        )

        # ----------------------------------------
        # exec downloading
        # ----------------------------------------

        # do copy data from remote storage
        target_files_count = len(target_files)
        for index, remote_config_yml_path in enumerate(target_files):
            relative_config_yml_path = remote_config_yml_path.replace(
                f"{__class__.MOCK_OUTPUT_DIR}/", ""
            )
            local_config_yml_path = f"{DIRPATH.OUTPUT_DIR}/{relative_config_yml_path}"
            local_config_yml_dir = os.path.dirname(local_config_yml_path)

            if not os.path.isfile(local_config_yml_path):
                logger.debug(
                    f"copy config_yml: {relative_config_yml_path} "
                    f"({index+1}/{target_files_count})"
                )

                os.makedirs(local_config_yml_dir, exist_ok=True)

                shutil.copy(remote_config_yml_path, local_config_yml_dir)

            else:
                logger.debug(
                    f"skip copy config_yml: {relative_config_yml_path} "
                    f"({index+1}/{target_files_count})"
                )
                continue

        return True

    async def download_experiment(self, workspace_id: str, unique_id: str) -> bool:
        # make paths
        experiment_local_path = self._make_experiment_local_path(
            workspace_id, unique_id
        )
        experiment_remote_path = self._make_experiment_remote_path(
            workspace_id, unique_id
        )

        if not os.path.isdir(experiment_remote_path):
            logger.warning("remote path is not exists. [%s]", experiment_remote_path)
            return False

        logger.debug(
            "download data from remote storage (mock). [%s -> %s]",
            experiment_remote_path,
            experiment_local_path,
        )

        # ----------------------------------------
        # exec downloading
        # ----------------------------------------

        # cleaning data from local path
        if os.path.isdir(experiment_local_path):
            await self._clear_local_experiment_data(experiment_local_path)

        # do copy data from remote storage
        shutil.copytree(
            experiment_remote_path, experiment_local_path, dirs_exist_ok=True
        )

        return True

    async def upload_experiment(
        self, workspace_id: str, unique_id: str, target_files: list = None
    ) -> bool:
        # make paths
        experiment_local_path = self._make_experiment_local_path(
            workspace_id, unique_id
        )
        experiment_remote_path = self._make_experiment_remote_path(
            workspace_id, unique_id
        )

        # ----------------------------------------
        # exec uploading
        # ----------------------------------------

        # do copy data to remote storage
        if target_files:  # Target specified files.
            logger.debug(
                "upload data to remote storage (mock). [%s -> %s]",
                target_files,
                experiment_remote_path,
            )

            create_directory(experiment_remote_path)

            # copy target files
            for target_file in target_files:
                target_file = f"{experiment_local_path}/{target_file}"
                shutil.copy(target_file, experiment_remote_path)

        else:  # Target all files.
            logger.debug(
                "upload data to remote storage (mock). [%s -> %s]",
                experiment_local_path,
                experiment_remote_path,
            )

            create_directory(experiment_remote_path, delete_dir=True)

            # copy all files
            shutil.copytree(
                experiment_local_path, experiment_remote_path, dirs_exist_ok=True
            )

        return True

    async def delete_experiment(self, workspace_id: str, unique_id: str) -> bool:
        # make paths
        experiment_remote_path = self._make_experiment_remote_path(
            workspace_id, unique_id
        )

        logger.debug(
            "delete data from remote storage (mock). [%s]",
            experiment_remote_path,
        )

        # ----------------------------------------
        # exec deleting
        # ----------------------------------------

        # do delete data from remote storage
        if os.path.isdir(experiment_remote_path):
            shutil.rmtree(experiment_remote_path)

        return True
