import copy
from typing import Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from studio.app.common.core.logger import AppLogger
from studio.app.common.core.workflow.workflow import (
    DataFilterParam,
    Message,
    NodeItem,
    NodeType,
    RunItem,
)
from studio.app.common.core.workflow.workflow_filter import WorkflowNodeDataFilter
from studio.app.common.core.workflow.workflow_result import (
    WorkflowMonitor,
    WorkflowResult,
)
from studio.app.common.core.workflow.workflow_runner import WorkflowRunner
from studio.app.common.core.workspace.workspace_data_capacity_services import (
    WorkspaceDataCapacityService,
)
from studio.app.common.core.workspace.workspace_dependencies import (
    is_workspace_available,
    is_workspace_owner,
)
from studio.app.const import FILETYPE

router = APIRouter(prefix="/run", tags=["run"])

logger = AppLogger.get_logger()


@router.post(
    "/{workspace_id}",
    response_model=str,
    dependencies=[Depends(is_workspace_owner)],
)
async def run(workspace_id: str, runItem: RunItem, background_tasks: BackgroundTasks):
    try:
        unique_id = WorkflowRunner.create_workflow_unique_id()
        WorkflowRunner(workspace_id, unique_id, runItem).run_workflow(background_tasks)

        logger.info("run snakemake")

        return unique_id

    except KeyError as e:
        logger.error(e, exc_info=True)
        # Pass through the specific error message for KeyErrors
        raise HTTPException(
            # Changed to 422 since it's a client configuration issue
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e).strip('"'),  # Remove quotes from the KeyError message
        )

    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run workflow.",
        )


@router.post(
    "/{workspace_id}/{uid}",
    response_model=str,
    dependencies=[Depends(is_workspace_owner)],
)
async def run_id(
    workspace_id: str, uid: str, runItem: RunItem, background_tasks: BackgroundTasks
):
    try:
        WorkflowRunner(workspace_id, uid, runItem).run_workflow(background_tasks)

        logger.info("run snakemake")
        logger.info("forcerun list: %s", runItem.forceRunList)

        return uid

    except Exception as e:
        # Check if this is a KeyError with a specific workflow yaml error message
        if isinstance(e, KeyError) and "Workflow yaml error" in str(e):
            logger.error(f"YAML validation error: {e}", exc_info=True)
            # Return 422 for YAML validation errors
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Workflow yaml error, see FAQ",
            )
        else:
            # Keep original error handling for other errors
            logger.error(e, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to run workflow.",
            )


@router.post(
    "/result/{workspace_id}/{uid}",
    response_model=Dict[str, Message],
    dependencies=[Depends(is_workspace_available)],
)
async def run_result(
    workspace_id: str,
    uid: str,
    nodeDict: NodeItem,
    background_tasks: BackgroundTasks,
):
    try:
        res = WorkflowResult(workspace_id, uid).observe(nodeDict.pendingNodeIdList)
        if res:
            background_tasks.add_task(
                WorkspaceDataCapacityService.update_experiment_data_usage,
                workspace_id,
                uid,
            )
        return res
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to result workflow.",
        )


@router.post(
    "/cancel/{workspace_id}/{uid}",
    response_model=bool,
    dependencies=[Depends(is_workspace_owner)],
)
async def cancel_run(workspace_id: str, uid: str):
    try:
        return WorkflowMonitor(workspace_id, uid).cancel_run()
    except HTTPException as e:
        logger.error(e)
        raise e
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cencel workflow.",
        )


@router.post("/filter/{workspace_id}/{uid}/{node_id}", response_model=bool)
async def apply_filter(
    workspace_id: str,
    uid: str,
    node_id: str,
    background_tasks: BackgroundTasks,
    params: Optional[DataFilterParam] = None,
):
    try:
        WorkflowNodeDataFilter(
            workspace_id=workspace_id, unique_id=uid, node_id=node_id
        ).filter_node_data(params)

        background_tasks.add_task(
            WorkspaceDataCapacityService.update_experiment_data_usage, workspace_id, uid
        )

        return True
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to filter data.",
        )


# TODO: 検証バージョン コード
@router.post(
    "/util/batch_run/{workspace_id}",
    response_model=str,
    dependencies=[Depends(is_workspace_owner)],
)
async def batch_run(
    workspace_id: str, runItem: RunItem, background_tasks: BackgroundTasks
):
    try:
        unique_id = 999

        import pprint

        # print("============= runItem:")
        # pprint.pprint(runItem.nodeDict.items())

        run_items = []

        # Batch Input Data を検索
        # TODO:
        # target_images =
        #   ["dev_mouse2p_short_image.tiff", "dev_mouse2p_long_image.tiff"]
        target_images = []
        for node_id, node in runItem.nodeDict.items():
            if node.type == "BatchImageFileNode":  # TODO: 要定数化
                target_images = node.data.path
                break

        # TODO: target_images がない場合は assertion

        print("========================== target_images:", target_images)

        # workflow実行対象データ（RunItem）を構築
        for idx, image in enumerate(target_images):
            new_run_item = copy.deepcopy(runItem)

            for node_id, node in new_run_item.nodeDict.items():
                # if node.type == NodeType.IMAGE:
                if node.type == "BatchImageFileNode":
                    new_run_item.name = f"{new_run_item.name} ({idx})"

                    new_run_item.nodeDict[node_id].data.path = [image]
                    new_run_item.nodeDict[node_id].data.fileType = FILETYPE.IMAGE
                    new_run_item.nodeDict[node_id].data.label = image
                    new_run_item.nodeDict[node_id].type = (
                        NodeType.IMAGE
                    )  # ※node typeを、batch type から normal type へ、ここで強制置換
                    break
            run_items.append(new_run_item)

        pprint.pprint(run_items)

        # target data 分のworkflowを実行
        for run_item in run_items:
            unique_id = WorkflowRunner.create_workflow_unique_id()
            WorkflowRunner(workspace_id, unique_id, run_item).run_workflow(
                background_tasks
            )

        last_unique_id = unique_id  # TODO: dummy code

        logger.info("run snakemake")

        return last_unique_id

    except KeyError as e:
        logger.error(e, exc_info=True)
        # Pass through the specific error message for KeyErrors
        raise HTTPException(
            # Changed to 422 since it's a client configuration issue
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e).strip('"'),  # Remove quotes from the KeyError message
        )

    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run workflow.",
        )
