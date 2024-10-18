import os
from glob import glob
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from studio.app.common.core.auth.auth_dependencies import get_user_remote_bucket_name
from studio.app.common.core.experiment.experiment import ExptConfig, ExptExtConfig
from studio.app.common.core.experiment.experiment_reader import ExptConfigReader
from studio.app.common.core.experiment.experiment_writer import ExptDataWriter
from studio.app.common.core.logger import AppLogger
from studio.app.common.core.storage.remote_storage_controller import (
    RemoteStorageController,
    RemoteStorageLockError,
    RemoteStorageReader,
    RemoteStorageSimpleReader,
    RemoteSyncStatusFileUtil,
)
from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.common.core.workspace.workspace_dependencies import (
    is_workspace_available,
    is_workspace_owner,
)
from studio.app.common.schemas.experiment import DeleteItem, RenameItem
from studio.app.dir_path import DIRPATH

router = APIRouter(prefix="/experiments", tags=["experiments"])

logger = AppLogger.get_logger()


@router.get(
    "/{workspace_id}",
    response_model=Dict[str, ExptExtConfig],
    dependencies=[Depends(is_workspace_available)],
)
async def get_experiments(
    workspace_id: str,
    remote_bucket_name: str = Depends(get_user_remote_bucket_name),
):
    # search EXPERIMENT_YMLs
    exp_config = {}
    config_paths = glob(
        join_filepath([DIRPATH.OUTPUT_DIR, workspace_id, "*", DIRPATH.EXPERIMENT_YML])
    )

    is_remote_storage_available = RemoteStorageController.is_available()

    # NOTE: If remote_storage is available and config_paths does not exist,
    # assume that data may exist in remote_storage and execute download of metadata.
    if is_remote_storage_available and not config_paths:
        async with RemoteStorageSimpleReader(
            remote_bucket_name
        ) as remote_storage_controller:
            await remote_storage_controller.download_all_experiments_metas(
                [workspace_id]
            )

        # search EXPERIMENT_YMLs, again
        exp_config = {}
        config_paths = glob(
            join_filepath(
                [DIRPATH.OUTPUT_DIR, workspace_id, "*", DIRPATH.EXPERIMENT_YML]
            )
        )

    for path in config_paths:
        try:
            config = ExptConfigReader.read(path)

            # NOTE: Include procs in the function and respond
            #   (for display on the frontend Record screen)
            if config.procs:
                config.function.update(config.procs)

            # Operate remote storage.
            if is_remote_storage_available:
                # check remote synced status.
                is_remote_synced = RemoteSyncStatusFileUtil.check_sync_status_success(
                    workspace_id, config.unique_id
                )

                # extend config to ExptExtConfig
                config = ExptExtConfig(**config.__dict__)
                config.is_remote_synced = is_remote_synced
            else:
                # extend config to ExptExtConfig
                # Always flag as synchronized if remote storage is unused.
                config = ExptExtConfig(**config.__dict__)
                config.is_remote_synced = True

            exp_config[config.unique_id] = config
        except Exception as e:
            logger.error(e, exc_info=True)
            pass

    return exp_config


@router.patch(
    "/{workspace_id}/{unique_id}/rename",
    response_model=ExptConfig,
    dependencies=[Depends(is_workspace_owner)],
)
async def rename_experiment(
    workspace_id: str,
    unique_id: str,
    item: RenameItem,
    remote_bucket_name: str = Depends(get_user_remote_bucket_name),
):
    try:
        config = await ExptDataWriter(
            remote_bucket_name,
            workspace_id,
            unique_id,
        ).rename(item.new_name)
        config.nodeDict = []
        config.edgeDict = []

        return config

    except RemoteStorageLockError as e:
        logger.error(e)
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(e))
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="rename experiment failed",
        )


@router.delete(
    "/{workspace_id}/{unique_id}",
    response_model=bool,
    dependencies=[Depends(is_workspace_owner)],
)
async def delete_experiment(
    workspace_id: str,
    unique_id: str,
    remote_bucket_name: str = Depends(get_user_remote_bucket_name),
):
    try:
        await ExptDataWriter(
            remote_bucket_name,
            workspace_id,
            unique_id,
        ).delete_data()
        return True
    except RemoteStorageLockError as e:
        logger.error(e)
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(e))
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="can not delete record.",
        )


@router.post(
    "/delete/{workspace_id}",
    response_model=bool,
    dependencies=[Depends(is_workspace_owner)],
)
async def delete_experiment_list(
    workspace_id: str,
    deleteItem: DeleteItem,
    remote_bucket_name: str = Depends(get_user_remote_bucket_name),
):
    try:
        for unique_id in deleteItem.uidList:
            await ExptDataWriter(
                remote_bucket_name,
                workspace_id,
                unique_id,
            ).delete_data()
        return True
    except RemoteStorageLockError as e:
        logger.error(e)
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(e))
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="can not delete record.",
        )


@router.get(
    "/download/config/{workspace_id}/{unique_id}",
    dependencies=[Depends(is_workspace_available)],
)
async def download_config_experiment(workspace_id: str, unique_id: str):
    config_filepath = join_filepath(
        [DIRPATH.OUTPUT_DIR, workspace_id, unique_id, DIRPATH.SNAKEMAKE_CONFIG_YML]
    )
    if os.path.exists(config_filepath):
        return FileResponse(config_filepath)
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="file not found"
        )


@router.get(
    "/sync_remote/{workspace_id}/{unique_id}",
    response_model=bool,
    dependencies=[Depends(is_workspace_available)],
)
async def sync_remote_experiment(
    workspace_id: str,
    unique_id: str,
    remote_bucket_name: str = Depends(get_user_remote_bucket_name),
):
    try:
        async with RemoteStorageReader(
            remote_bucket_name, workspace_id, unique_id
        ) as remote_storage_controller:
            result = await remote_storage_controller.download_experiment(
                workspace_id, unique_id
            )

        if not result:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return result

    except HTTPException as e:
        logger.error(e)
        raise e
    except RemoteStorageLockError as e:
        logger.error(e)
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(e))
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="sync remote experiment failed",
        )
