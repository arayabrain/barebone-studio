import os
import shutil
from glob import glob

from studio.app.common.core.logger import AppLogger
from studio.app.common.core.storage.remote_storage_controller import (
    BaseRemoteStorageController,
    StorageOption,
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

    def _make_input_data_local_path(self, workspace_id: str, filename: str) -> str:
        input_data_local_path = join_filepath(
            [DIRPATH.INPUT_DIR, workspace_id, filename]
        )
        return input_data_local_path

    def _make_input_data_remote_path(self, workspace_id: str, filename: str) -> str:
        input_data_remote_path = join_filepath(
            [__class__.MOCK_INPUT_DIR, workspace_id, filename]
        )
        return input_data_remote_path

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

    def _make_workspace_input_path(self, workspace_id: str) -> str:
        return join_filepath([__class__.MOCK_INPUT_DIR, workspace_id])

    def _make_workspace_output_path(self, workspace_id: str) -> str:
        return join_filepath([__class__.MOCK_OUTPUT_DIR, workspace_id])

    def _delete_directory_if_exists(self, path: str, label: str) -> None:
        if os.path.isdir(path):
            shutil.rmtree(path)
            logger.debug(f"Deleted mock {label} workspace path: {path}")
        else:
            logger.debug(f"Mock {label} workspace path not found: {path}")

    @property
    def bucket_name(self) -> str:
        return None  # Fixed with None in MockStorage

    async def download_input_data(self, workspace_id: str, filename: str) -> bool:
        # make paths
        input_data_local_path = self._make_input_data_local_path(workspace_id, filename)
        input_data_remote_path = self._make_input_data_remote_path(
            workspace_id, filename
        )

        if os.path.isfile(input_data_local_path):
            logger.debug(f"skip download input data: {input_data_remote_path}")
            return False

        if not os.path.isfile(input_data_remote_path):
            logger.warning("remote path is not exists. [%s]", input_data_remote_path)
            return False

        logger.debug(
            "download input data from remote storage (mock). [%s -> %s]",
            input_data_remote_path,
            input_data_local_path,
        )

        # ----------------------------------------
        # exec downloading
        # ----------------------------------------

        shutil.copy(input_data_remote_path, input_data_local_path)

        return True

    async def upload_input_data(self, workspace_id: str, filename: str) -> bool:
        # make paths
        input_data_local_path = self._make_input_data_local_path(workspace_id, filename)
        input_data_remote_path = self._make_input_data_remote_path(
            workspace_id, filename
        )

        logger.debug(
            "upload input data to remote storage (mock). [%s -> %s]",
            input_data_local_path,
            input_data_remote_path,
        )

        # ----------------------------------------
        # exec uploading
        # ----------------------------------------

        input_data_remote_dir = os.path.dirname(input_data_remote_path)
        create_directory(input_data_remote_dir)

        shutil.copy(input_data_local_path, input_data_remote_path)

        return True

    async def delete_input_data(self, workspace_id: str, filename: str) -> bool:
        # make paths
        input_data_remote_path = self._make_input_data_remote_path(
            workspace_id, filename
        )

        logger.debug(
            "delete input data from remote storage (mock). [%s]",
            input_data_remote_path,
        )

        # ----------------------------------------
        # exec deleting
        # ----------------------------------------

        os.remove(input_data_remote_path)

        return True

    async def download_all_experiments_metas(self, workspace_ids: list = None) -> bool:
        # ----------------------------------------
        # make paths
        # ----------------------------------------

        metadata_filenames = [
            DIRPATH.EXPERIMENT_YML,
            DIRPATH.SNAKEMAKE_CONFIG_YML,
            DIRPATH.WORKFLOW_YML,
        ]

        config_yml_paths = []

        if workspace_ids:  # search specified workspaces
            # Search per workspace
            for ws_id in workspace_ids:
                for metadata_filename in metadata_filenames:
                    config_yml_search_path = (
                        f"{__class__.MOCK_OUTPUT_DIR}/{ws_id}/**/{metadata_filename}"
                    )
                    tmp_config_yml_paths = glob(config_yml_search_path, recursive=True)
                    config_yml_paths.extend(tmp_config_yml_paths)
                    del tmp_config_yml_paths

        else:  # search all workspaces
            for metadata_filename in metadata_filenames:
                config_yml_search_path = (
                    f"{__class__.MOCK_OUTPUT_DIR}/**/{metadata_filename}"
                )
                tmp_config_yml_paths = glob(config_yml_search_path, recursive=True)
                config_yml_paths.extend(tmp_config_yml_paths)
                del tmp_config_yml_paths

        target_files = sorted(config_yml_paths)

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

    async def delete_workspace(self, workspace_id: str, category: str) -> bool:
        try:
            logger.info(
                f"[MOCK] Deleting workspace '{workspace_id}' (category: '{category}')"
            )

            if category == StorageOption.INPUT:
                path = self._make_workspace_input_path(workspace_id)
                self._delete_directory_if_exists(path, StorageOption.INPUT)

            elif category == StorageOption.OUTPUT:
                path = self._make_workspace_output_path(workspace_id)
                self._delete_directory_if_exists(path, StorageOption.OUTPUT)

            else:
                logger.warning(
                    f"[MOCK] Unknown category '{category}' — no action taken."
                )
                return False

            return True

        except Exception as e:
            logger.exception(f"[MOCK] Failed to delete workspace '{workspace_id}': {e}")
            return False
