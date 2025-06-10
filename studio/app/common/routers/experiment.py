import os
from dataclasses import asdict
from glob import glob
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlmodel import Session

from studio.app.common.core.auth.auth_dependencies import get_user_remote_bucket_name
from studio.app.common.core.experiment.experiment import ExptConfig, ExptExtConfig
from studio.app.common.core.experiment.experiment_reader import ExptConfigReader
from studio.app.common.core.experiment.experiment_services import ExperimentService
from studio.app.common.core.experiment.experiment_writer import ExptDataWriter
from studio.app.common.core.logger import AppLogger
from studio.app.common.core.snakemake.snakemake_reader import SmkConfigReader
from studio.app.common.core.storage.remote_storage_controller import (
    RemoteStorageController,
    RemoteStorageLockError,
    RemoteStorageReader,
    RemoteStorageSimpleReader,
    RemoteSyncStatusFileUtil,
)
from studio.app.common.core.workspace.workspace_dependencies import (
    is_workspace_available,
    is_workspace_owner,
)
from studio.app.common.db.database import get_db
from studio.app.common.schemas.experiment import CopyItem, DeleteItem, RenameItem

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
    config_paths = glob(ExptConfigReader.get_config_yaml_wild_path(workspace_id))

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
        config_paths = glob(ExptConfigReader.get_config_yaml_wild_path(workspace_id))

    for path in config_paths:
        try:
            config = ExptConfigReader.read_from_path(path)

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
                config = ExptExtConfig(**asdict(config))
                config.is_remote_synced = is_remote_synced
            else:
                # extend config to ExptExtConfig
                # Always flag as synchronized if remote storage is unused.
                config = ExptExtConfig(**asdict(config))
                config.is_remote_synced = True

            if ExptConfigReader.validate_experiment_config(config):
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
    db: Session = Depends(get_db),
    remote_bucket_name: str = Depends(get_user_remote_bucket_name),
):
    try:
        result = await ExperimentService.delete_experiment(
            db, remote_bucket_name, workspace_id, unique_id, auto_commit=True
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete experiment [{workspace_id}/{unique_id}]",
            )

        return result

    except RemoteStorageLockError as e:
        logger.error(e)
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(e))
    except HTTPException as e:
        logger.error(e, exc_info=True)
        raise e
    except Exception as e:
        logger.error("Deletion failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete experiment and its associated data.",
        )


@router.post(
    "/delete/{workspace_id}",
    response_model=bool,
    dependencies=[Depends(is_workspace_owner)],
)
async def delete_experiment_list(
    workspace_id: str,
    deleteItem: DeleteItem,
    db: Session = Depends(get_db),
    remote_bucket_name: str = Depends(get_user_remote_bucket_name),
):
    try:
        deleted_statuses = {}

        for unique_id in deleteItem.uidList:
            result = await ExperimentService.delete_experiment(
                db, remote_bucket_name, workspace_id, unique_id, auto_commit=True
            )
            deleted_statuses[unique_id] = result

        deleted_failed_statuses = [
            id for id, res in deleted_statuses.items() if not res
        ]

        if deleted_failed_statuses:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    f"Failed to delete some experiments "
                    f"[{workspace_id}] / {deleted_failed_statuses}"
                ),
            )

        return True

    except RemoteStorageLockError as e:
        logger.error(e)
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(e))
    except HTTPException as e:
        logger.error(e, exc_info=True)
        raise e
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="can not delete record.",
        )


@router.post(
    "/copy/{workspace_id}",
    response_model=bool,
    dependencies=[Depends(is_workspace_owner)],
)
async def copy_experiment_list(
    workspace_id: str,
    copyItem: CopyItem,
    db: Session = Depends(get_db),
    remote_bucket_name: str = Depends(get_user_remote_bucket_name),
):
    try:
        await ExperimentService.copy_experiment(
            db, remote_bucket_name, workspace_id, copyItem=copyItem
        )
        return True

    except Exception as e:
        logger.error("Copy failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to copy experiment and its associated data.",
        )


@router.get(
    "/download/config/{workspace_id}/{unique_id}",
    dependencies=[Depends(is_workspace_available)],
)
async def download_config_experiment(workspace_id: str, unique_id: str):
    config_filepath = SmkConfigReader.get_config_yaml_path(workspace_id, unique_id)
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="record not found"
            )
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
