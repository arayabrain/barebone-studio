import datetime
import json
import os
import shutil
from abc import ABCMeta, abstractmethod
from enum import Enum

from studio.app.common.core.logger import AppLogger
from studio.app.common.core.snakemake.smk_utils import SmkUtils
from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.dir_path import DIRPATH

logger = AppLogger.get_logger()


class RemoteStorageType(Enum):
    NO_USE = "0"
    MOCK = "1"
    S3 = "2"

    @classmethod
    def get_activated_type(cls) -> "RemoteStorageType":
        remote_storage_type_str = os.environ.get(
            "REMOTE_STORAGE_TYPE", cls.NO_USE.value
        )

        try:
            result = RemoteStorageType(remote_storage_type_str)
        except ValueError:
            result = RemoteStorageType.NO_USE

        return result


class RemoteSyncStatus(Enum):
    SUCCESS = "success"
    PROCESSING = "processing"
    ERROR = "error"


class RemoteSyncAction(Enum):
    DOWNLOAD = "download"
    UPLOAD = "upload"
    DELETE = "delete"


class StorageDirectoryType(Enum):
    INPUT = "input"
    OUTPUT = "output"


class RemoteStorageLockError(Exception):
    def __init__(self, workspace_id: str, unique_id: str):
        self.workspace_id = workspace_id
        self.unique_id = unique_id

        message = "Remote data is temporary locked. " f"[{workspace_id}/{unique_id}]"
        super().__init__(message)


class RemoteSyncStatusFileUtil:
    REMOTE_SYNC_STATUS_FILE = "remote_sync_stat.json"

    @classmethod
    def __make_sync_status_file_path(cls, workspace_id: str, unique_id: str) -> str:
        """
        make remote storage sync status file path.
        """
        experiment_local_path = join_filepath(
            [DIRPATH.OUTPUT_DIR, workspace_id, unique_id]
        )
        remote_sync_status_file_path = os.path.join(
            experiment_local_path, cls.REMOTE_SYNC_STATUS_FILE
        )
        return remote_sync_status_file_path

    @classmethod
    def check_sync_status_file(
        cls, workspace_id: str, unique_id: str
    ) -> RemoteSyncStatus:
        """
        check remote storage sync status file.
        """
        remote_sync_status_file_path = cls.__make_sync_status_file_path(
            workspace_id, unique_id
        )

        remote_sync_status = None
        if os.path.isfile(remote_sync_status_file_path):
            with open(remote_sync_status_file_path) as f:
                sync_status_data = json.load(f)
                status_str = str(sync_status_data.get("status")).upper()
                if status_str in RemoteSyncStatus.__members__:
                    remote_sync_status = RemoteSyncStatus[status_str]

        return remote_sync_status

    @classmethod
    def check_sync_status_success(cls, workspace_id: str, unique_id: str) -> bool:
        """
        check remote storage sync status file. (is success)
        """
        return (
            cls.check_sync_status_file(workspace_id, unique_id)
            == RemoteSyncStatus.SUCCESS
        )

    @classmethod
    def check_sync_status_unsynced(cls, workspace_id: str, unique_id: str) -> bool:
        """
        check remote storage sync status file. (is unsynced)
        """
        return cls.check_sync_status_file(workspace_id, unique_id) not in [
            RemoteSyncStatus.PROCESSING,
            RemoteSyncStatus.SUCCESS,
        ]

    @classmethod
    def create_sync_status_file(
        cls,
        remote_bucket_name: str,
        workspace_id: str,
        unique_id: str,
        remote_sync_action: RemoteSyncAction,
        status: RemoteSyncStatus,
    ) -> None:
        """
        create remote storage sync status file.
        """
        remote_sync_status_file_path = cls.__make_sync_status_file_path(
            workspace_id, unique_id
        )

        with open(remote_sync_status_file_path, "w") as f:
            sync_status_data = {
                "remote_bucket_name": remote_bucket_name,
                "remote_storage_type": RemoteStorageType.get_activated_type().value,
                "action": remote_sync_action.value,
                "status": status.value,
                "timestamp": datetime.datetime.now(),
            }
            json.dump(sync_status_data, f, default=str, indent=2)

    @classmethod
    def create_sync_status_file_for_success(
        cls,
        remote_bucket_name: str,
        workspace_id: str,
        unique_id: str,
        remote_sync_action: RemoteSyncAction,
    ) -> None:
        cls.create_sync_status_file(
            remote_bucket_name,
            workspace_id,
            unique_id,
            remote_sync_action,
            RemoteSyncStatus.SUCCESS,
        )

    @classmethod
    def create_sync_status_file_for_processing(
        cls,
        remote_bucket_name: str,
        workspace_id: str,
        unique_id: str,
        remote_sync_action: RemoteSyncAction,
    ) -> None:
        cls.create_sync_status_file(
            remote_bucket_name,
            workspace_id,
            unique_id,
            remote_sync_action,
            RemoteSyncStatus.PROCESSING,
        )

    @classmethod
    def create_sync_status_file_for_error(
        cls,
        remote_bucket_name: str,
        workspace_id: str,
        unique_id: str,
        remote_sync_action: RemoteSyncAction,
    ) -> None:
        cls.create_sync_status_file(
            remote_bucket_name,
            workspace_id,
            unique_id,
            remote_sync_action,
            RemoteSyncStatus.ERROR,
        )

    @classmethod
    def delete_sync_status_file(cls, workspace_id: str, unique_id: str) -> None:
        """
        delete remote storage sync status file.
        """
        remote_sync_status_file_path = cls.__make_sync_status_file_path(
            workspace_id, unique_id
        )

        if os.path.isfile(remote_sync_status_file_path):
            os.remove(remote_sync_status_file_path)

    @classmethod
    def get_remote_bucket_name(cls, workspace_id: str, unique_id: str) -> None:
        """
        get remote_bucket_name from sync status file.
        """
        remote_sync_status_file_path = cls.__make_sync_status_file_path(
            workspace_id, unique_id
        )

        remote_bucket_name = None
        if os.path.isfile(remote_sync_status_file_path):
            with open(remote_sync_status_file_path) as f:
                sync_status_data = json.load(f)
                remote_bucket_name = sync_status_data.get("remote_bucket_name")
        else:
            logger.warning(
                f"remote_sync_status_file not found. [{remote_sync_status_file_path}]"
            )

        assert remote_bucket_name, f"Invalid remote_bucket_name: {remote_bucket_name}"

        return remote_bucket_name


class RemoteSyncLockFileUtil:
    REMOTE_SYNC_LOCK_FILE = "remote_sync.lock"
    LOCK_FILE_EXPIRE_MINUTES = 60  # Fixed at 60 minutes

    @classmethod
    def __make_sync_lock_file_path(cls, workspace_id: str, unique_id: str) -> str:
        """
        make remote storage sync lock file path.
        """
        experiment_local_path = join_filepath(
            [DIRPATH.OUTPUT_DIR, workspace_id, unique_id]
        )
        remote_sync_lock_file_path = os.path.join(
            experiment_local_path, cls.REMOTE_SYNC_LOCK_FILE
        )
        return remote_sync_lock_file_path

    @classmethod
    def check_sync_lock_file(
        cls, workspace_id: str, unique_id: str, raise_error: bool = False
    ) -> bool:
        """
        check remote storage sync status file.
        """
        remote_sync_lock_file_path = cls.__make_sync_lock_file_path(
            workspace_id, unique_id
        )

        is_locked = False
        if os.path.isfile(remote_sync_lock_file_path):
            # Get lock file's modified time
            threshold_min = cls.LOCK_FILE_EXPIRE_MINUTES
            threshold_time = datetime.datetime.now() - datetime.timedelta(
                minutes=threshold_min
            )
            file_modified_time = datetime.datetime.fromtimestamp(
                os.path.getmtime(remote_sync_lock_file_path)
            )

            # If the lock file is old, delete it.
            if file_modified_time <= threshold_time:
                cls.delete_sync_lock_file(workspace_id, unique_id)
                is_locked = False
            else:
                is_locked = True

        if is_locked and raise_error:
            raise RemoteStorageLockError(workspace_id, unique_id)

        return is_locked

    @classmethod
    def create_sync_lock_file(
        cls,
        workspace_id: str,
        unique_id: str,
    ) -> None:
        """
        create remote storage sync lock file.
        """
        remote_sync_lock_file_path = cls.__make_sync_lock_file_path(
            workspace_id, unique_id
        )

        with open(remote_sync_lock_file_path, "w") as f:
            file_data = {
                "workspace_id": workspace_id,
                "unique_id": unique_id,
                "timestamp": datetime.datetime.now(),
            }
            json.dump(file_data, f, default=str, indent=2)

            # force fsync
            os.fsync(f.fileno())

    @classmethod
    def delete_sync_lock_file(cls, workspace_id: str, unique_id: str) -> None:
        """
        delete remote storage sync lock file.
        """
        remote_sync_lock_file_path = cls.__make_sync_lock_file_path(
            workspace_id, unique_id
        )

        if os.path.isfile(remote_sync_lock_file_path):
            os.remove(remote_sync_lock_file_path)


class BaseRemoteStorageController(metaclass=ABCMeta):
    @abstractmethod
    def _make_input_data_local_path(self, workspace_id: str, filename: str) -> str:
        """
        make input data directory local path.
        """

    @abstractmethod
    def _make_input_data_remote_path(self, workspace_id: str, filename: str) -> str:
        """
        make input data directory remote path.
        """

    @abstractmethod
    def _make_experiment_local_path(self, workspace_id: str, unique_id: str) -> str:
        """
        make experiment data directory local path.
        """

    @abstractmethod
    def _make_experiment_remote_path(self, workspace_id: str, unique_id: str) -> str:
        """
        make experiment data directory remote path.
        """

    @property
    @abstractmethod
    def bucket_name(self) -> str:
        """
        return current remotes storage bucket_name.
        """

    @abstractmethod
    def download_input_data(self, workspace_id: str, filename: str) -> bool:
        """
        download input data from remote storage.
        """

    @abstractmethod
    def upload_input_data(self, workspace_id: str, filename: str) -> bool:
        """
        upload input data to remote storage.
        """

    @abstractmethod
    def delete_input_data(self, workspace_id: str, filename: str) -> bool:
        """
        delete input data from remote storage.
        """

    @abstractmethod
    def download_all_experiments_metas(self, workspace_ids: list = None) -> bool:
        """
        download all experiment metadata from remote storage.
        """

    @abstractmethod
    def download_experiment(self, workspace_id: str, unique_id: str) -> bool:
        """
        download experiment data from remote storage.
        """

    @abstractmethod
    def upload_experiment(
        self, workspace_id: str, unique_id: str, target_files: list = None
    ) -> bool:
        """
        upload experiment data to remote storage.

        Args:
            target_files list:
                Specify files to be uploaded (By default, all files are targeted)
        """

    @abstractmethod
    def delete_experiment(self, workspace_id: str, unique_id: str) -> bool:
        """
        delete experiment data from remote storage.
        """

    @abstractmethod
    async def delete_workspace(
        self, workspace_id: str, directory_type: StorageDirectoryType
    ) -> bool:
        """
        Delete workspace data.
        """

    async def _clear_local_experiment_data(self, experiment_local_path: str):
        """
        Clean existing local experiment data
        - Delete all data except for some files (lockfile, etc.)
        """
        source_dir_path = experiment_local_path
        deleting_temp_dir = "_deleting_tmp"
        deleting_temp_dir_path = os.path.join(source_dir_path, deleting_temp_dir)
        exclude_files = [
            deleting_temp_dir,
            RemoteSyncLockFileUtil.REMOTE_SYNC_LOCK_FILE,
            RemoteSyncStatusFileUtil.REMOTE_SYNC_STATUS_FILE,
        ]

        if os.path.isdir(deleting_temp_dir_path):
            shutil.rmtree(deleting_temp_dir_path)

        os.makedirs(deleting_temp_dir_path)

        # Move files to be deleted to a temporary folder
        for filename in os.listdir(source_dir_path):
            source_path = os.path.join(source_dir_path, filename)

            if filename not in exclude_files:
                source_path = os.path.join(source_dir_path, filename)
                dest_path = os.path.join(deleting_temp_dir_path, filename)

                shutil.move(source_path, dest_path)

        # Delete temporary folders for deletion
        shutil.rmtree(deleting_temp_dir_path)


class RemoteStorageController(BaseRemoteStorageController):
    def __init__(self, bucket_name: str):
        remote_storage_type = RemoteStorageType.get_activated_type()

        if remote_storage_type == RemoteStorageType.MOCK:
            from studio.app.common.core.storage.mock_storage_controller import (
                MockStorageController,
            )

            self.__controller = MockStorageController()
        elif remote_storage_type == RemoteStorageType.S3:
            from studio.app.common.core.storage.s3_storage_controller import (
                S3StorageController,
            )

            self.__controller = S3StorageController(bucket_name)
        else:
            assert False, f"Invalid remote_storage_type: {remote_storage_type}"

    @staticmethod
    def is_available():
        """
        Determine if remote storage is available
        """
        remote_storage_type = RemoteStorageType.get_activated_type()
        is_available = remote_storage_type in [
            RemoteStorageType.MOCK,
            RemoteStorageType.S3,
        ]
        return is_available

    def _make_input_data_local_path(self, workspace_id: str, filename: str) -> str:
        return self.__controller._make_input_data_local_path(workspace_id, filename)

    def _make_input_data_remote_path(self, workspace_id: str, filename: str) -> str:
        return self.__controller._make_input_data_remote_path(workspace_id, filename)

    def _make_experiment_local_path(self, workspace_id: str, unique_id: str) -> str:
        return self.__controller._make_experiment_local_path(workspace_id, unique_id)

    def _make_experiment_remote_path(self, workspace_id: str, unique_id: str) -> str:
        return self.__controller._make_experiment_remote_path(workspace_id, unique_id)

    @staticmethod
    def create_user_bucket_name(id: int, prefix: str = "optinist-user") -> str:
        import hashlib
        import time

        current_time = time.time()
        hash_src = f"{id}-{current_time}"
        hash_value = hashlib.md5(hash_src.encode()).hexdigest()
        hash_value = hash_value[0:10]
        new_name = f"{prefix}-{id}-{hash_value}"

        return new_name

    @property
    def bucket_name(self) -> str:
        return self.__controller.bucket_name

    async def create_bucket(self) -> bool:
        remote_storage_type = RemoteStorageType.get_activated_type()

        if remote_storage_type == RemoteStorageType.S3:
            await self.__controller.create_bucket()
        elif remote_storage_type == RemoteStorageType.MOCK:
            logger.info(
                "This remote_storage_type does not use bucket: "
                f"{remote_storage_type.value}"
            )
            pass
        else:
            assert False, (
                "This remote_storage_type does not support bucket: "
                f"{remote_storage_type.value}"
            )

        return True

    async def delete_bucket(self, force_delete=False) -> bool:
        remote_storage_type = RemoteStorageType.get_activated_type()
        if remote_storage_type == RemoteStorageType.S3:
            await self.__controller.delete_bucket(force_delete)
        elif remote_storage_type == RemoteStorageType.MOCK:
            logger.info(
                "This remote_storage_type does not support bucket: "
                f"{remote_storage_type.value}"
            )
            pass
        else:
            assert False, (
                "This remote_storage_type does not use bucket: "
                f"{remote_storage_type.value}"
            )

        return True

    async def download_input_data(self, workspace_id: str, filename: str) -> bool:
        return await self.__controller.download_input_data(workspace_id, filename)

    async def upload_input_data(self, workspace_id: str, filename: str) -> bool:
        return await self.__controller.upload_input_data(workspace_id, filename)

    async def delete_input_data(self, workspace_id: str, filename: str) -> bool:
        return await self.__controller.delete_input_data(workspace_id, filename)

    async def download_all_experiments_metas(self, workspace_ids: list = None) -> bool:
        """
        Args:
          workspace_ids:
            List of workspace ids to be downloaded. if none, all workspaces are targeted
        """
        return await self.__controller.download_all_experiments_metas(workspace_ids)

    async def download_experiment(self, workspace_id: str, unique_id: str) -> bool:
        sync_status_params = {
            "remote_bucket_name": self.bucket_name,
            "workspace_id": workspace_id,
            "unique_id": unique_id,
            "remote_sync_action": RemoteSyncAction.DOWNLOAD,
        }
        result = False

        try:
            # create sync status file
            RemoteSyncStatusFileUtil.create_sync_status_file_for_processing(
                **sync_status_params
            )

            # download experiment data
            result = await self.__controller.download_experiment(
                workspace_id, unique_id
            )

            # download input data
            # *Download the input data related to the experiment data as well.
            input_filenames = SmkUtils.get_datatypes_inputs(
                workspace_id, unique_id, apply_basename=True
            )
            for input_filename in input_filenames:
                await self.download_input_data(workspace_id, input_filename)

            # update sync status file
            RemoteSyncStatusFileUtil.create_sync_status_file_for_success(
                **sync_status_params
            )
        except Exception as e:
            RemoteSyncStatusFileUtil.create_sync_status_file_for_error(
                **sync_status_params
            )
            raise e

        return result

    async def upload_experiment(
        self, workspace_id: str, unique_id: str, target_files: list = None
    ) -> bool:
        sync_status_params = {
            "remote_bucket_name": self.bucket_name,
            "workspace_id": workspace_id,
            "unique_id": unique_id,
            "remote_sync_action": RemoteSyncAction.UPLOAD,
        }
        result = False

        try:
            # create sync status file
            RemoteSyncStatusFileUtil.create_sync_status_file_for_processing(
                **sync_status_params
            )

            result = await self.__controller.upload_experiment(
                workspace_id, unique_id, target_files
            )

            # update sync status file
            RemoteSyncStatusFileUtil.create_sync_status_file_for_success(
                **sync_status_params
            )
        except Exception as e:
            RemoteSyncStatusFileUtil.create_sync_status_file_for_error(
                **sync_status_params
            )
            raise e

        return result

    async def delete_experiment(self, workspace_id: str, unique_id: str) -> bool:
        sync_status_params = {
            "remote_bucket_name": self.bucket_name,
            "workspace_id": workspace_id,
            "unique_id": unique_id,
            "remote_sync_action": RemoteSyncAction.DELETE,
        }
        result = False

        try:
            RemoteSyncStatusFileUtil.create_sync_status_file_for_processing(
                **sync_status_params
            )

            result = await self.__controller.delete_experiment(workspace_id, unique_id)

            RemoteSyncStatusFileUtil.create_sync_status_file_for_success(
                **sync_status_params
            )
        except Exception as e:
            RemoteSyncStatusFileUtil.create_sync_status_file_for_error(
                **sync_status_params
            )
            raise e

        return result

    async def delete_workspace(
        self, workspace_id: str, directory_type: StorageDirectoryType
    ) -> bool:
        try:
            logger.info(
                f"[AWS] Delete WID '{workspace_id}'"
                f"for category '{directory_type.value}'"
            )

            # Delegate the call to the actual backend (S3, Mock, etc.)
            return await self.__controller.delete_workspace(
                workspace_id, directory_type
            )

        except Exception as e:
            logger.exception(f"[AWS] Failed to delete workspace '{workspace_id}': {e}")
            return False


class BaseRemoteStorageSimpleReaderWriter(metaclass=ABCMeta):
    """
    Simplified Reader/Writer wrapper for RemoteStorageController
    - params: Specify only bucket_name
    """

    def __init__(self, bucket_name: str, sync_action: RemoteSyncAction):
        # Note: This Reader class does not implement exclusive control of data.

        self.bucket_name = bucket_name
        self.sync_action = sync_action
        self.__controller = RemoteStorageController(bucket_name)

    async def __aenter__(self) -> RemoteStorageController:
        return self.__controller

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass  # do nothing.


class RemoteStorageSimpleReader(BaseRemoteStorageSimpleReaderWriter):
    """
    Simplified Reader wrapper for RemoteStorageController
    """

    def __init__(self, bucket_name: str):
        super().__init__(bucket_name, RemoteSyncAction.DOWNLOAD)


class RemoteStorageSimpleWriter(BaseRemoteStorageSimpleReaderWriter):
    """
    Simplified Writer wrapper for RemoteStorageController
    """

    def __init__(self, bucket_name: str):
        super().__init__(bucket_name, RemoteSyncAction.UPLOAD)


class BaseRemoteStorageReaderWriter(metaclass=ABCMeta):
    """
    Reader/Writer wrapper for RemoteStorageController
    - ContextManager class supporting async
    - Provides exclusive control for the same experiment data
    - params: bucket_name, workspace_id, unique_id, are specified
    """

    def __init__(
        self,
        bucket_name: str,
        workspace_id: str,
        unique_id: str,
        sync_action: RemoteSyncAction,
    ):
        self.bucket_name = bucket_name
        self.workspace_id = workspace_id
        self.unique_id = unique_id
        self.sync_action = sync_action

        is_locked = RemoteSyncLockFileUtil.check_sync_lock_file(workspace_id, unique_id)
        if is_locked:
            logger.warning("This data is locked because it is being processed.")
            raise RemoteStorageLockError(workspace_id, unique_id)

        # generate remote-sync-lock-file
        RemoteSyncLockFileUtil.create_sync_lock_file(workspace_id, unique_id)

        # generate remote-sync-status-file (for pendding)
        RemoteSyncStatusFileUtil.create_sync_status_file_for_processing(
            bucket_name,
            workspace_id,
            unique_id,
            self.sync_action,
        )

        self.__controller = RemoteStorageController(bucket_name)

    async def __aenter__(self) -> RemoteStorageController:
        return self.__controller

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # update remote-sync-status-file
        if not exc_type:  # Processing success
            RemoteSyncStatusFileUtil.create_sync_status_file_for_success(
                self.bucket_name,
                self.workspace_id,
                self.unique_id,
                self.sync_action,
            )
        else:  # Processing error
            RemoteSyncStatusFileUtil.create_sync_status_file_for_error(
                self.bucket_name,
                self.workspace_id,
                self.unique_id,
                self.sync_action,
            )

        # delete lock file
        RemoteSyncLockFileUtil.delete_sync_lock_file(self.workspace_id, self.unique_id)


class RemoteStorageReader(BaseRemoteStorageReaderWriter):
    """
    Reader wrapper for RemoteStorageController
    """

    def __init__(self, bucket_name: str, workspace_id: str, unique_id: str):
        super().__init__(
            bucket_name, workspace_id, unique_id, RemoteSyncAction.DOWNLOAD
        )


class RemoteStorageWriter(BaseRemoteStorageReaderWriter):
    """
    Writer wrapper for RemoteStorageController
    """

    def __init__(self, bucket_name: str, workspace_id: str, unique_id: str):
        super().__init__(bucket_name, workspace_id, unique_id, RemoteSyncAction.UPLOAD)


class RemoteStorageDeleter(BaseRemoteStorageReaderWriter):
    """
    Deleter wrapper for RemoteStorageController
    """

    def __init__(self, bucket_name: str, workspace_id: str, unique_id: str):
        super().__init__(bucket_name, workspace_id, unique_id, RemoteSyncAction.DELETE)


async def upload_experiment_wrapper(
    remote_bucket_name: str, workspace_id: str, unique_id
):
    """
    Utility functions for uploading input data
    This function combines multiple steps into one function
      so that it can be executed via asyncio.gather.
    """
    async with RemoteStorageWriter(
        remote_bucket_name, workspace_id, unique_id
    ) as remote_storage_controller:
        await remote_storage_controller.upload_experiment(workspace_id, unique_id)


async def upload_input_data_wrapper(
    remote_bucket_name: str, workspace_id: str, input_data_name: str
):
    """
    Utility functions for uploading experiments data
    This function combines multiple steps into one function
      so that it can be executed via asyncio.gather.
    """
    async with RemoteStorageSimpleWriter(
        remote_bucket_name
    ) as remote_storage_controller:
        await remote_storage_controller.upload_input_data(workspace_id, input_data_name)
