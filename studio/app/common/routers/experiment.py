import os
from glob import glob
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlmodel import Session

from studio.app.common.core.experiment.experiment import ExptConfig
from studio.app.common.core.experiment.experiment_reader import ExptConfigReader
from studio.app.common.core.experiment.experiment_writer import ExptDataWriter
from studio.app.common.core.logger import AppLogger
from studio.app.common.core.utils.filepath_creater import join_filepath
from studio.app.common.core.workflow.workflow_runner import WorkflowRunner
from studio.app.common.core.workspace.workspace_dependencies import (
    is_workspace_available,
    is_workspace_owner,
)
from studio.app.common.core.workspace.workspace_services import WorkspaceService
from studio.app.common.db.database import get_db
from studio.app.common.schemas.experiment import CopyItem, DeleteItem, RenameItem
from studio.app.dir_path import DIRPATH

router = APIRouter(prefix="/experiments", tags=["experiments"])

logger = AppLogger.get_logger()


@router.get(
    "/{workspace_id}",
    response_model=Dict[str, ExptConfig],
    dependencies=[Depends(is_workspace_available)],
)
async def get_experiments(workspace_id: str):
    exp_config = {}
    config_paths = glob(
        join_filepath([DIRPATH.OUTPUT_DIR, workspace_id, "*", DIRPATH.EXPERIMENT_YML])
    )
    for path in config_paths:
        try:
            config = ExptConfigReader.read(path)
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
async def rename_experiment(workspace_id: str, unique_id: str, item: RenameItem):
    config = ExptDataWriter(
        workspace_id,
        unique_id,
    ).rename(item.new_name)
    try:
        config.nodeDict = []
        config.edgeDict = []

        return config

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
    workspace_id: str, unique_id: str, db: Session = Depends(get_db)
):
    try:
        WorkspaceService.delete_workspace_experiment(
            db, workspace_id, unique_id, auto_commit=True
        )

        return True

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
    workspace_id: str, deleteItem: DeleteItem, db: Session = Depends(get_db)
):
    try:
        for unique_id in deleteItem.uidList:
            WorkspaceService.delete_workspace_experiment(
                db, workspace_id, unique_id, auto_commit=True
            )

        return True
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
async def copy_experiment_list(workspace_id: str, copyItem: CopyItem):
    logger = AppLogger.get_logger()
    logger.info(f"workspace_id: {workspace_id}, copyItem: {copyItem}")
    created_unique_ids = []  # Keep track of successfully created unique IDs
    try:
        for unique_id in copyItem.uidList:
            logger.info(f"copying item with unique_id of {unique_id}")
            new_unique_id = WorkflowRunner.create_workflow_unique_id()
            ExptDataWriter(
                workspace_id,
                unique_id,
            ).copy_data(new_unique_id)
            created_unique_ids.append(new_unique_id)  # Record successful copy
        return True
    except Exception as e:
        logger.error(e, exc_info=True)
        # Clean up partially created data
        for created_unique_id in created_unique_ids:
            try:
                ExptDataWriter(
                    workspace_id,
                    created_unique_id,
                ).delete_data()
                logger.info(f"Cleaned up data for unique_id: {created_unique_id}")
            except Exception as cleanup_error:
                logger.error(cleanup_error, exc_info=True)
                logger.error(
                    f"Failed to clean up data for unique_id: {created_unique_id}",
                    exc_info=True,
                )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to copy record. Partially created files have been removed.",
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
