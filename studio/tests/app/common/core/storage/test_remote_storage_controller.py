"""
Note of this file:
- This file is the test code for RemoteStorageController.
- RemoteStorageController's mode (Mock, S3, ...)
  is set by the value of the environment variable (.env).
"""

import os
import shutil

import pytest

from studio.app.common.core.storage.remote_storage_controller import (  # noqa: E402
    RemoteStorageController,
    RemoteStorageDeleter,
    RemoteStorageReader,
    RemoteStorageSimpleReader,
    RemoteStorageSimpleWriter,
    RemoteStorageType,
    RemoteStorageWriter,
    RemoteSyncAction,
    RemoteSyncLockFileUtil,
    RemoteSyncStatusFileUtil,
)
from studio.app.dir_path import DIRPATH

remote_bucket_name = os.environ.get("S3_DEFAULT_BUCKET_NAME")
workspace_id = "default"
unique_id = "remote_storage_test"


def test_initialize():
    if not RemoteStorageController.is_available():
        print("RemoteStorageController is available, skip this test.")
        return

    test_data_src_path = f"{DIRPATH.DATA_DIR}/output_test/{workspace_id}/{unique_id}"
    test_data_output_path = f"{DIRPATH.DATA_DIR}/output/{workspace_id}/{unique_id}"

    # cleaning local storage
    if os.path.exists(test_data_output_path):
        shutil.rmtree(test_data_output_path)

    # copy test data
    shutil.copytree(
        test_data_src_path,
        test_data_output_path,
        dirs_exist_ok=True,
    )


@pytest.mark.asyncio
async def test_RemoteSyncLockFileUtil():
    if not RemoteStorageController.is_available():
        print("RemoteStorageController is available, skip this test.")
        return

    RemoteSyncLockFileUtil.create_sync_lock_file(workspace_id, unique_id)
    is_locked = RemoteSyncLockFileUtil.check_sync_lock_file(workspace_id, unique_id)
    assert is_locked, "check_sync_lock_file failed.."

    RemoteSyncLockFileUtil.delete_sync_lock_file(workspace_id, unique_id)
    is_locked = RemoteSyncLockFileUtil.check_sync_lock_file(workspace_id, unique_id)
    assert not is_locked, "check_sync_lock_file failed.."

    # ------------------------------------------------------------
    # Check automatic processing of status file
    #   by RemoteStorageReader ContextManager.
    # ------------------------------------------------------------

    async with RemoteStorageReader(
        remote_bucket_name, workspace_id, unique_id
    ) as remote_storage_controller:
        is_locked = RemoteSyncLockFileUtil.check_sync_lock_file(workspace_id, unique_id)
        assert is_locked, "check_sync_lock_file failed.."

        del remote_storage_controller  # not used

    is_locked = RemoteSyncLockFileUtil.check_sync_lock_file(workspace_id, unique_id)
    assert not is_locked, "check_sync_lock_file failed.."


def test_RemoteSyncStatusFileUtil():
    if not RemoteStorageController.is_available():
        print("RemoteStorageController is available, skip this test.")
        return

    # test create_sync_status_file()
    RemoteSyncStatusFileUtil.create_sync_status_file_for_success(
        remote_bucket_name, workspace_id, unique_id, RemoteSyncAction.UPLOAD
    )
    is_remote_sync_status_ok = RemoteSyncStatusFileUtil.check_sync_status_success(
        workspace_id, unique_id
    )
    assert is_remote_sync_status_ok, "create_sync_status_file failed.."

    # test get_remote_bucket_name()
    remote_bucket_name_ = RemoteSyncStatusFileUtil.get_remote_bucket_name(
        workspace_id, unique_id
    )
    assert remote_bucket_name_, "get_remote_bucket_name failed.."

    # test delete_sync_status_file()
    RemoteSyncStatusFileUtil.delete_sync_status_file(workspace_id, unique_id)


@pytest.mark.asyncio
async def test_RemoteStorageController_crud_bucket():
    if not RemoteStorageController.is_available():
        print("RemoteStorageController is available, skip this test.")
        return
    elif RemoteStorageType.get_activated_type() != RemoteStorageType.S3:
        print("RemoteStorageType is not covered, skip this test.")
        return

    new_bucket_name = "test-optinist-dummy-bucket-0123"

    async with RemoteStorageSimpleReader(new_bucket_name) as remote_storage_controller:
        result = await remote_storage_controller.create_bucket()
        assert result, f"create bucket failed. [{new_bucket_name}]"

    async with RemoteStorageSimpleWriter(new_bucket_name) as remote_storage_controller:
        result = await remote_storage_controller.delete_bucket(force_delete=True)
        assert result, f"delete bucket failed. [{new_bucket_name}]"


@pytest.mark.asyncio
async def test_RemoteStorageController_upload():
    if not RemoteStorageController.is_available():
        print("RemoteStorageController is available, skip this test.")
        return

    # upload specific files to remote
    async with RemoteStorageWriter(
        remote_bucket_name, workspace_id, unique_id
    ) as remote_storage_controller:
        target_files = [DIRPATH.EXPERIMENT_YML, DIRPATH.WORKFLOW_YML]
        await remote_storage_controller.upload_experiment(
            workspace_id, unique_id, target_files
        )

    # delete remote files
    async with RemoteStorageDeleter(
        remote_bucket_name, workspace_id, unique_id
    ) as remote_storage_controller:
        await remote_storage_controller.delete_experiment(workspace_id, unique_id)

    # upload all files to remote
    async with RemoteStorageWriter(
        remote_bucket_name, workspace_id, unique_id
    ) as remote_storage_controller:
        await remote_storage_controller.upload_experiment(workspace_id, unique_id)


@pytest.mark.asyncio
async def test_RemoteStorageController_download():
    if not RemoteStorageController.is_available():
        print("RemoteStorageController is available, skip this test.")
        return

    test_data_output_path = f"{DIRPATH.DATA_DIR}/output/{workspace_id}/{unique_id}"
    test_data_output_experiment_yaml = (
        f"{test_data_output_path}/{DIRPATH.EXPERIMENT_YML}"
    )

    # cleaning local storage
    if os.path.exists(test_data_output_path):
        shutil.rmtree(test_data_output_path)
        os.makedirs(test_data_output_path)

    # download remote metadata files
    async with RemoteStorageSimpleReader(
        remote_bucket_name
    ) as remote_storage_controller:
        # download all workspaces metadata
        await remote_storage_controller.download_all_experiments_metas()
        assert os.path.isfile(
            test_data_output_experiment_yaml
        ), "download_all_experiments_metas failed.."

        # download specified workspaces metadata
        await remote_storage_controller.download_all_experiments_metas([workspace_id])
        assert os.path.isfile(
            test_data_output_experiment_yaml
        ), "download_all_experiments_metas failed.."

    # re cleaning local storage
    if os.path.exists(test_data_output_path):
        shutil.rmtree(test_data_output_path)
        os.makedirs(test_data_output_path)

    # download remote files
    async with RemoteStorageReader(
        remote_bucket_name, workspace_id, unique_id
    ) as remote_storage_controller:
        await remote_storage_controller.download_experiment(workspace_id, unique_id)
        assert os.path.isfile(
            test_data_output_experiment_yaml
        ), "download_experiment failed.."
